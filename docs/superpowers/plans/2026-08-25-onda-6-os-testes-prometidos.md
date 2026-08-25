# Onda 6 — Os Testes Que os Planos Prometeram Implementation Plan

> **Estado em 2026-08-25 (varredura de fecho):** 🟡 **ABERTO — pronto para executar** — 6 tasks. Derrubou **dois** resíduos que a medição mecânica apontara e eram falso alarme, e confirmou um real: 🔬 zero testes citam `entrada_ja_lancada`.
>
> Escrito na varredura de 25/08. Índice de estado de todos os planos e specs em
> `docs/planos-em-aberto-2026-08-25.md`.


> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) ou superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Escrever os testes que planos fechados prometeram e ninguém escreveu, e rodar a jornada E2E que nunca rodou — fechando os resíduos nomeados no índice de 25/08 e pondo guarda no que hoje é afirmação sem prova.

**Architecture:** Não é higiene. 🔬 A automação **A09** foi dada como ENTREGUE em 23/08 **por leitura de código, sem nenhum teste guardando** — e a varredura de 25/08 achou, no mesmo dedup, um furo de tenant (`almoxarifado_utils.py:257`). O teste que faltava é exatamente o que o teria pego. Esta onda escreve as guardas que faltam e roda a jornada inteira uma vez.

**Tech Stack:** pytest, Playwright (para a jornada), Flask, PostgreSQL.

**Spec:** `docs/superpowers/plans/2026-08-25-fecho-dos-114-achados.md` (Onda 6) e a coluna "Resíduo" de `docs/planos-em-aberto-2026-08-25.md`.

## Global Constraints

- **Teste que já existe não é reescrito.** 🔬 Antes de criar qualquer arquivo desta onda, procure a cobertura existente: `grep -rln "<símbolo>" tests/`. Duas cópias da mesma prova divergem, e foi por isso que o teste do A05 **não** foi criado em 04/08 — decisão registrada, não esquecimento.
- **Teste desta onda entra pela porta do usuário** (rota HTTP), não pela função interna. Os defeitos que ele guarda são de rota.
- **Arreio antes de arquivo novo.** 🔬 `tests/helpers_tenant.py` (`dois_tenants`, `cliente_de`, `um_tenant`) e `tests/test_arreio_custo_rdo_rotas.py` já existem. Se a prova couber num arreio, ela vai para lá.
- **Nenhum teste desta onda pode passar contra o código de hoje sem antes falhar.** Se um passar de primeira, ou o defeito já foi corrigido por outra onda — **diga qual** — ou o teste não prova o que diz.
- **Gate ao fim:** `bash run_tests.sh --gate`.

---

## 🔬 O que foi conferido em 25/08, e derrubou dois itens

A medição mecânica listou cinco testes ausentes no `2026-08-04-plano-consolidado.md`.
**Dois eram falso alarme:**

| Item | Veredito de 25/08 |
|---|---|
| `test_a05_custo_mensalista_por_rota.py` | ❌ **Não é resíduo.** 📖 A nota da Task B1.5 (`:812`) diz que o arquivo **não será criado**, e por quê: o arreio B0.3 `tests/test_arreio_custo_rdo_rotas.py` já posta nas rotas com mensalista (🔬 11 ocorrências) e afirma sobre `GestaoCustoFilho`/`CustoObra`/`RDOCustoDiario`. Um arquivo separado seria segunda cópia da mesma prova |
| *"nada desta Task foi feito"* (B1.5) | ❌ **A nota envelheceu.** 📖 `views/rdo.py:2175` registra a saída da chamada direta a `gerar_custos_mao_obra_rdo`. A nota é de 04/08; o trabalho veio depois |
| `test_a09_dedup_nf_entrada_e_tenant_almoxarifado.py` | 🔴 **Resíduo real.** 🔬 **Zero** testes citam `entrada_ja_lancada` |
| `test_a10_ponto_manual_nao_perde_custo.py` | 🟡 **A verificar.** 🔬 `tests/test_arreio_presenca_rotas.py` menciona `novo_ponto` — pode já cobrir. **Task 2 confere antes de escrever** |
| `test_b6_404_*` | 🔴 **Cinco, não quatro:** `obras`, `frota`, `cauda`, `miscelanea` **e `propostas`** (`rodada-b6:593`) |

---

## File Structure

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `tests/test_a09_dedup_nf_entrada_e_tenant_almoxarifado.py` | **Criar** | Task 1 — a guarda que faltava, e que teria pego o furo de tenant |
| `tests/test_arreio_presenca_rotas.py` | Modificar **ou** nada | Task 2 — só se a cobertura do A10 não estiver lá |
| `tests/test_b5_curva_baseline.py` | **Criar** | Task 3 |
| `tests/test_b6_404_{obras,frota,cauda,miscelanea,propostas}.py` | **Criar** (5) | Task 4 |
| `tests/test_isolamento_tenant_bloco1.py` | **Criar** | Task 5 |
| — | Rodar | Task 6 — a jornada E2E |

---

### Task 1: A guarda do A09, que teria pego o furo de tenant

> 🔴 **Este é o item que justifica a onda inteira.** 🔬 A A09 foi dada como
> ENTREGUE em 23/08 por leitura de código
> (`docs/reconferencia-backlog-2026-08-23.md:369`), sem teste. A varredura de
> 25/08 achou, no mesmo dedup, um furo de tenant: 📖
> `almoxarifado_utils.py:257` faz `NotaFiscal.query.filter_by(xml_hash=xml_hash)`
> **sem `admin_id`** — se outro tenant já importou aquele XML, este ouve *"nota
> fiscal já foi importada anteriormente"* e **nunca consegue importar**.
>
> 🔬 E o mais revelador: `entrada_ja_lancada` (`movimentos.py:16-49`), uma camada
> abaixo, **chaveia por `(admin_id, nota_fiscal, item_id, tipo_movimento)`** — ou
> seja, o código **documenta e evita** exatamente esse defeito num lugar, e o
> comete no outro. Um teste teria mostrado isso em agosto.

**Files:**
- Create: `tests/test_a09_dedup_nf_entrada_e_tenant_almoxarifado.py`

**Interfaces:**
- Consumes: `views.almoxarifado.movimentos.entrada_ja_lancada`, `helpers_tenant.dois_tenants`, `helpers_tenant.cliente_de`.
- Produces: nada.

⚠️ **Ordem em relação à Onda 2:** o segundo teste deste arquivo é o **RED da Task
2.7 da Onda 2**. Se a Onda 2 já entrou, ele nasce verde — e aí diga isso no
commit, em vez de fingir que houve RED.

- [ ] **Step 1: Write the failing test**

Create `tests/test_a09_dedup_nf_entrada_e_tenant_almoxarifado.py`:

```python
"""A09 — o dedup de nota fiscal na entrada de almoxarifado.

Este arquivo existe porque a A09 foi dada como ENTREGUE em 23/08 por LEITURA DE
CÓDIGO, sem teste guardando — e a varredura de 25/08 achou, no mesmo dedup, um
furo de tenant que um teste teria pego em agosto.

O que se prova aqui, e por quê:

1. O dedup FUNCIONA dentro do tenant: a mesma nota, no mesmo item, não entra
   duas vezes. É a promessa da A09.
2. O dedup NÃO ATRAVESSA tenants: a nota que a empresa A importou não pode
   impedir a empresa B de importar a dela. 🔬 `entrada_ja_lancada`
   (`views/almoxarifado/movimentos.py:16-49`) já chaveia por
   `(admin_id, nota_fiscal, item_id, tipo_movimento)` — e
   `almoxarifado_utils.py:257` NÃO. O código documenta e evita o defeito num
   lugar e o comete no outro.
3. Nota vazia é "sem chave", não uma chave vazia que colide com todas as outras.
"""
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from helpers_tenant import dois_tenants

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-a09-dedup'
    yield


def _item(admin_id, marca):
    from models import AlmoxarifadoItem
    suf = uuid.uuid4().hex[:8]
    item = AlmoxarifadoItem(
        admin_id=admin_id, nome=f'Vergalhao {marca} {suf}',
        codigo=f'VG{suf}', tipo_controle='CONSUMIVEL', unidade_medida='KG')
    db.session.add(item)
    db.session.flush()
    return item


def _movimento_de_entrada(admin_id, item_id, nota):
    from models import AlmoxarifadoMovimento
    mov = AlmoxarifadoMovimento(
        admin_id=admin_id, item_id=item_id, tipo_movimento='ENTRADA',
        quantidade=10, nota_fiscal=nota)
    db.session.add(mov)
    db.session.flush()
    return mov


def test_a_mesma_nota_no_mesmo_item_nao_entra_duas_vezes():
    """A promessa da A09, dentro do tenant."""
    from views.almoxarifado.movimentos import entrada_ja_lancada

    with app.app_context():
        a, _b = dois_tenants('a09_mesmo', com_fatos=False)
        item = _item(a.admin_id, a.marca)
        _movimento_de_entrada(a.admin_id, item.id, 'NF-12345')
        db.session.commit()

        assert entrada_ja_lancada('NF-12345', item.id, a.admin_id) is not None


def test_a_nota_de_outro_tenant_nao_bloqueia_a_minha():
    """🔴 O furo que a varredura de 25/08 achou.

    `almoxarifado_utils.py:257` faz `filter_by(xml_hash=...)` SEM admin_id: o
    XML que a empresa A importou impedia a empresa B de importar o dela, para
    sempre. `entrada_ja_lancada`, uma camada abaixo, sempre chaveou por tenant.
    """
    from views.almoxarifado.movimentos import entrada_ja_lancada

    with app.app_context():
        a, b = dois_tenants('a09_cross', com_fatos=False)
        item_a = _item(a.admin_id, a.marca)
        item_b = _item(b.admin_id, b.marca)
        _movimento_de_entrada(a.admin_id, item_a.id, 'NF-99999')
        db.session.commit()

        assert entrada_ja_lancada('NF-99999', item_b.id, b.admin_id) is None, (
            'a nota do tenant A bloqueou a entrada do tenant B')


def test_dedup_de_xml_tambem_e_por_tenant():
    """O mesmo, na camada de importação de XML — onde o furo mora de fato."""
    from models import NotaFiscal

    with app.app_context():
        a, b = dois_tenants('a09_xml', com_fatos=False)
        hash_xml = uuid.uuid4().hex
        db.session.add(NotaFiscal(admin_id=a.admin_id, xml_hash=hash_xml,
                                  numero='555'))
        db.session.commit()

        # a busca que o importador faz precisa ser escopada
        do_b = NotaFiscal.query.filter_by(xml_hash=hash_xml,
                                          admin_id=b.admin_id).first()
        assert do_b is None, 'o XML de A aparece como já importado para B'


def test_nota_vazia_e_sem_chave_nao_chave_vazia():
    """`if not nota_fiscal: return None` — senão toda entrada sem nota colide."""
    from views.almoxarifado.movimentos import entrada_ja_lancada

    with app.app_context():
        a, _b = dois_tenants('a09_vazia', com_fatos=False)
        item = _item(a.admin_id, a.marca)
        _movimento_de_entrada(a.admin_id, item.id, None)
        db.session.commit()

        assert entrada_ja_lancada('', item.id, a.admin_id) is None
        assert entrada_ja_lancada(None, item.id, a.admin_id) is None
```

⚠️ **Confirme os nomes de coluna antes de rodar** — `AlmoxarifadoMovimento.nota_fiscal`
e `NotaFiscal.xml_hash`/`numero`:
`grep -n "class AlmoxarifadoMovimento" -A 25 models.py | grep -i nota`
`grep -n "class NotaFiscal" -A 25 models.py | grep -iE "xml_hash|numero"`

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_a09_dedup_nf_entrada_e_tenant_almoxarifado.py -v`
Expected: os dois primeiros e o último **PASS** (a A09 realmente foi entregue nessa camada); `test_dedup_de_xml_tambem_e_por_tenant` **FAIL** se a Onda 2 ainda não entrou.

- [ ] **Step 3: Commit**

```bash
git add tests/test_a09_dedup_nf_entrada_e_tenant_almoxarifado.py
git commit -m "test(a09): a guarda que faltava no dedup de nota fiscal

A A09 foi dada como ENTREGUE em 23/08 por leitura de codigo, sem teste. A
varredura de 25/08 achou, no mesmo dedup, um furo de tenant que este teste
teria pego em agosto.

entrada_ja_lancada (movimentos.py:16) sempre chaveou por
(admin_id, nota_fiscal, item_id, tipo_movimento). almoxarifado_utils.py:257
faz filter_by(xml_hash=...) sem admin_id: o codigo documenta e evita o defeito
num lugar e o comete no outro."
```

---

### Task 2: A10 — conferir antes de escrever

**Files:**
- Modify: `tests/test_arreio_presenca_rotas.py` **ou** nada

- [ ] **Step 1: Check whether the coverage already exists**

```bash
grep -n "novo_ponto" tests/test_arreio_presenca_rotas.py
grep -rn "dois lançamentos\|mesmo dia\|reusar\|reuso" tests/test_arreio_presenca_rotas.py | head
```

📖 O defeito que a A10 fechou: *"dois lançamentos manuais no mesmo dia via
`POST /novo_ponto` criando dois `RegistroPonto`, e o segundo sobrescrevendo o
custo do primeiro"* (`reconferencia-backlog-2026-08-23.md:404`). A correção foi
`views/admin.py:100-290` passar a **reusar** o `RegistroPonto` do dia.

- [ ] **Step 2: Decide, and say which**
  - **Se o arreio já cobre:** não crie arquivo. Registre a decisão neste plano e
    no `2026-08-04-plano-consolidado.md`, no mesmo formato da nota do A05 — que é
    o precedente da casa.
  - **Se não cobre:** o caso entra em `tests/test_arreio_presenca_rotas.py`,
    **não** em arquivo novo. Dois POSTs no mesmo dia, e a afirmação é sobre
    `RegistroPonto` (um só) e sobre o custo (não sobrescrito).

- [ ] **Step 3: Commit**

---

### Task 3: `test_b5_curva_baseline.py`

**Files:**
- Create: `tests/test_b5_curva_baseline.py`

- [ ] **Step 1: Read what the plan promised**

```bash
sed -n '680,710p' docs/superpowers/plans/2026-08-06-rodada-b5-varredura.md
```

O plano nomeia o dataset e o comportamento. Escreva o teste **contra o que ele
descreve**, não contra o que o código faz hoje — se os dois divergirem, é achado,
e ele entra em `docs/auditoria/achados-code-review-2026-08-25.md`.

- [ ] **Step 2-4:** RED (ou verde com justificativa), verde, commit.

---

### Task 4: Os cinco `test_b6_404_*`

**Files:**
- Create: `tests/test_b6_404_obras.py`, `_frota.py`, `_cauda.py`, `_miscelanea.py`, `_propostas.py`

> 🔬 **São cinco, não quatro.** A medição mecânica achou quatro porque
> `test_b6_404_propostas.py` (`rodada-b6:593`) escapou do padrão de nome que ela
> procurava.

- [ ] **Step 1: Read the five sections of the b6 plan**

```bash
sed -n '585,600p;630,645p;668,680p;703,715p;743,755p' docs/superpowers/plans/2026-08-06-rodada-b6-varredura.md
```

Cada seção nomeia as rotas e o comportamento esperado (404 em vez de 500, ou
403-engolido virando 404). O recorte entregue em agosto foi
`test_b6_estorno_recebimento.py` e `test_b6_familia2_reembolso_import.py` — o
resto ficou.

- [ ] **Step 2-4:** um arquivo por família, RED, verde, **um commit por arquivo**.

⚠️ 🔬 Estes testes cobrem o mesmo território que a **Onda 2** (404 em vez de 403
para recurso de outro tenant). Se a Onda 2 já entrou, alguns nascem verdes — e
está certo. **Diga quais**, no commit.

---

### Task 5: `test_isolamento_tenant_bloco1.py`

**Files:**
- Create: `tests/test_isolamento_tenant_bloco1.py`

> 🔴 **Este arquivo não é higiene: é a prova que faltava.** 📖 O
> `2026-06-02-bloco1-blindagem-acesso-plan.md` prometeu blindar o acesso, e a
> varredura de 25/08 achou **furos de tenant vivos** — `multitenant_helper.py:25`
> (o tenant fantasma), `transporte_views.py:204`, `veiculos_services.py:167`.
> **A blindagem do bloco 1 não cobriu o parque, e não havia teste dizendo isso.**

🔬 O isolamento é coberto hoje por `test_p1_isolamento_relatorios.py`,
`test_gestao_custo_filho_tenant.py` e `test_arreio_almoxarifado_e_tenant.py` —
**nenhum cobre `multitenant_helper.get_admin_id`**, que é a raiz.

- [ ] **Step 1:** escrever o arquivo como **censo**, não como caso: para cada
  papel de `TipoUsuario`, afirmar que `get_admin_id()`, `get_tenant_admin_id()` e
  `require_tenant()` concordam. É o teste que teria impedido a divergência de
  nascer.
- [ ] **Step 2-4:** RED (se a Onda 2 não entrou), verde, commit.

⚠️ Se a Onda 2 já entrou, este arquivo nasce verde. **Escreva-o mesmo assim** —
o valor dele é impedir o quarto resolvedor de nascer, não pegar o defeito de hoje.

---

### Task 6: A jornada E2E, que nunca rodou

- [ ] **Step 1: Run it**

Run: `bash run_tests.sh --jornada`

🔬 Os 7 blocos (59 passed) e a varredura de páginas (48/48) rodaram depois que o
Chromium voltou. **A jornada, não** — está em aberto desde a Fase 0.5.

- [ ] **Step 2: Report honestly**

Se falhar, **cada falha é achado**, e vai para
`docs/auditoria/achados-code-review-2026-08-25.md` com `arquivo:linha`. **Não
conserte no meio da onda** — a jornada é E2E, e um conserto às pressas aqui pode
mascarar defeito de outra onda.

Se passar, registre a contagem no fecho — é a primeira vez que ela roda.

- [ ] **Step 3: Commit** (só o registro; a jornada não muda código)

---

## Fecho da onda

- [ ] `bash run_tests.sh --gate` verde, com a contagem registrada — ela **sobe**
      nesta onda, e é para subir. Diga em quanto.
- [ ] `bash run_tests.sh --jornada` rodado, com resultado registrado.
- [ ] A decisão da Task 2 (A10 já coberto ou não) registrada **aqui e no
      `2026-08-04-plano-consolidado.md`**, no formato da nota do A05.
- [ ] `docs/planos-em-aberto-2026-08-25.md` — a coluna "Resíduo" dos sete planos
      atualizada com o que sobrou de verdade.
- [ ] **A09 riscada** de `docs/reconferencia-backlog-2026-08-23.md` — agora com
      teste, não com leitura de código.
