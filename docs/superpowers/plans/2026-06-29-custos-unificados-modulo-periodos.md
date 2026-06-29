# Custos unificados por grupo + módulo de períodos (Previsão × Realizado) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** No detalhe da obra → aba **Financeiro**, ao clicar numa etapa, colapsar as linhas de custo recorrentes (hoje "uma linha por mês") numa **linha por grupo `(descrição-base, fonte)`**, e abrir um **modal** com os períodos em duas abas — **Previsão** (campo `valor`) e **Realizado** (novo campo `valor_realizado`, lançamento manual) — alimentando KPI, Curva S e caixa.

**Architecture:** Reaproveita `ObraServicoCustoItem` como "uma linha por período" (Abordagem A da spec — sem tabelas novas). Backend ganha uma coluna `valor_realizado` (migração **202**), passa a gravar a **descrição-base** sem o sufixo "(mês/aa)" (o rótulo do período é derivado das datas no front), expõe `valor_realizado` no painel, aceita-o no endpoint de persistência e o soma aos indicadores. O **agrupamento `(descricao, fonte)` e o modal são feitos no front-end** a partir da lista plana de itens — o backend continua devolvendo/recebendo períodos individuais.

**Tech Stack:** Flask + SQLAlchemy (Postgres), migrações idempotentes caseiras em `migrations.py`, front-end vanilla JS + Bootstrap 5 (modal) + Chart.js, testes `pytest`.

## Global Constraints

- **Obra-piloto:** Baia. Invariantes financeiros que NÃO podem mudar (previsto não muda; realizado começa em 0): `veks 800.960` · `fat 550.775` · `lucro 24.976` · `imposto 128.903` · `contrato 1.505.613,76` · `data_fim 08/10`.
- **Migração 202** — número livre confirmado (a 201 é `Obra.regime_medicao`). Idempotente, padrão do repo: `ADD COLUMN IF NOT EXISTS` (não checar `information_schema` manualmente — o padrão recente usa `IF NOT EXISTS`, ver migração 200/201).
- **Realizado = lançamento manual** nesta versão. Modo híbrido (puxar de RDO/compras) é **fora de escopo** — só deixar a costura pronta.
- **Sem tratamento de duplicação:** RDO/compras não são vinculados a etapas, então `realizado_por_etapa` (via `GestaoCustoFilho`) é ~0 para estas etapas; `valor_realizado` é **aditivo** ao pipeline existente.
- `valor` continua sendo o **previsto** por período; `valor_realizado` é `Numeric(15,2) NOT NULL DEFAULT 0`.
- **Identidade do grupo** (linha unificada) = par **(`descricao`, `fonte`)** dentro da mesma OSC.
- **Fora de escopo:** modo híbrido; vincular RDO/compras a etapas; qualquer mudança no cronograma físico, RDO ou portal (custo de período continua fora deles).
- Suíte de regressão (rodar após cada task):
  ```
  python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q
  ```

---

## File Structure

| Arquivo | Responsabilidade | Mudança |
|---|---|---|
| `models.py` (`ObraServicoCustoItem`, ~l.5700) | ORM da linha/período de custo | **Modificar** — coluna `valor_realizado` |
| `migrations.py` (registry ~l.4001; defs perto da 201, ~l.13675) | Migração de schema + data-migration | **Modificar** — `_migration_202_osc_item_valor_realizado` |
| `services/importacao_fisico_financeiro.py` (`_add_linhas_de_meses`, l.43) | Importa linhas mensais da Planilha1 | **Modificar** — descrição vira nome-base (sem sufixo) |
| `services/cronograma_fisico_financeiro.py` (`painel_financeiro` l.482; `curva_realizado` l.563; `realizado_por_etapa` l.583) | Monta painel/KPI/Curva S; expõe itens | **Modificar** — expor `valor_realizado`; somar realizado manual aos indicadores; helper novo `realizado_manual_por_osc` |
| `views/obras.py` (`financeiro_etapa_itens`, l.2136) | Persiste itens da etapa (substitui tudo) | **Modificar** — aceitar/gravar `valor_realizado` |
| `static/js/financeiro_obra.js` (`showEtapa`, `etapaLinhaHTML`, l.65-148) | UI viva da etapa | **Modificar** — tabela agrupada + modal com abas |
| `templates/obras/detalhes_obra_profissional.html` (pane `#tab-financeiro`) | Host do painel | **Modificar** — markup do modal Bootstrap |
| `tests/test_painel_financeiro.py` | Testes de painel/endpoint | **Modificar** — novos testes |
| `tests/test_importacao_fisico_financeiro.py` | Testes de importação | **Modificar** — assert descrição sem sufixo |

---

## Task 1: Coluna `valor_realizado` (modelo + migração 202)

**Files:**
- Modify: `models.py:5711-5717` (classe `ObraServicoCustoItem`)
- Modify: `migrations.py:4001` (registry) e perto de `migrations.py:13695` (nova função)
- Test: `tests/test_painel_financeiro.py`

**Interfaces:**
- Produces: `ObraServicoCustoItem.valor_realizado` — `db.Numeric(15, 2)`, `nullable=False`, `default=0`. Lido/escrito como `Decimal`.
- Produces: migração `202` registrada como `(202, "<desc>", _migration_202_osc_item_valor_realizado)`.

- [ ] **Step 1: Write the failing test**

Adicionar ao final de `tests/test_painel_financeiro.py`:

```python
@pytest.mark.integration
def test_osc_item_tem_valor_realizado():
    from models import ObraServicoCustoItem
    cols = {c.name for c in ObraServicoCustoItem.__table__.columns}
    assert 'valor_realizado' in cols


@pytest.mark.integration
def test_osc_item_valor_realizado_default_zero():
    from models import ObraServicoCusto, ObraServicoCustoItem, Obra, Usuario
    from decimal import Decimal
    with app.app_context():
        aid = _novo_admin()
        obra = Obra(nome='T-vr', admin_id=aid)
        db.session.add(obra); db.session.flush()
        osc = ObraServicoCusto(obra_id=obra.id, admin_id=aid, nome='E1')
        db.session.add(osc); db.session.flush()
        it = ObraServicoCustoItem(
            obra_servico_custo_id=osc.id, admin_id=aid,
            descricao='Escritório', valor=Decimal('100'), fonte='veks', ordem=0)
        db.session.add(it); db.session.commit()
        assert Decimal(str(it.valor_realizado or 0)) == Decimal('0')
```

> `ObraServicoCusto` exige os mesmos campos NOT NULL do construtor existente — se este `ObraServicoCusto(...)` falhar por coluna faltando, copiar os kwargs mínimos de um teste já existente no mesmo arquivo (ex.: `test_endpoint_etapa_itens_substitui_e_recalcula`) que importa uma obra completa. Preferir, se mais simples, importar o fixture e pegar um `osc` real como naqueles testes.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_painel_financeiro.py::test_osc_item_tem_valor_realizado -v`
Expected: FAIL — `AssertionError` (coluna ainda não existe no modelo).

- [ ] **Step 3: Add the model column**

Em `models.py`, dentro de `class ObraServicoCustoItem`, logo após a linha `valor = db.Column(db.Numeric(15, 2), nullable=False, default=0)` (l.5712):

```python
    valor = db.Column(db.Numeric(15, 2), nullable=False, default=0)  # previsto por período
    valor_realizado = db.Column(db.Numeric(15, 2), nullable=False, default=0)  # realizado manual por período (spec 2026-06-29)
```

- [ ] **Step 4: Add the migration function**

Em `migrations.py`, logo após `_migration_201_obra_regime_medicao` (termina ~l.13695), adicionar:

```python
def _migration_202_osc_item_valor_realizado():
    """Custos unificados — realizado manual por período: coluna valor_realizado em
    obra_servico_custo_item. Data-migration: remove o sufixo '(mês/aa)' das descrições
    para que os períodos existentes agrupem por (descricao, fonte). Idempotente.
    Ver spec 2026-06-29-custos-unificados-modulo-periodos-design."""
    from sqlalchemy import text as sa_text
    try:
        with db.engine.begin() as conn:
            conn.execute(sa_text(
                "ALTER TABLE obra_servico_custo_item ADD COLUMN IF NOT EXISTS "
                "valor_realizado NUMERIC(15,2) NOT NULL DEFAULT 0"))
            # Data-migration: tira ' (jan/26)'... do fim da descrição (case-insensitive).
            conn.execute(sa_text(r"""
                UPDATE obra_servico_custo_item
                SET descricao = regexp_replace(
                    descricao,
                    ' \((jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)/[0-9]{2}\)$',
                    '', 'i')
                WHERE descricao ~* ' \((jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)/[0-9]{2}\)$'
            """))
        logger.info("[Migration 202] obra_servico_custo_item.valor_realizado + strip sufixo (mês/aa).")
    except Exception as e:
        logger.error(f"[Migration 202] Falha: {e}", exc_info=True)
        raise
```

- [ ] **Step 5: Register the migration**

Em `migrations.py`, na lista `migrations_to_run` (logo após a linha 201, l.4001), adicionar:

```python
            (201, "Obra.regime_medicao (fixa|percentual) + backfill percentual p/ obras com medição física", _migration_201_obra_regime_medicao),
            (202, "Custos unificados — valor_realizado por período + strip sufixo (mês/aa) das descrições", _migration_202_osc_item_valor_realizado),
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_painel_financeiro.py::test_osc_item_tem_valor_realizado tests/test_painel_financeiro.py::test_osc_item_valor_realizado_default_zero -v`
Expected: PASS (2 passed). O schema de teste é criado via `db.create_all()` a partir do modelo, então a coluna já existe sem rodar a migração.

- [ ] **Step 7: Run the full regression suite**

Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: verde (baseline + 2 novos).

- [ ] **Step 8: Commit**

```bash
git add models.py migrations.py tests/test_painel_financeiro.py
git commit -m "feat(baia): valor_realizado por período + migração 202 (strip sufixo mês/aa)"
```

---

## Task 2: Descrição vira nome-base na importação (sem sufixo "(mês/aa)")

**Files:**
- Modify: `services/importacao_fisico_financeiro.py:43-58` (`_add_linhas_de_meses`)
- Test: `tests/test_importacao_fisico_financeiro.py`

**Interfaces:**
- Consumes: nada novo.
- Produces: itens importados de meses passam a ter `descricao == nome` (nome-base, sem `(rotulo)`); `data_inicio`/`data_fim` continuam datados no mês (o front deriva "jun/26" das datas).

- [ ] **Step 1: Write the failing test**

Adicionar a `tests/test_importacao_fisico_financeiro.py` (seguir o estilo dos testes existentes que importam o fixture; importar `app`, `db`, `_novo_admin` como os demais testes do arquivo):

```python
@pytest.mark.integration
def test_importacao_descricao_periodo_sem_sufixo_mes():
    """Linhas de custo de período (INDIRETOS) gravam a descrição-base, sem '(mês/aa)'."""
    import re, json, os
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import ObraServicoCusto, ObraServicoCustoItem
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        osc_ids = [o.id for o in ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).all()]
        itens = ObraServicoCustoItem.query.filter(
            ObraServicoCustoItem.obra_servico_custo_id.in_(osc_ids)).all()
        sufixo = re.compile(r' \((jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)/\d{2}\)$', re.I)
        assert itens, "esperado ao menos um item importado"
        assert not any(sufixo.search(it.descricao) for it in itens), \
            "nenhuma descrição deve terminar com '(mês/aa)'"
        # ainda existem múltiplos períodos do mesmo grupo (mesma descricao+fonte)
        from collections import Counter
        chaves = Counter((it.descricao, it.fonte) for it in itens)
        assert any(c > 1 for c in chaves.values()), \
            "esperado ao menos um grupo com vários períodos (ex.: Escritório veks)"
```

> Se o arquivo de teste não tiver helper `_novo_admin`, copiar o padrão de bootstrap de admin usado no topo de `tests/test_painel_financeiro.py` (mesmo fixture). Ajustar imports ao cabeçalho existente do arquivo.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_importacao_fisico_financeiro.py::test_importacao_descricao_periodo_sem_sufixo_mes -v`
Expected: FAIL — descrições ainda contêm "(jun/26)" etc.

- [ ] **Step 3: Drop the suffix in `_add_linhas_de_meses`**

Em `services/importacao_fisico_financeiro.py`, trocar o corpo de `_add_linhas_de_meses` (l.48-57) para usar o nome-base na `descricao` e manter a janela datada no mês:

```python
    from app import db
    for chave in sorted(meses):
        valor = Decimal(str(meses[chave] or 0))
        if valor == 0:
            continue
        di, df, _rotulo = _mes_bounds(chave)  # rótulo é derivado das datas na UI
        db.session.add(Model(
            obra_servico_custo_id=osc.id, admin_id=admin_id,
            descricao=nome[:200], valor=valor, fonte=fonte,
            ordem=ordem, data_inicio=di, data_fim=df))
        ordem += 1
    return ordem
```

> Mudança mínima: `descricao=f"{nome} ({rotulo})"[:200]` → `descricao=nome[:200]`, e `rotulo` agora é descartado (`_rotulo`). A docstring da função (l.44-46) ainda menciona "nomeada 'nome (abrev/yy)'"; atualizar para "nomeada com o nome-base, datada no mês".

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_importacao_fisico_financeiro.py::test_importacao_descricao_periodo_sem_sufixo_mes -v`
Expected: PASS.

- [ ] **Step 5: Update any existing assert that expected the suffix**

Run: `grep -rn "jun/26\|(jun/\|abrev/yy\|/26)" tests/ services/`
Se algum teste/asserção existente esperava o sufixo na descrição, ajustar para o nome-base. (Não inventar; só corrigir o que quebrar.)

- [ ] **Step 6: Run the full regression suite**

Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: verde. Confirmar invariantes: veks 800.960 / fat 550.775 inalterados (a mudança é só de rótulo, não de valor).

- [ ] **Step 7: Commit**

```bash
git add services/importacao_fisico_financeiro.py tests/test_importacao_fisico_financeiro.py
git commit -m "refactor(baia): descrição do período é o nome-base (rótulo mês/aa derivado das datas)"
```

---

## Task 3: Expor `valor_realizado` no painel e somá-lo aos indicadores

**Files:**
- Modify: `services/cronograma_fisico_financeiro.py:519-522` (dict do item no painel)
- Modify: `services/cronograma_fisico_financeiro.py:563-597` (`curva_realizado`, `realizado_por_etapa`) + helper novo
- Modify: `services/cronograma_fisico_financeiro.py:546-547` (KPI `custo_realizado`)
- Test: `tests/test_painel_financeiro.py`

**Interfaces:**
- Produces: `painel_financeiro(obra)["etapas"][i]["itens"][j]["valor_realizado"]` — `Decimal`.
- Produces: `realizado_manual_por_osc(obra) -> dict[int, Decimal]` — Σ `valor_realizado` por `obra_servico_custo_id`.
- Modifies: `realizado_por_etapa(obra)` passa a **somar** `realizado_manual_por_osc` ao realizado por OSC (`GestaoCustoFilho` + manual).
- Modifies: `curva_realizado(obra)` passa a **somar** a contribuição mensal de `valor_realizado` (por mês de `data_inicio`).
- Modifies: KPI `custo_realizado` passa a incluir Σ de todo `valor_realizado` da obra.

- [ ] **Step 1: Write the failing tests**

Adicionar a `tests/test_painel_financeiro.py`:

```python
@pytest.mark.integration
def test_painel_itens_expoem_valor_realizado():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import painel_financeiro
    from models import Obra
    import json, os
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        p = painel_financeiro(Obra.query.get(oid))
        for e in p['etapas']:
            for it in e['itens']:
                assert 'valor_realizado' in it


@pytest.mark.integration
def test_realizado_manual_entra_no_realizado_da_etapa_e_kpi():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import painel_financeiro
    from models import Obra, ObraServicoCusto, ObraServicoCustoItem
    from decimal import Decimal
    import json, os
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        obra = Obra.query.get(oid)
        kpi_antes = painel_financeiro(obra)['kpis']['custo_realizado']
        # lança 7.000 de realizado manual num período qualquer
        osc = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first()
        it = (ObraServicoCustoItem.query
              .filter_by(obra_servico_custo_id=osc.id).order_by(ObraServicoCustoItem.ordem).first())
        it.valor_realizado = Decimal('7000')
        db.session.commit()
        p = painel_financeiro(Obra.query.get(oid))
        # KPI custo realizado cresceu 7.000
        assert abs(float(p['kpis']['custo_realizado']) - (float(kpi_antes) + 7000)) < 1
        # realizado da etapa dona do item reflete os 7.000 (era ~0 para estas etapas)
        et = next(e for e in p['etapas'] if e['osc_id'] == osc.id)
        assert float(et['realizado']) >= 7000 - 1


@pytest.mark.integration
def test_curva_realizado_inclui_valor_realizado_manual():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import curva_realizado
    from models import Obra, ObraServicoCusto, ObraServicoCustoItem
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
        it = (ObraServicoCustoItem.query
              .filter_by(obra_servico_custo_id=osc.id).order_by(ObraServicoCustoItem.ordem).first())
        it.data_inicio = date(2026, 7, 15)
        it.valor_realizado = Decimal('3000')
        db.session.commit()
        out = curva_realizado(Obra.query.get(oid))
        assert out.get('2026-07', Decimal('0')) >= Decimal('3000')
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_painel_financeiro.py::test_painel_itens_expoem_valor_realizado tests/test_painel_financeiro.py::test_realizado_manual_entra_no_realizado_da_etapa_e_kpi tests/test_painel_financeiro.py::test_curva_realizado_inclui_valor_realizado_manual -v`
Expected: FAIL — `valor_realizado` ausente no painel; KPI/curva ainda não somam o manual.

- [ ] **Step 3: Expose `valor_realizado` in the painel item dict**

Em `services/cronograma_fisico_financeiro.py`, no laço que monta `itens_por_osc` (l.519-522), incluir o campo:

```python
        for it in linhas:
            itens_por_osc.setdefault(it.obra_servico_custo_id, []).append(
                {"id": it.id, "descricao": it.descricao, "valor": it.valor,
                 "valor_realizado": it.valor_realizado, "fonte": it.fonte,
                 "data_inicio": it.data_inicio, "data_fim": it.data_fim})
```

- [ ] **Step 4: Add the `realizado_manual_por_osc` helper**

Em `services/cronograma_fisico_financeiro.py`, adicionar logo **antes** de `realizado_por_etapa` (antes da l.583):

```python
def realizado_manual_por_osc(obra) -> dict:
    """Σ valor_realizado (lançamento manual por período) por obra_servico_custo_id.
    Realizado manual da spec 2026-06-29 — aditivo ao realizado de GestaoCustoFilho."""
    from models import ObraServicoCusto, ObraServicoCustoItem
    osc_ids = [o.id for o in ObraServicoCusto.query.filter_by(
        obra_id=obra.id, admin_id=obra.admin_id).all()]
    out: dict = {}
    if not osc_ids:
        return out
    linhas = ObraServicoCustoItem.query.filter(
        ObraServicoCustoItem.obra_servico_custo_id.in_(osc_ids)).all()
    for l in linhas:
        vr = Decimal(str(l.valor_realizado or 0))
        if vr:
            out[l.obra_servico_custo_id] = out.get(l.obra_servico_custo_id, Decimal("0")) + vr
    return out
```

- [ ] **Step 5: Merge manual realizado into `realizado_por_etapa`**

Em `realizado_por_etapa` (l.583-597), antes do `return out`, somar o manual:

```python
    for osc_id, valor in rows:
        if osc_id is None:
            continue
        out[osc_id] = out.get(osc_id, Decimal("0")) + Decimal(valor or 0)
    for osc_id, vr in realizado_manual_por_osc(obra).items():
        out[osc_id] = out.get(osc_id, Decimal("0")) + vr
    return out
```

- [ ] **Step 6: Add monthly manual contribution to `curva_realizado`**

Em `curva_realizado` (l.563-580), antes do `return out`, somar `valor_realizado` por mês de `data_inicio`:

```python
    for dt, valor in rows:
        if not dt:
            continue
        chave = f"{dt.year:04d}-{dt.month:02d}"
        out[chave] = out.get(chave, Decimal("0")) + Decimal(valor or 0)
    # realizado manual por período (spec 2026-06-29): faseado pelo mês de data_inicio
    from models import ObraServicoCusto, ObraServicoCustoItem
    osc_ids = [o.id for o in ObraServicoCusto.query.filter_by(
        obra_id=obra.id, admin_id=obra.admin_id).all()]
    if osc_ids:
        for l in (ObraServicoCustoItem.query
                  .filter(ObraServicoCustoItem.obra_servico_custo_id.in_(osc_ids)).all()):
            vr = Decimal(str(l.valor_realizado or 0))
            if vr and l.data_inicio:
                chave = f"{l.data_inicio.year:04d}-{l.data_inicio.month:02d}"
                out[chave] = out.get(chave, Decimal("0")) + vr
    return out
```

- [ ] **Step 7: Add manual realizado to the KPI `custo_realizado`**

Em `painel_financeiro`, onde `custo_realizado` é computado (l.546-547), somar o total manual:

```python
    custo_realizado = Decimal(str(resumo.get("total_realizado", 0) or 0))
    custo_realizado += sum(realizado_manual_por_osc(obra).values(), Decimal("0"))
    verba_disponivel = k["recebido_ate_hoje"] - custo_realizado
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `python -m pytest tests/test_painel_financeiro.py::test_painel_itens_expoem_valor_realizado tests/test_painel_financeiro.py::test_realizado_manual_entra_no_realizado_da_etapa_e_kpi tests/test_painel_financeiro.py::test_curva_realizado_inclui_valor_realizado_manual -v`
Expected: PASS (3 passed).

- [ ] **Step 9: Run the full regression suite**

Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: verde. Como `valor_realizado` começa em 0 na importação, os invariantes (custo realizado/verba/curva da Baia) **não mudam** sem lançamento manual.

- [ ] **Step 10: Commit**

```bash
git add services/cronograma_fisico_financeiro.py tests/test_painel_financeiro.py
git commit -m "feat(baia): valor_realizado manual alimenta KPI, realizado por etapa e Curva S"
```

---

## Task 4: Endpoint aceita e grava `valor_realizado`

**Files:**
- Modify: `views/obras.py:2168-2196` (`financeiro_etapa_itens` — parse + persistência)
- Test: `tests/test_painel_financeiro.py`

**Interfaces:**
- Consumes: payload `{"itens": [{descricao, valor, fonte, data_inicio, data_fim, valor_realizado}], "valor_orcado": ...}`.
- Produces: cada `ObraServicoCustoItem` gravado com `valor_realizado` (default 0 se ausente; inválido/negativo → HTTP 400).

- [ ] **Step 1: Write the failing test**

Adicionar a `tests/test_painel_financeiro.py`:

```python
@pytest.mark.integration
def test_endpoint_etapa_itens_persiste_valor_realizado():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Usuario, ObraServicoCusto, ObraServicoCustoItem
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
        r = c.post(f'/obras/{oid}/financeiro/etapa/{osc_id}/itens',
                   json={'itens': [
                       {'descricao': 'Escritório', 'valor': '1000', 'fonte': 'veks',
                        'data_inicio': '2026-07-01', 'data_fim': '2026-07-31',
                        'valor_realizado': '250'}]})
        assert r.status_code == 200
        # valor_realizado negativo → 400
        r2 = c.post(f'/obras/{oid}/financeiro/etapa/{osc_id}/itens',
                    json={'itens': [{'descricao': 'X', 'valor': '1', 'fonte': 'veks',
                                     'valor_realizado': '-5'}]})
        assert r2.status_code == 400
    with app.app_context():
        it = ObraServicoCustoItem.query.filter_by(obra_servico_custo_id=osc_id).one()
        assert Decimal(str(it.valor_realizado)) == Decimal('250')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_painel_financeiro.py::test_endpoint_etapa_itens_persiste_valor_realizado -v`
Expected: FAIL — `valor_realizado` não persiste (fica 0) e payload negativo não é rejeitado.

- [ ] **Step 3: Parse `valor_realizado` in the loop**

Em `views/obras.py`, no laço `for i, it in enumerate(itens)` (l.2169-2181), antes do `novos.append(...)`:

```python
        fonte = 'fat_direto' if it.get('fonte') == 'fat_direto' else 'veks'
        desc = (str(it.get('descricao') or '').strip() or 'Item')[:200]
        vr_raw = it.get('valor_realizado')
        vr = Decimal('0') if vr_raw in (None, '') else _dec(vr_raw)
        if vr is None or vr < 0:
            return jsonify({'erro': 'valor_realizado inválido'}), 400
        novos.append((desc, valor, fonte, i, di, df, vr))
```

- [ ] **Step 4: Persist `valor_realizado`**

Em `views/obras.py`, ajustar o unpack e o `add` (l.2192-2196):

```python
    for desc, valor, fonte, ordem, di, df, vr in novos:
        db.session.add(ObraServicoCustoItem(
            obra_servico_custo_id=osc.id, admin_id=admin_id,
            descricao=desc, valor=valor, fonte=fonte, ordem=ordem,
            data_inicio=di, data_fim=df, valor_realizado=vr))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_painel_financeiro.py::test_endpoint_etapa_itens_persiste_valor_realizado -v`
Expected: PASS.

- [ ] **Step 6: Run the existing endpoint tests (tuple-shape regression)**

Run: `python -m pytest tests/test_painel_financeiro.py -k "etapa_itens" -v`
Expected: PASS — os testes existentes (`...substitui_e_recalcula`, `...persiste_datas`, `...multitenant`) continuam verdes; itens sem `valor_realizado` no payload gravam 0.

- [ ] **Step 7: Run the full regression suite**

Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: verde.

- [ ] **Step 8: Commit**

```bash
git add views/obras.py tests/test_painel_financeiro.py
git commit -m "feat(baia): endpoint de itens da etapa aceita e grava valor_realizado por período"
```

---

## Task 5: Front-end — tabela agrupada por grupo `(descrição, fonte)`

> A partir daqui é UI viva (`static/js/financeiro_obra.js`) e markup do modal. Não há teste pytest; a verificação é render server-side + checagem manual descrita em cada step. Mantém a paridade com a decisão da spec: tabela = uma linha por grupo, com Períodos/Previsto/Realizado e botão `▸` que abre o modal.

**Files:**
- Modify: `static/js/financeiro_obra.js:65-148` (`etapaLinhaHTML`, `showEtapa`)

**Interfaces:**
- Consumes: `et.itens` = lista plana de períodos, cada um `{id, descricao, valor, valor_realizado, fonte, data_inicio, data_fim}` (de Task 3).
- Produces (helpers JS, usados pelo modal na Task 6):
  - `rotuloMes(iso)` → string `"jun/26"` a partir de `data_inicio` (ou `"—"`).
  - `agruparPeriodos(itens)` → `[{descricao, fonte, periodos:[item...], previsto:Number, realizado:Number}]`, ordenado por `descricao` depois `fonte`.
  - `coletarItensDaEtapa()` → lê o estado atual dos grupos/modais e devolve a lista plana `[{descricao, valor, fonte, data_inicio, data_fim, valor_realizado}]` para o POST.

- [ ] **Step 1: Add the grouping + label helpers**

Em `static/js/financeiro_obra.js`, dentro da IIFE (perto do topo, após `BRLk`), adicionar:

```javascript
  var MESES_ABREV = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'];
  function rotuloMes(iso) {
    if (!iso) return '—';
    var s = String(iso).slice(0, 10), m = parseInt(s.slice(5, 7), 10);
    if (!m || m < 1 || m > 12) return '—';
    return MESES_ABREV[m - 1] + '/' + s.slice(2, 4);
  }
  function agruparPeriodos(itens) {
    var mapa = {}, ordem = [];
    (itens || []).forEach(function (it) {
      var fonte = it.fonte === 'fat_direto' ? 'fat_direto' : 'veks';
      var desc = (it.descricao || '').trim();
      var chave = desc + '||' + fonte;
      if (!mapa[chave]) {
        mapa[chave] = { descricao: desc, fonte: fonte, periodos: [], previsto: 0, realizado: 0 };
        ordem.push(chave);
      }
      mapa[chave].periodos.push(it);
      mapa[chave].previsto += Number(it.valor || 0);
      mapa[chave].realizado += Number(it.valor_realizado || 0);
    });
    return ordem.map(function (k) { return mapa[k]; }).sort(function (a, b) {
      return a.descricao.localeCompare(b.descricao) || a.fonte.localeCompare(b.fonte);
    });
  }
```

- [ ] **Step 2: Replace `etapaLinhaHTML` with a grouped-row renderer**

Em `static/js/financeiro_obra.js`, substituir `etapaLinhaHTML` (l.65-82) por um renderizador de **linha de grupo** (uma linha por grupo, com botão `▸`):

```javascript
  function fonteLabel(f) { return f === 'fat_direto' ? 'Fat direto' : 'Veks'; }
  function grupoLinhaHTML(g, idx) {
    return '<tr data-grupo="' + idx + '">' +
      '<td>' + String(g.descricao || '').replace(/</g, '&lt;') + '</td>' +
      '<td>' + fonteLabel(g.fonte) + '</td>' +
      '<td class="text-center">' + g.periodos.length + '</td>' +
      '<td class="text-end" data-grp-previsto>' + BRL(g.previsto) + '</td>' +
      '<td class="text-end" data-grp-realizado>' + BRL(g.realizado) + '</td>' +
      '<td class="text-center"><button type="button" class="btn btn-sm btn-link fin-grp-open p-0" ' +
        'data-grupo="' + idx + '" title="Abrir períodos">&#9656;</button></td>' +
    '</tr>';
  }
```

- [ ] **Step 3: Rewrite `showEtapa` to render the grouped table**

Em `static/js/financeiro_obra.js`, substituir o corpo de `showEtapa` (l.83-148) mantendo o caso `osc_id == null` igual. O estado dos grupos vive em `box._grupos`; o modal (Task 6) edita `box._grupos[idx].periodos` e chama `recalcGrupo(idx)`. O salvar serializa todos os períodos de todos os grupos.

```javascript
  function showEtapa(et) {
    var box = el('fin-etapa-det');
    if (et.osc_id == null) {
      box.innerHTML = '<div class="border rounded p-3 bg-light"><strong>' + et.nome + '</strong>' +
        '<div class="small text-muted mt-1">Etapa sem custo único vinculável — edição indisponível.</div></div>';
      return;
    }
    box._etapa = et;
    box._grupos = agruparPeriodos(et.itens);
    var linhas = box._grupos.map(grupoLinhaHTML).join('') ||
      '<tr><td colspan="6" class="text-muted small">Sem custos lançados.</td></tr>';
    box.innerHTML =
      '<div class="border rounded p-3 bg-light">' +
      '<div class="d-flex justify-content-between mb-2"><strong>' + et.nome +
        (et.tipo === 'periodo' ? ' <span class="badge bg-secondary" title="Custo de período — sem avanço físico, fora do RDO/cronograma">período</span>' : '') +
        '</strong>' +
        '<span>Realizado: <span id="fin-et-real">' + BRL(et.realizado) + '</span>' +
        ' / Previsto: <span id="fin-it-prev">' + BRL(et.previsto) + '</span></span></div>' +
      '<table class="table table-sm align-middle mb-2"><thead><tr>' +
        '<th>Custo</th><th style="width:90px">Fonte</th>' +
        '<th class="text-center" style="width:80px">Períodos</th>' +
        '<th class="text-end" style="width:130px">Previsto</th>' +
        '<th class="text-end" style="width:130px">Realizado</th>' +
        '<th style="width:36px"></th></tr></thead>' +
      '<tbody id="fin-grp-body">' + linhas + '</tbody></table>' +
      '<div class="d-flex justify-content-end">' +
        '<button type="button" id="fin-it-save" class="btn btn-primary btn-sm">Salvar etapa</button>' +
      '</div></div>';

    box.querySelectorAll('.fin-grp-open').forEach(function (btn) {
      btn.addEventListener('click', function () {
        abrirModuloPeriodos(box, parseInt(btn.getAttribute('data-grupo'), 10));
      });
    });
    el('fin-it-save').addEventListener('click', function () { salvarEtapa(box); });
  }

  function recalcGrupo(box, idx) {
    var g = box._grupos[idx];
    g.previsto = g.periodos.reduce(function (s, p) { return s + Number(p.valor || 0); }, 0);
    g.realizado = g.periodos.reduce(function (s, p) { return s + Number(p.valor_realizado || 0); }, 0);
    var tr = box.querySelector('#fin-grp-body tr[data-grupo="' + idx + '"]');
    if (tr) {
      tr.querySelector('[data-grp-previsto]').textContent = BRL(g.previsto);
      tr.querySelector('[data-grp-realizado]').textContent = BRL(g.realizado);
      tr.querySelector('td:nth-child(3)').textContent = g.periodos.length;
    }
    var prev = box._grupos.reduce(function (s, gg) { return s + gg.previsto; }, 0);
    var real = box._grupos.reduce(function (s, gg) { return s + gg.realizado; }, 0);
    el('fin-it-prev').textContent = BRL(prev);
    el('fin-et-real').textContent = BRL(real);
  }

  function coletarItensDaEtapa(box) {
    var itens = [];
    box._grupos.forEach(function (g) {
      g.periodos.forEach(function (p) {
        itens.push({
          descricao: g.descricao,
          fonte: g.fonte,
          valor: String(p.valor || 0),
          valor_realizado: String(p.valor_realizado || 0),
          data_inicio: p.data_inicio ? String(p.data_inicio).slice(0, 10) : '',
          data_fim: p.data_fim ? String(p.data_fim).slice(0, 10) : ''
        });
      });
    });
    return itens;
  }

  function salvarEtapa(box) {
    var et = box._etapa;
    var prevTotal = box._grupos.reduce(function (s, g) { return s + g.previsto; }, 0);
    fetch('/obras/' + OBRA_ID + '/financeiro/etapa/' + et.osc_id + '/itens', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
      body: JSON.stringify({ itens: coletarItensDaEtapa(box), valor_orcado: String(prevTotal) })
    })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (p) { render(p); box.innerHTML = '<div class="text-success small">Salvo e recalculado.</div>'; })
      .catch(function () { box.innerHTML = '<div class="text-danger small">Falha ao salvar.</div>'; });
  }
```

> `abrirModuloPeriodos` é definida na Task 6. Implementar a Task 6 antes de testar o clique no `▸`.

- [ ] **Step 4: Syntax check the JS**

Run: `node --check static/js/financeiro_obra.js`
Expected: sem saída (sintaxe OK). Se `node` não estiver disponível, abrir o app e confirmar que o console não acusa erro de parse ao carregar a aba.

- [ ] **Step 5: Commit (parcial — UI da tabela)**

```bash
git add static/js/financeiro_obra.js
git commit -m "feat(baia): tabela da etapa agrupa custos por (descrição, fonte) com botão de períodos"
```

---

## Task 6: Front-end — modal com abas Previsão e Realizado

**Files:**
- Modify: `static/js/financeiro_obra.js` (nova fn `abrirModuloPeriodos` + render das abas)
- Modify: `templates/obras/detalhes_obra_profissional.html` (markup do modal Bootstrap dentro/perto do pane `#tab-financeiro`)

**Interfaces:**
- Consumes: `box._grupos[idx]` (de Task 5) — `{descricao, fonte, periodos:[{valor, valor_realizado, data_inicio, data_fim}]}`.
- Produces: `abrirModuloPeriodos(box, idx)` — abre o modal, edita `periodos` in-place, e ao fechar/aplicar chama `recalcGrupo(box, idx)`.

- [ ] **Step 1: Add the modal markup to the template**

Em `templates/obras/detalhes_obra_profissional.html`, localizar o pane do painel financeiro:

Run: `grep -n 'id="tab-financeiro"\|fin-etapa-det\|fin-painel' templates/obras/detalhes_obra_profissional.html`

Adicionar, ao final do markup do pane `#tab-financeiro` (antes do `</div>` que fecha o pane), um modal Bootstrap reutilizável:

```html
<div class="modal fade" id="fin-periodos-modal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-lg modal-dialog-scrollable">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title" id="fin-pm-titulo">Períodos</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Fechar"></button>
      </div>
      <div class="modal-body">
        <ul class="nav nav-tabs mb-3" role="tablist">
          <li class="nav-item"><button class="nav-link active" data-bs-toggle="tab"
              data-bs-target="#fin-pm-prev" type="button">Previsão</button></li>
          <li class="nav-item"><button class="nav-link" data-bs-toggle="tab"
              data-bs-target="#fin-pm-real" type="button">Realizado</button></li>
        </ul>
        <div class="tab-content">
          <div class="tab-pane fade show active" id="fin-pm-prev">
            <table class="table table-sm align-middle"><thead><tr>
              <th>Mês</th><th style="width:140px">Início</th><th style="width:140px">Fim</th>
              <th class="text-end" style="width:150px">Previsto (R$)</th><th style="width:32px"></th>
            </tr></thead><tbody id="fin-pm-prev-body"></tbody></table>
            <div class="d-flex justify-content-between">
              <button type="button" id="fin-pm-add" class="btn btn-outline-secondary btn-sm">+ Adicionar período</button>
              <span class="small text-muted">Total previsto: <strong id="fin-pm-prev-total">R$ 0</strong></span>
            </div>
          </div>
          <div class="tab-pane fade" id="fin-pm-real">
            <table class="table table-sm align-middle"><thead><tr>
              <th>Mês</th><th class="text-end" style="width:150px">Realizado (R$)</th>
            </tr></thead><tbody id="fin-pm-real-body"></tbody></table>
            <div class="d-flex justify-content-end">
              <span class="small text-muted">Total realizado: <strong id="fin-pm-real-total">R$ 0</strong></span>
            </div>
          </div>
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">Fechar</button>
        <button type="button" id="fin-pm-aplicar" class="btn btn-primary btn-sm" data-bs-dismiss="modal">Aplicar</button>
      </div>
    </div>
  </div>
</div>
```

- [ ] **Step 2: Implement `abrirModuloPeriodos` in the JS**

Em `static/js/financeiro_obra.js`, adicionar (após `showEtapa`/`recalcGrupo`):

```javascript
  function ultimoDiaMes(ano, mes) { return new Date(ano, mes, 0).getDate(); }
  function periodoRowPrevHTML(p, i) {
    return '<tr data-p="' + i + '">' +
      '<td>' + rotuloMes(p.data_inicio) + '</td>' +
      '<td><input type="date" class="form-control form-control-sm fin-pm-ini" value="' +
        (p.data_inicio ? String(p.data_inicio).slice(0, 10) : '') + '"></td>' +
      '<td><input type="date" class="form-control form-control-sm fin-pm-fim" value="' +
        (p.data_fim ? String(p.data_fim).slice(0, 10) : '') + '"></td>' +
      '<td><input type="number" step="0.01" class="form-control form-control-sm text-end fin-pm-valor" value="' +
        Number(p.valor || 0) + '"></td>' +
      '<td class="text-center"><button type="button" class="btn btn-sm btn-link text-danger fin-pm-del p-0">&times;</button></td>' +
    '</tr>';
  }
  function periodoRowRealHTML(p, i) {
    return '<tr data-p="' + i + '">' +
      '<td>' + rotuloMes(p.data_inicio) + '</td>' +
      '<td><input type="number" step="0.01" class="form-control form-control-sm text-end fin-pm-realval" value="' +
        Number(p.valor_realizado || 0) + '"></td>' +
    '</tr>';
  }
  function abrirModuloPeriodos(box, idx) {
    var g = box._grupos[idx];
    el('fin-pm-titulo').innerHTML = (g.descricao || 'Períodos') +
      ' <span class="badge bg-light text-dark border">' + fonteLabel(g.fonte) + '</span>';

    function renderAbas() {
      el('fin-pm-prev-body').innerHTML = g.periodos.map(periodoRowPrevHTML).join('');
      el('fin-pm-real-body').innerHTML = g.periodos.map(periodoRowRealHTML).join('');
      totais();
      el('fin-pm-prev-body').querySelectorAll('tr').forEach(bindPrevRow);
      el('fin-pm-real-body').querySelectorAll('tr').forEach(bindRealRow);
    }
    function totais() {
      var tp = g.periodos.reduce(function (s, p) { return s + Number(p.valor || 0); }, 0);
      var tr = g.periodos.reduce(function (s, p) { return s + Number(p.valor_realizado || 0); }, 0);
      el('fin-pm-prev-total').textContent = BRL(tp);
      el('fin-pm-real-total').textContent = BRL(tr);
    }
    function bindPrevRow(trEl) {
      var i = parseInt(trEl.getAttribute('data-p'), 10);
      trEl.querySelector('.fin-pm-valor').addEventListener('input', function () {
        g.periodos[i].valor = Number(this.value || 0); totais();
      });
      trEl.querySelector('.fin-pm-ini').addEventListener('change', function () {
        g.periodos[i].data_inicio = this.value || null;
        trEl.querySelector('td:first-child').textContent = rotuloMes(this.value);
      });
      trEl.querySelector('.fin-pm-fim').addEventListener('change', function () {
        g.periodos[i].data_fim = this.value || null;
      });
      trEl.querySelector('.fin-pm-del').addEventListener('click', function () {
        g.periodos.splice(i, 1); renderAbas();
      });
    }
    function bindRealRow(trEl) {
      var i = parseInt(trEl.getAttribute('data-p'), 10);
      trEl.querySelector('.fin-pm-realval').addEventListener('input', function () {
        g.periodos[i].valor_realizado = Number(this.value || 0); totais();
      });
    }
    el('fin-pm-add').onclick = function () {
      g.periodos.push({ valor: 0, valor_realizado: 0, data_inicio: null, data_fim: null, fonte: g.fonte });
      renderAbas();
    };
    el('fin-pm-aplicar').onclick = function () { recalcGrupo(box, idx); };

    renderAbas();
    var modalEl = el('fin-periodos-modal');
    var modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
    modal.show();
  }
```

> **Nota de design (decisão da spec):** "Adicionar período" usa o seletor de datas direto (`data_inicio`/`data_fim`) em vez de um seletor de mês dedicado — o intervalo custom já é suportado e o rótulo "mês/aa" é derivado de `data_inicio`. Isso satisfaz "+ Adicionar período (seletor de mês → 1º/último dia; permite intervalo custom)" reaproveitando os inputs de data.

- [ ] **Step 3: Syntax check the JS**

Run: `node --check static/js/financeiro_obra.js`
Expected: sem saída.

- [ ] **Step 4: Manual verification in the app**

Subir o app (ver skill `run`), abrir uma obra com financeiro importado → aba **Financeiro** → clicar numa barra de etapa no gráfico de etapas. Conferir:
1. A tabela mostra **uma linha por grupo** (`Escritório | Veks | N | previsto | realizado | ▸`), não mais uma por mês.
2. Clicar `▸` abre o modal com abas **Previsão** e **Realizado**; a aba Previsão lista os períodos com mês derivado da data.
3. Editar um valor previsto e um realizado → "Aplicar" atualiza os totais da linha do grupo e o cabeçalho (Previsto/Realizado).
4. "Salvar etapa" persiste; após o reload do painel a etapa reflete os novos valores e a Curva S/`Custo realizado` sobem conforme o realizado lançado.

- [ ] **Step 5: Run the full regression suite (backend não regrediu)**

Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: verde.

- [ ] **Step 6: Commit**

```bash
git add static/js/financeiro_obra.js templates/obras/detalhes_obra_profissional.html
git commit -m "feat(baia): módulo de períodos (modal) com abas Previsão e Realizado por grupo de custo"
```

---

## Task 7: Teste de agrupamento e fechamento

**Files:**
- Modify: `tests/test_painel_financeiro.py`

**Interfaces:**
- Consumes: tudo das tasks anteriores.

- [ ] **Step 1: Write the grouping invariant test (backend feeds the front grouping)**

A spec pede o teste "itens com mesma `(descricao, fonte)` colapsam numa linha; `fonte` diferente = grupos diferentes". O agrupamento vive no front, mas o backend precisa **entregar os campos certos** para isso. Adicionar a `tests/test_painel_financeiro.py`:

```python
@pytest.mark.integration
def test_painel_itens_tem_campos_para_agrupar():
    """Cada item do painel expõe (descricao, fonte, valor, valor_realizado) — base do
    agrupamento (descricao, fonte) feito na UI. Itens de período repetem descricao+fonte."""
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import painel_financeiro
    from models import Obra
    from collections import Counter
    import json, os
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        p = painel_financeiro(Obra.query.get(oid))
        for e in p['etapas']:
            for it in e['itens']:
                assert {'descricao', 'fonte', 'valor', 'valor_realizado'} <= set(it.keys())
        # ao menos uma etapa de período tem grupo com >1 item (mesma descricao+fonte)
        algum_grupo_multi = False
        for e in p['etapas']:
            chaves = Counter((it['descricao'], it['fonte']) for it in e['itens'])
            if any(c > 1 for c in chaves.values()):
                algum_grupo_multi = True
        assert algum_grupo_multi
```

- [ ] **Step 2: Run it**

Run: `python -m pytest tests/test_painel_financeiro.py::test_painel_itens_tem_campos_para_agrupar -v`
Expected: PASS.

- [ ] **Step 3: Confirm Baia invariants unchanged**

Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: verde. Reconfirmar que os asserts de `veks 800.960 / fat 550.775 / lucro 24.976 / imposto 128.903` seguem passando (previsto não mudou; realizado começa em 0).

- [ ] **Step 4: Run the entire suite once**

Run: `python -m pytest -q`
Expected: sem regressões fora do escopo financeiro.

- [ ] **Step 5: Commit**

```bash
git add tests/test_painel_financeiro.py
git commit -m "test(baia): painel expõe campos de agrupamento (descricao, fonte, valor, valor_realizado)"
```

---

## Sequência de dependências

```
T1 (coluna+migração) → T3 (painel expõe + indicadores) → T4 (endpoint grava)
T1 → T2 (descrição nome-base na importação)
T3 → T5 (tabela agrupada) → T6 (modal abas)
T1..T6 → T7 (testes de fechamento)
```

T2 é independente de T3/T4 (só toca a importação) e pode ir em paralelo após T1.

## Rollback

Cada task é um commit isolado. Reverter o commit do front (T5/T6) mantém o backend (T1–T4) estável; reverter T3 derruba o realizado dos indicadores mas mantém a coluna. A migração 202 é idempotente e aditiva (coluna `DEFAULT 0` + strip de sufixo) — não precisa de down-migration.

---

## Self-Review

**1. Spec coverage**

| Requisito da spec | Task |
|---|---|
| Unificar linhas mês-a-mês numa linha por `(descricao, fonte)` | T5 (`agruparPeriodos`/tabela) |
| Modal com períodos editáveis (add/remove/editar) | T6 |
| Abas Previsão × Realizado | T6 |
| Realizado = lançamento manual | T4 (parse) + T6 (aba) |
| Realizado alimenta KPI custo realizado | T3 (step 7) |
| Realizado alimenta Curva S | T3 (step 6) |
| Realizado alimenta caixa/verba disponível | T3 (step 7 — `verba_disponivel` deriva de `custo_realizado`) |
| Nova coluna `valor_realizado` Numeric(15,2) NOT NULL default 0 | T1 |
| Descrição vira nome-base; rótulo derivado das datas | T2 (importação) + T5 (`rotuloMes`) |
| Migração 202 idempotente + data-migration strip sufixo | T1 |
| Identidade do grupo = (descricao, fonte) na mesma OSC | T5 (`agruparPeriodos`) + T3 (itens vêm por osc) |
| Endpoint reaproveitado carrega `valor_realizado` | T4 |
| Front envia conjunto completo de períodos | T5 (`coletarItensDaEtapa`) |
| Etapas sem `osc_id` seguem "edição indisponível" | T5 (caso `osc_id == null` preservado) |
| Testes: agrupamento / migração / módulo / indicadores / invariantes / suíte verde | T1, T3, T4, T7 |
| Fora de escopo (híbrido, vínculo RDO, cronograma/RDO/portal) | não tocados |

**2. Placeholder scan** — sem TBD/TODO; todo step de código mostra o código real; comandos com expected output.

**3. Type consistency** — `valor_realizado` é `Decimal`/`Numeric(15,2)` em todo o backend; no front é `Number`. Helpers JS nomeados de forma consistente entre T5 e T6: `agruparPeriodos`, `rotuloMes`, `fonteLabel`, `recalcGrupo`, `coletarItensDaEtapa`, `abrirModuloPeriodos`, `salvarEtapa`. O endpoint desempacota a tupla de 7 elementos `(desc, valor, fonte, ordem, di, df, vr)` consistentemente em T4 (steps 3 e 4).

Observação de cobertura parcial: o teste pytest do **módulo/modal** (interação de abas) não existe — é UI vanilla sem harness JS no repo; coberto por verificação manual (T6 step 4), no mesmo padrão das fases de UI viva do plano anterior (F6).
