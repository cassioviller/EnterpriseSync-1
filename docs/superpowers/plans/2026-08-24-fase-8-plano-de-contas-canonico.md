# Fase 8 — o plano de contas passa a significar uma coisa só

> **Decisão de 01/09** (`2026-09-01-decisoes-respondidas.md` §D6/§FASE8-T1):
> a Task 4 muda de método — detecção por **assinatura estrutural** dos ≥4
> seeders concorrentes, não pela dupla que o plano assumia. Tasks 1–3 já são
> executáveis; a medição de produção (Task 1, humana) ganhou as 3 perguntas
> novas do §FASE8-T1 e segue aguardando acesso.
>
> ## 🚦 DESTRAVADO em 2026-09-04 — leia este bloco antes de qualquer outro
>
> Este plano é a **Task 12** de `2026-08-31-fecho-do-que-esta-aberto.md` e está
> **em execução**. Os dois bloqueios que o texto abaixo descreve **caíram**, e
> os sítios que ainda os repetem levam correção datada no lugar onde estão:
>
> | Bloqueio antigo | Estado hoje |
> |---|---|
> | **D6 aberta** — "não execute a Task 4 sem o Cássio julgar" | ✅ **RESPONDIDA em 01/09** (`2026-09-01-decisoes-respondidas.md` §D6): **assinatura estrutural**, não `(codigo, nome)`. O método novo está no **Step 1 reescrito** deste plano (seção "🔑 O método da Task 4") |
> | **Task 1 humana bloqueia D2** | ✅ **vira PREMISSA DECLARADA em 02/09** (§FASE8-T1). Não há acesso ao banco de produção; a q8 é escrita e testada aqui, a execução fica para quando houver acesso. **Nenhuma task espera por ela** |
> | "a fase pode ser cortada em duas" | ❌ **não pode mais** — a D6 respondida em 01/09 manda as dez juntas, para o parque nunca ficar em dois estados |
>
> ⚠️ **PREMISSA DECLARADA (decisão do dono, 02/09):** os conjuntos de códigos
> conhecidos cobrem o parque de produção. **Não foi medido** — não há acesso ao
> banco de produção (item humano nº 2 do `ESTADO-ATUAL.md`). **O que a
> ratifica:** rodar `scripts/medir_producao.py` quando houver acesso. **O que
> acontece se a premissa for falsa:** a migration **PARA e nomeia o tenant**;
> nenhuma partida é migrada para conta errada. O custo é uma rodada manual por
> tenant de terceira origem, **não dado corrompido**. É essa falha fechada que
> torna a premissa aceitável em vez de temerária.
>
> 🔬 **04/09: a contagem "3 de 21 arquivos existem" não reproduz por nenhuma
> leitura.** São **25 caminhos**; dos **18 a criar, ZERO existem**; dos a
> modificar, 7 de 7 (são pré-existentes do repo). O número honesto é: **nada da
> Fase 8 foi executado**. A frase antiga fica riscada abaixo em vez de sumir,
> porque ela aparece em outros três documentos e quem a reencontrar precisa
> saber que ela já foi conferida e reprovada.
>
> ~~**Estado em 2026-08-25 (varredura de fecho):** 🟡 **ABERTO — trabalho real pendente** — escrito em 24/08, **não executado** — 🔬 3 de 21 arquivos existem. Bloqueado por dois pontos nomeados no próprio plano: a Task 1 é humana (medir produção) e a **D6** (os dois seeders aposentados trocam o significado de `5.1.01` e `5.1.02` entre si). 🔬 3/21 dos arquivos prometidos existem na árvore.~~
>
> Este é um dos poucos planos que ainda pedem código. **As caixas `- [ ]` abaixo não foram marcadas de propósito:** elas são
> rascunho de execução, não registro de estado. Quem carrega a verdade é este bloco,
> o `ESTADO-ATUAL.md`, o código e o git. O veredito acima foi dado por **existência de
> arquivo na árvore**, nunca por contagem de caixa.


> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para executar este plano task a task. Os passos usam checkbox (`- [ ]`) para acompanhamento.

**Goal:** Fazer com que um código de conta contábil signifique a mesma coisa em todo o parque, e usar isso para entregar margem de contribuição, DFC pelos três grupos, indicadores com procedência e a exportação Domínio.

**Architecture:** Um semeador só (`seed_plano_contas_if_needed`, o `_V2_CONTAS_SEED`) vira o plano canônico; os dois concorrentes ficam marcados `EM APOSENTADORIA` e param de ser chamados. Duas colunas novas em `plano_contas` (`classificacao_gasto`, `atividade_dfc`) carregam a semântica que hoje não existe em lugar nenhum, e as Tasks de leitura (margem, DFC, indicadores) são **leitura pura** — nenhuma cria caminho de escrita novo. O único ponto que toca dado histórico é o de-para das contas `5.x`, isolado numa migration própria com contagem antes e depois.

**Tech Stack:** Flask + SQLAlchemy 2.x, PostgreSQL, pytest, Jinja2. Migrations pelo runner caseiro de `migrations.py` (tupla ordenada, não Alembic).

**Spec:** `docs/superpowers/specs/2026-08-17-fase-8-financeiro-design.md` — leia antes de começar; este plano argumenta a partir dela e não a substitui. O plano velho `docs/superpowers/plans/2026-07-21-fase-8-financeiro-avancado-dominio.md` é da versão anterior do escopo: serve de referência histórica, **não** de roteiro.

---

## ⚠️ Procedência: o que mudou entre a spec (17/08) e este plano (24/08)

A spec traz números e `caminho:linha` medidos em 17/08. Sete dias depois, quatro envelheceram. Nenhum invalida a spec; todos mudam instruções deste plano. Marcas iguais às do `ESTADO-ATUAL.md`: 🔬 medido · 📖 lido no código.

| A spec diz | 🔬 24/08 | Consequência para o executor |
|---|---|---|
| migrations **310 e 311** (D4: "a maior aplicada é a 309") | a maior no repo é a **314** | Use **323** e **324**. É a própria regra da D4 aplicada de novo: numerar em sequência real, nunca renumerar para "organizar" — foi assim que nasceu o fantasma do 270 |
| `scripts/medir_producao.py` "ganha uma **sétima** pergunta" | 📖 o arquivo já tem `q1`..`q7` (a q7 é pontos duplicados no dia) | A pergunta nova é a **q8** |
| "as **28** contas do canônico" | 🔬 24/08: **35** linhas — 🔴 **04/09: são 36.** `V2 − SEED = {'6.1.02.009'}`, conferido por diferença de conjuntos | O seed de classificação da Task 5 cobre **36** contas. A 36ª é alvo vivo de `MAPEAMENTO_CONTABIL['despesa_geral']` |
| `PlanoContas` em `models.py:3234`, `PartidaContabil` em `:3332` | 📖 **3247** e **3345** | Deriva de edições posteriores. Ancore por nome de classe, não por linha |

## Global Constraints

- **Nada de flag de comportamento.** A fase não muda comportamento: conserta significado de dado e acrescenta leitura. Não introduza `feature flag` nenhuma.
- **Nenhuma coluna nova em `partida_contabil` nem em `lancamento_contabil`.** Tudo o que DFC, margem e indicadores precisam já está lá (`conta_codigo`, `admin_id`, `tipo_partida`, `valor`).
- **Nenhuma partida é apagada ou somada.** Se um código `5.x` não tiver destino explícito, a migration **falha e nomeia o código**. Nunca chuta.
- **Conta nunca é apagada.** `5.x` sem partida vira `ativo = False` — relatório histórico aponta para ela.
- **Relatório não esconde o que não sabe.** Não classificado aparece **como não classificado, com o valor**. DFC que não fecha **mostra a diferença**. Indicador sem base sai como "sem base", nunca `0%` nem `inf`.
- **Todo indicador na tela exibe data-base e as contas que o compõem.** Número sem procedência é o defeito de fabricação que abre o `ESTADO-ATUAL.md`.
- **`classificacao_gasto`** — `VARCHAR(12)`, NOT NULL, default `'nao_classificado'`. Valores: `fixo` | `variavel` | `nao_aplicavel` | `nao_classificado`.
- **`atividade_dfc`** — `VARCHAR(14)`, NOT NULL, default `'operacional'`. Valores: `operacional` | `investimento` | `financiamento`.
- **Migrations 323 e 324**, registradas **na ordem** na tupla de `migrations.py`. O runner governa pela ordem da tupla, não pelo máximo do repo. Toda migration é provada idempotente por **dupla execução** no banco de dev antes do commit.
- **TDD sem exceção.** Teste primeiro, RED conferido e citado no commit, depois o código.

---

## ✅ Bloqueios antes de começar — os dois caíram (04/09)

> Esta seção foi **reescrita em 04/09**, no Step 0-b da Task 12 do plano-mestre.
> O texto original mandava o executor parar na Task 4 em **seis** sítios; a D6
> foi respondida em 01/09 e a FASE8-T1 virou premissa declarada em 02/09. O que
> segue abaixo é o texto vigente; o antigo está riscado no fim da seção, porque
> ele é a origem de um bloqueio que outros documentos ainda citam.

**1. ~~Task 1 é humana e é pré-requisito de D2~~ → PREMISSA DECLARADA.** Não há
acesso ao banco de produção (item humano nº 2 do `ESTADO-ATUAL.md`). A q8 é
**escrita e testada aqui**; a execução contra produção fica para quando houver
acesso. **Nenhuma das dez tasks espera por ela** — ver o Step 6 da Task 12 do
plano-mestre, que carimba a premissa e o que a ratifica.

**2. ~~A D6 bloqueia a Task 4~~ → RESPONDIDA em 01/09: assinatura estrutural.**
O método está escrito logo abaixo e **substitui** a recomendação de
`(codigo, nome)` que este plano trazia.

### 🔑 O método da Task 4 — assinatura estrutural (D6 respondida, e corrigida em 04/09)

🔴 **O problema que a D6 nomeou continua real:** 🔬 `5.1.01` e `5.1.02` estão
**trocados** entre os dois seeders aposentados —

| Código | `contabilidade_utils.criar_plano_contas_padrao` (nº1) | `financeiro_seeds.PLANO_CONTAS_CONSTRUCAO` (nº2) |
|---|---|---|
| `5` | CUSTOS | DESPESAS |
| `5.1` | CUSTO DOS SERVIÇOS PRESTADOS | DESPESAS OPERACIONAIS |
| **`5.1.01`** | **Materiais Diretos** | **MÃO DE OBRA** |
| **`5.1.02`** | **Mão de Obra Direta** | **MATERIAIS** |
| `5.2` / `5.1.03`+ | CUSTOS INDIRETOS, Materiais Indiretos | EQUIPAMENTOS, VEÍCULOS, ADMINISTRATIVAS |

Um de-para chaveado **só em `codigo`** mandaria material para pessoal em metade
do parque, **em silêncio**. Por isso o de-para é chaveado em
**`(assinatura, codigo)`**, e a assinatura é descoberta pela **forma do plano de
contas do tenant** — nunca pelo `nome` da conta, que é justamente o que está
inconsistente.

🔴 **Correção obrigatória de 04/09: são QUATRO planos concorrentes, não dois** —
📖 `contabilidade_utils.py:514` já dizia isso, e o método original foi montado
contra dois. 🔬 Medidos por AST sobre o fonte:

| # | Onde | Contas | Marca estrutural |
|---|---|---|---|
| 1 | `contabilidade_utils.criar_plano_contas_padrao:21` — **aposentado** | 56 | `5.1.01 'Materiais Diretos'` aceita=**True**, `5.2.01 'Materiais Indiretos'`, `2.1.03.007-009`, `4.1.02.%` |
| 2 | `financeiro_seeds.PLANO_CONTAS_CONSTRUCAO:10` + `:103` — **aposentado** | 62 | `5.1.01 'MÃO DE OBRA'` aceita=**False** com filhos `5.1.01.001-004`, `2.1.03.001-003`, `4.1.01.001-003` |
| 3 | `contabilidade_utils._V2_CONTAS_SEED:1550` — **o canônico** | 36 | grupo `6` inteiro, `2.1.03.001`, `4.1.01.001`, **zero contas `5.x`** |
| 4 | `scripts/seed_demo_alfa.py::_upsert_conta:3480` (de `_seed:464`) | 12 | 🔴 **raízes invertidas**: `3` = receita, `4` = despesa; **zero contas `5.x`** |

⚠️ O nº4 **roda sozinho no boot** (📖 `app.py:618`, auto-seed do demo Alfa) —
existe em todo dev e todo CI. Qualquer método que o faça parar a migration para
o parque inteiro, todo dia.

🔴 **Os dois sinais que o texto anterior usava e que NÃO discriminam** — medidos
contra os quatro, não contra dois:

| Sinal descartado | Por que não serve |
|---|---|
| **existe grupo `6`** | 🔬 o **canônico (nº3) tem 10 contas `6.*`** — é a maioria do parque. Este sinal rotularia de legado quase todo tenant são |
| **`4.1.01.%`** e **`2.1.03.001`** | 🔬 ambos existem também no nº3; e o nº4 tem `4.1.01` **e** `4.1.02` ao mesmo tempo, casando com dois sinais de uma vez |

✅ **Os cinco sinais limpos** — 🔬 exclusivos de um só dos quatro planos:

| Sinal | Aponta para | Prova |
|---|---|---|
| filhos `5.1.01.001-004` (`codigo LIKE '5.1.01.%'`) | **nº2** | nº1 tem só a folha `5.1.01`; nº3 e nº4 têm zero `5.x` |
| `5.1.01` com `aceita_lancamento = False` | **nº2** | lá `5.1.01` é sintética ('MÃO DE OBRA'); no nº1 é analítica |
| `5.1.01` com `aceita_lancamento = True` | **nº1** | 'Materiais Diretos', e é ela que carrega partida |
| `5.2.01` | **nº1** | 'Materiais Indiretos'; o nº2 não tem `5.2.01` |
| `2.1.03.007-009` e `4.1.02.%` | **nº1** | exclusivos do nº1 entre os quatro |

### A regra que fecha o método

⚠️ **A assinatura só precisa separar os DOIS APOSENTADOS.** Só eles criam contas
`5.x`, e **só as `5.x` migram**. Um tenant canônico (nº3) ou demo (nº4) não tem
`5.x` e o de-para é **no-op** nele. Chavear por "grupo 6" trocava um sinal
irrelevante por rótulo errado na maioria do parque.

`classificar_assinatura(admin_id)` tem **quatro saídas**, não duas:

| Saída | Quando | O que a migration faz |
|---|---|---|
| `'contabilidade_utils'` | casa os sinais do nº1 | de-para do nº1 |
| `'financeiro_seeds'` | casa os sinais do nº2 | de-para do nº2 |
| `'sem_5x'` | o tenant **não tem nenhuma conta `5.x`** | **no-op** — nada a migrar |
| `AssinaturaDesconhecida(admin_id)` | tem `5.x` e **não casa nenhum dos dois** | 🔴 **PARA e NOMEIA o tenant** |

🔴 **E o ramo que o plano não tinha: a partida órfã.** 📖 O `JOIN plano_contas`
do de-para exclui toda partida cujo `conta_codigo` não tem linha no plano do
tenant — ela não migra, e o passo final estoura com *"N partidas continuam em
5.x"* **sem nomear nada**. 🔬 Existem códigos `5.x` que **nenhum** dos quatro
seeders cria e o relatório lê: `5.1.03` (CMV, `contabilidade_utils.py:643`),
`5.2.01` (`:700`), `5.3.01`/`5.3.02` (`:707-708`, e ambos em
`_DRE_PREFIXOS_FORA_DAS_OPERACIONAIS`, `:527`). A falha fechada tem de
**nomear `(admin_id, conta_codigo)`** dessas partidas, não só contá-las.

Derivar por semelhança de string (`'MÃO DE OBRA' ≈ 'Mão de Obra Direta'`)
continua **proibido**, e nenhum dos cinco sinais lê `nome` — a proibição da spec
é preservada.

### O texto antigo, riscado

> ~~**1. Task 1 é humana e é pré-requisito de D2.** A Task 1 mede produção. Sem ela, a Task 4 (de-para) está sendo decidida com número de banco de dev — que é 99,9% resíduo de suíte. Se produção mostrar `5.x` dominante, **esta spec está errada** e o canônico volta à mesa.~~
>
> ~~**2. Há uma decisão nova, D6, que a spec não previu. Ela bloqueia a Task 4.**~~
>
> ~~*Recomendado:* chavear o de-para em **`(codigo, nome)` com igualdade exata** contra os dois conjuntos fechados que estão **no repositório** — não é heurística de nome, é reconhecer a assinatura de um dos dois seeders conhecidos. Qualquer `(codigo, nome)` fora dos dois conjuntos **faz a migration falhar e nomear o par**.~~ → 🔴 **substituído pela assinatura estrutural acima.** O `(codigo, nome)` ainda depende do `nome`, que a spec proíbe e que é o dado inconsistente.
>
> ~~⚠️ **Não execute a Task 4 sem o Cássio julgar a D6.** As Tasks 1, 2, 3 e 5 a 10 não dependem dela e podem correr antes.~~ → ✅ **a D6 foi julgada em 01/09.**

---

## ❌ A fase NÃO pode mais ser cortada em duas

> Reescrito em 04/09. ~~Se a fase inteira for grande demais para uma branch só, o corte natural é **depois da Task 6**~~ — a **D6 respondida em 01/09** decidiu que **as dez tasks entram juntas**, para o parque nunca ficar em dois estados. O aviso original continua valendo como razão: aposentar o semeador sem migrar as `5.x` deixa metade do parque com significado velho e metade com o novo.

## File Structure

| Arquivo | Responsabilidade | Ação |
|---|---|---|
| `scripts/medir_producao.py` | q8: retrato de `5.x` × `6.x` em produção | Modificar |
| `models.py` (`PlanoContas`, 🔬 04/09 em ~**3253**) | as duas colunas novas | Modificar |
| `migrations.py` | 323 (colunas) e 324 (de-para) | Modificar |
| `contabilidade_utils.py` | canônico; `criar_plano_contas_padrao` marcada `EM APOSENTADORIA`; **`classificar_assinatura` + `AssinaturaDesconhecida`** (Task 4) | Modificar |
| `financeiro_seeds.py` | `criar_plano_contas_padrao` marcada `EM APOSENTADORIA` | Modificar |
| `contabilidade_views.py` 🔬 **:93**, `financeiro_views.py` 🔬 **:1320** (as duas âncoras andaram; localize por conteúdo) | passam a chamar o semeador único | Modificar |
| `services/plano_contas_depara.py` | **o de-para `(assinatura, codigo) → codigo`**, dado puro, sem lógica | Criar |
| `services/classificacao_gasto.py` | seed de `classificacao_gasto` + `atividade_dfc` das 🔬 **36** canônicas | Criar |
| `services/dfc_service.py` | DFC método direto pela contrapartida | Criar |
| `services/indicadores_service.py` | liquidez, estrutura, rentabilidade, ciclos | Criar |
| `services/exportacao_dominio.py` | exportação Domínio | Criar |
| `contabilidade_views.py` | rotas de classificação, DFC, indicadores, exportação | Modificar |
| `templates/contabilidade/{classificacao_contas,dfc,indicadores}.html` | as três telas novas | Criar |
| `tests/test_fase8_*.py` | um arquivo por task | Criar |

Por que `services/plano_contas_depara.py` é arquivo próprio e só dado: o de-para é a peça que um humano precisa **revisar linha a linha** antes da migration rodar. Misturado com lógica, ninguém revisa.

---

### Task 1 — q8 em `medir_producao.py`: o retrato de produção

🔴 **Roda contra produção, exige o humano.** O código da q8 é escrito e testado aqui; a execução é do Cássio.

**Files:**
- Modify: `scripts/medir_producao.py` (acrescenta `q8_planos_de_contas`, registra em `main()`)
- Test: `tests/test_fase8_medicao_q8.py`

**Interfaces:**
- Produces: `q8_planos_de_contas(cur) -> None` — imprime; segue o molde de `q1`..`q7` (usa `_t`, `_um`, `secao`).

- [ ] **Step 1: Escrever o teste que falha**

O teste roda a query da q8 contra o banco de dev por `db.engine`, sem depender do `psycopg2` direto do script.

```python
# tests/test_fase8_medicao_q8.py
"""q8 de medir_producao: quantos tenants em 5.x, 6.x, ambos, nenhum;
quantas partidas vivem em 5.x; e se existe partida órfã."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db  # noqa: E402


def test_q8_devolve_as_tres_respostas_e_nao_inventa_orfa():
    from scripts.medir_producao import SQL_Q8_PARTIDAS_5X, SQL_Q8_PARTIDAS_ORFAS, SQL_Q8_TENANTS
    with app.app_context():
        from sqlalchemy import text
        linhas = db.session.execute(text(SQL_Q8_TENANTS)).fetchall()
        assert linhas, 'a q8 tem de devolver ao menos uma linha de retrato'
        assert {c.lower() for c in linhas[0]._mapping.keys()} >= {
            'so_5x', 'so_6x', 'ambos', 'nenhum'}

        cinco = db.session.execute(text(SQL_Q8_PARTIDAS_5X)).scalar()
        assert cinco is not None and cinco >= 0

        orfas = db.session.execute(text(SQL_Q8_PARTIDAS_ORFAS)).scalar()
        assert orfas is not None, (
            'partida órfã tem de ser CONTADA, não presumida zero — se '
            'produção divergir do dev, a fase inteira volta à mesa')
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.pythonlibs/bin/pytest tests/test_fase8_medicao_q8.py -v`
Expected: FAIL com `ImportError: cannot import name 'SQL_Q8_TENANTS'`.

- [ ] **Step 3: Escrever a q8**

As três SQL saem como constantes de módulo justamente para o teste poder rodá-las sem `psycopg2`.

```python
# scripts/medir_producao.py — junto das outras perguntas

SQL_Q8_TENANTS = """
    WITH por_tenant AS (
        SELECT admin_id,
               bool_or(codigo LIKE '5.%%') AS tem5,
               bool_or(codigo LIKE '6.%%') AS tem6
          FROM plano_contas
         GROUP BY admin_id
    )
    SELECT count(*) FILTER (WHERE tem5 AND NOT tem6) AS so_5x,
           count(*) FILTER (WHERE tem6 AND NOT tem5) AS so_6x,
           count(*) FILTER (WHERE tem5 AND tem6)     AS ambos,
           count(*) FILTER (WHERE NOT tem5 AND NOT tem6) AS nenhum
      FROM por_tenant
"""

SQL_Q8_PARTIDAS_5X = """
    SELECT count(*) FROM partida_contabil WHERE conta_codigo LIKE '5.%%'
"""

SQL_Q8_PARTIDAS_ORFAS = """
    SELECT count(*)
      FROM partida_contabil p
     WHERE NOT EXISTS (
           SELECT 1 FROM plano_contas c
            WHERE c.codigo = p.conta_codigo AND c.admin_id = p.admin_id)
"""


def q8_planos_de_contas(cur):
    """Fase 8 / Task 1 — o retrato que decide se a Task 4 é um de-para de
    algumas centenas de linhas ou um projeto próprio.

    A pergunta que importa é UMA: quantas partidas vivem em `5.x` lá.
    ⚠️ Se produção mostrar `5.x` dominante, a spec da Fase 8 está errada e o
    canônico tem de ser reavaliado ANTES de qualquer código.
    """
    secao('q8 — planos de contas concorrentes (Fase 8)')
    for linha in _t(cur, SQL_Q8_TENANTS):
        print(f'  tenants só 5.x: {linha[0]} | só 6.x: {linha[1]} | '
              f'ambos: {linha[2]} | nenhum: {linha[3]}')
    print(f'  partidas em 5.x: {_um(cur, SQL_Q8_PARTIDAS_5X)}')
    orfas = _um(cur, SQL_Q8_PARTIDAS_ORFAS)
    print(f'  partidas ÓRFÃS (conta inexistente no plano do tenant): {orfas}')
    if orfas:
        print('  🔴 dev media ZERO órfãs. Produção divergiu — PARE e reveja '
              'a spec inteira antes de escrever a migration 324.')
```

E registre a chamada em `main()`, junto das outras: `q8_planos_de_contas(cur)`.

- [ ] **Step 4: Rodar e ver passar**

Run: `.pythonlibs/bin/pytest tests/test_fase8_medicao_q8.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/medir_producao.py tests/test_fase8_medicao_q8.py
git commit -m "feat(fase8): q8 de medir_producao — o retrato de 5.x que decide o tamanho da Task 4"
```

- [ ] **Step 6: 🔴 Entregar ao humano e PARAR nesta frente**

Peça ao Cássio: `python scripts/medir_producao.py` contra produção, e cole a saída da q8 no ledger de execução. **A Task 4 não começa sem esse número.** As Tasks 2, 3, 5–10 seguem em paralelo.

---

### Task 2 — as duas colunas (migration 323)

**Files:**
- Modify: `models.py` (classe `PlanoContas`)
- Modify: `migrations.py` (`_migration_323_plano_contas_semantica` + registro na tupla)
- Test: `tests/test_fase8_colunas_semantica.py`

**Interfaces:**
- Produces: `PlanoContas.classificacao_gasto` (str) e `PlanoContas.atividade_dfc` (str), mais as constantes `PlanoContas.CLASSIFICACAO_*` e `PlanoContas.DFC_*` usadas pelas Tasks 5–8.

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_fase8_colunas_semantica.py
"""As duas colunas de significado: default que NÃO classifica no gasto, e
default operacional no DFC — os dois escolhidos por motivos opostos e
ambos deliberados (ver spec, 'Modelo de dados')."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db  # noqa: E402


def test_conta_nova_nasce_nao_classificada_e_operacional():
    from models import PlanoContas
    with app.app_context():
        admin_id = _admin_de_teste()
        conta = PlanoContas(codigo='9.9.99.999', nome='Conta de teste',
                            tipo_conta='DESPESA', natureza='DEVEDORA',
                            nivel=4, aceita_lancamento=True, ativo=True,
                            admin_id=admin_id)
        db.session.add(conta)
        db.session.flush()

        assert conta.classificacao_gasto == PlanoContas.CLASSIFICACAO_NAO_CLASSIFICADO, (
            'default fixo produziria margem que parece pronta e está errada')
        assert conta.atividade_dfc == PlanoContas.DFC_OPERACIONAL, (
            'default neutro faria o DFC nascer com quase tudo fora dos três '
            'grupos — inutilizável no dia 1')
        db.session.rollback()
```

(`_admin_de_teste()` — copie o helper do arquivo de teste vizinho mais novo, `tests/test_fase6_contrato_baseline.py`, que já cria tenant próprio por teste. Não reutilize o tenant 1.)

- [ ] **Step 2: Rodar e ver falhar**

Run: `.pythonlibs/bin/pytest tests/test_fase8_colunas_semantica.py -v`
Expected: FAIL com `AttributeError: type object 'PlanoContas' has no attribute 'CLASSIFICACAO_NAO_CLASSIFICADO'`.

- [ ] **Step 3: Colunas no modelo**

```python
# models.py, dentro de class PlanoContas
    CLASSIFICACAO_FIXO = 'fixo'
    CLASSIFICACAO_VARIAVEL = 'variavel'
    CLASSIFICACAO_NAO_APLICAVEL = 'nao_aplicavel'
    CLASSIFICACAO_NAO_CLASSIFICADO = 'nao_classificado'

    DFC_OPERACIONAL = 'operacional'
    DFC_INVESTIMENTO = 'investimento'
    DFC_FINANCIAMENTO = 'financiamento'

    # Fase 8 — por TENANT e não constante de código, pelo mesmo motivo de
    # FaixaAlcada: frota é gasto fixo para quem tem frota própria e variável
    # para quem aluga por obra. Número que é regra de negócio não entra em
    # `if`. `nao_aplicavel` existe para ativo/passivo/PL/receita: sem ele,
    # "sem classificação" misturaria o que FALTA classificar com o que NUNCA
    # será, e o indicador de completude não significaria nada.
    classificacao_gasto = db.Column(db.String(12), nullable=False,
                                    default=CLASSIFICACAO_NAO_CLASSIFICADO,
                                    server_default=CLASSIFICACAO_NAO_CLASSIFICADO)
    atividade_dfc = db.Column(db.String(14), nullable=False,
                              default=DFC_OPERACIONAL,
                              server_default=DFC_OPERACIONAL)
```

- [ ] **Step 4: A migration 323**

```python
# migrations.py
def _migration_323_plano_contas_semantica():
    """Fase 8 — plano_contas ganha classificacao_gasto e atividade_dfc.

    Os defaults são escolhidos por motivos OPOSTOS e os dois de propósito:
    `nao_classificado` no gasto porque classificar por conta própria produz
    margem errada com cara de pronta; `operacional` no DFC porque na
    esmagadora maioria das contas de uma construtora é isso, e um default
    neutro faria o DFC nascer inutilizável.

    323 e não 310, nem 315: a D4 da spec pediu 310 quando a maior aplicada
    era a 309; 🔬 24/08 a maior do repo era a 314, e este plano escreveu 315.
    🔬 04/09 a maior é a 322 (o Resgate da Espinha gastou 319-322), logo 323.
    A regra da própria D4 — numerar pela sequência real MEDIDA no dia, nunca
    renumerar para organizar — é o que manda, e é ela que produziu os três
    números diferentes. Quem executar mede de novo antes de colar.

    Idempotente: ADD COLUMN IF NOT EXISTS.
    """
    from sqlalchemy import text as sa_text
    try:
        with db.engine.begin() as conn:
            conn.execute(sa_text("""
                ALTER TABLE plano_contas
                    ADD COLUMN IF NOT EXISTS classificacao_gasto
                        VARCHAR(12) NOT NULL DEFAULT 'nao_classificado'
            """))
            conn.execute(sa_text("""
                ALTER TABLE plano_contas
                    ADD COLUMN IF NOT EXISTS atividade_dfc
                        VARCHAR(14) NOT NULL DEFAULT 'operacional'
            """))
        logger.info('[Migration 323] plano_contas: classificacao_gasto e '
                    'atividade_dfc criadas.')
        return True
    except Exception as e:
        logger.error(f'[Migration 323] Falha: {e}', exc_info=True)
        return False
```

Registre **na ordem**, no fim da tupla:

```python
            (323, "Fase 8 — plano_contas.classificacao_gasto + atividade_dfc: a semantica que destrava margem de contribuicao e DFC", _migration_323_plano_contas_semantica),
```

- [ ] **Step 5: Rodar e ver passar, e provar idempotente**

```bash
.pythonlibs/bin/pytest tests/test_fase8_colunas_semantica.py -v
.pythonlibs/bin/python -c "from app import app; from migrations import _migration_323_plano_contas_semantica as m; app.app_context().push(); print(m(), m())"
```
Expected: PASS; e `True True` — a **dupla execução** é a prova de idempotência, não a leitura do SQL.

- [ ] **Step 6: Commit**

```bash
git add models.py migrations.py tests/test_fase8_colunas_semantica.py
git commit -m "feat(fase8): plano_contas ganha classificacao_gasto e atividade_dfc (migration 323)"
```

---

### Task 3 — um semeador só, e o guarda que impede o quarto

**Files:**
- Modify: `contabilidade_views.py:95`, `financeiro_views.py:1324-1329`
- Modify: `contabilidade_utils.py:21` e `financeiro_seeds.py:103` (marcar `EM APOSENTADORIA`)
- Test: `tests/test_fase8_semeador_unico.py`

**Interfaces:**
- Consumes: `contabilidade_utils.seed_plano_contas_if_needed(admin_id) -> None` (já existe, `:1597`).
- Produces: nenhuma assinatura nova. As duas `criar_plano_contas_padrao` continuam importáveis e **não são apagadas**.

- [ ] **Step 1: Escrever os dois testes que falham**

```python
# tests/test_fase8_semeador_unico.py
"""Dois tenants semeados por caminhos diferentes têm de receber O MESMO
plano. E um guarda por `ast` para ninguém acrescentar um quarto semeador —
mesmo molde do guarda da C9 da Fase 2, que já provou o valor dele."""
import ast
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db  # noqa: E402

# Os QUATRO lugares que instanciam PlanoContas hoje: o semeador canônico usa
# SQL puro, então sobram a dupla em aposentadoria e o seed de DEMONSTRAÇÃO.
#
# 🔴 CORREÇÃO DE 04/09 (pré-voo da Task 12): a versão de 24/08 listava só os
# dois primeiros, e 🔬 o scan devolve QUATRO. O teste reprovava acusando de
# "criador NOVO" código que já estava na árvore desde antes do plano — falso
# positivo no RED, o defeito que esta casa persegue. `scripts/` NÃO está na
# lista de diretórios ignorados abaixo, e não deve estar: seed de demo que
# roda no boot (📖 app.py:618) é código vivo, não andaime.
_CRIADORES_CONHECIDOS = {
    ('financeiro_seeds.py', 'criar_plano_contas_padrao'),
    ('contabilidade_utils.py', 'criar_plano_contas_padrao'),
    # scripts/seed_demo_alfa.py — seed da Construtora Alfa (demo), 12 contas
    # com as raízes INVERTIDAS (3 = receita, 4 = despesa). É o 4º plano
    # concorrente. Ele não é alvo desta fase (não cria 5.x, logo o de-para é
    # no-op nele), mas está aqui para o guarda não mentir.
    ('seed_demo_alfa.py', '_seed'),
    ('seed_demo_alfa.py', '_upsert_conta'),
}


def test_nenhum_criador_novo_de_plano_contas():
    raiz = pathlib.Path(__file__).resolve().parent.parent
    achados = set()
    for py in raiz.rglob('*.py'):
        partes = set(py.relative_to(raiz).parts)
        if partes & {'archive', 'tests', '__pycache__', '.pythonlibs', 'backups'}:
            continue
        try:
            arvore = ast.parse(py.read_text(encoding='utf-8'))
        except SyntaxError:
            continue
        for no in ast.walk(arvore):
            if isinstance(no, ast.FunctionDef):
                for interno in ast.walk(no):
                    if (isinstance(interno, ast.Call)
                            and isinstance(interno.func, ast.Name)
                            and interno.func.id == 'PlanoContas'):
                        achados.add((py.name, no.name))
    assert achados <= _CRIADORES_CONHECIDOS, (
        'criador NOVO de PlanoContas: '
        f'{sorted(achados - _CRIADORES_CONHECIDOS)}. Para cada código, o '
        'primeiro semeador a rodar decide o significado e os outros são '
        'descartados em silêncio — é o defeito que a Fase 8 fecha.')


def test_dois_caminhos_de_semeadura_dao_o_mesmo_plano():
    from models import PlanoContas
    with app.app_context():
        a = _admin_de_teste()
        b = _admin_de_teste()

        # caminho 1: a tela de contabilidade
        with app.test_client() as c:
            _logar(c, a)
            c.get('/contabilidade/plano-contas')
        # caminho 2: o botão do financeiro
        with app.test_client() as c:
            _logar(c, b)
            c.post('/financeiro/plano-contas/inicializar')

        plano_a = {x.codigo: x.nome for x in
                   PlanoContas.query.filter_by(admin_id=a).all()}
        plano_b = {x.codigo: x.nome for x in
                   PlanoContas.query.filter_by(admin_id=b).all()}
        assert plano_a and plano_a == plano_b, (
            'dois tenants receberam planos diferentes por terem clicado em '
            f'telas diferentes — só em A: {sorted(set(plano_a) - set(plano_b))}, '
            f'só em B: {sorted(set(plano_b) - set(plano_a))}')
```

(`_logar(client, admin_id)` — copie do arquivo de teste HTTP mais novo da casa, `tests/test_fase6_aditivo.py`, que já resolve sessão e `WTF_CSRF_ENABLED=False`.)

- [ ] **Step 2: Rodar e ver falhar**

Run: `.pythonlibs/bin/pytest tests/test_fase8_semeador_unico.py -v`
Expected: `test_dois_caminhos...` FALHA com planos divergentes (`5.1.01` num, ausente no outro). O guarda por `ast` pode já passar — se passar, **está certo**: ele é rede para o futuro, não descrição de defeito atual. Registre isso no ledger em vez de forçar um RED artificial.

- [ ] **Step 3: Trocar os dois chamadores**

```python
# contabilidade_views.py, ~:95 — no lugar de criar_plano_contas_padrao(admin_id)
        # Fase 8 — semeador ÚNICO. Antes, cada tela semeava com um conteúdo
        # diferente e o primeiro a rodar decidia o que `5.1.01` significa
        # naquele tenant. Ver docs/superpowers/specs/2026-08-17-fase-8-financeiro-design.md
        from contabilidade_utils import seed_plano_contas_if_needed
        seed_plano_contas_if_needed(admin_id)
```

```python
# financeiro_views.py, ~:1324 — no lugar do import e da chamada
        # Fase 8 — semeador ÚNICO (ver contabilidade_views.py e a spec).
        from contabilidade_utils import seed_plano_contas_if_needed
        seed_plano_contas_if_needed(admin_id)
        contas_criadas = PlanoContas.query.filter_by(admin_id=admin_id).count()
```

- [ ] **Step 4: Marcar as duas em aposentadoria (sem apagar)**

No topo da docstring de **ambas** as `criar_plano_contas_padrao`:

```python
    ⚠️ EM APOSENTADORIA (Fase 8, 2026-08-24). Não tem mais chamador vivo.
    NÃO É APAGADA de propósito: remover a função e mudar o leitor no mesmo
    release são duas mudanças difíceis de bissetar juntas — mesma decisão
    da AlocacaoEquipe no p7. O semeador vivo é
    `contabilidade_utils.seed_plano_contas_if_needed`.
    Spec: docs/superpowers/specs/2026-08-17-fase-8-financeiro-design.md
```

- [ ] **Step 5: Rodar e ver passar**

Run: `.pythonlibs/bin/pytest tests/test_fase8_semeador_unico.py -v`
Expected: PASS nos dois.

- [ ] **Step 6: Commit**

```bash
git add contabilidade_views.py financeiro_views.py contabilidade_utils.py financeiro_seeds.py tests/test_fase8_semeador_unico.py
git commit -m "feat(fase8): um semeador so — os dois concorrentes ficam EM APOSENTADORIA, com guarda por ast"
```

---

### Task 4 — o de-para das `5.x` (migration 324), por **assinatura estrutural**

> ♻️ **REESCRITA em 04/09** (Step 1 e Step 0-c da Task 12 do plano-mestre). A
> versão de 24/08 chaveava o de-para em `(codigo, nome)` e vinha marcada
> *"Bloqueada por D6 e pela Task 1"*. A **D6 foi respondida em 01/09**
> (assinatura estrutural) e a **Task 1 virou premissa declarada em 02/09**:
> nenhum dos dois bloqueia. O método vigente está na seção
> **"🔑 O método da Task 4"** no topo deste plano — leia-a antes deste bloco.
>
> ⚠️ **Por que a reescrita, e não só o destravamento:** trocar o método sem
> reescrever o corpo deixaria **oito sítios** deste plano (o dict, a docstring,
> a query `pares`, o `UPDATE`, o registry, a mensagem de commit, a Interface e
> o `CONTAS_5X_SINTETICAS`) dando a instrução **oposta** à do cabeçalho. Um
> implementador que lesse o corpo voltaria a chavear por `nome`.

Único ponto da fase que toca dado histórico.

**Files:**
- Create: `services/plano_contas_depara.py`
- Modify: `contabilidade_utils.py` (`AssinaturaDesconhecida` + `classificar_assinatura`; e os mapas de leitura do DRE, `:590` e `:712` — ver Step 0)
- Modify: `event_manager.py` (`:1488`, o escritor vivo de `5.1.01.001` — ver Step 0)
- Modify: `migrations.py` (`_migration_324_depara_contas_5x` + registro)
- Modify: `tests/test_fase06_d3_dre_despesas_v2.py` (ele prova a coexistência que esta task remove)
- Test: `tests/test_fase8_depara_5x.py`, e o censo de literal `5.x` novo

**Interfaces:**
- Produces: `DEPARA_5X: dict[tuple[str, str], str]` — chave **`(assinatura, codigo)`**, valor o código canônico de destino; `CONTAS_5X_CONHECIDAS: set[str]` derivado das chaves.
- Produces: `classificar_assinatura(admin_id, conn=None) -> str` em `contabilidade_utils.py`, devolvendo `'contabilidade_utils' | 'financeiro_seeds' | 'sem_5x'`, e a exceção `AssinaturaDesconhecida`.
- Consumes: nada de fora do repo. **Nenhum sinal lê `plano_contas.nome`.**

- [ ] **Step 0: O inventário dos leitores e escritores VIVOS de `5.x` — 🔴 achado de 04/09, e ele muda o tamanho da task**

🔴 **A Fase 8 não pode migrar as `5.x` e deixar o app apontando para elas.** 🔬
Medido no banco de dev e na fonte em 04/09, **depois** de o plano estar escrito:

| Sítio vivo | O que faz hoje | O que acontece DEPOIS do de-para, se nada mudar |
|---|---|---|
| 📖 `event_manager.py:1488` — handler de `folha_processada` | `PlanoContas.query.filter_by(codigo='5.1.01.001', ativo=True)` | 🔴 o passo 5 desativa a `5.1.01.001` (ela fica sem partida). A busca devolve `None`, e `:1520` faz `logger.warning('Plano de contas incompleto') ; return` — **a folha para de gerar lançamento contábil, em silêncio**. Falha fechada, mas silenciosa: só um warning no log |
| 📖 `contabilidade_utils.py:712` | `cmv = calcular_valor_contas(['5.1.03'], 'DEBITO')` | 🔴 **o CMV do DRE vai a zero** — nenhuma partida mora mais em `5.1.03` |
| 📖 `contabilidade_utils.py:590` | `_DRE_PREFIXOS_FORA_DAS_OPERACIONAIS = ('5.1.03', '5.2.01', '5.3.01', '5.3.02')` | 🔴 as quatro linhas próprias do DRE vão a zero |
| 📖 `contabilidade_utils.py:602-605` | `'pessoal': ('5.1.01','6.1.01')`, `'materiais': ('5.1.02',)`, `'administrativas': ('5.1.04',)`, `'comerciais': ('5.1.05',)` | ⚠️ `pessoal` sobrevive (já lê as duas raízes); **as outras três vão a zero** |

⚠️ **Isto não é a mesma coisa que o mapa de prefixos invertido** que a Onda 4
mediu e deixou para esta fase. Aquele é um erro de *classificação*; este é o
dado **sumindo de baixo** do leitor. Os dois se resolvem aqui, mas são
defeitos diferentes e cada um tem seu teste.

**O que este Step exige, no MESMO commit da migration:**

1. `event_manager.py:1488` passa a `'6.1.01.001'` (o destino que o `DEPARA_5X`
   já dá para `('financeiro_seeds', '5.1.01.001')` — os dois têm de bater, e há
   teste que falha se divergirem).
2. `contabilidade_utils.py:712` e `:590` passam aos prefixos canônicos.
   ⚠️ **`5.1.03` (CMV) não tem par óbvio no canônico** — 🔬 `_V2_CONTAS_SEED`
   não tem conta de CMV. Se não houver destino, **declare o resíduo por
   escrito** e deixe a linha de CMV do DRE saindo como "sem base", nunca como
   `0,00`: é a Global Constraint *"Indicador sem base sai como 'sem base'"*.
3. Um **censo** que falhe quando aparecer literal `5.x` novo fora dos dois
   seeders aposentados — o padrão que a casa já usa para resolvedor de tenant e
   para rótulo de origem. Sem ele, o próximo caminho de escrita volta calado.

⚠️ 🔬 **`tests/test_fase06_d3_dre_despesas_v2.py` cria contas `5.x` a cada
rodada** (`_garantir_conta`, `:92`) e existe justamente para provar que
`6.1.01.001` e `5.1.01.001` coexistem (`:154`). Depois deste Step ele **tem de
mudar junto** — é a prova viva do comportamento que esta task remove.

🔬 **O banco de dev não ajuda a decidir nada disto, e isso está medido:** dos
**8.606** tenants com plano de contas, **8.520** têm grupo 6 e só **211** têm
qualquer conta `5.x` — e os 211 são **resíduo de suíte**
(`d3_*@test.local`, do teste acima). Os três códigos que carregam partida em
dev são `5.1.01.001` ('Salários', 42 partidas), `5.1.03.001` (**'CMV'** no
banco, mas *'Aluguel de Equipamentos'* em `financeiro_seeds.py:85`) e
`5.2.01.001` ('Despesa financeira', **que não existe em seeder nenhum**).
🔴 **Prova por que o `(codigo, nome)` da versão de 24/08 teria falhado
também:** o nome no banco não bate com o nome do seeder.

- [ ] **Step 1: O classificador de assinatura, em `contabilidade_utils.py`**

⚠️ **Ele aceita `conn=None` de propósito.** A migration roda dentro de
`db.engine.begin()`; chamar ORM/`db.session` lá dentro abriria uma **segunda**
transação e a contagem "antes/depois" deixaria de valer. Com `conn`, o
classificador enxerga o mesmo estado que a migration está escrevendo.

```python
# contabilidade_utils.py
class AssinaturaDesconhecida(Exception):
    """O plano de contas do tenant tem contas 5.x e nao casa com nenhum dos
    dois seeders aposentados. A migracao PARA e NOMEIA o tenant — nunca chuta.
    """


def classificar_assinatura(admin_id, conn=None):
    """Descobre QUAL seeder criou o plano de contas deste tenant, pela FORMA.

    Quatro saidas, e a terceira e' a maioria do parque:

      'contabilidade_utils' — seeder aposentado nº1 (5.1.01 'Materiais
                              Diretos', analitica)
      'financeiro_seeds'    — seeder aposentado nº2 (5.1.01 'MAO DE OBRA',
                              sintetica, com filhos 5.1.01.00x)
      'sem_5x'              — nenhuma conta 5.x: canonico (_V2_CONTAS_SEED) ou
                              demo (seed_demo_alfa). O de-para e' NO-OP.
      AssinaturaDesconhecida — tem 5.x e nao casa nenhum dos dois.

    🔬 NENHUM sinal le `nome` — a proibicao da spec ("os nomes sao justamente o
    que esta inconsistente") e' preservada por construcao.

    🔴 Sinais deliberadamente NAO usados, e por que (medidos em 04/09 contra os
    QUATRO planos concorrentes, nao contra dois):
      - "existe grupo 6": o CANONICO tem 10 contas 6.*. Rotularia de legado
        quase todo tenant sao.
      - "4.1.01.%" e "2.1.03.001": existem tambem no canonico, e o demo Alfa
        (scripts/seed_demo_alfa.py, raizes invertidas 3=receita/4=despesa) tem
        4.1.01 E 4.1.02 ao mesmo tempo.
    """
    from sqlalchemy import text as sa_text

    def _scalar(sql, params):
        if conn is not None:
            return conn.execute(sa_text(sql), params).scalar()
        return db.session.execute(sa_text(sql), params).scalar()

    tem_5x = _scalar(
        "SELECT count(*) FROM plano_contas "
        "WHERE admin_id = :a AND codigo LIKE '5%'", {'a': admin_id})
    if not tem_5x:
        return 'sem_5x'

    # Sinal limpo de nº2: 5.1.01 tem FILHOS (5.1.01.001-004). O nº1 tem so' a
    # folha 5.1.01; o canonico e o demo nao tem 5.x nenhuma.
    filhos_5_1_01 = _scalar(
        "SELECT count(*) FROM plano_contas "
        "WHERE admin_id = :a AND codigo LIKE '5.1.01.%'", {'a': admin_id})
    # Sinal limpo e' o mais direto: 5.1.01 e' analitica no nº1, sintetica no nº2.
    aceita_5_1_01 = _scalar(
        "SELECT aceita_lancamento FROM plano_contas "
        "WHERE admin_id = :a AND codigo = '5.1.01'", {'a': admin_id})
    # Sinais limpos de nº1, exclusivos entre os quatro.
    marcas_n1 = _scalar(
        "SELECT count(*) FROM plano_contas WHERE admin_id = :a AND ("
        "  codigo = '5.2.01' OR codigo LIKE '4.1.02.%' "
        "  OR codigo IN ('2.1.03.007', '2.1.03.008', '2.1.03.009'))",
        {'a': admin_id})

    if filhos_5_1_01 or aceita_5_1_01 is False:
        return 'financeiro_seeds'
    if aceita_5_1_01 is True or marcas_n1:
        return 'contabilidade_utils'

    raise AssinaturaDesconhecida(
        f'tenant admin_id={admin_id} tem contas 5.x e nao casa com nenhum dos '
        'dois seeders aposentados. A migracao PARA aqui: acrescente a '
        'assinatura em contabilidade_utils.classificar_assinatura e o destino '
        'em services/plano_contas_depara.py, ou migre este tenant a mao.')
```

- [ ] **Step 2: Escrever o de-para como dado revisável**

```python
# services/plano_contas_depara.py
"""De-para das contas 5.x para o canônico (Fase 8, Task 4).

Chaveado em (ASSINATURA, codigo) — decisão D6, respondida em 01/09. Os dois
seeders aposentados TROCAM o significado de 5.1.01 e 5.1.02 entre si:

    5.1.01 = 'Materiais Diretos' (contabilidade_utils)
    5.1.01 = 'MÃO DE OBRA'       (financeiro_seeds)

Um de-para por código mandaria material para pessoal em metade do parque,
e o erro seria SILENCIOSO — a partida migraria sem falhar.

Por que (assinatura, codigo) e NÃO (codigo, nome): o nome é o dado que a
spec proíbe usar, porque é justamente o que está inconsistente. A
assinatura é descoberta pela FORMA do plano de contas
(contabilidade_utils.classificar_assinatura), sem ler nome nenhum.

Código sem destino na assinatura do tenant => a migration FALHA e nomeia
o par. Nunca chuta.
"""

DEPARA_5X: dict[tuple[str, str], str] = {
    # --- assinatura 'contabilidade_utils' (seeder nº1, 3 analíticas em 5.x) ---
    ('contabilidade_utils', '5.1.01'): '6.1.02.003',  # Materiais Diretos -> Despesa com Material
    ('contabilidade_utils', '5.1.02'): '6.1.01.001',  # Mão de Obra Direta -> Despesa com Salários
    ('contabilidade_utils', '5.2.01'): '6.1.02.003',  # Materiais Indiretos -> Despesa com Material
    # --- assinatura 'financeiro_seeds' (seeder nº2, 16 analíticas) ---
    ('financeiro_seeds', '5.1.01.001'): '6.1.01.001',  # Salários
    ('financeiro_seeds', '5.1.01.002'): '6.1.01.001',  # Encargos Sociais
    ('financeiro_seeds', '5.1.01.003'): '6.1.02.002',  # Vale Transporte -> Despesa com Transporte
    ('financeiro_seeds', '5.1.01.004'): '6.1.01.002',  # Vale Alimentação -> Despesa com Alimentação
    ('financeiro_seeds', '5.1.02.001'): '6.1.02.003',  # Material de Construção
    ('financeiro_seeds', '5.1.02.002'): '6.1.02.003',  # Ferramentas
    ('financeiro_seeds', '5.1.02.003'): '6.1.02.003',  # EPIs
    ('financeiro_seeds', '5.1.03.001'): '6.1.02.003',  # Aluguel de Equipamentos
    ('financeiro_seeds', '5.1.03.002'): '6.1.02.003',  # Manutenção de Equipamentos
    ('financeiro_seeds', '5.1.04.001'): '6.1.02.001',  # Combustível
    ('financeiro_seeds', '5.1.04.002'): '6.1.02.001',  # Manutenção de Veículos
    ('financeiro_seeds', '5.1.04.003'): '6.1.02.001',  # IPVA e Licenciamento
    ('financeiro_seeds', '5.1.05.001'): '6.1.02.003',  # Material de Escritório
    ('financeiro_seeds', '5.1.05.002'): '6.1.02.003',  # Telefone e Internet
    ('financeiro_seeds', '5.1.05.003'): '6.1.02.003',  # Energia Elétrica
    ('financeiro_seeds', '5.1.05.004'): '6.1.02.003',  # Água e Esgoto
}

# Derivado, nunca escrito à mão: os códigos 5.x que este de-para conhece.
CONTAS_5X_CONHECIDAS: set[str] = {codigo for (_ass, codigo) in DEPARA_5X}
```

⚠️ **Este arquivo é para o Cássio revisar linha a linha antes de a migration rodar.** Os destinos acima são a recomendação do executor, não decisão tomada: `Ferramentas`, `EPIs` e `Aluguel de Equipamentos` caindo todos em `Despesa com Material` é a escolha mais discutível da tabela.

🔴 **O `CONTAS_5X_SINTETICAS` da versão anterior foi REMOVIDO, não renomeado.**
🔬 Ele listava `5.1.01` e `5.1.02` como sintéticas, mas no seeder nº1 as duas são
`aceita_lancamento=True` — analíticas, e **são justamente as que carregam
partida**. Um conjunto que mente reprova errado no primeiro `assert` que o use.
O passo 4 da migration cobre sintéticas e analíticas pelo mesmo `NOT EXISTS` e
não precisa dele.

- [ ] **Step 3: Escrever os testes que falham**

```python
# tests/test_fase8_depara_5x.py
"""O de-para não pode perder nem somar partida, tem de FALHAR ruidosamente
diante de um código que não conhece, e tem de NOMEAR quem o fez parar."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db  # noqa: E402


def test_depara_preserva_a_contagem_e_a_soma():
    from sqlalchemy import text
    from migrations import _migration_324_depara_contas_5x
    with app.app_context():
        admin_id = _tenant_com_partidas_em_5x()   # helper do próprio arquivo
        antes_n = db.session.execute(text(
            'SELECT count(*) FROM partida_contabil WHERE admin_id=:a'),
            {'a': admin_id}).scalar()
        antes_soma = db.session.execute(text(
            'SELECT coalesce(sum(valor),0) FROM partida_contabil WHERE admin_id=:a'),
            {'a': admin_id}).scalar()

        assert _migration_324_depara_contas_5x() is True

        depois_n = db.session.execute(text(
            'SELECT count(*) FROM partida_contabil WHERE admin_id=:a'),
            {'a': admin_id}).scalar()
        depois_soma = db.session.execute(text(
            'SELECT coalesce(sum(valor),0) FROM partida_contabil WHERE admin_id=:a'),
            {'a': admin_id}).scalar()
        restantes = db.session.execute(text(
            "SELECT count(*) FROM partida_contabil "
            "WHERE admin_id=:a AND conta_codigo LIKE '5.%'"),
            {'a': admin_id}).scalar()

        assert depois_n == antes_n, 'partida sumiu ou foi duplicada'
        assert depois_soma == antes_soma, 'a soma mudou — valor foi somado 2x'
        assert restantes == 0, 'sobrou partida em 5.x depois do de-para'


def test_5_1_01_vai_para_destinos_OPOSTOS_conforme_a_assinatura():
    """O coração da D6: o MESMO código migra para contas diferentes.

    Em 'contabilidade_utils', 5.1.01 é Materiais Diretos -> 6.1.02.003.
    Em 'financeiro_seeds', 5.1.01.001 é Salários -> 6.1.01.001.
    Se este teste passar com um de-para chaveado só por código, o de-para
    está errado e o teste é que não presta.
    """
    from services.plano_contas_depara import DEPARA_5X
    assert DEPARA_5X[('contabilidade_utils', '5.1.01')] == '6.1.02.003'
    assert DEPARA_5X[('financeiro_seeds', '5.1.01.001')] == '6.1.01.001'


def test_tenant_canonico_e_no_op_e_nao_para_a_migracao():
    """O canônico (_V2_CONTAS_SEED) e o demo Alfa não têm 5.x.

    🔴 Este teste é a guarda contra o defeito que derrubaria o parque inteiro:
    o demo Alfa roda no auto-seed de TODO boot (app.py:618). Se ele caísse em
    AssinaturaDesconhecida, a migration falharia em todo dev e todo CI.
    """
    from contabilidade_utils import classificar_assinatura
    with app.app_context():
        admin_id = _tenant_canonico_sem_5x()   # helper do próprio arquivo
        assert classificar_assinatura(admin_id) == 'sem_5x'


def test_codigo_sem_destino_faz_a_migration_falhar_e_nomear():
    from sqlalchemy import text
    from migrations import _migration_324_depara_contas_5x
    with app.app_context():
        admin_id = _tenant_com_partida_em_codigo_desconhecido('5.9.99')
        assert _migration_324_depara_contas_5x() is False, (
            'código sem destino tem de FALHAR — ficar failed e retentar a '
            'cada boot é o comportamento certo (a lição da 279/309)')
        sobrou = db.session.execute(text(
            "SELECT count(*) FROM partida_contabil "
            "WHERE admin_id=:a AND conta_codigo='5.9.99'"),
            {'a': admin_id}).scalar()
        assert sobrou == 1, 'a migration falhou mas mexeu no dado assim mesmo'


def test_partida_ORFA_e_nomeada_e_nao_apenas_contada():
    """🔴 O ramo que a versão de 24/08 não cobria.

    Partida em 5.x cujo conta_codigo NÃO tem linha em plano_contas some do
    JOIN, não migra, e o passo final estourava com 'N partidas continuam em
    5.x' — sem dizer QUAL tenant nem QUAL código. 'Falha fechada e nomeada'
    exige o nome.
    """
    from migrations import _migration_324_depara_contas_5x
    with app.app_context():
        admin_id = _tenant_com_partida_orfa('5.3.01')   # sem linha em plano_contas
        assert _migration_324_depara_contas_5x() is False
        # o nome do tenant e o código têm de aparecer no log/na exceção
        assert str(admin_id) in _ultima_mensagem_de_erro()
        assert '5.3.01' in _ultima_mensagem_de_erro()


def test_conta_5x_sem_partida_e_desativada_e_nao_apagada():
    from models import PlanoContas
    from migrations import _migration_324_depara_contas_5x
    with app.app_context():
        admin_id = _tenant_com_5x_sem_partida()
        _migration_324_depara_contas_5x()
        conta = PlanoContas.query.filter_by(
            admin_id=admin_id, codigo='5.1.03').first()
        assert conta is not None, (
            'conta de plano de contas NUNCA é apagada — relatório histórico '
            'aponta para ela')
        assert conta.ativo is False
```

⚠️ **Os helpers `_tenant_*` e `_ultima_mensagem_de_erro` são do próprio arquivo e
precisam ser escritos.** Ao montar `PlanoContas(...)`, 📖 `natureza` e `nivel` são
**`NOT NULL`** (`models.py:3276-3277`) e a PK é composta **`(admin_id, codigo)`**
(`:3271-3273`); o campo do tipo chama-se **`tipo_conta`**, não `tipo` (`:3275`).
Um campo faltando faz o teste falhar por `IntegrityError` — pelo motivo errado, o
defeito que este plano vem contando desde a Onda 2.

- [ ] **Step 4: Rodar e ver falhar**

Run: `.pythonlibs/bin/pytest tests/test_fase8_depara_5x.py -v`
Expected: FAIL com `ImportError: cannot import name '_migration_324_depara_contas_5x'`.

- [ ] **Step 5: A migration 324**

```python
# migrations.py
def _migration_324_depara_contas_5x():
    """Fase 8 / Task 4 — reescreve partida_contabil.conta_codigo das 5.x
    para o canônico, e desativa as 5.x sem partida.

    TRANSAÇÃO ÚNICA com contagem antes e depois. A lição da migração 218
    (Fase 0.6) vale aqui: numa troca de significado, a ordem dos atos decide
    se o backfill é real ou no-op silencioso.

    Chaveia em (ASSINATURA, codigo) — D6 respondida em 01/09. A assinatura sai
    de contabilidade_utils.classificar_assinatura, que le a FORMA do plano de
    contas e nunca o `nome`. Tenant sem 5.x e' no-op. Tenant com 5.x que nao
    casa nenhuma assinatura => FALHA e NOMEIA o tenant.

    Ficar 'failed' e retentar a cada boot é o comportamento certo; é o que a
    279 deveria ter feito e não fez (lição da 309).

    Nenhuma partida é apagada ou somada. Nenhuma conta é apagada.
    """
    from sqlalchemy import text as sa_text

    from contabilidade_utils import (AssinaturaDesconhecida,
                                     classificar_assinatura)
    from services.plano_contas_depara import DEPARA_5X
    try:
        with db.engine.begin() as conn:
            antes = conn.execute(sa_text(
                'SELECT count(*), coalesce(sum(valor),0) FROM partida_contabil'
            )).one()

            # 0. PARTIDA ORFA: 5.x sem linha em plano_contas. Ela sumiria do
            #    JOIN e o erro final nao diria de quem e'. Nomeia AQUI.
            orfas = conn.execute(sa_text("""
                SELECT DISTINCT p.admin_id, p.conta_codigo
                  FROM partida_contabil p
                 WHERE p.conta_codigo LIKE '5.%'
                   AND NOT EXISTS (SELECT 1 FROM plano_contas c
                                    WHERE c.admin_id = p.admin_id
                                      AND c.codigo = p.conta_codigo)
            """)).fetchall()
            if orfas:
                raise RuntimeError(
                    'partidas ORFAS em 5.x (o codigo nao existe no plano de '
                    'contas do tenant) — (admin_id, conta_codigo): '
                    f'{sorted((a, c) for (a, c) in orfas)}. A migracao nao '
                    'chuta destino para conta que nem existe.')

            # 1. Uma assinatura por tenant que tem partida em 5.x.
            tenants = [r[0] for r in conn.execute(sa_text("""
                SELECT DISTINCT admin_id FROM partida_contabil
                 WHERE conta_codigo LIKE '5.%'
            """)).fetchall()]
            assinatura_de = {}
            for aid in tenants:
                # conn=conn: o classificador tem de enxergar ESTA transacao.
                assinatura_de[aid] = classificar_assinatura(aid, conn=conn)

            # 2. Todo (assinatura, codigo) com partida viva precisa de destino.
            pares = conn.execute(sa_text("""
                SELECT DISTINCT p.admin_id, p.conta_codigo
                  FROM partida_contabil p
                 WHERE p.conta_codigo LIKE '5.%'
            """)).fetchall()
            sem_destino = sorted({
                (assinatura_de[aid], cod) for (aid, cod) in pares
                if (assinatura_de[aid], cod) not in DEPARA_5X})
            if sem_destino:
                raise RuntimeError(
                    'de-para incompleto — pares (assinatura, codigo) SEM '
                    f'destino: {sem_destino}. A migração não chuta: '
                    'acrescente o destino em services/plano_contas_depara.py '
                    'e deixe esta migração retentar no próximo boot.')

            # 3. Reescreve, tenant a tenant, dentro da MESMA transação.
            for (aid, cod) in pares:
                conn.execute(sa_text("""
                    UPDATE partida_contabil SET conta_codigo = :destino
                     WHERE admin_id = :aid AND conta_codigo = :cod
                """), {'destino': DEPARA_5X[(assinatura_de[aid], cod)],
                       'aid': aid, 'cod': cod})

            # 4. Contagem e soma têm de bater. Se não baterem, tudo volta.
            depois = conn.execute(sa_text(
                'SELECT count(*), coalesce(sum(valor),0) FROM partida_contabil'
            )).one()
            if (antes[0], antes[1]) != (depois[0], depois[1]):
                raise RuntimeError(
                    f'contagem/soma mudaram no de-para: {antes} -> {depois}')

            # 5. 5.x sem partida: desativa. NUNCA apaga.
            conn.execute(sa_text("""
                UPDATE plano_contas c SET ativo = false
                 WHERE c.codigo LIKE '5.%'
                   AND NOT EXISTS (SELECT 1 FROM partida_contabil p
                                    WHERE p.admin_id = c.admin_id
                                      AND p.conta_codigo = c.codigo)
            """))
            sobraram = conn.execute(sa_text(
                "SELECT count(*) FROM partida_contabil "
                "WHERE conta_codigo LIKE '5.%'")).scalar()
            if sobraram:
                raise RuntimeError(
                    f'{sobraram} partidas continuam em 5.x depois do de-para')

        logger.info(f'[Migration 324] de-para 5.x concluído; {len(pares)} '
                    f'pares migrados em {len(tenants)} tenants, contagem e '
                    f'soma conferidas: {antes}.')
        return True
    except AssinaturaDesconhecida as e:
        logger.error(f'[Migration 324] Falha (nada foi gravado): {e}',
                     exc_info=True)
        return False
    except Exception as e:
        logger.error(f'[Migration 324] Falha (nada foi gravado): {e}',
                     exc_info=True)
        return False
```

⚠️ O `except AssinaturaDesconhecida` separado existe para o **log dizer o
motivo certo**, não para tratar diferente: os dois devolvem `False` e não
gravam nada. Se o `ruff` reclamar dos dois ramos idênticos, funda-os em
`except (AssinaturaDesconhecida, Exception)` — **mas mantenha a mensagem da
exceção no log**, que é quem nomeia o tenant.

Registre **na ordem**, depois da 323:

```python
            (324, "Fase 8 — de-para das contas 5.x para o canonico, chaveado por (assinatura, codigo) via classificar_assinatura; partida orfa e assinatura desconhecida PARAM e nomeiam; 5.x sem partida desativada", _migration_324_depara_contas_5x),
```

- [ ] **Step 6: Rodar, ver passar, provar idempotente**

```bash
.pythonlibs/bin/pytest tests/test_fase8_depara_5x.py -v
.pythonlibs/bin/python -c "from app import app; from migrations import _migration_324_depara_contas_5x as m; app.app_context().push(); print(m(), m())"
```
Expected: PASS nos seis; `True True` na dupla execução (a segunda não acha par nenhum e é no-op).

- [ ] **Step 7: Commit**

```bash
git add services/plano_contas_depara.py contabilidade_utils.py event_manager.py migrations.py tests/test_fase8_depara_5x.py tests/test_fase06_d3_dre_despesas_v2.py
git commit -m "feat(fase8): de-para das 5.x por assinatura estrutural — migration 324, e os leitores/escritores vivos de 5.x remapeados no mesmo commit"
```

---

### Task 5 — o seed de classificação e a tela de edição por tenant

**Files:**
- Create: `services/classificacao_gasto.py`
- Create: `templates/contabilidade/classificacao_contas.html`
- Modify: `contabilidade_views.py` (rotas `GET/POST /contabilidade/classificacao-contas`)
- Test: `tests/test_fase8_classificacao.py`

**Interfaces:**
- Produces:
  - `SEED_CLASSIFICACAO: dict[str, tuple[str, str]]` — `codigo -> (classificacao_gasto, atividade_dfc)`
  - `aplicar_seed_classificacao(admin_id: int) -> int` — devolve quantas contas classificou; **só toca conta em `nao_classificado`**, nunca sobrescreve escolha do tenant.

- [ ] **Step 1: O seed das 36 canônicas**

🔬 São **36**, não 28 (a spec envelheceu) nem 35 (esta era a conta de 24/08, e ela esquecia `6.1.02.009`). Ativo, passivo, PL e receita levam `nao_aplicavel` — sem isso, "conta sem classificação" misturaria o que falta classificar com o que nunca será.

```python
# services/classificacao_gasto.py
"""Seed de classificacao_gasto × atividade_dfc para o plano canônico.

Só classifica conta que está em `nao_classificado`: escolha de tenant
nunca é sobrescrita por seed. O padrão erra para `nao_classificado` onde
não há consenso óbvio (D3) — o que não pode é o sistema decidir por conta
própria e o empresário descobrir depois que a margem dele saiu de uma
premissa que ele não viu.
"""
from models import PlanoContas as _PC

_FIXO, _VAR = _PC.CLASSIFICACAO_FIXO, _PC.CLASSIFICACAO_VARIAVEL
_NA, _NC = _PC.CLASSIFICACAO_NAO_APLICAVEL, _PC.CLASSIFICACAO_NAO_CLASSIFICADO
_OP, _INV, _FIN = _PC.DFC_OPERACIONAL, _PC.DFC_INVESTIMENTO, _PC.DFC_FINANCIAMENTO

SEED_CLASSIFICACAO: dict[str, tuple[str, str]] = {
    # Ativo, passivo, PL e receita: nao_aplicavel no gasto.
    '1': (_NA, _OP), '1.1': (_NA, _OP), '1.1.01': (_NA, _OP),
    '1.1.02': (_NA, _OP), '1.1.03': (_NA, _OP),
    '1.1.01.001': (_NA, _OP), '1.1.01.002': (_NA, _OP),
    '1.1.02.001': (_NA, _OP), '1.1.03.001': (_NA, _OP),
    '2': (_NA, _OP), '2.1': (_NA, _OP), '2.1.01': (_NA, _OP),
    '2.1.02': (_NA, _OP), '2.1.03': (_NA, _OP),
    '2.1.01.001': (_NA, _OP), '2.1.02.001': (_NA, _OP),
    '2.1.02.002': (_NA, _OP), '2.1.02.003': (_NA, _OP),
    '2.1.03.001': (_NA, _OP),
    '4': (_NA, _OP), '4.1': (_NA, _OP), '4.2': (_NA, _OP),
    '4.1.01': (_NA, _OP), '4.2.01': (_NA, _OP),
    '4.1.01.001': (_NA, _OP), '4.2.01.001': (_NA, _OP),
    # Despesas: aqui a classificação significa alguma coisa.
    '6': (_NC, _OP), '6.1': (_NC, _OP),
    '6.1.01': (_NC, _OP), '6.1.02': (_NC, _OP),
    # Salários e alimentação de equipe de obra: VARIÁVEIS numa construtora
    # que dimensiona equipe por obra. Tenant que mantém equipe fixa muda na
    # tela — é exatamente o caso que motivou a coluna ser por tenant.
    '6.1.01.001': (_VAR, _OP),
    '6.1.01.002': (_VAR, _OP),
    # Combustível e transporte acompanham a obra.
    '6.1.02.001': (_VAR, _OP),
    '6.1.02.002': (_VAR, _OP),
    '6.1.02.003': (_VAR, _OP),
    # 🔴 A 36a, achada no pre-voo de 04/09: a versao de 24/08 listava 35 e
    # esquecia esta. Ela e' alvo VIVO de escrita — 📖 contabilidade_utils.py:1545,
    # MAPEAMENTO_CONTABIL['despesa_geral'] = {'debito': '6.1.02.009', ...}.
    # Sem ela, uma conta canonica que RECEBE partida fica 'nao_classificado'
    # para sempre, e o valor dela mora na linha "nao classificado" do DRE
    # gerencial de todo tenant.
    '6.1.02.009': (_VAR, _OP),   # Despesas Gerais Diversas
}


def aplicar_seed_classificacao(admin_id: int) -> int:
    """Classifica as contas canônicas AINDA não classificadas do tenant.

    Devolve quantas mudaram. Não commita — quem chama decide a transação.
    """
    from app import db
    alteradas = 0
    contas = (_PC.query
              .filter_by(admin_id=admin_id)
              .filter(_PC.classificacao_gasto == _NC)
              .all())
    for conta in contas:
        par = SEED_CLASSIFICACAO.get(conta.codigo)
        if par is None:
            continue          # conta avulsa do tenant: fica nao_classificado
        conta.classificacao_gasto, conta.atividade_dfc = par
        alteradas += 1
    return alteradas
```

- [ ] **Step 2: O teste que falha**

```python
# tests/test_fase8_classificacao.py
def test_seed_classifica_canonicas_e_nao_toca_escolha_do_tenant():
    from models import PlanoContas
    from services.classificacao_gasto import aplicar_seed_classificacao
    with app.app_context():
        admin_id = _admin_com_plano_canonico()
        combustivel = PlanoContas.query.filter_by(
            admin_id=admin_id, codigo='6.1.02.001').first()
        combustivel.classificacao_gasto = PlanoContas.CLASSIFICACAO_FIXO
        db.session.flush()

        aplicar_seed_classificacao(admin_id)
        db.session.flush()

        salarios = PlanoContas.query.filter_by(
            admin_id=admin_id, codigo='6.1.01.001').first()
        assert salarios.classificacao_gasto == PlanoContas.CLASSIFICACAO_VARIAVEL
        assert combustivel.classificacao_gasto == PlanoContas.CLASSIFICACAO_FIXO, (
            'o seed sobrescreveu a escolha do tenant — a coluna existe '
            'justamente porque empresas classificam o mesmo gasto de formas '
            'diferentes e legítimas')


def test_conta_avulsa_do_tenant_fica_nao_classificada_e_aparece_na_tela():
    from models import PlanoContas
    from services.classificacao_gasto import aplicar_seed_classificacao
    with app.app_context():
        admin_id = _admin_com_plano_canonico()
        db.session.add(PlanoContas(
            codigo='6.1.02.900', nome='Conta avulsa do cliente',
            tipo_conta='DESPESA', natureza='DEVEDORA', nivel=4,
            aceita_lancamento=True, ativo=True, admin_id=admin_id))
        db.session.flush()
        aplicar_seed_classificacao(admin_id)
        db.session.flush()
        avulsa = PlanoContas.query.filter_by(
            admin_id=admin_id, codigo='6.1.02.900').first()
        assert avulsa.classificacao_gasto == PlanoContas.CLASSIFICACAO_NAO_CLASSIFICADO
```

- [ ] **Step 3: Rodar e ver falhar** — `ModuleNotFoundError: services.classificacao_gasto`.

- [ ] **Step 4: A tela, no molde de `/configuracoes/alcadas`**

Rota `GET` lista as contas do tenant com dois `<select>` por linha (`classificacao_gasto`, `atividade_dfc`), ordenadas por código, com as `nao_classificado` **no topo** e um contador "N de M contas classificadas". `POST` grava o que mudou e volta com flash. Autorização: o mesmo decorador que `/configuracoes/alcadas` usa — **não invente um novo**; leia `contabilidade_views.py` e copie o padrão vizinho.

- [ ] **Step 5: Rodar e ver passar** — os dois testes verdes.

- [ ] **Step 6: Commit**

```bash
git add services/classificacao_gasto.py templates/contabilidade/classificacao_contas.html contabilidade_views.py tests/test_fase8_classificacao.py
git commit -m "feat(fase8): seed de classificacao das 36 canonicas + tela de edicao por tenant"
```

---

### Task 6 — DRE Gerencial com margem de contribuição

**Files:**
- Modify: `contabilidade_utils.py` (nova `calcular_dre_gerencial`, ao lado de `calcular_dre_mensal`)
- Modify: `templates/contabilidade/` (a tela do DRE ganha o bloco gerencial)
- Test: `tests/test_fase8_margem_contribuicao.py`

**Interfaces:**
- Produces: `calcular_dre_gerencial(admin_id, data_inicio, data_fim) -> dict` com as chaves `receita_liquida`, `custos_variaveis`, `margem_contribuicao`, `margem_percentual`, `custos_fixos`, `resultado`, `nao_classificado`, `tem_base`.

- [ ] **Step 1: O teste que falha, com um caso conferido na calculadora**

```python
# tests/test_fase8_margem_contribuicao.py
def test_margem_de_contribuicao_de_um_caso_montado_a_mao():
    """Receita 100.000, variáveis 60.000, fixos 25.000.
    Margem = 40.000 (40%); resultado = 15.000."""
    from contabilidade_utils import calcular_dre_gerencial
    with app.app_context():
        admin_id = _tenant_com_lancamentos(receita=100000, variavel=60000,
                                           fixo=25000)
        dre = calcular_dre_gerencial(admin_id, date(2026, 8, 1), date(2026, 8, 31))
        assert float(dre['margem_contribuicao']) == pytest.approx(40000.0)
        assert float(dre['margem_percentual']) == pytest.approx(40.0)
        assert float(dre['resultado']) == pytest.approx(15000.0)


def test_nao_classificado_aparece_em_linha_propria_com_o_valor():
    from contabilidade_utils import calcular_dre_gerencial
    with app.app_context():
        admin_id = _tenant_com_lancamentos(receita=100000, variavel=60000,
                                           fixo=25000, nao_classificado=5000)
        dre = calcular_dre_gerencial(admin_id, date(2026, 8, 1), date(2026, 8, 31))
        assert float(dre['nao_classificado']) == pytest.approx(5000.0), (
            'relatório que esconde o que não sabe classificar é relatório '
            'que mente devagar')


def test_sem_receita_no_periodo_a_margem_e_sem_base_e_nao_zero_por_cento():
    from contabilidade_utils import calcular_dre_gerencial
    with app.app_context():
        admin_id = _tenant_com_lancamentos(receita=0, variavel=1000, fixo=0)
        dre = calcular_dre_gerencial(admin_id, date(2026, 8, 1), date(2026, 8, 31))
        assert dre['tem_base'] is False
        assert dre['margem_percentual'] is None, (
            '0% diria "a empresa não tem margem"; a verdade é "não há base '
            'para calcular"')


def test_mutacao_classificar_tudo_como_fixo_mata_o_teste_da_margem():
    """Guarda de mutação: se a margem ignorasse classificacao_gasto, este
    teste passaria junto com o primeiro. Ele tem de DIVERGIR."""
    from contabilidade_utils import calcular_dre_gerencial
    from models import PlanoContas
    with app.app_context():
        admin_id = _tenant_com_lancamentos(receita=100000, variavel=60000,
                                           fixo=25000)
        PlanoContas.query.filter_by(admin_id=admin_id).update(
            {'classificacao_gasto': PlanoContas.CLASSIFICACAO_FIXO})
        db.session.flush()
        dre = calcular_dre_gerencial(admin_id, date(2026, 8, 1), date(2026, 8, 31))
        assert float(dre['margem_contribuicao']) == pytest.approx(100000.0), (
            'com tudo fixo não há custo variável: a margem tem de ser a '
            'receita inteira. Se este número continuar 40.000, a margem não '
            'está lendo classificacao_gasto')
```

- [ ] **Step 2: Rodar e ver falhar** — `ImportError: cannot import name 'calcular_dre_gerencial'`.

- [ ] **Step 3: Implementar** — agregue `PartidaContabil` por `classificacao_gasto` no período, via `JOIN plano_contas ON (codigo, admin_id)`. `margem_percentual` só existe se `receita_liquida > 0`; senão `None` e `tem_base = False`.

- [ ] **Step 4: Rodar e ver passar** — os quatro verdes, **incluindo o de mutação**.

- [ ] **Step 5: Commit**

```bash
git add contabilidade_utils.py templates/contabilidade tests/test_fase8_margem_contribuicao.py
git commit -m "feat(fase8): DRE gerencial — margem de contribuicao, com linha propria para o nao classificado"
```

---

### Task 7 — DFC pelos três grupos, método direto

**Files:**
- Create: `services/dfc_service.py`
- Create: `templates/contabilidade/dfc.html`
- Modify: `contabilidade_views.py` (rota `/contabilidade/dfc`)
- Test: `tests/test_fase8_dfc.py`

**Interfaces:**
- Produces: `montar_dfc(admin_id, data_inicio, data_fim) -> dict` com `operacional`, `investimento`, `financiamento`, `variacao_caixa`, `diferenca`, `fecha` (bool).

- [ ] **Step 1: O teste que falha — e ele soma os três e compara**

```python
# tests/test_fase8_dfc.py
def test_os_tres_grupos_somam_a_variacao_de_caixa():
    from services.dfc_service import montar_dfc
    with app.app_context():
        admin_id = _tenant_com_movimento_de_caixa()
        dfc = montar_dfc(admin_id, date(2026, 8, 1), date(2026, 8, 31))
        soma = (dfc['operacional'] + dfc['investimento'] + dfc['financiamento'])
        assert soma == pytest.approx(dfc['variacao_caixa'])
        assert dfc['fecha'] is True


def test_quando_nao_fecha_a_diferenca_e_mostrada_e_nao_escondida():
    from services.dfc_service import montar_dfc
    with app.app_context():
        admin_id = _tenant_com_partida_de_caixa_sem_contrapartida()
        dfc = montar_dfc(admin_id, date(2026, 8, 1), date(2026, 8, 31))
        assert dfc['fecha'] is False
        assert dfc['diferenca'] != 0, (
            'DFC que não fecha tem de MOSTRAR a diferença; esconder é o '
            'defeito que o residual "outras" do DRE já evitou uma vez')
```

- [ ] **Step 2: Rodar e ver falhar** — `ModuleNotFoundError: services.dfc_service`.

- [ ] **Step 3: Implementar pelo método direto**

Para cada lançamento que toca `1.1.01.x` ou `1.1.02.x`, a natureza do movimento vem da **outra perna** da partida — `plano_contas.atividade_dfc` da contrapartida. 🔬 `1.1.02.001` é a conta com mais partidas do sistema (3.061 em dev), então o dado existe e é o mais denso que temos. Lançamento de caixa **sem** contrapartida entra em `diferenca`, nunca é distribuído por rateio.

- [ ] **Step 4: Rodar e ver passar.**

- [ ] **Step 5: Commit**

```bash
git add services/dfc_service.py templates/contabilidade/dfc.html contabilidade_views.py tests/test_fase8_dfc.py
git commit -m "feat(fase8): DFC pelos tres grupos, metodo direto pela contrapartida; diferenca aparece na tela"
```

---

### Task 8 — indicadores e ciclos, cada um com procedência

**Files:**
- Create: `services/indicadores_service.py`
- Create: `templates/contabilidade/indicadores.html`
- Modify: `contabilidade_views.py` (rota `/contabilidade/indicadores`)
- Test: `tests/test_fase8_indicadores.py`

**Interfaces:**
- Produces: `calcular_indicadores(admin_id, data_base) -> list[dict]`, cada item com `nome`, `valor`, `data_base`, `contas` (lista dos códigos que o compõem), `tem_base` (bool).

| Grupo | Indicadores |
|---|---|
| Liquidez | corrente, seca |
| Estrutura | endividamento, imobilização do PL |
| Rentabilidade | margem líquida, ROE, giro do ativo |
| Ciclos | prazo médio de recebimento, de pagamento, ciclo financeiro |

- [ ] **Step 1: O teste que falha, um caso de valor conhecido por indicador**

```python
# tests/test_fase8_indicadores.py
def test_liquidez_corrente_de_um_caso_conhecido():
    """AC 200.000 / PC 80.000 = 2,5."""
    from services.indicadores_service import calcular_indicadores
    with app.app_context():
        admin_id = _tenant_com_balanco(ativo_circulante=200000,
                                       passivo_circulante=80000)
        por_nome = {i['nome']: i for i in
                    calcular_indicadores(admin_id, date(2026, 8, 31))}
        assert por_nome['liquidez_corrente']['valor'] == pytest.approx(2.5)


def test_divisao_por_zero_vira_sem_base_e_nunca_inf():
    from services.indicadores_service import calcular_indicadores
    with app.app_context():
        admin_id = _tenant_com_balanco(ativo_circulante=200000,
                                       passivo_circulante=0)
        por_nome = {i['nome']: i for i in
                    calcular_indicadores(admin_id, date(2026, 8, 31))}
        ind = por_nome['liquidez_corrente']
        assert ind['tem_base'] is False and ind['valor'] is None


def test_todo_indicador_carrega_data_base_e_as_contas_que_o_compoem():
    from services.indicadores_service import calcular_indicadores
    with app.app_context():
        admin_id = _tenant_com_balanco(ativo_circulante=200000,
                                       passivo_circulante=80000)
        for ind in calcular_indicadores(admin_id, date(2026, 8, 31)):
            assert ind['data_base'] == date(2026, 8, 31)
            assert ind['contas'], (
                f"{ind['nome']} sem procedência — indicador sem as contas que "
                'o compõem é o defeito de fabricação do ESTADO-ATUAL, agora '
                'em forma de número na tela')
```

- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar** — derivados do balanço e do DRE que já existem.
- [ ] **Step 4: Rodar e ver passar.**
- [ ] **Step 5: Commit**

```bash
git add services/indicadores_service.py templates/contabilidade/indicadores.html contabilidade_views.py tests/test_fase8_indicadores.py
git commit -m "feat(fase8): indicadores e ciclos, cada um com data-base e as contas que o compoem"
```

---

### Task 9 — exportação Domínio

**Depende da Task 4.** Exportar para a contabilidade externa um plano que significa duas coisas é exportar o defeito para fora de casa.

**Files:**
- Create: `services/exportacao_dominio.py`
- Modify: `contabilidade_views.py` (rota de download)
- Test: `tests/test_fase8_exportacao_dominio.py`

**Interfaces:**
- Produces: `exportar_dominio(admin_id, data_inicio, data_fim) -> str` — o conteúdo do arquivo no layout Domínio.

- [ ] **Step 1: 🔴 Confirmar o layout ANTES de escrever o teste.** O escopo é "inalterado" em relação ao plano original, mas o plano original é de julho e **não** traz o leiaute campo a campo. Antes de qualquer código: leia `docs/superpowers/plans/2026-07-21-fase-8-financeiro-avancado-dominio.md`, e se ele não fixar o leiaute, **pergunte ao Cássio qual versão do Domínio** o escritório contábil recebe. Escrever um exportador para um leiaute suposto é trabalho jogado fora.
- [ ] **Step 2: Teste que falha, com um lançamento de valor conhecido e o registro esperado byte a byte.**
- [ ] **Step 3: Rodar e ver falhar.**
- [ ] **Step 4: Implementar.**
- [ ] **Step 5: Rodar e ver passar.**
- [ ] **Step 6: Commit**

```bash
git add services/exportacao_dominio.py contabilidade_views.py tests/test_fase8_exportacao_dominio.py
git commit -m "feat(fase8): exportacao Dominio sobre o plano ja unificado"
```

---

### Task 10 — paridade, gate e fecho

**Este é o teste que impede a fase de reescrever o passado enquanto conserta o vocabulário.**

**Files:**
- Test: `tests/test_fase8_paridade.py`
- Modify: `ESTADO-ATUAL.md`

- [ ] **Step 1: O teste de paridade**

```python
# tests/test_fase8_paridade.py
def test_dre_e_balanco_nao_mudam_depois_da_fase_inteira():
    """Os números que JÁ existem não podem mudar. A fase conserta o
    vocabulário; o passado fica igual."""
    from contabilidade_utils import calcular_dre_mensal
    from migrations import (_migration_323_plano_contas_semantica,
                            _migration_324_depara_contas_5x)
    with app.app_context():
        admin_id = _tenant_com_historico_em_5x_e_6x()
        antes = calcular_dre_mensal(admin_id, 2026, 8)
        _migration_323_plano_contas_semantica()
        _migration_324_depara_contas_5x()
        depois = calcular_dre_mensal(admin_id, 2026, 8)
        assert antes['receita_bruta'] == depois['receita_bruta']
        assert antes['resultado_liquido'] == depois['resultado_liquido'], (
            'a fase mudou o resultado do passado — o de-para não é para '
            'corrigir números, é para corrigir significado')
```

⚠️ Se este teste falhar, **não conserte o teste**. Uma diferença aqui significa que o de-para mudou a que linha do DRE uma despesa pertence — o que pode ser legítimo (era esse o defeito) ou um erro de destino. Leve o caso ao Cássio com os dois DREs lado a lado antes de mexer em qualquer coisa.

- [ ] **Step 2: Gate completo sobre a árvore que vai ser integrada**

```bash
bash run_tests.sh --gate
```
Referência a bater: o gate do `main` do mesmo dia. Registre **passed / skipped / deselected / xfailed** e o tempo. Um gate verde só vale para a árvore em que rodou — se você mesclar o `main` depois, **rode de novo**.

- [ ] **Step 3: `ruff` medido contra a base da branch, com a MESMA config**

```bash
.pythonlibs/bin/ruff check <arquivos tocados>
```
A pergunta certa não é quantas violações existem, é **quantas você acrescentou**. Comparar configs diferentes dá número errado — já deu, na Fase 6.

⚠️ **O `ruff` NÃO mede a migration, e ela é o arquivo de maior risco desta fase.**
📖 `pyproject.toml:101` põe `migrations.py` em `extend-exclude`. Não é bloqueio e
não se conserta aqui (mexer no `extend-exclude` acenderia o repo inteiro); é uma
**expectativa a ajustar por escrito**: a 323 e a 324 são revisadas por leitura
humana e pela dupla execução do Step 4, nunca pelo linter.

- [ ] **Step 4: Dupla execução das duas migrations no banco de dev** — prova de idempotência por execução, não por leitura.

- [ ] **Step 5: `ESTADO-ATUAL.md`** — registre o fecho **e nomeie os resíduos**, em vez de dizer que ficou tudo redondo. Comece por estes, que já se sabe que vão sobrar: o leiaute Domínio se a Task 9 tiver sido cortada; as contas avulsas de tenant que continuam `nao_classificado` por desenho; e a D6, com o que foi decidido.

- [ ] **Step 6: Commit de fecho**

```bash
git add ESTADO-ATUAL.md tests/test_fase8_paridade.py
git commit -m "chore(fase8): fecho — plano de contas canonico, margem, DFC e indicadores"
```

---

## Self-review deste plano

**Cobertura da spec:** Task 1→T1 · Task 2→"Modelo de dados"+migration 310 (aqui 323) · Task 3→T2 · Task 4→T3+migration 311 (aqui 324) · Task 5→T4 (coluna, seed, tela) · Task 6→T4 (margem no DRE) · Task 7→T5 · Task 8→T6 · Task 9→T7 · Task 10→"Testes/Paridade". Todos os seis casos de borda da spec têm teste nomeado. D1, D2, D3, D4 e D5 estão respeitadas; a **D6 nasceu com este plano e foi ✅ RESPONDIDA em 01/09** (`2026-09-01-decisoes-respondidas.md` §D6) — assinatura estrutural, e a Task 4 foi reescrita em 04/09 para executá-la.

**Fora de escopo, e continua fora:** passos 4 e 5 do RFA, consolidação entre tenants, conversão de moeda, competência × caixa como opção de relatório, e a `NotaFiscal` legada × `nota_fiscal_pedido`.

**O que este plano NÃO resolve, e você deve saber antes de começar:**
1. ~~A **D6** bloqueia a Task 4.~~ ✅ **Respondida em 01/09** e a Task 4 reescrita em 04/09: o de-para chaveia por `(assinatura, codigo)`, a assinatura sai da FORMA do plano de contas, e o que não casa **para e é nomeado**. Continua verdade o núcleo do aviso: **o de-para nunca chuta**.
2. A **Task 1** é humana e ~~bloqueia~~ **virou PREMISSA DECLARADA em 02/09** (§FASE8-T1). Sem o número de produção, a D2 está sendo decidida com banco de dev — 99,9% resíduo de suíte. 🔴 **O que a ratifica:** rodar `scripts/medir_producao.py` quando houver acesso. **O que acontece se a premissa for falsa:** a migration PARA e nomeia o tenant; nenhuma partida é migrada para conta errada. O custo é uma rodada manual por tenant de terceira origem, **não dado corrompido**.
3. O **leiaute Domínio** da Task 9 não está fixado em lugar nenhum que eu tenha encontrado.
