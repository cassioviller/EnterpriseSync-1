# As Issues de Arquitetura — Implementation Plan

> ## 📊 Estado das oito issues, medido em 2026-09-03
>
> As oito issues de `docs/superpowers/issues/` (A–H) nasceram do plano de
> remediação de 08/06. Este plano as reconferiu **uma a uma contra a árvore de
> hoje**, e não contra o texto delas.
>
> | Destino | Quantas | Quais |
> |---|---|---|
> | **Viram task neste plano** | **5** | **A**, **B**, **C**, **E**, **H** (parcial) |
> | **Fechadas ou absorvidas — não viram task** | **1** | **D** (metade fechada pela migration 218; a outra metade é a **Task 12** do plano mestre) |
> | **Adiadas, com motivo escrito** | **2** | **F** (a evidência não sobreviveu à medição), **G** (depende do registro persistido que a issue B deixa fora do escopo mínimo) |
> | **Dependem de decisão humana** | **0** | nenhuma das sete bloqueia por decisão — ver a seção final, que registra as **três decisões de projeto** que este plano toma e cujo custo de erro está declarado |
>
> **8 tasks.** Sete de código, uma de fecho. Nenhuma cria migration.
>
> 🔴 **Recortes adiados, nomeados** (não somem, mas não viram task hoje):
> o **ADR do plano de contas** (recorte da D), o **registro de pendências e o
> painel de integrações** (recortes da B), o **serviço de prontidão** (G), a
> **extração do registro de migrations** (recorte da H, colide com a T8 e a
> T12), e os **20 arquivos de teste restantes que embrulham `main()` num único
> `test_`** (recorte da H, cujo padrão de conserto a Task 4 estabelece).
>
> ⚠️ **Este plano é a Task 9 de `2026-08-31-fecho-do-que-esta-aberto.md` e roda
> DEPOIS da T12.** A ordem do plano mestre é T7 → T8 → T12 → T13 → **T9** → T14
> → T15 → T16. Não é preferência: a **Task 12 entrega a fonte única do plano de
> contas**, que é a issue D, e a Task 1 deste plano toca a mesma classe
> (`PlanoContas`, em `models.py`) que a T12 ganha duas colunas novas.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para executar este plano task a task. Os passos usam checkbox (`- [ ]`) para acompanhamento.

**Goal:** Fechar a dívida de arquitetura que sobreviveu a três meses — o cache
que devolve entidade ORM, os dois `url_map` divergentes entre a app importável
e a de produção, o cálculo de preço duplicado em JavaScript, a folha que diz
"sucesso" com o lançamento contábil no chão, e os testes que existem no disco e
não existem na suíte — **sem inventar task para issue que já morreu e sem
adiar nada em silêncio**.

**Architecture:** Quatro naturezas, e cada uma tem um teste de forma diferente.
**(a) Cache que devolve identidade em vez de valor** — `@lru_cache` sobre
`Model.query...first()` guarda a instância entre requests; depois do
`session.remove()` do teardown ela está *detached* e, se o request anterior
commitou, expirada: o acesso ao atributo levanta `DetachedInstanceError`. Prova:
dois `app_context()` seguidos, com controle positivo do detachment.
**(b) Dois `url_map`** — `app.py` registra 38 blueprints, `main.py` acrescenta
15, e a guarda de layout só roda no fim do `main.py`. Prova: **subprocesso** que
importa só `app` e conta o `url_map` — dentro do processo do pytest o `conftest`
já importou `main` e a asserção passaria por verdade vácua.
**(c) Fórmula duplicada** — a mesma conta vive em `services/orcamento_view_service.py`,
no `<script>` de `templates/orcamentos/editar.html`, e **transcrita duas vezes**
dentro do próprio teste de paridade. Prova: chamar o backend de verdade.
**(d) Efeito colateral que falha em silêncio** — `gerar_lancamento_contabil_automatico`
promete na docstring "NUNCA propaga exceções", devolve `False`, e o chamador
descarta o retorno e dá `flash('...com sucesso!')`. Prova: resposta HTTP.

**Tech Stack:** Flask 3 + Flask-Login, SQLAlchemy 2.0.41, PostgreSQL, pytest,
Jinja2. Migrations pelo runner caseiro de `migrations.py` (tupla ordenada, não
Alembic) — **este plano não cria nenhuma**.

**Spec:** `docs/superpowers/issues/README.md` e os oito arquivos `A-*.md` a
`H-*.md`, derivados de
`docs/superpowers/plans/2026-06-08-remediacao-saude-app-plan.md`.

---

## Global Constraints

- **TDD sem exceção.** O teste vem primeiro, o **RED é conferido e citado no
  commit**, e só então o código. Nenhuma exceção neste plano.
- **Um teste de guarda tem de reprovar também quando o próprio gatilho para de
  funcionar.** Se o teste depende de um erro injetado ou de um efeito de
  ambiente (detachment de sessão, subprocesso que não importa `main`,
  monkeypatch que faz o lançamento falhar), ele **afirma primeiro que o gatilho
  ocorreu**. 🔬 É a constraint que já pegou dois defeitos nesta linhagem: a
  Task 2 do plano mestre (asserção de ausência sem âncora positiva) e a onp/Task 1
  (o `first_or_404` interceptava o gatilho antes do `except`).
- **Nenhum teste prova por `inspect.getsource()` nem por regex sobre template.**
  O que se afirma é olhado **no banco**, na **resposta HTTP** ou no **`url_map`**.
  🔬 Esta constraint é o que reprova o teste que a Task 4 reescreve: ele afirma a
  fórmula do template com `re.search` e a do backend com uma transcrição à mão —
  e por isso não viu uma divergência de **R$ 0,05**, dez vezes a própria
  tolerância dele.
- **Localizar por conteúdo, nunca por número de linha.** As T7, T12 e T13 do
  plano mestre rodam **antes** deste plano e mexem em `main.py`,
  `contabilidade_utils.py`, `models.py` e nas views. Toda linha citada aqui foi
  medida em **2026-09-03** e vai ter andado.
- **Este plano não cria migration.** 🔬 O máximo registrado hoje é **318**
  (`migrations.py:7884`, `_migration_318_flag_folha_rateio_encargos`); a tupla
  `migrations_to_run` (`migrations.py:7624`) tem **248 entradas, de 20 a 318, em
  ordem e sem duplicata**. A T8 reserva 319/320/321 e a T12 reserva 322/323
  (ruling C1 do pré-voo). Se alguma task deste plano vier a precisar de uma
  migration, **confira o máximo real no dia** (`grep -n "_migration_3[0-9][0-9]_" migrations.py | tail -3`)
  — nunca reserve faixa.
- **Um implementador de cada vez.** 🔴 Ruling do ledger de 31/08: o índice do
  git é estado compartilhado e a paralelização de implementadores já arrastou o
  arquivo de uma task para o commit de outra. Vale mesmo com arquivos disjuntos.
- **Gate ao fim:** `bash run_tests.sh --gate`. Piso vigente **3247 passed / 8
  skipped / 201 deselected / 72 xfailed / 0 failed**. O `skipped` **nunca sobe**;
  os `xfailed` são `strict=True` e **só descem**. A suíte com browser tem piso
  **3435 passed / 1 failed** — o `1 failed` é o achado P4 do RDO unificado, o
  único vermelho conhecido, e continua sendo o único depois deste plano.

---

## File Structure

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `models.py` | Modificar `ParametrosLegais.get_parametros_cached` e `PlanoContas.get_conta_cached` (hoje `:3186-3211` e `:3284-3310`) | Task 1 |
| `services/folha_service.py` | Modificar — remover `_cache_parametros_legais` (`:56`) e `limpar_cache_parametros_legais` (`:91-95`) | Task 1 |
| `blueprints_registry.py` | **Criar** — a fábrica única de registro | Task 2 |
| `app.py` | Modificar o fim do arquivo (chama a fábrica) | Task 2 |
| `main.py` | Modificar — os 15 blocos `try/except` de registro passam à fábrica | Task 2 |
| `tests/conftest.py` | Modificar `:61-66` e `:92-117` — os dois contornos de `import main` | Task 3 |
| `tests/test_orcamento_pricing_parity.py` | **Reescrever** — deixa de ser script com `sys.exit` e passa a chamar o backend real | Task 4 |
| `views/orcamentos_views.py` | Modificar — rota de preview de preço | Task 5 |
| `templates/orcamentos/editar.html` | Modificar `:1019-1025` — a fórmula sai do JS | Task 5 |
| `folha_pagamento_views.py` | Modificar `:316-336` — o retorno para de ser descartado | Task 6 |
| `tests/test_propostas_block_scripts_213.py` | Modificar ou apagar — hoje coleta **zero** testes | Task 7 |
| `docs/superpowers/issues/README.md` | Modificar — coluna de estado apontando para este plano | Task 8 |
| `tests/test_issues_de_arquitetura.py` | **Criar** | Testes das Tasks 1, 2, 3, 6 e 7 |

---

### Task 1: Os dois getters cacheados param de devolver entidade ORM

> 🔴 📖 `models.py:3186-3188` e `models.py:3284-3286`. Dois `@staticmethod` com
> `@lru_cache` que devolvem instância SQLAlchemy:
>
> ```python
> @staticmethod
> @lru_cache(maxsize=128)
> def get_parametros_cached(admin_id: int, ano: int):
>     return ParametrosLegais.query.filter_by(...).first()   # models.py:3188
>
> @staticmethod
> @lru_cache(maxsize=256)
> def get_conta_cached(admin_id: int, codigo: str):
>     return PlanoContas.query.filter_by(...).first()        # models.py:3286
> ```
>
> O `lru_cache` é **de processo**: em worker longevo a instância sobrevive ao
> `db.session.remove()` do teardown, e se o request que a cacheou commitou
> (`expire_on_commit=True` é o padrão) os atributos ficam expirados. No request
> seguinte o acesso levanta `DetachedInstanceError`. É exatamente o defeito que
> `_obter_parametros_legais` já teve, e cuja correção está documentada na
> docstring de 📖 `services/folha_service.py:58-72` — este plano só aplica o
> mesmo padrão aos dois que ficaram.
>
> 🔬 **Medição que muda a forma da task: os dois getters têm ZERO chamadores.**
> `grep -rn "get_conta_cached\|get_parametros_cached"` sobre `*.py`, `*.html` e
> `*.js` devolve **só as definições e os dois `cache_clear()`**. O bug é
> **latente**, não ativo — é por isso que a issue A é P1 de **baixo risco**.
>
> ⚠️ **Por que converter e não apagar.** Apagar o par getter+`invalidar_cache`
> obrigaria a editar os 📖 **6 chamadores vivos de `invalidar_cache()`**
> (`financeiro_seeds.py:150`; `contabilidade_utils.py:112` e `:1654`;
> `folha_pagamento_views.py:435`, `:501`, `:527`) — e um deles,
> `contabilidade_utils.py:1654`, está **dentro de `seed_plano_contas_if_needed`**,
> que é o sítio central da **Task 12**. Converter mantém a superfície pública
> intacta e não colide.

**Files:**
- Modify: `models.py` (`ParametrosLegais.get_parametros_cached`, `PlanoContas.get_conta_cached`)
- Modify: `services/folha_service.py` (`_cache_parametros_legais`, `limpar_cache_parametros_legais`)
- Test: `tests/test_issues_de_arquitetura.py` (criar)

**Interfaces:**
- Consumes: `ParametrosLegais`, `PlanoContas` (`models.py`); o padrão de referência em `services/folha_service.py:58`.
- Produces: value-objects imutáveis para os dois getters; `invalidar_cache()` continua existindo e continua funcionando para os 6 chamadores.

- [ ] **Step 0: Reconferir antes de tocar**

A T12 roda antes desta task e **acrescenta duas colunas** a `plano_contas`
(`classificacao_gasto`, `atividade_dfc`). Confira, por leitura:

```bash
grep -n "class PlanoContas" -A 40 models.py | grep -n "classificacao_gasto\|atividade_dfc\|get_conta_cached"
grep -rn "get_conta_cached\|get_parametros_cached" --include="*.py" --include="*.html" --include="*.js" .
```

Se a T12 tiver criado um consumidor novo de `get_conta_cached`, ele entra no
Step 3 desta task. Se o número de chamadores continuar **zero**, registre isso
no commit — é o que sustenta o risco baixo.

- [ ] **Step 1: Write the failing test**

Crie `tests/test_issues_de_arquitetura.py`. O teste tem **duas metades, e a
primeira é o controle positivo** — sem ela, o teste passaria verde no dia em que
o `app_context` deixasse de destacar a sessão:

```python
"""As issues de arquitetura (docs/superpowers/issues/), reconferidas em 09/2026.

A regra destes testes é a da casa: o que se afirma é olhado no BANCO, na
RESPOSTA HTTP ou no `url_map` — nunca no texto do código.
"""

def test_getter_cacheado_devolve_valor_e_nao_entidade_detached(app, tenant):
    from sqlalchemy.orm.exc import DetachedInstanceError
    from models import ParametrosLegais, db

    # --- CONTROLE POSITIVO: o gatilho existe -------------------------------
    # Sem isto o teste passaria por verdade vácua se o teardown parasse de
    # destacar a sessão. Uma instância ORM comum, commitada e depois solta do
    # contexto, TEM de levantar ao acessar atributo expirado.
    with app.app_context():
        crua = ParametrosLegais.query.filter_by(
            admin_id=tenant.admin_id, ano_vigencia=2026).first()
        assert crua is not None, 'seed do teste não criou ParametrosLegais'
        db.session.commit()          # expire_on_commit expira os atributos
    with pytest.raises(DetachedInstanceError):
        _ = crua.ano_vigencia        # ← o gatilho, provado

    # --- A AFIRMAÇÃO -------------------------------------------------------
    with app.app_context():
        ParametrosLegais.get_parametros_cached(tenant.admin_id, 2026)
        db.session.commit()
    with app.app_context():
        p = ParametrosLegais.get_parametros_cached(tenant.admin_id, 2026)
        assert p is not None
        assert p.ano_vigencia == 2026     # hoje: DetachedInstanceError
```

O mesmo par para `PlanoContas.get_conta_cached(admin_id, codigo)`, lendo `nome`
e `tipo_conta` — os dois campos que a T12 usa.

Um terceiro teste guarda a invalidação, que é o contrato dos 6 chamadores:
editar a linha no banco, chamar `invalidar_cache()`, e afirmar que o **próximo**
`get_..._cached` devolve o valor novo.

⚠️ **`lru_cache` é global do processo.** Os testes têm de chamar
`invalidar_cache()` no setup **e** no teardown, senão contaminam a suíte pela
ordem de coleção. Use uma fixture com `yield`.

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_issues_de_arquitetura.py -k "getter_cacheado" -x -q
```

O RED esperado é `DetachedInstanceError` na **segunda** metade, com a primeira
já verde. **Se a primeira metade falhar, PARE**: o controle positivo não vale e
o teste não prova nada — reveja o gatilho antes de mexer no código.

Copie a linha do erro para a mensagem do commit.

- [ ] **Step 3: A correção**

Em `models.py`, cada getter passa a devolver um value-object imutável com os
campos que os consumidores usam:

```python
ParametrosLegaisView = namedtuple('ParametrosLegaisView', [...])
PlanoContasView = namedtuple('PlanoContasView', ['admin_id', 'codigo', 'nome',
                                                 'tipo_conta', 'natureza',
                                                 'nivel', 'conta_pai_codigo',
                                                 'aceita_lancamento', 'ativo'])
```

Regras:
- O `@lru_cache` **fica** — o que muda é o que ele guarda. É valor, não identidade.
- `invalidar_cache()` **não muda de assinatura**: continua chamando `cache_clear()`.
- O getter devolve `None` quando não acha, como hoje.
- ⚠️ Se a T12 tiver acrescentado `classificacao_gasto` e `atividade_dfc` a
  `plano_contas`, os dois campos entram no `PlanoContasView`. **Confira na
  classe, não nesta lista.**

- [ ] **Step 4: A remoção do cache morto de `folha_service`**

📖 `services/folha_service.py:56` declara `_cache_parametros_legais = {}` e
`:91-95` declara `limpar_cache_parametros_legais()`, que o zera. 🔬 **Ninguém
escreve nesse dicionário e ninguém chama essa função** — `grep` sobre `*.py` e
`*.html` devolve só as próprias cinco linhas. É o resíduo da correção que a
docstring de `:58-72` descreve.

Apague os dois. **Não há teste próprio para isto** e a task declara isso em vez
de fabricar um: é remoção de código provadamente morto, e a rede é o Step 5.

- [ ] **Step 5: Run test to verify it passes**

```bash
python -m pytest tests/test_issues_de_arquitetura.py -q
python -m pytest tests/ -m "not browser" -k "folha or contab or plano_contas" -q
```

A segunda varredura é a adjacência: os dois modelos tocados são os da folha e
da contabilidade. Registre o número.

- [ ] **Step 6: Commit**

```bash
git add models.py services/folha_service.py tests/test_issues_de_arquitetura.py
git commit -m "fix(issue-a): cache guarda valor, nunca entidade ORM

RED: DetachedInstanceError em get_parametros_cached no 2o app_context
(<cole a linha>). Controle positivo verde: a instancia ORM crua levanta no
mesmo cenario, provando o gatilho.

Os dois getters passam a devolver namedtuple; invalidar_cache() inalterado
para os 6 chamadores. Removidos _cache_parametros_legais e
limpar_cache_parametros_legais (folha_service), sem escritor e sem chamador."
```

---

### Task 2: Uma fábrica só registra os blueprints — `app` e `main:app` passam a ter o mesmo `url_map`

> 🔴 🔬 Medido em 03/09: `app.py` faz **38** `register_blueprint`; `main.py` faz
> mais **15**, entre eles `portal_obras_bp`, `medicao_bp`, `importacao_bp`,
> `custos_escritorio_bp`, `catalogos_bp`, `cadastros_hub_bp`, `rdo_editar_bp` e
> `rdo_crud_bp`. Quem faz `from app import app` recebe uma aplicação **sem
> esses módulos**.
>
> 📖 O próprio `app.py` documenta a consequência, no fim do arquivo:
>
> > *"⚠️ A CHAMADA NÃO MORA AQUI (…) quatro blueprints do layout
> > (`cadastros_hub`, `catalogos`, `custos_escritorio`, `importacao`) são
> > registrados no `main.py`, não neste arquivo. Conferir no fim do `app.py`
> > reprovaria um app que ainda está sendo montado."*
>
> A guarda `_conferir_endpoints_do_layout` existe (`app.py:1132`) e só é chamada
> em 📖 `main.py:303`. Ela é a rede contra o modo de falha real de 19/08 —
> blueprint que falha ao registrar, `except` que loga WARNING e segue, e
> `base_completo.html` servindo **500 em toda página autenticada**
> (`tests/test_boot_endpoints_do_layout.py:1-26` conta o caso medido). Hoje essa
> rede **não cobre a app importável**.

**Files:**
- Create: `blueprints_registry.py`
- Modify: `app.py` (fim do arquivo)
- Modify: `main.py` (os 15 blocos de registro)
- Test: `tests/test_issues_de_arquitetura.py`

**Interfaces:**
- Consumes: os 53 blueprints; `_conferir_endpoints_do_layout` (`app.py:1132`).
- Produces: `registrar_blueprints(aplicacao)` — idempotente, tolerante a falha por blueprint, chamada por `app.py` e delegada por `main.py`.

- [ ] **Step 0: Reconferir antes de tocar — a T7 mexeu no `main.py`**

🔴 A **T7 (Onda 4)** roda antes desta task e o **Step 0-b dela apaga
`exportacao_relatorios.py`**, inclusive o registro em `main.py` (era `:157-158`
em 02/09). **Não assuma 15.** Meça:

```bash
grep -c "app.register_blueprint" app.py
grep -n "app.register_blueprint" main.py
```

O número que vale é o do dia. O teste do Step 1 **não fixa contagem** — compara
conjuntos.

- [ ] **Step 1: Write the failing test**

⚠️ **Este teste PRECISA de subprocesso, e o motivo é a constraint do gate.**
📖 `tests/conftest.py:65` faz `import main` **no nível de módulo do conftest**,
antes de qualquer coleção. Dentro do processo do pytest, `app` e `main.app` são
**o mesmo objeto já completo**: comparar os dois `url_map` ali passaria verde
hoje, por verdade vácua, exatamente o defeito que a Task 2 do plano mestre
levou para fix round.

Prior art de subprocesso na casa: 📖 `tests/test_cronograma_normalizacao.py:339`
e `tests/test_cronograma_reconciliacao.py:422`
(`subprocess.run([sys.executable, '-c', codigo], cwd=RAIZ, ...)`).

```python
_CODIGO = r'''
import os, sys, json
os.environ.setdefault("SIGE_ENABLE_DEMO_SEED", "false")   # conftest.py:61
os.environ.setdefault("SIGE_BOOT_DDL", "0")               # conftest.py:62
from app import app
saida = {
    "importou_main": "main" in sys.modules,     # CONTROLE: tem de ser False
    "endpoints": sorted({r.endpoint for r in app.url_map.iter_rules()}),
}
import main                                     # agora sim, o conjunto cheio
saida["endpoints_com_main"] = sorted({r.endpoint for r in app.url_map.iter_rules()})
print("JSON:" + json.dumps(saida))
'''

def test_app_importavel_registra_o_mesmo_que_o_entrypoint():
    r = subprocess.run([sys.executable, '-c', _CODIGO], cwd=RAIZ,
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-3000:]
    dados = json.loads(r.stdout.split('JSON:', 1)[1].splitlines()[0])

    # CONTROLE POSITIVO: o subprocesso realmente NÃO tinha `main` importado.
    # Sem isto o teste passaria verde no dia em que algum import indireto
    # puxasse `main` — e deixaria de medir o que existe para medir.
    assert dados["importou_main"] is False
    assert len(dados["endpoints"]) > 400, 'o app nem subiu direito'

    faltando = set(dados["endpoints_com_main"]) - set(dados["endpoints"])
    assert faltando == set(), (
        f'{len(faltando)} endpoints só existem depois de importar main: '
        f'{sorted(faltando)[:15]}')
```

E um segundo teste, que é a rede de 19/08 estendida à app importável: um
subprocesso que importa só `app` e chama `_conferir_endpoints_do_layout(app)` —
hoje ele levanta `RuntimeError` com a lista de endpoints do layout ausentes.

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_issues_de_arquitetura.py -k "importavel or layout" -x -q
```

O RED tem de nomear os endpoints que só existem depois do `import main`. Copie
os primeiros para a mensagem do commit — eles são a medida do defeito.

⚠️ Se o subprocesso não subir (erro de conexão, DDL rodando apesar das duas
variáveis), **PARE e resolva isso primeiro**: um teste que falha por não subir
não é o RED desta task.

- [ ] **Step 3: Criar `blueprints_registry.py`**

Mova para lá, **na mesma ordem em que aparecem hoje**, os 15 blocos
`try/except` de `main.py`:

```python
def registrar_blueprints(aplicacao):
    """Fonte única do registro de blueprints. Idempotente e tolerante a falha
    por blueprint — um blueprint que não importa não derruba o boot, exatamente
    como antes; o que muda é que os DOIS caminhos (app importável e main:app)
    passam pela mesma lista."""
```

Regras que não podem ser perdidas na mudança:
- **Idempotência**: cada bloco confere `if <nome> in aplicacao.blueprints: continue`
  antes de registrar. Sem isso, `main.py` delegando depois de `app.py` já ter
  chamado explodiria em `ValueError: The name ... is already registered`.
- **O `try/except` por blueprint continua**, com o mesmo `logger.error(..., exc_info=True)`.
  ⚠️ Não troque por um `except` único em volta do laço: um import quebrado
  derrubaria os 14 seguintes.
- **A ordem importa.** 📖 `main.py:118` define a rota
  `_servicos_legacy_redirect` **entre** dois blocos de registro, e há um ciclo
  conhecido (`compras_views.py:10` faz `from app import db` enquanto `app.py`
  importa `compras_views` dentro do bloco de registro — o caso de 19/08). O que
  não é registro de blueprint **fica no `main.py`**.

- [ ] **Step 4: `app.py` chama a fábrica; `main.py` delega**

- No **fim** de `app.py` (depois de tudo o que hoje já está lá), chamar
  `registrar_blueprints(app)` e **então** `_conferir_endpoints_do_layout(app)`.
- `main.py` passa a chamar a mesma função. Por idempotência, a segunda chamada é
  um no-op — mas **mantenha a chamada**: é ela que garante que `main:app`
  continua correto se alguém subir por lá sem passar por `app.py`.
- Apague de `app.py` o comentário "⚠️ A CHAMADA NÃO MORA AQUI…" e escreva no
  lugar por que ela **passou** a morar ali, citando esta task.

⚠️ **O risco desta task é ordem de import, e ele é real.** Se `app.py` passar a
importar no seu próprio fim um módulo que faz `from app import app`, o ciclo
resolve — é o que `main.py` já faz hoje — mas **qualquer erro novo derruba a
suíte inteira**, não um teste. Rode o Step 5 antes de comemorar.

- [ ] **Step 5: Run test to verify it passes**

```bash
python -m pytest tests/test_issues_de_arquitetura.py -q
python -m pytest tests/ -m "not browser" -q     # a suíte inteira: o risco é de boot
```

O segundo comando não é zelo: esta é a única task do plano cujo modo de falha é
**global**. O número tem de bater com o piso (3247 + os testes novos).

- [ ] **Step 6: Commit**

```bash
git add blueprints_registry.py app.py main.py tests/test_issues_de_arquitetura.py
git commit -m "fix(issue-c): uma fabrica so registra os blueprints

RED: <N> endpoints so existiam depois de importar main (<primeiros nomes>),
medido em subprocesso que provou nao ter main em sys.modules.

A guarda _conferir_endpoints_do_layout passa a cobrir tambem a app
importavel — era a rede de 19/08 e so valia para main:app."
```

---

### Task 3: Os contornos de teste caem — o `conftest` para de montar o app à mão

> 📖 `tests/conftest.py` tem **dois** contornos para o mesmo defeito da Task 2:
> `:64-66` (`try: import main` / `except Exception: pass`, no nível de módulo) e
> `:92-117` (a fixture `_registrar_blueprints_opcionais`, com um *fallback* que
> registra `importacao` e `catalogos` na mão).
>
> 🔴 Os dois engolem a exceção. Se `import main` quebrar, a suíte segue com um
> app incompleto e os `BuildError` aparecem espalhados, sem apontar a causa —
> é o mesmo modo de falha silenciosa que o `except` de registro de blueprint
> tinha em 19/08, agora do lado dos testes.
>
> ⚠️ 📖 O comentário da fixture (`:101-102`) ainda afirma que `import main` "não tem
> efeitos colaterais" — e 📖 o comentário de `:42-58`, cinquenta linhas acima, prova
> que essa frase é **falsa** e já custou 10 minutos de gate travado. Duas
> verdades contraditórias no mesmo arquivo é dívida por si só.

**Files:**
- Modify: `tests/conftest.py` (`:64-66` e `:92-117`)
- Test: `tests/test_issues_de_arquitetura.py` (o teste da Task 2 é a rede)

**Interfaces:**
- Consumes: `registrar_blueprints` (Task 2).
- Produces: nada — remove código.

- [ ] **Step 1: O teste já existe, e é o da Task 2**

Esta task não escreve teste novo: quem prova que o contorno é dispensável é o
teste do subprocesso da Task 2 (o `url_map` de `from app import app` já é o
completo). **O que esta task acrescenta é a prova negativa**: um teste que
afirma que a suíte monta o app **sem** o `import main` do conftest.

```python
def test_conftest_nao_precisa_mais_importar_main():
    """A app importável já é a canônica (Task 2). Se este teste falhar, o
    contorno voltou — ou a fábrica parou de ser chamada por app.py."""
    r = subprocess.run([sys.executable, '-c', _CODIGO_SO_APP], cwd=RAIZ, ...)
    ...
    assert dados["importou_main"] is False          # controle
    assert 'custos_escritorio.painel_mensal' in dados["endpoints"]
    assert 'importacao' in dados["blueprints"]
    assert 'catalogos' in dados["blueprints"]
```

Os três nomes não são escolhidos ao acaso: são exatamente os que 📖 o próprio
comentário do conftest (`:94-99`) cita como o motivo do contorno.

- [ ] **Step 2: Run test to verify it fails**

Rode **antes** de aplicar a Task 2 (ou com `git stash`) para confirmar que ele
reprova sem a fábrica. Se a Task 2 já estiver aplicada, o teste nasce verde —
e nesse caso **cite o RED da Task 2 no commit** e diga que este é um teste de
regressão, não de correção. Não invente um RED que não houve.

- [ ] **Step 3: Apagar os dois contornos**

- `tests/conftest.py:64-66` — o `try: import main` / `except Exception: pass` de nível de
  módulo sai. As duas `os.environ.setdefault` (`SIGE_ENABLE_DEMO_SEED` e
  `SIGE_BOOT_DDL`, `:61-62`) **ficam**: elas guardam contra o DDL e o seed de import-time,
  que é problema distinto e continua valendo.
- `tests/conftest.py:92-117` — a fixture `_registrar_blueprints_opcionais` sai
  inteira, com o *fallback* manual.
- ⚠️ **Não apague os comentários de `:42-58`** (a medição do convoy de
  `AccessExclusiveLock`). Eles documentam por que as duas variáveis de ambiente
  existem, e essa razão sobrevive a esta task.

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/ -m "not browser" -q
```

Suíte inteira de novo: mexer no `conftest` afeta todo teste que renderiza
página. Compare com o número do Step 5 da Task 2 — tem de ser igual mais os
testes novos.

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py tests/test_issues_de_arquitetura.py
git commit -m "test(issue-c): o conftest para de montar o app a mao

Os dois contornos (`import main` de modulo e a fixture com fallback manual de
importacao/catalogos) existiam so por causa dos dois url_map. Com a fabrica
unica da task anterior, `from app import app` ja e' o app canonico.
Os setdefault de SIGE_BOOT_DDL/SIGE_ENABLE_DEMO_SEED ficam: guardam outra coisa."
```

---

### Task 4: O teste de paridade de preço passa a chamar o backend — hoje ele compara duas cópias da mesma fórmula

> 🔴🔬 **Este é o achado que a reconferência rendeu, e ele é maior do que a
> issue E descrevia.** 📖 `tests/test_orcamento_pricing_parity.py` diz na
> docstring que garante que "o preview mostrado ao usuário coincide com os
> totais persistidos pelo backend". Ele não garante:
>
> - `js_preview()` (`:17-27`) é uma **transcrição à mão** da fórmula do template;
> - `backend_preview()` (`:30-43`) é uma **transcrição à mão** do backend;
> - a única coisa que olha o código real é um `re.search` sobre o texto de
>   `templates/orcamentos/editar.html` (`:96-98`) — 📖 proibido pela constraint
>   da casa: o que se afirma não se prova em texto;
> - e o arquivo é um **script**: `main()` imprime, `sys.exit(0 ou 1)` (`:106`), e
>   um único `def test_...` (`:109-115`) embrulha tudo em
>   `assert e.code in (0, None)`. Trinta e poucos casos viram **um** verde no
>   gate, e a mensagem de falha é um código de saída.
>
> 🔬 **A prova de que ele é cego, feita hoje com aritmética exata:** as duas
> transcrições calculam `venda = round4(custo_unit/divisor) × qtd`, enquanto o
> backend real (📖 `services/orcamento_view_service.py:176`) e o template real
> (📖 `templates/orcamentos/editar.html:1025`) calculam
> `venda = round2(custo_compra/divisor)`. No caso `(12,34 × 1000; imp 9,9%; mar 19,9%)`
> — que **está na tabela de casos do próprio teste** (`:59`):
>
> | | venda_total |
> |---|---|
> | backend real (`recalcular_item`) e template real | **17.578,35** |
> | o que o teste compara (as duas transcrições) | **17.578,30** |
> | divergência | **R$ 0,05** — dez vezes a tolerância `0.005` do teste (`:46`) |
>
> O teste passa verde porque compara **erro com erro**. O template e o backend
> concordam entre si; é o teste que discorda dos dois e não tem como saber.

**Files:**
- Modify (reescrever): `tests/test_orcamento_pricing_parity.py`
- Test: o próprio arquivo

**Interfaces:**
- Consumes: `services/orcamento_view_service.recalcular_item` (chamada real, com `OrcamentoItem` e `Orcamento` semeados); `views/orcamentos_views.py:405/498/527` são os chamadores de produção.
- Produces: o padrão de conserto para os outros **20** arquivos que embrulham `main()` num único `test_` (recorte da issue H — ver "Adiadas").

- [ ] **Step 1: Write the failing test**

Reescreva o arquivo como pytest de verdade — casos parametrizados, sem `main()`,
sem `sys.exit`, sem `re.search` sobre template:

```python
@pytest.mark.parametrize('custo_unit,qtd,imp,mar,venda_esperada', [
    ...,
    ('12.34', '1000', '9.9', '19.9', Decimal('17578.35')),   # o caso que expõe
])
def test_recalcular_item_bate_com_o_valor_persistido(app, tenant, custo_unit, qtd,
                                                     imp, mar, venda_esperada):
    """Chama recalcular_item de verdade, com item real, e confere o que ficou
    NO BANCO depois do commit — não uma transcrição da fórmula."""
```

E o caso-âncora, que é o que fecha o buraco de vez:

```python
def test_venda_total_e_custo_compra_dividido_pelo_divisor_uma_vez_so(...):
    """RED hoje: a transcrição do teste velho arredondava o preço unitário
    ANTES de multiplicar pela quantidade, e errava R$ 0,05 em 1000 unidades."""
```

⚠️ **Controle positivo obrigatório**: antes de afirmar o valor, o teste afirma
que o item **foi persistido e recalculado** — `item.venda_total is not None` e
`item.composicao_snapshot` normalizado (com `subtotal_compra` presente). Sem
isso, um `recalcular_item` que virasse no-op faria o teste passar por vácuo.

- [ ] **Step 2: Run test to verify it fails**

Rode o caso-âncora **contra a transcrição velha** primeiro (mantendo
`js_preview`/`backend_preview` no arquivo por um commit), para capturar o RED
que prova o achado: `17578.30 != 17578.35`. Cole essa linha no commit. **É a
prova de que o teste velho era cego**, e ela some assim que o arquivo for
reescrito — capture antes.

- [ ] **Step 3: A correção — o teste**

- Apague `js_preview()`, `backend_preview()`, `assert_close()`, `main()`, o
  `re.search` sobre o template e o `if __name__ == '__main__'`.
- Cada caso vira um `test_` próprio via `parametrize`: **N verdes no gate, N
  mensagens de falha distintas**, em vez de um código de saída.
- ⚠️ **Nenhuma linha de código de produção muda nesta task.** O backend e o
  template estão certos e concordam; quem estava errado era o teste. Se você se
  vir editando `services/orcamento_view_service.py` aqui, pare e releia o Step 2.

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_orcamento_pricing_parity.py -v
python -m pytest tests/ -m "not browser" -k "orcamento or pricing or bdi" -q
```

⚠️ **O `passed` do gate SOBE** nesta task (1 teste vira N). Isso é ganho, não
regressão — registre o delta exato no commit para que a Task 8 saiba explicar o
número novo.

- [ ] **Step 5: Commit**

```bash
git add tests/test_orcamento_pricing_parity.py
git commit -m "test(issue-e): a paridade de preco passa a chamar o backend

RED: o caso (12.34 x 1000, imp 9.9%, mar 19.9%) da propria tabela do teste
velho dava 17578.30 nas duas transcricoes e 17578.35 no backend e no template
reais — R$ 0,05, dez vezes a tolerancia de 0.005 do proprio teste. Ele passava
verde porque comparava erro com erro.

Fim do `main()`/`sys.exit` e do re.search sobre o template. <N> casos
parametrizados, cada um um verde e uma mensagem de falha propria."
```

---

### Task 5: O endpoint de preview, e a fórmula de preço sai do JavaScript

> 📖 A conta vive hoje em dois lugares que precisam concordar:
> `services/orcamento_view_service.py:165-181` (`recalcular_item`, o que
> persiste) e `templates/orcamentos/editar.html:1021-1025` (o preview em tempo
> real). 🔬 Hoje eles concordam — a Task 4 provou isso chamando os dois. Nada
> garante que continuem concordando: 📖 a docstring do teste velho registra que
> "o teste de paridade já quebrou por causa de uma divergência de nome de
> variável no JS", e o comentário do template (`:1019-1020`) é a fórmula do
> backend **copiada em prosa**.
>
> A Task 4 fecha o buraco do lado do backend. Esta fecha o do JS: o servidor
> passa a ser a única autoridade, e o JS só exibe.

**Files:**
- Modify: `views/orcamentos_views.py` (rota nova, blueprint `orcamentos`, `url_prefix='/orcamentos'`, `views/orcamentos_views.py:32`)
- Modify: `templates/orcamentos/editar.html:1019-1025` (e o `<script>` em volta)
- Test: `tests/test_orcamento_pricing_parity.py` (o arquivo que a Task 4 deixou honesto)

**Interfaces:**
- Consumes: a mesma função que persiste — `recalcular_item` / o núcleo dela.
- Produces: `POST /orcamentos/api/preview-preco`, que devolve `{custo_total, preco_unitario, venda_total, lucro_total, erro}`.

- [ ] **Step 1: Write the failing test**

O teste afirma **na resposta HTTP**, e o par é o que fecha o contrato:

```python
def test_preview_de_preco_devolve_o_mesmo_que_o_backend_persiste(client, tenant):
    """A afirmação é: para os MESMOS inputs, o que o endpoint devolve e o que
    o banco guarda depois de recalcular_item são o mesmo número."""
    # 1. persiste um item de verdade e lê venda_total DO BANCO
    # 2. chama o endpoint com os mesmos inputs
    # 3. assert resposta['venda_total'] == str(venda_total_do_banco)
```

Controle positivo: o teste afirma primeiro que o item **foi mesmo persistido com
`venda_total > 0`** — senão `0 == 0` passaria e não provaria nada.

Um segundo teste para a borda que o código já trata: `imp + mar >= 100%` devolve
`erro` e `venda_total = 0` **nos dois lados** (📖 `orcamento_view_service.py:169-172`).

- [ ] **Step 2: Run test to verify it fails**

RED esperado: `404` / `BuildError` — a rota não existe. Cite no commit.

- [ ] **Step 3: A rota**

Em `views/orcamentos_views.py`, ao lado das rotas de item (`:346`, `:416`):
- `@login_required` e `@admin_required` como as vizinhas; **isolamento por
  tenant pelo resolvedor único** (`utils.tenant.get_tenant_admin_id`), nunca por
  `current_user.id` cru.
- **Não persiste nada.** Calcula e devolve. Se precisar de um `OrcamentoItem`
  para reusar `recalcular_item`, use `db.session.begin_nested()` e desfaça — ou,
  melhor, extraia o núcleo aritmético (`custo_compra`, `divisor`, os três
  totais) para uma função pura e chame-a dos dois lados.
- ⚠️ **Prefira extrair o núcleo puro.** É o que torna o endpoint e a
  persistência a mesma conta em vez de duas que se conferem.

- [ ] **Step 4: O JS passa a exibir**

Em `templates/orcamentos/editar.html`:
- apague as linhas `const divisor = ...`, `const custoTot = ...`,
  `const precoUnit = ...`, `const vendaTot = ...` (hoje `:1021-1025`) e o
  comentário-fórmula de `:1019-1020`;
- no lugar, `fetch` para o endpoint, **com debounce** (a issue pede; o editor
  dispara a cada tecla);
- estado de erro visível: se o `fetch` falhar, o preview mostra "—", **nunca um
  número velho**. Número obsoleto na tela de preço é pior que campo vazio.

- [ ] **Step 5: Run test to verify it passes**

```bash
python -m pytest tests/test_orcamento_pricing_parity.py -v
python -m pytest tests/ -m "not browser" -k "orcamento" -q
```

⚠️ **Esta task muda uma tela.** Rode também a suíte com browser dos orçamentos
(`-m browser -k orcamento`) e compare com o piso — é a única rede para o
debounce e para o estado de erro.

- [ ] **Step 6: Commit**

```bash
git add views/orcamentos_views.py templates/orcamentos/editar.html tests/test_orcamento_pricing_parity.py
git commit -m "feat(issue-e): o preco tem uma autoridade so; o JS exibe

RED: POST /orcamentos/api/preview-preco devolvia 404.

A formula sai do <script> de editar.html e passa a vir do backend. O preview e'
contrato de endpoint, nao reimplementacao — a divergencia de nome de variavel
no JS que ja quebrou a paridade uma vez deixa de ser possivel."
```

---

### Task 6: A folha para de dizer "sucesso" quando o lançamento contábil não saiu

> 🔴 📖 `folha_pagamento_views.py:316-336`, rota `POST /folha/processar/<ano>/<mes>`
> (`:144`). A chamada a `gerar_lancamento_contabil_automatico` **descarta o
> retorno** e está dentro de um `try` cujo `except` faz
> `logger.warning(f"[WARN] Lancamento contabil folha nao gerado: {_e}")` — e
> quatro linhas abaixo, em `:340`, incondicionalmente:
>
> ```python
> flash(f'Folha processada com sucesso! {folhas_criadas} funcionários processados.', 'success')
> ```
>
> 📖 E a função chamada **avisa na própria docstring** (`contabilidade_utils.py:1691`)
> que *"NUNCA propaga exceções: erros são apenas logados"*, devolvendo `False`
> em quatro caminhos distintos: operação não mapeada (`:1705`), valor inválido
> (`:1709`), e qualquer exceção (`:1751-1757`). **Ninguém, em nenhum dos 7
> chamadores** (`compras_views.py:922`, `gestao_custos_views.py:850` e `:1004`,
> `alimentacao_views.py:524`, `folha_pagamento_views.py:327`,
> `financeiro_service.py:238`, `transporte_views.py:260`), olha esse `False`.
>
> O gestor vê "sucesso", a contabilidade não tem o lançamento, e o único sinal é
> uma linha de log.

**Files:**
- Modify: `folha_pagamento_views.py:316-336`
- Test: `tests/test_issues_de_arquitetura.py`

**Interfaces:**
- Consumes: `gerar_lancamento_contabil_automatico` (`contabilidade_utils.py:1676`), que **continua devolvendo `False` e continua não propagando** — o contrato dela não muda.
- Produces: um `flash` de pendência acionável na rota de processar folha.

> ⚠️ **Escopo mínimo, e o recorte está declarado.** A issue B pede cinco coisas:
> um registro persistido de resultado de evento (com migração e modelo), o
> handler de folha, o flash, o mesmo padrão em material→GestãoCusto e
> proposta→Obra, e um painel de "Integrações pendentes". Esta task entrega **o
> flash e o handler de folha** — a parte que é conserto. O registro persistido e
> o painel são **funcionalidade nova, feature-sized**, e a casa proíbe
> placeholder: estão na seção "Adiadas, e por quê", com o que os traz de volta.

- [ ] **Step 1: Write the failing test**

```python
def test_folha_avisa_quando_o_lancamento_contabil_nao_saiu(client, tenant_v2, monkeypatch):
    """O gatilho é injetado (o lançamento falha por monkeypatch), então o teste
    afirma PRIMEIRO que a folha em si foi processada — senão um 500 ou um
    redirect precoce faria a asserção de aviso passar pelo motivo errado."""
    monkeypatch.setattr('contabilidade_utils.gerar_lancamento_contabil_automatico',
                        lambda **kw: False)

    resp = client.post(f'/folha/processar/{ano}/{mes}', follow_redirects=True)
    assert resp.status_code == 200

    # CONTROLE POSITIVO — a folha FOI processada (no banco, depois do teardown)
    with app.app_context():
        assert RegistroFolha.query.filter_by(admin_id=..., ano=ano, mes=mes).count() > 0

    corpo = resp.get_data(as_text=True)
    assert 'lançamento contábil' in corpo.lower()
    assert 'pendente' in corpo.lower()
```

E o par que impede o aviso de virar ruído permanente:

```python
def test_folha_nao_avisa_quando_o_lancamento_saiu(client, tenant_v2):
    """Sem o monkeypatch: nenhum aviso de pendência, e o LancamentoContabil
    existe no banco com origem='FOLHA_PAGAMENTO'."""
```

⚠️ **Dois cuidados de fixture, medidos:**
1. 📖 O bloco só roda sob `if is_v2_active()` (`folha_pagamento_views.py:320`).
   O tenant do teste tem de ser **v2** (`Usuario.versao_sistema == 'v2'`,
   conferido por `contabilidade_utils._is_v2_admin_direct:1762`), ou o teste
   passa sem tocar o código sob teste. 🔴 É o defeito de processo mais repetido
   desta linhagem de planos — **nove ocorrências registradas no ledger**, sempre
   a mesma causa: o gatilho que o plano escolhe é interceptado por uma
   validação anterior, e o teste fica verde sem alcançar o código sob teste.
2. 📖 O bloco também exige `folhas_criadas > 0 and total_proventos_mes > 0`
   (`:316`). A fixture precisa de funcionário com salário.

- [ ] **Step 2: Run test to verify it fails**

RED esperado: a resposta contém "Folha processada com sucesso!" e **não** contém
aviso nenhum. Cole o trecho no commit.

- [ ] **Step 3: A correção**

```python
lc_ok = gerar_lancamento_contabil_automatico(...)
```
- guardar o retorno; no `except`, tratar como `False`;
- se `False`, um `flash(..., 'warning')` que diz **o que ficou pendente e o que
  fazer**: `'Folha processada, mas o lançamento contábil ficou pendente — confira o plano de contas do tenant em Configurações › Contabilidade.'`
- o `flash` de sucesso continua existindo (a folha **foi** processada); o que
  muda é que ele deixa de ser a única mensagem.

⚠️ **Não faça o lançamento abortar o processamento da folha.** A issue é
explícita: *"falhas de efeito colateral nunca abortam o fluxo principal; são
registradas e sinalizadas"*. Trocar silêncio por rollback seria um defeito pior.

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_issues_de_arquitetura.py -k folha -v
python -m pytest tests/ -m "not browser" -k "folha or contab" -q
```

- [ ] **Step 5: Commit**

```bash
git add folha_pagamento_views.py tests/test_issues_de_arquitetura.py
git commit -m "fix(issue-b): a folha para de dizer sucesso com o lancamento no chao

RED: com gerar_lancamento_contabil_automatico devolvendo False, a resposta
trazia so 'Folha processada com sucesso!' e nenhum aviso. Controle positivo
verde: a folha foi mesmo gravada no banco, entao o aviso ausente era ausencia
de aviso, nao ausencia de processamento.

O retorno para de ser descartado. O fluxo principal NAO aborta — a falha de
efeito colateral vira aviso acionavel, como a issue B manda."
```

---

### Task 7: O arquivo de teste que a suíte nunca roda

> 🔴🔬 Medido em 03/09 com `pytest --collect-only`:
>
> ```
> tests/test_propostas_block_scripts_213.py  →  no tests collected in 0.06s
> ```
>
> **316 linhas**, nome `test_*`, docstring descrevendo dois cenários
> ponta-a-ponta via HTTP ("guard estático nos 3 templates" e
> "POST /propostas/<id>/cronograma-default") — e **zero** testes coletados,
> porque o arquivo é um script: tem `main()`, `sys.exit` e `if __name__ ==
> '__main__'`, e **nenhuma função `def test_`**. Ele está no disco, aparece nos
> `grep`, parece cobertura, e o gate nunca o executou.
>
> 🔬 É o único assim: dos 42 arquivos de `tests/` com `sys.exit` + `__main__`,
> 41 têm ao menos um `def test_` (e são coletados). Este é o que escorregou.
>
> Isto é a issue **H** no seu ponto mais agudo: *"skip silencioso (…) o que
> chegou a esconder nove testes de integração inteiros"*.

**Files:**
- Modify ou Delete: `tests/test_propostas_block_scripts_213.py`
- Test: o próprio arquivo, se sobreviver

**Interfaces:**
- Consumes: nada.
- Produces: `+N passed` no gate, se converter; nada, se apagar.

- [ ] **Step 1: Medir a sobreposição ANTES de decidir**

Existe um irmão: 📖 `tests/test_propostas_block_scripts_213_playwright.py`, que
**é** coletado e tem `pytestmark = pytest.mark.browser` (`:348`) — ou seja, vive
na suíte com browser, não no gate. Antes de converter ou apagar, meça o que cada
um cobre:

```bash
python -m pytest tests/test_propostas_block_scripts_213_playwright.py --collect-only -q
grep -n "def \|assert " tests/test_propostas_block_scripts_213.py | head -40
```

Se o irmão cobrir os dois cenários, o veredito pode ser **apagar** — e nesse
caso o commit tem de **nomear o teste do irmão que cobre cada cenário**. Se não
cobrir (e a docstring sugere que não: o cenário B é `POST` via HTTP, sem
browser), o veredito é **converter**.

⚠️ **Não decida por leitura de docstring.** Nenhum dos dois arquivos foi
executado nesta reconferência; o veredito é medido, não presumido.

- [ ] **Step 2: Write the failing test**

Se o veredito for **converter**: transforme cada cenário num `def test_` próprio,
sem `main()` e sem `sys.exit`. O RED é o `--collect-only` de hoje: **0
coletados**. Cite a linha exata `no tests collected in 0.06s` no commit — é o
defeito, e ele some no instante do conserto.

Se o veredito for **apagar**: não há teste a escrever; o commit carrega a
medição de sobreposição como justificativa, e o Step 4 confirma que o `passed`
do gate **não cai**.

- [ ] **Step 3: A correção**

- Converter: cada `assert` do `main()` vira asserção de um `test_`, com a
  mensagem de falha preservada. As asserções que olham HTML de resposta
  **continuam olhando a resposta HTTP** — é o que a constraint pede.
- ⚠️ Se algum cenário precisar de dado que hoje não existe, **crie a fixture**;
  **não** acrescente `pytest.skip`. O `skipped` do gate não sobe (constraint
  global), e trocar "arquivo invisível" por "skip silencioso" seria fechar a
  issue H com o defeito da issue H.

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_propostas_block_scripts_213.py -v      # se converteu
python -m pytest tests/ -m "not browser" -k "proposta" -q
```

Registre o delta de `passed` e de `skipped`. O `skipped` tem de ficar igual.

- [ ] **Step 5: Commit**

```bash
git add tests/test_propostas_block_scripts_213.py
git commit -m "test(issue-h): o teste que a suite nunca rodou volta a existir

RED: `pytest --collect-only` sobre o arquivo devolvia 'no tests collected in
0.06s' — 316 linhas com nome test_*, main() e sys.exit, e nenhum `def test_`.
Unico assim entre os 42 arquivos com sys.exit+__main__.

<N> testes coletados agora. Sobreposicao com o irmao _playwright medida antes
de decidir, nao presumida: <resultado>."
```

---

### Task 8: O README das issues aponta para este plano, e o gate fecha a etapa

**Files:**
- Modify: `docs/superpowers/issues/README.md`
- Modify: este plano (o bloco de estado do topo)

**Interfaces:**
- Consumes: o estado real de cada task acima.
- Produces: o rastro que impede as issues de chegarem a mais um 08/06.

- [ ] **Step 1: Coluna de estado no README**

Em `docs/superpowers/issues/README.md`, acrescente à tabela uma coluna
**Estado**, com o commit ou a seção:

| # | Estado |
|---|---|
| A | ✅ `<commit da Task 1>` |
| B | 🟡 parcial — `<commit da Task 6>` (o flash); registro e painel em "Adiadas" |
| C | ✅ `<commits das Tasks 2 e 3>` |
| D | ✅ metade fechada pela **migration 218**; metade entregue pela **Task 12** do plano mestre — `<commit>`; recorte do ADR em "Adiadas" |
| E | ✅ `<commits das Tasks 4 e 5>` |
| F | ⛔ adiada — ver "Adiadas, e por quê" |
| G | ⛔ adiada — ver "Adiadas, e por quê" |
| H | 🟡 parcial — `<commits das Tasks 4 e 7>`; registro de migrations e os 20 arquivos restantes em "Adiadas" |

⚠️ Acrescente também, no topo do README, a data da reconferência e o
`arquivo:linha` de onde ela está escrita — este plano. Uma tabela de estado sem
procedência apodrece do mesmo jeito que a de 08/06.

- [ ] **Step 2: Carimbar este plano**

Troque o bloco de estado do topo por um bloco de fecho com o placar real: quais
tasks fecharam, com que commit, e o número do gate. Se alguma task ficou aberta,
**diga qual e por quê** — o defeito que este plano combate é adiar sem registrar,
e ele valeria contra o próprio plano.

- [ ] **Step 3: O gate**

```bash
bash run_tests.sh --gate
```

Régua: **3247 passed / 8 skipped / 201 deselected / 72 xfailed / 0 failed**, ou
mais verdes. O `passed` **vai subir** — as Tasks 4 e 7 transformam scripts em
testes parametrizados. ⚠️ **Explique o número, não o arredonde**: some os deltas
que cada task registrou no commit e confira que batem com a diferença medida.
🔬 É o Ruling S0902-R2 do ledger: previsto 3212, medido 3247, e a conta foi
fechada com os três arquivos que nasceram depois do piso.

O `skipped` **não pode subir** e os `xfailed` **não podem subir** (são
`strict=True`).

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/issues/README.md docs/superpowers/plans/2026-08-31-issues-de-arquitetura.md
git commit -m "docs(issues): as sete issues de arquitetura ganham plano ou adiamento por escrito

Gate: <numeros>. A e C fechadas, B e H parciais com recorte nomeado, E fechada,
D absorvida pela Task 12 (metade ja estava fechada pela migration 218), F e G
adiadas com motivo e com o que as traz de volta."
```

- [ ] **Step 5: O ritual da Task 10 do plano mestre**

Merge e push são efeito fora do worktree. **PARE aqui e pergunte** — é a Ruling
C5 do pré-voo: o plano autoriza a cadência, não o gesto.

---

## Já fechado, ou absorvido — não vira task

### D — Fonte única do plano de contas: metade fechada, metade é a Task 12

A issue D pede cinco coisas. Reconferidas hoje, uma a uma:

| O que a issue D pede | Estado em 03/09 |
|---|---|
| 1. Escolher a definição canônica e deprecar a outra | 🟡 **é a Task 2 da Fase 8** (`2026-08-24-fase-8-plano-de-contas-canonico.md`), que é a **Task 12** do plano mestre — **ainda não executada** |
| 2. Seeder que completa lacunas, idempotente, criando pais em ordem | ✅ **FECHADO.** 📖 `contabilidade_utils.py:1605-1660`: `ON CONFLICT (admin_id, codigo) DO NOTHING` (`:1641`), o gate `if count == 0` virou incondicional, e o laço percorre `_V2_CONTAS_SEED` "por nível (raízes primeiro): a auto-FK composta de `conta_pai_codigo` exige o pai já inserido" (`:1631-1632`) |
| 3. Migração de saneamento por tenant | ✅ **FECHADO** pela **migration 218** — 📖 `migrations.py:7813` registra *"Fase 0.6 / D4 — plano_contas por tenant: backfill + PK (admin_id, codigo) + 6 FKs compostas"*, e a docstring em `migrations.py:18331-18334` traz a medição: *"315 tenants com lançamentos contábeis, 2 com plano de contas, e 980 das 1.204 partidas apontando para um par (admin_id, conta) inexistente"* |
| 4. **ADR** comparando "código como PK global" × "(admin_id, código)" | 🔴 **NÃO EXISTE**, e a decisão foi tomada **ao contrário do que a issue previa** — ver abaixo |
| 5. Verde: todo tenant tem as contas essenciais; folha→lançamento funciona | ✅ coberto por `tests/test_fase06_d4_plano_contas_por_tenant.py` e `tests/test_fase06_d3_dre_despesas_v2.py` |

🔴 **O `Problem Statement` da issue D está factualmente desatualizado.** Ele
afirma que *"o código da conta é chave primária global"*. 📖 `models.py:3270-3273`
hoje:

```python
admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), primary_key=True, nullable=False)
codigo   = db.Column(db.String(20), primary_key=True)
# "A ordem das colunas da PK segue a do índice criado pela migration 218."
```

A PK **é composta**. E o mesmo vale para o plano da Fase 8 **velho e obsoleto**
(`2026-07-21-fase-8-financeiro-avancado-dominio.md`), cujo "buraco D" (`:52`) e
cuja "premissa 4" (`:197`) citam `models.py:2501` e a PK global — 📖 esse plano
já está carimbado *"❌ OBSOLETO — não executar"*, e este é mais um motivo.

⚠️ **Procedência do commit, dita como é:** 🔬 `git log -S` para a migration 218,
para o `ON CONFLICT (admin_id, codigo)` e para o `_config_empresa` devolve, nos
três casos, `b30923b5` (22/07) — que é a **reimportação do repositório inteiro**
(1437 arquivos, +478.283 linhas). O histórico anterior a 22/07 não está neste
repo. **A prova destes três fechamentos é o código e o registro da migration, não
o hash** — e é assim que este documento os afirma.

**Recorte que sobra da D, e que este plano NÃO transforma em task: o ADR.**
A issue pedia um ADR registrando a decisão de **manter** a PK global e os
gatilhos para revisá-la. A decisão executada foi a oposta — a PK **foi** migrada
para `(admin_id, codigo)`. Um ADR ainda vale (📖 `docs/adr/` tem 0001 a 0005 e
nenhum sobre plano de contas), mas ele documentaria uma decisão **tomada e já
aplicada**, não uma pendente. Não é conserto e não tem RED; vai para "Adiadas".

---

## Adiadas, e por quê

> Adiar é resposta legítima. Adiar **sem registrar** é como as oito issues
> chegaram a 31/08 sem ninguém notar. Cada item abaixo diz **o motivo** e **o
> que precisa mudar para voltar à fila**.

### F — N+1 de config por request: a evidência não sobreviveu à medição

🔬 Medido em 03/09, por varredura de escopo léxico sobre todo `*.py` de produção
(excluídos `tests/`, `archive/`, `entrega_baia_rev10/`, `scripts/`): **zero**
ocorrências de `ConfiguracaoEmpresa.query` **dentro de um `for` ou `while`**. Os
sítios que a issue nomeia foram abertos um a um e são **uma consulta por
request, no corpo da rota** — 📖 `medicao_views.py:65`, `cronograma_views.py:540`,
`portal_obras_views.py:402`, `propostas_consolidated.py:526/1205/2622` (estes
três já sob `safe_db_operation`).

📖 O cache por request que a issue queria promover **existe**:
`services/pricing.py:73` (`_config_empresa`, com `g._bdi_cfg_cache` e *fallback*
para consulta direta fora de contexto de app). O que nunca foi feito é
**compartilhá-lo** — e isso é, literalmente, o resíduo já nomeado no cabeçalho
do plano de origem: 📖 *"resíduo: `services/tenant_config.py` nunca existiu"*
(`2026-06-08-remediacao-saude-app-plan.md:3`).

**Por que não vira task:** sem N+1 medido, não existe RED. Um teste de contagem
de queries que já começa em 1 não reprova nada, e promover o helper "por
padrão", sem defeito, seria refactor cosmético num arquivo de precificação — a
área de maior custo de erro do repo.

**O que a traz de volta:** uma medição de contagem de queries num fluxo real
(materializar uma proposta com N itens, ou renderizar uma medição com N linhas)
que mostre **N consultas à `configuracao_empresa` num único request**. Com esse
número, a task nasce com RED e com alvo. Sem ele, não nasce.

### G — Onboarding / prontidão do tenant: depende do que a issue B deixa fora

🔬 Não existe serviço de prontidão. A única coisa parecida é
📖 `scripts/prontidao_piloto_compras.py` — um script de linha de comando, para
**um** módulo (compras), que imprime um relatório por `admin_id`.

**Por que não vira task:** 📖 o próprio `Decision Document` da G diz que *"os
avisos contextuais reutilizam os deep-links de correção do Bloco B"*, e a Task 6
deste plano entrega da issue B **só o aviso**, não o registro persistido de
pendências nem os deep-links. Construir o checklist agora significaria inventar
uma segunda fonte de verdade para "o que falta ao tenant", que divergiria da
primeira na primeira correção. Além disso, G é **feature-sized** (serviço + card
na home + avisos em três telas + e2e) — o plano mestre já registra que
funcionalidade desse tamanho ganha plano próprio e não entra como placeholder.

**O que a traz de volta:** a issue B entregue por inteiro (registro persistido +
deep-links). Aí a G é o consumidor natural dele, e o `scripts/prontidao_piloto_compras.py`
vira a semente do serviço, generalizado dos módulos de compras para os quatro
itens que a issue lista (parâmetros do ano, plano de contas essencial, BDI, ≥1
funcionário).

### B (recorte) — o registro persistido de pendências e o painel de integrações

A Task 6 entrega o conserto: o retorno para de ser descartado e o gestor é
avisado. Ficam de fora, por serem **funcionalidade nova**: o modelo + migração
de resultado de evento, o mesmo padrão aplicado a material→GestãoCusto e
proposta→Obra (📖 os outros **6 chamadores** de
`gerar_lancamento_contabil_automatico`, todos ignorando o `False` do mesmo jeito),
e o painel "Integrações pendentes".

**O que os traz de volta:** o plano das automações
(`2026-09-XX-onda-das-automacoes.md`, já previsto no cabeçalho do plano mestre)
é o lugar natural — e a medição *"os 225 usos de `admin_id` em query sem guarda
de `None`"*, que o plano mestre já sugere registrar "na onda das automações **ou
na issue B**", é o mesmo mecanismo de falha silenciosa e deve ir junto.

### H (recorte 1) — extrair o registro de migrations: colide com a T8 e a T12

🔬 `migrations.py` tem **18.744 linhas**; a tupla `migrations_to_run`
(`:7624-7885`) tem **248 entradas, de 20 a 318, em ordem e sem duplicata**, com
**51 números ausentes** na faixa. A issue H pede extrair a lista-registro para um
módulo próprio e documentar a convenção de numeração.

**Por que não vira task hoje:** 🔴 a **T8** (Espinha Financeira) e a **T12**
(Fase 8) **acrescentam migrations à mesma tupla** — 319/320/321 e 322/323, pela
Ruling C1 do pré-voo. Mover a tupla de arquivo enquanto duas tasks escrevem
nela é conflito garantido, e o custo de errar não é um merge feio: é uma
migration nascer fora de ordem, o runner executá-la na hora errada e o `DROP`
de uma futura estourar em produção.

**O que a traz de volta:** T8 e T12 fechadas e mergeadas. Aí a extração é
mecânica, e o teste é honesto: um teste que **importa** o módulo novo e afirma
que a tupla está ordenada, sem duplicata, e que todo número registrado tem
função correspondente — asserções sobre o objeto carregado, não sobre o texto do
arquivo.

### H (recorte 2) — os 20 arquivos que embrulham `main()` num único `test_`

🔬 Medido: **21** arquivos de `tests/` têm um `main()` de script chamado de
dentro de um único `def test_`, com `assert e.code in (0, None)`. Cada um vale
**um** verde no gate por dezenas de verificações internas, e a mensagem de falha
é um código de saída.

A **Task 4** conserta o primeiro deles (`test_orcamento_pricing_parity.py`) — e
o conserta porque ali o embrulho **escondia um defeito real** (a divergência de
R$ 0,05). Os outros 20 não têm, hoje, defeito medido por trás: convertê-los é
ganho de diagnóstico, não conserto.

**O que os traz de volta:** o padrão que a Task 4 estabelece, aplicado em lote —
cabe numa varredura própria, com o critério "converter, medir o `passed` antes e
depois, e explicar o delta". Cada conversão **sobe** o `passed` do gate, o que é
ganho; mas 20 conversões de uma vez tornariam o número do gate ilegível.

### D (recorte) — o ADR do plano de contas

📖 `docs/adr/` tem 0001 a 0005 e nenhum sobre o plano de contas. A decisão que
um ADR registraria (`codigo` global × `(admin_id, codigo)`) **já foi tomada e
aplicada** pela migration 218, ao contrário do que a issue D previa.

**Por que não vira task:** não é conserto, não tem RED, e o gate não tem como
reprovar sua ausência.

**O que o traz de volta:** a **Task 12**. A Fase 8 acrescenta duas colunas de
semântica a `plano_contas` (`classificacao_gasto`, `atividade_dfc`) e escolhe um
seeder canônico entre quatro concorrentes — decisões que **precisam** de ADR, e
que naturalmente absorvem o registro retroativo da PK. Escrever o ADR agora,
antes da T12, seria escrevê-lo duas vezes.

---

## As três decisões que este plano toma, e o custo de cada uma

> Nenhuma issue ficou bloqueada esperando resposta humana. Mas três escolhas de
> projeto foram feitas aqui, e a casa registra o custo de errar em vez de
> apresentar a escolha como óbvia.

**Decisão 1 — a issue A converte, não apaga.** Os dois getters têm zero
chamadores; apagar seria mais limpo. Converter mantém a superfície pública e
**não colide com a Task 12**, que edita `seed_plano_contas_if_needed` — um dos 6
chamadores de `invalidar_cache()`.
*Custo se errado:* fica um par de getters convertidos que ninguém usa; ruído
pequeno, e apagá-los depois é trivial e sem colisão, uma vez que a T12 tenha
fechado.

**Decisão 2 — a issue B entrega o aviso, não o registro persistido.** O conserto
(o `False` deixar de ser descartado) e a funcionalidade (modelo, migração,
painel) foram separados; só o conserto entra.
*Custo se errado:* o gestor passa a ver um aviso por request, mas não tem onde
ver o histórico de pendências — o painel continua faltando. É estritamente
melhor que hoje, onde ele não vê nada, e não fecha nenhuma porta para o painel.

**Decisão 3 — a issue E entra em duas tasks, e a primeira é só de teste.** A
Task 4 não muda uma linha de produção: o backend e o template **concordam**; era
o teste que discordava dos dois. Só a Task 5 mexe no JS.
*Custo se errado:* se o backend e o template divergirem em algum caso fora da
tabela da Task 4, a Task 4 não pega — mas a Task 5 elimina a possibilidade na
raiz, tirando a fórmula do JS. Por isso as duas, e nesta ordem.

---

## Notas de execução

- **Ordem:** 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8. As Tasks 2 e 3 são **sequenciais e
  não independentes** (a 3 apaga o contorno que só a 2 torna dispensável); as
  Tasks 4 e 5 também (a 5 constrói sobre o teste que a 4 deixou honesto).
  As Tasks 1, 6 e 7 são independentes das demais — **mas rodam uma de cada vez
  do mesmo jeito**, pela constraint global do índice do git.
- **Antes de começar, leia o ledger.** 🔴 A lição de 02/09 (Ruling S0902-R4):
  um pré-voo refeito sem ler o ledger produziu uma nota que mandava **não
  procurar um defeito vivo**. O ledger se lê **antes** do pré-voo:
  `.superpowers/sdd/2026-08-31-fecho-do-que-esta-aberto/progress.md`.
- **As duas tasks de maior risco são a 2 e a 5**, por motivos opostos: a 2 pode
  derrubar a suíte inteira (ordem de import no boot) e a 5 pode quebrar uma tela
  sem que teste nenhum veja (debounce, estado de erro do `fetch`). As duas têm
  Step de suíte cheia, e a 5 tem Step de suíte com browser.
- **Cada etapa fechada passa pelo ritual da Task 10 do plano mestre** — e o
  push **para e pergunta**.
