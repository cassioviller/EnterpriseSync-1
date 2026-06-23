# Cronograma Físico-Financeiro (derivado) — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar ao cronograma do SIGE uma visão físico-financeira (custo previsto por etapa, faseado no tempo com Curva S, split Veks×Fat Direto, realizado×previsto) derivada do que já existe, com export XLSX.

**Architecture:** Funções **puras** num serviço novo (`services/cronograma_fisico_financeiro.py`) fazem alocação custo→tarefa (por peso do IMC), faseamento por dias úteis e Curva S — testáveis sem banco/servidor. Um orquestrador junta isso com queries; uma rota renderiza a página e outra exporta XLSX. Única gravação nova: 3 colunas Veks/Fat em `ObraServicoCusto`.

**Tech Stack:** Python 3.11, Flask (`cronograma_bp`), SQLAlchemy, openpyxl, pytest. Migração no padrão numerado de `migrations.py`.

---

## Convenções de verificação

- **GATE de boot** (após mudanças que tocam app/models/views):
  ```bash
  python -c "import main; print('BLUEPRINTS', len(main.app.blueprints))"
  ```
  Esperado: termina com `BLUEPRINTS 54`, exit 0.
  > Use `main` (não `app`): o app servido pelo gunicorn é `main:app`, que registra
  > os blueprints extras de `main.py` além dos 37 de `app.py`. Validar via `import app`
  > deixa de fora rotas reais e pode falhar ao renderizar templates que referenciam
  > esses endpoints (ex.: `custos_escritorio.painel_mensal` em `base_completo.html`).
- **Testes puros** (sem servidor):
  ```bash
  .pythonlibs/bin/python -m pytest tests/test_cronograma_fisico_financeiro.py -q
  ```
- Decimais com `decimal.Decimal`; arredondar só na apresentação/comparação (centavos).

Referências do código existente (verificadas em 2026-06-23):
- `ObraServicoCusto` — `models.py:5563` (campos `valor_orcado`, `realizado_material/mao_obra/outros`, `material/mao_obra/outros_a_realizar`, FK `item_medicao_comercial_id`).
- `ItemMedicaoCronogramaTarefa` — `models.py:5217` (`item_medicao_id`, `cronograma_tarefa_id`, `peso`, `.tarefa`).
- `TarefaCronograma` — `models.py:4835` (`obra_id`, `tarefa_pai_id`, `servico_id`, `data_inicio`, `data_fim`, `nome_tarefa`).
- Helpers de calendário — `utils/cronograma_engine.py`: `get_calendario(admin_id)`, `_is_dia_util(d, sab, dom)`, `dias_uteis_entre(inicio, fim, sab, dom)`.
- Blueprint — `cronograma_views.py:31` `cronograma_bp` (`url_prefix='/cronograma'`); helper `_admin_id()` em `:47`.
- Padrão de migração — `migrations.py`: função `_migration_NNN_*` + registro na lista `migrations_to_run` (~linha 3830). Maior número atual = 192 → **usar 193**.

---

## Estrutura de arquivos

- **Modify** `models.py` — 3 colunas novas em `ObraServicoCusto`.
- **Modify** `migrations.py` — `_migration_193_*` + registro.
- **Create** `services/cronograma_fisico_financeiro.py` — funções puras + orquestrador + export XLSX.
- **Create** `tests/test_cronograma_fisico_financeiro.py` — testes das funções puras e do XLSX.
- **Modify** `cronograma_views.py` — 2 rotas (página + export).
- **Create** `templates/cronograma/fisico_financeiro.html` — a tabela + Curva S.
- **Modify** `templates/cronograma/obra.html` (ou equivalente) — link para a nova página.
- **Modify** `tests/test_browser_all_modules.py` — smoke da nova página (ou arquivo próprio).

---

## Task 1: Coluna Veks/Fat em ObraServicoCusto (modelo + migração 193)

**Files:**
- Modify: `models.py:5616` (após `outros_a_realizar`, dentro de `ObraServicoCusto`)
- Modify: `migrations.py` (nova função + registro na lista)

- [ ] **Step 1: Adicionar as 3 colunas no modelo**

Em `models.py`, dentro da classe `ObraServicoCusto`, logo após a linha
`outros_a_realizar = db.Column(db.Numeric(15, 2), default=0, nullable=False)`:

```python
    # Físico-financeiro: quem paga cada categoria — 'veks' (empresa) ou 'fat_direto'
    # (cliente paga o fornecedor direto). Default 'veks'.
    fonte_material = db.Column(db.String(20), default='veks', nullable=False)
    fonte_mao_obra = db.Column(db.String(20), default='veks', nullable=False)
    fonte_outros = db.Column(db.String(20), default='veks', nullable=False)
```

- [ ] **Step 2: Escrever a migração 193**

Em `migrations.py`, junto às demais `_migration_*` (ex.: após `_migration_189_*`):

```python
def _migration_193_obra_servico_custo_fonte_pagamento():
    """Físico-financeiro — adiciona fonte_material/fonte_mao_obra/fonte_outros
    em obra_servico_custo (Veks x Faturamento Direto). Idempotente."""
    from sqlalchemy import text as sa_text
    try:
        with db.engine.begin() as conn:
            for col in ('fonte_material', 'fonte_mao_obra', 'fonte_outros'):
                conn.execute(sa_text(f"""
                    ALTER TABLE obra_servico_custo
                      ADD COLUMN IF NOT EXISTS {col} VARCHAR(20) NOT NULL DEFAULT 'veks'
                """))
        logger.info("[Migration 193] fonte_material/mao_obra/outros adicionadas em obra_servico_custo.")
    except Exception as e:
        logger.error(f"[Migration 193] Falha: {e}", exc_info=True)
        raise
```

- [ ] **Step 3: Registrar a migração na lista `migrations_to_run`**

Em `migrations.py` (~linha 3830), adicionar a entrada (mantendo a ordem numérica, ao
final da lista):

```python
            (193, "fonte pagamento Veks/Fat em obra_servico_custo", _migration_193_obra_servico_custo_fonte_pagamento),
```

- [ ] **Step 4: GATE de boot (a migração roda no boot)**

Run:
```bash
python -c "import main; print('BLUEPRINTS', len(main.app.blueprints))"
```
Expected: `BLUEPRINTS 54`. Nos logs deve aparecer `[Migration 193]` (aplicada ou skip).

- [ ] **Step 5: Verificar a coluna no banco**

Run:
```bash
python -c "
import app
from models import db
from sqlalchemy import text
with app.app.app_context():
    rows = db.session.execute(text(\"SELECT column_name FROM information_schema.columns WHERE table_name='obra_servico_custo' AND column_name LIKE 'fonte_%'\")).fetchall()
    print(sorted(r[0] for r in rows))
"
```
Expected: `['fonte_mao_obra', 'fonte_material', 'fonte_outros']`

- [ ] **Step 6: Commit**

```bash
git add models.py migrations.py
git commit -m "feat(custo): coluna Veks/Fat Direto em ObraServicoCusto (migração 193)"
```

---

## Task 2: Função pura `fasear_por_dias_uteis`

**Files:**
- Create: `services/cronograma_fisico_financeiro.py`
- Test: `tests/test_cronograma_fisico_financeiro.py`

- [ ] **Step 1: Escrever os testes que falham**

Create `tests/test_cronograma_fisico_financeiro.py`:
```python
from datetime import date
from decimal import Decimal

from services.cronograma_fisico_financeiro import fasear_por_dias_uteis

D = Decimal


def test_sem_datas_vai_para_nao_faseado():
    out = fasear_por_dias_uteis(D("1000"), None, None, False, False)
    assert out == {"__nao_faseado__": D("1000")}


def test_tarefa_dentro_de_um_mes():
    # seg-sex de uma única semana de junho/2026 → tudo em 2026-06
    out = fasear_por_dias_uteis(D("1000"), date(2026, 6, 1), date(2026, 6, 5), False, False)
    assert set(out) == {"2026-06"}
    assert out["2026-06"] == D("1000")


def test_tarefa_cruza_dois_meses_divide_por_dias_uteis():
    # 29/06 (seg) a 03/07 (sex): 2 dias úteis em junho (29,30) + 3 em julho (1,2,3)
    out = fasear_por_dias_uteis(D("1000"), date(2026, 6, 29), date(2026, 7, 3), False, False)
    assert set(out) == {"2026-06", "2026-07"}
    # conservação do total
    assert out["2026-06"] + out["2026-07"] == D("1000")
    # proporção 2/5 e 3/5
    assert out["2026-06"] == D("400.00")
    assert out["2026-07"] == D("600.00")


def test_valor_zero_retorna_vazio():
    assert fasear_por_dias_uteis(D("0"), date(2026, 6, 1), date(2026, 6, 5), False, False) == {}
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.pythonlibs/bin/python -m pytest tests/test_cronograma_fisico_financeiro.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'services.cronograma_fisico_financeiro'`.

- [ ] **Step 3: Implementar a função**

Create `services/cronograma_fisico_financeiro.py`:
```python
"""Cronograma físico-financeiro (derivado).

Funções puras (sem banco) para alocação de custo às tarefas, faseamento por dias
úteis e Curva S; mais um orquestrador que monta a visão por etapa a partir de
ObraServicoCusto + pesos do IMC + datas das tarefas.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

CENTAVO = Decimal("0.01")
NAO_FASEADO = "__nao_faseado__"


def _is_dia_util(d: date, considerar_sabado: bool, considerar_domingo: bool) -> bool:
    wd = d.weekday()  # 0=seg ... 5=sab 6=dom
    if wd == 5 and not considerar_sabado:
        return False
    if wd == 6 and not considerar_domingo:
        return False
    return True


def fasear_por_dias_uteis(valor: Decimal, data_inicio, data_fim,
                          considerar_sabado: bool, considerar_domingo: bool) -> dict:
    """Distribui `valor` pelos dias úteis entre data_inicio e data_fim (inclusive),
    agregando por mês 'YYYY-MM'. Sem datas → bucket NAO_FASEADO. valor 0 → {}.
    Conserva o total (o último mês absorve o resto do arredondamento)."""
    if valor is None or valor == 0:
        return {}
    valor = Decimal(valor)
    if not data_inicio or not data_fim:
        return {NAO_FASEADO: valor}

    dias_por_mes: dict[str, int] = {}
    d = data_inicio
    total_dias = 0
    while d <= data_fim:
        if _is_dia_util(d, considerar_sabado, considerar_domingo):
            chave = f"{d.year:04d}-{d.month:02d}"
            dias_por_mes[chave] = dias_por_mes.get(chave, 0) + 1
            total_dias += 1
        d += timedelta(days=1)

    if total_dias == 0:
        return {NAO_FASEADO: valor}

    meses = sorted(dias_por_mes)
    out: dict[str, Decimal] = {}
    acumulado = Decimal("0")
    for i, mes in enumerate(meses):
        if i < len(meses) - 1:
            parcela = (valor * dias_por_mes[mes] / total_dias).quantize(CENTAVO, ROUND_HALF_UP)
            out[mes] = parcela
            acumulado += parcela
        else:
            out[mes] = (valor - acumulado).quantize(CENTAVO, ROUND_HALF_UP)
    return out
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.pythonlibs/bin/python -m pytest tests/test_cronograma_fisico_financeiro.py -q`
Expected: PASS (4 testes).

- [ ] **Step 5: Commit**

```bash
git add services/cronograma_fisico_financeiro.py tests/test_cronograma_fisico_financeiro.py
git commit -m "feat(ff): faseamento de custo por dias úteis (função pura)"
```

---

## Task 3: Função pura `alocar_por_peso`

**Files:**
- Modify: `services/cronograma_fisico_financeiro.py`
- Test: `tests/test_cronograma_fisico_financeiro.py`

- [ ] **Step 1: Adicionar testes que falham**

Acrescentar em `tests/test_cronograma_fisico_financeiro.py`:
```python
from services.cronograma_fisico_financeiro import alocar_por_peso


def test_aloca_proporcional_ao_peso_e_conserva_total():
    out = alocar_por_peso(D("1000"), [("a", D("30")), ("b", D("70"))])
    assert out == {"a": D("300.00"), "b": D("700.00")}
    assert sum(out.values()) == D("1000")


def test_peso_zero_distribui_igualmente():
    out = alocar_por_peso(D("900"), [("a", D("0")), ("b", D("0")), ("c", D("0"))])
    assert sum(out.values()) == D("900")
    assert out["a"] == D("300.00") and out["c"] == D("300.00")


def test_sem_tarefas_retorna_vazio():
    assert alocar_por_peso(D("100"), []) == {}
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.pythonlibs/bin/python -m pytest tests/test_cronograma_fisico_financeiro.py -q`
Expected: FAIL com `ImportError: cannot import name 'alocar_por_peso'`.

- [ ] **Step 3: Implementar**

Acrescentar em `services/cronograma_fisico_financeiro.py`:
```python
def alocar_por_peso(valor: Decimal, pesos: list) -> dict:
    """Distribui `valor` entre chaves proporcional ao peso. `pesos` é lista de
    (chave, peso). Se Σpeso == 0, distribui igualmente. Conserva o total
    (última chave absorve o resto)."""
    if not pesos:
        return {}
    valor = Decimal(valor)
    soma = sum((Decimal(p) for _, p in pesos), Decimal("0"))
    n = len(pesos)
    out: dict = {}
    acumulado = Decimal("0")
    for i, (chave, peso) in enumerate(pesos):
        if i < n - 1:
            if soma > 0:
                parcela = (valor * Decimal(peso) / soma).quantize(CENTAVO, ROUND_HALF_UP)
            else:
                parcela = (valor / n).quantize(CENTAVO, ROUND_HALF_UP)
            out[chave] = parcela
            acumulado += parcela
        else:
            out[chave] = (valor - acumulado).quantize(CENTAVO, ROUND_HALF_UP)
    return out
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.pythonlibs/bin/python -m pytest tests/test_cronograma_fisico_financeiro.py -q`
Expected: PASS (7 testes no total).

- [ ] **Step 5: Commit**

```bash
git add services/cronograma_fisico_financeiro.py tests/test_cronograma_fisico_financeiro.py
git commit -m "feat(ff): alocação de custo por peso (função pura)"
```

---

## Task 4: Função pura `montar_curva_s`

**Files:**
- Modify: `services/cronograma_fisico_financeiro.py`
- Test: `tests/test_cronograma_fisico_financeiro.py`

- [ ] **Step 1: Adicionar testes que falham**

Acrescentar em `tests/test_cronograma_fisico_financeiro.py`:
```python
from services.cronograma_fisico_financeiro import montar_curva_s


def test_curva_s_acumula_e_fecha_em_um():
    curva = montar_curva_s({"2026-07": D("600"), "2026-06": D("400")})
    assert [c["mes"] for c in curva] == ["2026-06", "2026-07"]  # ordenado
    assert curva[0]["acumulado"] == D("400")
    assert curva[1]["acumulado"] == D("1000")
    assert curva[1]["pct_acumulado"] == D("1")
    assert curva[0]["pct_acumulado"] == D("0.4")


def test_curva_s_vazia():
    assert montar_curva_s({}) == []
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.pythonlibs/bin/python -m pytest tests/test_cronograma_fisico_financeiro.py -q`
Expected: FAIL com `ImportError: cannot import name 'montar_curva_s'`.

- [ ] **Step 3: Implementar**

Acrescentar em `services/cronograma_fisico_financeiro.py`:
```python
def montar_curva_s(meses_valores: dict) -> list:
    """Recebe {'YYYY-MM': Decimal}; retorna lista ordenada por mês com
    custo do mês, acumulado e pct_acumulado (sobre o total). Ignora o bucket
    NAO_FASEADO."""
    meses = {k: Decimal(v) for k, v in meses_valores.items() if k != NAO_FASEADO}
    if not meses:
        return []
    total = sum(meses.values(), Decimal("0"))
    curva = []
    acumulado = Decimal("0")
    for mes in sorted(meses):
        acumulado += meses[mes]
        pct = (acumulado / total) if total > 0 else Decimal("0")
        curva.append({
            "mes": mes,
            "custo_mes": meses[mes],
            "acumulado": acumulado,
            "pct_acumulado": pct,
        })
    return curva
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.pythonlibs/bin/python -m pytest tests/test_cronograma_fisico_financeiro.py -q`
Expected: PASS (9 testes no total).

- [ ] **Step 5: Commit**

```bash
git add services/cronograma_fisico_financeiro.py tests/test_cronograma_fisico_financeiro.py
git commit -m "feat(ff): Curva S de custo (função pura)"
```

---

## Task 5: Função pura `classificar_veks_fat`

**Files:**
- Modify: `services/cronograma_fisico_financeiro.py`
- Test: `tests/test_cronograma_fisico_financeiro.py`

- [ ] **Step 1: Adicionar testes que falham**

Acrescentar em `tests/test_cronograma_fisico_financeiro.py`:
```python
from services.cronograma_fisico_financeiro import classificar_veks_fat


def test_material_fat_mao_obra_veks():
    veks, fat = classificar_veks_fat(
        material=D("100"), mao_obra=D("50"), outros=D("10"),
        fonte_material="fat_direto", fonte_mao_obra="veks", fonte_outros="veks",
    )
    assert fat == D("100")
    assert veks == D("60")
    assert veks + fat == D("160")


def test_tudo_veks_por_default():
    veks, fat = classificar_veks_fat(
        material=D("100"), mao_obra=D("50"), outros=D("10"),
        fonte_material="veks", fonte_mao_obra="veks", fonte_outros="veks",
    )
    assert veks == D("160") and fat == D("0")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.pythonlibs/bin/python -m pytest tests/test_cronograma_fisico_financeiro.py -q`
Expected: FAIL com `ImportError: cannot import name 'classificar_veks_fat'`.

- [ ] **Step 3: Implementar**

Acrescentar em `services/cronograma_fisico_financeiro.py`:
```python
def classificar_veks_fat(material, mao_obra, outros,
                         fonte_material, fonte_mao_obra, fonte_outros):
    """Soma as categorias em (veks, fat_direto) conforme cada fonte. Qualquer
    valor de fonte != 'fat_direto' é tratado como 'veks'."""
    veks = Decimal("0")
    fat = Decimal("0")
    for valor, fonte in (
        (material, fonte_material),
        (mao_obra, fonte_mao_obra),
        (outros, fonte_outros),
    ):
        v = Decimal(valor or 0)
        if fonte == "fat_direto":
            fat += v
        else:
            veks += v
    return veks, fat
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.pythonlibs/bin/python -m pytest tests/test_cronograma_fisico_financeiro.py -q`
Expected: PASS (11 testes no total).

- [ ] **Step 5: Commit**

```bash
git add services/cronograma_fisico_financeiro.py tests/test_cronograma_fisico_financeiro.py
git commit -m "feat(ff): classificação Veks/Fat Direto (função pura)"
```

---

## Task 6: Orquestrador `montar_fisico_financeiro` (com banco)

**Files:**
- Modify: `services/cronograma_fisico_financeiro.py`

- [ ] **Step 1: Implementar o orquestrador**

Acrescentar em `services/cronograma_fisico_financeiro.py`:
```python
def _previsto_por_categoria(osc):
    """Previsto = realizado + a_realizar, por categoria (Decimal)."""
    material = Decimal(osc.realizado_material or 0) + Decimal(osc.material_a_realizar or 0)
    mao_obra = Decimal(osc.realizado_mao_obra or 0) + Decimal(osc.mao_obra_a_realizar or 0)
    outros = Decimal(osc.realizado_outros or 0) + Decimal(osc.outros_a_realizar or 0)
    return material, mao_obra, outros


def _raiz_da_tarefa(tarefa, por_id):
    """Sobe a hierarquia até o nó raiz (etapa). `por_id` mapeia id->tarefa."""
    atual = tarefa
    visitados = set()
    while atual.tarefa_pai_id and atual.tarefa_pai_id in por_id and atual.id not in visitados:
        visitados.add(atual.id)
        atual = por_id[atual.tarefa_pai_id]
    return atual


def montar_fisico_financeiro(obra_id: int, admin_id: int) -> dict:
    """Monta a visão físico-financeira por etapa (nó raiz do cronograma) a partir
    de ObraServicoCusto (custo) + pesos do IMC (alocação por tarefa) + datas das
    tarefas (faseamento). Tudo derivado; ver design 2026-06-23."""
    from models import (
        ObraServicoCusto, TarefaCronograma, ItemMedicaoCronogramaTarefa,
    )
    from utils.cronograma_engine import get_calendario

    cal = get_calendario(admin_id)
    sab, dom = cal.considerar_sabado, cal.considerar_domingo

    tarefas = TarefaCronograma.query.filter_by(obra_id=obra_id, admin_id=admin_id).all()
    por_id = {t.id: t for t in tarefas}

    custos = ObraServicoCusto.query.filter_by(obra_id=obra_id, admin_id=admin_id).all()

    etapas: dict = {}      # raiz_id -> agregado
    meses_globais: dict = {}
    nao_faseado = Decimal("0")
    avisos: list = []

    def _etapa(raiz):
        if raiz.id not in etapas:
            etapas[raiz.id] = {
                "etapa_id": raiz.id,
                "nome": raiz.nome_tarefa,
                "categoria": getattr(getattr(raiz, "servico", None), "categoria", None),
                "previsto": {"material": Decimal("0"), "mao_obra": Decimal("0"),
                             "outros": Decimal("0"), "total": Decimal("0")},
                "veks": Decimal("0"), "fat_direto": Decimal("0"),
                "orcado": Decimal("0"), "realizado": Decimal("0"),
                "meses": {},
            }
        return etapas[raiz.id]

    for osc in custos:
        material, mao_obra, outros = _previsto_por_categoria(osc)
        previsto_total = material + mao_obra + outros
        veks, fat = classificar_veks_fat(
            material, mao_obra, outros,
            osc.fonte_material, osc.fonte_mao_obra, osc.fonte_outros,
        )

        # pesos das tarefas-folha ligadas a este custo (via IMC)
        vinculos = []
        if osc.item_medicao_comercial_id:
            vinculos = ItemMedicaoCronogramaTarefa.query.filter_by(
                item_medicao_id=osc.item_medicao_comercial_id, admin_id=admin_id,
            ).all()
        pesos = [(v.cronograma_tarefa_id, Decimal(v.peso or 0))
                 for v in vinculos if v.cronograma_tarefa_id in por_id]

        if not pesos:
            # sem cronograma vinculado: custo não fasea; cai numa etapa sintética
            avisos.append(f"Serviço '{osc.nome}' sem tarefas vinculadas — custo não faseado.")
            nao_faseado += previsto_total
            raiz_sintetica = type("R", (), {"id": f"osc-{osc.id}", "nome_tarefa": osc.nome,
                                            "servico": None, "tarefa_pai_id": None})
            et = _etapa(raiz_sintetica)
        else:
            # alocar previsto entre as folhas e agregá-lo nas etapas-raiz das folhas
            aloc = alocar_por_peso(previsto_total, pesos)
            # a etapa de cada folha é a raiz da árvore daquela folha
            for tarefa_id, valor_tarefa in aloc.items():
                folha = por_id[tarefa_id]
                raiz = _raiz_da_tarefa(folha, por_id)
                et = _etapa(raiz)
                fases = fasear_por_dias_uteis(
                    valor_tarefa, folha.data_inicio, folha.data_fim, sab, dom)
                for mes, parcela in fases.items():
                    if mes == NAO_FASEADO:
                        nao_faseado += parcela
                        continue
                    et["meses"][mes] = et["meses"].get(mes, Decimal("0")) + parcela
                    meses_globais[mes] = meses_globais.get(mes, Decimal("0")) + parcela
            et = None  # já agregamos por folha acima

        # agregados de valor da etapa: somar no(s) etapa(s) — para custo com pesos,
        # somamos proporcional já distribuído; para o resumo por etapa usamos o
        # custo inteiro do serviço na etapa da 1ª folha (ou sintética).
        etapa_resumo = (
            _etapa(_raiz_da_tarefa(por_id[pesos[0][0]], por_id)) if pesos else et
        )
        etapa_resumo["previsto"]["material"] += material
        etapa_resumo["previsto"]["mao_obra"] += mao_obra
        etapa_resumo["previsto"]["outros"] += outros
        etapa_resumo["previsto"]["total"] += previsto_total
        etapa_resumo["veks"] += veks
        etapa_resumo["fat_direto"] += fat
        etapa_resumo["orcado"] += Decimal(osc.valor_orcado or 0)
        etapa_resumo["realizado"] += Decimal(osc.realizado_total or 0)

    for et in etapas.values():
        et["desvio"] = et["realizado"] - et["previsto"]["total"]

    meses_ordenados = sorted(meses_globais)
    totais = {
        "veks": sum((e["veks"] for e in etapas.values()), Decimal("0")),
        "fat_direto": sum((e["fat_direto"] for e in etapas.values()), Decimal("0")),
        "previsto": sum((e["previsto"]["total"] for e in etapas.values()), Decimal("0")),
        "orcado": sum((e["orcado"] for e in etapas.values()), Decimal("0")),
        "realizado": sum((e["realizado"] for e in etapas.values()), Decimal("0")),
    }
    totais["total"] = totais["veks"] + totais["fat_direto"]

    return {
        "etapas": sorted(etapas.values(), key=lambda e: str(e["nome"] or "")),
        "meses_ordenados": meses_ordenados,
        "totais": totais,
        "curva_s": montar_curva_s(meses_globais),
        "nao_faseado": nao_faseado,
        "avisos": avisos,
    }
```

- [ ] **Step 2: GATE de import (a função importa sem erro)**

Run:
```bash
python -c "import app; from services.cronograma_fisico_financeiro import montar_fisico_financeiro; print('IMPORT_OK')"
```
Expected: termina com `IMPORT_OK` (e `BLUEPRINTS` não é checado aqui, mas o import de app não pode quebrar).

- [ ] **Step 3: Commit**

```bash
git add services/cronograma_fisico_financeiro.py
git commit -m "feat(ff): orquestrador montar_fisico_financeiro (custo->etapa, faseado)"
```

---

## Task 7: Export XLSX

**Files:**
- Modify: `services/cronograma_fisico_financeiro.py`
- Test: `tests/test_cronograma_fisico_financeiro.py`

- [ ] **Step 1: Adicionar teste que falha**

Acrescentar em `tests/test_cronograma_fisico_financeiro.py`:
```python
from services.cronograma_fisico_financeiro import exportar_fisico_financeiro_xlsx


def test_xlsx_tem_abas_e_cabecalho():
    dados = {
        "etapas": [{
            "etapa_id": 1, "nome": "Fundação", "categoria": "Fundação",
            "previsto": {"material": D("20000"), "mao_obra": D("49000"),
                         "outros": D("9300"), "total": D("78300")},
            "veks": D("58300"), "fat_direto": D("20000"),
            "orcado": D("78300"), "realizado": D("0"), "desvio": D("-78300"),
            "meses": {"2026-06": D("70000"), "2026-07": D("8300")},
        }],
        "meses_ordenados": ["2026-06", "2026-07"],
        "totais": {"veks": D("58300"), "fat_direto": D("20000"), "total": D("78300"),
                   "previsto": D("78300"), "orcado": D("78300"), "realizado": D("0")},
        "curva_s": [
            {"mes": "2026-06", "custo_mes": D("70000"), "acumulado": D("70000"), "pct_acumulado": D("0.894")},
            {"mes": "2026-07", "custo_mes": D("8300"), "acumulado": D("78300"), "pct_acumulado": D("1")},
        ],
        "nao_faseado": D("0"), "avisos": [],
    }
    wb = exportar_fisico_financeiro_xlsx(dados)
    assert {ws.title for ws in wb.worksheets} == {"Cronograma FF (por etapa)", "Curva S"}
    ws = wb["Cronograma FF (por etapa)"]
    # cabeçalho: Etapa | Veks | Fat Direto | Total | % | 2026-06 | 2026-07
    header = [c.value for c in ws[1]]
    assert header[:5] == ["Etapa", "Veks (R$)", "Fat Direto (R$)", "Total (R$)", "%"]
    assert "2026-06" in header and "2026-07" in header
    # primeira etapa
    assert ws.cell(row=2, column=1).value == "Fundação"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.pythonlibs/bin/python -m pytest tests/test_cronograma_fisico_financeiro.py -q`
Expected: FAIL com `ImportError: cannot import name 'exportar_fisico_financeiro_xlsx'`.

- [ ] **Step 3: Implementar**

Acrescentar em `services/cronograma_fisico_financeiro.py`:
```python
def exportar_fisico_financeiro_xlsx(dados: dict):
    """Gera um openpyxl.Workbook no layout da planilha de referência:
    aba 'Cronograma FF (por etapa)' + aba 'Curva S'."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Cronograma FF (por etapa)"

    meses = dados.get("meses_ordenados", [])
    header = ["Etapa", "Veks (R$)", "Fat Direto (R$)", "Total (R$)", "%"] + list(meses)
    ws.append(header)

    total_geral = dados["totais"]["total"] or Decimal("1")
    for et in dados["etapas"]:
        total_et = et["previsto"]["total"]
        pct = (total_et / total_geral) if total_geral else Decimal("0")
        linha = [
            et["nome"],
            float(et["veks"]), float(et["fat_direto"]), float(total_et), float(pct),
        ]
        for mes in meses:
            linha.append(float(et["meses"].get(mes, 0)))
        ws.append(linha)

    t = dados["totais"]
    rodape = ["TOTAL GERAL", float(t["veks"]), float(t["fat_direto"]), float(t["total"]), 1.0]
    # soma por mês
    soma_mes = {m: Decimal("0") for m in meses}
    for et in dados["etapas"]:
        for m in meses:
            soma_mes[m] += et["meses"].get(m, Decimal("0"))
    rodape += [float(soma_mes[m]) for m in meses]
    ws.append(rodape)

    # aba Curva S
    ws2 = wb.create_sheet("Curva S")
    ws2.append(["Mês", "Custo do mês", "Custo acumulado", "% acumulado"])
    for ponto in dados.get("curva_s", []):
        ws2.append([
            ponto["mes"], float(ponto["custo_mes"]),
            float(ponto["acumulado"]), float(ponto["pct_acumulado"]),
        ])
    return wb
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.pythonlibs/bin/python -m pytest tests/test_cronograma_fisico_financeiro.py -q`
Expected: PASS (12 testes no total).

- [ ] **Step 5: Commit**

```bash
git add services/cronograma_fisico_financeiro.py tests/test_cronograma_fisico_financeiro.py
git commit -m "feat(ff): export XLSX do cronograma físico-financeiro"
```

---

## Task 8: Rotas + template + link na página de cronograma

**Files:**
- Modify: `cronograma_views.py` (2 rotas novas, ao final do arquivo)
- Create: `templates/cronograma/fisico_financeiro.html`
- Modify: `templates/cronograma/obra.html` (link para a nova página)

- [ ] **Step 1: Adicionar as 2 rotas**

Ao final de `cronograma_views.py`:
```python
@cronograma_bp.route('/obra/<int:obra_id>/fisico-financeiro')
@login_required
def fisico_financeiro(obra_id: int):
    from services.cronograma_fisico_financeiro import montar_fisico_financeiro
    from models import Obra
    admin_id = _admin_id()
    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
    if not obra:
        flash('Obra não encontrada.', 'danger')
        return redirect(url_for('cronograma.index'))
    dados = montar_fisico_financeiro(obra_id, admin_id)
    return render_template('cronograma/fisico_financeiro.html', obra=obra, dados=dados)


@cronograma_bp.route('/obra/<int:obra_id>/fisico-financeiro/export.xlsx')
@login_required
def fisico_financeiro_xlsx(obra_id: int):
    import io
    from services.cronograma_fisico_financeiro import (
        montar_fisico_financeiro, exportar_fisico_financeiro_xlsx,
    )
    from models import Obra
    admin_id = _admin_id()
    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first()
    if not obra:
        flash('Obra não encontrada.', 'danger')
        return redirect(url_for('cronograma.index'))
    dados = montar_fisico_financeiro(obra_id, admin_id)
    wb = exportar_fisico_financeiro_xlsx(dados)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf, as_attachment=True,
        download_name=f'cronograma_ff_obra_{obra_id}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
```

- [ ] **Step 2: Criar o template**

Create `templates/cronograma/fisico_financeiro.html`:
```html
{% extends "base_completo.html" %}
{% block content %}
<div class="container-fluid py-3">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h4 class="mb-0">Cronograma Físico-Financeiro — {{ obra.nome }}</h4>
    <a class="btn btn-success btn-sm"
       href="{{ url_for('cronograma.fisico_financeiro_xlsx', obra_id=obra.id) }}">
      Baixar Excel
    </a>
  </div>

  {% if dados.avisos %}
    <div class="alert alert-warning">
      <ul class="mb-0">{% for a in dados.avisos %}<li>{{ a }}</li>{% endfor %}</ul>
    </div>
  {% endif %}

  {% if not dados.etapas %}
    <div class="alert alert-info">
      Nenhum custo faseável encontrado. Verifique se o cronograma foi materializado
      (proposta aprovada) e se as tarefas têm datas e custo (ObraServicoCusto).
    </div>
  {% else %}
  <div class="table-responsive">
    <table class="table table-sm table-bordered align-middle">
      <thead class="table-light">
        <tr>
          <th>Etapa</th><th class="text-end">Veks (R$)</th>
          <th class="text-end">Fat Direto (R$)</th><th class="text-end">Total (R$)</th>
          <th class="text-end">%</th>
          {% for mes in dados.meses_ordenados %}<th class="text-end">{{ mes }}</th>{% endfor %}
        </tr>
      </thead>
      <tbody>
        {% for et in dados.etapas %}
        <tr>
          <td>{{ et.nome }}</td>
          <td class="text-end">{{ '%.2f'|format(et.veks) }}</td>
          <td class="text-end">{{ '%.2f'|format(et.fat_direto) }}</td>
          <td class="text-end">{{ '%.2f'|format(et.previsto.total) }}</td>
          <td class="text-end">
            {% if dados.totais.total %}{{ '%.1f'|format(100 * et.previsto.total / dados.totais.total) }}%{% else %}—{% endif %}
          </td>
          {% for mes in dados.meses_ordenados %}
          <td class="text-end">{{ '%.2f'|format(et.meses.get(mes, 0)) }}</td>
          {% endfor %}
        </tr>
        {% endfor %}
      </tbody>
      <tfoot class="table-light fw-bold">
        <tr>
          <td>TOTAL GERAL</td>
          <td class="text-end">{{ '%.2f'|format(dados.totais.veks) }}</td>
          <td class="text-end">{{ '%.2f'|format(dados.totais.fat_direto) }}</td>
          <td class="text-end">{{ '%.2f'|format(dados.totais.total) }}</td>
          <td class="text-end">100%</td>
          {% for mes in dados.meses_ordenados %}<td></td>{% endfor %}
        </tr>
      </tfoot>
    </table>
  </div>

  <h5 class="mt-4">Curva S financeira (custo acumulado)</h5>
  <table class="table table-sm table-bordered w-auto">
    <thead class="table-light"><tr><th>Mês</th><th class="text-end">Custo do mês</th><th class="text-end">Acumulado</th><th class="text-end">% acumulado</th></tr></thead>
    <tbody>
      {% for p in dados.curva_s %}
      <tr>
        <td>{{ p.mes }}</td>
        <td class="text-end">{{ '%.2f'|format(p.custo_mes) }}</td>
        <td class="text-end">{{ '%.2f'|format(p.acumulado) }}</td>
        <td class="text-end">{{ '%.1f'|format(100 * p.pct_acumulado) }}%</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  {% if dados.nao_faseado and dados.nao_faseado > 0 %}
    <p class="text-muted">Custo não faseado (tarefas sem datas): R$ {{ '%.2f'|format(dados.nao_faseado) }}</p>
  {% endif %}
  {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 3: Adicionar o link na página da obra**

Em `templates/cronograma/obra.html`, localizar a barra de ações/botões do topo
(onde já há botões como "Recalcular"/"Nova tarefa") e adicionar:
```html
<a class="btn btn-outline-primary btn-sm"
   href="{{ url_for('cronograma.fisico_financeiro', obra_id=obra.id) }}">
  Físico-Financeiro
</a>
```
Se não houver uma barra óbvia, adicionar logo após o `<h*>` de título da página.

- [ ] **Step 4: GATE de boot + rota registrada**

Run:
```bash
python -c "import main; print('BLUEPRINTS', len(main.app.blueprints)); print('FF_ROUTE', any('fisico-financeiro' in str(r) for r in main.app.url_map.iter_rules()))"
```
Expected: `BLUEPRINTS 54` e `FF_ROUTE True`.

- [ ] **Step 5: Commit**

```bash
git add cronograma_views.py templates/cronograma/fisico_financeiro.html templates/cronograma/obra.html
git commit -m "feat(ff): página e export do cronograma físico-financeiro"
```

---

## Task 9: Smoke Playwright da nova página

**Files:**
- Modify: `tests/test_browser_all_modules.py` (adicionar parametrização da nova rota no ConsoleSweep)

- [ ] **Step 1: Adicionar a rota ao varredor de console (sem erro de JS)**

Em `tests/test_browser_all_modules.py`, localizar a lista de páginas do
`TestConsoleSweep::test_sem_erros_js_criticos` (parametrização `(path, nome)`) e
adicionar uma entrada que aponte para uma obra com cronograma. Como o path precisa de
`obra_id`, usar a primeira obra com cronograma materializado (helper já existente no
arquivo para descobrir uma obra; se não houver, adicionar):
```python
        ("/cronograma/", "Cronograma"),  # já existe — manter
        # nova: a página físico-financeira é coberta via navegação a partir da obra
```
Se o arquivo tiver um teste de navegação por obra (TestBloco3ObrasRdo), adicionar lá um
caso que abre `/cronograma/obra/<id>/fisico-financeiro` da 1ª obra e valida HTTP 200 +
presença do texto "Físico-Financeiro".

- [ ] **Step 2: Rodar o smoke (servidor precisa estar de pé)**

Run (servidor gunicorn já roda via workflow; senão subir):
```bash
bash run_tests.sh --bloco3 2>&1 | tail -15
```
Expected: `[SUCESSO] Todos os testes passaram!` (inclui o novo caso). Se não houver obra
com cronograma no banco de teste, o caso deve pular com skip explícito (não falhar).

- [ ] **Step 3: Commit**

```bash
git add tests/test_browser_all_modules.py
git commit -m "test(ff): smoke da página físico-financeira"
```

---

## Self-Review — cobertura do spec

- Spec §1.1 custo por etapa/tarefa → Task 6 (`montar_fisico_financeiro`, alocação por peso) + Task 3.
- Spec §1.2 faseamento mensal + Curva S → Tasks 2 e 4 + orquestrador (Task 6).
- Spec §1.3 split Veks×Fat → Task 1 (colunas) + Task 5 + Task 6.
- Spec §1.4 realizado×previsto por etapa → Task 6 (`orcado`/`realizado`/`desvio` por etapa).
- Spec §1.5 / §4.5 export XLSX (firme) → Task 7 + rota na Task 8.
- Spec §3 definições (etapa=raiz; previsto=realizado+a_realizar; 3 colunas Veks/Fat;
  indiretos fora) → Tasks 1 e 6.
- Spec §5 fluxo de dados → Task 6.
- Spec §6 casos de borda (sem datas→nao_faseado; sem OSC→aviso; empty state) → Tasks 2 e 6
  (avisos/nao_faseado) + Task 8 (empty state no template).
- Spec §7 invariantes/testes → Tasks 2–5 (puros) + Task 9 (smoke).
- Spec §8 fora de escopo (realizado não faseado; indiretos; edição; cotações) → respeitado.
```
