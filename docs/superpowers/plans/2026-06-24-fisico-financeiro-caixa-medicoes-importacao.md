# Físico-Financeiro: Caixa + Medições de Contrato + Importação Completa — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Importar um JSON deixa a obra inteira planejada (cronograma + custo + vinculação atividade↔custo + medições de contrato + snapshot de caixa) e o painel Físico-Financeiro abre pronto, com KPIs, medições, fluxo de caixa (verbatim × recalculado) e alerta da inconsistência dos Indiretos.

**Architecture:** Estende a Abordagem A — derivado (`docs/superpowers/specs/2026-06-24-fisico-financeiro-caixa-medicoes-importacao-design.md`). Modelo novo `MedicaoContrato` (entidade fixa, **não** refatora `MedicaoObra`) + coluna `Obra.fluxo_caixa_planilha` (snapshot verbatim). Importador popula modelos existentes; serviço derivado ganha funções puras (caixa, medições, divergência, KPIs); view/template existentes ganham seções novas. EVM/Curva física/Gantt adiados.

**Tech Stack:** Flask + SQLAlchemy (Postgres), Jinja2 + Bootstrap 5 (`templates/base_completo.html`), Chart.js local, `openpyxl`, pytest (marcadores `@integration`/`@browser`), `Decimal` para dinheiro.

---

## Mapa de arquivos

| Arquivo | Responsabilidade | Ação |
|---|---|---|
| `models.py` | `MedicaoContrato` + `Obra.fluxo_caixa_planilha` | **Modificar** |
| `migrations.py` | Migração 197 (`medicao_contrato`) + 198 (`obra.fluxo_caixa_planilha`) | **Modificar** |
| `services/cronograma_fisico_financeiro.py` | Funções puras: `calcular_fluxo_caixa`, `comparar_fluxo_caixa`; wrappers `medicoes_contrato`, `fluxo_caixa`, `fluxo_caixa_divergencia`, `kpis`; ampliar `montar_fisico_financeiro` (`meses_veks`/`meses_fat`) | **Modificar** |
| `tests/test_cronograma_fisico_financeiro.py` | Testes das funções puras novas | **Modificar** |
| `services/importacao_fisico_financeiro.py` | Parse do JSON → popular modelos existentes (idempotente, tenant-scoped) | **Criar** |
| `tests/test_importacao_fisico_financeiro.py` | Integração do importador com números do JSON | **Criar** |
| `cronograma_views.py:2531` | Passar novas séries ao template | **Modificar** |
| `importacao_views.py` | Rota de upload do JSON → importar → redirecionar ao painel | **Modificar** |
| `templates/cronograma/fisico_financeiro.html` | KPIs, medições, fluxo de caixa, alerta Indiretos | **Modificar** |
| `tests/test_fisico_financeiro_painel_playwright.py` | Smoke da página | **Criar** |

**Dados de referência (fonte de verdade do piloto):** `cronograma_fisico_financeiro_baias.json` (de `files.zip`). Estrutura: `obra`, `contrato{valor_venda:1505613.76, data_inicio:"2026-06-04", data_fim_cronograma:"2026-09-11"}`, `parametros{imposto_pct:0.135}`, `medicoes[6]{nome,data,pct,recebido_no_mes,obs}` (Σpct=1), `eap[12]{codigo,nome,grupo,cronograma{inicio,fim,pct_fisico,tarefas_mpp[],transversal},custo{veks,fat_direto,total,peso_pct},itens[]}` (1 transversal=Indiretos), `cronograma_tarefas[43]{id,nivel,nome,inicio,fim,dias,pct_fisico,predecessoras[],marco,resumo}`, `fluxo_caixa_mensal{meses[],medicao[],entrada_liquida[],caixa_inicial[],caixa_final[],gasto_veks[],fat_direto[],imposto[],custo_veks_por_mes{direto[],indireto[]},lucro_caixa_final:152047,inconsistencia}`, `resumo{custo_total:1158160,desembolso_veks:734460,faturamento_direto:423700}`.

**Setup para os testes:** o JSON está em `files.zip` na raiz. Descompacte uma vez antes de rodar os testes:
```bash
unzip -o files.zip cronograma_fisico_financeiro_baias.json -d tests/fixtures/
```
Os testes de importação carregam `tests/fixtures/cronograma_fisico_financeiro_baias.json`.

**Convenções fixas (JSON → modelos existentes):**
- `Obra`: find-or-create por (`codigo`=`obra.codigo_obra`, `admin_id`). `valor_contrato`=`contrato.valor_venda`; `data_inicio`=`contrato.data_inicio`; `data_previsao_fim`=`contrato.data_fim_cronograma`; `cliente_id` via `services.cliente_resolver.obter_ou_criar_cliente`.
- Por **etapa**: 1 `TarefaCronograma` raiz (`tarefa_pai_id=None`, datas da etapa) + N folhas (1 por id em `tarefas_mpp`, datas de `cronograma_tarefas`); transversal/sem `tarefas_mpp` → 1 folha com datas da etapa.
- 1 `ItemMedicaoComercial` por etapa (`valor_comercial`=`round(peso_pct×valor_venda,2)`).
- 1 `ItemMedicaoCronogramaTarefa` por folha (`peso`=`max(1, dias da folha)`).
- 1 `ObraServicoCusto` por etapa: `valor_orcado`=`custo.total`; `mao_obra_a_realizar`=`custo.veks`/`fonte_mao_obra='veks'`; `material_a_realizar`=`custo.fat_direto`/`fonte_material='fat_direto'`; `outros_a_realizar=0`/`fonte_outros='veks'`; `realizado_*=0`.
- `medicoes[i]` → `MedicaoContrato` (`nome,data,pct,recebido_no_mes,obs,ordem=i`). **Não** cria `MedicaoObra`.
- `fluxo_caixa_mensal` → `Obra.fluxo_caixa_planilha` (verbatim).

---

## Fase 1 — Modelo + migrações

### Task 1: Modelo `MedicaoContrato` + migração 197

**Files:**
- Modify: `models.py` (após `MedicaoObraItem`, ~linha 5317)
- Modify: `migrations.py` (função nova + registro na lista de `executar_migracoes`)
- Test: `tests/test_importacao_fisico_financeiro.py`

- [ ] **Step 1: Escrever o teste de schema que falha**

```python
# tests/test_importacao_fisico_financeiro.py
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

import pytest
from decimal import Decimal
from app import app, db
from models import MedicaoContrato


@pytest.mark.integration
def test_medicao_contrato_schema_existe():
    with app.app_context():
        # smoke: a tabela existe e aceita insert/rollback
        cols = {c.name for c in MedicaoContrato.__table__.columns}
        assert {'obra_id', 'admin_id', 'nome', 'data', 'pct',
                'recebido_no_mes', 'obs', 'ordem'} <= cols
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_importacao_fisico_financeiro.py::test_medicao_contrato_schema_existe -v`
Expected: FAIL com `ImportError: cannot import name 'MedicaoContrato'`.

- [ ] **Step 3: Adicionar o modelo em `models.py`** (após a classe `MedicaoObraItem`)

```python
class MedicaoContrato(db.Model):
    """Medição de contrato (cronograma de faturamento FIXO pelo contrato).
    Distinta de MedicaoObra (medição por execução). valor = pct × valor_contrato."""
    __tablename__ = 'medicao_contrato'

    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id', ondelete='CASCADE'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nome = db.Column(db.String(120), nullable=False)
    data = db.Column(db.Date)
    pct = db.Column(db.Numeric(7, 5), nullable=False, default=0)
    recebido_no_mes = db.Column(db.String(8))
    obs = db.Column(db.Text)
    ordem = db.Column(db.Integer, default=0)

    obra = db.relationship('Obra', backref='medicoes_contrato')

    @property
    def valor(self):
        from decimal import Decimal as _D
        return (_D(str(self.obra.valor_contrato or 0)) * _D(str(self.pct or 0)))

    __table_args__ = (
        db.Index('ix_medicao_contrato_obra', 'obra_id'),
        db.Index('ix_medicao_contrato_admin', 'admin_id'),
    )

    def __repr__(self):
        return f'<MedicaoContrato {self.nome} obra={self.obra_id}>'
```

- [ ] **Step 4: Adicionar a migração 197 em `migrations.py`** (junto das demais `_migration_*`, ex.: após `_migration_196_...`)

```python
def _migration_197_medicao_contrato():
    """Físico-financeiro — cria tabela medicao_contrato (cronograma de
    faturamento fixo pelo contrato). Idempotente."""
    from sqlalchemy import text as sa_text
    try:
        with db.engine.begin() as conn:
            conn.execute(sa_text("""
                CREATE TABLE IF NOT EXISTS medicao_contrato (
                    id SERIAL PRIMARY KEY,
                    obra_id INTEGER NOT NULL REFERENCES obra(id) ON DELETE CASCADE,
                    admin_id INTEGER NOT NULL REFERENCES usuario(id),
                    nome VARCHAR(120) NOT NULL,
                    data DATE,
                    pct NUMERIC(7,5) NOT NULL DEFAULT 0,
                    recebido_no_mes VARCHAR(8),
                    obs TEXT,
                    ordem INTEGER DEFAULT 0
                )
            """))
            conn.execute(sa_text("CREATE INDEX IF NOT EXISTS ix_medicao_contrato_obra ON medicao_contrato(obra_id)"))
            conn.execute(sa_text("CREATE INDEX IF NOT EXISTS ix_medicao_contrato_admin ON medicao_contrato(admin_id)"))
        logger.info("[Migration 197] medicao_contrato criada.")
    except Exception as e:
        logger.error(f"[Migration 197] Falha: {e}", exc_info=True)
        raise
```

- [ ] **Step 5: Registrar 197 na lista de `executar_migracoes`** (em `migrations.py:~3996`, após a tupla `(196, ...)`)

```python
            (196, "fonte pagamento Veks/Fat em obra_servico_custo", _migration_196_obra_servico_custo_fonte_pagamento),
            (197, "Físico-financeiro — tabela medicao_contrato", _migration_197_medicao_contrato),
```

- [ ] **Step 6: Rodar e ver passar**

Run: `pytest tests/test_importacao_fisico_financeiro.py::test_medicao_contrato_schema_existe -v`
Expected: PASS (a migração roda no boot do app via `app_context`; se o ambiente de teste não rodar migrações automaticamente, chame `from migrations import executar_migracoes; executar_migracoes()` dentro do `app_context` no topo do teste).

- [ ] **Step 7: Commit**

```bash
git add models.py migrations.py tests/test_importacao_fisico_financeiro.py
git commit -m "feat(ff): modelo MedicaoContrato + migração 197"
```

### Task 2: Coluna `Obra.fluxo_caixa_planilha` + migração 198

**Files:**
- Modify: `models.py` (classe `Obra`, ~linha 254 após `valor_contrato`)
- Modify: `migrations.py`
- Test: `tests/test_importacao_fisico_financeiro.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
@pytest.mark.integration
def test_obra_tem_coluna_fluxo_caixa_planilha():
    from models import Obra
    assert 'fluxo_caixa_planilha' in {c.name for c in Obra.__table__.columns}
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_importacao_fisico_financeiro.py::test_obra_tem_coluna_fluxo_caixa_planilha -v`
Expected: FAIL (`assert` falha — coluna não existe).

- [ ] **Step 3: Adicionar a coluna em `models.py`** (classe `Obra`, após `valor_contrato`)

```python
    fluxo_caixa_planilha = db.Column(db.JSON)  # snapshot verbatim da Planilha1 (fluxo_caixa_mensal)
```

- [ ] **Step 4: Migração 198 em `migrations.py`**

```python
def _migration_198_obra_fluxo_caixa_planilha():
    """Físico-financeiro — coluna JSON para o snapshot verbatim do fluxo de
    caixa da Planilha1. Idempotente."""
    from sqlalchemy import text as sa_text
    try:
        with db.engine.begin() as conn:
            conn.execute(sa_text("""
                ALTER TABLE obra
                  ADD COLUMN IF NOT EXISTS fluxo_caixa_planilha JSONB
            """))
        logger.info("[Migration 198] obra.fluxo_caixa_planilha adicionada.")
    except Exception as e:
        logger.error(f"[Migration 198] Falha: {e}", exc_info=True)
        raise
```

- [ ] **Step 5: Registrar 198 na lista** (após a tupla `(197, ...)`)

```python
            (198, "Físico-financeiro — obra.fluxo_caixa_planilha (snapshot verbatim)", _migration_198_obra_fluxo_caixa_planilha),
```

- [ ] **Step 6: Rodar e ver passar**

Run: `pytest tests/test_importacao_fisico_financeiro.py::test_obra_tem_coluna_fluxo_caixa_planilha -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add models.py migrations.py tests/test_importacao_fisico_financeiro.py
git commit -m "feat(ff): Obra.fluxo_caixa_planilha (snapshot) + migração 198"
```

---

## Fase 2 — Funções puras do serviço (sem DB, TDD)

### Task 3: `calcular_fluxo_caixa` (núcleo puro do caixa)

Regra confirmada na Planilha1: `imposto` e `fat_direto` são do **período anterior**.
- `imposto[m] = (medicao[m] − fat_anterior) × imposto_pct`
- `entrada[m] = medicao[m] − fat_anterior − imposto[m]`
- `caixa_inicial[m] = entrada[m]` (1º mês) ou `caixa_final[m−1] + entrada[m]`
- `caixa_final[m] = caixa_inicial[m] − gasto_veks[m]`
- `lucro_em_caixa = caixa_final[último mês]`
- `fat_anterior` começa em 0 e, ao fim de cada mês, vira `fat_direto[m]`.

**Files:**
- Modify: `services/cronograma_fisico_financeiro.py`
- Test: `tests/test_cronograma_fisico_financeiro.py`

- [ ] **Step 1: Escrever o teste que falha** (anexar ao fim de `tests/test_cronograma_fisico_financeiro.py`)

```python
from services.cronograma_fisico_financeiro import calcular_fluxo_caixa


def test_caixa_rolante_2_meses_sem_fat():
    meses = ["2026-06", "2026-07"]
    res = calcular_fluxo_caixa(
        meses,
        medicao={"2026-06": D("100000"), "2026-07": D("50000")},
        fat_direto={"2026-06": D("0"), "2026-07": D("0")},
        gasto_veks={"2026-06": D("30000"), "2026-07": D("20000")},
        imposto_pct=D("0.135"),
    )
    jun, jul = res["linhas"]
    # jun: imposto=(100000-0)*0.135=13500; entrada=86500; caixa_ini=86500; caixa_fim=56500
    assert jun["imposto"] == D("13500.00")
    assert jun["entrada"] == D("86500.00")
    assert jun["caixa_final"] == D("56500.00")
    # jul: fat_anterior=0; imposto=6750; entrada=43250; caixa_ini=56500+43250=99750; caixa_fim=79750
    assert jul["caixa_inicial"] == D("99750.00")
    assert jul["caixa_final"] == D("79750.00")
    assert res["lucro_em_caixa"] == D("79750.00")


def test_caixa_fat_do_periodo_anterior():
    meses = ["2026-06", "2026-07"]
    res = calcular_fluxo_caixa(
        meses,
        medicao={"2026-06": D("100000"), "2026-07": D("100000")},
        fat_direto={"2026-06": D("40000"), "2026-07": D("0")},
        gasto_veks={"2026-06": D("0"), "2026-07": D("0")},
        imposto_pct=D("0.135"),
    )
    jun, jul = res["linhas"]
    # jun: fat_anterior=0 -> imposto=13500, entrada=86500
    assert jun["entrada"] == D("86500.00")
    # jul: fat_anterior=40000 -> imposto=(100000-40000)*0.135=8100; entrada=100000-40000-8100=51900
    assert jul["imposto"] == D("8100.00")
    assert jul["entrada"] == D("51900.00")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_cronograma_fisico_financeiro.py -k caixa -v`
Expected: FAIL com `ImportError: cannot import name 'calcular_fluxo_caixa'`.

- [ ] **Step 3: Implementar em `services/cronograma_fisico_financeiro.py`**

```python
def calcular_fluxo_caixa(meses, medicao, fat_direto, gasto_veks, imposto_pct):
    """Modelo de caixa derivado. Dicts mes->Decimal. fat_direto e imposto são do
    PERÍODO ANTERIOR (regra da Planilha1). Retorna {linhas:[...], lucro_em_caixa}."""
    imposto_pct = Decimal(imposto_pct)
    fat_anterior = Decimal("0")
    caixa_final_anterior = None
    linhas = []
    for m in meses:
        med = Decimal(medicao.get(m, 0) or 0)
        imp = ((med - fat_anterior) * imposto_pct).quantize(CENTAVO, ROUND_HALF_UP)
        entrada = (med - fat_anterior - imp).quantize(CENTAVO, ROUND_HALF_UP)
        if caixa_final_anterior is None:
            caixa_ini = entrada
        else:
            caixa_ini = caixa_final_anterior + entrada
        veks = Decimal(gasto_veks.get(m, 0) or 0)
        caixa_fim = (caixa_ini - veks).quantize(CENTAVO, ROUND_HALF_UP)
        linhas.append({
            "mes": m, "medicao": med, "fat_anterior": fat_anterior,
            "imposto": imp, "entrada": entrada,
            "caixa_inicial": caixa_ini, "gasto_veks": veks, "caixa_final": caixa_fim,
        })
        fat_anterior = Decimal(fat_direto.get(m, 0) or 0)
        caixa_final_anterior = caixa_fim
    return {
        "linhas": linhas,
        "lucro_em_caixa": linhas[-1]["caixa_final"] if linhas else Decimal("0"),
    }
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_cronograma_fisico_financeiro.py -k caixa -v`
Expected: PASS (2 testes).

- [ ] **Step 5: Commit**

```bash
git add services/cronograma_fisico_financeiro.py tests/test_cronograma_fisico_financeiro.py
git commit -m "feat(ff): calcular_fluxo_caixa (regra fat/imposto do período anterior)"
```

### Task 4: `comparar_fluxo_caixa` (divergência recalc × verbatim)

**Files:**
- Modify: `services/cronograma_fisico_financeiro.py`
- Test: `tests/test_cronograma_fisico_financeiro.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
from services.cronograma_fisico_financeiro import comparar_fluxo_caixa


def test_divergencia_por_mes_e_resumo_veks():
    recalc = {"2026-06": D("100000"), "2026-07": D("100000")}   # gasto_veks recalc
    verbatim = {"2026-06": D("130000"), "2026-07": D("100000")} # gasto_veks planilha
    res = comparar_fluxo_caixa(recalc, verbatim)
    assert res["por_mes"]["2026-06"]["delta"] == D("30000")     # verbatim - recalc
    assert res["por_mes"]["2026-07"]["delta"] == D("0")
    assert res["total_recalc"] == D("200000")
    assert res["total_verbatim"] == D("230000")
    assert res["delta_total"] == D("30000")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_cronograma_fisico_financeiro.py -k divergencia -v`
Expected: FAIL com `ImportError`.

- [ ] **Step 3: Implementar**

```python
def comparar_fluxo_caixa(recalc, verbatim):
    """Compara dois dicts mes->Decimal (ex.: gasto_veks recalculado × verbatim).
    delta = verbatim - recalc por mês e no total."""
    meses = sorted(set(recalc) | set(verbatim))
    por_mes = {}
    total_r = Decimal("0")
    total_v = Decimal("0")
    for m in meses:
        r = Decimal(recalc.get(m, 0) or 0)
        v = Decimal(verbatim.get(m, 0) or 0)
        por_mes[m] = {"recalc": r, "verbatim": v, "delta": v - r}
        total_r += r
        total_v += v
    return {
        "por_mes": por_mes,
        "total_recalc": total_r,
        "total_verbatim": total_v,
        "delta_total": total_v - total_r,
    }
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_cronograma_fisico_financeiro.py -k divergencia -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/cronograma_fisico_financeiro.py tests/test_cronograma_fisico_financeiro.py
git commit -m "feat(ff): comparar_fluxo_caixa (delta verbatim - recalc)"
```

### Task 5: Ampliar `montar_fisico_financeiro` com `meses_veks`/`meses_fat`

O caixa recalculado precisa do **Veks faseado por mês** (e fat por mês). Hoje o orquestrador só acumula o previsto total (`meses_globais`). Vamos acumular também a fração Veks e Fat por mês, proporcional a cada `ObraServicoCusto`.

**Files:**
- Modify: `services/cronograma_fisico_financeiro.py` (função `montar_fisico_financeiro`)
- Test: `tests/test_cronograma_fisico_financeiro.py`

- [ ] **Step 1: Escrever o teste que falha** (testa a chave nova no retorno, com obra mínima em memória)

```python
@pytest.mark.integration
def test_montar_inclui_meses_veks_e_fat():
    # smoke estrutural: as chaves existem mesmo sem dados
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))
    from app import app
    from services.cronograma_fisico_financeiro import montar_fisico_financeiro
    with app.app_context():
        dados = montar_fisico_financeiro(obra_id=-1, admin_id=-1)  # obra inexistente
    assert "meses_veks" in dados and "meses_fat" in dados
    assert dados["meses_veks"] == {} and dados["meses_fat"] == {}
```

> Adicione `import pytest` no topo do arquivo de teste se ainda não houver.

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_cronograma_fisico_financeiro.py::test_montar_inclui_meses_veks_e_fat -v`
Expected: FAIL (`KeyError`/`assert` — chaves ausentes).

- [ ] **Step 3: Modificar `montar_fisico_financeiro`**

Adicionar os acumuladores e preencher dentro do loop de faseamento. Localizar `meses_globais: dict = {}` e adicionar ao lado:

```python
    meses_veks: dict = {}
    meses_fat: dict = {}
```

Dentro do bloco que faseia (`for tarefa_id, valor_tarefa in aloc.items():`), após calcular `fases`, repartir cada parcela em Veks/Fat pela razão do OSC. **Imediatamente antes** desse `for`, calcular a razão do OSC (usar `previsto_total`, `veks`, `fat` já calculados no escopo):

```python
            razao_veks = (veks / previsto_total) if previsto_total else Decimal("0")
            razao_fat = (fat / previsto_total) if previsto_total else Decimal("0")
```

E dentro do laço dos meses (onde já faz `meses_globais[mes] = ... + parcela`), acrescentar:

```python
                    meses_veks[mes] = meses_veks.get(mes, Decimal("0")) + (parcela * razao_veks)
                    meses_fat[mes] = meses_fat.get(mes, Decimal("0")) + (parcela * razao_fat)
```

Por fim, no `return`, acrescentar as duas chaves:

```python
        "meses_veks": meses_veks,
        "meses_fat": meses_fat,
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_cronograma_fisico_financeiro.py::test_montar_inclui_meses_veks_e_fat -v`
Expected: PASS.

- [ ] **Step 5: Rodar a suíte do serviço (regressão)**

Run: `pytest tests/test_cronograma_fisico_financeiro.py -v`
Expected: PASS (todos, incluindo os antigos).

- [ ] **Step 6: Commit**

```bash
git add services/cronograma_fisico_financeiro.py tests/test_cronograma_fisico_financeiro.py
git commit -m "feat(ff): montar_fisico_financeiro expõe meses_veks/meses_fat"
```

---

## Fase 3 — Importador (integração, DB)

### Task 6: Esqueleto do importador + upsert da Obra/Cliente

**Files:**
- Create: `services/importacao_fisico_financeiro.py`
- Test: `tests/test_importacao_fisico_financeiro.py`

- [ ] **Step 1: Escrever helper de fixture + teste que falha** (anexar ao arquivo de teste)

```python
import json
from datetime import date, datetime
from werkzeug.security import generate_password_hash


def _carregar_json():
    caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                           'cronograma_fisico_financeiro_baias.json')
    with open(caminho, encoding='utf-8') as f:
        return json.load(f)


def _novo_admin():
    from models import Usuario, TipoUsuario
    tag = datetime.utcnow().strftime('%H%M%S%f')
    u = Usuario(username=f'ff_{tag}', email=f'ff_{tag}@test.local',
                nome=f'Admin FF {tag}',
                password_hash=generate_password_hash('senha123'),
                tipo_usuario=TipoUsuario.ADMIN)
    db.session.add(u)
    db.session.commit()
    return u.id


@pytest.mark.integration
def test_importa_cria_obra_com_contrato():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Obra
    with app.app_context():
        admin_id = _novo_admin()
        res = importar_fisico_financeiro(_carregar_json(), admin_id)
        obra = Obra.query.get(res['obra_id'])
        assert obra.admin_id == admin_id
        assert abs(float(obra.valor_contrato) - 1505613.76) < 0.01
        assert obra.data_inicio == date(2026, 6, 4)
        assert obra.data_previsao_fim == date(2026, 9, 11)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_importacao_fisico_financeiro.py::test_importa_cria_obra_com_contrato -v`
Expected: FAIL com `ModuleNotFoundError: services.importacao_fisico_financeiro`.

- [ ] **Step 3: Criar `services/importacao_fisico_financeiro.py`**

```python
"""Importa o JSON físico-financeiro (snapshot Planilha1 + cronograma) e deixa a
obra inteira planejada: cronograma, custo por etapa, vinculação atividade↔custo,
medições de contrato e snapshot de caixa. Idempotente e tenant-scoped.
Reaproveita os modelos existentes (Abordagem A — derivado)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal


def _parse_date(s):
    if not s:
        return None
    return date.fromisoformat(s[:10])


def importar_fisico_financeiro(payload: dict, admin_id: int) -> dict:
    from app import db
    from models import Obra
    from services.cliente_resolver import obter_ou_criar_cliente

    obra_j = payload['obra']
    contrato = payload.get('contrato', {})

    cliente = obter_ou_criar_cliente(nome=obra_j.get('cliente'), admin_id=admin_id)
    codigo = obra_j.get('codigo_obra') or obra_j.get('nome')

    obra = Obra.query.filter_by(codigo=codigo, admin_id=admin_id).first()
    if obra is None:
        obra = Obra(codigo=codigo, admin_id=admin_id, nome=obra_j.get('nome'),
                    data_inicio=_parse_date(contrato.get('data_inicio')) or date.today())
        db.session.add(obra)
    obra.nome = obra_j.get('nome')
    obra.valor_contrato = float(contrato.get('valor_venda') or 0)
    obra.data_inicio = _parse_date(contrato.get('data_inicio')) or obra.data_inicio
    obra.data_previsao_fim = _parse_date(contrato.get('data_fim_cronograma'))
    if cliente is not None:
        obra.cliente_id = cliente.id
    db.session.flush()

    avisos: list[str] = []
    # (etapas, medições, snapshot — próximas tasks)
    db.session.commit()
    return {'obra_id': obra.id, 'avisos': avisos}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_importacao_fisico_financeiro.py::test_importa_cria_obra_com_contrato -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/importacao_fisico_financeiro.py tests/test_importacao_fisico_financeiro.py
git commit -m "feat(ff): importador — esqueleto + upsert Obra/Cliente"
```

### Task 7: Importar etapas → cronograma + custo + vinculação

**Files:**
- Modify: `services/importacao_fisico_financeiro.py`
- Test: `tests/test_importacao_fisico_financeiro.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
@pytest.mark.integration
def test_importa_cria_etapas_tarefas_e_custos():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import (TarefaCronograma, ItemMedicaoComercial,
                        ItemMedicaoCronogramaTarefa, ObraServicoCusto)
    with app.app_context():
        admin_id = _novo_admin()
        res = importar_fisico_financeiro(_carregar_json(), admin_id)
        oid = res['obra_id']
        raizes = TarefaCronograma.query.filter_by(obra_id=oid, admin_id=admin_id,
                                                  tarefa_pai_id=None).count()
        assert raizes == 12  # 12 etapas da EAP
        folhas = TarefaCronograma.query.filter(
            TarefaCronograma.obra_id == oid,
            TarefaCronograma.admin_id == admin_id,
            TarefaCronograma.tarefa_pai_id.isnot(None)).count()
        assert folhas >= 12
        assert ItemMedicaoComercial.query.filter_by(obra_id=oid).count() == 12
        assert ItemMedicaoCronogramaTarefa.query.filter_by(admin_id=admin_id).count() == folhas
        # custo: Σ veks ≈ 734.460 ; Σ fat ≈ 423.700
        oscs = ObraServicoCusto.query.filter_by(obra_id=oid, admin_id=admin_id).all()
        soma_veks = sum(float(o.mao_obra_a_realizar or 0) for o in oscs)
        soma_fat = sum(float(o.material_a_realizar or 0) for o in oscs)
        assert abs(soma_veks - 734460) < 50
        assert abs(soma_fat - 423700) < 50
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_importacao_fisico_financeiro.py::test_importa_cria_etapas_tarefas_e_custos -v`
Expected: FAIL (`assert raizes == 12` → 0; etapas ainda não importadas).

- [ ] **Step 3: Implementar a importação de etapas** (substituir o comentário `# (etapas...)` em `importar_fisico_financeiro`)

```python
    from models import (TarefaCronograma, ItemMedicaoComercial,
                        ItemMedicaoCronogramaTarefa, ObraServicoCusto)

    # Mapa de datas das tarefas do MS Project por id
    tarefas_mpp = {t['id']: t for t in payload.get('cronograma_tarefas', [])}

    # Limpa coleções derivadas da obra (idempotência) — ordem respeita FKs
    ids_imc = [r[0] for r in db.session.query(ItemMedicaoComercial.id)
               .filter_by(obra_id=obra.id).all()]
    if ids_imc:
        ItemMedicaoCronogramaTarefa.query.filter(
            ItemMedicaoCronogramaTarefa.item_medicao_id.in_(ids_imc)).delete(synchronize_session=False)
    ObraServicoCusto.query.filter_by(obra_id=obra.id, admin_id=admin_id).delete(synchronize_session=False)
    ItemMedicaoComercial.query.filter_by(obra_id=obra.id).delete(synchronize_session=False)
    TarefaCronograma.query.filter_by(obra_id=obra.id, admin_id=admin_id).delete(synchronize_session=False)
    db.session.flush()

    valor_venda = Decimal(str(contrato.get('valor_venda') or 0))

    for etapa in payload.get('eap', []):
        cron = etapa.get('cronograma', {})
        custo = etapa.get('custo', {})
        di = _parse_date(cron.get('inicio'))
        df = _parse_date(cron.get('fim'))

        raiz = TarefaCronograma(obra_id=obra.id, admin_id=admin_id,
                                nome_tarefa=etapa['nome'], tarefa_pai_id=None,
                                data_inicio=di, data_fim=df,
                                percentual_concluido=0)
        db.session.add(raiz)
        db.session.flush()

        folhas_ids = cron.get('tarefas_mpp') or []
        folhas = []
        if folhas_ids:
            for tid in folhas_ids:
                t = tarefas_mpp.get(tid, {})
                fdi = _parse_date(t.get('inicio')) or di
                fdf = _parse_date(t.get('fim')) or df
                folhas.append((t.get('nome') or etapa['nome'], fdi, fdf,
                               int(t.get('dias') or 1)))
        else:
            dias = (df - di).days + 1 if (di and df) else 1
            folhas.append((etapa['nome'], di, df, max(1, dias)))

        peso_pct = Decimal(str(custo.get('peso_pct') or 0))
        imc = ItemMedicaoComercial(
            obra_id=obra.id, admin_id=admin_id, nome=etapa['nome'],
            valor_comercial=(valor_venda * peso_pct).quantize(Decimal('0.01')))
        db.session.add(imc)
        db.session.flush()

        for nome_f, fdi, fdf, dias in folhas:
            folha = TarefaCronograma(obra_id=obra.id, admin_id=admin_id,
                                     nome_tarefa=nome_f, tarefa_pai_id=raiz.id,
                                     data_inicio=fdi, data_fim=fdf,
                                     duracao_dias=dias, percentual_concluido=0)
            db.session.add(folha)
            db.session.flush()
            db.session.add(ItemMedicaoCronogramaTarefa(
                item_medicao_id=imc.id, cronograma_tarefa_id=folha.id,
                admin_id=admin_id, peso=max(1, dias)))

        db.session.add(ObraServicoCusto(
            obra_id=obra.id, admin_id=admin_id, nome=etapa['nome'],
            item_medicao_comercial_id=imc.id,
            valor_orcado=Decimal(str(custo.get('total') or 0)),
            mao_obra_a_realizar=Decimal(str(custo.get('veks') or 0)),
            fonte_mao_obra='veks',
            material_a_realizar=Decimal(str(custo.get('fat_direto') or 0)),
            fonte_material='fat_direto',
            outros_a_realizar=Decimal('0'), fonte_outros='veks',
            realizado_material=0, realizado_mao_obra=0, realizado_outros=0))
```

> **Nota:** confirme os nomes exatos dos campos de `ObraServicoCusto` em `models.py:5563+` (ex.: se há `nome`/`servico_catalogo_id` obrigatórios). Ajuste o construtor aos campos NOT NULL existentes.

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_importacao_fisico_financeiro.py::test_importa_cria_etapas_tarefas_e_custos -v`
Expected: PASS.

- [ ] **Step 5: Verificar que o painel deriva** (o serviço já existente roda sobre os dados importados)

```python
@pytest.mark.integration
def test_painel_deriva_apos_import():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import montar_fisico_financeiro
    with app.app_context():
        admin_id = _novo_admin()
        oid = importar_fisico_financeiro(_carregar_json(), admin_id)['obra_id']
        dados = montar_fisico_financeiro(oid, admin_id)
        assert len(dados['etapas']) == 12
        assert dados['totais']['total'] > 0
        assert dados['meses_veks']  # Veks faseado por mês não-vazio
```

Run: `pytest tests/test_importacao_fisico_financeiro.py::test_painel_deriva_apos_import -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/importacao_fisico_financeiro.py tests/test_importacao_fisico_financeiro.py
git commit -m "feat(ff): importador — etapas, tarefas (raiz+folhas), IMC, vínculo e custo"
```

### Task 8: Importar medições de contrato + snapshot de caixa

**Files:**
- Modify: `services/importacao_fisico_financeiro.py`
- Test: `tests/test_importacao_fisico_financeiro.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
@pytest.mark.integration
def test_importa_medicoes_e_snapshot():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import Obra, MedicaoContrato, MedicaoObra
    with app.app_context():
        admin_id = _novo_admin()
        oid = importar_fisico_financeiro(_carregar_json(), admin_id)['obra_id']
        meds = MedicaoContrato.query.filter_by(obra_id=oid, admin_id=admin_id).all()
        assert len(meds) == 6
        assert abs(sum(float(m.pct) for m in meds) - 1.0) < 1e-6
        # valor total das medições ≈ valor de venda
        total = sum(float(m.valor) for m in meds)
        assert abs(total - 1505613.76) < 1.0
        # NÃO cria MedicaoObra (não refatora o sistema existente)
        assert MedicaoObra.query.filter_by(obra_id=oid).count() == 0
        # snapshot verbatim guardado
        snap = Obra.query.get(oid).fluxo_caixa_planilha
        assert snap and snap['lucro_caixa_final'] == 152047
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_importacao_fisico_financeiro.py::test_importa_medicoes_e_snapshot -v`
Expected: FAIL (`len(meds) == 6` → 0).

- [ ] **Step 3: Implementar** (antes do `db.session.commit()` final em `importar_fisico_financeiro`)

```python
    from models import MedicaoContrato

    MedicaoContrato.query.filter_by(obra_id=obra.id, admin_id=admin_id).delete(synchronize_session=False)
    for i, med in enumerate(payload.get('medicoes', [])):
        db.session.add(MedicaoContrato(
            obra_id=obra.id, admin_id=admin_id, nome=med.get('nome'),
            data=_parse_date(med.get('data')),
            pct=Decimal(str(med.get('pct') or 0)),
            recebido_no_mes=med.get('recebido_no_mes'),
            obs=med.get('obs'), ordem=i))

    obra.fluxo_caixa_planilha = payload.get('fluxo_caixa_mensal')
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_importacao_fisico_financeiro.py::test_importa_medicoes_e_snapshot -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/importacao_fisico_financeiro.py tests/test_importacao_fisico_financeiro.py
git commit -m "feat(ff): importador — MedicaoContrato + snapshot fluxo_caixa_planilha"
```

### Task 9: Idempotência + isolamento multitenant

**Files:**
- Test: `tests/test_importacao_fisico_financeiro.py`

- [ ] **Step 1: Escrever os testes que falham (ou já passam pela implementação idempotente)**

```python
@pytest.mark.integration
def test_reimport_nao_duplica():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import TarefaCronograma, MedicaoContrato, Obra
    with app.app_context():
        admin_id = _novo_admin()
        oid1 = importar_fisico_financeiro(_carregar_json(), admin_id)['obra_id']
        oid2 = importar_fisico_financeiro(_carregar_json(), admin_id)['obra_id']
        assert oid1 == oid2  # mesma obra (codigo+admin)
        assert Obra.query.filter_by(admin_id=admin_id).count() == 1
        assert TarefaCronograma.query.filter_by(obra_id=oid1, tarefa_pai_id=None).count() == 12
        assert MedicaoContrato.query.filter_by(obra_id=oid1).count() == 6


@pytest.mark.integration
def test_isolamento_multitenant():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import TarefaCronograma
    with app.app_context():
        a1 = _novo_admin()
        a2 = _novo_admin()
        o1 = importar_fisico_financeiro(_carregar_json(), a1)['obra_id']
        o2 = importar_fisico_financeiro(_carregar_json(), a2)['obra_id']
        assert o1 != o2
        # tarefas de a1 não vazam para a2
        assert TarefaCronograma.query.filter_by(obra_id=o1, admin_id=a2).count() == 0
```

- [ ] **Step 2: Rodar**

Run: `pytest tests/test_importacao_fisico_financeiro.py -k "reimport or multitenant" -v`
Expected: PASS (a implementação da Task 7/8 já apaga coleções derivadas antes de repopular). Se `test_reimport_nao_duplica` falhar por duplicação, revisar os `.delete(...)` da Task 7.

- [ ] **Step 3: Rodar a suíte de importação inteira (regressão)**

Run: `pytest tests/test_importacao_fisico_financeiro.py -v`
Expected: PASS (todos).

- [ ] **Step 4: Commit**

```bash
git add tests/test_importacao_fisico_financeiro.py
git commit -m "test(ff): idempotência do re-import + isolamento multitenant"
```

---

## Fase 4 — Wrappers de serviço + View + Import UI

### Task 10: Wrappers `medicoes_contrato`/`fluxo_caixa`/`fluxo_caixa_divergencia`/`kpis`

**Files:**
- Modify: `services/cronograma_fisico_financeiro.py`
- Test: `tests/test_importacao_fisico_financeiro.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
@pytest.mark.integration
def test_wrappers_de_servico():
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from services.cronograma_fisico_financeiro import (
        medicoes_contrato, fluxo_caixa, fluxo_caixa_divergencia, kpis)
    from models import Obra
    with app.app_context():
        admin_id = _novo_admin()
        oid = importar_fisico_financeiro(_carregar_json(), admin_id)['obra_id']
        obra = Obra.query.get(oid)

        meds = medicoes_contrato(obra)
        assert len(meds) == 6
        assert abs(sum(float(m['valor']) for m in meds) - 1505613.76) < 1.0

        fc = fluxo_caixa(obra)
        assert fc['linhas'] and 'lucro_em_caixa' in fc

        div = fluxo_caixa_divergencia(obra)
        # Δ Veks ≈ 90.000 (734.460 etapas × 824.460 verbatim)
        assert abs(float(div['resumo']['delta_veks']) - 90000) < 2000

        k = kpis(obra)
        assert abs(float(k['venda']) - 1505613.76) < 1.0
        assert k['desembolso_veks'] > 0 and k['fat_direto'] > 0
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_importacao_fisico_financeiro.py::test_wrappers_de_servico -v`
Expected: FAIL com `ImportError`.

- [ ] **Step 3: Implementar os wrappers em `services/cronograma_fisico_financeiro.py`**

```python
def medicoes_contrato(obra) -> list:
    from models import MedicaoContrato
    meds = (MedicaoContrato.query
            .filter_by(obra_id=obra.id, admin_id=obra.admin_id)
            .order_by(MedicaoContrato.ordem).all())
    venda = Decimal(str(obra.valor_contrato or 0))
    out = []
    for m in meds:
        pct = Decimal(str(m.pct or 0))
        out.append({
            "nome": m.nome, "data": m.data, "pct": pct,
            "valor": (venda * pct).quantize(CENTAVO, ROUND_HALF_UP),
            "mes": m.recebido_no_mes, "obs": m.obs,
        })
    return out


def _medicao_por_mes(obra):
    """Soma valor das medições por mês 'YYYY-MM' (pela data)."""
    out = {}
    for m in medicoes_contrato(obra):
        if m["data"]:
            chave = f"{m['data'].year:04d}-{m['data'].month:02d}"
            out[chave] = out.get(chave, Decimal("0")) + m["valor"]
    return out


def fluxo_caixa(obra):
    """Fluxo de caixa recalculado: medições (por mês) + Veks/Fat faseados pelo
    cronograma. imposto_pct vem do snapshot/contrato (default 0.135)."""
    dados = montar_fisico_financeiro(obra.id, obra.admin_id)
    medicao = _medicao_por_mes(obra)
    veks = {k: Decimal(v) for k, v in dados["meses_veks"].items()}
    fat = {k: Decimal(v) for k, v in dados["meses_fat"].items()}
    meses = sorted(set(medicao) | set(veks) | set(fat))
    snap = obra.fluxo_caixa_planilha or {}
    imposto_pct = Decimal(str((snap.get("imposto_pct") if isinstance(snap, dict) else None) or "0.135"))
    res = calcular_fluxo_caixa(meses, medicao, fat, veks, imposto_pct)
    res["meses"] = meses
    return res


def fluxo_caixa_divergencia(obra):
    """Compara Veks faseado (recalc) × GASTO VEKS do snapshot verbatim, mês a mês,
    e resume a inconsistência dos Indiretos (Δ Veks e os dois lucros)."""
    dados = montar_fisico_financeiro(obra.id, obra.admin_id)
    recalc = {k: Decimal(v) for k, v in dados["meses_veks"].items()}
    snap = obra.fluxo_caixa_planilha or {}
    verbatim = {}
    if isinstance(snap, dict) and snap.get("meses") and snap.get("gasto_veks"):
        meses_snap = snap["meses"]
        # mapeia rótulos 'jun','jul'... para 'YYYY-MM' usando a data de início da obra
        verbatim = _veks_verbatim_por_mes(meses_snap, snap["gasto_veks"], obra)
    cmp = comparar_fluxo_caixa(recalc, verbatim)
    veks_etapas = dados["totais"]["veks"]
    veks_verbatim = cmp["total_verbatim"]
    lucro_caixa = Decimal(str((snap.get("lucro_caixa_final") if isinstance(snap, dict) else 0) or 0))
    cmp["resumo"] = {
        "veks_etapas": veks_etapas,
        "veks_verbatim": veks_verbatim,
        "delta_veks": (veks_verbatim - veks_etapas) if veks_verbatim else Decimal("0"),
        "lucro_em_caixa": lucro_caixa,
        "lucro_por_etapas": dados["totais"].get("realizado") or
                            (Decimal(str(obra.valor_contrato or 0)) - dados["totais"]["total"]),
    }
    return cmp


_MESES_PT = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
             "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}


def _veks_verbatim_por_mes(rotulos, valores, obra):
    """Converte rótulos 'jun','jul'... + lista de valores em {'YYYY-MM': Decimal},
    inferindo o ano pela data_inicio da obra (rola para o ano seguinte se o mês
    for menor que o mês inicial)."""
    ano_base = obra.data_inicio.year if obra.data_inicio else date.today().year
    mes_ini = obra.data_inicio.month if obra.data_inicio else 1
    out = {}
    for rotulo, val in zip(rotulos, valores):
        m = _MESES_PT.get(str(rotulo).strip().lower()[:3])
        if not m:
            continue
        ano = ano_base if m >= mes_ini else ano_base + 1
        out[f"{ano:04d}-{m:02d}"] = out.get(f"{ano:04d}-{m:02d}", Decimal("0")) + Decimal(str(val or 0))
    return out


def kpis(obra):
    dados = montar_fisico_financeiro(obra.id, obra.admin_id)
    venda = Decimal(str(obra.valor_contrato or 0))
    custo = dados["totais"]["total"]
    snap = obra.fluxo_caixa_planilha or {}
    imposto_pct = Decimal(str((snap.get("imposto_pct") if isinstance(snap, dict) else None) or "0.135"))
    imposto = (venda * imposto_pct).quantize(CENTAVO, ROUND_HALF_UP)
    lucro = venda - custo - imposto
    recebido = Decimal("0")
    for m in medicoes_contrato(obra):
        if m["data"] and m["data"] <= date.today():
            recebido += m["valor"]
    return {
        "venda": venda, "custo_total": custo,
        "imposto": imposto, "lucro_projetado": lucro,
        "lucro_pct": (lucro / venda) if venda else Decimal("0"),
        "desembolso_veks": dados["totais"]["veks"],
        "fat_direto": dados["totais"]["fat_direto"],
        "recebido_ate_hoje": recebido,
    }
```

> **Nota:** se `obra.fluxo_caixa_planilha` não tiver `imposto_pct`, usa-se 0.135 (parâmetro da Baias). O `lucro_por_etapas` é uma estimativa simples (venda − custo); o objetivo aqui é só **expor a divergência**, não fechar contabilmente.

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_importacao_fisico_financeiro.py::test_wrappers_de_servico -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/cronograma_fisico_financeiro.py tests/test_importacao_fisico_financeiro.py
git commit -m "feat(ff): wrappers medicoes_contrato/fluxo_caixa/divergencia/kpis"
```

### Task 11: View passa as novas séries ao template

**Files:**
- Modify: `cronograma_views.py:2531-2541`

- [ ] **Step 1: Modificar a rota `fisico_financeiro`** (passar os novos blocos)

```python
@cronograma_bp.route('/obra/<int:obra_id>/fisico-financeiro')
@login_required
def fisico_financeiro(obra_id: int):
    guard = _check_v2()
    if guard:
        return guard
    from services.cronograma_fisico_financeiro import (
        montar_fisico_financeiro, medicoes_contrato, fluxo_caixa,
        fluxo_caixa_divergencia, kpis,
    )
    admin_id = _admin_id()
    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()
    dados = montar_fisico_financeiro(obra_id, admin_id)
    return render_template(
        'cronograma/fisico_financeiro.html', obra=obra, dados=dados,
        kpis=kpis(obra), medicoes=medicoes_contrato(obra),
        caixa=fluxo_caixa(obra), divergencia=fluxo_caixa_divergencia(obra),
    )
```

- [ ] **Step 2: Verificação manual rápida** (a página ainda renderiza sem erro mesmo sem os blocos no HTML)

Run: `python -c "import main"` 
Expected: sem exceção (blueprints registram).

- [ ] **Step 3: Commit**

```bash
git add cronograma_views.py
git commit -m "feat(ff): view passa kpis/medicoes/caixa/divergencia ao template"
```

### Task 12: Rota de import do JSON em produção

**Files:**
- Modify: `importacao_views.py`
- Test: `tests/test_importacao_fisico_financeiro.py`

- [ ] **Step 1: Escrever o teste que falha** (chamada direta da função de view via test client exigiria login; aqui testamos a função de serviço já coberta + um smoke da rota GET do formulário)

```python
@pytest.mark.integration
def test_rota_import_json_get_existe():
    with app.test_client() as c:
        resp = c.get('/importacao/fisico-financeiro')
        # redireciona para login (302) — a rota existe (não 404)
        assert resp.status_code in (200, 302)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_importacao_fisico_financeiro.py::test_rota_import_json_get_existe -v`
Expected: FAIL (404 — rota não existe).

- [ ] **Step 3: Adicionar a rota em `importacao_views.py`** (no fim do arquivo, antes de eventuais helpers privados)

```python
@importacao_bp.route('/fisico-financeiro', methods=['GET', 'POST'])
@login_required
def importar_fisico_financeiro_view():
    import json as _json
    from flask import request, redirect, url_for, flash
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    admin_id = current_user.admin_id if getattr(current_user, 'admin_id', None) else current_user.id

    if request.method == 'POST':
        arquivo = request.files.get('arquivo')
        if not arquivo:
            flash('Selecione um arquivo JSON.', 'warning')
            return redirect(url_for('importacao.importar_fisico_financeiro_view'))
        try:
            payload = _json.load(arquivo.stream)
            res = importar_fisico_financeiro(payload, admin_id)
        except Exception as e:
            flash(f'Falha ao importar: {e}', 'danger')
            return redirect(url_for('importacao.importar_fisico_financeiro_view'))
        flash('Obra importada — painel físico-financeiro pronto.', 'success')
        return redirect(url_for('cronograma.fisico_financeiro', obra_id=res['obra_id']))

    return render_template('importacao/fisico_financeiro_upload.html')
```

> **Nota:** confirme em `importacao_views.py` o nome do blueprint (`importacao_bp`), o import de `login_required`/`current_user` e o padrão de `admin_id` usado nas outras rotas; ajuste para casar.

- [ ] **Step 4: Criar o template mínimo** `templates/importacao/fisico_financeiro_upload.html`

```html
{% extends "base_completo.html" %}
{% block content %}
<div class="container py-4">
  <h3>Importar Cronograma Físico-Financeiro (JSON)</h3>
  <p class="text-muted">Importa cronograma, custos, vínculos, medições de contrato
     e o fluxo de caixa de uma vez. A obra abre pronta no painel.</p>
  <form method="post" enctype="multipart/form-data">
    <input type="file" name="arquivo" accept="application/json,.json" class="form-control mb-3" required>
    <button class="btn btn-primary" type="submit">Importar</button>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 5: Rodar e ver passar**

Run: `pytest tests/test_importacao_fisico_financeiro.py::test_rota_import_json_get_existe -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add importacao_views.py templates/importacao/fisico_financeiro_upload.html tests/test_importacao_fisico_financeiro.py
git commit -m "feat(ff): rota de import do JSON em produção (upload → painel)"
```

---

## Fase 5 — Template do painel

### Task 13: Seções KPIs + medições + fluxo de caixa + alerta Indiretos

**Files:**
- Modify: `templates/cronograma/fisico_financeiro.html`

- [ ] **Step 1: Adicionar as seções ao template** (após o cabeçalho/KPIs existentes; usar os contextos `kpis`, `medicoes`, `caixa`, `divergencia`)

```html
{# --- KPIs --- #}
<div class="row g-3 mb-4">
  {% set k = kpis %}
  {% for rotulo, valor in [
      ('Venda', k.venda), ('Custo total', k.custo_total),
      ('Lucro projetado', k.lucro_projetado), ('Desembolso Veks', k.desembolso_veks),
      ('Faturamento direto', k.fat_direto), ('Recebido até hoje', k.recebido_ate_hoje)] %}
  <div class="col-6 col-md-2">
    <div class="card h-100"><div class="card-body p-2">
      <div class="small text-muted">{{ rotulo }}</div>
      <div class="fw-bold" style="font-variant-numeric:tabular-nums">
        R$ {{ '%.2f'|format(valor|float) }}</div>
    </div></div>
  </div>
  {% endfor %}
</div>

{# --- Alerta da inconsistência dos Indiretos --- #}
{% if divergencia and divergencia.resumo.delta_veks and divergencia.resumo.delta_veks|float|abs > 1 %}
<div class="alert alert-warning">
  <strong>Inconsistência dos Indiretos:</strong>
  Veks pelas etapas = R$ {{ '%.0f'|format(divergencia.resumo.veks_etapas|float) }};
  GASTO VEKS da planilha = R$ {{ '%.0f'|format(divergencia.resumo.veks_verbatim|float) }}
  (Δ R$ {{ '%.0f'|format(divergencia.resumo.delta_veks|float) }}).
  Lucro em caixa (planilha) = R$ {{ '%.0f'|format(divergencia.resumo.lucro_em_caixa|float) }}.
  Decida se os Indiretos rodam ~3,5 ou ~5 meses — o app não escolhe sozinho.
</div>
{% endif %}

{# --- Medições de contrato --- #}
<h5 class="mt-4">Medições de contrato</h5>
<table class="table table-sm">
  <thead><tr><th>Medição</th><th>Data</th><th>%</th><th class="text-end">Valor (R$)</th><th>Mês</th></tr></thead>
  <tbody>
  {% for m in medicoes %}
    <tr><td>{{ m.nome }}</td><td>{{ m.data and m.data.strftime('%d/%m/%Y') or '—' }}</td>
        <td>{{ '%.1f'|format((m.pct|float)*100) }}%</td>
        <td class="text-end">{{ '%.2f'|format(m.valor|float) }}</td>
        <td>{{ m.mes or '—' }}</td></tr>
  {% endfor %}
  </tbody>
</table>

{# --- Fluxo de caixa (recalculado) com divergência de Veks --- #}
<h5 class="mt-4">Fluxo de caixa mensal (recalculado)</h5>
<table class="table table-sm">
  <thead><tr><th>Mês</th><th class="text-end">Medição</th><th class="text-end">Imposto</th>
    <th class="text-end">Entrada líq.</th><th class="text-end">Caixa inicial</th>
    <th class="text-end">Gasto Veks</th><th class="text-end">Caixa final</th>
    <th class="text-end">Δ Veks vs planilha</th></tr></thead>
  <tbody>
  {% for l in caixa.linhas %}
    <tr><td>{{ l.mes }}</td>
        <td class="text-end">{{ '%.0f'|format(l.medicao|float) }}</td>
        <td class="text-end">{{ '%.0f'|format(l.imposto|float) }}</td>
        <td class="text-end">{{ '%.0f'|format(l.entrada|float) }}</td>
        <td class="text-end">{{ '%.0f'|format(l.caixa_inicial|float) }}</td>
        <td class="text-end">{{ '%.0f'|format(l.gasto_veks|float) }}</td>
        <td class="text-end">{{ '%.0f'|format(l.caixa_final|float) }}</td>
        <td class="text-end">
          {% set d = divergencia.por_mes.get(l.mes) %}
          {{ d and '%.0f'|format(d.delta|float) or '—' }}</td></tr>
  {% endfor %}
  </tbody>
  <tfoot><tr><th colspan="6" class="text-end">Lucro em caixa (recalc):</th>
    <th class="text-end">{{ '%.0f'|format(caixa.lucro_em_caixa|float) }}</th><th></th></tr></tfoot>
</table>
```

- [ ] **Step 2: Verificação manual** (renderização não quebra)

Run: `python -c "import main"`
Expected: sem exceção.

- [ ] **Step 3: Commit**

```bash
git add templates/cronograma/fisico_financeiro.html
git commit -m "feat(ff): painel — KPIs, medições, fluxo de caixa e alerta Indiretos"
```

---

## Fase 6 — Smoke de ponta a ponta

### Task 14: Smoke da página físico-financeiro

**Files:**
- Create: `tests/test_fisico_financeiro_painel_playwright.py`

- [ ] **Step 1: Escrever o smoke** (segue o padrão de `test_browser_all_modules.py`; usa as fixtures `sige_base_url`/`browser_launch_options` do conftest e um login helper se houver)

```python
import pytest

pytestmark = pytest.mark.browser


@pytest.mark.browser
def test_painel_ff_carrega(sige_base_url, browser_launch_options):
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(**browser_launch_options)
        page = browser.new_page()
        # Pré-condição: servidor em PW_BASE_URL com sessão/obra de teste.
        # Smoke mínimo: a rota responde (status != 5xx) ou redireciona ao login.
        resp = page.goto(f"{sige_base_url}/cronograma/obra/1/fisico-financeiro",
                         wait_until="domcontentloaded")
        assert resp is not None and resp.status < 500
        browser.close()
```

- [ ] **Step 2: Rodar** (pula se não houver servidor/Playwright)

Run: `pytest tests/test_fisico_financeiro_painel_playwright.py -v`
Expected: PASS ou SKIP (sem servidor/browser).

- [ ] **Step 3: Rodar a suíte físico-financeiro inteira (regressão final)**

Run: `pytest tests/test_cronograma_fisico_financeiro.py tests/test_importacao_fisico_financeiro.py -v`
Expected: PASS (todos).

- [ ] **Step 4: Commit**

```bash
git add tests/test_fisico_financeiro_painel_playwright.py
git commit -m "test(ff): smoke da página físico-financeiro"
```

---

## Checklist de cobertura do spec

- [x] Importação completa numa ação (obra pronta) → Tasks 6–8, 12
- [x] `MedicaoContrato` (entidade fixa, sem refatorar `MedicaoObra`) → Tasks 1, 8 (+ assert `MedicaoObra==0`)
- [x] Snapshot verbatim do fluxo de caixa → Tasks 2, 8
- [x] Vinculação atividade↔custo por etapa (raiz+folhas, IMC, IMCT, OSC) → Task 7
- [x] Fluxo de caixa recalculado (regra fat/imposto do período anterior) → Tasks 3, 10
- [x] Divergência recalc × verbatim + inconsistência Indiretos (só alerta) → Tasks 4, 10, 13
- [x] KPIs → Tasks 10, 13
- [x] Idempotência + multitenant → Task 9
- [x] EVM / Curva física / Gantt → **fora de escopo** (YAGNI), conforme spec

## Notas de execução

- **Confirmar nomes de campo** de `ObraServicoCusto` (`models.py:5563+`) antes da Task 7 (campos NOT NULL no construtor) e o padrão de blueprint/`admin_id`/`login_required` em `importacao_views.py` antes da Task 12.
- **Migrações** rodam no boot via `executar_migracoes()`. Se a suíte de teste não subir o app com migração, chamar `executar_migracoes()` num `app_context` no setup (módulo de teste).
- **Decimais**: dinheiro sempre `Decimal`; `float()` só na apresentação (templates) e nas tolerâncias de teste.
```
