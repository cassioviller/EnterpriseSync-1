# Importador Baias + Dashboard Físico-Financeiro — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que, ao importar um arquivo das Baias (JSON) em produção, o painel Físico-Financeiro da obra abra pronto — com custo por etapa faseado, Curva S física × financeira, fluxo de caixa (regra do faturamento direto), KPIs e EVM (PV/EV/AC/SPI/CPI).

**Architecture:** Mantém a **Abordagem A — derivado** já aprovada (`docs/superpowers/specs/2026-06-23-cronograma-fisico-financeiro-design.md`): nada de tabelas novas (`EtapaFisicoFinanceiro`/`ItemCusto`). Um **importador** popula os modelos existentes (`Obra`, `Cliente`, `TarefaCronograma`, `ItemMedicaoComercial`, `ItemMedicaoCronogramaTarefa`, `ObraServicoCusto`, `MedicaoObra`); o **serviço derivado** (`services/cronograma_fisico_financeiro.py`) é estendido com funções puras (caixa, EVM, curva física, KPIs); a **view/template** existentes ganham os novos blocos. Tudo multitenant por `admin_id` e idempotente.

**Tech Stack:** Flask + SQLAlchemy (Postgres), Jinja2 + Bootstrap 5 (`templates/base_completo.html`), Chart.js local (`static/js/vendor/chart.js`), `openpyxl`, pytest (marcadores `@integration`/`@browser`), `Decimal` para dinheiro.

---

## Mapa de arquivos

| Arquivo | Responsabilidade | Ação |
|---|---|---|
| `services/importacao_fisico_financeiro.py` | Parse do JSON → popular modelos existentes (idempotente, tenant-scoped) | **Criar** |
| `tests/test_importacao_fisico_financeiro.py` | Unit/integração do importador com os números do JSON | **Criar** |
| `services/cronograma_fisico_financeiro.py` | Funções puras novas: `fluxo_caixa`, `evm`, `curva_s_fisica`, `kpis`; ampliar `montar_fisico_financeiro` | **Modificar** |
| `tests/test_cronograma_fisico_financeiro.py` | Testes das funções novas (invariantes + números do JSON) | **Modificar** |
| `cronograma_views.py` | Passar as novas séries para o template; (Fase 3) | **Modificar** |
| `templates/cronograma/fisico_financeiro.html` | KPIs, gráficos Chart.js, fluxo de caixa, medições, SPI/CPI | **Modificar** |
| `importacao_views.py` | Novo módulo de import "Cronograma Físico-Financeiro (JSON)" | **Modificar** |
| `templates/importacao/*` | Card/preview do novo módulo | **Modificar** |
| `static/js/fisico_financeiro_charts.js` | Inicialização dos gráficos | **Criar** (Fase 3) |

**Dados de referência (fonte de verdade do piloto):** `cronograma_fisico_financeiro_baias.json` (já no repositório, dentro de `files (5).zip`; descompacte para a raiz ou aponte o teste para o caminho). Estrutura confirmada:
- `obra{nome, codigo_obra, cliente, local}`, `contrato{valor_venda: 1505613.76, data_inicio: "2026-06-04", data_fim_cronograma: "2026-09-11"}`, `parametros{imposto_pct: 0.135}`.
- `medicoes[6]` = `{nome, data, pct, recebido_no_mes}` (Σpct = 1.0; pct é fração do `valor_venda`).
- `eap[12]` = `{codigo, nome, grupo, cronograma{inicio, fim, pct_fisico, tarefas_mpp[], transversal}, custo{veks, fat_direto, total, peso_pct}, itens[]{item, veks, fat}}`. `INDIRETOS` tem `transversal: true`.
- `cronograma_tarefas[43]` = `{id, nivel, nome, inicio, fim, dias, pct_fisico, predecessoras[], marco, resumo}`.
- `resumo{custo_total: 1158160, desembolso_veks: 734460, faturamento_direto: 423700, imposto_estimado: 146058, lucro_projetado_estimado: 201396}`.

**Decisões de mapeamento (JSON → modelos existentes)** — fixas para todo o plano:
- `Obra`: chave idempotente = (`codigo` = `obra.codigo_obra`, `admin_id`). `valor_contrato` = `contrato.valor_venda`; `data_inicio` = `contrato.data_inicio`; `data_previsao_fim` = `contrato.data_fim_cronograma`; `cliente_id` = Cliente encontrado/criado por (`nome` = `obra.cliente`, `admin_id`).
- Por **etapa EAP** cria-se: 1 `TarefaCronograma` **raiz** (`tarefa_pai_id=None`, datas da etapa) + N `TarefaCronograma` **folha** (uma por id em `cronograma.tarefas_mpp`, datas vindas de `cronograma_tarefas`). Se `tarefas_mpp` vazio (ex.: transversal), cria 1 folha com as datas da etapa.
- 1 `ItemMedicaoComercial` por etapa (`valor_comercial` = `round(peso_pct × valor_venda, 2)`; usado só para exibição — o serviço derivado liga custo↔tarefa por ele).
- 1 `ItemMedicaoCronogramaTarefa` por folha, `peso = max(1, dias da folha)` (faseia proporcional à duração).
- 1 `ObraServicoCusto` por etapa: `item_medicao_comercial_id` = IMC; `valor_orcado` = `custo.total`; `mao_obra_a_realizar` = `custo.veks` com `fonte_mao_obra='veks'`; `material_a_realizar` = `custo.fat_direto` com `fonte_material='fat_direto'`; `outros_a_realizar=0`, `fonte_outros='veks'`; `realizado_*=0`. (Invariante: `previsto.total = veks+fat = custo.total`.)
- 1 `MedicaoObra` por medição: `numero=i+1`, `data_medicao`/`periodo_*` da data, `percentual_executado = pct×100`, `valor_medido = round(pct × valor_venda, 2)`, `status='PENDENTE'`.

---

## Fase 1 — Importador (objetivo-chave: importar → página FF abre pronta)

### Task 1: Esqueleto do importador + carregamento idempotente da Obra

**Files:**
- Create: `services/importacao_fisico_financeiro.py`
- Test: `tests/test_importacao_fisico_financeiro.py`

- [ ] **Step 1: Escrever o teste que falha (fixture de admin + JSON, cria a obra)**

```python
# tests/test_importacao_fisico_financeiro.py
import json
import os
from datetime import date
from decimal import Decimal

import pytest

from app import app, db
from models import Usuario, TipoUsuario, Obra, Cliente
from werkzeug.security import generate_password_hash
from services.importacao_fisico_financeiro import importar_fisico_financeiro

JSON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "cronograma_fisico_financeiro_baias.json",
)


def _carregar_json():
    if not os.path.exists(JSON_PATH):
        pytest.skip("cronograma_fisico_financeiro_baias.json ausente na raiz")
    with open(JSON_PATH, encoding="utf-8") as fp:
        return json.load(fp)


@pytest.fixture
def admin():
    with app.app_context():
        import secrets
        tag = secrets.token_hex(4)
        u = Usuario(
            username=f"ff_{tag}", email=f"ff_{tag}@test.local", nome="FF Import",
            password_hash=generate_password_hash("x"), tipo_usuario=TipoUsuario.ADMIN,
            ativo=True,
        )
        db.session.add(u)
        db.session.commit()
        yield u
        db.session.rollback()


@pytest.mark.integration
def test_importar_cria_obra_idempotente(admin):
    dados = _carregar_json()
    with app.app_context():
        r1 = importar_fisico_financeiro(dados, admin.id)
        obra = Obra.query.filter_by(codigo=dados["obra"]["codigo_obra"], admin_id=admin.id).first()
        assert obra is not None
        assert float(obra.valor_contrato) == dados["contrato"]["valor_venda"]
        assert obra.data_inicio == date.fromisoformat(dados["contrato"]["data_inicio"])
        assert obra.cliente_id is not None
        # idempotência: reimportar não duplica a obra
        r2 = importar_fisico_financeiro(dados, admin.id)
        assert Obra.query.filter_by(codigo=dados["obra"]["codigo_obra"], admin_id=admin.id).count() == 1
        assert r1["obra_id"] == r2["obra_id"]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_importacao_fisico_financeiro.py::test_importar_cria_obra_idempotente -q -p no:warnings`
Expected: FAIL com `ModuleNotFoundError: No module named 'services.importacao_fisico_financeiro'`.

- [ ] **Step 3: Implementar carregamento idempotente da obra**

```python
# services/importacao_fisico_financeiro.py
"""Importador do cronograma físico-financeiro (piloto Baias).

Ingere o JSON `cronograma_fisico_financeiro_baias.json` e popula os modelos
EXISTENTES (Abordagem A — derivado): Obra, Cliente, TarefaCronograma,
ItemMedicaoComercial, ItemMedicaoCronogramaTarefa, ObraServicoCusto, MedicaoObra.
Idempotente por (Obra.codigo, admin_id) e escopado por tenant.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from app import db


def _data(s):
    return date.fromisoformat(s) if s else None


def _obter_ou_criar_cliente(admin_id: int, nome: str) -> int:
    from models import Cliente
    nome = (nome or "Cliente").strip()
    c = Cliente.query.filter_by(admin_id=admin_id, nome=nome).first()
    if not c:
        c = Cliente(admin_id=admin_id, nome=nome)
        db.session.add(c)
        db.session.flush()
    return c.id


def _obter_ou_criar_obra(admin_id: int, dados: dict):
    from models import Obra
    obra_in = dados["obra"]
    contrato = dados["contrato"]
    codigo = str(obra_in["codigo_obra"])
    obra = Obra.query.filter_by(codigo=codigo, admin_id=admin_id).first()
    if not obra:
        obra = Obra(codigo=codigo, admin_id=admin_id, status="Em andamento")
        db.session.add(obra)
    obra.nome = obra_in["nome"]
    obra.cliente_id = _obter_ou_criar_cliente(admin_id, obra_in.get("cliente"))
    obra.valor_contrato = float(contrato["valor_venda"])
    obra.data_inicio = _data(contrato.get("data_inicio"))
    obra.data_previsao_fim = _data(contrato.get("data_fim_cronograma") or contrato.get("data_fim_contratual"))
    db.session.flush()
    return obra


def importar_fisico_financeiro(dados: dict, admin_id: int) -> dict:
    """Importa o JSON no escopo do tenant. Retorna contagens + obra_id."""
    obra = _obter_ou_criar_obra(admin_id, dados)
    db.session.commit()
    return {"obra_id": obra.id, "etapas": 0, "tarefas": 0, "medicoes": 0}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_importacao_fisico_financeiro.py::test_importar_cria_obra_idempotente -q -p no:warnings`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/importacao_fisico_financeiro.py tests/test_importacao_fisico_financeiro.py
git commit -m "feat(ff-import): esqueleto idempotente do importador (obra+cliente)"
```

---

### Task 2: Limpeza idempotente das linhas-filhas FF da obra

Reimportar deve substituir (não acumular) tarefas/OSC/IMC/medições da obra.

**Files:**
- Modify: `services/importacao_fisico_financeiro.py`
- Test: `tests/test_importacao_fisico_financeiro.py`

- [ ] **Step 1: Teste que falha (reimport não duplica filhos)**

```python
@pytest.mark.integration
def test_reimport_nao_duplica_filhos(admin):
    from models import TarefaCronograma, ObraServicoCusto, ItemMedicaoComercial, MedicaoObra
    dados = _carregar_json()
    with app.app_context():
        importar_fisico_financeiro(dados, admin.id)
        importar_fisico_financeiro(dados, admin.id)  # 2ª vez
        obra = Obra.query.filter_by(codigo=dados["obra"]["codigo_obra"], admin_id=admin.id).first()
        n_eap = len(dados["eap"])
        assert ObraServicoCusto.query.filter_by(obra_id=obra.id, admin_id=admin.id).count() == n_eap
        assert ItemMedicaoComercial.query.filter_by(obra_id=obra.id, admin_id=admin.id).count() == n_eap
        assert MedicaoObra.query.filter_by(obra_id=obra.id, admin_id=admin.id).count() == len(dados["medicoes"])
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_importacao_fisico_financeiro.py::test_reimport_nao_duplica_filhos -q -p no:warnings`
Expected: FAIL (`AssertionError`: contagem 0 ≠ esperado — filhos ainda não são criados).

- [ ] **Step 3: Implementar limpeza + chamada no orquestrador**

```python
def _limpar_filhos_ff(obra_id: int, admin_id: int) -> None:
    """Remove tarefas, OSC, IMC (+links) e medições da obra antes de recriar.
    Ordem respeita FKs: links → IMC/OSC → tarefas → medições."""
    from models import (
        TarefaCronograma, ObraServicoCusto, ItemMedicaoComercial,
        ItemMedicaoCronogramaTarefa, MedicaoObra,
    )
    imc_ids = [r[0] for r in db.session.query(ItemMedicaoComercial.id)
               .filter_by(obra_id=obra_id, admin_id=admin_id).all()]
    if imc_ids:
        ItemMedicaoCronogramaTarefa.query.filter(
            ItemMedicaoCronogramaTarefa.item_medicao_id.in_(imc_ids)
        ).delete(synchronize_session=False)
    ObraServicoCusto.query.filter_by(obra_id=obra_id, admin_id=admin_id).delete(synchronize_session=False)
    ItemMedicaoComercial.query.filter_by(obra_id=obra_id, admin_id=admin_id).delete(synchronize_session=False)
    TarefaCronograma.query.filter_by(obra_id=obra_id, admin_id=admin_id).delete(synchronize_session=False)
    MedicaoObra.query.filter_by(obra_id=obra_id, admin_id=admin_id).delete(synchronize_session=False)
    db.session.flush()
```

Em `importar_fisico_financeiro`, logo após `obra = _obter_ou_criar_obra(...)`:

```python
    _limpar_filhos_ff(obra.id, admin_id)
```

(o teste ainda passará porque os filhos só começam a ser criados na Task 3; aqui garantimos a limpeza idempotente desde já.)

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_importacao_fisico_financeiro.py::test_reimport_nao_duplica_filhos -q -p no:warnings`
Expected: PASS (contagens 0 == 0 → ainda não criados; passa). A asserção forte vem na Task 3.

- [ ] **Step 5: Commit**

```bash
git add services/importacao_fisico_financeiro.py tests/test_importacao_fisico_financeiro.py
git commit -m "feat(ff-import): limpeza idempotente das linhas-filhas da obra"
```

---

### Task 3: Criar tarefas (raiz+folhas), IMC, links e OSC por etapa

**Files:**
- Modify: `services/importacao_fisico_financeiro.py`
- Test: `tests/test_importacao_fisico_financeiro.py`

- [ ] **Step 1: Teste que falha (contagens + conservação de custo)**

```python
@pytest.mark.integration
def test_importa_etapas_custo_e_tarefas(admin):
    from models import TarefaCronograma, ObraServicoCusto, ItemMedicaoCronogramaTarefa
    dados = _carregar_json()
    with app.app_context():
        r = importar_fisico_financeiro(dados, admin.id)
        obra_id = r["obra_id"]
        n_eap = len(dados["eap"])
        # 1 OSC por etapa
        oscs = ObraServicoCusto.query.filter_by(obra_id=obra_id, admin_id=admin.id).all()
        assert len(oscs) == n_eap
        # conservação: Σ valor_orcado == resumo.custo_total (tolerância de centavos)
        soma = sum(Decimal(str(o.valor_orcado or 0)) for o in oscs)
        assert abs(soma - Decimal(str(dados["resumo"]["custo_total"]))) <= Decimal("1.00")
        # veks/fat preservados por etapa
        for o in oscs:
            assert (o.fonte_mao_obra == "veks") and (o.fonte_material == "fat_direto")
        # raízes = n_eap; total de tarefas = raízes + folhas (>= raízes)
        raizes = TarefaCronograma.query.filter_by(obra_id=obra_id, admin_id=admin.id, tarefa_pai_id=None).count()
        assert raizes == n_eap
        # cada IMC tem pelo menos 1 link de peso
        assert ItemMedicaoCronogramaTarefa.query.filter_by(admin_id=admin.id).count() >= n_eap
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_importacao_fisico_financeiro.py::test_importa_etapas_custo_e_tarefas -q -p no:warnings`
Expected: FAIL (`len(oscs) == 0`).

- [ ] **Step 3: Implementar a criação por etapa**

```python
def _index_tarefas_mpp(dados: dict) -> dict:
    """id da tarefa MPP -> registro de cronograma_tarefas."""
    return {t["id"]: t for t in dados.get("cronograma_tarefas", [])}


def _criar_etapas(obra, dados: dict, admin_id: int) -> dict:
    from models import (
        TarefaCronograma, ItemMedicaoComercial, ItemMedicaoCronogramaTarefa,
        ObraServicoCusto,
    )
    mpp = _index_tarefas_mpp(dados)
    valor_venda = Decimal(str(dados["contrato"]["valor_venda"]))
    n_tarefas = 0

    for etapa in dados["eap"]:
        cron = etapa["cronograma"]
        custo = etapa["custo"]
        ini, fim = _data(cron.get("inicio")), _data(cron.get("fim"))

        raiz = TarefaCronograma(
            obra_id=obra.id, admin_id=admin_id, tarefa_pai_id=None,
            nome_tarefa=etapa["nome"], ordem=0, duracao_dias=1,
            data_inicio=ini, data_fim=fim,
            percentual_concluido=float(cron.get("pct_fisico") or 0),
        )
        db.session.add(raiz)
        db.session.flush()
        n_tarefas += 1

        # folhas: uma por tarefa MPP da etapa; se vazio, 1 folha com datas da etapa
        ids_mpp = cron.get("tarefas_mpp") or []
        folhas_spec = [mpp[i] for i in ids_mpp if i in mpp] or [
            {"nome": etapa["nome"], "inicio": cron.get("inicio"),
             "fim": cron.get("fim"), "dias": 1, "pct_fisico": cron.get("pct_fisico") or 0}
        ]

        imc = ItemMedicaoComercial(
            obra_id=obra.id, admin_id=admin_id, nome=etapa["nome"],
            valor_comercial=(valor_venda * Decimal(str(custo.get("peso_pct") or 0))).quantize(Decimal("0.01")),
            status="PENDENTE",
        )
        db.session.add(imc)
        db.session.flush()

        for j, fspec in enumerate(folhas_spec, start=1):
            dias = int(round(float(fspec.get("dias") or 1)))
            folha = TarefaCronograma(
                obra_id=obra.id, admin_id=admin_id, tarefa_pai_id=raiz.id,
                nome_tarefa=fspec["nome"], ordem=j, duracao_dias=max(1, dias),
                data_inicio=_data(fspec.get("inicio")), data_fim=_data(fspec.get("fim")),
                percentual_concluido=float(fspec.get("pct_fisico") or 0),
            )
            db.session.add(folha)
            db.session.flush()
            n_tarefas += 1
            db.session.add(ItemMedicaoCronogramaTarefa(
                item_medicao_id=imc.id, cronograma_tarefa_id=folha.id,
                admin_id=admin_id, peso=Decimal(max(1, dias)),
            ))

        db.session.add(ObraServicoCusto(
            obra_id=obra.id, admin_id=admin_id, nome=etapa["nome"],
            item_medicao_comercial_id=imc.id,
            valor_orcado=Decimal(str(custo.get("total") or 0)),
            realizado_material=Decimal("0"), realizado_mao_obra=Decimal("0"),
            realizado_outros=Decimal("0"),
            material_a_realizar=Decimal(str(custo.get("fat_direto") or 0)),
            mao_obra_a_realizar=Decimal(str(custo.get("veks") or 0)),
            outros_a_realizar=Decimal("0"),
            fonte_material="fat_direto", fonte_mao_obra="veks", fonte_outros="veks",
        ))

    db.session.flush()
    return {"etapas": len(dados["eap"]), "tarefas": n_tarefas}
```

Em `importar_fisico_financeiro`, após `_limpar_filhos_ff(...)`:

```python
    stats = _criar_etapas(obra, dados, admin_id)
    db.session.commit()
    return {"obra_id": obra.id, **stats, "medicoes": 0}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_importacao_fisico_financeiro.py::test_importa_etapas_custo_e_tarefas -q -p no:warnings`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/importacao_fisico_financeiro.py tests/test_importacao_fisico_financeiro.py
git commit -m "feat(ff-import): etapas → tarefas+IMC+links+OSC (conserva custo total)"
```

---

### Task 4: Criar medições da obra

**Files:**
- Modify: `services/importacao_fisico_financeiro.py`
- Test: `tests/test_importacao_fisico_financeiro.py`

- [ ] **Step 1: Teste que falha (6 medições, Σ valor == valor_venda)**

```python
@pytest.mark.integration
def test_importa_medicoes(admin):
    from models import MedicaoObra
    dados = _carregar_json()
    with app.app_context():
        r = importar_fisico_financeiro(dados, admin.id)
        meds = MedicaoObra.query.filter_by(obra_id=r["obra_id"], admin_id=admin.id).order_by(MedicaoObra.numero).all()
        assert len(meds) == len(dados["medicoes"])
        soma = sum(Decimal(str(m.valor_medido or 0)) for m in meds)
        assert abs(soma - Decimal(str(dados["contrato"]["valor_venda"]))) <= Decimal("1.00")
        assert meds[0].numero == 1
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_importacao_fisico_financeiro.py::test_importa_medicoes -q -p no:warnings`
Expected: FAIL (`len(meds) == 0`).

- [ ] **Step 3: Implementar criação de medições**

```python
def _criar_medicoes(obra, dados: dict, admin_id: int) -> int:
    from models import MedicaoObra
    valor_venda = Decimal(str(dados["contrato"]["valor_venda"]))
    n = 0
    for i, med in enumerate(dados.get("medicoes", []), start=1):
        d = _data(med.get("data"))
        pct = Decimal(str(med.get("pct") or 0))
        db.session.add(MedicaoObra(
            obra_id=obra.id, admin_id=admin_id, numero=i,
            data_medicao=d, periodo_inicio=d, periodo_fim=d,
            percentual_executado=float(pct * 100),
            valor_medido=(valor_venda * pct).quantize(Decimal("0.01")),
            valor_total_medido_periodo=(valor_venda * pct).quantize(Decimal("0.01")),
            status="PENDENTE",
            observacoes=med.get("obs"),
        ))
        n += 1
    db.session.flush()
    return n
```

Em `importar_fisico_financeiro`, antes do `commit` final:

```python
    n_med = _criar_medicoes(obra, dados, admin_id)
    db.session.commit()
    return {"obra_id": obra.id, **stats, "medicoes": n_med}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_importacao_fisico_financeiro.py::test_importa_medicoes -q -p no:warnings`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/importacao_fisico_financeiro.py tests/test_importacao_fisico_financeiro.py
git commit -m "feat(ff-import): medições da obra (Σ valor == valor_venda)"
```

---

### Task 5: Integração — após importar, a página FF derivada renderiza dados

**Files:**
- Test: `tests/test_importacao_fisico_financeiro.py`

- [ ] **Step 1: Teste de integração (montar_fisico_financeiro vê as etapas)**

```python
@pytest.mark.integration
def test_pos_import_montar_ff_tem_etapas_e_faseamento(admin):
    from services.cronograma_fisico_financeiro import montar_fisico_financeiro
    dados = _carregar_json()
    with app.app_context():
        r = importar_fisico_financeiro(dados, admin.id)
        ff = montar_fisico_financeiro(r["obra_id"], admin.id)
        assert len(ff["etapas"]) == len(dados["eap"])
        # veks + fat == previsto total (invariante do design)
        t = ff["totais"]
        assert abs((t["veks"] + t["fat_direto"]) - t["previsto"]) <= Decimal("1.00")
        # custo faseado em meses + curva S monotônica
        assert len(ff["meses_ordenados"]) >= 1
        acum = [p["acumulado"] for p in ff["curva_s"]]
        assert acum == sorted(acum)
```

- [ ] **Step 2: Rodar**

Run: `python -m pytest tests/test_importacao_fisico_financeiro.py::test_pos_import_montar_ff_tem_etapas_e_faseamento -q -p no:warnings`
Expected: PASS (a engine derivada já existe; o import só populou os dados).

- [ ] **Step 3: Commit**

```bash
git add tests/test_importacao_fisico_financeiro.py
git commit -m "test(ff-import): pós-import a engine derivada fica pronta (etapas+curva S)"
```

---

### Task 6: Expor o importador na UI de importação (upload em produção)

**Files:**
- Modify: `importacao_views.py` (registrar módulo `fisico_financeiro` que aceita `.json`)
- Modify: `templates/importacao/index.html` (card do novo módulo)
- Test: `tests/test_importacao_fisico_financeiro.py` (rota de confirmação)

- [ ] **Step 1: Ler o padrão atual de `_handle_preview`/`_handle_confirmar`**

Run: `sed -n '170,330p' importacao_views.py`
Objetivo: confirmar como `MODULO_CONFIG`, `preview` e `confirmar` funcionam para XLSX e onde encaixar um ramo JSON. (O módulo FF usa `.json`, então adicionar uma rota dedicada `POST /importacao/fisico-financeiro/confirmar` que recebe o arquivo, faz `json.load`, chama `importar_fisico_financeiro` e redireciona para a página FF da obra.)

- [ ] **Step 2: Teste que falha (rota de confirmação cria a obra)**

```python
@pytest.mark.integration
def test_rota_confirmar_importa_json(admin):
    import io, json as _json
    dados = _carregar_json()
    with app.app_context():
        app.config["WTF_CSRF_ENABLED"] = False
        c = app.test_client()
        with c.session_transaction() as s:
            s["_user_id"] = str(admin.id)
            s["_fresh"] = True
        payload = _json.dumps(dados).encode("utf-8")
        r = c.post(
            "/importacao/fisico-financeiro/confirmar",
            data={"arquivo": (io.BytesIO(payload), "baias.json")},
            content_type="multipart/form-data", follow_redirects=False,
        )
        assert r.status_code in (302, 303)
        obra = Obra.query.filter_by(codigo=dados["obra"]["codigo_obra"], admin_id=admin.id).first()
        assert obra is not None
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `python -m pytest tests/test_importacao_fisico_financeiro.py::test_rota_confirmar_importa_json -q -p no:warnings`
Expected: FAIL (404 — rota inexistente).

- [ ] **Step 4: Implementar a rota no `importacao_views.py`**

Adicionar (seguindo os imports/guards já usados no arquivo — `Blueprint importacao_bp`, `@login_required`, `get_tenant_admin_id`):

```python
@importacao_bp.route('/fisico-financeiro/confirmar', methods=['POST'])
@login_required
def fisico_financeiro_confirmar():
    import json as _json
    from utils.tenant import get_tenant_admin_id
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    admin_id = get_tenant_admin_id()
    arquivo = request.files.get('arquivo')
    if not arquivo or not arquivo.filename.lower().endswith('.json'):
        flash('Envie o arquivo .json do cronograma físico-financeiro.', 'danger')
        return redirect(url_for('importacao.index'))
    try:
        dados = _json.load(arquivo.stream)
        resultado = importar_fisico_financeiro(dados, admin_id)
    except Exception as e:  # noqa: BLE001
        flash(f'Falha ao importar: {e}', 'danger')
        return redirect(url_for('importacao.index'))
    flash(
        f"Importado: {resultado['etapas']} etapas, {resultado['tarefas']} tarefas, "
        f"{resultado['medicoes']} medições.", 'success')
    return redirect(url_for('cronograma.fisico_financeiro', obra_id=resultado['obra_id']))
```

- [ ] **Step 5: Adicionar o card no template `templates/importacao/index.html`**

Inserir um bloco de upload `.json` (mesmo estilo dos cards existentes) apontando para a rota:

```html
<div class="col-md-4 mb-3">
  <div class="card h-100 shadow-sm">
    <div class="card-body">
      <h5 class="card-title"><i class="fas fa-chart-line me-2"></i>Cronograma Físico-Financeiro</h5>
      <p class="text-muted small">Importa o JSON do cronograma físico-financeiro (obra Baias) e abre o painel pronto.</p>
      <form method="POST" action="{{ url_for('importacao.fisico_financeiro_confirmar') }}" enctype="multipart/form-data">
        <input type="file" name="arquivo" accept=".json" required class="form-control form-control-sm mb-2">
        <button class="btn btn-sm btn-primary" type="submit"><i class="fas fa-upload me-1"></i>Importar</button>
      </form>
    </div>
  </div>
</div>
```

- [ ] **Step 6: Rodar e ver passar**

Run: `python -m pytest tests/test_importacao_fisico_financeiro.py::test_rota_confirmar_importa_json -q -p no:warnings`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add importacao_views.py templates/importacao/index.html tests/test_importacao_fisico_financeiro.py
git commit -m "feat(ff-import): upload .json na UI de importação → abre o painel FF"
```

---

### Task 7: Gate verde da Fase 1

- [ ] **Step 1: Rodar o gate rápido + os testes do importador**

Run: `bash run_tests.sh --gate`
Expected: `=== N passed, ... ===` com 0 failed (N ≥ 312 + novos testes do importador).

- [ ] **Step 2: Atualizar o status no documento de plano (marcar Fase 1 ✅) e commit**

```bash
git add docs/superpowers/plans/2026-06-24-importador-e-dashboard-fisico-financeiro.md
git commit -m "docs(plan): Fase 1 (importador) concluída — gate verde"
```

---

## Fase 2 — Analytics puras (caixa, EVM, curva física, KPIs)

> Todas as funções vivem em `services/cronograma_fisico_financeiro.py`, **sem Flask**, testadas isoladamente. Reusam `Decimal`, `CENTAVO`, `NAO_FASEADO`.

### Task 8: `fluxo_caixa` — regra do faturamento direto + imposto

Regra (do JSON `parametros.regra_fat_direto` e prompt §2): por período de medição,
`imposto = (medição − fat_direto_do_período) × imposto_pct`;
`entrada_líquida = medição − fat_direto_do_período − imposto`;
`caixa_mês = entrada_líquida − desembolso_veks_do_mês`; acumula `caixa_final`.

**Files:**
- Modify: `services/cronograma_fisico_financeiro.py`
- Test: `tests/test_cronograma_fisico_financeiro.py`

- [ ] **Step 1: Teste que falha (números fechados)**

```python
from services.cronograma_fisico_financeiro import fluxo_caixa


def test_fluxo_caixa_aplica_imposto_e_fat_direto():
    # 1 período: medição 100, fat_direto 40, imposto 13,5%, desembolso veks 30
    linhas = fluxo_caixa(
        medicoes=[{"mes": "2026-07", "valor": D("100")}],
        fat_direto_por_mes={"2026-07": D("40")},
        desembolso_veks_por_mes={"2026-07": D("30")},
        imposto_pct=D("0.135"),
    )
    l = linhas[0]
    assert l["imposto"] == D("8.10")            # (100-40)*0.135
    assert l["entrada_liquida"] == D("51.90")   # 100-40-8.10
    assert l["desembolso_veks"] == D("30")
    assert l["caixa_mes"] == D("21.90")         # 51.90-30
    assert l["caixa_acumulado"] == D("21.90")


def test_fluxo_caixa_acumula_entre_meses():
    linhas = fluxo_caixa(
        medicoes=[{"mes": "2026-07", "valor": D("100")}, {"mes": "2026-08", "valor": D("50")}],
        fat_direto_por_mes={"2026-07": D("0"), "2026-08": D("0")},
        desembolso_veks_por_mes={"2026-07": D("10"), "2026-08": D("5")},
        imposto_pct=D("0"),
    )
    assert linhas[1]["caixa_acumulado"] == linhas[0]["caixa_mes"] + linhas[1]["caixa_mes"]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py::test_fluxo_caixa_aplica_imposto_e_fat_direto -q -p no:warnings`
Expected: FAIL (`ImportError: cannot import name 'fluxo_caixa'`).

- [ ] **Step 3: Implementar `fluxo_caixa`**

```python
def fluxo_caixa(medicoes, fat_direto_por_mes, desembolso_veks_por_mes, imposto_pct):
    """Fluxo de caixa por mês a partir das medições (fixas pelo contrato) menos o
    faturamento direto do período, menos imposto sobre o líquido, menos o
    desembolso Veks faseado. `medicoes` = [{'mes','valor'}]; os *_por_mes são
    dicts {'YYYY-MM': Decimal}. Retorna lista ordenada por mês com acumulado."""
    imposto_pct = Decimal(imposto_pct)
    linhas = []
    caixa_acc = Decimal("0")
    for med in sorted(medicoes, key=lambda m: m["mes"]):
        mes = med["mes"]
        valor = Decimal(med["valor"])
        fat = Decimal(fat_direto_por_mes.get(mes, 0))
        desemb = Decimal(desembolso_veks_por_mes.get(mes, 0))
        base = valor - fat
        imposto = (base * imposto_pct).quantize(CENTAVO, ROUND_HALF_UP)
        entrada = (base - imposto).quantize(CENTAVO, ROUND_HALF_UP)
        caixa_mes = entrada - desemb
        caixa_acc += caixa_mes
        linhas.append({
            "mes": mes, "medicao": valor, "fat_direto": fat, "imposto": imposto,
            "entrada_liquida": entrada, "desembolso_veks": desemb,
            "caixa_mes": caixa_mes, "caixa_acumulado": caixa_acc,
        })
    return linhas
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py -k fluxo_caixa -q -p no:warnings`
Expected: PASS (2 testes).

- [ ] **Step 5: Commit**

```bash
git add services/cronograma_fisico_financeiro.py tests/test_cronograma_fisico_financeiro.py
git commit -m "feat(ff): fluxo_caixa (regra fat direto + imposto) — função pura"
```

---

### Task 9: `curva_s_fisica` e `evm` (PV/EV/AC/SPI/CPI)

Definições (prompt §0/§2):
- **PV(mês)** = custo planejado acumulado (a Curva S financeira já existente → `acumulado`).
- **EV(mês)** = `BAC × avanço_físico_acumulado(mês)`, onde avanço físico é ponderado por custo.
- **AC(mês)** = custo realizado acumulado (na ausência de lançamento mês a mês: `AC = PV`, conforme design §8).
- **SPI** = EV/PV; **CPI** = EV/AC. `BAC` = custo total previsto.

**Files:**
- Modify: `services/cronograma_fisico_financeiro.py`
- Test: `tests/test_cronograma_fisico_financeiro.py`

- [ ] **Step 1: Teste que falha (curva física + EVM coerentes)**

```python
from services.cronograma_fisico_financeiro import curva_s_fisica, evm


def test_curva_s_fisica_pondera_por_custo():
    # 2 etapas: A custo 100 @ 50% físico; B custo 300 @ 100% físico
    # avanço físico ponderado = (100*0.5 + 300*1.0)/400 = 0.875
    etapas = [
        {"previsto": {"total": D("100")}, "pct_fisico": D("0.5")},
        {"previsto": {"total": D("300")}, "pct_fisico": D("1.0")},
    ]
    pct = curva_s_fisica(etapas)
    assert pct == D("0.875")


def test_evm_spi_cpi():
    # PV=800 (planejado acum), EV=BAC*fisico=1000*0.7=700, AC=PV (sem lançamento)
    r = evm(bac=D("1000"), pv=D("800"), avanco_fisico=D("0.7"), ac=None)
    assert r["pv"] == D("800")
    assert r["ev"] == D("700")
    assert r["ac"] == D("800")           # AC=PV por padrão
    assert r["spi"] == (D("700") / D("800"))
    assert r["cpi"] == (D("700") / D("800"))


def test_evm_com_ac_real():
    r = evm(bac=D("1000"), pv=D("800"), avanco_fisico=D("0.7"), ac=D("650"))
    assert r["ac"] == D("650")
    assert r["cpi"] == (D("700") / D("650"))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py -k "curva_s_fisica or evm" -q -p no:warnings`
Expected: FAIL (`ImportError`).

- [ ] **Step 3: Implementar**

```python
def curva_s_fisica(etapas) -> Decimal:
    """Avanço físico acumulado ponderado por custo previsto:
    Σ(custo_etapa × pct_fisico_etapa) / Σ(custo_etapa). Sem custo → 0."""
    num = Decimal("0")
    den = Decimal("0")
    for e in etapas:
        custo = Decimal(e["previsto"]["total"])
        pct = Decimal(e.get("pct_fisico") or 0)
        num += custo * pct
        den += custo
    return (num / den) if den > 0 else Decimal("0")


def evm(bac, pv, avanco_fisico, ac=None):
    """Earned Value Management. EV = BAC × avanço físico. Se ac None → AC=PV
    (sem faseamento de realizado; ver design §8). SPI=EV/PV, CPI=EV/AC."""
    bac = Decimal(bac); pv = Decimal(pv); avanco = Decimal(avanco_fisico)
    ev = (bac * avanco)
    ac = Decimal(ac) if ac is not None else pv
    spi = (ev / pv) if pv > 0 else Decimal("0")
    cpi = (ev / ac) if ac > 0 else Decimal("0")
    return {"bac": bac, "pv": pv, "ev": ev, "ac": ac, "spi": spi, "cpi": cpi}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py -k "curva_s_fisica or evm" -q -p no:warnings`
Expected: PASS (3 testes).

- [ ] **Step 5: Commit**

```bash
git add services/cronograma_fisico_financeiro.py tests/test_cronograma_fisico_financeiro.py
git commit -m "feat(ff): curva_s_fisica + evm (PV/EV/AC/SPI/CPI) — funções puras"
```

---

### Task 10: `kpis` + ampliar `montar_fisico_financeiro` para expor caixa/EVM/curva física

`montar_fisico_financeiro` passa a anexar: `pct_fisico` por etapa (de `percentual_concluido` da raiz, 0-1), `fat_direto_por_mes` (faseado), `kpis`, `fluxo` (precisa das medições — recebe-as do banco), `evm`, `curva_s_fisica`.

**Files:**
- Modify: `services/cronograma_fisico_financeiro.py`
- Test: `tests/test_cronograma_fisico_financeiro.py`

- [ ] **Step 1: Teste que falha (kpis fecham com a venda)**

```python
from services.cronograma_fisico_financeiro import kpis


def test_kpis_lucro_projetado():
    totais = {"previsto": D("1158160"), "veks": D("734460"), "fat_direto": D("423700")}
    k = kpis(valor_venda=D("1505613.76"), totais=totais, imposto_total=D("146058"), recebido=D("0"))
    assert k["venda"] == D("1505613.76")
    assert k["custo_total"] == D("1158160")
    assert k["desembolso_veks"] == D("734460")
    assert k["fat_direto"] == D("423700")
    # lucro = venda - custo - imposto
    assert k["lucro_projetado"] == D("1505613.76") - D("1158160") - D("146058")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py -k kpis -q -p no:warnings`
Expected: FAIL (`ImportError`).

- [ ] **Step 3: Implementar `kpis` + ampliação do orquestrador**

```python
def kpis(valor_venda, totais, imposto_total, recebido):
    """KPIs de topo. lucro_projetado = venda − custo_total − imposto_total."""
    venda = Decimal(valor_venda)
    custo = Decimal(totais["previsto"])
    imposto = Decimal(imposto_total)
    return {
        "venda": venda,
        "custo_total": custo,
        "desembolso_veks": Decimal(totais["veks"]),
        "fat_direto": Decimal(totais["fat_direto"]),
        "imposto": imposto,
        "lucro_projetado": venda - custo - imposto,
        "lucro_pct": ((venda - custo - imposto) / venda) if venda > 0 else Decimal("0"),
        "recebido": Decimal(recebido),
    }
```

Na função `montar_fisico_financeiro`, antes do `return`, anexar (sem quebrar as chaves existentes):

```python
    # pct físico por etapa (raiz): percentual_concluido 0-100 → fração 0-1
    for et in etapas.values():
        raiz = por_id.get(et["etapa_id"]) if isinstance(et["etapa_id"], int) else None
        et["pct_fisico"] = (Decimal(raiz.percentual_concluido or 0) / 100) if raiz else Decimal("0")
    avanco_fisico = curva_s_fisica(list(etapas.values()))
    # fat direto faseado por mês: reusa o faseamento já calculado por etapa,
    # multiplicando a fração fat/total de cada etapa pelos seus meses.
    fat_por_mes: dict = {}
    for et in etapas.values():
        tot = et["previsto"]["total"] or Decimal("1")
        frac_fat = (et["fat_direto"] / tot) if tot else Decimal("0")
        for mes, val in et["meses"].items():
            fat_por_mes[mes] = fat_por_mes.get(mes, Decimal("0")) + (val * frac_fat)
```

E no dict de retorno, acrescentar as chaves:

```python
        "avanco_fisico": avanco_fisico,
        "fat_direto_por_mes": fat_por_mes,
```

(A montagem de `kpis`/`fluxo`/`evm` completos — que dependem de medições e imposto — é feita na view na Fase 3, combinando estas funções puras com os dados do banco.)

- [ ] **Step 4: Rodar e ver passar (todos os testes do serviço)**

Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py -q -p no:warnings`
Expected: PASS (todos — antigos + novos).

- [ ] **Step 5: Commit**

```bash
git add services/cronograma_fisico_financeiro.py tests/test_cronograma_fisico_financeiro.py
git commit -m "feat(ff): kpis + montar_fisico_financeiro expõe avanço físico e fat/mês"
```

---

### Task 11: Gate verde da Fase 2

- [ ] **Step 1: Rodar o gate**

Run: `bash run_tests.sh --gate`
Expected: 0 failed.

- [ ] **Step 2: Commit do status**

```bash
git add docs/superpowers/plans/2026-06-24-importador-e-dashboard-fisico-financeiro.md
git commit -m "docs(plan): Fase 2 (analytics puras) concluída — gate verde"
```

---

## Fase 3 — Dashboard UI (KPIs, gráficos, caixa, medições)

> **Pré-requisito recomendado:** o usuário tem um protótipo HTML do dashboard (KPIs, Curva S com recebido/gasto/lucro, custo por etapa clicável, fluxo de caixa). **Pedir o protótipo antes de implementar esta fase** para ancorar layout/comportamento. As tarefas abaixo entregam a estrutura; o protótipo refina o visual.

### Task 12: View monta o payload consolidado (KPIs + séries) e JSON da API

**Files:**
- Modify: `cronograma_views.py` (rota `fisico_financeiro` + nova rota `…/dados` JSON)
- Test: `tests/test_importacao_fisico_financeiro.py` (smoke da rota após import)

- [ ] **Step 1: Teste que falha (rota `/dados` devolve KPIs e séries)**

```python
@pytest.mark.integration
def test_rota_dados_ff_apos_import(admin):
    dados = _carregar_json()
    with app.app_context():
        r = importar_fisico_financeiro(dados, admin.id)
        c = app.test_client()
        with c.session_transaction() as s:
            s["_user_id"] = str(admin.id); s["_fresh"] = True
        resp = c.get(f"/cronograma/obra/{r['obra_id']}/fisico-financeiro/dados")
        assert resp.status_code == 200
        body = resp.get_json()
        for chave in ("kpis", "curva_s", "fluxo_caixa", "evm", "medicoes", "etapas"):
            assert chave in body
        assert body["kpis"]["venda"] == dados["contrato"]["valor_venda"]
```

- [ ] **Step 2..4:** Implementar a rota `GET /cronograma/obra/<int:obra_id>/fisico-financeiro/dados` que: chama `montar_fisico_financeiro`, lê `MedicaoObra` da obra, calcula `imposto_total`/`recebido` a partir das medições + `fat_direto_por_mes`, chama `fluxo_caixa`, `kpis`, `evm` (com `bac=totais['previsto']`, `pv=curva_s[-1].acumulado`, `avanco_fisico`), e devolve `jsonify` com floats (helper `_to_float` recursivo sobre `Decimal`). Guard `_check_v2()` + `_admin_id()` como na rota existente. Rodar o teste → PASS.

- [ ] **Step 5: Commit** `feat(ff): rota /dados consolida KPIs + séries (caixa, EVM, curva)`.

### Task 13: Template — KPIs + Curva S física × financeira (Chart.js)

**Files:** Modify `templates/cronograma/fisico_financeiro.html`; Create `static/js/fisico_financeiro_charts.js`.

- [ ] Adicionar cartões de KPI (venda, custo, lucro projetado + %, desembolso Veks, fat direto, recebido) lendo de `dados`/`/dados`.
- [ ] Incluir `<canvas id="curvaS">` + script que faz `fetch('…/dados')` e desenha duas linhas (física × financeira) com Chart.js (`static/js/vendor/chart.js`).
- [ ] Smoke Playwright existente (`tests/test_browser_all_modules.py`) continua passando; estender a asserção para conferir presença de `id="curvaS"`.
- [ ] Commit `feat(ff-ui): KPIs + Curva S física×financeira (Chart.js)`.

### Task 14: Template — custo por etapa (barra empilhada Veks+Fat), SPI/CPI, fluxo de caixa, tabela de medições

**Files:** Modify `templates/cronograma/fisico_financeiro.html`, `static/js/fisico_financeiro_charts.js`.

- [ ] Barra empilhada por etapa (Veks + Fat direto); cartões SPI/CPI com cor (verde ≥0,95 / âmbar 0,85–0,95 / vermelho <0,85).
- [ ] Tabela de fluxo de caixa por mês (medição, fat direto, imposto, entrada líquida, desembolso, caixa do mês, acumulado).
- [ ] Tabela de medições (nº, data, %, valor, status).
- [ ] Item de navegação no padrão do menu (link para a página FF a partir dos detalhes da obra).
- [ ] Commit `feat(ff-ui): custo por etapa + SPI/CPI + fluxo de caixa + medições`.

### Task 15: Gate + smoke da Fase 3

- [ ] `bash run_tests.sh --gate` → 0 failed; `PW_BASE_URL=http://localhost:5000 python -m pytest tests/test_browser_all_modules.py -k fisico -m browser -q` → passa. Commit do status.

---

## Fase 4 — (Opcional/posterior) Edição (CRUD) e Gantt

> Esta fase altera a fonte de custo (abordagem B do design original) e deve ser **planejada em documento próprio** após a Fase 3 estabilizar. Resumo do escopo para o plano futuro:
- CRUD de itens/custo por etapa (POST/PUT/DELETE) recalculando via serviço; edição de datas/% das tarefas.
- Gantt/timeline a partir de `cronograma_tarefas` (lib de timeline ou Chart.js horizontal-bar).

---

## Riscos / decisões a confirmar com o usuário

1. **Mapeamento veks→mão de obra / fat→material** no `ObraServicoCusto` (Task 3): preserva os totais e o split Veks/Fat (o que o painel usa), mas rotula a categoria de forma aproximada. Se o usuário quiser o detalhamento item a item (`eap[].itens`), será preciso uma tabela de itens (sai da Abordagem A). **Recomendação:** manter o mapeamento agregado nesta entrega.
2. **Formato do arquivo de produção**: este plano usa o **JSON** (`cronograma_fisico_financeiro_baias.json`). Se a importação em produção precisar partir da planilha `Previsao_Cronograma_e_Orcamentos.xlsx`, adiciona-se um parser XLSX→mesmo dict (tarefa extra, mesma engine). **Recomendação:** padronizar no JSON (estável) e gerar o JSON a partir da planilha offline.
3. **`pct_fisico` em escala mista** no JSON (alguns 0-100, outros frações): a Task 3 trata `percentual_concluido` como percentual; conferir com um dado real de avanço.
4. **AC (custo realizado) mês a mês**: enquanto não houver lançamento faseado, `AC=PV` (CPI=SPI no início). Integração com `GestaoCustoFilho` faseado é trabalho futuro.

---

## Self-review (cobertura do escopo)

- Importador idempotente/tenant-scoped (obra+cliente+tarefas+IMC+links+OSC+medições): Tasks 1-4. ✅
- Import → página FF derivada pronta: Task 5. ✅
- Upload em produção: Task 6. ✅
- Fluxo de caixa (fat direto + imposto): Task 8. ✅
- EVM (PV/EV/AC/SPI/CPI) + Curva S física: Task 9. ✅
- KPIs (venda/custo/lucro/desembolso/fat/recebido): Task 10. ✅
- Dashboard (KPIs, Curva S física×financeira, custo por etapa, SPI/CPI, caixa, medições): Tasks 12-14. ✅
- Testes (unit do serviço com números do JSON; smoke; isolamento por `admin_id` nas queries): em todas as tasks. ✅
- Edição/Gantt: Fase 4 (plano próprio). ✅ (escopo separado, conforme YAGNI)
