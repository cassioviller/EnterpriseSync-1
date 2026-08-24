# RDO em Rascunho Não Move o Cronograma — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fechar a última metade do trabalho de 21/08. O custo de mão de obra
já parou de vazar de RDO em rascunho; o **avanço físico** não. Hoje um RDO que
ninguém submeteu move o percentual do cronograma, a curva S e o físico-financeiro.

**Architecture:** A guarda de estado existe e é boa —
`services/rdo_ciclo_vida.publica_custos()` (`:141`) barra o evento
`rdo_finalizado` para RDO em rascunho. O que ficou de fora dela é o percentual:
`utils/cronograma_engine.atualizar_percentual_tarefa()` (`:1412`) deriva o
avanço de `RDOApontamentoCronograma` com `join(RDO)` **sem filtrar
`RDO.estado`**, e é chamada direto pelas rotas de salvar, fora do guarda. Este
plano trata a query como a origem (fix na fonte, não no chamador) e paga o
preço que isso cobra: como a única escrita de percentual acontece no salvar,
filtrar rascunho **sem** recalcular no Submeter faria o avanço parar de
funcionar em silêncio.

**Tech Stack:** Python 3, Flask, SQLAlchemy, PostgreSQL, pytest.

**Spec:** Não há spec escrito. Nasce do resíduo registrado em
`docs/planos-em-aberto-2026-08-23.md` seção 6, medido em 24/08.

---

## Investigação — o que foi medido em 24/08, não suposto

🔬 **A causa raiz é a query, não o chamador.** `atualizar_percentual_tarefa`
(`utils/cronograma_engine.py:1412`) monta:

```python
.join(RDO, RDO.id == RDOApontamentoCronograma.rdo_id)
.filter(RDOApontamentoCronograma.tarefa_cronograma_id == tarefa_id,
        RDOApontamentoCronograma.admin_id == admin_id)
```

Sem `RDO.estado`. Corrigir só os 5 pontos de chamada
(`views/rdo.py:585,988,4418`; `cronograma_views.py:2871,2959`) deixaria
qualquer recálculo futuro reintroduzir o avanço do rascunho.

🔬 **O experimento.** Acrescentar `RDO.estado != 'rascunho'` ao filtro e rodar
6 arquivos de teste expostos: **15 failed, 60 passed** (23,6s).

🔬 **As 15 falhas são dívida de fixture, não contradição semântica.** Os testes
criam `RDO(..., status='Finalizado')` e **não setam `estado`** — a coluna nasceu
na Fase 5 com default `'rascunho'`, e as fixturas anteriores nunca foram
atualizadas. Elas *querem dizer* "RDO submetido"; dizem "rascunho".
**Prova:** uma linha (`estado='preenchido'`) em `tests/test_rdo_recomputo_cadeia.py:60`
levou aquele arquivo de 2 falhas para **8 passed**.

🔴 **O achado que impede o fix ingênuo.** 🔬 Nenhum dos dois handlers de
`rdo_finalizado` (`event_manager.py:662` lança custo, `:1731` recalcula
medição) toca em percentual de cronograma, e
`services/rdo_ciclo_vida.transicionar()` (`:181`) também não. A **única**
escrita de `percentual_concluido` acontece no salvar — enquanto o RDO ainda é
rascunho. Filtrar rascunho sem acrescentar recálculo no Submeter **não deixa o
avanço mais correto: deixa o avanço morto**, sem erro em log.

🔬 **O retificador nasce em rascunho** (`services/rdo_assinatura.py:176`). Por
isso o filtro exclui **só** `rascunho` e **não mexe** em `retificado` — o
desempate estável por `data_relatorio desc, id desc` já prefere o retificador
sobre o original. Mudar a semântica de `retificado` é decisão separada.

---

## DECISÃO DO DONO — ler antes da Task 1

O fix tem uma consequência visível, e ela não é minha para tomar:

**Depois dele, apontar produção pela grade do cronograma não move mais o
percentual até alguém clicar Submeter.** Hoje move na hora. O Alan vai apontar
e ver a barra parada até fechar o dia.

Isso é **exatamente** o que a norma do RDO (capítulo 23a, §7 e motivo de
devolução nº 6) já promete por escrito: rascunho não conta. Mas é mudança de
comportamento no meio da frente que vai ser apresentada ao Guilherme.

- **Se vale**: executar como está escrito.
- **Se não vale agora**: não execute nada. O capítulo 23a **já não promete** o
  contrário (foi reescrito em `e4449443` justamente para não mentir), então o
  custo de adiar é zero em documentação — o sistema fica incoerente com a norma,
  não a norma com o sistema.

---

## Global Constraints

- Sem migration: nenhuma coluna nova. `RDO.estado` existe desde a migration 260.
- Toda query filtra por `admin_id` (convenção de tenancy).
- Testes em `tests/`, `pytestmark = pytest.mark.integration`. Rodar: `python -m pytest tests/<arquivo>.py -v`
- Commits em português: `fix(cronograma):`, `test(cronograma):`.
- **Não** tocar em `RDO.status` — ≥9 consumidores filtram por `'Finalizado'`
  (a lista está no cabeçalho de `services/rdo_ciclo_vida.py`).

---

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `utils/cronograma_engine.py` (modificar, `atualizar_percentual_tarefa` ~1440) | O filtro `RDO.estado != RASCUNHO` na query. Origem única. |
| `utils/cronograma_engine.py` (modificar, `_atualizar_percentual_sem_commit` ~413) | Mesmo filtro, se ela repetir a query. **Conferir antes de escrever.** |
| `views/rdo.py` (modificar, ~1711, rota de submeter) | Recalcular as tarefas do RDO depois de `transicionar(rdo, PREENCHIDO)`. |
| `views/rdo.py` (modificar, ~1895, rota de reabrir) | Simétrico: ao voltar para rascunho, o avanço daquele RDO sai. |
| `tests/test_rascunho_nao_move_cronograma.py` (criar) | A guarda: rascunho não move, Submeter move, Reabrir tira. |
| ~30 arquivos em `tests/` (modificar fixtures) | `estado='preenchido'` onde a fixture quer dizer "RDO submetido". |

---

### Task 1: O teste que falha — rascunho não move, Submeter move

- [ ] **Step 1: Escrever `tests/test_rascunho_nao_move_cronograma.py`**

Três casos, um por comportamento:
1. RDO em `rascunho` com apontamento de 50% ⇒ `percentual_concluido` fica em 0.
2. O mesmo RDO submetido (`transicionar(rdo, PREENCHIDO)` + a rota) ⇒ vai a 50%.
3. Reabrir (`PREENCHIDO → RASCUNHO`) ⇒ volta a 0.

Reaproveitar as fixtures de `tests/test_rdo_recomputo_cadeia.py` (`_rdo`,
`_tarefa`) — não criar helper novo de ambiente.

- [ ] **Step 2: Rodar e confirmar que 1 e 3 falham e 2 passa**

O caso 2 passa hoje por acidente (rascunho já move). Ele existe para pegar a
regressão do Step seguinte, que é o risco real deste plano.

### Task 2: O filtro na origem

- [ ] **Step 1: Acrescentar `RDO.estado != RASCUNHO` à query**

Importar de `services.rdo_ciclo_vida`, não escrever a string solta — o módulo é
o dono dos estados.

- [ ] **Step 2: Conferir `_atualizar_percentual_sem_commit` (`:413`)**

Se ela repete a query, aplicar o mesmo filtro. Se delega, não duplicar.

- [ ] **Step 3: Rodar o teste da Task 1** — casos 1 e 3 passam; o caso 2 **deve quebrar**.

Se o caso 2 continuar verde, pare: significa que existe outro escritor de
percentual que esta investigação não achou, e o mapa está errado.

### Task 3: Recalcular no Submeter e no Reabrir

- [ ] **Step 1: Depois de `transicionar(rdo, PREENCHIDO)` (`views/rdo.py:1711`), recalcular**

As tarefas alcançadas saem de `RDOApontamentoCronograma.filter_by(rdo_id=rdo.id)`
— mesmo padrão que a exclusão de RDO já usa (`views/rdo.py:558-562`). Fora da
transação de estado, como o comentário de `:577` justifica.

- [ ] **Step 2: Simétrico em `reabrir` (`views/rdo.py:1895`)**
- [ ] **Step 3: Rodar o teste da Task 1** — os três casos verdes.

### Task 4: Pagar a dívida de fixture

- [ ] **Step 1: Rodar a suíte inteira e listar as falhas**

`bash run_tests.sh` (gate de referência: 2560 passed, 6 skipped, 2 xfailed).

- [ ] **Step 2: Para cada falha, decidir caso a caso**

Regra: se a fixture cria RDO com `status='Finalizado'` e espera avanço, ela quer
dizer **submetido** ⇒ `estado='preenchido'`. Se o teste é sobre rascunho, o
valor esperado é que mudou ⇒ ajustar o assert, não a fixture.
**Não** aplicar `sed` em massa: a distinção acima é a razão de o plano existir.

- [ ] **Step 3: Gate verde** e commit.

### Task 5: Fechar o resíduo na documentação

- [ ] **Step 1: `docs/planos-em-aberto-2026-08-23.md` seção 6** — riscar a linha do resíduo.
- [ ] **Step 2: `ESTADO-ATUAL.md`** — registrar com a prova.
- [ ] **Step 3: Capítulo 23a** — hoje ele descreve o comportamento **desejado**;
      conferir se alguma frase precisa deixar de ser aspiracional. Se nada mudar,
      registrar que foi conferido.
