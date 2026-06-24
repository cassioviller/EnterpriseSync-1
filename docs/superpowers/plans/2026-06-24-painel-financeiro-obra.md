# Painel Financeiro da Obra — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar a aba "Financeiro" da página da obra no Painel Financeiro estilo `dashboard_baias` — KPIs, custo por etapa clicável/editável, Curva S com 4 séries (incl. custo realizado no tempo), doughnut Veks×Fat, caixa por mês e medições — com Verba Disponível = caixa (recebido − realizado).

**Architecture:** A aba carrega sob demanda via endpoint JSON (`GET /obras/<id>/financeiro/dados`) e renderiza no cliente com Chart.js (já global). Backend reaproveita os wrappers FF (`services/cronograma_fisico_financeiro.py`) e `services/resumo_custos_obra.py`; o realizado no tempo vem de `GestaoCustoFilho`. Edição inline de itens reusa `recalcular_servico`. Mapa de Orçamentos (já existente) é só surfaçado.

**Tech Stack:** Flask + SQLAlchemy (Postgres), Jinja2 + Bootstrap 5 (`base_completo.html`), Chart.js local, `Decimal` para dinheiro, pytest (`@integration`/`@browser`).

---

## Mapa de arquivos

| Arquivo | Responsabilidade | Ação |
|---|---|---|
| `services/cronograma_fisico_financeiro.py` | `curva_realizado`, `realizado_por_etapa`, `painel_financeiro` | **Modificar** |
| `tests/test_painel_financeiro.py` | testes do serviço + endpoints | **Criar** |
| `services/resumo_custos_obra.py` | `verba_disponivel`=caixa + `saldo_orcamentario` | **Modificar** |
| `tests/test_resumo_custos_obra.py` | ajustar/cobrir verba caixa | **Modificar** |
| `views/obras.py` | endpoints `financeiro/dados` (JSON) e `financeiro/etapa/<osc_id>` (POST) | **Modificar** |
| `cronograma_views.py` | rota FF antiga → redirect p/ aba Financeiro | **Modificar** |
| `templates/obras/detalhes_obra_profissional.html` | conteúdo novo da aba `#tab-financeiro` | **Modificar** |
| `static/js/financeiro_obra.js` | fetch + Chart.js + drill-down + edição inline | **Criar** |

**Fatos confirmados (verificados no código):**
- Wrappers FF: `montar_fisico_financeiro(obra_id, admin_id)`, `kpis(obra, dados=None)`, `fluxo_caixa(obra, dados=None)`, `medicoes_contrato(obra)`, `fluxo_caixa_divergencia(obra, dados=None)`. Constantes `CENTAVO`, `Decimal`, `ROUND_HALF_UP` no topo do módulo.
- `services/resumo_custos_obra.py`: `calcular_resumo_obra(obra_id, admin_id)` → `{indicadores, ...}`; `verba_disponivel` em `:336`; `recalcular_servico(osc_id)` em `:44`.
- `GestaoCustoFilho`: `data_referencia` (Date, NOT NULL), `valor` (Numeric), `obra_id`, `obra_servico_custo_id`; join `GestaoCustoPai` (tem `admin_id`, `tipo_categoria`). Padrão de query do realizado em `resumo_custos_obra.py:255-264` (filtra `tipo_categoria != 'FATURAMENTO_DIRETO'`).
- `ObraServicoCusto`: `valor_orcado`, `mao_obra_a_realizar` (Veks), `material_a_realizar` (Fat), `fonte_*`, `realizado_total` (property), `a_realizar_total` (property).
- Página da obra: rota `main.detalhes_obra` (`views/obras.py:1343`, `/obras/<int:id>`), template `templates/obras/detalhes_obra_profissional.html`, aba `#tab-financeiro` em **1521-1580**. Chart.js global em `base_completo.html:27`.
- Rota FF standalone: `cronograma.fisico_financeiro` (`cronograma_views.py:2533`, `/cronograma/obras/<int:obra_id>/fisico-financeiro`).
- `utils/tenant.py::get_tenant_admin_id()`; helpers de teste em `tests/test_importacao_fisico_financeiro.py` (`_novo_admin`, `_carregar_json`).

---

## Fase 1 — Serviço de dados

### Task 1: `curva_realizado` + `realizado_por_etapa`

**Files:**
- Modify: `services/cronograma_fisico_financeiro.py`
- Test: `tests/test_painel_financeiro.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_painel_financeiro.py
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

from datetime import date, datetime
from decimal import Decimal
import pytest
from werkzeug.security import generate_password_hash
from app import app, db

D = Decimal


def _novo_admin():
    from models import Usuario, TipoUsuario
    tag = datetime.utcnow().strftime('%H%M%S%f')
    u = Usuario(username=f'pf_{tag}', email=f'pf_{tag}@t.local', nome='PF',
                password_hash=generate_password_hash('x'), tipo_usuario=TipoUsuario.ADMIN)
    db.session.add(u); db.session.commit()
    return u.id


def _obra_com_realizado(admin_id):
    """Cria obra + 2 lançamentos de custo realizado (GestaoCustoFilho) em meses
    distintos + 1 de FATURAMENTO_DIRETO (que deve ser excluído)."""
    from models import Obra, GestaoCustoPai, GestaoCustoFilho
    obra = Obra(nome='Obra PF', codigo=f'PF{admin_id}', admin_id=admin_id,
                data_inicio=date(2026, 6, 1), valor_contrato=1000000.0)
    db.session.add(obra); db.session.flush()
    pai = GestaoCustoPai(tipo_categoria='MAO_OBRA', admin_id=admin_id,
                         entidade_nome='Equipe', valor_total=0)
    db.session.add(pai); db.session.flush()
    pai_fat = GestaoCustoPai(tipo_categoria='FATURAMENTO_DIRETO', admin_id=admin_id,
                             entidade_nome='Cliente', valor_total=0)
    db.session.add(pai_fat); db.session.flush()
    db.session.add_all([
        GestaoCustoFilho(pai_id=pai.id, data_referencia=date(2026, 6, 10),
                         descricao='Diária', valor=D('10000'), obra_id=obra.id, admin_id=admin_id),
        GestaoCustoFilho(pai_id=pai.id, data_referencia=date(2026, 7, 5),
                         descricao='Empreitada', valor=D('25000'), obra_id=obra.id, admin_id=admin_id),
        GestaoCustoFilho(pai_id=pai_fat.id, data_referencia=date(2026, 6, 20),
                         descricao='Material cliente', valor=D('99999'), obra_id=obra.id, admin_id=admin_id),
    ])
    db.session.commit()
    return obra


@pytest.mark.integration
def test_curva_realizado_por_mes_exclui_fat_direto():
    from services.cronograma_fisico_financeiro import curva_realizado
    with app.app_context():
        aid = _novo_admin()
        obra = _obra_com_realizado(aid)
        out = curva_realizado(obra)
        assert out == {'2026-06': D('10000'), '2026-07': D('25000')}  # FAT_DIRETO fora
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_painel_financeiro.py::test_curva_realizado_por_mes_exclui_fat_direto -v`
Expected: FAIL com `ImportError: cannot import name 'curva_realizado'`.

- [ ] **Step 3: Implementar em `services/cronograma_fisico_financeiro.py`** (após os wrappers existentes)

```python
def curva_realizado(obra) -> dict:
    """Custo realizado por mês 'YYYY-MM' a partir de GestaoCustoFilho.data_referencia,
    tenant-scoped, excluindo FATURAMENTO_DIRETO. Fonte: RDO/diárias, empreitadas,
    compras, aluguel — cresce ao longo do tempo."""
    from models import GestaoCustoFilho, GestaoCustoPai
    rows = (db.session.query(GestaoCustoFilho.data_referencia, GestaoCustoFilho.valor)
            .join(GestaoCustoPai, GestaoCustoFilho.pai_id == GestaoCustoPai.id)
            .filter(GestaoCustoFilho.obra_id == obra.id)
            .filter(GestaoCustoPai.admin_id == obra.admin_id)
            .filter(GestaoCustoPai.tipo_categoria != 'FATURAMENTO_DIRETO')
            .all())
    out: dict = {}
    for dt, valor in rows:
        if not dt:
            continue
        chave = f"{dt.year:04d}-{dt.month:02d}"
        out[chave] = out.get(chave, Decimal("0")) + Decimal(valor or 0)
    return out
```

> **Nota:** `db` já é usado em outras funções do módulo via `from models import db` / imports locais. Use o mesmo padrão dos wrappers existentes (eles fazem `from models import ...` dentro da função). Adicione `db` ao import local se necessário.

Adicione também `realizado_por_etapa`:

```python
def realizado_por_etapa(obra) -> dict:
    """Realizado por etapa: {obra_servico_custo_id: Decimal} a partir de
    GestaoCustoFilho.obra_servico_custo_id (exclui FATURAMENTO_DIRETO)."""
    from models import GestaoCustoFilho, GestaoCustoPai
    rows = (db.session.query(GestaoCustoFilho.obra_servico_custo_id, GestaoCustoFilho.valor)
            .join(GestaoCustoPai, GestaoCustoFilho.pai_id == GestaoCustoPai.id)
            .filter(GestaoCustoFilho.obra_id == obra.id)
            .filter(GestaoCustoPai.admin_id == obra.admin_id)
            .filter(GestaoCustoPai.tipo_categoria != 'FATURAMENTO_DIRETO')
            .all())
    out: dict = {}
    for osc_id, valor in rows:
        if osc_id is None:
            continue
        out[osc_id] = out.get(osc_id, Decimal("0")) + Decimal(valor or 0)
    return out
```

- [ ] **Step 4: Garantir `db` acessível no módulo** — se o módulo ainda não importa `db` no escopo dessas funções, mantenha o `from models import GestaoCustoFilho, GestaoCustoPai` local e adicione `from models import db` no topo das duas funções (ou no topo do módulo, seguindo o padrão já presente).

- [ ] **Step 5: Rodar e ver passar**

Run: `pytest tests/test_painel_financeiro.py::test_curva_realizado_por_mes_exclui_fat_direto -v`
Expected: PASS.

- [ ] **Step 6: Teste de `realizado_por_etapa`**

```python
@pytest.mark.integration
def test_realizado_por_etapa_agrupa_por_osc():
    from services.cronograma_fisico_financeiro import realizado_por_etapa
    from models import Obra, GestaoCustoPai, GestaoCustoFilho, ObraServicoCusto, ItemMedicaoComercial
    with app.app_context():
        aid = _novo_admin()
        obra = Obra(nome='O2', codigo=f'O2{aid}', admin_id=aid, data_inicio=date(2026,6,1), valor_contrato=0)
        db.session.add(obra); db.session.flush()
        imc = ItemMedicaoComercial(obra_id=obra.id, admin_id=aid, nome='E1', valor_comercial=D('0'))
        db.session.add(imc); db.session.flush()
        osc = ObraServicoCusto.query.filter_by(item_medicao_comercial_id=imc.id).first()
        if osc is None:
            osc = ObraServicoCusto(obra_id=obra.id, admin_id=aid, nome='E1', valor_orcado=D('0'))
            db.session.add(osc); db.session.flush()
        pai = GestaoCustoPai(tipo_categoria='MAO_OBRA', admin_id=aid, entidade_nome='x', valor_total=0)
        db.session.add(pai); db.session.flush()
        db.session.add(GestaoCustoFilho(pai_id=pai.id, data_referencia=date(2026,6,1),
                       descricao='d', valor=D('500'), obra_id=obra.id, admin_id=aid,
                       obra_servico_custo_id=osc.id))
        db.session.commit()
        out = realizado_por_etapa(obra)
        assert out.get(osc.id) == D('500')
```

Run: `pytest tests/test_painel_financeiro.py::test_realizado_por_etapa_agrupa_por_osc -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add services/cronograma_fisico_financeiro.py tests/test_painel_financeiro.py
git commit -m "feat(fin): curva_realizado + realizado_por_etapa (GestaoCustoFilho por mês/etapa)"
```

### Task 2: Verba Disponível = caixa + `saldo_orcamentario`

**Files:**
- Modify: `services/resumo_custos_obra.py` (`:335-353` e `_resumo_vazio`)
- Test: `tests/test_painel_financeiro.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
@pytest.mark.integration
def test_verba_disponivel_eh_caixa():
    """verba_disponivel = recebido − realizado; saldo_orcamentario = contrato − custo."""
    from services.resumo_custos_obra import calcular_resumo_obra
    from models import Obra, GestaoCustoPai, GestaoCustoFilho
    with app.app_context():
        aid = _novo_admin()
        obra = Obra(nome='OV', codigo=f'OV{aid}', admin_id=aid, data_inicio=date(2026,6,1),
                    valor_contrato=100000.0)
        db.session.add(obra); db.session.flush()
        pai = GestaoCustoPai(tipo_categoria='MAO_OBRA', admin_id=aid, entidade_nome='x', valor_total=0)
        db.session.add(pai); db.session.flush()
        db.session.add(GestaoCustoFilho(pai_id=pai.id, data_referencia=date(2026,6,5),
                       descricao='real', valor=D('30000'), obra_id=obra.id, admin_id=aid))
        db.session.commit()
        r = calcular_resumo_obra(obra.id, aid)
        i = r['indicadores']
        # recebido=0, realizado=30000 -> verba (caixa) = -30000
        assert i['verba_disponivel'] == round(i['valor_recebido'] - i['total_realizado'], 2)
        assert 'saldo_orcamentario' in i
        assert i['saldo_orcamentario'] == round(i['total_proposta_orcada'] - i['custo_real_da_obra'], 2)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_painel_financeiro.py::test_verba_disponivel_eh_caixa -v`
Expected: FAIL (`verba_disponivel` ainda é margem; `saldo_orcamentario` ausente → KeyError).

- [ ] **Step 3: Modificar `services/resumo_custos_obra.py`** (bloco `:335-353`)

Trocar:
```python
    custo_real_da_obra = total_realizado + total_a_realizar + administracao + faturamento_direto
    verba_disponivel = total_proposta_orcada - custo_real_da_obra
    lucro_liquido = valor_medido - (total_realizado + administracao + faturamento_direto)
```
por:
```python
    custo_real_da_obra = total_realizado + total_a_realizar + administracao + faturamento_direto
    # Verba disponível = visão de CAIXA: o que já entrou menos o que já foi gasto.
    verba_disponivel = valor_recebido - total_realizado
    # Saldo orçamentário = visão de MARGEM (preservada): contrato menos custo projetado.
    saldo_orcamentario = total_proposta_orcada - custo_real_da_obra
    lucro_liquido = valor_medido - (total_realizado + administracao + faturamento_direto)
```

No dict `indicadores` (logo abaixo), adicionar a chave `saldo_orcamentario`:
```python
        'verba_disponivel': round(verba_disponivel, 2),
        'saldo_orcamentario': round(saldo_orcamentario, 2),
```

Em `_resumo_vazio()` (lista de chaves ~`:404-409`), adicionar `'saldo_orcamentario'` ao conjunto de chaves zeradas.

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_painel_financeiro.py::test_verba_disponivel_eh_caixa -v`
Expected: PASS.

- [ ] **Step 5: Regressão do teste existente**

Run: `pytest tests/test_resumo_custos_obra.py -q`
Expected: PASS. Se algum teste asseverava `verba_disponivel == contrato − custo`, atualize-o para a nova semântica (caixa) e adicione asserção de `saldo_orcamentario`. Mostre o diff do teste no commit.

- [ ] **Step 6: Commit**

```bash
git add services/resumo_custos_obra.py tests/test_resumo_custos_obra.py tests/test_painel_financeiro.py
git commit -m "feat(fin): verba_disponivel=caixa (recebido−realizado) + saldo_orcamentario (margem)"
```

### Task 3: Orquestrador `painel_financeiro(obra)`

**Files:**
- Modify: `services/cronograma_fisico_financeiro.py`
- Test: `tests/test_painel_financeiro.py`

- [ ] **Step 1: Escrever o teste que falha** (usa a fixture Baias já importável)

```python
@pytest.mark.integration
def test_painel_financeiro_estrutura():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import painel_financeiro
    from models import Obra
    import json
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        payload = json.load(open(caminho, encoding='utf-8'))
        oid = importar_fisico_financeiro(payload, aid)['obra_id']
        obra = Obra.query.get(oid)
        p = painel_financeiro(obra)
        for k in ('kpis', 'etapas', 'curva_s', 'caixa', 'medicoes', 'doughnut', 'divergencia'):
            assert k in p, k
        # curva_s tem 4 séries de mesmo comprimento
        cs = p['curva_s']
        assert set(['meses', 'recebido_liquido', 'gasto_veks', 'lucro', 'realizado']) <= set(cs)
        n = len(cs['meses'])
        assert all(len(cs[s]) == n for s in ('recebido_liquido', 'gasto_veks', 'lucro', 'realizado'))
        # etapas trazem realizado (>=0) e previsto
        assert p['etapas'] and all('realizado' in e and 'previsto' in e for e in p['etapas'])
        # doughnut
        assert set(['veks', 'fat']) <= set(p['doughnut'])
        # verba (caixa) presente nos kpis
        assert 'verba_disponivel' in p['kpis']
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_painel_financeiro.py::test_painel_financeiro_estrutura -v`
Expected: FAIL (`ImportError: painel_financeiro`).

- [ ] **Step 3: Implementar `painel_financeiro` em `services/cronograma_fisico_financeiro.py`**

```python
def painel_financeiro(obra) -> dict:
    """Monta o dicionário consolidado do Painel Financeiro (pronto para JSON).
    Junta KPIs, etapas (previsto+realizado), Curva S de 4 séries (recebido líquido,
    gasto Veks previsto, lucro, custo realizado), caixa, medições, doughnut e divergência."""
    from services.resumo_custos_obra import calcular_resumo_obra

    dados = montar_fisico_financeiro(obra.id, obra.admin_id)
    k = kpis(obra, dados)
    caixa = fluxo_caixa(obra, dados)
    meds = medicoes_contrato(obra)
    div = fluxo_caixa_divergencia(obra, dados)
    resumo = calcular_resumo_obra(obra.id, obra.admin_id).get('indicadores', {})

    realizado_mes = curva_realizado(obra)
    realizado_etapa = realizado_por_etapa(obra)

    # eixo de meses unificado: meses do caixa ∪ meses do realizado, ordenado
    meses = sorted(set([l["mes"] for l in caixa["linhas"]]) | set(realizado_mes))

    # séries acumuladas alinhadas a `meses`
    caixa_por_mes = {l["mes"]: l for l in caixa["linhas"]}
    receb_ac, gasto_ac, real_ac = [], [], []
    r = g = re = Decimal("0")
    for m in meses:
        linha = caixa_por_mes.get(m)
        r += (linha["entrada"] if linha else Decimal("0"))
        g += (linha["gasto_veks"] if linha else Decimal("0"))
        re += realizado_mes.get(m, Decimal("0"))
        receb_ac.append(r); gasto_ac.append(g); real_ac.append(re)
    lucro_ac = [receb_ac[i] - gasto_ac[i] for i in range(len(meses))]

    # etapas com realizado por OSC (precisa do osc_id em montar_fisico_financeiro)
    etapas = []
    for e in dados["etapas"]:
        osc_id = e.get("osc_id") or e.get("etapa_id")
        etapas.append({
            "nome": e["nome"],
            "veks": e["veks"],
            "fat": e["fat_direto"],
            "previsto": e["previsto"]["total"],
            "realizado": realizado_etapa.get(osc_id, Decimal("0")),
            "osc_id": osc_id,
        })

    return {
        "kpis": {**k, "verba_disponivel": resumo.get("verba_disponivel", 0),
                 "custo_realizado": resumo.get("total_realizado", 0)},
        "etapas": etapas,
        "curva_s": {
            "meses": meses,
            "recebido_liquido": receb_ac,
            "gasto_veks": gasto_ac,
            "lucro": lucro_ac,
            "realizado": real_ac,
        },
        "caixa": caixa,
        "medicoes": meds,
        "doughnut": {"veks": dados["totais"]["veks"], "fat": dados["totais"]["fat_direto"]},
        "divergencia": div,
    }
```

- [ ] **Step 4: Garantir `osc_id` nas etapas de `montar_fisico_financeiro`**

Ler a função `montar_fisico_financeiro`. No dicionário de cada etapa (onde monta `etapa_id`, `nome`, etc.), o `etapa_id` é o id da TarefaCronograma raiz — NÃO o `ObraServicoCusto.id`. Para `realizado_por_etapa` casar, precisamos do `osc_id`. Há duas opções:
  - **(escolhida)** Em `painel_financeiro`, em vez de depender de `e["osc_id"]`, calcular o realizado por etapa **pelo nome** se o id não estiver disponível. Mais robusto: ajustar `montar_fisico_financeiro` para incluir `osc_id` quando a etapa vem de um único OSC.

Implementação mínima e segura: em `montar_fisico_financeiro`, onde cada `etapa` agrega de um `osc`, gravar também `et["osc_id"] = osc.id` (quando a etapa corresponde a 1 OSC; se agrega vários, deixar `None`). Localize o ponto onde `et["realizado"] += ...` é somado por `osc` e adicione, no mesmo escopo, `et.setdefault("osc_id", osc.id)` (mantém o primeiro; se houver 2º OSC diferente, set para `None`):

```python
            # rastreia o OSC de origem da etapa (para casar realizado por etapa)
            if "osc_id" not in et:
                et["osc_id"] = osc.id
            elif et["osc_id"] != osc.id:
                et["osc_id"] = None
```

E inclua `"osc_id": et.get("osc_id")` no dicionário final de cada etapa retornada (no `sorted(etapas.values(), ...)` os dicts já carregam a chave). Garanta que o `_etapa()` inicialize sem `osc_id` (não precisa pré-criar).

> Após esse ajuste, `e.get("osc_id")` em `painel_financeiro` traz o id correto. No piloto Baias cada etapa = 1 OSC, então casa 1:1.

- [ ] **Step 5: Rodar e ver passar**

Run: `pytest tests/test_painel_financeiro.py::test_painel_financeiro_estrutura -v`
Expected: PASS.

- [ ] **Step 6: Regressão dos testes FF existentes**

Run: `pytest tests/test_cronograma_fisico_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: PASS (o novo `osc_id` é chave extra; não quebra asserções existentes).

- [ ] **Step 7: Commit**

```bash
git add services/cronograma_fisico_financeiro.py tests/test_painel_financeiro.py
git commit -m "feat(fin): painel_financeiro (KPIs+etapas+Curva S 4 séries+caixa+medições+doughnut)"
```

---

## Fase 2 — Endpoints

### Task 4: `GET /obras/<id>/financeiro/dados` (JSON)

**Files:**
- Modify: `views/obras.py`
- Test: `tests/test_painel_financeiro.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
@pytest.mark.integration
def test_endpoint_financeiro_dados():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    import json
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        r = c.get(f'/obras/{oid}/financeiro/dados')
        assert r.status_code == 200
        data = r.get_json()
        for k in ('kpis', 'etapas', 'curva_s', 'caixa', 'medicoes', 'doughnut'):
            assert k in data
        assert len(data['curva_s']['meses']) == len(data['curva_s']['realizado'])
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_painel_financeiro.py::test_endpoint_financeiro_dados -v`
Expected: FAIL (404).

- [ ] **Step 3: Implementar o endpoint em `views/obras.py`**

Localize o blueprint usado pela rota `detalhes_obra` (é `main_bp`, endpoint `main.detalhes_obra`). Adicione (perto das outras rotas de `/obras/<id>/...`):

```python
@main_bp.route('/obras/<int:id>/financeiro/dados')
@login_required
def financeiro_dados(id):
    from models import Obra
    from services.cronograma_fisico_financeiro import painel_financeiro
    from utils.tenant import get_tenant_admin_id
    admin_id = get_tenant_admin_id()
    obra = Obra.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    return jsonify(_jsonable(painel_financeiro(obra)))
```

E um helper de serialização (no topo do módulo ou perto do endpoint), convertendo `Decimal`→`float` e `date/datetime`→ISO recursivamente:

```python
def _jsonable(obj):
    from decimal import Decimal as _D
    from datetime import date as _date, datetime as _dt
    if isinstance(obj, _D):
        return float(obj)
    if isinstance(obj, (_date, _dt)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj
```

Garanta que `jsonify` e `login_required` estão importados em `views/obras.py` (provavelmente já estão; se não, adicione `from flask import jsonify` e `from flask_login import login_required`).

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_painel_financeiro.py::test_endpoint_financeiro_dados -v`
Expected: PASS.

- [ ] **Step 5: Teste de isolamento multitenant**

```python
@pytest.mark.integration
def test_endpoint_financeiro_dados_multitenant():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    import json
    with app.app_context():
        a1 = _novo_admin(); a2 = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), a1)['obra_id']
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(a2); s['_fresh'] = True  # outro tenant
        r = c.get(f'/obras/{oid}/financeiro/dados')
        assert r.status_code == 404  # a2 não enxerga obra de a1
```

Run: `pytest tests/test_painel_financeiro.py::test_endpoint_financeiro_dados_multitenant -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add views/obras.py tests/test_painel_financeiro.py
git commit -m "feat(fin): endpoint JSON /obras/<id>/financeiro/dados"
```

### Task 5: `POST /obras/<id>/financeiro/etapa/<osc_id>` (edição inline)

**Files:**
- Modify: `views/obras.py`
- Test: `tests/test_painel_financeiro.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
@pytest.mark.integration
def test_endpoint_editar_etapa():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Obra, ObraServicoCusto
    import json
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        osc = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=aid).first()
        osc_id = osc.id
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        r = c.post(f'/obras/{oid}/financeiro/etapa/{osc_id}',
                   data={'veks': '12345', 'fat': '6789', 'valor_orcado': '19134'})
        assert r.status_code == 200
        data = r.get_json()
        assert 'etapas' in data  # devolve o painel recalculado
    with app.app_context():
        osc = ObraServicoCusto.query.get(osc_id)
        assert float(osc.mao_obra_a_realizar) == 12345.0
        assert float(osc.material_a_realizar) == 6789.0
        assert float(osc.valor_orcado) == 19134.0
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_painel_financeiro.py::test_endpoint_editar_etapa -v`
Expected: FAIL (404).

- [ ] **Step 3: Implementar em `views/obras.py`**

```python
@main_bp.route('/obras/<int:id>/financeiro/etapa/<int:osc_id>', methods=['POST'])
@login_required
def financeiro_editar_etapa(id, osc_id):
    from decimal import Decimal, InvalidOperation
    from models import Obra, ObraServicoCusto
    from services.cronograma_fisico_financeiro import painel_financeiro
    from services.resumo_custos_obra import recalcular_servico
    from utils.tenant import get_tenant_admin_id
    admin_id = get_tenant_admin_id()
    obra = Obra.query.filter_by(id=id, admin_id=admin_id).first_or_404()
    osc = ObraServicoCusto.query.filter_by(id=osc_id, obra_id=obra.id, admin_id=admin_id).first_or_404()

    def _dec(v):
        try:
            return Decimal(str(v).replace(',', '.')) if v not in (None, '') else Decimal('0')
        except (InvalidOperation, ValueError):
            return None
    veks = _dec(request.form.get('veks'))
    fat = _dec(request.form.get('fat'))
    orc = _dec(request.form.get('valor_orcado'))
    if veks is None or fat is None or orc is None:
        return jsonify({'erro': 'valores inválidos'}), 400

    osc.mao_obra_a_realizar = veks
    osc.fonte_mao_obra = 'veks'
    osc.material_a_realizar = fat
    osc.fonte_material = 'fat_direto'
    osc.valor_orcado = orc
    db.session.commit()
    recalcular_servico(osc.id)
    db.session.commit()
    return jsonify(_jsonable(painel_financeiro(obra)))
```

Confirme que `request` e `db` estão importados em `views/obras.py` (devem estar).

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_painel_financeiro.py::test_endpoint_editar_etapa -v`
Expected: PASS.

- [ ] **Step 5: Teste multitenant (não edita OSC de outra obra)**

```python
@pytest.mark.integration
def test_editar_etapa_multitenant():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import ObraServicoCusto
    import json
    with app.app_context():
        a1 = _novo_admin(); a2 = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), a1)['obra_id']
        osc_id = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=a1).first().id
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(a2); s['_fresh'] = True
        r = c.post(f'/obras/{oid}/financeiro/etapa/{osc_id}',
                   data={'veks': '1', 'fat': '1', 'valor_orcado': '2'})
        assert r.status_code == 404
```

Run: `pytest tests/test_painel_financeiro.py::test_editar_etapa_multitenant -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add views/obras.py tests/test_painel_financeiro.py
git commit -m "feat(fin): endpoint POST edição de item de custo por etapa (recalcula)"
```

### Task 6: Redirect da rota FF antiga → aba Financeiro

**Files:**
- Modify: `cronograma_views.py` (`fisico_financeiro`, ~`:2533`)
- Test: `tests/test_painel_financeiro.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
@pytest.mark.integration
def test_rota_ff_antiga_redireciona():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    import json
    with app.app_context():
        aid = _novo_admin()
        # painel é v2-gated; garante v2
        from models import Usuario
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'; db.session.commit()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        r = c.get(f'/cronograma/obras/{oid}/fisico-financeiro')
        assert r.status_code in (301, 302)
        assert f'/obras/{oid}' in r.headers.get('Location', '')
        assert 'tab-financeiro' in r.headers.get('Location', '')
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_painel_financeiro.py::test_rota_ff_antiga_redireciona -v`
Expected: FAIL (rota ainda renderiza o template, status 200).

- [ ] **Step 3: Modificar `cronograma_views.py`** — substituir o corpo de `fisico_financeiro` por um redirect:

```python
@cronograma_bp.route('/obras/<int:obra_id>/fisico-financeiro')
@login_required
def fisico_financeiro(obra_id: int):
    # O painel agora vive na aba Financeiro da página da obra.
    from flask import redirect, url_for
    return redirect(url_for('main.detalhes_obra', id=obra_id) + '#tab-financeiro')
```

> Mantenha a rota `export.xlsx` como está. Confirme o endpoint real da página da obra (`main.detalhes_obra`).

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_painel_financeiro.py::test_rota_ff_antiga_redireciona -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cronograma_views.py tests/test_painel_financeiro.py
git commit -m "feat(fin): rota FF standalone redireciona para a aba Financeiro"
```

---

## Fase 3 — Front (template + JS)

### Task 7: Estrutura da aba Financeiro (canvases + containers)

**Files:**
- Modify: `templates/obras/detalhes_obra_profissional.html` (bloco `#tab-financeiro`, 1521-1580)

- [ ] **Step 1: Substituir o conteúdo de `#tab-financeiro`** pelo esqueleto do painel (mantém o `<div class="tab-pane fade" id="tab-financeiro" ...>` e o comentário de fechamento). Insira `data-obra-id` para o JS:

```html
<div class="tab-pane fade" id="tab-financeiro" role="tabpanel"
     data-obra-id="{{ obra.id }}" data-endpoint="{{ url_for('main.financeiro_dados', id=obra.id) }}">
  <div id="fin-loading" class="text-muted py-4">Carregando painel financeiro…</div>
  <div id="fin-painel" style="display:none">

    <!-- KPIs -->
    <div class="row g-3 mb-4" id="fin-kpis"></div>

    <!-- Custo por etapa + drill-down -->
    <div class="card mb-4"><div class="card-body">
      <h6 class="fw-bold mb-3">Custo por etapa <small class="text-muted">(clique para editar)</small></h6>
      <canvas id="finEtapas" height="320"></canvas>
      <div id="fin-etapa-det" class="mt-3"></div>
    </div></div>

    <!-- Curva S + doughnut -->
    <div class="row g-3 mb-4">
      <div class="col-lg-8"><div class="card h-100"><div class="card-body">
        <h6 class="fw-bold mb-3">Curva S — recebido, gasto, lucro e realizado</h6>
        <canvas id="finCurva" height="240"></canvas>
      </div></div></div>
      <div class="col-lg-4"><div class="card h-100"><div class="card-body">
        <h6 class="fw-bold mb-3">Veks × Faturamento direto</h6>
        <canvas id="finSplit" height="240"></canvas>
      </div></div></div>
    </div>

    <!-- Caixa + medições -->
    <div class="row g-3 mb-4">
      <div class="col-lg-6"><div class="card h-100"><div class="card-body">
        <h6 class="fw-bold mb-3">Caixa final por mês</h6>
        <canvas id="finCaixa" height="220"></canvas>
      </div></div></div>
      <div class="col-lg-6"><div class="card h-100"><div class="card-body">
        <h6 class="fw-bold mb-3">Medições de contrato</h6>
        <table class="table table-sm"><thead><tr><th>Parcela</th><th>Data</th><th>%</th>
          <th class="text-end">Valor</th></tr></thead><tbody id="fin-medicoes"></tbody></table>
      </div></div></div>
    </div>

    <!-- Alerta Indiretos -->
    <div id="fin-alerta"></div>

    <!-- Mapa de Orçamentos (link p/ aba existente) -->
    <div class="card"><div class="card-body d-flex align-items-center justify-content-between">
      <div><h6 class="fw-bold mb-0">Mapa de Orçamentos</h6>
        <small class="text-muted">Cotações por frente de trabalho.</small></div>
      <button class="btn btn-outline-primary btn-sm"
              onclick="document.querySelector('[data-bs-target=\"#tab-mapa\"]').click()">
        Abrir Mapa
      </button>
    </div></div>

  </div>
  <div id="fin-erro" class="alert alert-warning" style="display:none">
    Não foi possível carregar o painel financeiro.</div>
</div>
<!-- /tab-pane Financeiro -->
```

- [ ] **Step 2: Incluir o JS** (no fim do template, junto dos outros `<script>`):

```html
<script src="{{ url_for('static', filename='js/financeiro_obra.js') }}"></script>
```

- [ ] **Step 3: Compile check**

Run:
```bash
python3 -c "import main; from app import app; app.jinja_env.get_template('obras/detalhes_obra_profissional.html'); print('ok')"
```
Expected: `ok` (sem erro de Jinja; `url_for('main.financeiro_dados', ...)` resolve — exige a Task 4 já mergeada).

- [ ] **Step 4: Commit**

```bash
git add templates/obras/detalhes_obra_profissional.html
git commit -m "feat(fin): estrutura da aba Financeiro (canvases + containers)"
```

### Task 8: `financeiro_obra.js` — fetch + KPIs + medições + 4 charts

**Files:**
- Create: `static/js/financeiro_obra.js`

- [ ] **Step 1: Criar `static/js/financeiro_obra.js`** (carrega ao abrir a aba; renderiza KPIs, medições e os 4 gráficos)

```javascript
/* Painel Financeiro da Obra — carrega sob demanda e renderiza com Chart.js. */
(function () {
  var BRL = function (v) { return 'R$ ' + Math.round(v || 0).toLocaleString('pt-BR'); };
  var BRLk = function (v) { return 'R$ ' + Math.round((v || 0) / 1000).toLocaleString('pt-BR') + 'k'; };
  var C = {}, loaded = false, PANEL = null, ENDPOINT = null, OBRA_ID = null;

  function el(id) { return document.getElementById(id); }

  function renderKPIs(k) {
    var cards = [
      ['Venda (contrato)', k.venda, ''], ['Custo total', k.custo_total, ''],
      ['Lucro projetado', k.lucro_projetado, 'text-success'],
      ['Desembolso Veks', k.desembolso_veks, ''],
      ['Faturamento direto', k.fat_direto, 'text-success'],
      ['Recebido até hoje', k.recebido_ate_hoje, ''],
      ['Verba disponível (caixa)', k.verba_disponivel, (k.verba_disponivel >= 0 ? 'text-success' : 'text-danger')],
      ['Custo realizado', k.custo_realizado, '']
    ];
    el('fin-kpis').innerHTML = cards.map(function (c) {
      return '<div class="col-6 col-md-3"><div class="card h-100"><div class="card-body p-2">' +
        '<div class="small text-muted">' + c[0] + '</div>' +
        '<div class="fw-bold ' + c[2] + '" style="font-variant-numeric:tabular-nums">' + BRL(c[1]) + '</div>' +
        '</div></div></div>';
    }).join('');
  }

  function renderMedicoes(meds) {
    el('fin-medicoes').innerHTML = (meds || []).map(function (m) {
      var d = m.data ? m.data.split('-').reverse().join('/') : '—';
      return '<tr><td>' + m.nome + '</td><td>' + d + '</td><td>' +
        (m.pct * 100).toFixed(1) + '%</td><td class="text-end">' + BRL(m.valor) + '</td></tr>';
    }).join('');
  }

  function renderAlerta(div) {
    if (!div || !div.resumo || Math.abs(div.resumo.delta_veks || 0) <= 1) { el('fin-alerta').innerHTML = ''; return; }
    var r = div.resumo;
    el('fin-alerta').innerHTML = '<div class="alert alert-warning">' +
      '<strong>Inconsistência dos Indiretos:</strong> Veks etapas ' + BRL(r.veks_etapas) +
      ' × planilha ' + BRL(r.veks_verbatim) + ' (Δ ' + BRL(r.delta_veks) + '). ' +
      'Lucro em caixa (planilha) ' + BRL(r.lucro_em_caixa) + '. Decida 3,5 vs 5 meses dos Indiretos.</div>';
  }

  function buildCharts(p) {
    var blue = '#2E6BB0', green = '#198754', amber = '#C8870E', red = '#C0392B', grid = { color: '#E5EBF2' };
    var st = p.etapas.slice().sort(function (a, b) { return b.previsto - a.previsto; });
    C.etapas = new Chart(el('finEtapas'), {
      type: 'bar',
      data: {
        labels: st.map(function (s) { return s.nome; }), datasets: [
          { label: 'Veks', data: st.map(function (s) { return s.veks; }), backgroundColor: blue, stack: 's' },
          { label: 'Fat direto', data: st.map(function (s) { return s.fat; }), backgroundColor: green, stack: 's' }]
      },
      options: {
        indexAxis: 'y', maintainAspectRatio: false,
        onClick: function (e, els) { if (els.length) showEtapa(st[els[0].index]); },
        plugins: { tooltip: { callbacks: { label: function (c) { return c.dataset.label + ': ' + BRL(c.parsed.x); } } } },
        scales: { x: { stacked: true, grid: grid, ticks: { callback: BRLk } }, y: { stacked: true, grid: { display: false } } }
      }
    });
    var cs = p.curva_s;
    C.curva = new Chart(el('finCurva'), {
      type: 'line',
      data: {
        labels: cs.meses, datasets: [
          { label: 'Recebido líquido', data: cs.recebido_liquido, borderColor: green, borderDash: [6, 4], tension: .35, pointRadius: 3 },
          { label: 'Gasto Veks (prev.)', data: cs.gasto_veks, borderColor: blue, tension: .35, pointRadius: 3 },
          { label: 'Lucro', data: cs.lucro, borderColor: amber, backgroundColor: 'rgba(200,135,14,.12)', fill: true, tension: .35, pointRadius: 3 },
          { label: 'Custo realizado', data: cs.realizado, borderColor: red, tension: .35, pointRadius: 3 }]
      },
      options: { maintainAspectRatio: false, plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: function (c) { return c.dataset.label + ': ' + BRL(c.parsed.y); } } } }, scales: { y: { grid: grid, ticks: { callback: BRLk } }, x: { grid: { display: false } } } }
    });
    C.split = new Chart(el('finSplit'), {
      type: 'doughnut',
      data: { labels: ['Desembolso Veks', 'Fat direto'], datasets: [{ data: [p.doughnut.veks, p.doughnut.fat], backgroundColor: [blue, green] }] },
      options: { maintainAspectRatio: false, cutout: '62%', plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: function (c) { return c.label + ': ' + BRL(c.parsed); } } } } }
    });
    var caixaLin = p.caixa.linhas || [];
    C.caixa = new Chart(el('finCaixa'), {
      type: 'bar',
      data: { labels: caixaLin.map(function (l) { return l.mes; }), datasets: [{ label: 'Caixa final', data: caixaLin.map(function (l) { return l.caixa_final; }), backgroundColor: caixaLin.map(function (l) { return l.caixa_final < 110000 ? amber : blue; }) }] },
      options: { maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: function (c) { return BRL(c.parsed.y); } } } }, scales: { y: { grid: grid, ticks: { callback: BRLk } }, x: { grid: { display: false } } } }
    });
  }

  function render(p) {
    PANEL = p;
    renderKPIs(p.kpis); renderMedicoes(p.medicoes); renderAlerta(p.divergencia);
    if (C.etapas) { Object.keys(C).forEach(function (k) { C[k].destroy(); }); C = {}; }
    buildCharts(p);
  }

  function load() {
    if (loaded) return;
    loaded = true;
    fetch(ENDPOINT, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (p) { el('fin-loading').style.display = 'none'; el('fin-painel').style.display = 'block'; render(p); })
      .catch(function () { el('fin-loading').style.display = 'none'; el('fin-erro').style.display = 'block'; });
  }

  // showEtapa é definida na Task 9 (drill-down/edição). Stub seguro até lá:
  window.showEtapa = window.showEtapa || function () {};

  document.addEventListener('DOMContentLoaded', function () {
    var pane = el('tab-financeiro');
    if (!pane) return;
    ENDPOINT = pane.getAttribute('data-endpoint');
    OBRA_ID = pane.getAttribute('data-obra-id');
    window.__finCtx = { get panel() { return PANEL; }, render: render, BRL: BRL, OBRA_ID: function () { return OBRA_ID; } };
    var btn = document.querySelector('[data-bs-target="#tab-financeiro"]');
    if (btn) btn.addEventListener('shown.bs.tab', load);
    if (pane.classList.contains('active', 'show')) load();
  });
})();
```

- [ ] **Step 2: Verificação manual** (smoke de carregamento na Task 10). Por ora confirme que o arquivo é JS válido:

Run: `node --check static/js/financeiro_obra.js`
Expected: sem erro (se `node` indisponível, pule — a Task 10 valida via página).

- [ ] **Step 3: Commit**

```bash
git add static/js/financeiro_obra.js
git commit -m "feat(fin): financeiro_obra.js — KPIs, medições e 4 gráficos (Curva S 4 séries)"
```

### Task 9: Drill-down da etapa + edição inline

**Files:**
- Modify: `static/js/financeiro_obra.js`

- [ ] **Step 1: Adicionar `showEtapa` (substituindo o stub)** — antes do `document.addEventListener` final, defina:

```javascript
  function showEtapa(et) {
    var box = el('fin-etapa-det');
    box.innerHTML =
      '<div class="border rounded p-3 bg-light"><div class="d-flex justify-content-between mb-2">' +
      '<strong>' + et.nome + '</strong><span>Realizado: ' + BRL(et.realizado) + ' / Previsto: ' + BRL(et.previsto) + '</span></div>' +
      '<div class="row g-2 align-items-end">' +
      '<div class="col-auto"><label class="small text-muted">Veks (R$)</label>' +
      '<input id="ed-veks" type="number" class="form-control form-control-sm" value="' + Math.round(et.veks) + '"></div>' +
      '<div class="col-auto"><label class="small text-muted">Fat direto (R$)</label>' +
      '<input id="ed-fat" type="number" class="form-control form-control-sm" value="' + Math.round(et.fat) + '"></div>' +
      '<div class="col-auto"><label class="small text-muted">Orçado (R$)</label>' +
      '<input id="ed-orc" type="number" class="form-control form-control-sm" value="' + Math.round(et.previsto) + '"></div>' +
      '<div class="col-auto"><button id="ed-save" class="btn btn-primary btn-sm">Salvar</button></div>' +
      '</div></div>';
    el('ed-save').addEventListener('click', function () {
      if (et.osc_id == null) { alert('Etapa sem custo vinculável.'); return; }
      var fd = new FormData();
      fd.append('veks', el('ed-veks').value || '0');
      fd.append('fat', el('ed-fat').value || '0');
      fd.append('valor_orcado', el('ed-orc').value || '0');
      var oid = document.getElementById('tab-financeiro').getAttribute('data-obra-id');
      fetch('/obras/' + oid + '/financeiro/etapa/' + et.osc_id, { method: 'POST', body: fd })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (p) { render(p); box.innerHTML = '<div class="text-success small">Salvo e recalculado.</div>'; })
        .catch(function () { box.innerHTML = '<div class="text-danger small">Falha ao salvar.</div>'; });
    });
  }
  window.showEtapa = showEtapa;
```

> Como `showEtapa` referencia `render`, `BRL` e `el` (todas no mesmo IIFE), defina-a dentro do mesmo escopo do arquivo (não global). O `window.showEtapa = showEtapa;` apenas expõe para o `onClick` do chart, que chama `showEtapa(st[i])` — ajuste o `onClick` do gráfico de etapas (Task 8) para chamar a função local `showEtapa` diretamente (já chama). Remova o stub `window.showEtapa = window.showEtapa || ...` da Task 8.

- [ ] **Step 2: Validar JS**

Run: `node --check static/js/financeiro_obra.js`
Expected: sem erro (ou pule se `node` ausente).

- [ ] **Step 3: Commit**

```bash
git add static/js/financeiro_obra.js
git commit -m "feat(fin): drill-down da etapa com edição inline (POST recalcula painel)"
```

### Task 10: Smoke de render do painel (autenticado)

**Files:**
- Test: `tests/test_painel_financeiro.py`

- [ ] **Step 1: Escrever o smoke** — importa a fixture, garante v2, abre a página da obra e confere que a aba e o endpoint existem e respondem:

```python
@pytest.mark.integration
def test_pagina_obra_tem_aba_financeiro_e_endpoint():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Usuario
    import json
    with app.app_context():
        aid = _novo_admin()
        u = Usuario.query.get(aid); u.versao_sistema = 'v2'; db.session.commit()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(aid); s['_fresh'] = True
        page = c.get(f'/obras/{oid}', follow_redirects=True)
        assert page.status_code == 200
        html = page.get_data(as_text=True)
        assert 'tab-financeiro' in html
        assert 'financeiro_obra.js' in html
        # o endpoint JSON responde com as séries
        data = c.get(f'/obras/{oid}/financeiro/dados').get_json()
        assert len(data['curva_s']['meses']) == len(data['curva_s']['realizado'])
        assert len(data['etapas']) == 12
```

- [ ] **Step 2: Rodar**

Run: `pytest tests/test_painel_financeiro.py::test_pagina_obra_tem_aba_financeiro_e_endpoint -v`
Expected: PASS.

- [ ] **Step 3: Rodar a suíte do painel + regressões**

Run: `pytest tests/test_painel_financeiro.py tests/test_cronograma_fisico_financeiro.py tests/test_importacao_fisico_financeiro.py tests/test_resumo_custos_obra.py -q`
Expected: PASS (todos).

- [ ] **Step 4: Commit**

```bash
git add tests/test_painel_financeiro.py
git commit -m "test(fin): smoke da aba Financeiro + endpoint de dados"
```

---

## Checklist de cobertura do spec

- [x] Aba Financeiro vira painel estilo dashboard_baias → Tasks 7-9
- [x] Carregamento sob demanda via JSON + Chart.js no cliente → Tasks 4, 8
- [x] KPIs incl. Verba Disponível = caixa → Tasks 2, 3, 8
- [x] Custo por etapa clicável + edição inline → Tasks 3, 5, 9
- [x] Curva S com 4 séries (incl. custo realizado no tempo) → Tasks 1, 3, 8
- [x] Doughnut Veks×Fat + caixa por mês + medições → Tasks 3, 8
- [x] verba_disponivel=caixa + saldo_orcamentario no serviço compartilhado → Task 2
- [x] Realizado por mês/etapa de GestaoCustoFilho → Task 1
- [x] Rota FF antiga redireciona → Task 6
- [x] Mapa de Orçamentos surfaçado (link) → Task 7
- [x] Multitenant + testes → Tasks 4, 5, 10
- [x] EVM/Gantt/reforma do Mapa → fora de escopo (spec §8)

## Notas de execução

- A aba é **v2-gated** indiretamente? Não — a página da obra (`main.detalhes_obra`) não é v2-gated; só o antigo painel standalone era. Os testes setam v2 só por segurança do redirect; a aba Financeiro aparece para qualquer tenant.
- `Decimal` no backend; `float` só na fronteira JSON (`_jsonable`). Datas → ISO; o JS reformata para BR.
- Reusar `recalcular_servico` (de `resumo_custos_obra`) após editar o OSC — não recriar a lógica de recálculo.
- Se `montar_fisico_financeiro` agregar uma etapa a partir de múltiplos OSC, `osc_id=None` desabilita a edição inline daquela etapa (alert no clique). No piloto Baias é 1:1.
