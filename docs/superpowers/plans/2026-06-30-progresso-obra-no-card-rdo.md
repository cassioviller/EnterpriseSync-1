# Card de RDO mostra o progresso da OBRA — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corrigir `calcular_progresso_rdo` para que tarefas sem `quantidade_total` derivem o realizado do `percentual_realizado` do último apontamento — fazendo os cards de RDO exibirem o avanço real da obra (acumulado até a data do RDO) em vez de 0,0%.

**Architecture:** Mudança de uma função só (`utils/cronograma_engine.py::calcular_progresso_rdo`). A rota (`views/rdo.py`), o template (`rdo_lista_unificada.html`) e o agregador (`calcular_progresso_geral_obra_v2`) já consomem o valor corretamente — não mudam. A correção alinha esse motor com `sincronizar_percentuais_obra`, que já usa `percentual_realizado`.

**Tech Stack:** Flask + SQLAlchemy (Postgres), `pytest`. Sem migração.

## Global Constraints

- **Semântica:** cada card mostra o progresso **acumulado da obra até a data daquele RDO** (não o snapshot atual). É o que `calcular_progresso_geral_obra_v2(obra_id, data_relatorio, admin_id)` já calcula.
- **Inalterado para tarefas COM `quantidade_total`:** o caminho `acumulado / quantidade_total` segue idêntico. O fallback só atua quando `quantidade_total` é nulo/0.
- **Fonte do fallback:** último `RDOApontamentoCronograma.percentual_realizado` com `RDO.data_relatorio <= data_rdo`, ordenado por `data_relatorio` desc (mesma fonte que `sincronizar_percentuais_obra`).
- **Invariantes da Baia inalterados:** veks 800.960 / fat 550.775 / lucro 24.976 / imposto 128.903 / contrato 1.505.613,76 / data_fim 08/10.
- Suíte de regressão (rodar ao fim de cada task):
  ```
  python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q
  ```

---

## File Structure

| Arquivo | Responsabilidade | Mudança |
|---|---|---|
| `utils/cronograma_engine.py` (`calcular_progresso_rdo`, bloco "Realizado" ~l.425-433) | Calcula planejado/realizado de uma tarefa a uma data | **Modificar** — fallback p/ `percentual_realizado` sem `quantidade_total` |
| `tests/test_importacao_fisico_financeiro.py` | Testes do import/progresso (tem `_novo_admin` e acesso à fixture) | **Modificar** — unit do fallback + integração do progresso por data |

`views/rdo.py`, `templates/rdo_lista_unificada.html`, `calcular_progresso_geral_obra_v2`: **sem mudança**.

---

## Task 1: Fallback em `calcular_progresso_rdo` + testes

**Files:**
- Modify: `utils/cronograma_engine.py` (`calcular_progresso_rdo`, bloco "Realizado" ~l.425-433)
- Test: `tests/test_importacao_fisico_financeiro.py`

**Interfaces:**
- Consumes: `RDOApontamentoCronograma`, `RDO` (já importados na função); `_novo_admin()` e a fixture `tests/fixtures/cronograma_fisico_financeiro_baias.json` (já usada nos testes do arquivo).
- Produces: `calcular_progresso_rdo(tarefa_id, data_rdo, admin_id) -> {'percentual_planejado', 'percentual_realizado', 'quantidade_acumulada'}` — para tarefa sem `quantidade_total`, `percentual_realizado` passa a ser o do último apontamento até `data_rdo` (antes era sempre 0.0). `calcular_progresso_geral_obra_v2` (inalterada) passa a refletir esse valor.

- [ ] **Step 1: Write the failing tests**

Adicionar a `tests/test_importacao_fisico_financeiro.py`:

```python
def test_calcular_progresso_rdo_fallback_sem_quantidade_total():
    """Tarefa sem quantidade_total: realizado = percentual_realizado do último
    apontamento até a data (antes era sempre 0)."""
    import json, os
    from datetime import date
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from utils.cronograma_engine import calcular_progresso_rdo
    from models import TarefaCronograma
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        projetos = (TarefaCronograma.query
                    .filter_by(obra_id=oid, admin_id=aid)
                    .filter(TarefaCronograma.nome_tarefa.like('EXECUÇÃO DE PROJETOS%'))
                    .first())
        assert projetos is not None and not projetos.quantidade_total
        # antes do 1º apontamento (22/06) → 0
        r21 = calcular_progresso_rdo(projetos.id, date(2026, 6, 21), aid)
        assert r21['percentual_realizado'] == 0.0
        # 22/06 → 50 (primeiro apontamento); 27/06 → 65 (acumulado)
        assert calcular_progresso_rdo(projetos.id, date(2026, 6, 22), aid)['percentual_realizado'] == 50.0
        assert calcular_progresso_rdo(projetos.id, date(2026, 6, 27), aid)['percentual_realizado'] == 65.0


def test_progresso_geral_obra_cresce_por_data():
    """O progresso acumulado da obra (usado nos cards de RDO) é > 0 e cresce de
    22/06 para 27/06."""
    import json, os
    from datetime import date
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from utils.cronograma_engine import calcular_progresso_geral_obra_v2
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        oid = importar_fisico_financeiro(json.load(open(caminho, encoding='utf-8')), aid)['obra_id']
        p22 = calcular_progresso_geral_obra_v2(oid, date(2026, 6, 22), aid)['progresso_geral_pct']
        p27 = calcular_progresso_geral_obra_v2(oid, date(2026, 6, 27), aid)['progresso_geral_pct']
        assert 0 < p22 < p27 < 100
```

- [ ] **Step 2: Run them — expect FAIL**

Run: `python -m pytest tests/test_importacao_fisico_financeiro.py::test_calcular_progresso_rdo_fallback_sem_quantidade_total tests/test_importacao_fisico_financeiro.py::test_progresso_geral_obra_cresce_por_data -v`
Expected: FAIL — `percentual_realizado` volta 0.0 (sem `quantidade_total`) e `progresso_geral_pct` é 0 nas duas datas.

- [ ] **Step 3: Implementar o fallback**

Em `utils/cronograma_engine.py`, dentro de `calcular_progresso_rdo`, substituir o bloco de "Realizado" (hoje):

```python
    perc_realizado = 0.0
    if tarefa.quantidade_total and tarefa.quantidade_total > 0:
        perc_realizado = min(100.0, round(acumulado / tarefa.quantidade_total * 100, 2))

    return {
        'percentual_planejado': perc_planejado,
        'percentual_realizado': perc_realizado,
        'quantidade_acumulada': acumulado,
    }
```

por:

```python
    perc_realizado = 0.0
    if tarefa.quantidade_total and tarefa.quantidade_total > 0:
        perc_realizado = min(100.0, round(acumulado / tarefa.quantidade_total * 100, 2))
    else:
        # Tarefa sem quantidade física: o avanço é o percentual_realizado do
        # ÚLTIMO apontamento até data_rdo (mesma fonte que
        # sincronizar_percentuais_obra). Antes esse caso devolvia sempre 0.
        ultimo = (
            db.session.query(RDOApontamentoCronograma.percentual_realizado)
            .join(RDO, RDO.id == RDOApontamentoCronograma.rdo_id)
            .filter(
                RDOApontamentoCronograma.tarefa_cronograma_id == tarefa_id,
                RDOApontamentoCronograma.admin_id == admin_id,
                RDO.data_relatorio <= data_rdo,
            )
            .order_by(RDO.data_relatorio.desc())
            .first()
        )
        if ultimo is not None and ultimo[0] is not None:
            perc_realizado = min(100.0, float(ultimo[0]))
            if acumulado <= 0:
                # sinaliza apontamento p/ n_tarefas_apontadas em
                # calcular_progresso_geral_obra_v2 (testa quantidade_acumulada > 0)
                acumulado = perc_realizado

    return {
        'percentual_planejado': perc_planejado,
        'percentual_realizado': perc_realizado,
        'quantidade_acumulada': acumulado,
    }
```

(`RDOApontamentoCronograma` e `RDO` já estão importados nesse escopo da função.)

- [ ] **Step 4: Run them — expect PASS**

Run: `python -m pytest tests/test_importacao_fisico_financeiro.py::test_calcular_progresso_rdo_fallback_sem_quantidade_total tests/test_importacao_fisico_financeiro.py::test_progresso_geral_obra_cresce_por_data -v`
Expected: PASS.

- [ ] **Step 5: Suíte de regressão**

Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: verde; invariantes da Baia preservados.

- [ ] **Step 6: Commit**

```bash
git add utils/cronograma_engine.py tests/test_importacao_fisico_financeiro.py
git commit -m "fix(baia): card de RDO mostra progresso da obra (fallback p/ percentual_realizado sem quantidade_total)"
```

---

## Task 2: Verificação no browser + fechamento

**Files:**
- (sem código novo)

- [ ] **Step 1: App importa**

Run: `python -c "from app import app; print('app import ok')"`
Expected: `app import ok`.

- [ ] **Step 2: Verificar os cards no browser real**

Subir a app (`gunicorn --bind 0.0.0.0:5000 --workers 1 --timeout 120 main:app`). Logar como
`admin@construtoraalfa.com.br` / `Alfa@2026` (chromium do Nix via
`$REPLIT_PLAYWRIGHT_CHROMIUM_EXECUTABLE`). Reimportar a Baia (Importação → Físico-Financeiro,
a fixture `cronograma_fisico_financeiro_baias.json`). Abrir `/rdo/lista?obra_id=<id>` e conferir:
1. Os 6 cards (22→27/06) mostram **Progresso Geral > 0%** (não mais 0,0%).
2. O valor **cresce** do card de 22/06 para o de 27/06 (acumulado até a data).

- [ ] **Step 3: Atualizar o handoff**

Em `ESTADO_ATUALIZACAO_BAIA.md`, registrar (1-2 linhas) que o card de RDO passou a exibir o
progresso acumulado da obra (correção em `calcular_progresso_rdo`), e que as tarefas não citadas no
relatório estão em 0% (confirmado: 51 de 56).

```bash
git add ESTADO_ATUALIZACAO_BAIA.md
git commit -m "docs(baia): card de RDO exibe progresso da obra; 51/56 tarefas em 0% confirmado"
```

---

## Sequência de dependências

```
T1 (fallback + testes) → T2 (verificação + fechamento)
```

## Rollback

Task isolada num commit. Reverter T1 volta `calcular_progresso_rdo` ao comportamento anterior
(card 0,0%) sem afetar nada além do progresso exibido. Sem migração.

---

## Self-Review

**1. Spec coverage**

| Requisito da spec | Task |
|---|---|
| Fallback em `calcular_progresso_rdo` (sem `quantidade_total` → `percentual_realizado` do último apontamento ≤ data) | T1 Step 3 |
| Filtro por data (`RDO.data_relatorio <= data_rdo`, ordenado desc) preserva "acumulado até a data" | T1 Step 3 |
| Tarefas com `quantidade_total` inalteradas | T1 Step 3 (ramo `if` intacto) |
| `n_tarefas_apontadas` correto (proxy em `quantidade_acumulada`) | T1 Step 3 |
| Card mostra progresso da obra crescente por data | T1 Step 1 (integração) + T2 Step 2 (browser) |
| Sem mudança em rota/template/agregador | (nenhuma task os toca) |
| Invariantes da Baia preservados | T1 Step 5 |
| Parte 1 (51/56 em 0%) registrada | T2 Step 3 |

**2. Placeholder scan** — sem TBD/TODO; o código do fallback está completo; comandos com expected output. Verificação de UI é manual (T2), padrão das rodadas anteriores.

**3. Type consistency** —
- `calcular_progresso_rdo(tarefa_id, data_rdo, admin_id) -> dict` com chaves `percentual_planejado`/`percentual_realizado`/`quantidade_acumulada` — assinatura e retorno inalterados; só o valor de `percentual_realizado` muda no ramo sem `quantidade_total`.
- `calcular_progresso_geral_obra_v2(obra_id, data_ref, admin_id) -> {'progresso_geral_pct', ...}` consumida nos testes de T1 com os mesmos nomes da função existente.
- `RDOApontamentoCronograma.percentual_realizado` (float) e `RDO.data_relatorio` (date) — campos reais usados na query do fallback.
</content>
