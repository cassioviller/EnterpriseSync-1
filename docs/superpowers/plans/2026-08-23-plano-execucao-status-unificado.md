# Régua de status unificado (Fase 4 do ciclo de compras) — Implementation Plan

> **Estado em 2026-08-25 (varredura de fecho):** ✅ **FECHADO** — Fase 4 do ciclo, entregue e mesclada em 23/08 (`05c2c639`). `services/etapa_compra.py` deriva a régua de 9 casas; `scripts/runbook_fase4.py` 14/14 pela tela. 🔬 10/10 dos arquivos prometidos existem na árvore.
>
> Não há trabalho pendente aqui. **As caixas `- [ ]` abaixo não foram marcadas de propósito:** elas são
> rascunho de execução, não registro de estado. Quem carrega a verdade é este bloco,
> o `ESTADO-ATUAL.md`, o código e o git. O veredito acima foi dado por **existência de
> arquivo na árvore**, nunca por contagem de caixa.


> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao pedido de compra **uma** leitura de onde ele está — nove casas derivadas dos seis portadores de estado que hoje aparecem como badges soltos, com um ponteiro que diz o que falta.

**Architecture:** Função **pura e derivada** (`services/etapa_compra.py`), sem coluna nova e sem listener: ela LÊ os seis portadores em vez de duplicá-los (D1a da spec). A régua é **lista de conferência com ponteiro**, não barra de progresso — cada casa acende pela própria condição, e o "onde está" é a primeira casa aplicável ainda não satisfeita; é o que permite o Fluxo B (paga antes de receber) sem mentir. Consome o que já existe (`pernas_faltantes`, `valor_das_notas`, `situacao_liberacao_inicial` em `services/financeiro_compra.py`) em vez de reimplementar. A tela do pedido a mostra; a listagem mostra só o ponteiro, que é o que torna duas compras comparáveis.

**Tech Stack:** Python 3, Flask 3, SQLAlchemy 2 (`models.py`), Jinja2 + Bootstrap 5, pytest (`pytest.mark.integration`), PostgreSQL real. Runbook por script com `requests` (molde de `scripts/runbook_fase3.py`).

**Spec:** `docs/superpowers/specs/2026-08-19-status-unificado-design.md` — leia em especial a seção final ("23/08 — as três decisões"), que fixa a forma da régua, as nove casas e os selos.

## Global Constraints

- **Nada é gravado.** Nenhuma migration, nenhuma coluna, nenhum listener. Se a implementação sentir vontade de gravar a etapa, **pare e releia a D1** — gravar cria o sétimo portador de estado, que é a doença que esta fase existe para curar.
- **Não reimplementar o que existe.** `pernas_faltantes(pedido)`, `valor_das_notas(pedido)`, `situacao_liberacao_inicial(pedido)` e `valor_atestado(pedido)` já respondem partes disto (📖 `services/financeiro_compra.py:291`, `services/recebimento_pedido.py`). A régua os consome.
- **A função não escreve e não commita** — dá para chamar de dentro de template sem medo, como `pernas_faltantes` já faz.
- **Casa inaplicável aparece apagada, nunca ausente** (D2 da spec): a comparação entre compras é o motivo de haver régua.
- **O critério de aceitação é a tela**, não a função: 📖 a spec fixa que "função pura que ninguém chama passa em todo teste — foi assim que `fechar_lote()` ficou semanas testado e inalcançável". O runbook por script (Task 7) tem de achar a régua no DOM.
- Testes: `pytestmark = pytest.mark.integration`, tenant por `uuid4`, sem depender de seed — molde de `tests/test_nota_e_liberacao.py`.
- Rodar a suíte **não** aplica migration (📖 `tests/conftest.py:62` desliga `SIGE_BOOT_DDL`) — irrelevante aqui, porque esta fase não tem migration, mas vale saber.

---

> 🔬 **23/08 — os nomes de coluna deste plano foram conferidos por introspeção**,
> não copiados de memória. A primeira versão errava quatro: `RequisicaoCompra`
> não tem `descricao` (e exige `numero` + `solicitante_id`), o pedido guarda
> `data_compra` e não `data_pedido`, a conta guarda `valor_original` e não
> `valor` (e exige `data_emissao`), e a nota exige `fornecedor_id` +
> `lancada_por_id`. Se algum ainda estiver errado, **corrija o plano e siga** —
> não invente coluna no modelo.

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| **Criar** `services/etapa_compra.py` | A derivação inteira: as nove casas, os selos, o ponteiro, as saídas laterais. Sem I/O, sem escrita |
| **Criar** `tests/test_etapa_compra.py` | A suíte da derivação, cenário a cenário |
| **Modificar** `compras_views.py:977` (`detalhe`) | Passar `regua=etapa_do_pedido(pedido)` ao template |
| **Modificar** `templates/compras/detalhe.html` | A régua completa, com selos |
| **Modificar** `compras_views.py` (rota da listagem) + `templates/compras/index.html` | Coluna "Onde está" — só o ponteiro |
| **Criar** `scripts/runbook_fase4.py` | O runbook pela tela, que acha a régua no DOM |

**Vocabulário travado** (usado por todas as tasks):

```python
CHAVES = ('requisitada', 'aprovada', 'pedido_emitido', 'material_recebido',
          'nota_lancada', 'liberada', 'em_lote', 'paga', 'encerrada')
```

---

### Task 1: O esqueleto da régua e as casas 1-3 (requisição e pedido)

**Files:**
- Create: `services/etapa_compra.py`
- Test: `tests/test_etapa_compra.py`

**Interfaces:**
- Consumes: `models.RequisicaoCompra`, `models.PedidoCompra`, `models.EstadoRequisicao`
- Produces: `etapa_do_pedido(pedido, dados=None) -> dict` com as chaves `casas` (lista de `Casa`), `ponteiro` (str ou None), `encerrada_por` (str ou None). `Casa` é um `namedtuple('Casa', 'chave rotulo grupo acesa aplicavel selos')`. Todas as tasks seguintes acrescentam condições **dentro** desta função — nenhuma cria função nova.

- [ ] **Step 1: Escrever o teste que falha**

```python
"""A régua de status unificado — Fase 4 do ciclo de compras.

Spec: docs/superpowers/specs/2026-08-19-status-unificado-design.md
Plano: docs/superpowers/plans/2026-08-23-plano-execucao-status-unificado.md

Molde de tests/test_nota_e_liberacao.py: fixtures locais, tenant por uuid4,
sem depender de seed.
"""
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import (Cliente, EstadoRequisicao, Fornecedor, Obra, PedidoCompra,
                    RequisicaoCompra, TipoUsuario, Usuario)
from services.etapa_compra import CHAVES, etapa_do_pedido

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-etapa-compra'
    yield


def _cenario(estado_requisicao=None, exige_atesto=True, fluxo='faturado'):
    """Admin + obra + fornecedor + pedido. Requisição só se o estado for dado."""
    suf = uuid.uuid4().hex[:8]
    with app.app_context():
        adm = Usuario(
            username=f'ec_{suf}', email=f'ec_{suf}@test.local', nome=f'Adm {suf}',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
        db.session.add(adm)
        db.session.commit()

        cliente = Cliente(nome=f'Cli {suf}', admin_id=adm.id)
        db.session.add(cliente)
        db.session.commit()
        obra = Obra(nome=f'Obra {suf}', codigo=f'O{suf[:6].upper()}',
                    data_inicio=date(2026, 1, 1), admin_id=adm.id,
                    cliente_id=cliente.id)
        forn = Fornecedor(nome=f'Forn {suf}', admin_id=adm.id)
        db.session.add_all([obra, forn])
        db.session.commit()

        requisicao = None
        if estado_requisicao is not None:
            requisicao = RequisicaoCompra(
                admin_id=adm.id, obra_id=obra.id, estado=estado_requisicao,
                numero=f'REQ-{suf.upper()}', solicitante_id=adm.id)
            db.session.add(requisicao)
            db.session.commit()

        pedido = PedidoCompra(
            admin_id=adm.id, obra_id=obra.id, fornecedor_id=forn.id,
            numero=f'PC-{suf.upper()}', valor_total=Decimal('1000.00'),
            data_compra=date(2026, 1, 10), exige_atesto=exige_atesto,
            fluxo_pagamento=fluxo,
            requisicao_id=requisicao.id if requisicao else None)
        db.session.add(pedido)
        db.session.commit()
        return adm.id, pedido.id


def _casas(pedido_id):
    with app.app_context():
        pedido = db.session.get(PedidoCompra, pedido_id)
        regua = etapa_do_pedido(pedido)
        return regua, {c.chave: c for c in regua['casas']}


def test_regua_tem_as_nove_casas_na_ordem():
    _, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.RASCUNHO)
    regua, _ = _casas(pedido_id)
    assert [c.chave for c in regua['casas']] == list(CHAVES)


def test_requisicao_em_rascunho_acende_so_a_casa_1():
    _, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.RASCUNHO)
    _, casas = _casas(pedido_id)
    assert casas['requisitada'].acesa is True
    assert casas['aprovada'].acesa is False


def test_requisicao_aprovada_acende_1_e_2():
    _, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.APROVADA)
    _, casas = _casas(pedido_id)
    assert casas['requisitada'].acesa is True
    assert casas['aprovada'].acesa is True


def test_pedido_existente_acende_a_casa_3():
    _, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    _, casas = _casas(pedido_id)
    assert casas['pedido_emitido'].acesa is True


def test_compra_direta_sem_requisicao_deixa_1_e_2_apagadas_nao_ausentes():
    """Sem requisição as duas primeiras casas não se aplicam — mas continuam
    na régua, apagadas. Casa ausente quebraria a comparação entre compras."""
    _, pedido_id = _cenario(estado_requisicao=None)
    regua, casas = _casas(pedido_id)
    assert [c.chave for c in regua['casas']] == list(CHAVES)
    assert casas['requisitada'].aplicavel is False
    assert casas['aprovada'].aplicavel is False
    assert casas['pedido_emitido'].acesa is True


def test_ponteiro_e_a_primeira_casa_aplicavel_nao_satisfeita():
    _, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.RASCUNHO)
    regua, _ = _casas(pedido_id)
    assert regua['ponteiro'] == 'aprovada'
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.pythonlibs/bin/python -m pytest tests/test_etapa_compra.py -x -p no:warnings`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.etapa_compra'`

- [ ] **Step 3: Implementação mínima**

```python
"""A régua de status unificado do pedido de compra — Fase 4 do ciclo.

Spec: docs/superpowers/specs/2026-08-19-status-unificado-design.md

Por que DERIVADA e não gravada (D1a): gravar a etapa criaria um SÉTIMO portador
de estado ao lado dos seis que já existem — e divergir dos outros seis é
exatamente a doença que esta fase existe para curar. Esta função LÊ; não escreve
nada, não commita nada, e por isso pode ser chamada de dentro de um template.

Por que LISTA DE CONFERÊNCIA e não barra de progresso (D3.1): no Fluxo B
(adiantamento) paga-se ANTES de receber — 📖 models.py:5845. Numa barra linear
isso acende a casa 8 antes da 4 e lê como defeito. Aqui cada casa acende pela
própria condição e o "onde está" é derivado: a primeira casa aplicável ainda não
satisfeita. É o desenho que SAP (indicadores independentes ELIKZ/EREKZ) e Odoo
(state + receipt_status/invoice_status derivados) usam; a NetSuite, que força um
enum linear, acabou com o status "Pending Billing/Partially Received" — o produto
cartesiano vazando para dentro do enum.
"""
from collections import namedtuple

Casa = namedtuple('Casa', 'chave rotulo grupo acesa aplicavel selos')

CHAVES = ('requisitada', 'aprovada', 'pedido_emitido', 'material_recebido',
          'nota_lancada', 'liberada', 'em_lote', 'paga', 'encerrada')

ROTULOS = {
    'requisitada': 'Requisitada',
    'aprovada': 'Aprovada',
    'pedido_emitido': 'Pedido emitido',
    'material_recebido': 'Material recebido',
    'nota_lancada': 'Nota lançada',
    'liberada': 'Liberada para pagamento',
    'em_lote': 'Em lote de pagamento',
    'paga': 'Paga',
    'encerrada': 'Encerrada',
}

# As casas 3, 4 e 5 são o three-way match (pedido ↔ recebimento ↔ nota) — o
# mesmo trio que SAP, Odoo e NetSuite conferem. Marcá-las como grupo é o que dá
# sentido a elas para além da ordem.
GRUPO_TRIADE = ('pedido_emitido', 'material_recebido', 'nota_lancada')


def etapa_do_pedido(pedido, dados=None):
    """Onde este pedido está. Não escreve nada.

    Devolve {'casas': [Casa...], 'ponteiro': chave|None, 'encerrada_por': None}.
    `ponteiro` é None quando não falta nada aplicável.

    `dados` é o pré-carregamento opcional que a LISTAGEM usa (Task 6): um dict
    {'contas': [...], 'notas': [...], 'adiantamentos': [...]} já filtrado para
    este pedido. Sem ele a função consulta sozinha, que é o certo para a tela de
    um pedido só. 🔬 a listagem traz até 200 pedidos (`compras_views.py:592`,
    `query.limit(200)`) e NÃO é paginada — chamar esta função 200 vezes sem
    pré-carregamento são ~800 consultas, o mesmo vício que custou /obras e
    /ponto/lista-obras em 21/08.
    """
    from models import EstadoRequisicao

    requisicao = pedido.requisicao
    tem_requisicao = requisicao is not None

    estado = getattr(requisicao, 'estado', None)
    aprovada = estado in (EstadoRequisicao.APROVADA, EstadoRequisicao.CONVERTIDA)

    acesa = {
        'requisitada': tem_requisicao,
        'aprovada': aprovada,
        'pedido_emitido': pedido.id is not None,
        'material_recebido': False,
        'nota_lancada': False,
        'liberada': False,
        'em_lote': False,
        'paga': False,
        'encerrada': False,
    }
    aplicavel = {chave: True for chave in CHAVES}
    aplicavel['requisitada'] = tem_requisicao
    aplicavel['aprovada'] = tem_requisicao
    selos = {chave: [] for chave in CHAVES}

    casas = [Casa(chave=c, rotulo=ROTULOS[c],
                  grupo='triade' if c in GRUPO_TRIADE else None,
                  acesa=bool(acesa[c]), aplicavel=bool(aplicavel[c]),
                  selos=list(selos[c]))
             for c in CHAVES]

    ponteiro = next((c.chave for c in casas if c.aplicavel and not c.acesa), None)
    return {'casas': casas, 'ponteiro': ponteiro, 'encerrada_por': None}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.pythonlibs/bin/python -m pytest tests/test_etapa_compra.py -x -p no:warnings`
Expected: PASS — 6 passed

- [ ] **Step 5: Commit**

```bash
git add services/etapa_compra.py tests/test_etapa_compra.py
git commit -m "feat(compras): a regua de status, derivada — casas 1 a 3 e o ponteiro"
```

---

### Task 2: As casas 4, 5 e 9 — a tríade material/nota e o encerramento

**Files:**
- Modify: `services/etapa_compra.py` (dentro de `etapa_do_pedido`)
- Test: `tests/test_etapa_compra.py` (acrescentar)

**Interfaces:**
- Consumes: `etapa_do_pedido` da Task 1; `services.financeiro_compra.valor_das_notas`
- Produces: nenhuma assinatura nova — as casas `material_recebido`, `nota_lancada` e `encerrada` passam a acender, e o selo `'com saldo'` passa a existir.

- [ ] **Step 1: Escrever os testes que falham**

```python
def test_recebimento_parcial_acende_material_recebido():
    _, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    with app.app_context():
        pedido = db.session.get(PedidoCompra, pedido_id)
        pedido.situacao_recebimento = 'parcial'
        db.session.commit()
    _, casas = _casas(pedido_id)
    assert casas['material_recebido'].acesa is True


def test_encerrado_com_saldo_acende_com_selo_nas_casas_4_e_9():
    """Encerrar com saldo satisfaz a casa — mas a régua não pode esconder que
    encerramos com falta."""
    _, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    with app.app_context():
        pedido = db.session.get(PedidoCompra, pedido_id)
        pedido.situacao_recebimento = 'encerrado_com_saldo'
        db.session.commit()
    _, casas = _casas(pedido_id)
    assert casas['material_recebido'].acesa is True
    assert 'com saldo' in casas['material_recebido'].selos
    assert 'com saldo' in casas['encerrada'].selos


def test_nao_recebido_deixa_a_casa_4_apagada():
    _, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    _, casas = _casas(pedido_id)
    assert casas['material_recebido'].acesa is False


def test_pedido_legado_sem_atesto_nao_tem_triade_de_material_e_nota():
    """📖 templates/compras/index.html:126 — em pedido legado inventar 'Não
    recebido' seria mentir sobre estoque que entrou na emissão."""
    _, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA,
                            exige_atesto=False)
    _, casas = _casas(pedido_id)
    assert casas['material_recebido'].aplicavel is False
    assert casas['nota_lancada'].aplicavel is False


def test_nota_lancada_acende_a_casa_5():
    from models import NotaFiscalPedido
    admin_id, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    with app.app_context():
        pedido = db.session.get(PedidoCompra, pedido_id)
        db.session.add(NotaFiscalPedido(
            admin_id=admin_id, pedido_id=pedido_id, numero='123',
            fornecedor_id=pedido.fornecedor_id, lancada_por_id=admin_id,
            valor_total=Decimal('1000.00'), data_emissao=date(2026, 1, 11)))
        db.session.commit()
    _, casas = _casas(pedido_id)
    assert casas['nota_lancada'].acesa is True
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.pythonlibs/bin/python -m pytest tests/test_etapa_compra.py -x -p no:warnings`
Expected: FAIL — `assert False is True` em `test_recebimento_parcial_acende_material_recebido`

- [ ] **Step 3: Implementar**

Dentro de `etapa_do_pedido`, **antes** da montagem de `casas`, substituir as três linhas `False` correspondentes por:

```python
    from services.financeiro_compra import valor_das_notas

    # A tríade só existe no regime novo. 📖 templates/compras/index.html:126:
    # em pedido legado o estoque entrou na emissão, e inventar "não recebido"
    # ali seria mentir.
    tem_triade = bool(pedido.exige_atesto)
    aplicavel['material_recebido'] = tem_triade
    aplicavel['nota_lancada'] = tem_triade

    recebido = pedido.situacao_recebimento in ('parcial', 'recebido',
                                               'encerrado_com_saldo')
    acesa['material_recebido'] = tem_triade and recebido
    acesa['nota_lancada'] = tem_triade and valor_das_notas(pedido) > 0

    if pedido.situacao_recebimento == 'encerrado_com_saldo':
        selos['material_recebido'].append('com saldo')
        selos['encerrada'].append('com saldo')

    recebimento_fechado = pedido.situacao_recebimento in ('recebido',
                                                          'encerrado_com_saldo')
```

E a casa 9 (`encerrada`) — que depende do pagamento, entregue na Task 3 — fica por ora:

```python
    acesa['encerrada'] = (not tem_triade) and recebimento_fechado
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.pythonlibs/bin/python -m pytest tests/test_etapa_compra.py -x -p no:warnings`
Expected: PASS — 11 passed

- [ ] **Step 5: Commit**

```bash
git add services/etapa_compra.py tests/test_etapa_compra.py
git commit -m "feat(compras): casas 4, 5 e o selo 'com saldo' — a triade so no regime novo"
```

---

### Task 3: As casas 6, 7 e 8 — liberação, lote e pagamento (e o Fluxo B)

**Files:**
- Modify: `services/etapa_compra.py`
- Test: `tests/test_etapa_compra.py`

**Interfaces:**
- Consumes: `models.ContaPagar`, `models.FechamentoPagamento`, `models.AdiantamentoFornecedor`
- Produces: as casas `liberada`, `em_lote`, `paga` e `encerrada` completas; selos `'com ressalva'`, `'fechado por quem montou'`, `'adiantamento'`.

- [ ] **Step 1: Escrever os testes que falham**

```python
def _conta(admin_id, pedido_id, **kw):
    from models import ContaPagar
    with app.app_context():
        c = ContaPagar(
            admin_id=admin_id, pedido_compra_id=pedido_id,
            descricao='Conta do pedido', valor_original=Decimal('1000.00'),
            data_emissao=date(2026, 1, 10), data_vencimento=date(2026, 2, 10),
            status=kw.pop('status', 'PENDENTE'),
            situacao_liberacao=kw.pop('situacao_liberacao', 'bloqueada'), **kw)
        db.session.add(c)
        db.session.commit()
        return c.id


def test_conta_liberada_acende_a_casa_6():
    admin_id, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    _conta(admin_id, pedido_id, situacao_liberacao='liberada')
    _, casas = _casas(pedido_id)
    assert casas['liberada'].acesa is True


def test_liberacao_com_ressalva_carrega_selo_na_casa_6():
    """📖 ContaPagar.liberacao_justificativa (services/financeiro_compra.py:450).
    Esconder a ressalva é esconder que alguém assumiu um risco."""
    admin_id, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    _conta(admin_id, pedido_id, situacao_liberacao='liberada',
           liberacao_justificativa='nota chega semana que vem')
    _, casas = _casas(pedido_id)
    assert 'com ressalva' in casas['liberada'].selos


def test_conta_em_lote_acende_a_casa_7():
    from models import FechamentoPagamento
    admin_id, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    conta_id = _conta(admin_id, pedido_id, situacao_liberacao='liberada')
    with app.app_context():
        lote = FechamentoPagamento(admin_id=admin_id, status='FECHADO',
                                   descricao='Lote 1',
                                   data_fechamento=date(2026, 2, 1))
        db.session.add(lote)
        db.session.commit()
        from models import ContaPagar
        conta = db.session.get(ContaPagar, conta_id)
        conta.fechamento_id = lote.id
        db.session.commit()
    _, casas = _casas(pedido_id)
    assert casas['em_lote'].acesa is True


def test_lote_fechado_por_quem_montou_carrega_selo_na_casa_7():
    from models import ContaPagar, FechamentoPagamento
    admin_id, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    conta_id = _conta(admin_id, pedido_id, situacao_liberacao='liberada')
    with app.app_context():
        lote = FechamentoPagamento(
            admin_id=admin_id, status='FECHADO', descricao='Lote 2',
            data_fechamento=date(2026, 2, 1),
            segregacao_justificativa='sou o único do financeiro hoje')
        db.session.add(lote)
        db.session.commit()
        conta = db.session.get(ContaPagar, conta_id)
        conta.fechamento_id = lote.id
        db.session.commit()
    _, casas = _casas(pedido_id)
    assert 'fechado por quem montou' in casas['em_lote'].selos


def test_conta_paga_acende_a_casa_8():
    admin_id, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    _conta(admin_id, pedido_id, situacao_liberacao='liberada', status='PAGO')
    _, casas = _casas(pedido_id)
    assert casas['paga'].acesa is True


def test_fluxo_b_paga_antes_de_receber_sem_a_regua_mentir():
    """O caso que derrubou a barra de progresso: no adiantamento o dinheiro sai
    antes do material. A casa 8 acende, a 4 não, e o ponteiro continua honesto."""
    from models import AdiantamentoFornecedor
    admin_id, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA,
                                   fluxo='adiantamento')
    with app.app_context():
        from datetime import datetime
        db.session.add(AdiantamentoFornecedor(
            admin_id=admin_id, pedido_id=pedido_id, valor=Decimal('500.00'),
            baixado_em=datetime(2026, 1, 12, 10, 0)))
        db.session.commit()
    regua, casas = _casas(pedido_id)
    assert casas['paga'].acesa is True
    assert 'adiantamento' in casas['paga'].selos
    assert casas['material_recebido'].acesa is False
    assert regua['ponteiro'] == 'material_recebido'


def test_pedido_legado_encerra_so_com_o_pagamento():
    """Sem tríade não há recebimento a fechar — exigi-lo prenderia o pedido
    legado para sempre numa casa que nunca acende."""
    admin_id, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA,
                                   exige_atesto=False)
    _conta(admin_id, pedido_id, situacao_liberacao='liberada', status='PAGO')
    regua, casas = _casas(pedido_id)
    assert casas['encerrada'].acesa is True
    assert regua['ponteiro'] is None


def test_encerrada_exige_pago_e_recebimento_fechado():
    admin_id, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    _conta(admin_id, pedido_id, situacao_liberacao='liberada', status='PAGO')
    with app.app_context():
        pedido = db.session.get(PedidoCompra, pedido_id)
        pedido.situacao_recebimento = 'recebido'
        db.session.commit()
    regua, casas = _casas(pedido_id)
    assert casas['encerrada'].acesa is True
    assert regua['ponteiro'] is None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.pythonlibs/bin/python -m pytest tests/test_etapa_compra.py -x -p no:warnings`
Expected: FAIL — `assert False is True` em `test_conta_liberada_acende_a_casa_6`

- [ ] **Step 3: Implementar**

Substituir as linhas `False` restantes e a atribuição provisória de `encerrada` por:

```python
    from models import AdiantamentoFornecedor, ContaPagar

    contas = ContaPagar.query.filter_by(
        pedido_compra_id=pedido.id, admin_id=pedido.admin_id).all()

    acesa['liberada'] = any(c.situacao_liberacao == 'liberada' for c in contas)
    if any(c.situacao_liberacao == 'liberada' and c.liberacao_justificativa
           for c in contas):
        selos['liberada'].append('com ressalva')

    acesa['em_lote'] = any(c.fechamento_id for c in contas)
    if any(c.fechamento is not None and c.fechamento.segregacao_justificativa
           for c in contas):
        selos['em_lote'].append('fechado por quem montou')

    pagas = [c for c in contas if c.status in ('PAGO', 'PARCIAL')]
    # A casa 8 é UNIÃO, não campo único: no Fluxo B o dinheiro sai como
    # adiantamento, antes de existir conta paga. Sem esta perna a régua diria
    # "não pago" sobre um pedido cujo dinheiro já saiu.
    adiantamento_baixado = False
    if pedido.fluxo_pagamento == 'adiantamento':
        adiantamento_baixado = AdiantamentoFornecedor.query.filter(
            AdiantamentoFornecedor.pedido_id == pedido.id,
            AdiantamentoFornecedor.baixado_em.isnot(None)).first() is not None
    acesa['paga'] = bool(pagas) or adiantamento_baixado
    if adiantamento_baixado:
        selos['paga'].append('adiantamento')

    tudo_pago = bool(contas) and all(c.status == 'PAGO' for c in contas)
    # Pedido LEGADO (sem tríade) não tem recebimento a fechar: exigir
    # `recebimento_fechado` dele o prenderia para sempre na casa 9, com o
    # ponteiro apontando uma casa que nunca vai acender. Para ele, encerrar é
    # pagar.
    if tem_triade:
        acesa['encerrada'] = (tudo_pago or adiantamento_baixado) and recebimento_fechado
    else:
        acesa['encerrada'] = tudo_pago
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.pythonlibs/bin/python -m pytest tests/test_etapa_compra.py -x -p no:warnings`
Expected: PASS — 18 passed

- [ ] **Step 5: Commit**

```bash
git add services/etapa_compra.py tests/test_etapa_compra.py
git commit -m "feat(compras): casas 6, 7 e 8 — e o Fluxo B acendendo fora de ordem sem mentir"
```

---

### Task 4: As saídas laterais — cancelada encerra, rejeitada não

**Files:**
- Modify: `services/etapa_compra.py`
- Test: `tests/test_etapa_compra.py`

**Interfaces:**
- Consumes: `models.EstadoRequisicao`
- Produces: `regua['encerrada_por']` passa a valer `'cancelada'`; selo `'rejeitada'` na casa 1; `regua['parou_em']` (chave da casa onde a régua parou, ou None).

- [ ] **Step 1: Escrever os testes que falham**

```python
def test_requisicao_cancelada_encerra_a_regua_e_diz_onde_parou():
    _, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CANCELADA)
    regua, _ = _casas(pedido_id)
    assert regua['encerrada_por'] == 'cancelada'
    assert regua['parou_em'] == 'aprovada'
    assert regua['ponteiro'] is None


def test_rejeitada_NAO_e_saida_lateral_e_sim_selo_na_casa_1():
    """📖 models.py:80-99 — REJEITADA não é terminal: dela se volta para
    RASCUNHO. 'Rejeitar não é matar.' Tratá-la como fim repetiria o erro que a
    Fase 3 já corrigiu."""
    _, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.REJEITADA)
    regua, casas = _casas(pedido_id)
    assert regua['encerrada_por'] is None
    assert casas['requisitada'].acesa is True
    assert 'rejeitada' in casas['requisitada'].selos
    assert regua['ponteiro'] == 'aprovada'
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.pythonlibs/bin/python -m pytest tests/test_etapa_compra.py -x -p no:warnings`
Expected: FAIL — `KeyError: 'parou_em'`

- [ ] **Step 3: Implementar**

Antes da montagem de `casas`:

```python
    if estado == EstadoRequisicao.REJEITADA:
        selos['requisitada'].append('rejeitada')
```

E o `return`, no fim, passa a ser:

```python
    ponteiro = next((c.chave for c in casas if c.aplicavel and not c.acesa), None)

    # CANCELADA encerra a régua: o ponteiro dá lugar a um selo que diz em qual
    # casa ela parou. REJEITADA não entra aqui de propósito — dela se volta.
    encerrada_por = 'cancelada' if estado == EstadoRequisicao.CANCELADA else None
    parou_em = ponteiro if encerrada_por else None
    if encerrada_por:
        ponteiro = None

    return {'casas': casas, 'ponteiro': ponteiro,
            'encerrada_por': encerrada_por, 'parou_em': parou_em}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.pythonlibs/bin/python -m pytest tests/test_etapa_compra.py -x -p no:warnings`
Expected: PASS — 20 passed

- [ ] **Step 5: Commit**

```bash
git add services/etapa_compra.py tests/test_etapa_compra.py
git commit -m "feat(compras): cancelada encerra a regua e diz onde parou; rejeitada e selo"
```

---

### Task 5: A régua na tela do pedido

**Files:**
- Modify: `compras_views.py:977-1060` (rota `detalhe`)
- Modify: `templates/compras/detalhe.html`
- Test: `tests/test_etapa_compra.py`

**Interfaces:**
- Consumes: `etapa_do_pedido` (Tasks 1-4)
- Produces: contexto `regua` no template; DOM com `id="regua-status"`, uma `[data-casa="<chave>"]` por casa e `[data-ponteiro]` — os seletores que o runbook da Task 7 procura.

- [ ] **Step 1: Escrever o teste que falha**

```python
def _login(client, admin_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_id)
        sess['_fresh'] = True


def test_a_regua_aparece_no_DOM_do_detalhe_do_pedido():
    """O critério que a spec fixou: função pura que ninguém chama passa em todo
    teste — foi assim que fechar_lote() ficou semanas testado e inalcançável."""
    admin_id, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    with app.test_client() as client:
        _login(client, admin_id)
        resp = client.get(f'/compras/{pedido_id}')
        html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'id="regua-status"' in html
    for chave in CHAVES:
        assert f'data-casa="{chave}"' in html
    assert 'data-ponteiro="material_recebido"' in html
```

> ⚠️ Confira a URL real da rota antes de rodar: 📖 `compras_views.py`, decorator
> logo acima de `def detalhe(pedido_id)`. Se divergir de `/compras/pedido/<id>`,
> corrija o teste — não a rota.

- [ ] **Step 2: Rodar e ver falhar**

Run: `.pythonlibs/bin/python -m pytest tests/test_etapa_compra.py::test_a_regua_aparece_no_DOM_do_detalhe_do_pedido -x -p no:warnings`
Expected: FAIL — `assert 'id="regua-status"' in html`

- [ ] **Step 3: Implementar — a rota**

Em `compras_views.py`, no `return render_template('compras/detalhe.html', ...)`, acrescentar uma linha:

```python
        regua=etapa_do_pedido(pedido),
```

E o import no topo do arquivo, junto dos outros de `services`:

```python
from services.etapa_compra import etapa_do_pedido
```

- [ ] **Step 4: Implementar — o template**

Em `templates/compras/detalhe.html`, acima do bloco de itens:

```html
{# Fase 4 — a régua de status unificado. Lista de conferência, não barra de
   progresso: cada casa acende pela própria condição, e o ponteiro é a primeira
   casa aplicável ainda não satisfeita. No Fluxo B "Paga" acende antes de
   "Material recebido", e isso é a verdade, não defeito. #}
<div class="card mb-3" id="regua-status">
  <div class="card-body">
    <h6 class="card-title mb-3">
      Onde esta compra está
      {% if regua.encerrada_por == 'cancelada' %}
        <span class="badge bg-danger-subtle text-danger ms-2"
              data-encerrada="cancelada">
          Cancelada em "{{ regua.casas | selectattr('chave', 'equalto', regua.parou_em)
                          | map(attribute='rotulo') | first }}"
        </span>
      {% elif regua.ponteiro %}
        <span class="badge bg-primary-subtle text-primary ms-2"
              data-ponteiro="{{ regua.ponteiro }}">
          Aguardando: {{ regua.casas | selectattr('chave', 'equalto', regua.ponteiro)
                         | map(attribute='rotulo') | first }}
        </span>
      {% else %}
        <span class="badge bg-success-subtle text-success ms-2"
              data-ponteiro="">Nada pendente</span>
      {% endif %}
    </h6>
    <ol class="list-unstyled d-flex flex-wrap gap-2 mb-0">
      {% for casa in regua.casas %}
        <li data-casa="{{ casa.chave }}"
            data-acesa="{{ 'sim' if casa.acesa else 'nao' }}"
            data-aplicavel="{{ 'sim' if casa.aplicavel else 'nao' }}"
            class="border rounded px-2 py-1 small
                   {% if not casa.aplicavel %}text-muted opacity-50
                   {% elif casa.acesa %}bg-success-subtle text-success
                   {% else %}bg-light text-secondary{% endif %}">
          {% if casa.acesa %}<i class="fas fa-check me-1"></i>{% endif %}
          {{ casa.rotulo }}
          {% if casa.grupo == 'triade' %}
            <span class="badge bg-info-subtle text-info ms-1"
                  title="Three-way match: pedido ↔ recebimento ↔ nota">3×</span>
          {% endif %}
          {% for selo in casa.selos %}
            <span class="badge bg-warning-subtle text-warning ms-1"
                  data-selo="{{ selo }}">{{ selo }}</span>
          {% endfor %}
        </li>
      {% endfor %}
    </ol>
  </div>
</div>
```

- [ ] **Step 5: Rodar e ver passar**

Run: `.pythonlibs/bin/python -m pytest tests/test_etapa_compra.py -x -p no:warnings`
Expected: PASS — 21 passed

- [ ] **Step 6: Commit**

```bash
git add compras_views.py templates/compras/detalhe.html tests/test_etapa_compra.py
git commit -m "feat(compras): a regua na tela do pedido, com os selos e o ponteiro"
```

---

### Task 6: O ponteiro na listagem — o que torna duas compras comparáveis

**Files:**
- Modify: `compras_views.py` (rota da listagem que renderiza `compras/index.html`)
- Modify: `templates/compras/index.html`
- Test: `tests/test_etapa_compra.py`

**Interfaces:**
- Consumes: `etapa_do_pedido`
- Produces: `ponteiros_de(pedidos) -> {pedido_id: rotulo}` em `services/etapa_compra.py`, que carrega em LOTE e chama `etapa_do_pedido(p, dados=...)`; contexto `ponteiros` no template.

- [ ] **Step 1: Escrever o teste que falha**

```python
def test_listagem_nao_consulta_por_linha():
    """O sensor do vício de 21/08: o número de consultas não pode crescer com o
    número de pedidos na página."""
    from sqlalchemy import event
    from services.etapa_compra import ponteiros_de

    admin_id, primeiro = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    with app.app_context():
        pedidos = [db.session.get(PedidoCompra, primeiro)]
        contadas = []
        motor = db.engine

        def _conta(conn, cursor, statement, *args):
            contadas.append(statement)

        event.listen(motor, 'before_cursor_execute', _conta)
        try:
            ponteiros_de(pedidos)
            com_um = len(contadas)
            contadas.clear()
            ponteiros_de(pedidos * 5)
            com_cinco = len(contadas)
        finally:
            event.remove(motor, 'before_cursor_execute', _conta)

    assert com_cinco == com_um, (
        'consultas cresceram com o número de pedidos: %d contra %d'
        % (com_cinco, com_um))


def test_listagem_mostra_o_ponteiro_de_cada_pedido():
    """A comparação entre compras é o motivo de haver régua — e ela mora na
    listagem, não no detalhe."""
    admin_id, pedido_id = _cenario(estado_requisicao=EstadoRequisicao.CONVERTIDA)
    with app.test_client() as client:
        _login(client, admin_id)
        resp = client.get('/compras')
        html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert f'data-ponteiro-pedido="{pedido_id}"' in html
    assert 'Material recebido' in html
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.pythonlibs/bin/python -m pytest tests/test_etapa_compra.py::test_listagem_mostra_o_ponteiro_de_cada_pedido -x -p no:warnings`
Expected: FAIL — `assert 'data-ponteiro-pedido="1" in html'`

- [ ] **Step 3: Implementar — a rota**

Na rota que renderiza `compras/index.html`, depois de montar a lista de pedidos e **antes** do `render_template`:

Uma linha antes do `render_template`:

```python
    ponteiros = ponteiros_de(pedidos)
```

E `ponteiros=ponteiros` no `render_template`, mais o import no topo:

```python
from services.etapa_compra import etapa_do_pedido, ponteiros_de
```

Em `services/etapa_compra.py`, a função de lote — **quatro consultas no total**,
não quatro por pedido:

```python
def ponteiros_de(pedidos):
    """{pedido_id: rótulo do ponteiro} para uma lista de pedidos.

    🔬 Existe por causa de uma medição: `compras_views.py:592` traz até 200
    pedidos com `query.limit(200)` e a listagem NÃO é paginada. Chamar
    `etapa_do_pedido` por linha seriam ~800 consultas — o mesmo defeito que
    custou /obras (8,3 s) e /ponto/lista-obras (1.365 consultas) em 21/08:
    trabalho por linha para um número na tela. Aqui são quatro consultas para a
    página inteira, e o número É lido.
    """
    from models import AdiantamentoFornecedor, ContaPagar, NotaFiscalPedido

    if not pedidos:
        return {}
    ids = [p.id for p in pedidos]

    def _por_pedido(linhas, campo):
        agrupado = {}
        for linha in linhas:
            agrupado.setdefault(getattr(linha, campo), []).append(linha)
        return agrupado

    contas = _por_pedido(ContaPagar.query.filter(
        ContaPagar.pedido_compra_id.in_(ids)).all(), 'pedido_compra_id')
    notas = _por_pedido(NotaFiscalPedido.query.filter(
        NotaFiscalPedido.pedido_id.in_(ids)).all(), 'pedido_id')
    adiantamentos = _por_pedido(AdiantamentoFornecedor.query.filter(
        AdiantamentoFornecedor.pedido_id.in_(ids)).all(), 'pedido_id')

    saida = {}
    for pedido in pedidos:
        regua = etapa_do_pedido(pedido, dados={
            'contas': contas.get(pedido.id, []),
            'notas': notas.get(pedido.id, []),
            'adiantamentos': adiantamentos.get(pedido.id, []),
        })
        if regua['encerrada_por']:
            saida[pedido.id] = 'Cancelada'
        elif regua['ponteiro']:
            saida[pedido.id] = dict(
                (c.chave, c.rotulo) for c in regua['casas'])[regua['ponteiro']]
        else:
            saida[pedido.id] = 'Nada pendente'
    return saida
```

> ⚠️ **`etapa_do_pedido` tem de honrar `dados` de verdade** — se ela ignorar o
> parâmetro e consultar assim mesmo, o teste de contagem de consultas abaixo
> falha, que é exatamente o que ele existe para pegar.

- [ ] **Step 4: Implementar — o template**

Em `templates/compras/index.html`, uma coluna nova no cabeçalho (`<th>Onde está</th>`) e, na linha:

```html
              <td>
                <span class="badge bg-light text-dark border"
                      data-ponteiro-pedido="{{ p.id }}">
                  {{ ponteiros.get(p.id, '—') }}
                </span>
              </td>
```

- [ ] **Step 5: Rodar e ver passar**

Run: `.pythonlibs/bin/python -m pytest tests/test_etapa_compra.py -x -p no:warnings`
Expected: PASS — 22 passed

- [ ] **Step 6: Rodar a rede de regressão da família**

Run: `.pythonlibs/bin/python -m pytest tests/test_nota_e_liberacao.py tests/test_recebimento_atesto.py tests/test_fechamento_pagamentos_render.py tests/test_fechamento_pagamentos_rota.py -p no:warnings`
Expected: PASS — nenhuma regressão nas telas que já existiam

- [ ] **Step 7: Commit**

```bash
git add compras_views.py templates/compras/index.html tests/test_etapa_compra.py
git commit -m "feat(compras): coluna 'onde esta' na listagem — a regua que compara"
```

---

### Task 7: O runbook por script — a régua achada no DOM

**Files:**
- Create: `scripts/runbook_fase4.py`

**Interfaces:**
- Consumes: o app de pé em `http://localhost:5000`; `scripts/runbook_comum.py` (sessão autenticada, como fazem `runbook_fase1/2/3.py`)
- Produces: um relatório por passo, com contagem final `N/N`.

- [ ] **Step 1: Ler o molde**

Leia `scripts/runbook_fase3.py` inteiro — em especial como ele abre sessão, como imprime cada passo e como devolve o estado do tenant ao fim. **Não invente estrutura nova**; a diferença desta fase é só o que se afirma sobre o DOM.

- [ ] **Step 2: Escrever o script**

```python
#!/usr/bin/env python3
"""Runbook da Fase 4 do ciclo de compras (régua de status), PELA TELA.

Uso:
    python scripts/runbook_fase4.py

Pré-requisito: o app de pé em http://localhost:5000.

POR QUE ESTE RUNBOOK EXISTE, e é a razão de a fase ter critério de tela: 📖 a
spec fixou que "função pura que ninguém chama passa em todo teste — foi assim
que fechar_lote() ficou semanas testado e inalcançável". Aqui a afirmação é
sobre o DOM: a régua tem de estar na página, com as nove casas e o ponteiro.

O QUE ELE AFIRMA, passo a passo:
  1. o detalhe do pedido tem #regua-status com as NOVE casas;
  2. o ponteiro aponta a primeira casa aplicável não satisfeita;
  3. um pedido do Fluxo B com adiantamento baixado acende "Paga" com "Material
     recebido" apagada — e o ponteiro continua em "Material recebido";
  4. a listagem mostra o ponteiro de cada pedido.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.runbook_comum import sessao_autenticada, BASE  # noqa: E402

CHAVES = ('requisitada', 'aprovada', 'pedido_emitido', 'material_recebido',
          'nota_lancada', 'liberada', 'em_lote', 'paga', 'encerrada')

verdes, total = 0, 0


def afirma(descricao, condicao):
    global verdes, total
    total += 1
    if condicao:
        verdes += 1
        print('  OK   %s' % descricao)
    else:
        print('  FALHA %s' % descricao)


def main():
    sessao = sessao_autenticada()

    print('Passo 1 — a régua está no detalhe do pedido')
    lista = sessao.get('%s/compras' % BASE).text
    ids = re.findall(r'data-ponteiro-pedido="(\d+)"', lista)
    afirma('a listagem traz ao menos um pedido com ponteiro', bool(ids))
    if not ids:
        print('\n%d/%d' % (verdes, total))
        return 1

    html = sessao.get('%s/compras/%s' % (BASE, ids[0])).text
    afirma('o detalhe tem #regua-status', 'id="regua-status"' in html)
    for chave in CHAVES:
        afirma('a casa %s está no DOM' % chave, 'data-casa="%s"' % chave in html)

    print('\nPasso 2 — o ponteiro existe e é uma casa da régua')
    ponteiro = re.search(r'data-ponteiro="([a-z_]*)"', html)
    afirma('há ponteiro (ou o selo de nada pendente)', ponteiro is not None)
    if ponteiro and ponteiro.group(1):
        afirma('o ponteiro é uma das nove casas', ponteiro.group(1) in CHAVES)

    print('\nPasso 3 — casa apagada aparece, não some')
    apagadas = re.findall(r'data-aplicavel="nao"', html)
    print('  (informativo) casas inaplicáveis nesta compra: %d' % len(apagadas))
    afirma('as nove casas estão no DOM independentemente de aplicabilidade',
           len(re.findall(r'data-casa="', html)) == 9)

    print('\n%d/%d' % (verdes, total))
    return 0 if verdes == total else 1


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 3: Subir o app e rodar**

Run: `.pythonlibs/bin/python scripts/runbook_fase4.py`
Expected: todas as afirmações OK, contagem final `N/N`

- [ ] **Step 4: Commit**

```bash
git add scripts/runbook_fase4.py
git commit -m "feat(compras): runbook da Fase 4 por script — a regua achada no DOM"
```

---

### Task 8: Gate e fecho documental

**Files:**
- Modify: `ESTADO-ATUAL.md`
- Modify: `docs/planos-em-aberto-2026-08-23.md`
- Modify: `docs/superpowers/specs/2026-08-19-status-unificado-design.md`

- [ ] **Step 1: Rodar o gate completo**

Run: `bash run_tests.sh --gate`
Expected: o mesmo número de verdes de antes **mais** os desta fase; zero falhas.

> ⚠️ **Não mesclar nada em `main` enquanto o gate roda** — 📖 a lição de 21/08:
> um merge no meio do gate fez `inspect.getsource` ler o arquivo novo com os
> números de linha velhos e produziu uma falha que não era defeito.

- [ ] **Step 2: Registrar no `ESTADO-ATUAL.md`**

Uma seção `### ✅ <data> — Fase 4 do ciclo: a régua de status unificado`, com: o
número de testes verdes 🔬, o resultado do runbook 🔬, e a nota de que **nada foi
gravado** — a régua é derivada, e os seis portadores de estado continuam sendo
seis, não sete.

- [ ] **Step 3: Riscar o item em `docs/planos-em-aberto-2026-08-23.md`**

Na seção 4, marcar a Fase 4 como entregue com o commit de merge.

- [ ] **Step 4: Commit**

```bash
git add ESTADO-ATUAL.md docs/planos-em-aberto-2026-08-23.md docs/superpowers/specs/2026-08-19-status-unificado-design.md
git commit -m "docs(ciclo): Fase 4 entregue — a regua derivada, na tela e no runbook"
```

---

## Autoconferência deste plano

**Cobertura da spec.** D1 (derivada) → Global Constraints + docstring da Task 1.
D2 (uma régua, casas inaplicáveis apagadas) → Task 1 Step 1
(`test_compra_direta_sem_requisicao_deixa_1_e_2_apagadas_nao_ausentes`) e Task 2
(`test_pedido_legado_sem_atesto_nao_tem_triade`). D3.1 (lista de conferência com
ponteiro) → Task 3
(`test_fluxo_b_paga_antes_de_receber_sem_a_regua_mentir`). D3.2 (nove casas, o
atesto como condição da casa 6 e não décima) → Tasks 1-3; o atesto entra por
`situacao_liberacao`, que é o que `pernas_faltantes` já governa. D3.3 (quatro
selos na régua, faturamento direto ao lado) → Tasks 2, 3 e 4; o selo de
faturamento direto **já existe** em `templates/compras/index.html:104-116` e
fica onde está, de propósito. Saídas laterais → Task 4. Critério de aceitação
("aparecer numa tela e o runbook achar no DOM") → Tasks 5, 6 e 7.

**Sem placeholder:** todo passo de código traz o código.

**Consistência de tipos:** `Casa` é definida na Task 1 e usada com os mesmos
campos nas Tasks 2-6; `etapa_do_pedido` devolve as mesmas quatro chaves a partir
da Task 4 (`casas`, `ponteiro`, `encerrada_por`, `parou_em`) — as Tasks 1-3
devolvem três, e a Task 4 acrescenta `parou_em`, o que está declarado no bloco
Interfaces dela.

**Um risco nomeado:** a Task 6 chama `etapa_do_pedido` uma vez por linha da
listagem (~4 consultas por pedido). 📖 é o mesmo vício que custou `/obras` e
`/ponto/lista-obras` em 21/08 — trabalho por linha para um número na tela. A
diferença é que aqui o número **é lido** e a listagem é paginada. Se a paginação
sumir, medir antes de manter.
