# Painel Financeiro Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesenhar a aba Financeiro da obra (layout A — grade equilibrada, 9 KPIs em 3 grupos) e acabar com a deformação dos gráficos.

**Architecture:** Mudança só de front-end. O template ganha 3 cartões-grupo de KPI (Resultado/Caixa/Custo) com cabeçalho estático e corpo preenchido por JS, e os `<canvas>` passam a viver em wrappers `.fin-chart` de altura fixa. O `financeiro_obra.js` preenche cada grupo e não depende mais do atributo `height` no canvas. Sem mudança de backend/endpoint.

**Tech Stack:** Flask + Jinja2, Bootstrap 5, Chart.js, pytest.

**Spec:** `docs/superpowers/specs/2026-06-24-painel-financeiro-redesign-design.md`
**Branch:** `feat/painel-financeiro-redesign` (já criada)

---

## File Structure

- **Modify** `templates/obras/detalhes_obra_profissional.html` — bloco interno de `#tab-financeiro` (linhas 1524-1564): 3 cartões-grupo de KPI + wrappers `.fin-chart`.
- **Modify** `static/js/financeiro_obra.js` — `renderKPIs(k)` preenche os 3 grupos (ids `fin-kpi-resultado/caixa/custo`) em vez da fileira `#fin-kpis`.
- **Modify** `tests/test_painel_financeiro.py` — novo smoke de template.

Sem arquivos novos. Sem backend.

---

### Task 1: Smoke test do novo markup (RED)

**Files:**
- Test: `tests/test_painel_financeiro.py` (append no fim)

- [ ] **Step 1: Escrever o teste que falha**

Acrescente ao final de `tests/test_painel_financeiro.py`:

```python
@pytest.mark.integration
def test_painel_tem_grupos_kpi_e_wrappers_chart():
    # Redesign: 3 grupos de KPI (Resultado/Caixa/Custo) com corpo preenchido por
    # JS (ids fin-kpi-*) + cada canvas dentro de um wrapper .fin-chart de altura fixa.
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
        body = c.get(f'/obras/{oid}').get_data(as_text=True)
    # cabeçalhos dos 3 grupos (estáticos no template)
    for rotulo in ('Resultado', 'Caixa', 'Custo'):
        assert rotulo in body, rotulo
    # contêineres-alvo do JS
    for gid in ('fin-kpi-resultado', 'fin-kpi-caixa', 'fin-kpi-custo'):
        assert gid in body, gid
    # cada gráfico num wrapper de altura fixa; canvases sem height inline
    assert body.count('class="fin-chart"') >= 4
    for cid in ('finEtapas', 'finCurva', 'finSplit', 'finCaixa'):
        assert f'<canvas id="{cid}"></canvas>' in body, cid
```

- [ ] **Step 2: Rodar o teste e confirmar que FALHA**

Run: `python3 -m pytest tests/test_painel_financeiro.py::test_painel_tem_grupos_kpi_e_wrappers_chart -q`
Expected: FAIL (o template ainda tem a fileira `#fin-kpis` e canvases com `height=`, sem `fin-kpi-*` nem `.fin-chart`).

- [ ] **Step 3: Commit do teste vermelho**

```bash
git add tests/test_painel_financeiro.py
git commit -m "test(fin): smoke do redesign do painel (grupos KPI + wrappers .fin-chart)"
```

---

### Task 2: Reescrever o markup da aba (template)

**Files:**
- Modify: `templates/obras/detalhes_obra_profissional.html:1524-1564`

- [ ] **Step 1: Substituir o bloco interno de `#tab-financeiro`**

Substitua exatamente o trecho atual (de `<div id="fin-loading"...` na linha 1524 até `Não foi possível carregar o painel financeiro.</div>` na linha 1564) por:

```html
  <div id="fin-loading" class="text-muted py-4">Carregando painel financeiro…</div>
  <div id="fin-painel" style="display:none">

    <!-- Resumo: 3 grupos de KPI -->
    <div class="row g-3 mb-4">
      <div class="col-md-4"><div class="card h-100"><div class="card-body">
        <div class="text-uppercase small text-muted fw-bold mb-2">
          <i class="fas fa-chart-line me-1"></i>Resultado</div>
        <div id="fin-kpi-resultado"></div>
      </div></div></div>
      <div class="col-md-4"><div class="card h-100"><div class="card-body">
        <div class="text-uppercase small text-muted fw-bold mb-2">
          <i class="fas fa-wallet me-1"></i>Caixa</div>
        <div id="fin-kpi-caixa"></div>
      </div></div></div>
      <div class="col-md-4"><div class="card h-100"><div class="card-body">
        <div class="text-uppercase small text-muted fw-bold mb-2">
          <i class="fas fa-coins me-1"></i>Custo</div>
        <div id="fin-kpi-custo"></div>
      </div></div></div>
    </div>

    <!-- Custo por etapa -->
    <div class="card mb-4"><div class="card-body">
      <h6 class="fw-bold mb-3">Custo por etapa <small class="text-muted">(clique para editar)</small></h6>
      <div class="fin-chart" style="position:relative;height:360px"><canvas id="finEtapas"></canvas></div>
      <div id="fin-etapa-det" class="mt-3"></div>
    </div></div>

    <!-- Curva S + Doughnut -->
    <div class="row g-3 mb-4">
      <div class="col-lg-8"><div class="card h-100"><div class="card-body">
        <h6 class="fw-bold mb-3">Curva S — recebido, gasto, lucro e realizado</h6>
        <div class="fin-chart" style="position:relative;height:300px"><canvas id="finCurva"></canvas></div>
      </div></div></div>
      <div class="col-lg-4"><div class="card h-100"><div class="card-body">
        <h6 class="fw-bold mb-3">Veks × Faturamento direto</h6>
        <div class="fin-chart" style="position:relative;height:300px"><canvas id="finSplit"></canvas></div>
      </div></div></div>
    </div>

    <!-- Caixa + Medições -->
    <div class="row g-3 mb-4">
      <div class="col-lg-6"><div class="card h-100"><div class="card-body">
        <h6 class="fw-bold mb-3">Caixa final por mês</h6>
        <div class="fin-chart" style="position:relative;height:280px"><canvas id="finCaixa"></canvas></div>
      </div></div></div>
      <div class="col-lg-6"><div class="card h-100"><div class="card-body">
        <h6 class="fw-bold mb-3">Medições de contrato</h6>
        <div style="max-height:280px;overflow:auto">
          <table class="table table-sm mb-0"><thead><tr><th>Parcela</th><th>Data</th><th>%</th>
            <th class="text-end">Valor</th></tr></thead><tbody id="fin-medicoes"></tbody></table>
        </div>
      </div></div></div>
    </div>

    <div id="fin-alerta"></div>

    <!-- CTA Mapa de Orçamentos -->
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
```

Notas:
- Os ids `fin-loading`, `fin-painel`, `fin-etapa-det`, `fin-medicoes`, `fin-alerta`,
  `fin-erro` e os ids de canvas (`finEtapas/finCurva/finSplit/finCaixa`) são
  preservados — o JS depende deles.
- A fileira antiga `<div class="row g-3 mb-4" id="fin-kpis"></div>` é REMOVIDA
  (substituída pelos 3 grupos). O id `fin-kpis` deixa de existir.
- Os `<canvas>` perdem o atributo `height=...` (a altura vem do wrapper `.fin-chart`).

- [ ] **Step 2: Rodar o smoke do Task 1 e confirmar que PASSA**

Run: `python3 -m pytest tests/test_painel_financeiro.py::test_painel_tem_grupos_kpi_e_wrappers_chart -q`
Expected: PASS.

- [ ] **Step 3: Commit do template**

```bash
git add templates/obras/detalhes_obra_profissional.html
git commit -m "feat(fin): redesign da aba Financeiro — grupos de KPI + wrappers .fin-chart"
```

---

### Task 3: `renderKPIs` preenche os 3 grupos (JS)

**Files:**
- Modify: `static/js/financeiro_obra.js:12-28` (função `renderKPIs`)

- [ ] **Step 1: Substituir a função `renderKPIs`**

Substitua a função atual (linhas 12-28, de `function renderKPIs(k) {` até o `}` que fecha em ~28) por:

```javascript
  function kpiRow(label, valor, cls) {
    return '<div class="d-flex justify-content-between align-items-baseline py-1 border-bottom">' +
      '<span class="small text-muted">' + label + '</span>' +
      '<span class="fw-bold ' + (cls || '') + '" style="font-variant-numeric:tabular-nums">' +
      BRL(valor) + '</span></div>';
  }
  function renderKPIs(k) {
    var pos = function (v) { return (v || 0) >= 0 ? 'text-success' : 'text-danger'; };
    var pct = (k.lucro_pct != null)
      ? ' <small class="text-muted">(' + (k.lucro_pct * 100).toFixed(1) + '%)</small>' : '';
    el('fin-kpi-resultado').innerHTML =
      kpiRow('Venda (contrato)', k.venda, '') +
      kpiRow('Custo total', k.custo_total, '') +
      kpiRow('Imposto', k.imposto, '') +
      '<div class="d-flex justify-content-between align-items-baseline py-1">' +
        '<span class="small text-muted">Lucro projetado' + pct + '</span>' +
        '<span class="fw-bold ' + pos(k.lucro_projetado) + '" style="font-variant-numeric:tabular-nums">' +
        BRL(k.lucro_projetado) + '</span></div>';
    el('fin-kpi-caixa').innerHTML =
      kpiRow('Recebido até hoje', k.recebido_ate_hoje, '') +
      kpiRow('Verba disponível', k.verba_disponivel, pos(k.verba_disponivel)).replace('border-bottom', '');
    el('fin-kpi-custo').innerHTML =
      kpiRow('Desembolso Veks', k.desembolso_veks, '') +
      kpiRow('Faturamento direto', k.fat_direto, '') +
      kpiRow('Custo realizado', k.custo_realizado, '').replace('border-bottom', '');
  }
```

Notas:
- Usa o helper `BRL` já existente. O último item de cada grupo remove a borda
  inferior (`.replace('border-bottom','')`) para não deixar linha sobrando.
- Mantém exatamente os mesmos campos do payload — nenhuma mudança de contrato.

- [ ] **Step 2: Confirmar que a suíte do painel segue verde**

Run: `python3 -m pytest tests/test_painel_financeiro.py -q`
Expected: PASS (todos), incluindo o smoke novo.

- [ ] **Step 3: Commit do JS**

```bash
git add static/js/financeiro_obra.js
git commit -m "feat(fin): renderKPIs agrupado (Resultado/Caixa/Custo)"
```

---

### Task 4: Suíte completa do físico-financeiro verde + verificação manual

**Files:** nenhum (verificação).

- [ ] **Step 1: Rodar as suítes relacionadas**

Run: `python3 -m pytest tests/test_painel_financeiro.py tests/test_cronograma_fisico_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: PASS (todos). Nenhuma regressão (o contrato do endpoint não mudou).

- [ ] **Step 2: Verificação manual — gráficos não deformam + edição salva**

Run (renderiza o painel JSON e confere que os campos seguem corretos para a obra Baias do tenant Alfa):

```bash
python3 -c "
import sys; sys.path.insert(0,'/home/runner/workspace')
from main import app
app.config['WTF_CSRF_ENABLED']=False
c=app.test_client()
with c.session_transaction() as s: s['_user_id']='832'; s['_fresh']=True
r=c.get('/obras/detalhes/2515')
html=r.get_data(as_text=True)
print('status', r.status_code)
print('grupos:', all(x in html for x in ('Resultado','Caixa','Custo')))
print('wrappers .fin-chart:', html.count('class=\"fin-chart\"'))
print('canvas sem height:', all(f'<canvas id=\"{c}\"></canvas>' in html for c in ('finEtapas','finCurva','finSplit','finCaixa')))
"
```
Expected: `status 200`, `grupos: True`, `wrappers .fin-chart: 4`, `canvas sem height: True`.

Nota: confirmação visual final (gráficos com altura travada, edição inline salvando)
é feita pelo usuário no navegador logado como `admin_alfa`, abrindo a obra Baias
(codigo 10) → aba Financeiro.

- [ ] **Step 3: Sem commit (passo de verificação).** Se algo falhar, voltar ao Task correspondente.

---

## Self-Review

**1. Spec coverage:**
- Redesenho completo / layout A → Task 2 (markup) + Task 3 (JS). ✓
- 9 KPIs em 3 grupos → Task 2 (shells) + Task 3 (valores). ✓
- Fim da deformação (wrappers altura fixa + maintainAspectRatio:false) → Task 2 (wrappers, canvas sem height); `maintainAspectRatio:false` já está no JS atual e é preservado. ✓
- Consistente com o sistema (cards/cores/ícones FontAwesome) → Task 2. ✓
- Sem backend → nenhum task toca backend. ✓
- Testes: smokes atuais verdes + novo smoke → Task 1 + Task 4. ✓

**2. Placeholder scan:** sem TBD/TODO; todo passo tem código/comando completo. ✓

**3. Type/consistency:** ids preservados (`fin-loading/painel/erro/etapa-det/medicoes/alerta`, `finEtapas/finCurva/finSplit/finCaixa`); novos ids `fin-kpi-resultado/caixa/custo` usados igualmente no template (Task 2) e no JS (Task 3); helper `BRL` reusado. ✓
