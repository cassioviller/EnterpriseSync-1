# Rollup de Percentual do Cronograma — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o percentual do grupo (tarefa resumo) reagir de forma correta e previsível quando tarefas novas são inseridas no meio da fase.

**Architecture:** O percentual do pai já é recalculado — `services/cronograma_scheduler.recalcular_obra()` chama `utils.cronograma_engine.rollup_percentual_pos_recalculo()` em **todos** os caminhos de criação de tarefa (o posicionado, via `_aplicar_hierarquia`, e o de anexar-no-fim). O que este plano ataca é (a) pinar em teste o que o rollup de fato produz no cenário relatado, e (b) alinhar a ordem de processamento dos pais com a função irmã `rollup_realizado`, que já documenta a heurística por `ordem` como falha silenciosa.

**Tech Stack:** Python 3, Flask, SQLAlchemy, PostgreSQL, pytest (`pytest.mark.integration`).

**Spec:** Não há spec escrito. Este plano nasce da sessão de brainstorming de 2026-08-20 (reunião com o Paulo). O critério de aceite verbal foi: "inseri 5 itens zerados numa fase que estava em 98% e ela tinha que cair para ~80%".


## Estado — 2026-08-21

Tasks 1 e 2 **executadas e mescladas no `main`** (resgatadas da branch
`sdd/reuniao-20-08`, que ficou fora do merge do dia 20). A Task 3 **não tem
checkbox de propósito**: ela continua BLOQUEADA na decisão do Paulo sobre qual
fórmula vale — não confunda "0 pendentes" com plano concluído.

## Global Constraints

- Python/Flask/SQLAlchemy; PostgreSQL. Sem ORM novo, sem lib nova.
- Testes em `tests/`, nome `test_*.py`, marcados `pytestmark = pytest.mark.integration`.
- Fixtures reaproveitam `tests/test_cronograma_versao_service._ambiente` e `._tarefa` — não criar helper novo de ambiente.
- Requests de test client ficam **fora** de `app_context` aberto (Flask-Login cacheia `g._login_user`).
- Rodar teste: `python -m pytest tests/<arquivo>.py -v`
- Commits em português, prefixo `fix(cronograma):` / `test(cronograma):`.

## DECISÃO PENDENTE — ler antes da Task 3

A fórmula do rollup hoje é **média ponderada pela duração das filhas**
(`utils/cronograma_engine.py:610`, e a gêmea `rollup_realizado` em `:1010`).
Com ela, 5 tarefas novas de 1 dia cada, inseridas numa fase cujas tarefas
somam ~300 dias, movem o pai de 98% para ~96% — **não** para 80%.

Para o pai cair para ~80% a regra teria de ser **média simples por
quantidade de itens**. Essa troca muda número em cascata: curva S, EVM
(`bac` congelado na baseline), medição e o físico-financeiro. **Não execute
a Task 3 sem confirmação explícita do Paulo sobre qual das duas regras vale.**
As Tasks 1 e 2 valem nas duas hipóteses e podem ser executadas já.

---

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `tests/test_cronograma_rollup_insercao.py` (criar) | Pina o comportamento do rollup ao inserir tarefa: o número que o pai assume, e a ordem de processamento em árvore de 3 níveis. |
| `utils/cronograma_engine.py` (modificar, `rollup_percentual_pos_recalculo`, linhas 584-613) | Trocar a ordenação dos pais de `ordem` decrescente para profundidade decrescente, igual à gêmea `rollup_realizado`. |

---

### Task 1: Caracterizar o rollup na inserção de tarefa

Este teste **não corrige nada**. Ele grava em código o que o sistema faz hoje,
para que a decisão de regra (ver "DECISÃO PENDENTE") seja tomada sobre número
medido e não sobre lembrança de reunião.

**Files:**
- Create: `tests/test_cronograma_rollup_insercao.py`
- Test: `tests/test_cronograma_rollup_insercao.py`

**Interfaces:**
- Consumes: `tests.test_cronograma_versao_service._ambiente() -> (Usuario, Obra)`, `._tarefa(obra, admin, nome, ordem=0, **kw) -> TarefaCronograma`; `services.cronograma_scheduler.recalcular_obra(obra_id, admin_id, *, cliente=False, commit=True) -> ResultadoAgendamento`.
- Produces: nada consumido por outras tasks — é teste de caracterização.

- [x] **Step 1: Escrever o teste de caracterização**

Criar `tests/test_cronograma_rollup_insercao.py` com este conteúdo:

**Ponto crítico do cenário:** `recalcular_obra` sincroniza TODA folha com o
último apontamento do RDO antes de agregar os pais, e folha sem apontamento é
**zerada** (`utils/cronograma_engine._atualizar_percentual_sem_commit:453`).
Gravar percentual direto na folha não sobrevive ao recálculo — por isso as
folhas "antigas" recebem apontamento de RDO de verdade, e as "novas" ficam sem,
que é exatamente o estado de uma tarefa recém-inserida.

```python
"""Caracterização do rollup de percentual quando entram tarefas novas.

Cenário relatado na reunião de 2026-08-20: uma fase em ~98% recebe 5
tarefas novas zeradas e o percentual do grupo quase não se move. Este
módulo NÃO corrige — ele mede, para que a escolha da fórmula (ponderada
por duração x média simples por item) seja feita sobre número real.
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import TarefaCronograma
from services.cronograma_scheduler import recalcular_obra
from test_cronograma_versao_service import (_ambiente, _rdo_com_apontamento,
                                            _tarefa)

pytestmark = pytest.mark.integration


def _folha(obra, admin, pai, nome, *, ordem, duracao, pct=None):
    """Folha sob `pai`. Com `pct`, ganha apontamento de RDO nesse percentual.

    Sem `quantidade_total`, o engine lê `percentual_realizado` do apontamento
    direto — sem passar pela divisão quantidade/total.
    """
    t = _tarefa(obra, admin, nome, ordem=ordem,
                duracao_dias=duracao,
                data_inicio=date(2026, 7, 1),
                data_fim=date(2026, 7, 1),
                tarefa_pai_id=pai.id)
    if pct is not None:
        _rdo_com_apontamento(obra, admin, t, acumulada=pct, pct=pct)
    return t


def _fase_com_filhas(pcts_e_duracoes):
    """Obra com um pai 'Primeira Fase' e uma folha por par (pct, duracao).

    `pct=None` = folha recém-inserida, sem apontamento — o engine a lê como 0.
    Devolve (admin_id, obra_id, pai_id).
    """
    with app.app_context():
        admin, obra = _ambiente()
        pai = _tarefa(obra, admin, 'Primeira Fase', ordem=0,
                      duracao_dias=1, data_inicio=date(2026, 7, 1),
                      data_fim=date(2026, 7, 1))
        for i, (pct, dur) in enumerate(pcts_e_duracoes, start=1):
            _folha(obra, admin, pai, f'Item {i}',
                   ordem=i, duracao=dur, pct=pct)
        return admin.id, obra.id, pai.id


def _pct_do_pai(pai_id):
    with app.app_context():
        return TarefaCronograma.query.get(pai_id).percentual_concluido


def test_rollup_pondera_por_duracao_e_nao_por_contagem():
    """20 itens de 15 dias em 98% + 5 itens novos de 1 dia sem apontamento.

    Ponderado por duração: 98 * 300 / 305 = 96.39.
    Média simples por item seria 98 * 20 / 25 = 78.40.
    Este assert grava QUAL das duas está em vigor.
    """
    admin_id, obra_id, pai_id = _fase_com_filhas(
        [(98.0, 15)] * 20 + [(None, 1)] * 5)

    with app.app_context():
        recalcular_obra(obra_id, admin_id, cliente=False, commit=True)

    assert _pct_do_pai(pai_id) == pytest.approx(96.39, abs=0.01)


def test_rollup_roda_no_caminho_de_insercao():
    """Inserir uma folha sem apontamento num pai que estava em 100%.

    Prova que o rollup NÃO deixa de rodar na criação — a suspeita inicial
    da reunião. Duas folhas de 5 dias: uma em 100%, a nova em 0% ⇒ 50%.
    """
    admin_id, obra_id, pai_id = _fase_com_filhas([(100.0, 5)])

    with app.app_context():
        recalcular_obra(obra_id, admin_id, cliente=False, commit=True)
    assert _pct_do_pai(pai_id) == pytest.approx(100.0, abs=0.01)

    with app.app_context():
        # `ordem = max + 1` é o que o caminho "anexar no fim" de
        # `criar_tarefa` grava numa filha (cronograma_views.py:676).
        db.session.add(TarefaCronograma(
            obra_id=obra_id, admin_id=admin_id, nome_tarefa='Item novo',
            ordem=99, duracao_dias=5,
            data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 5),
            tarefa_pai_id=pai_id, percentual_concluido=0.0, is_cliente=False))
        db.session.commit()
        recalcular_obra(obra_id, admin_id, cliente=False, commit=True)

    assert _pct_do_pai(pai_id) == pytest.approx(50.0, abs=0.01)
```

- [x] **Step 2: Rodar os dois testes**

Run: `python -m pytest tests/test_cronograma_rollup_insercao.py -v`

Esperado: **os dois PASSAM.** São testes de caracterização — passar significa
que a medição está registrada.

Se `test_rollup_pondera_por_duracao_e_nao_por_contagem` **falhar** com valor
próximo de `78.40`, a fórmula em vigor já é média simples por item; nesse caso
troque o valor esperado para `78.40`, ajuste a docstring e **registre isso na
resposta ao Paulo** — muda a decisão pendente.

Se `test_rollup_roda_no_caminho_de_insercao` falhar (pai continua em 100%),
o rollup realmente não roda na inserção e este plano precisa de uma task nova
antes da Task 2 — pare e reporte.

- [x] **Step 3: Commit**

```bash
git add tests/test_cronograma_rollup_insercao.py
git commit -m "test(cronograma): caracterizar o rollup de percentual na insercao de tarefa"
```

---

### Task 2: Ordenar os pais por profundidade, não por `ordem`

`rollup_percentual_pos_recalculo` processa os pais com
`sorted(pais, key=lambda t: t.ordem, reverse=True)`. A função gêmea
`rollup_realizado` (mesmo arquivo, linha 1010) documenta essa heurística como
falha silenciosa e usa **profundidade real na árvore**. Um pai intermediário
precisa ser calculado antes do pai acima dele; com `ordem` isso só funciona
enquanto a numeração for pré-ordem DFS — e o caminho "anexar no fim" de
`criar_tarefa` (`cronograma_views.py:676`) grava `ordem = max + 1` numa filha,
quebrando exatamente essa premissa.

**Files:**
- Modify: `utils/cronograma_engine.py:584-613` (`rollup_percentual_pos_recalculo`)
- Test: `tests/test_cronograma_rollup_insercao.py`

**Interfaces:**
- Consumes: nada de tasks anteriores além do arquivo de teste criado na Task 1.
- Produces: `rollup_percentual_pos_recalculo(tarefas: list, pai_ids: set, admin_id: int) -> None` — assinatura **inalterada**. Chamadores existentes (`services/cronograma_scheduler.recalcular_obra:614`, `utils/cronograma_engine.recalcular_cronograma`) não mudam.

- [x] **Step 1: Escrever o teste que falha**

Acrescentar ao fim de `tests/test_cronograma_rollup_insercao.py`:

```python
def test_rollup_agrega_avo_a_partir_do_pai_ja_agregado():
    """Árvore de 3 níveis com `ordem` que NÃO acompanha a profundidade.

    Raiz(ordem=90) → Sub(ordem=10) → duas folhas, uma em 100% e outra sem
    apontamento. A Sub tem de virar 50% ANTES de a Raiz ler a Sub. Com
    ordenação por `ordem` decrescente a Raiz (90) é processada primeiro,
    lê a Sub ainda em 0 e grava 0.
    """
    with app.app_context():
        admin, obra = _ambiente()
        raiz = _tarefa(obra, admin, 'Raiz', ordem=90, duracao_dias=1,
                       data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 1))
        sub = _tarefa(obra, admin, 'Sub', ordem=10, duracao_dias=1,
                      data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 1),
                      tarefa_pai_id=raiz.id)
        _folha(obra, admin, sub, 'Folha A', ordem=11, duracao=5, pct=100.0)
        _folha(obra, admin, sub, 'Folha B', ordem=12, duracao=5, pct=None)
        admin_id, obra_id = admin.id, obra.id
        raiz_id, sub_id = raiz.id, sub.id

    with app.app_context():
        recalcular_obra(obra_id, admin_id, cliente=False, commit=True)

    assert _pct_do_pai(sub_id) == pytest.approx(50.0, abs=0.01)
    # A Raiz tem UMA filha (Sub, duracao 1) já em 50% ⇒ 50%.
    assert _pct_do_pai(raiz_id) == pytest.approx(50.0, abs=0.01)
```

- [x] **Step 2: Rodar para confirmar que falha**

Run: `python -m pytest tests/test_cronograma_rollup_insercao.py::test_rollup_agrega_avo_a_partir_do_pai_ja_agregado -v`

Esperado: **FAIL** no segundo assert, com `0.0 != 50.0 ± 0.01` (a Raiz foi
calculada antes da Sub).

- [x] **Step 3: Trocar a ordenação por profundidade**

Em `utils/cronograma_engine.py`, dentro de `rollup_percentual_pos_recalculo`,
substituir o bloco:

```python
    # Bottom-up: % dos pais calculado a partir dos filhos (média ponderada por duração)
    pais = [t for t in tarefas if t.id in pai_ids]
    for pai in sorted(pais, key=lambda t: t.ordem, reverse=True):
        filhas = [t for t in tarefas if t.tarefa_pai_id == pai.id]
        if not filhas:
            continue
        total_dur = sum(max(f.duracao_dias or 1, 1) for f in filhas)
        if total_dur > 0:
            pai.percentual_concluido = round(
                sum((f.percentual_concluido or 0) * max(f.duracao_dias or 1, 1) for f in filhas) / total_dur, 2
            )
```

por:

```python
    # Bottom-up: % dos pais calculado a partir dos filhos (média ponderada por
    # duração). A ordem de processamento é por PROFUNDIDADE decrescente, não
    # por `ordem` — mesma correção que `rollup_realizado` (abaixo) já carrega.
    # `ordem` só coincide com profundidade enquanto a numeração for pré-ordem
    # DFS, e o caminho "anexar no fim" de `criar_tarefa` grava `ordem = max+1`
    # numa FILHA, quebrando a premissa: o pai acima seria calculado antes do
    # subgrupo e leria 0 em vez do agregado.
    por_id = {t.id: t for t in tarefas}
    filhas_por_pai: dict = {}
    for t in tarefas:
        if t.tarefa_pai_id:
            filhas_por_pai.setdefault(t.tarefa_pai_id, []).append(t)

    def _profundidade(tarefa_id) -> int:
        """Distância até a raiz. Defensivo contra ciclo e pai órfão."""
        nivel, visto, atual = 0, {tarefa_id}, por_id.get(tarefa_id)
        while atual is not None and atual.tarefa_pai_id:
            pai_id = atual.tarefa_pai_id
            if pai_id in visto:  # ciclo: para de subir
                break
            visto.add(pai_id)
            nivel += 1
            atual = por_id.get(pai_id)
        return nivel

    pais = [t for t in tarefas if t.id in pai_ids]
    for pai in sorted(pais, key=lambda t: _profundidade(t.id), reverse=True):
        filhas = filhas_por_pai.get(pai.id, [])
        if not filhas:
            continue
        total_dur = sum(max(f.duracao_dias or 1, 1) for f in filhas)
        if total_dur > 0:
            pai.percentual_concluido = round(
                sum((f.percentual_concluido or 0) * max(f.duracao_dias or 1, 1)
                    for f in filhas) / total_dur, 2
            )
```

- [x] **Step 4: Rodar o teste novo**

Run: `python -m pytest tests/test_cronograma_rollup_insercao.py -v`

Esperado: **os 3 testes PASSAM.**

- [x] **Step 5: Rodar a suíte de cronograma inteira (regressão)**

Run: `python -m pytest tests/test_cronograma_scheduler.py tests/test_cronograma_engine_unificado.py tests/test_cronograma_metricas.py tests/test_a19_progresso_v1_convergencia.py tests/test_a19_progresso_v1_ponto_unico.py -v`

Esperado: **todos PASSAM.** Qualquer falha aqui é regressão introduzida pelo
Step 3 — corrigir antes de commitar, não seguir em frente.

- [x] **Step 6: Commit**

```bash
git add utils/cronograma_engine.py tests/test_cronograma_rollup_insercao.py
git commit -m "fix(cronograma): rollup dos pais por profundidade, nao por ordem"
```

---

### Task 3: BLOQUEADA — troca da fórmula para média simples por item

**Não execute sem a confirmação descrita em "DECISÃO PENDENTE".**

Se o Paulo confirmar que o percentual do grupo deve ser **média simples por
quantidade de itens** (98% com 20 itens + 5 itens zerados ⇒ 78,4%), a mudança é
trocar o peso `max(f.duracao_dias or 1, 1)` por `1` nas DUAS funções
(`rollup_percentual_pos_recalculo` e `rollup_realizado`) e atualizar o valor
esperado em `test_rollup_pondera_por_duracao_e_nao_por_contagem` para `78.40`,
renomeando o teste para `test_rollup_media_simples_por_item`.

Antes de executar, mapear o impacto em: `services/cronograma_fisico_financeiro.py`,
`services/medicao_service.py`, `services/cronograma_pdf.py` e o `bac` congelado
em `CronogramaBaseline` — todos leem percentual de pai.
