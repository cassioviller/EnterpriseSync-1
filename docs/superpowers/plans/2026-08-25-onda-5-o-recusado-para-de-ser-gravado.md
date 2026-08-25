# Onda 5 — O Recusado Para de Ser Gravado Implementation Plan

> **Estado em 2026-08-25 (varredura de fecho):** 🟡 **ABERTO — pronto para executar** — 8 tasks. A Task 1 (traceback no HTML) é **a de maior superfície exposta da varredura e a mais barata de fechar**.
>
> Escrito na varredura de 25/08. Índice de estado de todos os planos e specs em
> `docs/planos-em-aberto-2026-08-25.md`.


> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) ou superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer com que uma operação recusada não deixe rastro no banco, que uma rota sem papel deixe de ser administrável por qualquer um, e que duas entregas da Fase 6 cheguem à tela — fechando os 10 achados de estado inconsistente e de superfície exposta.

**Architecture:** O grupo maior tem raiz num contrato quebrado: 📖 o decorador `_com_undo` **documenta depender** de que "rota que devolveu 400/404 fez rollback ⇒ o diff é vazio" (`cronograma_views.py:181-183`), e três `return 400` não fazem o rollback. A correção é no decorador, não em cada `return` — assim o quarto que nascer já vem certo. O resto são defeitos avulsos, ordenados por superfície exposta: primeiro o traceback no HTML, depois as rotas sem papel, depois o que só erra em silêncio.

**Tech Stack:** Flask, SQLAlchemy 2.0.41, PostgreSQL, pytest, Jinja2.

**Spec:** `docs/superpowers/plans/2026-08-25-fecho-dos-114-achados.md` (Onda 5) — evidência em `docs/auditoria/achados-code-review-2026-08-25.md` §8, §4, §5, §6, §7, §9, §10.

## Global Constraints

- **Recusar é não deixar rastro.** Todo `return 4xx` faz `db.session.rollback()` antes — e o teste que prova isso olha o **banco**, não o código de status.
- **Nada de `traceback` na resposta.** Erro vai para o log; o usuário vê mensagem.
- **Rota que muda configuração da empresa exige papel**, não só `@login_required`.
- **Entrega inalcançável não é entrega.** Toda tela nova tem link de alguma tela existente, e teste que chega nela **pela navegação**.
- **TDD sem exceção**, com o RED citado no commit.
- **Gate ao fim:** `bash run_tests.sh --gate`. Régua: **2560 passed, 6 skipped, 201 deselected, 2 xfailed**.

---

## File Structure

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `ponto_views.py` | Modificar `:611`, `:2338` | Task 1 |
| `cronograma_views.py` | Modificar `:189-215` (`_com_undo`), `:1017`, `:1058`, `:1168`, `:1618` | Task 2 |
| `portal_obras_views.py` | Modificar `:663`, `:768`, `:798`, `:958`, `:534`, `:576` | Task 3 |
| `services/proposta_diff.py` | Modificar `:88` | Task 4 |
| `views/orcamentos_views.py` | Modificar `:617` + templates | Task 4 |
| `services/entregas_terceiros.py` | Modificar `:340`, `:357` | Task 5 |
| `services/cronograma_apontamento_service.py` | Modificar `:397` | Task 5 |
| `services/cronograma_proposta.py` | Modificar `:602`, `:675` | Task 5 |
| `views/rdo.py` | Modificar `:2127`, `:3070`, `:4002`, `:3969`, `:2969` | Task 6 |
| `crud_rdo_completo.py` | Modificar `:602`, `:324` | Task 6 |
| `frota_views.py`, `transporte_views.py`, `reembolso_views.py` | Modificar `:499`, `:741`, `:1063`, `:442`, `:34` | Task 7 |
| `models.py` | Modificar `:7608`, `:8648`, `:7698` | Task 8 |
| `views/aditivos_views.py`, `services/contrato_obra.py`, `templates/` | Modificar | Task 8 |
| `tests/test_onda5_recusado_nao_grava.py` | **Criar** | Todos os testes desta onda |

---

### Task 1: O traceback sai da resposta

> 🔴 **O item de maior superfície exposta da varredura inteira, e o mais barato
> de fechar.** 📖 `/ponto/` e `/equipe/alocacao-principal` renderizam
> `traceback.format_exc()` **no HTML** em caso de erro, expondo caminhos, frames
> e **SQL com os parâmetros vinculados** a qualquer usuário autenticado.

**Files:**
- Modify: `ponto_views.py:611`, `:2338`
- Test: `tests/test_onda5_recusado_nao_grava.py` (criar)

**Interfaces:**
- Consumes: nada.
- Produces: nada.

- [ ] **Step 1: Write the failing test**

Create `tests/test_onda5_recusado_nao_grava.py`:

```python
"""Onda 5 — o recusado para de ser gravado.

A regra dos testes desta onda: o que se afirma é olhado NO BANCO. Código de
status 400 não prova que nada foi gravado — foi exatamente essa confusão que
deixou o `_com_undo` empilhar edições recusadas.
"""
import os
import sys
import uuid

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
        app.secret_key = 'test-onda5-recusado'
    yield


# ---------------------------------------------------------------------------
# Task 1 — o traceback
# ---------------------------------------------------------------------------

def test_nenhuma_rota_de_ponto_renderiza_traceback():
    """🔴 `ponto_views.py:611` — `traceback.format_exc()` no HTML.

    Expunha caminhos, frames e SQL COM PARÂMETROS VINCULADOS a qualquer
    usuário autenticado.
    """
    import inspect

    import ponto_views
    fonte = inspect.getsource(ponto_views)
    assert 'format_exc()' not in fonte, (
        'ponto_views ainda pode mandar traceback para a resposta')


def test_ponto_com_erro_mostra_mensagem_nao_stack():
    """A prova pela porta: mesmo quebrando, a resposta não traz frames."""
    with app.app_context():
        t = um_tenant('onda5_ponto', com_fatos=False)
        admin_id = t.admin_id

    resposta = cliente_de(admin_id).get('/ponto/')
    corpo = resposta.get_data(as_text=True)
    for vazamento in ('Traceback (most recent call last)', 'File "/home/',
                      'sqlalchemy.exc'):
        assert vazamento not in corpo, f'{vazamento!r} vazou na resposta'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_onda5_recusado_nao_grava.py -k traceback -v`
Expected: FAIL — `format_exc()` ainda no fonte.

- [ ] **Step 3: Write minimal implementation**

Nas duas rotas, trocar o `render_template` que recebe o traceback por:

```python
    except Exception:
        # O traceback ia para o HTML: caminhos, frames e SQL com os
        # parâmetros vinculados, visíveis a qualquer usuário autenticado.
        # Erro vai para o log; o usuário vê mensagem.
        logger.exception('falha ao montar a tela de ponto')
        flash('Não foi possível carregar a tela de ponto. '
              'A equipe técnica foi notificada.', 'danger')
        return redirect(url_for('main.dashboard'))
```

⚠️ 📖 Junto, na mesma task: `:2338` — o geofencing é **pulado inteiro** quando o
cliente omite latitude/longitude, o que torna o controle consultivo. Decida
explicitamente: ou ausência de coordenada **recusa** o ponto, ou o registro é
marcado como "sem geolocalização" e a tela mostra isso. **Não deixe silencioso.**

- [ ] **Step 4-5:** verde, e commit.

---

### Task 2: A edição recusada para de ser gravada — e empilhada no undo

> 🔴 📖 **O decorador documenta depender de uma invariante que três rotas
> violam.** `_com_undo` (`cronograma_views.py:181-183`) diz, no próprio
> docstring: *"rota que devolveu 400/404 fez rollback ⇒ o diff é vazio ⇒ nada é
> empilhado, sem tratamento caso a caso"*.
>
> 🔬 Três `return 400` em `atualizar_tarefa` **não fazem o rollback** — `:1017`
> (`modo_apontamento`), `:1058` (subatividade×serviço), `:1168` (hierarquia
> circular) — ao contrário dos vizinhos em `:1000`, `:1010` e `:1130`. O
> `_com_undo` então chama `registrar_acao`, que **autoflusha e commita**: a
> edição recusada é **gravada e empilhada no undo**. Idem `atualizar_vinculo`
> (`:1618`), que atribui `vinculo.tipo` em `:1613` e devolve 400 sem rollback —
> **TI vira II em silêncio.**

**Files:**
- Modify: `cronograma_views.py:189-215` (`_com_undo`), e os quatro `return 400`
- Test: `tests/test_onda5_recusado_nao_grava.py` (acrescentar)

**Interfaces:**
- Consumes: nada.
- Produces: `_com_undo(tipo_acao)` mantém assinatura. Passa a **garantir** a invariante que hoje só documenta.

- [ ] **Step 1: Write the failing test**

```python
# ---------------------------------------------------------------------------
# Task 2 — a edição recusada
# ---------------------------------------------------------------------------

def _obra_com_tarefa(admin_id):
    """Uma tarefa de cronograma real, para a rota ter o que recusar."""
    from models import Obra, TarefaCronograma
    obra = Obra.query.filter_by(admin_id=admin_id).first()
    tarefa = TarefaCronograma(
        obra_id=obra.id, admin_id=admin_id,
        nome=f'Alvenaria {uuid.uuid4().hex[:6]}',
        duracao_dias=5, ativa=True, percentual_concluido=0)
    db.session.add(tarefa)
    db.session.flush()
    return obra, tarefa


def test_modo_apontamento_invalido_nao_grava_nada():
    """🔴 `cronograma_views.py:1017` — `return 400` sem rollback.

    O `_com_undo` então commitava, e a edição recusada era gravada E
    empilhada no undo. O docstring do decorador (`:181`) afirma o contrário.
    """
    from models import TarefaCronograma

    with app.app_context():
        t = um_tenant('onda5_crono', com_fatos=False)
        obra, tarefa = _obra_com_tarefa(t.admin_id)
        db.session.commit()
        admin_id, obra_id, tarefa_id = t.admin_id, obra.id, tarefa.id
        nome_antes = tarefa.nome

    resposta = cliente_de(admin_id).post(
        f'/cronograma/obra/{obra_id}/tarefa/{tarefa_id}/atualizar',
        json={'nome': 'NOME NOVO QUE NAO DEVE ENTRAR',
              'modo_apontamento': 'VALOR_INVALIDO'})
    assert resposta.status_code == 400

    with app.app_context():
        depois = TarefaCronograma.query.get(tarefa_id)
        assert depois.nome == nome_antes, (
            'a edição recusada foi gravada mesmo assim')


def test_o_decorador_garante_a_invariante_que_documenta():
    """A guarda que impede o quarto `return 400` sem rollback de nascer."""
    import inspect

    import cronograma_views
    fonte = inspect.getsource(cronograma_views._com_undo)
    assert 'rollback' in fonte, (
        '_com_undo documenta depender do rollback da rota mas não o garante')
```

⚠️ Confirme a URL real da rota e os campos aceitos:
`grep -n "def atualizar_tarefa" -B 5 cronograma_views.py`

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_onda5_recusado_nao_grava.py -k "modo_apontamento or invariante" -v`
Expected: FAIL — o nome foi gravado, e `_com_undo` não menciona rollback.

- [ ] **Step 3: Write minimal implementation**

**3a.** No `_com_undo`, garantir a invariante em vez de confiar nela:

```python
                resposta = view(obra_id, *args, **kwargs)

                # A invariante que este decorador SEMPRE documentou depender
                # ("rota que devolveu 400/404 fez rollback ⇒ diff vazio ⇒ nada
                # empilhado") não era garantida por ninguém: três `return 400`
                # de `atualizar_tarefa` e um de `atualizar_vinculo` pulavam o
                # rollback, e o `registrar_acao` abaixo autoflushava e
                # commitava a edição recusada — gravando-a E empilhando-a no
                # undo. Agora a garantia mora aqui, e o quarto `return 400`
                # que nascer já vem certo.
                codigo = getattr(resposta, 'status_code', None)
                if codigo is None and isinstance(resposta, tuple) and len(resposta) > 1:
                    codigo = resposta[1]
                if codigo and int(codigo) >= 400:
                    db.session.rollback()
                    return resposta
```

**3b.** Acrescentar `db.session.rollback()` nos quatro `return 400` mesmo assim
— cinto e suspensório, e deixa cada rota legível isoladamente.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_onda5_recusado_nao_grava.py -v`
Expected: PASS

Run: `python -m pytest tests/ -k cronograma -m "not browser" -q`
Expected: PASS, mesma contagem de antes.

- [ ] **Step 5: Commit**

```bash
git add cronograma_views.py tests/test_onda5_recusado_nao_grava.py
git commit -m "fix(cronograma): a edicao recusada para de ser gravada e empilhada no undo

RED: o nome foi gravado apesar do 400; _com_undo nao mencionava rollback

O docstring de _com_undo (:181) afirma como GARANTIA que 'rota que devolveu
400/404 fez rollback => o diff e vazio => nada e empilhado'. Tres return 400
de atualizar_tarefa e um de atualizar_vinculo nao faziam o rollback, e o
registrar_acao autoflushava e commitava.

A garantia passa a morar no decorador: o quarto return 400 que nascer ja vem
certo."
```

---

### Task 3: O portal para de ser administrável por qualquer um

**Files:**
- Modify: `portal_obras_views.py:768`, `:798`, `:663`, `:958`, `:534`, `:576`
- Test: `tests/test_onda5_recusado_nao_grava.py` (acrescentar)

🔴 📖 `:768` e `:798` — `toggle_portal` e `gerar_medicao` têm **só
`@login_required`**. Qualquer FUNCIONARIO do tenant liga/desliga o portal do
cliente — **recarimbando `token_cliente_expira_em` +180 dias sem rotacionar o
token** — ou cria uma `MedicaoObra` cujo `valor_medido` é percentual de
`obra.valor_contrato`. 📖 Rotas administrativas comparáveis usam
`admin_required`, e `templates/obras/detalhes_obra_profissional.html:1477,1657`
renderizam os dois botões **sem condição**.

📖 `:663` — o fallback de 5 MB é **morto**: `app.py:159` põe
`MAX_CONTENT_LENGTH = 64 MB`, então `max_bytes` é sempre 64 MB. Sobra rota
**anônima, sem autenticação e sem rate limit** gravando blobs de 64 MB no volume
persistente a cada requisição.

📖 `:958` — `os.path.join(static_root, rel.arquivo_path)` sem checar que o
resultado fica sob `static/`. Latente hoje; leitor de arquivo arbitrário no dia
em que aquela coluna de 500 chars receber um `../`. **É o mesmo defeito que fez
remover `/persistent-uploads`** (`app.py:176`).

- [ ] **Step 1-5:** um teste por item — FUNCIONARIO recebendo 403 em
  `toggle_portal`, upload de 6 MB sendo recusado, e `arquivo_path` com `../`
  devolvendo 404 —, correção, verde, commit.

⚠️ **Ao pôr papel nas duas rotas, ponha a condição no template também.** Botão
que aparece e dá 403 é pior que botão que não aparece.

---

### Task 4: As duas entregas da Fase 6 chegam à tela

**Files:**
- Modify: `services/proposta_diff.py:88`, `views/orcamentos_views.py:617`, e os templates
- Test: `tests/test_onda5_recusado_nao_grava.py` (acrescentar)

🔴 📖 `proposta_diff.py:88` — `diff_versoes`/`total_do_diff` leem
`PropostaItem.subtotal`, que é **NULL** para todo item não construído pelo
caminho de explosão da Task #89 (`subtotal_snap = None` em
`propostas_consolidated.py:899`). Uma revisão que muda **só** `preco_unitario`
aparece como "mantido" e a tela nova reporta **impacto R$ 0,00**.
🔬 `PropostaItem.subtotal_calculado` existe exatamente para isso e **não é usado
em lugar nenhum**.

⚪ 📖 `views/orcamentos_views.py:617` — **nem `orcamentos.comparar` nem
`propostas.comparar` são linkados de template nenhum.** A Task 12 inteira da
Fase 6 foi entregue **inalcançável pela interface**.

- [ ] **Step 1: Write the failing test**

```python
def test_revisao_que_muda_so_o_preco_aparece_no_diff():
    """🔴 `services/proposta_diff.py:88` — lê `subtotal`, NULL fora da Task #89.

    Revisão que muda só `preco_unitario` saía como "mantido", com impacto
    R$ 0,00.
    """
    import inspect

    from services import proposta_diff
    fonte = inspect.getsource(proposta_diff)
    assert 'subtotal_calculado' in fonte, (
        'o diff ainda lê `subtotal`, que é NULL para a maioria dos itens')


def test_a_tela_de_comparar_e_alcancavel_pela_navegacao():
    """Entrega inalcançável não é entrega."""
    import subprocess
    saida = subprocess.run(
        ['grep', '-rl', 'orcamentos.comparar', 'templates/'],
        capture_output=True, text=True).stdout
    assert saida.strip(), (
        'nenhum template linka orcamentos.comparar — a Task 12 da Fase 6 '
        'segue inalcançável')
```

- [ ] **Step 2-5:** RED, correção (`subtotal_calculado` no diff; link nas telas
  de proposta e de orçamento), verde, commit.

---

### Task 5: O progresso que é apagado e o retrocesso que passa

**Files:**
- Modify: `services/entregas_terceiros.py:340`, `:357`; `services/cronograma_apontamento_service.py:397`; `services/cronograma_proposta.py:602`, `:675`
- Test: `tests/test_onda5_recusado_nao_grava.py` (acrescentar)

🟡 📖 `entregas_terceiros.py:340` — o toggle reverso põe `percentual_concluido =
0.0` em **toda** tarefa de `terceiros_tarefa_ids_lista[]` não marcada em
`entrega_tarefa_ids[]`. **Subempreitada em 45% é zerada** no próximo salvamento
de RDO que não a marque. O docstring só promete reverter *"para pendente"* —
progresso parcial é dado real, não estado.

🟡 📖 `:357` — o `except` pelado devolve `(0, 0)` **depois** de os laços já terem
mutado `TarefaCronograma` na sessão, e o chamador commita: escrita parcial
reportando que nada foi aplicado.

🟡 📖 `cronograma_apontamento_service.py:397` — `registrar_apontamento` lê
`pct_ant` só de `percentual_realizado` (travado em 100) enquanto
`recomputar_cadeia:246` prefere `percentual_acumulado`. Depois de uma
superexecução (120 acumulado / 100 realizado), uma regressão real para 110%
**passa por baixo** da guarda `RetrocessoNaoPermitido` e grava incremento +10,
que qualquer recompute depois vira **−10**.

🟡 📖 `cronograma_proposta.py:602`/`:675` — os ramos de reúso por chave natural
reaproveitam a tarefa casada **sem restaurar `ativa`**: item suprimido e
re-adicionado como *novo* (sem linhagem → `reativar_…` nunca roda) fica **sem
tarefa viva**, em silêncio. `natural_key_index` não filtra `ativa`.

- [ ] **Step 1-5:** um teste por defeito, RED, correção, verde, **um commit por
  defeito** — são independentes e misturá-los impede a bisseção.

---

### Task 6: Os RDOs que quebram, duplicam ou perdem dado

**Files:**
- Modify: `views/rdo.py:2127`, `:3070`, `:4002`, `:3969`, `:2969`; `crud_rdo_completo.py:602`, `:324`
- Test: `tests/test_onda5_recusado_nao_grava.py` (acrescentar)

🔴 📖 `views/rdo.py:2127` — `atualizar_rdo` lê `rdo.tempo_manha`, que **não é
atributo de `RDO`**: todo POST em `/rdo/<id>/atualizar` levanta `AttributeError` e
faz rollback. 🔬 **Verificado em runtime — a rota está morta.**
🔴 📖 `:3070` — `obra_id` não vinculada no ramo de edição de
`rdo_salvar_unificado`; o `NameError` **escapa** do `except (ValueError,
IndexError)` local e aborta a edição inteira.
🟡 📖 `:4002` — `salvar_rdo_flexivel` ignora `rdo_id` e não tem guarda de
obra+data: **é o produtor dos RDOs duplicados na mesma data** que os serviços de
exportação e atualização contornam.
🟡 📖 `:3969` — a colisão de `numero_rdo` é checada por `admin_id` embora a coluna
seja `UNIQUE` **global**: uma linha com `admin_id` NULL causa `IntegrityError` em
laço permanente.
⚪ 📖 `:2969` e `crud_rdo_completo.py:602` — campos gravados em atributos **não
mapeados** e perdidos em silêncio, inclusive `finalizado_em`/`finalizado_por_id`
(**a autoria da finalização**) numa rota viva.
⚪ 📖 `crud_rdo_completo.py:324` — `salvar_rdo` usa `func` não importado e passa
kwargs que `RDO` não aceita. Sem rota, mas marcada para revival: **ou conserte,
ou apague.**

- [ ] **Step 1-5:** um teste por defeito, RED, correção, verde, commit.

⚠️ 🔬 `:4002` é o mais caro: consertar a duplicação **muda o que os serviços de
exportação e atualização recebem**. Rode `tests/test_rdo_*` inteiro depois, e leia
os contornos que eles fazem hoje — alguns podem sair junto.

---

### Task 7: Frota, transporte e reembolso

**Files:**
- Modify: `frota_views.py:499`, `:741`, `:1063`; `transporte_views.py:442`; `reembolso_views.py:34`
- Test: `tests/test_onda5_recusado_nao_grava.py` (acrescentar)

🟡 📖 `frota_views.py:499` — `veiculo.km_atual = km_final` **sem comparação**: um
uso retroativo faz o **odômetro andar para trás** e cala o alerta de manutenção.
🔬 As três rotas irmãs têm a guarda — só esta ficou de fora.
🟡 📖 `:741` — a edição lê passageiros de `to_dict()` (**só o primeiro valor do
multi-select**) enquanto a criação usa `getlist`+CSV; e apaga
`responsavel_veiculo`/`observacoes` quando o campo não vem no form.
🟡 📖 `:1063` — `.join(FrotaVeiculo)` **duplicado** (tipo + status). 🔬 Confirmado
no SA 2.0.41 que o segundo join **não** é deduplicado → o filtro por tipo do
dashboard TCO **sempre erra**.
🟡 📖 `transporte_views.py:442` — o lote grava sem `origem_id`, e
`_limpar_gestao_custo_filho` filtra por `origem_id`: excluir lançamento em lote
**deixa o valor vivo em Contas a Pagar** dizendo *"Gestão de Custos atualizada"*.
🟡 📖 `reembolso_views.py:34` — `url_for('main_bp.dashboard')`; 🔬 o blueprint
chama-se `main` (`views/__init__.py:6`). Tenant sem V2 clicando em Reembolsos
recebe **BuildError 500** em vez do aviso.

- [ ] **Step 1-5:** um teste por defeito, RED, correção, verde, commit.

---

### Task 8: Os índices que discordam das queries, e o resto da Fase 6

**Files:**
- Modify: `models.py:7608`, `:8648`, `:7698`; `services/contrato_obra.py:407`; `views/aditivos_views.py:143`, `:147`, `:74`; `templates/aditivos/listar.html:50`; `templates/obras/detalhes_obra_profissional.html:1316`
- Test: `tests/test_onda5_recusado_nao_grava.py` (acrescentar)

🟡 📖 `models.py:7608` — `uq_contrato_versao_vigente` é `UNIQUE (obra_id) WHERE
vigente_ate IS NULL`, mas **todo leitor filtra por `(obra_id, admin_id)`**. Uma
linha com `admin_id` divergente — e 🔬 a migration 273 **cita precedente real, a
266** — trava a obra **permanentemente**: `abrir_versao` não vê a linha, nunca a
fecha, e seu INSERT de uma segunda `vigente_ate IS NULL` viola o índice →
`IntegrityError` em toda escrita de contrato daquela obra, enquanto
`abrir_aditivo` reporta *"obra não tem contrato vigente"*.

⚠️ **Escolha explícita, e diga qual:** ou o índice ganha `admin_id`, ou as queries
o perdem. **As duas resolvem; misturar não.** A primeira é mais segura (mantém o
escopo por tenant em toda parte); a segunda é mais simples (o `obra_id` já é único
globalmente). O plano recomenda **a primeira** — e ela **precisa de migration**,
com o máximo do repo conferido no dia do commit.

⚪ 📖 `models.py:8648` — a migration 274 cria `versao INTEGER NOT NULL DEFAULT 1`;
o modelo declara `nullable=False, default=1` **sem `server_default`**. Schema
criado por `db.create_all()` (tenant novo, CI via `pre_start.py`) fica **sem
default no banco**, enquanto produção migrada tem: INSERT fora do ORM funciona
em produção e falha com `NotNullViolation` em schema novo. **Os dois schemas
discordam em silêncio.** Falta `server_default=db.text('1')`.

⚪ 📖 `models.py:7698` — o backref de `AditivoContrato.obra` usa
`passive_deletes=True` mas, ao contrário do irmão `ObraContratoVersao.obra`
**criado no mesmo hunk**, omite `cascade='all, delete-orphan'`.

⚪ 📖 `templates/obras/detalhes_obra_profissional.html:1316` — `app.py:940-953`
engole **de propósito** a falha de registro do `aditivos_bp` (loga e segue de
pé), mas a página faz `url_for('aditivos.listar', ...)` **sem guarda**: se o
blueprint não registrar — o cenário que o `app.py` foi escrito para sobreviver —
**toda obra com `valor_contrato > 0` dá BuildError 500**. 🔬
`templates/obra_form.html` usa href literal e está safe.

⚪ Junto: `contrato_obra.py:407` (`_versao_vigente_da_obra` pode devolver versão
já encerrada em memória), `aditivos_views.py:143` (`aprovar_aditivo` pode
devolver `None` e a view faz `float(versao.valor)` **depois** do commit),
`:147` (o reformat de moeda aplicado à **frase inteira**: o ponto final vira
vírgula), `:74` (`pode_editar=True` fixo — usuário só-leitura vê "Aprovar" e leva
404 opaco), `templates/aditivos/listar.html:50` (o mapa de rótulos usa
`'proposta'`/`'manual'`, mas `ORIGEM_TIPO` grava `proposta_aprovada`,
`cadastro_manual`, `contrato_original`, `backfill` — **só `aditivo` casa**).

- [ ] **Step 1-5:** RED, correção, verde, commit. **A migration do índice em
  commit próprio**, com dupla execução provada no banco de dev.

- [ ] **Step 6: Run the full gate**

Run: `bash run_tests.sh --gate`
Expected: **2560 passed, 6 skipped, 201 deselected, 2 xfailed** — ou mais verdes.

---

## Fecho da onda

- [ ] `bash run_tests.sh --gate` verde, com a contagem registrada.
- [ ] A escolha da Task 8 (índice ganha `admin_id` **ou** queries o perdem)
      registrada aqui, com o porquê.
- [ ] `docs/auditoria/achados-code-review-2026-08-25.md` — marcar os 10 achados.
- [ ] 🔬 `grep -rn "format_exc" --include=*.py . | grep -v __pycache__ | grep -v tests/`
      — nenhum resultado fora de log.
