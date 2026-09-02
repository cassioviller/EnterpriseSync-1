# O Que Não Persiste, e o Que Persiste Pela Metade Implementation Plan

> **Estado em 2026-08-31:** ✅ **FECHADO — 6/6 tasks.** Gate de fecho na branch
> `sdd/a-porta-irma`: **2872 passed, 6 skipped, 201 deselected, 2 xfailed, 0
> failed** (46min44s) — 18 verdes acima do piso de 2854, e o skipped ficou nos
> mesmos 6 (nenhuma cobertura saiu do gate). Os cinco achados estão marcados
> como corrigidos em `docs/auditoria/achados-code-review-2026-08-25.md`, seção
> "✅ Corrigidos pelo plano 'O Que Não Persiste' (31/08)", com o commit de cada
> um.
>
> | Task | Commit |
> |---|---|
> | 1 — o `except` do portal para de commitar às cegas | `42c17ddb` |
> | 2 — a trilha existe nas seis rotas | `b581da0d` |
> | 3 — a reativação inline delega ao restaurador | `e404a5e8` `22fa7e4e` `915462d0` |
> | 4 — a constraint irmã de versão ganha o tenant (migration 316) | `416967b9` `f906e20f` |
> | 5 — o diff de proposta compara maçã com maçã | `6ce5c90a` `aba6df97` |
> | 6 — o gate, e o fecho | este bloco |
>
> ⚠️ **Dois fix rounds, e os dois vieram de porta irmã.** A migration 316
> falhava em banco novo porque `create_all()` cria a irmã como CONSTRAINT
> enquanto a migration a tratava como ÍNDICE (`f906e20f`); e o
> `total_do_diff` continuava misturando centavos com valor cru depois do fix
> da Task 5 (`aba6df97`). Um terceiro achado foi sobre o próprio teste: um
> teste da Onda 5 provava por `inspect.getsource()` e reprovava a melhora de
> comportamento da Task 3 — reescrito para provar pelo banco (`915462d0`).
>
> Nasceu do `/code-review max` sobre a branch da Onda 5. Evidência em
> `docs/auditoria/achados-code-review-2026-08-25.md`, seção "Achados do
> `/code-review max` sobre a branch da Onda 5 (28/08)".
>
> 🔬 **Os cinco achados foram reconferidos na fonte em 28/08**, um a um, antes
> de este plano ser escrito.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para executar este plano task a task. Os passos usam checkbox (`- [ ]`) para acompanhamento.

**Goal:** Fazer com que o que o sistema diz ter gravado esteja gravado — a
trilha de auditoria do portal, a restauração de tarefa arquivada, a numeração de
versão de contrato e o diff de proposta — fechando os cinco defeitos em que a
escrita **não chega ao banco** ou **chega pela metade**.

**Architecture:** Duas naturezas, e a fronteira entre elas é o `commit`.
**(a) O que não persiste:** `_registrar_acesso` não commita — está na docstring
(`portal_obras_views.py:138`) — e quatro das seis rotas do portal que registram
trilha não commitam depois; a mais grave, `ver_comprovante`, devolve `send_file`
e o `session.remove()` do teardown desfaz o evento. **(b) O que persiste pela
metade:** a reativação inline de `cronograma_proposta.py:609` liga `ativa=True`
e esquece `arquivada_em` e as filhas; a migration 315 escopou uma constraint por
tenant e deixou a irmã sem escopo; o diff compara um snapshot arredondado no
banco com um produto não arredondado. Nos cinco, a tela reporta sucesso.

**Tech Stack:** Flask, SQLAlchemy 2.0.41, PostgreSQL (SAVEPOINT), pytest,
migrations pelo runner caseiro de `migrations.py` (tupla ordenada, não Alembic).

**Spec:** `docs/auditoria/achados-code-review-2026-08-25.md` (seção de 28/08).

## Global Constraints

- **TDD sem exceção.** Teste primeiro, RED conferido e **citado no commit**.
- **Nenhum teste prova por `inspect.getsource()`.** O que se afirma é olhado
  **no banco**, depois do commit — nunca no texto do código, e nunca só no
  código de status HTTP. 🔬 É a regra que a Onda 5 violou e que deixou passar um
  `rollback` que apagava a transação inteira do chamador.
- **Teste de persistência confere DEPOIS do teardown da requisição.** Um
  `assert` dentro do mesmo contexto vê a sessão, não o banco. Use requisição via
  `test_client` e só então consulte, em `app_context` novo.
- **Serviço não commita nem faz rollback da sessão inteira.** Quem commita é o
  chamador; quem precisa desfazer só o seu usa `db.session.begin_nested()`.
  🔬 Precedente desta mesma semana: `services/entregas_terceiros.py:302`.
- **Migration que conserta constraint conserta os dados também**, ou explica por
  escrito por que não há linha a corrigir.
- **Gate ao fim:** `bash run_tests.sh --gate`. Régua: **2840 passed, 10 skipped,
  201 deselected, 2 xfailed** — ou mais verdes.

---

## File Structure

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `portal_obras_views.py` | Modificar `:641-650` | Task 1 |
| `portal_obras_views.py` | Modificar `:696`, `:774`, `:786`, `:939` | Task 2 |
| `services/cronograma_proposta.py` | Modificar `:609-610`, `:685-686` | Task 3 |
| `models.py` | Modificar `:7616` | Task 4 |
| `migrations.py` | **Acrescentar** migration nova | Task 4 |
| `services/proposta_diff.py` | Modificar `:92` | Task 5 |
| `templates/propostas/comparar.html` | Modificar `:78-79` | Task 5 |
| `tests/test_o_que_nao_persiste.py` | **Criar** | Todos os testes deste plano |

---

### Task 1: O `except` do portal para de commitar às cegas e de contar a exceção

> 🔴 📖 `portal_obras_views.py:641-650`. O `except` de `aprovar_compra` faz
> `rollback`, registra a trilha e chama `db.session.commit()` **sem guarda** —
> se esse commit levantar (conexão caída, constraint de `PortalAcessoEvento`),
> a exceção sai do handler e o visitante **anônimo** recebe um 500 cru, onde
> antes havia mensagem tratada.
>
> E a linha seguinte, `:648`, dá `flash(f'Erro ao aprovar compra: {e}')` — a
> exceção crua, com SQL e parâmetros vinculados, para um **portador de token
> não autenticado**.

**Files:**
- Modify: `portal_obras_views.py:641-650`
- Test: `tests/test_o_que_nao_persiste.py` (criar)

**Interfaces:**
- Consumes: `_registrar_acesso` (`portal_obras_views.py:137`, não commita).
- Produces: nada.

- [ ] **Step 1: Write the failing test**

Create `tests/test_o_que_nao_persiste.py`:

```python
"""O que não persiste, e o que persiste pela metade.

A regra destes testes: a afirmação é olhada NO BANCO, depois do teardown da
requisição. `assert` dentro do mesmo contexto vê a SESSÃO, não o banco — e a
diferença entre as duas é exatamente onde estes cinco defeitos moram.

Nenhum teste aqui prova por `inspect.getsource()`.
"""
import os
import sys
import uuid
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from helpers_tenant import cliente_de, um_tenant

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-nao-persiste'
    yield


def test_erro_ao_aprovar_compra_nao_conta_a_excecao_ao_anonimo():
    """🔴 `portal_obras_views.py:648` — `flash(f'Erro ao aprovar compra: {e}')`.

    O portal é acessado por TOKEN, sem autenticação. `str(e)` de erro
    SQLAlchemy carrega o SQL e os parâmetros vinculados, e vai para a tela de
    quem tem o link.
    """
    from models import Obra

    with app.app_context():
        t = um_tenant('portal-erro', com_fatos=False)
        obra = db.session.get(Obra, t.obra_id)
        # 🔬 Campo conferido: `Obra.token_cliente` (`models.py:397`).
        obra.token_cliente = token = uuid.uuid4().hex
        db.session.commit()

    # compra_id inexistente força o caminho de erro sem depender de fixture
    # de compra — o que se afirma é sobre a MENSAGEM, não sobre a compra.
    cliente = app.test_client()
    resposta = cliente.post(f'/portal/obra/{token}/compra/999999999/aprovar',
                            data={}, follow_redirects=True)
    corpo = resposta.get_data(as_text=True)

    for vazamento in ('[SQL:', '[parameters:', 'psycopg2.', 'sqlalchemy.exc',
                      'Traceback (most recent call last)'):
        assert vazamento not in corpo, (
            f'{vazamento!r} vazou para visitante anônimo do portal')
```

🔬 Prefixo conferido: `url_prefix='/portal'` (`portal_obras_views.py:41`).

⚠️ `_get_obra_by_token` (`:89`) trata **token expirado como ausência** e aborta
com 404. Se `token_cliente_expira_em` tiver default no passado, o teste bate no
404 antes do `except` e não prova nada — deixe a expiração NULA, que segue
valendo por desenho.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_o_que_nao_persiste.py -k anonimo -v`
Expected: **FAIL** — a exceção aparece no corpo. ⚠️ Se o `_get_compra_do_portal`
abortar com 404 antes de chegar ao `except`, o teste passa sem provar nada:
force um erro DENTRO do `try` (ex.: `raise SQLAlchemyError('boom')` temporário),
confirme o RED, e desfaça.

- [ ] **Step 3: Write minimal implementation**

```python
    except Exception as e:
        db.session.rollback()
        logger.error(f"[PORTAL] Erro ao aprovar compra {compra_id}: {e}",
                     exc_info=True)
        # A trilha da tentativa sobrevive ao rollback: registra e commita só
        # ela — mas o commit da AUDITORIA não pode derrubar o handler. Sem
        # esta guarda, uma falha aqui virava 500 cru para visitante anônimo,
        # onde antes havia mensagem tratada.
        try:
            _registrar_acesso(obra, 'compra_aprovar', 'pedido_compra',
                              compra_id, {'resultado': 'erro'})
            db.session.commit()
        except Exception as e_trilha:
            db.session.rollback()
            logger.error(f"[PORTAL] trilha da falha não gravou: {e_trilha}")
        # `str(e)` traz SQL e parâmetros vinculados, e quem lê isto é um
        # portador de token NÃO autenticado. Detalhe vive no log.
        flash('Não foi possível aprovar a compra. O erro foi registrado; '
              'acione o responsável pela obra.', 'danger')
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_o_que_nao_persiste.py -k anonimo -v`
Expected: **PASS**.

Run: `python -m pytest tests/ -k portal -m "not browser" -q`
Expected: verde.

- [ ] **Step 5: Commit**

```bash
git add tests/test_o_que_nao_persiste.py portal_obras_views.py
git commit -m "fix(portal): o commit da trilha ganha guarda, e a excecao para de ir ao anonimo"
```

---

### Task 2: A trilha do portal passa a existir nas seis rotas, não em duas

> 🔴 📖 `_registrar_acesso` **não commita** — docstring em `:138`. A Onda 5
> aplicou o desenho "um evento commitado por tentativa" em **duas** das seis
> rotas que registram trilha.
>
> 🔬 A pior é `ver_comprovante` (`:774`): registra o evento e devolve
> `send_file(...)` **sem commit em lugar nenhum da requisição** — o
> `session.remove()` do teardown do Flask-SQLAlchemy desfaz tudo. **Toda
> visualização de comprovante de pagamento pelo cliente some.** As outras três
> (`upload_comprovante:696`, `aprovar_mapa_concorrencia:786`,
> `selecionar_mapa_v2:939`) registram na entrada e têm saídas antecipadas que
> nunca alcançam commit — ou seja, **a tentativa recusada não deixa rastro**,
> que é justamente o conjunto de tentativas para o qual a auditoria existe.

**Files:**
- Modify: `portal_obras_views.py:696`, `:774`, `:786`, `:939`
- Test: `tests/test_o_que_nao_persiste.py`

**Interfaces:**
- Consumes: `_registrar_acesso`.
- Produces: `_commit_trilha(obra, acao, ...)` — helper novo em
  `portal_obras_views.py`, assinatura
  `(obra, acao: str, alvo_tipo: str | None = None, alvo_id: int | None = None, detalhes: dict | None = None) -> None`.
  Registra e commita **só** a trilha, sem nunca levantar. Consumido pelas seis
  rotas.

- [ ] **Step 1: Write the failing test**

```python
def _obra_com_token(marca):
    from models import Obra

    t = um_tenant(marca, com_fatos=False)
    obra = db.session.get(Obra, t.obra_id)
    # 🔬 Campo conferido: `Obra.token_cliente` (`models.py:397`).
    obra.token_cliente = token = uuid.uuid4().hex
    db.session.commit()
    return t, token


def test_visualizacao_de_comprovante_deixa_rastro():
    """🔴 `portal_obras_views.py:774` — registra e devolve `send_file` sem
    commit algum.

    `_registrar_acesso` não commita (docstring :138), e o `session.remove()`
    do teardown desfaz o evento. Toda visualização de comprovante de
    pagamento pelo cliente sumia — e é o acesso que mais interessa auditar.

    A conferência é feita em contexto NOVO, depois do teardown: dentro da
    mesma sessão o evento apareceria e o teste passaria por engano.
    """
    from models import PortalAcessoEvento

    with app.app_context():
        t, token = _obra_com_token('portal-trilha')
        obra_id = t.obra_id
        antes = PortalAcessoEvento.query.filter_by(
            obra_id=obra_id, acao='compra_comprovante_ver').count()

    app.test_client().get(
        f'/portal/obra/{token}/compra/999999999/comprovante')

    with app.app_context():
        depois = PortalAcessoEvento.query.filter_by(
            obra_id=obra_id, acao='compra_comprovante_ver').count()
        assert depois > antes, (
            'a visualização de comprovante não deixou rastro — o teardown '
            'desfez o evento que ninguém commitou')


def test_tentativa_recusada_no_portal_tambem_deixa_rastro():
    """🔴 `:696`, `:786`, `:939` — registram na entrada e têm saídas
    antecipadas que nunca alcançam commit.

    Upload recusado (tipo errado, >5 MB, compra fora de APROVADO) e seleção
    de mapa recusada somem da trilha. É exatamente o conjunto de tentativas
    para o qual uma auditoria existe.
    """
    from models import PortalAcessoEvento

    with app.app_context():
        t, token = _obra_com_token('portal-recusa')
        obra_id = t.obra_id
        antes = PortalAcessoEvento.query.filter_by(obra_id=obra_id).count()

    app.test_client().post(
        f'/portal/obra/{token}/compra/999999999/comprovante',
        data={}, follow_redirects=True)

    with app.app_context():
        depois = PortalAcessoEvento.query.filter_by(obra_id=obra_id).count()
        assert depois > antes, (
            'a tentativa recusada de upload não deixou rastro')
```

🔬 **Ações conferidas** (`grep -n "_registrar_acesso(" portal_obras_views.py`):

| Linha | Ação | Commita hoje? |
|---|---|---|
| `:696` `upload_comprovante` | `'compra_comprovante'` | ❌ saídas antecipadas |
| `:774` `ver_comprovante` | `'compra_comprovante_ver'` | ❌ **nunca** |
| `:786` `aprovar_mapa_concorrencia` | `'mapa_v1_aprovar'` | ❌ saídas antecipadas |
| `:939` `selecionar_mapa_v2` | `'mapa_v2_selecionar'` | ❌ saídas antecipadas |
| `:567-645` `aprovar_compra` | `'compra_aprovar'` | ✅ com o negócio |
| `:660-684` `recusar_compra` | `'compra_recusar'` | ✅ com o negócio |

⚠️ **A conferência achou mais do que o review contou.** Há uma sétima família
de registro que ninguém mapeou: `ciencia_login`, `ciencia_login_falha`,
`ciencia_rdo`, `ciencia_senha_trocada`, `ciencia_recuperacao_pedida`
(`:1306`, `:1315`, `:1368`, `:1498`, `:1517`, `:1550`). **Antes de fechar a
task, verifique se cada uma alcança commit** — `ciencia_login_falha` é
tentativa de login que falhou, exatamente o tipo de evento que uma auditoria
existe para guardar, e tem a mesma forma das quatro acima. Se alguma não
commitar, ela entra nesta task; se todas commitarem, registre isso no commit
para o próximo leitor não refazer a checagem.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_o_que_nao_persiste.py -k rastro -v`
Expected: **FAIL** nos dois — `depois == antes`.

- [ ] **Step 3: Write minimal implementation**

Primeiro o helper, ao lado de `_registrar_acesso`:

```python
def _commit_trilha(obra, acao, alvo_tipo=None, alvo_id=None, detalhes=None):
    """Registra o evento E commita só ele. Nunca levanta.

    `_registrar_acesso` deliberadamente não commita, porque em rota de
    ESCRITA o evento tem de viajar na transação do negócio. Mas quatro rotas
    registram e nunca chegam a um commit — `ver_comprovante` devolve
    `send_file` e o `session.remove()` do teardown desfaz o evento; as de
    upload e de mapa têm saídas antecipadas.

    Onde o evento é a ÚNICA escrita da requisição, ou onde a saída pode
    acontecer antes do commit do negócio, use este.
    """
    try:
        _registrar_acesso(obra, acao, alvo_tipo, alvo_id, detalhes)
        db.session.commit()
    except Exception as e:   # auditoria não impede o cliente de agir
        db.session.rollback()
        logger.error(f"[PORTAL] trilha '{acao}' não gravou: {e}")
```

Depois, nas quatro rotas, trocar `_registrar_acesso(...)` por
`_commit_trilha(...)`:

- `:774` `ver_comprovante` — antes do `return send_file(...)`.
- `:696` `upload_comprovante`, `:786` `aprovar_mapa_concorrencia`,
  `:939` `selecionar_mapa_v2` — no registro de entrada.

⚠️ **Não troque nas duas rotas que já commitam junto com o negócio**
(`aprovar_compra` e `recusar_compra`): lá o evento tem de viajar na transação do
negócio, e commitar antes quebraria a atomicidade que a Onda 5 construiu.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_o_que_nao_persiste.py -k rastro -v`
Expected: **PASS** nos dois.

Run: `python -m pytest tests/ -k portal -m "not browser" -q`
Expected: verde. ⚠️ `test_tentativa_no_portal_deixa_exatamente_um_evento` conta
só `acao='compra_aprovar'` — deve seguir passando; se cair, `_commit_trilha`
entrou numa rota que não devia.

- [ ] **Step 5: Commit**

```bash
git add tests/test_o_que_nao_persiste.py portal_obras_views.py
git commit -m "fix(portal): a trilha existe nas seis rotas, e a tentativa recusada deixa rastro"
```

---

### Task 3: A reativação inline delega ao restaurador que já existe

> 🔴 📖 `services/cronograma_proposta.py:609-610` e `:685-686` fazem
> `if not tarefa.ativa: tarefa.ativa = True` — reimplementação **incompleta** do
> `reativar_tarefas_de_itens_reincluidos`, no mesmo módulo (`:892`).
>
> 🔬 O restaurador cumpre **duas** obrigações que o inline ignora: `:957-959`
> faz `t.ativa = True` **e** `t.arquivada_em = None`, e caminha uma fronteira
> que **cascateia para as filhas arquivadas**. O inline liga a flag da tarefa
> casada e para ali.
>
> **O estado resultante é inconsistente:** `ativa=True` com `arquivada_em` não
> nulo. Todo outro escritor limpa os dois (`cronograma_versao_service.py:807`),
> `cronograma_undo.py:57` carrega `arquivada_em` no snapshot de undo, e o
> próprio `reativar_tarefas_de_itens_reincluidos` **nunca poderá limpar** porque
> filtra `ativa.is_(False)`. E o serviço re-incluído volta como pai solitário,
> com a subárvore inteira ainda `ativa=False`.

**Files:**
- Modify: `services/cronograma_proposta.py:609-610`, `:685-686`
- Test: `tests/test_o_que_nao_persiste.py`

**Interfaces:**
- Consumes: `reativar_tarefas_de_itens_reincluidos(obra_id, admin_id, proposta_item_ids) -> int`
  (`services/cronograma_proposta.py:892`).
- Produces: nada.

- [ ] **Step 1: Write the failing test**

```python
def test_reativar_tarefa_arquivada_limpa_arquivada_em_e_cascateia():
    """🔴 `cronograma_proposta.py:609` — `if not t.ativa: t.ativa = True`.

    Reimplementa incompleto o `reativar_tarefas_de_itens_reincluidos`
    (`:892`), que cumpre DUAS obrigações: limpa `arquivada_em` e cascateia
    para as filhas. O inline faz nem uma nem outra.

    `ativa=True` com `arquivada_em` preenchido é estado que nenhum outro
    escritor produz — e que o próprio restaurador nunca poderá limpar,
    porque filtra `ativa.is_(False)`.
    """
    from datetime import datetime

    from models import TarefaCronograma

    with app.app_context():
        t = um_tenant('reativa', com_fatos=False)
        arquivada = datetime(2026, 8, 1)

        pai = TarefaCronograma(
            obra_id=t.obra_id, admin_id=t.admin_id,
            nome_tarefa=f'Servico {uuid.uuid4().hex[:6]}', ordem=0,
            responsavel='propria', duracao_dias=5,
            percentual_concluido=0.0, ativa=False, arquivada_em=arquivada)
        db.session.add(pai)
        db.session.flush()

        filha = TarefaCronograma(
            obra_id=t.obra_id, admin_id=t.admin_id,
            nome_tarefa=f'Sub {uuid.uuid4().hex[:6]}', ordem=1,
            responsavel='propria', duracao_dias=2,
            percentual_concluido=0.0, ativa=False, arquivada_em=arquivada,
            tarefa_pai_id=pai.id)
        db.session.add(filha)
        db.session.commit()

        from services.cronograma_proposta import (
            reativar_tarefas_de_itens_reincluidos)
        # A prova é do INVARIANTE, não do caminho: depois de restaurar, não
        # pode existir tarefa viva com lápide, nem filha esquecida.
        reativar_tarefas_de_itens_reincluidos(
            t.obra_id, t.admin_id, [pai.gerada_por_proposta_item_id])
        db.session.commit()

        for alvo, rotulo in ((pai, 'o serviço'), (filha, 'a subtarefa')):
            db.session.refresh(alvo)
            assert alvo.ativa is True, f'{rotulo} não voltou'
            assert alvo.arquivada_em is None, (
                f'{rotulo} voltou viva com lápide: ativa=True e '
                f'arquivada_em={alvo.arquivada_em}')
```

⚠️ O teste chama o restaurador diretamente porque é ele o comportamento
correto que o inline tem de passar a usar. Se `gerada_por_proposta_item_id` for
`None` no cenário acima, semeie um `PropostaItem` e ligue os dois — o
restaurador casa por esse id.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_o_que_nao_persiste.py -k reativar -v`
Expected: **FAIL** — a filha continua `ativa=False`, ou o `arquivada_em` do pai
continua preenchido, dependendo de qual metade o cenário exercita.

- [ ] **Step 3: Write minimal implementation**

Nos dois pontos (`:609-610` e `:685-686`), trocar a reimplementação por delegação:

```python
            # `natural_key_index` não filtra `ativa`: a casada pode ser uma
            # tarefa ARQUIVADA (item suprimido numa revisão anterior). Quem
            # sabe restaurar é `reativar_tarefas_de_itens_reincluidos`
            # (:892), e ele cumpre DUAS obrigações que o `ativa = True`
            # inline ignorava: limpa `arquivada_em` e cascateia para as
            # filhas arquivadas. `ativa=True` com lápide era estado que
            # nenhum outro escritor produz, e que o próprio restaurador
            # nunca poderia limpar (ele filtra `ativa.is_(False)`).
            if not tarefa_serv.ativa:
                reativar_tarefas_de_itens_reincluidos(
                    obra_id, admin_id, [pi_id] if pi_id else [])
```

⚠️ Confira os nomes de `obra_id`/`admin_id` no escopo dos dois pontos — podem
estar como `obra.id` / `obra.admin_id`. E importe o restaurador no topo do
módulo, não dentro do laço.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_o_que_nao_persiste.py -k reativar -v`
Expected: **PASS**.

Run: `python -m pytest tests/ -k "cronograma or proposta" -m "not browser" -q`
Expected: verde.

- [ ] **Step 5: Commit**

```bash
git add tests/test_o_que_nao_persiste.py services/cronograma_proposta.py
git commit -m "fix(cronograma): a reativacao inline delega ao restaurador, com lapide e cascata"
```

---

### Task 4: A constraint irmã de versão de contrato ganha o tenant

> 🔴 📖 `models.py:7613-7616`. A migration 315 alargou
> `uq_contrato_versao_vigente` para `(obra_id, admin_id)` — e deixou a irmã
> `uq_contrato_versao_obra_versao` como **`UNIQUE(obra_id, versao)`**, sem
> `admin_id`.
>
> 🔬 `services/contrato_obra.py:196-198` calcula `max(versao)` filtrando por
> `(obra_id, admin_id)`. Tome a linha de `admin_id` divergente que a própria
> docstring da migration cita (precedente da migration 266), em `versao=3`: o
> tenant correto vê `max=1`, monta `versao=2`, depois `3`, e o INSERT viola
> `uq_contrato_versao_obra_versao`. **A obra permanentemente travada que a 315
> descreve continua travada — só muda o nome da constraint no erro.**

**Files:**
- Modify: `models.py:7616`
- Modify: `migrations.py` (acrescentar migration nova ao fim da tupla)
- Test: `tests/test_o_que_nao_persiste.py`

**Interfaces:**
- Consumes: `services.contrato_obra.abrir_versao`.
- Produces: nada.

- [ ] **Step 1: Write the failing test**

```python
def test_versao_de_contrato_e_unica_por_tenant_nao_por_obra():
    """🔴 `models.py:7616` — `UNIQUE(obra_id, versao)` sem `admin_id`.

    A migration 315 escopou a irmã (`uq_contrato_versao_vigente`) por tenant
    e deixou esta como estava. Com uma linha de admin_id divergente — o
    cenário que a própria docstring da 315 cita — o tenant correto numera a
    partir do SEU máximo e colide com a linha alheia.
    """
    from sqlalchemy import text

    from models import ObraContratoVersao

    with app.app_context():
        t = um_tenant('contrato-uq', com_fatos=False)

        # A linha "órfã": mesma obra, tenant divergente, versão alta.
        orfa = ObraContratoVersao(
            obra_id=t.obra_id, admin_id=t.admin_id + 999999,
            versao=3, valor_contrato=1000, vigente_ate=date(2026, 1, 1))
        db.session.add(orfa)
        db.session.commit()

        from models import Obra
        from services.contrato_obra import ORIGEM_CADASTRO, abrir_versao

        obra_ref = db.session.get(Obra, t.obra_id)
        # 🔬 Assinatura conferida (`services/contrato_obra.py:114`):
        # `abrir_versao(obra, valor, origem_tipo, *, origem_proposta_id=None,
        # aditivo_id=None, motivo=None, criado_por_id=None, vigente_de=None,
        # prazo_dias=None)`. `valor` e `origem_tipo` são POSICIONAIS e
        # obrigatórios.
        #
        # O tenant correto numera a partir do SEU máximo (0) — 1, 2, 3 — e é
        # na terceira que ele encontra a órfã de versao=3.
        for _ in range(3):
            abrir_versao(obra_ref, 500, ORIGEM_CADASTRO)
            db.session.commit()

        vivas = ObraContratoVersao.query.filter_by(
            obra_id=t.obra_id, admin_id=t.admin_id).count()
        assert vivas == 3, (
            'a numeração do tenant colidiu com a versão de outro tenant na '
            'mesma obra — uq_contrato_versao_obra_versao não tem admin_id')
```

🔬 `origem_tipo` conferido: o domínio é `ORIGENS` (`:106`), e
`ORIGEM_CADASTRO = 'cadastro_manual'` (`:97`). Use a constante, nunca a string
literal — `ORIGEM_TIPO` é identidade hoje (`:111`), e escrever o texto cru
esconderia a quebra no dia em que deixar de ser.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_o_que_nao_persiste.py -k versao_de_contrato -v`
Expected: **FAIL** com `IntegrityError` citando `uq_contrato_versao_obra_versao`.

- [ ] **Step 3: Write minimal implementation**

Em `models.py:7616`:

```python
        # `admin_id` NÃO é decorativo aqui: `abrir_versao`
        # (services/contrato_obra.py:196-198) calcula `max(versao)` filtrando
        # por (obra_id, admin_id). Sem o tenant nesta constraint, a linha de
        # admin_id divergente que a migration 315 descreve continuava
        # travando a obra — a 315 consertou a irmã e deixou esta, e o único
        # efeito foi mudar o NOME da constraint no IntegrityError.
        db.UniqueConstraint('obra_id', 'admin_id', 'versao',
                            name='uq_contrato_versao_obra_versao'),
```

E a migration nova, ao fim da tupla de `migrations.py` — que **também detecta os
dados**, porque constraint nova não conserta linha velha:

🔬 Padrão conferido em `migrations.py:7381` (a própria 315): função **sem
argumentos**, `with db.engine.begin() as conn`, `text` importado como `sa_text`
dentro da função, e registro numa tupla `(numero, descrição, função)` em `:7730`.

```python
def _migration_316_versao_contrato_por_tenant():
    """A irmã da 315: UNIQUE(obra_id, versao) → (obra_id, admin_id, versao).

    A 315 escopou `uq_contrato_versao_vigente` por tenant e parou ali. Mas
    `abrir_versao` (services/contrato_obra.py:196-198) calcula `max(versao)`
    filtrando por (obra_id, admin_id): com uma linha de `admin_id` divergente
    — o mesmo precedente da 266 que a 315 cita — o tenant correto renumera do
    SEU máximo e colide com a linha alheia. A obra travada seguia travada; só
    mudou o nome da constraint no erro.

    Ao contrário da 315, NÃO é seguro sem olhar os dados. Alargar de
    (obra_id, versao) para (obra_id, admin_id, versao) é AFROUXAR, então toda
    linha existente continua válida — mas se já houver duplicata no trio
    novo, a constraint não nasce. Daí a checagem explícita.

    Alocação: 316 (máximo real do repo em 28/08: 315).
    """
    from sqlalchemy import text as sa_text
    with db.engine.begin() as conn:
        conn.execute(sa_text(
            "ALTER TABLE obra_contrato_versao "
            "DROP CONSTRAINT IF EXISTS uq_contrato_versao_obra_versao"))
        colisoes = conn.execute(sa_text(
            "SELECT obra_id, admin_id, versao, count(*) "
            "FROM obra_contrato_versao "
            "GROUP BY obra_id, admin_id, versao HAVING count(*) > 1"
        )).fetchall()
        if colisoes:
            # Reporta, não mascara: constraint que não sobe em silêncio é
            # pior que a antiga — some do modelo mental sem sumir do banco.
            raise RuntimeError(
                f"obra_contrato_versao tem {len(colisoes)} colisao(oes) em "
                f"(obra_id, admin_id, versao) — resolva antes: {colisoes[:5]}")
        conn.execute(sa_text(
            "ALTER TABLE obra_contrato_versao "
            "ADD CONSTRAINT uq_contrato_versao_obra_versao "
            "UNIQUE (obra_id, admin_id, versao)"))
    logger.info("[Migration 316] uq_contrato_versao_obra_versao agora cobre "
                "(obra_id, admin_id, versao) — o trio que abrir_versao usa.")
```

E o registro, ao fim da tupla em `migrations.py:7730`, na forma da 315:

```python
            (316, "Fix round do code review — uq_contrato_versao_obra_versao ganha admin_id: a 315 escopou a irma e deixou esta, e abrir_versao numera por (obra_id, admin_id)", _migration_316_versao_contrato_por_tenant),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_o_que_nao_persiste.py -k versao_de_contrato -v`
Expected: **PASS**.

Run: `python -m pytest tests/ -k "contrato or aditivo" -m "not browser" -q`
Expected: verde. ⚠️ `test_indice_de_vigencia_casa_com_as_queries` afirma só o
índice da 315 — deve seguir passando.

- [ ] **Step 5: Commit**

```bash
git add tests/test_o_que_nao_persiste.py models.py migrations.py
git commit -m "fix(contrato): a constraint irma de versao ganha o tenant que a 315 esqueceu"
```

---

### Task 5: O diff de proposta compara maçã com maçã

> 🔴 📖 `services/proposta_diff.py:92` — `dv = _dec(it.subtotal_calculado) -
> _dec(anterior.subtotal_calculado)`.
>
> 🔬 `subtotal_calculado` (`models.py:4029-4036`) devolve o snapshot persistido
> quando existe — `Numeric(15,2)`, **duas casas** — e, quando não, o produto
> `quantidade × preco_unitario`, com `Numeric(10,3) × Numeric(10,2)` = até
> **cinco casas**. No caso misto — que o próprio comentário da correção chama de
> comum — uma linha intocada dá `14.06315 − 14.06 = 0.00315 ≠ 0` e é reportada
> **"alterado"**, e o total do diff deixa de fechar com qualquer das versões.
>
> 📖 E `templates/propostas/comparar.html:78-79` não acompanhou a mudança:
> segue imprimindo o `subtotal` cru ao lado do impacto novo, então o caso de
> snapshot NULL renderiza `0,00 | 0,00 | Δ 12.500,00` — na tela que este mesmo
> diff acabou de ganhar link.

**Files:**
- Modify: `services/proposta_diff.py:92`
- Modify: `templates/propostas/comparar.html:78-79`
- Test: `tests/test_o_que_nao_persiste.py`

**Interfaces:**
- Consumes: `PropostaItem.subtotal_calculado` (`models.py:4029`).
- Produces: nada.

- [ ] **Step 1: Write the failing test**

```python
def test_linha_intocada_nao_vira_alterado_por_arredondamento():
    """🔴 `proposta_diff.py:92` — compara snapshot de 2 casas com produto de
    até 5.

    `subtotal_calculado` devolve `Numeric(15,2)` quando há snapshot e
    `quantidade × preco_unitario` (Numeric(10,3) × Numeric(10,2)) quando não
    há. No caso misto, linha INTOCADA dá diferença de 0.00315 e sai como
    'alterado'.
    """
    from decimal import Decimal

    from models import Proposta, PropostaItem
    # 🔬 Nome conferido (`services/proposta_diff.py:48`):
    # `diff_versoes(origem, destino) -> list[dict]`. Não existe
    # `diff_de_propostas`.
    from services.proposta_diff import diff_versoes

    with app.app_context():
        t = um_tenant('diff-arred', com_fatos=False)

        def _proposta(com_snapshot):
            p = Proposta(admin_id=t.admin_id,
                         numero=f'P-{uuid.uuid4().hex[:8]}')
            db.session.add(p)
            db.session.flush()
            item = PropostaItem(
                proposta_id=p.id, descricao='Item', unidade='m2',
                quantidade=Decimal('4.505'),
                preco_unitario=Decimal('3.12'),
                subtotal=Decimal('14.06') if com_snapshot else None)
            db.session.add(item)
            db.session.flush()
            return p

        anterior = _proposta(com_snapshot=True)    # 14.06 (2 casas)
        atual = _proposta(com_snapshot=False)      # 14.06316 (produto cru)
        db.session.commit()

        linhas = diff_versoes(anterior, atual)
        situacoes = {l['situacao'] for l in linhas}
        assert situacoes == {'mantido'}, (
            f'linha intocada saiu como {situacoes} — a diferença é só o '
            f'arredondamento do snapshot')
```

⚠️ Confira os campos obrigatórios de `Proposta`/`PropostaItem` antes de rodar
(`grep -n "class PropostaItem" -A 25 models.py`) — o construtor acima cobre os
que o diff lê, não necessariamente todos os `nullable=False`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_o_que_nao_persiste.py -k arredondamento -v`
Expected: **FAIL** — `{'alterado'} != {'mantido'}`.

- [ ] **Step 3: Write minimal implementation**

Comparar na precisão do dinheiro, que é a do snapshot:

```python
from decimal import ROUND_HALF_UP, Decimal

CENTAVO = Decimal('0.01')


def _em_centavos(valor):
    """Dinheiro se compara em centavos.

    `subtotal_calculado` devolve `Numeric(15,2)` quando há snapshot e o
    produto `quantidade × preco_unitario` (até 5 casas) quando não há. Sem
    normalizar, o caso MISTO — comum, e o comentário abaixo já dizia isso —
    fazia linha intocada dar 0.00315 e sair como 'alterado', e o total do
    diff parar de fechar com as duas versões.
    """
    return _dec(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)
```

e a linha 92 vira:

```python
        dv = _em_centavos(it.subtotal_calculado) - _em_centavos(
            anterior.subtotal_calculado)
```

No template, `templates/propostas/comparar.html:78-79`, trocar o `subtotal` cru
pelo mesmo valor que o diff usa:

```jinja
                    <td class="text-end">{{ (item.subtotal_calculado or 0) | brl }}</td>
```

🔬 Filtro conferido: `@app.template_filter('brl')` em `app.py:280`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_o_que_nao_persiste.py -k arredondamento -v`
Expected: **PASS**.

Run: `python -m pytest tests/ -k "proposta or diff" -m "not browser" -q`
Expected: verde.

- [ ] **Step 5: Commit**

```bash
git add tests/test_o_que_nao_persiste.py services/proposta_diff.py templates/propostas/comparar.html
git commit -m "fix(proposta): o diff compara em centavos, e a tela de comparar mostra o mesmo valor"
```

---

### Task 6: O gate, e o fecho do plano

**Files:**
- Nenhum. Só verificação.

- [x] **Step 1: Rodar o gate inteiro**

Run: `bash run_tests.sh --gate`
Expected: **2840 passed, 10 skipped, 201 deselected, 2 xfailed** — ou mais
verdes, somando os testes deste plano.

⚠️ **Confira o número de SKIPPED, não só o de failed.** 🔬 No gate de 28/08 quatro
testes de `tests/test_propagacao_proposta_obra.py` pararam de rodar em silêncio.
Skip subindo é cobertura saindo sem aviso.

⚠️ **A Task 4 acrescenta migration.** Confirme que o runner a aplicou antes de
ler o resultado do gate — migration não aplicada faz o teste passar pelo motivo
errado.

- [x] **Step 2: Marcar os achados**

Em `docs/auditoria/achados-code-review-2026-08-25.md`, seção de 28/08, mover os
cinco de "Abertos" para corrigidos, **com o commit que fechou cada um**.

- [x] **Step 3: Commit do fecho**

```bash
git add docs/
git commit -m "docs(nao-persiste): o plano fecha, com o gate e os cinco achados marcados"
```

---

## Notas de execução

**Ordem recomendada:** 1 → 2 (portal, e a 1 cria o hábito que a 2 generaliza) →
3 → 5 (independentes) → 4 por último, porque é a única com **migration** e a
única que pode falhar por dado pré-existente.

⚠️ **A Task 4 pode abortar por colisão de dados**, e isso é de propósito: a
migration recusa subir se houver duplicata em `(obra_id, admin_id, versao)`.
Se acontecer, **não afrouxe a constraint** — traga as linhas e decida o que
fazer com elas.

⚠️ **Este plano NÃO cobre os seis achados de autorização e vazamento** — eles
estão em `docs/superpowers/plans/2026-08-28-a-porta-irma.md`, porque a causa é
outra: a guarda fechou uma porta e deixou a gêmea aberta.
