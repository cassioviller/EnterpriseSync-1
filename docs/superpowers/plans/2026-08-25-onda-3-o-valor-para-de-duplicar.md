# Onda 3 — O Valor Para de Duplicar ou Sumir Implementation Plan

> **Estado em 2026-08-25 (varredura de fecho):** 🟡 **ABERTO — pronto para executar** — 10 tasks. Fecha a automação **A12** do backlog. O 16º achado da onda (`financeiro_service.py:619`) **não está aqui** — espera a decisão D2.
>
> Escrito na varredura de 25/08. Índice de estado de todos os planos e specs em
> `docs/planos-em-aberto-2026-08-25.md`.


> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) ou superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer com que uma unidade de estoque saia uma vez só, um passivo não encolha sozinho, e a folha não seja lançada duas nem três vezes — fechando os 16 achados em que o sistema conta o mesmo valor mais de uma vez ou o perde de vista.

**Architecture:** Três grupos com três disciplinas diferentes. **(a) Estoque:** existe uma coluna que a saída valida (`quantidade_disponivel`) e que metade dos caminhos de escrita não mantém; a correção é fazer todos manterem, num único ponto de escrita. **(b) `GestaoCustoPai`×filhos:** a disciplina correta já está escrita em `transporte_views.py:565-579`, com o comentário explicando por que se conta filho em vez de somar valor — reembolso e a migração de contas a pagar não a seguem. **(c) Folha, ponto e compras:** cada um é um defeito próprio de dupla contagem, sem raiz comum.

**Tech Stack:** Flask, SQLAlchemy 2.0.41, PostgreSQL, pytest.

**Spec:** `docs/superpowers/plans/2026-08-25-fecho-dos-114-achados.md` (Onda 3) — evidência em `docs/auditoria/achados-code-review-2026-08-25.md` §5, §2, §8, §9.

## Global Constraints

- **Um ponto de escrita por invariante.** `quantidade_disponivel` passa a ser mantida por uma função só; nenhum caminho novo escreve nela direto.
- **Contar filho, nunca somar valor**, para decidir se um `GestaoCustoPai` morre. 📖 A razão está escrita em `transporte_views.py:566-571`: soma zero **não** é ausência de filho — um estorno negativo ou um valor 0 zera a soma com filhos vivos, e `GestaoCustoPai.itens` é `cascade='all, delete-orphan'`.
- **Reprocessar é estornar e refazer, nunca apagar metade e recriar.**
- **TDD sem exceção**, com o RED citado no commit.
- **Nenhuma migration** salvo onde a task disser. Onde disser, confira o máximo do repo **no dia do commit** e numere em sequência real.
- **Gate ao fim:** `bash run_tests.sh --gate`. Régua: **2560 passed, 6 skipped, 201 deselected, 2 xfailed**.

---

## 🔴 Bloqueio: a Task 3.6 da spec não está aqui

📖 `financeiro_service.py:619` (a exclusão de gêmeos que faz obrigação evaporar
de `saidas_previstas`) **não** tem task neste plano. Ela depende da **decisão
D2**, que exige alterar `tests/test_b5_fluxo_gemeos_e_orfaos.py:100` — um teste
hoje verde que afirma o defeito como intencional.

**Quando D2 for decidida, ela vira um plano próprio de uma task.** Não a
encaixe aqui: misturar uma mudança de teste verde com quinze correções torna
impossível dizer, depois, o que quebrou o quê.

---

## File Structure

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `services/estoque_saldo.py` | **Criar** | Task 1 — o ponto único que mantém `quantidade`, `quantidade_inicial` e `quantidade_disponivel` juntas |
| `almoxarifado_utils.py` | Modificar `:645-690` | Task 1 — `apply_movimento_manual` passa a usar o ponto único |
| `views/almoxarifado/movimentos.py` | Modificar `:1045`, `:1066`, `:1330`, `:411`, `:455`, `:857` | Tasks 1-3 |
| `reembolso_views.py` | Modificar `:293`, `:330` | Task 4 |
| `gestao_custos_views.py` | Modificar `:1415`, `:1433` | Task 5 |
| `financeiro_service.py` | Modificar `:752` | Task 6 |
| `services/financeiro_compra.py` | Modificar `:433`, `:420`, `:566` | Task 7 |
| `folha_pagamento_views.py` | Modificar `:148` | Task 8 |
| `services/folha_service.py` | Modificar `:761`, `:1336`, `:1444` | Task 9 |
| `services/custo_funcionario_dia.py` | Modificar `:97` | Task 9 |
| `ponto_views.py` | Modificar `:1487`, `:2446` | Task 10 |
| `views/rdo.py` | Modificar `:2867`, `:1888` | Task 10 |
| `tests/test_onda3_valor_nao_duplica.py` | **Criar** | Todos os testes desta onda |

---

### Task 1: A unidade sai uma vez só

> 🔴 **O achado mais caro do almoxarifado.** 📖 A saída valida em
> `func.sum(quantidade_disponivel)` (`movimentos.py:597`), mas
> `apply_movimento_manual` (`almoxarifado_utils.py:645-690`) mantém **só**
> `estoque.quantidade`. Quebra nos dois sentidos:
>
> - ENTRADA manual de 100 cria lote com `quantidade_disponivel = NULL` → a
>   guarda de saída vê 0 e **recusa** material que existe.
> - SAÍDA manual zera `quantidade` e deixa `quantidade_disponivel` em 100 → **as
>   mesmas unidades saem de novo.**
>
> 🔬 O caminho de entrada por nota (`movimentos.py:400-406`) faz certo:
> `quantidade=1, quantidade_inicial=1, quantidade_disponivel=1`. É a prova de
> que a invariante existe e de que metade do código a ignora.

**Files:**
- Create: `services/estoque_saldo.py`
- Modify: `almoxarifado_utils.py:645-690`
- Test: `tests/test_onda3_valor_nao_duplica.py` (criar)

**Interfaces:**
- Consumes: `models.AlmoxarifadoEstoque`.
- Produces:
  - `criar_lote(item_id, quantidade, admin_id, **campos) -> AlmoxarifadoEstoque` — cria com as três colunas coerentes.
  - `creditar(estoque, quantidade) -> None` — soma em `quantidade` **e** `quantidade_disponivel`.
  - `debitar(estoque, quantidade) -> None` — subtrai das duas; levanta `SaldoInsuficiente` se faltar.
  - `class SaldoInsuficiente(ValueError)`

- [ ] **Step 1: Write the failing test**

Create `tests/test_onda3_valor_nao_duplica.py`:

```python
"""Onda 3 — o valor para de duplicar ou sumir.

O arreio de tenant é `tests/helpers_tenant.py`. Aqui o que se prova é
aritmética de saldo e disciplina de pai×filho, não isolamento.
"""
import os
import sys
import uuid
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from helpers_tenant import cliente_de, dois_tenants, um_tenant

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-onda3-valor'
    yield


def _item_consumivel(admin_id):
    from models import AlmoxarifadoItem
    suf = uuid.uuid4().hex[:8]
    item = AlmoxarifadoItem(
        admin_id=admin_id, nome=f'Cimento {suf}', codigo=f'CIM{suf}',
        tipo_controle='CONSUMIVEL', unidade_medida='SC',
        permite_devolucao=True)
    db.session.add(item)
    db.session.flush()
    return item


# ---------------------------------------------------------------------------
# Task 1 — a unidade sai uma vez só
# ---------------------------------------------------------------------------

def test_lote_novo_nasce_com_as_tres_colunas_coerentes():
    """🔴 A entrada manual criava lote com `quantidade_disponivel = NULL`.

    A saída valida em `func.sum(quantidade_disponivel)`
    (`movimentos.py:597`): com NULL, a guarda vê 0 e RECUSA material que
    existe.
    """
    from services.estoque_saldo import criar_lote

    with app.app_context():
        t = um_tenant('onda3_lote', com_fatos=False)
        item = _item_consumivel(t.admin_id)
        lote = criar_lote(item.id, Decimal('100'), t.admin_id)
        db.session.flush()

        assert lote.quantidade == Decimal('100')
        assert lote.quantidade_inicial == Decimal('100')
        assert lote.quantidade_disponivel == Decimal('100')


def test_debitar_baixa_as_duas_colunas_juntas():
    """🔴 A saída manual zerava `quantidade` e deixava `quantidade_disponivel`.

    As mesmas unidades saíam de novo.
    """
    from services.estoque_saldo import criar_lote, debitar

    with app.app_context():
        t = um_tenant('onda3_deb', com_fatos=False)
        item = _item_consumivel(t.admin_id)
        lote = criar_lote(item.id, Decimal('100'), t.admin_id)
        db.session.flush()

        debitar(lote, Decimal('40'))
        assert lote.quantidade == Decimal('60')
        assert lote.quantidade_disponivel == Decimal('60'), (
            'quantidade_disponivel ficou para trás — a unidade sairia de novo')
        # `quantidade_inicial` é histórico: não se mexe
        assert lote.quantidade_inicial == Decimal('100')


def test_debitar_alem_do_saldo_levanta():
    from services.estoque_saldo import SaldoInsuficiente, criar_lote, debitar

    with app.app_context():
        t = um_tenant('onda3_ins', com_fatos=False)
        item = _item_consumivel(t.admin_id)
        lote = criar_lote(item.id, Decimal('10'), t.admin_id)
        db.session.flush()
        with pytest.raises(SaldoInsuficiente):
            debitar(lote, Decimal('11'))


def test_creditar_sobe_as_duas():
    from services.estoque_saldo import creditar, criar_lote

    with app.app_context():
        t = um_tenant('onda3_cred', com_fatos=False)
        item = _item_consumivel(t.admin_id)
        lote = criar_lote(item.id, Decimal('10'), t.admin_id)
        db.session.flush()
        creditar(lote, Decimal('5'))
        assert lote.quantidade == Decimal('15')
        assert lote.quantidade_disponivel == Decimal('15')


def test_nenhum_caminho_cria_estoque_sem_quantidade_disponivel():
    """A guarda que impede o sexto caminho de nascer errado."""
    import inspect

    import almoxarifado_utils
    import views.almoxarifado.movimentos as mov

    for modulo in (almoxarifado_utils, mov):
        fonte = inspect.getsource(modulo)
        for bloco in fonte.split('AlmoxarifadoEstoque(')[1:]:
            corpo = bloco.split(')')[0]
            if 'quantidade=' in corpo:
                assert 'quantidade_disponivel' in corpo, (
                    f'{modulo.__name__}: lote criado sem quantidade_disponivel'
                    f' → {corpo[:200]}')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_onda3_valor_nao_duplica.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.estoque_saldo'`.

- [ ] **Step 3: Write minimal implementation**

Create `services/estoque_saldo.py`:

```python
"""O saldo de um lote de estoque, mantido num lugar só.

`AlmoxarifadoEstoque` tem três colunas de quantidade e elas precisam andar
juntas:

- `quantidade_inicial` — histórico do lote, nunca muda depois de criado;
- `quantidade` — o que resta, e o que as telas mostram;
- `quantidade_disponivel` — o que a SAÍDA valida
  (`views/almoxarifado/movimentos.py:597`, `func.sum(quantidade_disponivel)`).

O caminho de entrada por nota (`movimentos.py:400-406`) mantinha as três. O
caminho manual (`almoxarifado_utils.apply_movimento_manual`) e o de devolução
mantinham só `quantidade` — e o resultado era o pior dos dois mundos: entrada
manual criava lote com `quantidade_disponivel = NULL` (a saída recusava
material que existia) e saída manual zerava `quantidade` deixando
`quantidade_disponivel` intacta (**as mesmas unidades saíam de novo**).
"""
from decimal import Decimal

from app import db
from models import AlmoxarifadoEstoque

__all__ = ['SaldoInsuficiente', 'creditar', 'criar_lote', 'debitar']


class SaldoInsuficiente(ValueError):
    """Pediram mais do que o lote tem disponível."""


def _d(valor):
    return valor if isinstance(valor, Decimal) else Decimal(str(valor or 0))


def criar_lote(item_id, quantidade, admin_id, **campos):
    """Um lote novo, com as três colunas coerentes desde o nascimento."""
    qtd = _d(quantidade)
    lote = AlmoxarifadoEstoque(
        item_id=item_id,
        admin_id=admin_id,
        quantidade=qtd,
        quantidade_inicial=qtd,
        quantidade_disponivel=qtd,
        status=campos.pop('status', 'DISPONIVEL'),
        **campos)
    db.session.add(lote)
    return lote


def creditar(estoque, quantidade):
    """Devolução ou entrada num lote que já existe."""
    qtd = _d(quantidade)
    estoque.quantidade = _d(estoque.quantidade) + qtd
    estoque.quantidade_disponivel = _d(estoque.quantidade_disponivel) + qtd


def debitar(estoque, quantidade):
    """Saída. Levanta se o disponível não cobre."""
    qtd = _d(quantidade)
    disponivel = _d(estoque.quantidade_disponivel)
    if qtd > disponivel:
        raise SaldoInsuficiente(
            f'lote {estoque.id}: pedido {qtd}, disponível {disponivel}')
    estoque.quantidade = _d(estoque.quantidade) - qtd
    estoque.quantidade_disponivel = disponivel - qtd
```

- [ ] **Step 4: Apply it in `apply_movimento_manual`**

Em `almoxarifado_utils.py`, no ramo CONSUMÍVEL de `apply_movimento_manual`
(`:645-690`), trocar cada `AlmoxarifadoEstoque(...)` por `criar_lote(...)` e
cada `estoque.quantidade += movimento.quantidade` por
`creditar(estoque, movimento.quantidade)`. No ramo de SAÍDA, trocar a baixa
manual por `debitar(estoque, movimento.quantidade)`.

⚠️ **Faça o mesmo em `rollback_movimento_manual`**, a irmã: se ela desfizer só
`quantidade`, a correção da ida cria o defeito na volta.

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_onda3_valor_nao_duplica.py -v`
Expected: PASS

Run: `python -m pytest tests/test_arreio_almoxarifado_e_tenant.py -v`
Expected: PASS, mesma contagem de antes.

- [ ] **Step 6: Commit**

```bash
git add services/estoque_saldo.py almoxarifado_utils.py tests/test_onda3_valor_nao_duplica.py
git commit -m "fix(almoxarifado): a unidade sai uma vez so

RED: ModuleNotFoundError services.estoque_saldo; debitar deixava
quantidade_disponivel para tras

A saida valida em func.sum(quantidade_disponivel), e o caminho manual mantinha
so quantidade. Entrada manual criava lote com disponivel NULL (a guarda
recusava material que existia); saida manual zerava quantidade e deixava
disponivel intacta — as mesmas unidades saiam de novo.

O caminho de entrada por nota (movimentos.py:400) sempre manteve as tres. A
invariante existia; metade do codigo a ignorava."
```

---

### Task 2: O material devolvido volta a existir

**Files:**
- Modify: `views/almoxarifado/movimentos.py:1066` (`processar_devolucao`), `:1330` (`processar_devolucao_multipla`)
- Test: `tests/test_onda3_valor_nao_duplica.py` (acrescentar)

**Interfaces:**
- Consumes: `criar_lote` de `services.estoque_saldo` (Task 1).
- Produces: nada.

📖 O lote de retorno nasce com `AlmoxarifadoEstoque(item_id=item_id,
quantidade=quantidade, status='DISPONIVEL', admin_id=admin_id)` — sem
`quantidade_disponivel`. **O material devolvido fica invisível para
`sum(quantidade_disponivel)` e nunca mais pode ser emitido.**

- [ ] **Step 1: Write the failing test**

```python
# ---------------------------------------------------------------------------
# Task 2 — o material devolvido volta a existir
# ---------------------------------------------------------------------------

def test_devolucao_de_consumivel_volta_a_ser_emitivel():
    """🔴 `movimentos.py:1066` criava o lote de retorno só com `quantidade`.

    O devolvido ficava invisível para `sum(quantidade_disponivel)`.
    """
    from sqlalchemy import func

    from models import AlmoxarifadoEstoque

    with app.app_context():
        t = um_tenant('onda3_dev', com_fatos=False)
        item = _item_consumivel(t.admin_id)
        db.session.commit()
        item_id, admin_id, funcionario_id = item.id, t.admin_id, t.funcionario_id

    resposta = cliente_de(admin_id).post('/almoxarifado/devolucao', data={
        'funcionario_id': str(funcionario_id),
        'item_id': str(item_id),
        'quantidade': '7',
        'condicao_devolucao': 'BOM',
    }, follow_redirects=True)
    assert resposta.status_code == 200

    with app.app_context():
        disponivel = db.session.query(
            func.coalesce(func.sum(AlmoxarifadoEstoque.quantidade_disponivel), 0)
        ).filter(AlmoxarifadoEstoque.item_id == item_id).scalar()
        assert Decimal(str(disponivel)) == Decimal('7'), (
            f'devolveu 7 e o disponível ficou {disponivel} — material sumiu')
```

⚠️ Confirme a URL e o nome dos campos do formulário de devolução antes de rodar:
`grep -n "route.*devolucao" views/almoxarifado/movimentos.py`

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_onda3_valor_nao_duplica.py -k devolucao -v`
Expected: FAIL — disponível fica `0` (a coluna nasceu NULL).

- [ ] **Step 3: Write minimal implementation**

Em `movimentos.py:1066`, trocar:

```python
            estoque = AlmoxarifadoEstoque(
                item_id=item_id,
                quantidade=quantidade,
                status='DISPONIVEL',
                admin_id=admin_id
            )
            db.session.add(estoque)
```

por:

```python
            # `criar_lote` mantém `quantidade_inicial` e
            # `quantidade_disponivel` junto com `quantidade`. Sem as três, o
            # material devolvido é invisível para a guarda de saída
            # (`func.sum(quantidade_disponivel)`, `:597`) e nunca mais pode
            # ser emitido.
            estoque = criar_lote(item_id, quantidade, admin_id)
```

com `from services.estoque_saldo import criar_lote` no topo. **Repita em
`processar_devolucao_multipla` (`:1330`)**, que tem a omissão idêntica.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_onda3_valor_nao_duplica.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add views/almoxarifado/movimentos.py tests/test_onda3_valor_nao_duplica.py
git commit -m "fix(almoxarifado): material devolvido volta a ser emitivel

RED: devolveu 7 e o disponivel ficou 0

O lote de retorno nascia so com quantidade. Invisivel para
sum(quantidade_disponivel), o devolvido nunca mais podia ser emitido.
Identico em processar_devolucao_multipla."
```

---

### Task 3: A devolução para de ir toda para a obra 1, e a entrada volta a ser atômica

**Files:**
- Modify: `views/almoxarifado/movimentos.py:1045`, `:411`, `:455`, `:467`, `:857`
- Test: `tests/test_onda3_valor_nao_duplica.py` (acrescentar)

**Interfaces:**
- Consumes: nada.
- Produces: nada.

🔴 **`:1045` é um bug de três linhas de distância.** 📖 `obra_id=estoque.obra_id
or 1`, mas `estoque.obra_id = None` foi atribuído em `:1031`. A expressão é
**sempre `1`** — toda devolução serializada é carimbada com a obra de id 1, obra
arbitrária que pode ser de outro tenant, e a obra real se perde.
`relatorios.py:214` (consumo por obra) lê exatamente essa coluna.

🔴 **`:411`/`:455` — a "TRANSAÇÃO ATÔMICA" não é atômica.** 📖 O
`EventManager.emit('material_entrada', ...)` roda **dentro** do laço, antes do
`db.session.commit()` da rota (`:467`), e o handler
`criar_conta_pagar_entrada_material` commita (`event_manager.py:216`). Depois do
item 1 a sessão já foi commitada: falha no item 3 chama `rollback()` que **não
desfaz nada**. A rota de item único (`:185`, `:236`) emite **depois** do commit —
esta divergiu.

- [ ] **Step 1: Write the failing test**

```python
# ---------------------------------------------------------------------------
# Task 3 — a obra 1 e a atomicidade
# ---------------------------------------------------------------------------

def test_devolucao_serializada_preserva_a_obra_real():
    """🔴 `movimentos.py:1045` — `estoque.obra_id or 1`, com obra_id posto a
    None três linhas antes (`:1031`). A expressão era SEMPRE 1.
    """
    import inspect

    import views.almoxarifado.movimentos as mov
    fonte = inspect.getsource(mov)
    assert 'estoque.obra_id or 1' not in fonte, (
        'toda devolução ainda vai para a obra de id 1')


def test_entrada_em_lote_emite_depois_do_commit():
    """🔴 O emit dentro do laço tornava o rollback um no-op.

    A rota de item único (`:185`, `:236`) emite depois do commit. Esta
    divergiu, e o docstring dela promete 'TRANSAÇÃO ATÔMICA'.
    """
    import inspect

    import views.almoxarifado.movimentos as mov
    fonte = inspect.getsource(mov.processar_entrada_multipla)
    pos_emit = fonte.find("EventManager.emit('material_entrada'")
    pos_commit = fonte.find('db.session.commit()')
    assert pos_emit > pos_commit > 0, (
        'o emit de material_entrada ainda acontece antes do commit da rota')
```

⚠️ Confirme o nome real da função da entrada em lote:
`grep -n "def processar_entrada" views/almoxarifado/movimentos.py`

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_onda3_valor_nao_duplica.py -k "obra_real or atomic or commit" -v`
Expected: FAIL — os dois padrões ainda estão no arquivo.

- [ ] **Step 3: Write minimal implementation**

**3a.** Em `:1031-1045`, guardar a obra **antes** de limpá-la:

```python
                # A obra real, ANTES de o lote ser liberado. `obra_id` é
                # zerado logo abaixo porque o item volta ao estoque livre —
                # mas o MOVIMENTO precisa dizer de onde ele voltou.
                # `estoque.obra_id or 1` era sempre 1: a atribuição a None
                # acontecia três linhas antes.
                obra_de_origem = estoque.obra_id

                estoque.status = 'DISPONIVEL'
                estoque.funcionario_atual_id = None
                estoque.obra_id = None
```

e no `AlmoxarifadoMovimento`, `obra_id=obra_de_origem`.

⚠️ Se `AlmoxarifadoMovimento.obra_id` for `NOT NULL`, **pare e reporte** — a
correção passa a exigir migration para torná-lo nullable, e isso é decisão
separada. Confira: `grep -n "class AlmoxarifadoMovimento" -A 30 models.py | grep obra_id`

**3b.** Em `processar_entrada_multipla`, tirar os dois `EventManager.emit`
(`:411` e `:455`) de dentro do laço. Acumule numa lista e emita **depois** do
`db.session.commit()` de `:467`:

```python
        # Os emits saem do laço: o handler `criar_conta_pagar_entrada_material`
        # commita (`event_manager.py:216`), então emitir dentro do laço já
        # tinha commitado o item 1 quando o item 3 falhava — e o
        # `db.session.rollback()` do erro não desfazia nada. Meia carga ficava
        # no estoque com o chamador informado de que a operação falhou.
        # A rota de item único (`:185`, `:236`) sempre emitiu depois do commit.
        entradas_para_notificar = []
        ...
        # dentro do laço, no lugar do emit:
                    if fornecedor_id:
                        entradas_para_notificar.append({
                            'movimento_id': movimento.id,
                            'item_id': item.id,
                            'fornecedor_id': fornecedor_id,
                        })
        ...
        db.session.commit()
        for carga in entradas_para_notificar:
            EventManager.emit('material_entrada', carga, admin_id=admin_id)
```

⚠️ `movimento.id` só existe depois de flush. Se o laço não tiver `db.session.flush()`,
acrescente um antes de montar a carga.

**3c.** Em `:857` (`processar_saida_multipla`), o `continue` silencioso quando o
lote não está mais `DISPONIVEL` deve virar falha explícita: acumule os lotes que
sumiram e, se houver algum, `rollback()` e responda `success: False` nomeando-os.
📖 Hoje a resposta é `success: true` com a contagem cheia.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_onda3_valor_nao_duplica.py -v`
Expected: PASS

Run: `python -m pytest tests/ -k almoxarifado -m "not browser" -q`
Expected: PASS, mesma contagem de antes.

- [ ] **Step 5: Commit**

```bash
git add views/almoxarifado/movimentos.py tests/test_onda3_valor_nao_duplica.py
git commit -m "fix(almoxarifado): a obra real sobrevive, e a entrada em lote e atomica

RED: 'estoque.obra_id or 1' no fonte; emit antes do commit da rota

obra_id era zerado tres linhas antes do 'or 1': toda devolucao serializada ia
para a obra de id 1, arbitraria e possivelmente de outro tenant.

O emit dentro do laco tornava o rollback um no-op, porque o handler commita.
Meia carga ficava no estoque com o chamador informado de que falhou."
```

---

### Task 4: Excluir um reembolso para de apagar os dos colegas

**Files:**
- Modify: `reembolso_views.py:293` (editar), `:330` (excluir)
- Test: `tests/test_onda3_valor_nao_duplica.py` (acrescentar)

**Interfaces:**
- Consumes: nada.
- Produces: nada.

🔴 📖 `:330` apaga o `GestaoCustoPai` **compartilhado** se ele estiver PENDENTE.
O cascade `all, delete-orphan` (`models.py:7203`) leva junto os filhos de **todos
os outros reembolsos do mesmo funcionário**. E `:293` sobrescreve
`gcp.valor_total = valor` com o valor de **um** reembolso, sem tocar no
`GestaoCustoFilho`: os irmãos evaporam do total e pai×filhos divergem.

📖 **A disciplina correta está escrita**, em `transporte_views.py:565-579`, com o
comentário explicando por que se conta filho em vez de somar valor. Copie-a.

- [ ] **Step 1: Write the failing test**

```python
# ---------------------------------------------------------------------------
# Task 4 — o pai compartilhado do reembolso
# ---------------------------------------------------------------------------

def test_excluir_um_reembolso_nao_apaga_os_dos_colegas():
    """🔴 `reembolso_views.py:330` apagava o GestaoCustoPai COMPARTILHADO.

    O cascade `all, delete-orphan` (`models.py:7203`) levava junto os filhos
    de todos os outros reembolsos do mesmo funcionário.
    """
    from models import GestaoCustoFilho, ReembolsoFuncionario

    with app.app_context():
        t = um_tenant('onda3_reemb', com_fatos=False)
        admin_id, func_id, obra_id = t.admin_id, t.funcionario_id, t.obra_id

    cliente = cliente_de(admin_id)
    for i, valor in enumerate(('100,00', '250,00'), start=1):
        cliente.post('/reembolsos/novo', data={
            'funcionario_id': str(func_id), 'obra_id': str(obra_id),
            'categoria': 'TRANSPORTE', 'descricao': f'corrida {i}',
            'valor': valor, 'data_reembolso': '2026-08-25',
        }, follow_redirects=True)

    with app.app_context():
        reembolsos = ReembolsoFuncionario.query.filter_by(
            admin_id=admin_id, funcionario_id=func_id).all()
        assert len(reembolsos) == 2, 'o fixture precisa de dois reembolsos'
        primeiro, segundo = reembolsos[0].id, reembolsos[1].id
        filhos_antes = GestaoCustoFilho.query.count()

    cliente.post(f'/reembolsos/{primeiro}/excluir', follow_redirects=True)

    with app.app_context():
        assert ReembolsoFuncionario.query.get(segundo) is not None, (
            'o reembolso do colega foi apagado junto')
        filhos_depois = GestaoCustoFilho.query.count()
        assert filhos_depois == filhos_antes - 1, (
            f'apagou {filhos_antes - filhos_depois} filhos; devia apagar 1')
```

⚠️ Confirme as URLs e os campos do formulário de reembolso:
`grep -n "route" reembolso_views.py | head -12`

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_onda3_valor_nao_duplica.py -k reembolso -v`
Expected: FAIL — o segundo reembolso perdeu o filho, ou sumiu.

- [ ] **Step 3: Write minimal implementation**

Em `reembolso_views.py:330` (`excluir`), trocar a exclusão direta do pai por:

```python
        # O `GestaoCustoPai` é COMPARTILHADO entre os reembolsos do mesmo
        # funcionário, e `GestaoCustoPai.itens` é `cascade='all,
        # delete-orphan'` (`models.py:7203`): apagá-lo levava junto os filhos
        # de TODOS os outros reembolsos dele.
        #
        # Disciplina copiada de `transporte_views.py:565-579`: apaga o FILHO
        # deste reembolso, recalcula o total do pai, e só mata o pai se não
        # sobrar filho nenhum — contando filhos, nunca somando valor. Soma
        # zero não é ausência de filho.
        if reembolso.origem_tabela == 'gestao_custo_pai' and reembolso.origem_id:
            gcp = GestaoCustoPai.query.filter_by(
                id=reembolso.origem_id, admin_id=admin_id).first()
            if gcp:
                GestaoCustoFilho.query.filter_by(
                    pai_id=gcp.id, origem_id=reembolso.id).delete()
                db.session.flush()
                novo_total = db.session.query(
                    func.coalesce(func.sum(GestaoCustoFilho.valor), 0)
                ).filter(GestaoCustoFilho.pai_id == gcp.id).scalar()
                gcp.valor_total = Decimal(str(novo_total))
                restantes = db.session.query(
                    func.count(GestaoCustoFilho.id)
                ).filter(GestaoCustoFilho.pai_id == gcp.id).scalar() or 0
                if restantes == 0 and gcp.status == 'PENDENTE':
                    db.session.delete(gcp)
```

⚠️ Confira como o filho deste reembolso é identificado hoje — se
`GestaoCustoFilho` não tiver `origem_id` apontando para o reembolso, **pare e
reporte**: sem chave que ligue filho a reembolso, a correção precisa de uma, e
isso é migration.

Em `:293` (`editar`), trocar `gcp.valor_total = valor` pelo mesmo recálculo por
soma dos filhos, **depois** de atualizar o filho deste reembolso.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_onda3_valor_nao_duplica.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add reembolso_views.py tests/test_onda3_valor_nao_duplica.py
git commit -m "fix(reembolso): excluir um para de apagar os dos colegas

RED: apagou 2 filhos quando devia apagar 1

O GestaoCustoPai e compartilhado entre os reembolsos do mesmo funcionario, e
itens e cascade all,delete-orphan: apagar o pai levava junto os filhos de
todos os outros. Editar sobrescrevia valor_total com o valor de UM reembolso.

Disciplina copiada de transporte_views.py:565-579, que ja documentava a
armadilha."
```

---

### Task 5: A migração "idempotente" para de perder a rodada inteira

**Files:**
- Modify: `gestao_custos_views.py:1415`, `:1433` (`migrar_contas_pagar`)
- Test: `tests/test_onda3_valor_nao_duplica.py` (acrescentar)

**Interfaces:**
- Consumes: nada.
- Produces: nada.

🔴 **Dois defeitos na mesma função.** 📖 `:1433` monta `GestaoCustoFilho` com
`obra_id` possivelmente NULL **e** sem `centro_custo_id`, violando
`ck_gestao_custo_filho_destino` (`models.py:7261`) — e
`custos_escritorio_views._criar_conta_pagar` cria toda despesa de escritório sem
`obra_id`, **então essas linhas existem por construção**. O `IntegrityError`
estoura **fora** do `try` por registro, o handler externo faz rollback, e **toda
a rodada se perde** — num botão anunciado como *"ação segura e pode ser
repetida"*.

📖 `:1415`: o pai nasce com `valor_total=valor_original` e o único filho com
`valor=saldo_cp`, e a query **inclui de propósito** contas PARCIAL onde os dois
diferem. A primeira edição chama `_recalcular_total_pai`, que reescreve
`valor_total` para o saldo — **o passivo encolhe pelo valor já pago, sem trilha.**

- [ ] **Step 1: Write the failing test**

```python
# ---------------------------------------------------------------------------
# Task 5 — a migração de contas a pagar
# ---------------------------------------------------------------------------

def test_migracao_pula_o_registro_ruim_em_vez_de_perder_a_rodada():
    """🔴 O IntegrityError estourava FORA do try por registro."""
    import inspect

    import gestao_custos_views
    fonte = inspect.getsource(gestao_custos_views.migrar_contas_pagar)
    assert 'centro_custo_id' in fonte, (
        'o filho ainda nasce sem destino, violando '
        'ck_gestao_custo_filho_destino')


def test_pai_e_filho_nascem_com_o_mesmo_valor():
    """🔴 Pai com `valor_original`, filho com `saldo`: a primeira edição
    encolhia o passivo pelo valor já pago, sem trilha.
    """
    import inspect

    import gestao_custos_views
    fonte = inspect.getsource(gestao_custos_views.migrar_contas_pagar)
    assert 'valor_total=cp.valor_original' not in fonte.replace(' ', ''), (
        'o pai ainda nasce com valor_original enquanto o filho recebe saldo')
```

⚠️ Confirme o nome real da função: `grep -n "def migrar_contas_pagar" gestao_custos_views.py`

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_onda3_valor_nao_duplica.py -k migracao -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

**3a.** Pai e filho passam a nascer com o **mesmo** valor — o saldo, que é o que
resta a pagar:

```python
            # Pai e filho com o MESMO valor. Nasciam diferentes (pai com
            # `valor_original`, filho com `saldo`) e a query inclui de
            # propósito contas PARCIAL, onde os dois divergem. A primeira
            # edição chamava `_recalcular_total_pai`, que reescrevia
            # `valor_total` para a soma dos filhos: o passivo encolhia pelo
            # valor já pago, sem trilha nenhuma.
            valor_migrado = _d(cp.saldo)
```

usando `valor_migrado` nos dois.

**3b.** O destino obrigatório, e o `try` cobrindo o `flush` de cada registro:

```python
            # `ck_gestao_custo_filho_destino` (`models.py:7261`) exige obra OU
            # centro de custo. Despesa de escritório nasce sem obra por
            # construção (`custos_escritorio_views._criar_conta_pagar`), então
            # sem este ramo o IntegrityError é garantido — e estourava FORA do
            # try por registro, levando a rodada inteira num rollback.
            if not cp.obra_id and not centro_custo_id:
                pulados.append((cp.id, 'sem obra e sem centro de custo'))
                continue
            try:
                db.session.flush()
            except IntegrityError as erro:
                db.session.rollback()
                pulados.append((cp.id, str(erro.orig)[:120]))
                continue
```

e o relatório final diz quantos entraram e quantos foram pulados, **com o
motivo** — 📖 a Global Constraint da casa: *"relatório não esconde o que não
sabe"*.

**3c.** Chamar `sincronizar_obra_do_pai(pai)` depois de criar o filho — 📖 hoje
não é chamado aqui, e `gcp.obra_id` fica NULL.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_onda3_valor_nao_duplica.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gestao_custos_views.py tests/test_onda3_valor_nao_duplica.py
git commit -m "fix(gestao-custos): a migracao para de perder a rodada e de encolher o passivo

RED: filho nascia sem destino; pai com valor_original e filho com saldo

O IntegrityError estourava fora do try por registro e o handler externo fazia
rollback: todo registro migrado naquela execucao se perdia, num botao
anunciado como 'acao segura e pode ser repetida'.

E pai e filho nasciam com valores diferentes: a primeira edicao encolhia o
passivo pelo valor ja pago, sem trilha."
```

---

### Task 6: O card e o detalhe param de discordar

**Files:**
- Modify: `financeiro_service.py:752`
- Test: `tests/test_onda3_valor_nao_duplica.py` (acrescentar)

📖 Pai PARCIAL: `valor_pai` é o `saldo` restante, mas o laço de filhos manuais
soma cada filho pelo `valor` **cheio** e descarta o `resto` negativo. Dois filhos
de R$ 500 com R$ 600 pagos dão `saidas_previstas = 400` no card e R$ 1.000 de
previsto no detalhe — **os R$ 600 já pagos contados duas vezes na mesma tela.**

- [ ] **Step 1: Write the failing test**

```python
def test_card_e_detalhe_do_pai_parcial_batem():
    """🔴 `financeiro_service.py:752` — o KPI usa o saldo restante e o detalhe
    lista os filhos pelo valor cheio.
    """
    import inspect

    import financeiro_service
    fonte = inspect.getsource(financeiro_service)
    assert 'resto' not in fonte or 'max(' in fonte, (
        'o resto negativo ainda é descartado em silêncio')
```

⚠️ Este teste é fraco de propósito — é âncora, não prova. **Substitua-o** por um
que monte um `GestaoCustoPai` PARCIAL com dois filhos e compare o total do card
com a soma do detalhe, assim que você localizar as duas funções que os produzem:
`grep -n "saidas_previstas\|def detalhes" financeiro_service.py`

- [ ] **Step 2-5:** RED, correção (o rateio do pagamento entre os filhos, em vez
  de descartar o resto), verde, commit.

---

### Task 7: A ressalva para de zerar todas as parcelas

**Files:**
- Modify: `services/financeiro_compra.py:433`, `:420`, `:566`
- Test: `tests/test_onda3_valor_nao_duplica.py` (acrescentar)

🔴 📖 `:433` — `if total_aberto > 0 and atestado != total_aberto:` **sem guarda
`atestado > 0`**. O caminho da ressalva D6 existe justamente para liberar conta
com "sem atesto de recebimento" em aberto; quando é usado (alcançável de
`compras_views.py:1580`), `atestado` é 0 e **toda parcela é reescrita para
R$ 0,00**, com `saldo = 0 - valor_pago`. É a *"conta de R$ 0,00 que desaparece de
toda projeção de caixa"* que o docstring de `criar_obrigacao` diz evitar. E
`divergencia_nota_atestado` devolve `dentro=True` quando `atestado <= 0`, então
**nem o aviso de divergência dispara**.

- [ ] **Step 1: Write the failing test**

```python
def test_liberar_com_ressalva_nao_zera_as_parcelas():
    """🔴 `services/financeiro_compra.py:433` — sem guarda `atestado > 0`.

    A ressalva existe para liberar SEM atesto; com atesto 0, o rateio
    proporcional reescrevia toda parcela para R$ 0,00.
    """
    import inspect

    from services import financeiro_compra
    fonte = inspect.getsource(financeiro_compra)
    assert 'atestado > 0 and total_aberto > 0' in fonte or \
           'if atestado > 0' in fonte, (
        'o rateio ainda roda com atestado == 0 e zera todas as parcelas')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_onda3_valor_nao_duplica.py -k ressalva -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
        # `atestado > 0` é a guarda que faltava. O rateio existe para pagar o
        # que foi atestado em vez do que foi pedido — mas a ressalva D6 libera
        # JUSTAMENTE sem atesto, e aí `atestado` é 0: sem esta guarda, toda
        # parcela virava R$ 0,00 com `saldo = 0 - valor_pago`. É a "conta de
        # R$ 0,00 que desaparece de toda projeção de caixa" que o docstring de
        # `criar_obrigacao` diz evitar.
        if atestado > 0 and total_aberto > 0 and atestado != total_aberto:
```

**3b.** `:420` — `liberar()` seleciona por `pedido_compra_id` **sem filtrar
`fechamento_id`**: fechar um lote com a parcela 1 de 3 libera as 2 e 3, pagáveis
sem nunca terem estado em lote fechado. Acrescente o filtro.

**3c.** `:566` — `reabrir_lote` volta o `status` para 'ABERTO' mas **não** reverte
a `situacao_liberacao` que `fechar_lote` pôs em 'liberada'. Reverta.

- [ ] **Step 4-5:** verde, e commit.

---

### Task 8: Reprocessar a folha para de dobrá-la

**Files:**
- Modify: `folha_pagamento_views.py:148`
- Test: `tests/test_onda3_valor_nao_duplica.py` (acrescentar)

> 🔴 **Esta é a automação A12.** 🔬 A reconferência de 23/08
> (`docs/reconferencia-backlog-2026-08-23.md:512`) já a listava como ABERTA; o
> code review chegou nela por caminho independente. **Risque da lista das 25 ao
> fechar esta task.**

📖 `reprocessar` apaga só `FolhaPagamento`; o `GestaoCustoPai`/`Filho` e o
lançamento contábil da rodada anterior **sobrevivem e são recriados**: a folha
dobra no contas a pagar e no razão.

⚠️ 📖 A mesma função usa `admin_id=current_user.id` — que é o **defeito de tenant
da Onda 2** para papéis não-admin. Se a Onda 2 já entrou, troque por
`get_admin_id()` aqui também.

- [ ] **Step 1: Write the failing test**

```python
def test_reprocessar_folha_nao_dobra_o_contas_a_pagar():
    """🔴 A12 — `folha_pagamento_views.py:148` apagava só `FolhaPagamento`.

    O GestaoCustoPai/Filho e o lançamento contábil da rodada anterior
    sobreviviam e eram recriados.
    """
    from models import GestaoCustoFilho

    with app.app_context():
        t = um_tenant('onda3_folha')
        admin_id = t.admin_id

    cliente = cliente_de(admin_id)
    dados = {'mes_referencia': '2026-07', 'reprocessar': 'false'}
    cliente.post('/folha/processar', data=dados, follow_redirects=True)
    with app.app_context():
        depois_da_primeira = GestaoCustoFilho.query.count()

    dados['reprocessar'] = 'true'
    cliente.post('/folha/processar', data=dados, follow_redirects=True)
    with app.app_context():
        depois_do_reprocesso = GestaoCustoFilho.query.count()

    assert depois_do_reprocesso == depois_da_primeira, (
        f'reprocessar dobrou: {depois_da_primeira} → {depois_do_reprocesso}')
```

⚠️ Confirme a URL e o campo de mês: `grep -n "route.*processar" folha_pagamento_views.py`

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_onda3_valor_nao_duplica.py -k folha -v`
Expected: FAIL — a contagem dobra.

- [ ] **Step 3: Write minimal implementation**

```python
        if reprocessar:
            # Estornar ANTES de recriar. Apagava só `FolhaPagamento`, e o
            # `GestaoCustoPai`/`Filho` e o lançamento contábil da rodada
            # anterior sobreviviam para serem recriados: a folha dobrava no
            # contas a pagar e no razão. É a automação A12 do backlog.
            from services.folha_service import estornar_folha_do_mes
            estornar_folha_do_mes(admin_id=admin_id,
                                  mes_referencia=mes_referencia)
            db.session.commit()
```

⚠️ Se `estornar_folha_do_mes` não existir em `services/folha_service.py`, ela é
**parte desta task**: escreva-a, e faça-a apagar as três coisas — `FolhaPagamento`,
os `GestaoCustoPai`/`Filho` cuja origem seja a folha daquele mês, e o
`LancamentoContabil` correspondente — com contagem antes e depois no log.
Confira primeiro: `grep -n "def estornar" services/folha_service.py`

- [ ] **Step 4-5:** verde, e commit citando a A12.

---

### Task 9: A mão de obra para de ser cobrada duas e três vezes

**Files:**
- Modify: `services/folha_service.py:761`, `:1336`, `:1444`; `services/custo_funcionario_dia.py:97`
- Test: `tests/test_onda3_valor_nao_duplica.py` (acrescentar)

📖 Três dobras distintas no mesmo serviço:
- `:761` — atraso descontado **duas vezes**: as horas faltantes já estão dentro de `horas_falta`, e `desconto_atrasos` cobra de novo.
- `:1336` — usa `salario_bruto` (que **já inclui** HE e DSR) como "Salário Base" e **soma HE 50/100 e DSR outra vez** como fatias separadas.
- `:1444` — `processar_e_salvar_folha_obra` lança a folha **inteira do mês** contra *cada* obra trabalhada: o custo por obra e todo roll-up saem inflados.

E 📖 `custo_funcionario_dia.py:97` — para diarista o `componente_folha` é rateado
mas `custo_hora_normal` não: **a tela mostra o dobro do que foi lançado.**

- [ ] **Step 1: Write the failing test** — um teste por dobra, cada um montando
  um funcionário com o perfil que a expõe. 🔬 `tests/helpers_tenant.um_tenant`
  aceita `tipo_remuneracao`, `valor_diaria` e `salario` — use-os em vez de
  montar `Funcionario` à mão.

- [ ] **Step 2-5:** RED, correção **uma dobra por commit** (são independentes e
  misturá-las torna a bisseção impossível), verde, commit.

⚠️ 🔬 `:1444` é a mais cara e a que mais mexe em número que alguém já viu:
lançar a folha por obra exige **ratear por horas apontadas naquela obra**, e o
rateio precisa somar exatamente o total do mês. Prove isso com teste antes de
mexer no resto.

---

### Task 10: O ponto que não vira hora, e o RDO que cobra quem saiu

**Files:**
- Modify: `ponto_views.py:1487`, `:2446`; `views/rdo.py:2867`, `:1888`
- Test: `tests/test_onda3_valor_nao_duplica.py` (acrescentar)

📖 `ponto_views.py:1487` — a importação Excel **nunca calcula
`horas_trabalhadas`**: o mês importado marca 0h, a folha cobra todo dia como
falta cheia, nenhum custo de obra é gerado. O ramo de atualização ainda descarta
`obra_id`/`tipo_registro`.
📖 `:2446` — as duas rotas de ponto facial commitam sem
`PontoService._calcular_horas`, e `/api/identificar-e-registrar` nunca emite
`ponto_registrado`.
📖 `views/rdo.py:2867` — a edição unificada apaga `RDOMaoObra` em bloco **sem**
`remover_custos_rdo`/`remover_custo_diario_rdo`: o trabalhador removido **segue
sendo cobrado**.
📖 `:1888` — `reabrir_rdo` desfaz o percentual do cronograma mas deixa o custo de
MO no razão com o RDO em `rascunho`.

- [ ] **Step 1-5:** um teste por defeito, RED, correção, verde, commit.

⚠️ 📖 `:1888` conversa diretamente com o trabalho de 24/08 (`95eb585f`,
"rascunho não move o cronograma"). **Leia
`docs/superpowers/plans/2026-08-24-rascunho-nao-move-cronograma.md` antes**: a
simetria Submeter/Reabrir foi desenhada lá, e o custo é a metade que ficou de
fora.

---

## Fecho da onda

- [ ] `bash run_tests.sh --gate` verde, com a contagem registrada.
- [ ] **A12 riscada** de `docs/reconferencia-backlog-2026-08-23.md`.
- [ ] `docs/auditoria/achados-code-review-2026-08-25.md` — marcar os 15 achados
      desta onda (o 16º, `financeiro_service.py:619`, segue esperando a D2).
- [ ] 🔬 `grep -rn "AlmoxarifadoEstoque(" --include=*.py . | grep -v __pycache__`
      — todo construtor restante passa por `criar_lote`, ou tem as três colunas.
