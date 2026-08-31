# Fecho do Que Está Aberto — Implementation Plan

> **Estado em 2026-08-31:** 🟡 **EM EXECUÇÃO — 5 de 10 tasks fechadas.**
>
> | Task | Estado |
> |---|---|
> | 1 — as três decisões sobem para quem decide | ✅ `0b7abc49` `556f1bc3` — **aguardando decisão humana** (D6, VIGA-I, FASE8-T1) |
> | 2 — apagar `relatorios_financeiros_avancados.py` (D4) | ✅ `3d0873a4` `41b605d0` |
> | 3 — apagar as seis rotas mortas de veículos (D3) | ✅ `0b3f932c` `0d1a7c6d` |
> | 4 — Onda 2 (o tenant para de vazar) | ✅ nada a executar: já mergeada em `fed8f19b` (26/08); doc corrigido em `b13e23c9` |
> | 5 — `o-que-nao-persiste` (os cinco achados restantes) | ✅ 6/6 tasks, gate 2872/6 skipped |
> | 6 — Onda 6 (os testes prometidos) | ⬜ próxima |
> | 7 — Onda 4 (o relatório passa a funcionar) | ⬜ |
> | 8 — Resgate da Espinha Financeira (9 de 10 tasks) | ⬜ |
> | 9 — as oito issues de arquitetura viram plano | ⬜ |
> | 10 — o índice volta a valer, gate consolidado, merge da branch | ⬜ |
>
> ⚠️ **Este é um plano de SEQUENCIAMENTO.** Ele não reescreve as 47 tasks que
> já existem nos seis planos abertos — elas já estão escritas com TDD e RED
> citado nos seus planos de origem, e duplicá-las criaria uma segunda fonte de
> verdade que diverge na primeira correção. O que este plano faz é: **resolver
> as decisões travadas, ordenar a execução, definir o gate entre cada etapa, e
> integrar a branch.**
>
> Duas tasks (2 e 3) são exceção e trazem código próprio: são as duas remoções
> que estavam bloqueadas por decisão e agora foram decididas — pequenas,
> independentes e já pesquisadas na fonte.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para executar este plano task a task. Os passos usam checkbox (`- [ ]`) para acompanhamento.

**Goal:** Levar a zero a lista de trabalho em aberto do repositório — seis
planos, oito issues de arquitetura, quatro decisões humanas e uma branch de 30
commits não integrada — fechando cada item pela ordem que respeita suas
dependências, ou marcando explicitamente o que só uma pessoa pode destravar.

**Architecture:** O trabalho aberto não é uma fila; é um grafo com três
bloqueios reais. **(1)** A Onda 4 depende da Onda 2 — sua Task 2 *torna
exploitável* um furo que a Onda 2 fecha, então executá-la antes é abrir o furo
de propósito. **(2)** Duas tasks da Onda 4 estavam presas às decisões D3 e D4,
agora tomadas (apagar, nos dois casos) — e este plano as absorve como Tasks 2 e
3, porque são remoções pequenas e independentes que não precisam esperar o
resto da Onda 4. **(3)** Dois planos — Fase 8 e Resgate da Espinha Financeira —
tocam decisões que **nenhum executor pode tomar**: medir produção, o
significado de `5.1.01`/`5.1.02`, e a regra de verba/lucro do telhado viga I.
🔬 **Mas o bloqueio é PARCIAL, e conferir isso mudou o plano:** no Resgate da
Espinha só a **Task 8 de 10** depende da decisão — as outras nove são porte de
código já escrito e testado, e entram normalmente (Task 8 deste plano). Na
Fase 8 o bloqueio é mais fundo, porque o próprio plano avisa que **cortar entre
as Tasks 3 e 4 "deixa o parque em dois estados"** — e a Task 4 é a travada.
A Task 1 escala as três decisões; o que dá para executar sem elas, executa.

**Tech Stack:** Flask, SQLAlchemy 2.0.41, PostgreSQL, pytest, Jinja2.

**Spec:** `docs/auditoria/achados-code-review-2026-08-25.md` (achados de origem)
e os seis planos abertos listados na tabela de File Structure. O índice de
estado histórico é `docs/planos-em-aberto-2026-08-25.md` — 🔬 **conferido em
31/08: está desatualizado**, escrito contra `main` em `657326c4` e não menciona
a Onda 5, `a-porta-irma` nem `o-que-nao-persiste`. A Task 10 o substitui.

## Global Constraints

- **Gate:** `bash run_tests.sh --gate` (= `pytest tests/ -m "not browser"`).
- **Piso vigente, medido em 31/08 ao fim da Task 5 (`o-que-nao-persiste`):**
  **2872 passed, 6 skipped, 201 deselected, 2 xfailed, 0 failed** (46min44s).
  Toda task que fecha uma etapa roda o gate e compara contra este piso. (O piso
  anterior, da onda "A Porta Irmã", era 2854 passed / 6 skipped em 43min55s.)
- **O skipped nunca sobe.** 🔬 Em 28/08, 4 testes saíram do gate sem que nada
  sinalizasse, e isso só foi descoberto por acaso. Skip subindo é cobertura
  saindo sem aviso — se subir, pare e descubra por quê antes de seguir.
- **TDD sem exceção.** Teste primeiro, RED conferido e **citado no commit**,
  depois o código.
- **Nenhum teste prova por `inspect.getsource()`.** O que se afirma é olhado no
  banco, na resposta HTTP ou no `url_map`.
- ⚠️ **Um teste de guarda tem de reprovar também quando o próprio gatilho para
  de funcionar.** 🔬 Regra herdada da onda "A Porta Irmã", onde **três** dos
  testes propostos pelo plano passariam verdes sem nunca chegar ao código sob
  teste. Se o teste depende de um erro injetado, ele afirma primeiro que o erro
  ocorreu.
- **A branch de trabalho é `sdd/a-porta-irma`.** Decisão registrada: **merge só
  ao fim de tudo**, com gate consolidado (Task 10). Não abra branch por plano.
- **Recusar é não deixar rastro.** Todo `return 4xx` faz
  `db.session.rollback()` antes.
- **Arreio antes de arquivo novo.** 🔬 `tests/helpers_tenant.py` (`um_tenant`,
  `dois_tenants`, `cliente_de`) já existe. Use.

---

## 🔴 Decisões — o estado de cada uma

| # | Decisão | Estado | Consequência |
|---|---|---|---|
| **D3** | `views/vehicles.py`: apagar ou consertar as rotas mortas? | ✅ **APAGAR** (31/08) | Task 3 deste plano. Absorve a Task 5 da Onda 4 |
| **D4** | `relatorios_financeiros_avancados.py` tem dono? | ✅ **APAGAR** (31/08) | Task 2 deste plano. Absorve a Task 4 da Onda 4 |
| **D5** | O aditivo: garantia própria ou ligar `escopo_obra_ativo`? | ✅ **GARANTIA PRÓPRIA** (28/08) | Já executada na onda "A Porta Irmã" (`da778eba`) |
| **D6** | O de-para do plano de contas pode ser chaveado só por código? | 🔴 **ABERTA — bloqueia a Task 4 da Fase 8** | Task 1: escalar. 🔬 E a Task 3 não pode ir sem a 4 — o plano avisa que cortar ali deixa o parque em dois estados |
| **VIGA-I** | A regra de verba/lucro do telhado viga I (verba, lucro %, opção A/B/C, com a venda total travada) | 🔴 **ABERTA — bloqueia SÓ a Task 8 de 10** do Resgate da Espinha | Task 1: escalar. As outras nove tasks entram na Task 8 deste plano |
| **FASE8-T1** | Medir o plano de contas em **produção** (não em dev) | 🔴 **ABERTA — é trabalho humano** | Task 1: escalar |

⚠️ **O bloqueio dos dois é PARCIAL — e a primeira versão deste plano errou
isso.** A conferência na fonte, em 31/08, mostrou:

- **Resgate da Espinha Financeira:** 🔬 o cabeçalho do plano diz "**uma única
  task** presa a decisão de negócio", e a Task 8 confirma: *"Se o Cássio não
  decidir, entregue as Tasks 1–7 e 9–10 e deixe esta nomeada como resíduo."*
  **Nove das dez tasks entram na fila** — são porte de 2.542 linhas já escritas
  e testadas no PR #6. Isso virou a **Task 8** deste plano.
- **Fase 8:** 🔬 a D6 diz que *"as Tasks 1, 2, 3 e 5 a 10 não dependem dela"*,
  mas a seção "Onde a fase pode ser cortada em duas" diz o contrário sobre a 3:
  *"Não corte no meio da 3–4: aposentar o semeador sem migrar as `5.x` deixa o
  parque em dois estados."* **O plano se contradiz**, e a metade insegura é a
  que age sobre dados de todos os tenants. **A Fase 8 fica fora da fila** até a
  D6 ser respondida — executar só a metade segura exigiria arbitrar essa
  contradição, e o custo do erro é partida contábil migrada em silêncio para a
  conta errada.

Executar o que está travado significaria decidir por conta própria o
significado contábil de `5.1.01` e a regra de rateio de lucro de um produto —
decisões de negócio, não de código. A Task 1 escala as três.

---

## File Structure

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `docs/superpowers/plans/2026-08-31-decisoes-pendentes.md` | **Criar** | Task 1 — o pedido de decisão, com evidência |
| `relatorios_financeiros_avancados.py` | **Apagar** (942 linhas) | Task 2 |
| `main.py:163-169` | Modificar | Task 2 — tirar o registro do blueprint |
| `scripts/rastreio_modulos.py:50` | Modificar | Task 2 — tirar da tabela de rastreio |
| `views/vehicles.py` | Modificar (6 blocos) | Task 3 |
| `tests/test_fecho_rotas_extintas.py` | **Criar** | Tasks 2 e 3 — congela as extinções |
| `docs/superpowers/plans/2026-08-25-onda-2-*.md` | Executar + marcar | Task 4 |
| `docs/superpowers/plans/2026-08-28-o-que-nao-persiste.md` | Executar + marcar | Task 5 |
| `docs/superpowers/plans/2026-08-25-onda-6-*.md` | Executar + marcar | Task 6 |
| `docs/superpowers/plans/2026-08-25-onda-4-*.md` | Executar + marcar | Task 7 |
| `docs/superpowers/plans/2026-08-24-resgate-espinha-financeira.md` | Executar 9/10 + marcar | Task 8 |
| `docs/superpowers/plans/2026-08-31-issues-de-arquitetura.md` | **Criar** | Task 9 |
| `docs/planos-em-aberto-2026-08-31.md` | **Criar** | Task 10 — o índice que volta a valer |

---

### Task 1: As três decisões que só uma pessoa toma sobem para quem decide

> 🔴 Esta task **não escreve código** e **não pode ser fechada por um agente**.
> Ela produz o pedido de decisão e para. As Tasks 2-9 seguem sem depender dela.

**Files:**
- Create: `docs/superpowers/plans/2026-08-31-decisoes-pendentes.md`

**Interfaces:**
- Consumes: nada.
- Produces: nada que outra task deste plano consuma. Destrava, no futuro, a
  Fase 8 e o Resgate da Espinha Financeira.

- [ ] **Step 1: Reunir a evidência de cada decisão, da fonte**

```bash
# D6 — os dois seeders que trocam o significado de 5.1.01 e 5.1.02
grep -rn "5\.1\.01\|5\.1\.02" --include=*.py . | grep -v archive | grep -v test

# FASE8-T1 — o que dev diz hoje (para contrastar com produção)
grep -n "Task 1" docs/superpowers/plans/2026-08-24-fase-8-plano-de-contas-canonico.md

# VIGA-I — onde a regra de verba/lucro é citada
grep -rn "viga I\|viga-i\|telhado" docs/superpowers/plans/2026-08-24-resgate-espinha-financeira.md
```

- [ ] **Step 2: Escrever o pedido de decisão**

Crie `docs/superpowers/plans/2026-08-31-decisoes-pendentes.md` com esta
estrutura — **uma seção por decisão**, e cada uma respondendo três perguntas:
o que está travado, quais são as saídas, e o que muda em cada saída.

```markdown
# Decisões pendentes — o que trava a Fase 8 e o Resgate da Espinha

> **Para quem decide.** Três perguntas. Cada uma trava um plano inteiro que já
> está escrito e pronto para executar. Nenhuma delas é técnica: são o
> significado de uma conta contábil, uma medição de produção, e uma regra de
> rateio de lucro.

## D6 — o de-para do plano de contas não pode ser chaveado só por código

**O que trava:** `docs/superpowers/plans/2026-08-24-fase-8-plano-de-contas-canonico.md`,
Task 4 em diante (10 tasks, 3 de 21 arquivos existem).

**O problema:** os dois seeders aposentados trocam entre si o significado de
`5.1.01` e `5.1.02`. Um de-para chaveado só pelo código da conta aplicaria o
significado errado à metade do parque, silenciosamente — e um lançamento
contábil mal classificado não se anuncia.

**A tabela que expõe a colisão**, extraída dos dois seeders concorrentes:

| Código | `contabilidade_utils.criar_plano_contas_padrao` | `financeiro_seeds.PLANO_CONTAS_CONSTRUCAO` |
|---|---|---|
| `5` | CUSTOS | DESPESAS |
| `5.1` | CUSTO DOS SERVIÇOS PRESTADOS | DESPESAS OPERACIONAIS |
| **`5.1.01`** | **Materiais Diretos** | **MÃO DE OBRA** |
| **`5.1.02`** | **Mão de Obra Direta** | **MATERIAIS** |

**O aperto:** a spec manda escrever o de-para conta a conta, **não** derivado
por heurística de nome, "porque os nomes são justamente o que está
inconsistente". Mas 🔬 **a única evidência sobrevivente de qual seeder rodou é
`plano_contas.nome`.** A spec proíbe usar o nome, e sem o nome a Task 4 não é
executável corretamente.

**As saídas:**

- **(a) Chavear em `(codigo, nome)` com igualdade exata** contra os dois
  conjuntos fechados que estão no repositório — *recomendada pelo plano*. Não é
  heurística: é reconhecer a assinatura de um dos dois seeders conhecidos.
  Qualquer par fora dos dois conjuntos **faz a migration falhar e nomear o
  par**. Preserva o "nunca chutar"; derivar por semelhança de string
  (`'MÃO DE OBRA' ≈ 'Mão de Obra Direta'`) segue proibido.
- **(b) Manter a regra literal da spec** (só `codigo`) — mandaria material para
  pessoal em metade do parque, **em silêncio**, porque a partida migra sem
  falhar.
- **(c) Adiar a Fase 8** até haver outra evidência de proveniência além do nome.

**O que muda em cada uma:** (a) destrava as 10 tasks e assume que os dois
conjuntos do repositório cobrem todo o parque — se algum tenant tiver um plano
de contas de terceira origem, a migration para e mostra qual. (b) é a única que
corrompe dado. (c) mantém o status quo: dois significados para o mesmo código,
e relatórios que não se comparam entre tenants.

## FASE8-T1 — medir o plano de contas em produção

**O que trava:** a mesma Fase 8, na raiz. A Task 4 estaria sendo decidida com
número de banco de **dev**, que é majoritariamente resíduo de suíte de teste.

**A pergunta:** se produção mostrar `5.x` dominante, a spec da Fase 8 está
errada e o canônico volta à mesa. Ninguém mediu.

## VIGA-I — a regra de verba/lucro do telhado viga I

**O que trava:** `docs/superpowers/plans/2026-08-24-resgate-espinha-financeira.md`
(10 tasks, 7 de 20 arquivos existem, porte de 2.542 linhas do PR #6).

**O que trava exatamente:** apenas a **Task 8 de 10** (migration 319: `verba`,
`lucro` e `pai` em `rdo_subempreitada_apontamento`). 🔬 As outras nove são porte
de código já escrito e testado, e estão sendo entregues pela Task 8 do plano de
fecho de 31/08 — **esta decisão não segura o resto.**

**A pergunta:** o "telhado viga I" precisa de **verba**, **lucro %** e a escolha
entre as **opções A/B/C**, mantendo a **venda total travada**.

**O que muda:** com a resposta, a migration 319 entra, o ramo de subempreitada
volta a `custo_nao_mo_atividade`, e os testes da Fatia 2
(`tests/test_resultado_fatia2_custo_nao_mo.py`) saem de `xfail`. Sem ela, o
resultado por atividade fica **sem o custo de subempreitada** — não erra, mas
mede menos do que promete, e o `xfail` é o registro disso.
```

⚠️ **O conteúdo acima foi extraído da fonte em 31/08** — a tabela de colisão
vem da seção D6 de `2026-08-24-fase-8-plano-de-contas-canonico.md`, e o escopo
do viga I vem da Task 8 de `2026-08-24-resgate-espinha-financeira.md`. Confira
que continuam valendo antes de enviar; não reescreva as saídas de memória.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/2026-08-31-decisoes-pendentes.md
git commit -m "docs(decisoes): as tres perguntas que travam a fase 8 e a espinha sobem para quem decide"
```

- [ ] **Step 4: PARAR e escalar**

Diga ao usuário, explicitamente, que a Fase 8 e o Resgate da Espinha Financeira
**permanecem abertos** e que este plano não os fecha. Não siga adiante
assumindo uma resposta.

---

### Task 2: Apagar `relatorios_financeiros_avancados.py` (D4)

> ✅ **Decisão D4 tomada em 31/08: apagar.** Absorve a Task 4 da Onda 4.
>
> 🔬 **Conferido na fonte em 31/08, antes desta task ser escrita:**
> - O módulo tem **942 linhas** e **3 rotas** (`/`, `/tco/<int:veiculo_id>`,
>   `/api/dados-financeiros`) sob o blueprint `relatorios_financeiros`
>   (`url_prefix='/relatorios/financeiros'`).
> - Suas duas chamadas de `render_template` apontam para
>   `relatorios/financeiros/dashboard.html` e `.../tco_detalhado.html` — e
>   📖 **o diretório `templates/relatorios/` NÃO EXISTE.** As rotas que
>   renderizam não têm o que renderizar.
> - 🔬 **Zero** testes referenciam o módulo. 🔬 **Zero** templates ou JS usam
>   `url_for('relatorios_financeiros.*')`.
> - Só dois arquivos o mencionam: `main.py:165` (registro) e
>   `scripts/rastreio_modulos.py:50` (tabela de rastreio).

**Files:**
- Delete: `relatorios_financeiros_avancados.py`
- Modify: `main.py:163-169`
- Modify: `scripts/rastreio_modulos.py:50`
- Test: `tests/test_fecho_rotas_extintas.py` (criar)

**Interfaces:**
- Consumes: nada.
- Produces: `tests/test_fecho_rotas_extintas.py`, que a Task 3 estende.

- [ ] **Step 1: Write the failing test**

Crie `tests/test_fecho_rotas_extintas.py`:

```python
"""As rotas que este repositório extinguiu, e a prova de que não voltaram.

Segue o padrão de `tests/test_b5_fluxo_gemeos_e_orfaos.py:210`, que congela a
extinção da família `main.*` de custo de veículo: a morte é PROVADA pelo
`url_map`, não afirmada por comentário. Um `grep` diz que ninguém chama; só o
`url_map` diz que ninguém PODE chamar.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints
from app import app

pytestmark = pytest.mark.integration


def _endpoints():
    return {r.endpoint for r in app.url_map.iter_rules()}


def test_relatorios_financeiros_avancados_esta_extinto():
    """🔴 D4 — o módulo respondia `{"success": true, "dados": {}}` em vez de
    errar, por seis defeitos independentes.

    🔬 As duas rotas que renderizavam apontavam para
    `templates/relatorios/financeiros/*.html`, e o diretório
    `templates/relatorios/` não existe — nunca existiu na árvore. Um relatório
    que não tem template não é um relatório quebrado, é um relatório que nunca
    funcionou.

    Apagar foi mais honesto que consertar: ninguém reclamou em meses porque
    ninguém conseguia usar.
    """
    vivos = {e for e in _endpoints() if e.startswith('relatorios_financeiros.')}
    assert not vivos, (
        f'o blueprint relatorios_financeiros voltou a registrar rotas: {vivos}')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_fecho_rotas_extintas.py -v`
Expected: **FAIL** — três endpoints vivos
(`relatorios_financeiros.dashboard_financeiro` e as outras duas). Se passar de
primeira, **pare**: o blueprint já não registra, e o achado mudou.

- [ ] **Step 3: Write minimal implementation**

Apague o arquivo e as duas referências:

```bash
git rm relatorios_financeiros_avancados.py
```

Em `main.py`, remova o bloco de registro inteiro (linhas 163-169), que hoje é:

```python
# Registrar Relatórios Financeiros Avançados
try:
    from relatorios_financeiros_avancados import financeiros_bp
    app.register_blueprint(financeiros_bp)
    logger.info("[OK] Relatórios Financeiros Avançados registrado")
except Exception as e:
    logger.error(f"[ERROR] Erro ao registrar Relatórios Financeiros: {e}", exc_info=True)
```

Substitua por uma linha de lápide, no mesmo estilo do
`# Relatórios de uso detalhado removido (código obsoleto limpo)` que já existe
logo abaixo:

```python
# Relatórios Financeiros Avançados removido em 31/08 (decisão D4): módulo
# inoperante por seis defeitos, renderizando templates que nunca existiram
# (`templates/relatorios/`). Extinção congelada em
# tests/test_fecho_rotas_extintas.py.
```

Em `scripts/rastreio_modulos.py:50`, remova a entrada:

```python
    'Relatórios financeiros avançados': ['relatorios_financeiros_avancados.py'],
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_fecho_rotas_extintas.py -v`
Expected: **PASS**.

Run: `python -c "import main; print('app sobe')"`
Expected: `app sobe` — sem o registro, o app ainda tem de subir.

Run: `python -m pytest tests/ -k "relatorio or financeiro" -m "not browser" -q`
Expected: verde. ⚠️ Se algum teste cair, ele dependia do módulo morto — traga o
caso, não o conserte por reflexo.

- [ ] **Step 5: Commit**

```bash
git add -A tests/test_fecho_rotas_extintas.py main.py scripts/rastreio_modulos.py
git commit -m "fix(relatorios): o modulo financeiro avancado sai — 942 linhas que nunca renderizaram"
```

---

### Task 3: Apagar as seis rotas quebradas de veículos (D3)

> ✅ **Decisão D3 tomada em 31/08: apagar.** Absorve a Task 5 da Onda 4.
>
> 🔬 **As seis causas foram reconferidas na fonte em 31/08, uma a uma** — e
> **duas alegações do achado original não bateram** e precisaram ser
> reescritas. Não repasse a lista antiga; use esta:

| Linha | Função | Causa, verificada em 31/08 |
|---|---|---|
| `:192` | `processar_passageiro_veiculo` (helper de `novo_uso_veiculo_lista`) | `PassageiroVeiculo` **não está importado** — `views/vehicles.py:3` importa só `db, TipoUsuario, Funcionario, Obra`. NameError → `-1` → rollback com a mensagem **falsa** "já estavam registrados como passageiros" |
| `:665` | `deletar_uso_veiculo` | `url_for('main.detalhes_veiculo', veiculo_id=...)`, mas a assinatura é `detalhes_veiculo(id)` (`:1598`). BuildError **depois** do commit: a exclusão funciona e a tela diz "Erro ao excluir uso" |
| `:716` | `editar_custo_veiculo` | `form.km_custo` / `form.litros` não existem em `CustoVeiculoForm` (`forms.py:224`), que tem `km_atual` e `litros_combustivel`. **A edição de custo nunca gravou** |
| `:834` | `dashboard_veiculo` | `uso.horas_uso` sobre instâncias de `UsoVeiculo` — 🔬 **`horas_uso` é coluna de `RDOEquipamento` (`models.py:1451`), não de `UsoVeiculo`.** O achado original dizia "campos inexistentes"; o campo existe, no modelo errado |
| `:925` | `historico_veiculo` | `from sqlalchemy import Funcionario, Obra` → ImportError em toda requisição |
| `:1321` | `aprovar_lancamento_veiculo` | `item.aprovado = True` sobre `UsoVeiculo`/`CustoVeiculo` — 🔬 **nenhum dos dois tem a coluna** (`aprovado` é de `ServicoObraReal`, `models.py:663`). SQLAlchemy aceita o atributo em Python e não persiste: **commit vazio com flash de sucesso** |

> 🔬 **Prova de que estão mortas pela interface:** as **24** funções de rota de
> `views/vehicles.py` têm **zero** referências em `templates/` e `static/`
> (medido em 31/08, `url_for('main.<func>')` para cada uma). Nenhum link direto
> a `/veiculos` em template ou JS. A capacidade viva equivalente é o
> `frota_bp` (`frota_views.py`, 13 rotas).
>
> ⚠️ **O escopo é AS SEIS, não o módulo inteiro.** As outras 18 rotas estão
> mortas pela interface mas **funcionam**, e uma delas —
> `relatorios_veiculos` (`/veiculos/relatorios`) — é exercitada por
> `tests/test_browser_all_modules.py:647`. Apagá-las é outra decisão, e a
> Task 9 a registra como pendência, não como feito.

**Files:**
- Modify: `views/vehicles.py` (6 blocos + 1 helper órfão)
- Test: `tests/test_fecho_rotas_extintas.py` (criado na Task 2)

**Interfaces:**
- Consumes: `_endpoints()` de `tests/test_fecho_rotas_extintas.py` (Task 2).
- Produces: nada.

- [ ] **Step 1: Write the failing test**

Acrescente a `tests/test_fecho_rotas_extintas.py`:

```python
# ---------------------------------------------------------------------------
# D3 — as seis rotas de veículo que quebravam na primeira requisição
# ---------------------------------------------------------------------------

# 🔬 As seis, por endpoint. Cada uma quebrava por uma causa DIFERENTE, e três
# delas mentiam para o usuário: rollback com mensagem de sucesso (:192), erro
# numa exclusão que funcionou (:665), e commit vazio com flash de aprovação
# (:1321). A capacidade viva equivalente é o `frota_bp`.
SEIS_EXTINTAS = (
    'main.novo_uso_veiculo_lista',      # :192 NameError PassageiroVeiculo
    'main.deletar_uso_veiculo',         # :665 BuildError depois do commit
    'main.editar_custo_veiculo',        # :716 form.km_custo não existe
    'main.dashboard_veiculo',           # :834 horas_uso é de RDOEquipamento
    'main.historico_veiculo',           # :925 ImportError na linha de import
    'main.aprovar_lancamento_veiculo',  # :1321 aprovado não é coluna
)


@pytest.mark.parametrize('endpoint', SEIS_EXTINTAS)
def test_rota_de_veiculo_quebrada_esta_extinta(endpoint):
    """🔴 D3 — seis rotas registradas, alcançáveis por URL, e quebradas na
    primeira requisição.

    Consertar código que nenhuma tela chama é criar manutenção para uma
    funcionalidade que ninguém pediu — e três delas MENTIAM para o usuário,
    que é pior que quebrar em silêncio.

    O teste itera sobre AS SEIS, não sobre uma: apagar cinco e deixar a sexta
    é o padrão que a onda "A Porta Irmã" existiu para fechar.
    """
    assert endpoint not in _endpoints(), (
        f'{endpoint} voltou ao url_map — a capacidade viva é o frota_bp')


def test_a_familia_viva_de_frota_continua_registrada():
    """A contraprova: apagar as seis não pode ter levado a frota junto.

    Sem esta afirmação, o teste acima passaria também se alguém apagasse o
    app inteiro — um guarda que só sabe dizer "não existe" não distingue
    remoção cirúrgica de estrago.
    """
    vivos = {e for e in _endpoints() if e.startswith('frota.')}
    assert len(vivos) >= 13, (
        f'a família frota.* encolheu para {len(vivos)} — esperado >= 13')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_fecho_rotas_extintas.py -v`
Expected: **FAIL nos seis casos** (`main.* voltou ao url_map`), e **PASS** em
`test_a_familia_viva_de_frota_continua_registrada`. Se algum dos seis passar
antes da remoção, **pare** — essa rota já não está registrada e a tabela acima
está velha.

- [ ] **Step 3: Write minimal implementation**

Em `views/vehicles.py`, apague **do decorador até o fim do corpo** de cada uma
das seis funções. Faixas medidas em 31/08 — **confira o nome da função antes de
cortar**, porque qualquer edição anterior desloca as linhas:

| Bloco a apagar | Faixa em 31/08 |
|---|---|
| `processar_passageiro_veiculo` (helper) + `novo_uso_veiculo_lista` | `:171-378` |
| `deletar_uso_veiculo` | `:636-676` |
| `editar_custo_veiculo` | `:677-731` |
| `dashboard_veiculo` | `:812-917` |
| `historico_veiculo` | `:918-1014` |
| `aprovar_lancamento_veiculo` | `:1305-1335` |

⚠️ **O helper `processar_passageiro_veiculo` (`:171`) sai junto** — 🔬 seus
únicos chamadores são `:324` e `:335`, ambos dentro de
`novo_uso_veiculo_lista`. Fica órfão no instante em que a rota sai.

⚠️ **O helper `organizar_passageiros_por_posicao` (`:379`) FICA** — 🔬 é usado
em `:556`, dentro de `detalhes_uso_veiculo`, que **não** está entre as seis.

No lugar do primeiro bloco removido, deixe a lápide:

```python
# Seis rotas de veículo removidas em 31/08 (decisão D3): registradas e
# alcançáveis por URL, mortas pela interface (zero referências em templates e
# JS) e quebradas na primeira requisição — três delas mentindo para o usuário
# (rollback com mensagem de sucesso, erro numa exclusão que funcionou, commit
# vazio com flash de aprovação). A capacidade viva é o `frota_bp`.
# Extinção congelada em tests/test_fecho_rotas_extintas.py.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_fecho_rotas_extintas.py -v`
Expected: **PASS** — os seis e a contraprova da frota.

Run: `python -m pytest tests/ -k "veiculo or frota or uso" -m "not browser" -q`
Expected: verde. ⚠️ 🔬 `tests/test_b5_fluxo_gemeos_e_orfaos.py:210` já congela
uma extinção anterior da mesma família — ele tem de **continuar passando**.

Run: `bash run_tests.sh --gate`
Expected: **2854 passed** ou mais (o piso mais os testes novos), **6 skipped**,
**201 deselected**, **0 failed**. 🔬 O deselected não muda: nenhuma das seis é
exercitada por teste de browser — `/veiculos/relatorios` é `relatorios_veiculos`,
que **não** está entre as seis.

- [ ] **Step 5: Commit**

```bash
git add tests/test_fecho_rotas_extintas.py views/vehicles.py
git commit -m "fix(veiculos): as seis rotas que quebravam na primeira requisicao saem (D3)"
```

---

### Task 4: Onda 2 — o tenant para de vazar

> ⚠️ **Esta task vem ANTES da Onda 4, sempre.** 🔬 A Task 2 da Onda 4 *torna
> exploitável* um furo que esta onda fecha. Executar a Onda 4 primeiro é abrir
> o furo de propósito.

**Files:**
- Execute: `docs/superpowers/plans/2026-08-25-onda-2-o-tenant-para-de-vazar.md` (8 tasks)

**Interfaces:**
- Consumes: nada deste plano.
- Produces: o resolvedor de tenant corrigido, de que a Onda 4 (Task 7) depende.

- [ ] **Step 1: Ler o plano inteiro antes de tocar em código**

Run: `sed -n '1,80p' docs/superpowers/plans/2026-08-25-onda-2-o-tenant-para-de-vazar.md`

⚠️ **A Task 1 daquele plano é MEDIÇÃO OBRIGATÓRIA, não código.** Consertar o
resolvedor torna invisível, de uma vez, todo dado carimbado no tenant fantasma
— medir antes é a única chance de saber o tamanho do estrago. **Não pule para
a Task 2.**

- [ ] **Step 2: Executar as 8 tasks, uma a uma, pela sub-skill**

Use `superpowers:subagent-driven-development` (recomendado) ou
`superpowers:executing-plans`, task a task, com o ciclo TDD de cada uma.

⚠️ Ao escrever cada teste, aplique a constraint global: **o teste tem de
reprovar quando o próprio gatilho para de funcionar.** Antes de aceitar um
verde, pergunte se o teste chegaria ao código sob teste caso o defeito não
existisse.

- [ ] **Step 3: Gate**

Run: `bash run_tests.sh --gate`
Expected: **0 failed**, **skipped ≤ 6**, passed ≥ 2854 + os testes que a onda
acrescentou.

- [ ] **Step 4: Marcar o plano como fechado**

No cabeçalho de `2026-08-25-onda-2-o-tenant-para-de-vazar.md`, troque
`🟡 **ABERTO — pronto para executar**` por `✅ **FECHADO — 8/8 tasks**` com os
números reais do gate e os commits, no formato que
`2026-08-28-a-porta-irma.md` usa hoje.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/2026-08-25-onda-2-o-tenant-para-de-vazar.md
git commit -m "docs(onda-2): a onda fecha, com o gate e as 8 tasks marcadas"
```

---

### Task 5: `o-que-nao-persiste` — os cinco achados restantes do review

> Os cinco que sobraram do `/code-review max` sobre a branch da Onda 5, depois
> que a onda "A Porta Irmã" fechou os outros seis. Causa comum: **escrita que
> não chega ao banco, ou chega pela metade.**

**Files:**
- Execute: `docs/superpowers/plans/2026-08-28-o-que-nao-persiste.md` (6 tasks)

**Interfaces:**
- Consumes: nada.
- Produces: nada que outra task deste plano consuma.

- [x] **Step 1: Conferir que os cinco achados ainda existem na fonte**

Os cinco, e onde estão listados como abertos em
`docs/auditoria/achados-code-review-2026-08-25.md`, seção
"🔴 Abertos — os cinco que sobraram":

```bash
grep -n "portal_obras_views.py:647\|models.py:7616\|cronograma_proposta.py:609\|proposta_diff.py:92\|portal_obras_views.py:774" docs/auditoria/achados-code-review-2026-08-25.md
```

⚠️ O plano é de 28/08 e a árvore mudou desde então. **Reconfira cada um na
fonte antes de corrigir** — a própria onda "A Porta Irmã" encontrou duas
alegações do review que não batiam.

- [x] **Step 2: Executar as 6 tasks pela sub-skill**

Use `superpowers:subagent-driven-development` ou
`superpowers:executing-plans`, task a task.

- [x] **Step 3: Gate**

Run: `bash run_tests.sh --gate`
Expected: **0 failed**, **skipped ≤ 6**.
✅ **Medido em 31/08:** 2872 passed, 6 skipped, 201 deselected, 2 xfailed, 0
failed (46min44s). +18 verdes sobre o piso de 2854; skipped ficou em 6.

- [x] **Step 4: Marcar o plano e o documento de auditoria**

Feche o cabeçalho do plano, e em
`docs/auditoria/achados-code-review-2026-08-25.md` mova os cinco de
"🔴 Abertos — os cinco que sobraram" para uma tabela de corrigidos com o
commit de cada um — exatamente como a seção
"✅ Corrigidos pela onda 'A Porta Irmã' (31/08)" faz.

- [x] **Step 5: Commit**

```bash
git add docs/superpowers/plans/2026-08-28-o-que-nao-persiste.md docs/auditoria/achados-code-review-2026-08-25.md
git commit -m "docs(nao-persiste): a onda fecha, e os cinco achados restantes saem de abertos"
```

---

### Task 6: Onda 6 — os testes que os planos prometeram

> A menor das ondas abertas (377 linhas, 6 tasks). 🔬 Ela já derrubou dois
> resíduos que a medição mecânica apontara e eram falso alarme, e confirmou um
> real: zero testes citam `entrada_ja_lancada`.

**Files:**
- Execute: `docs/superpowers/plans/2026-08-25-onda-6-os-testes-prometidos.md` (6 tasks)

**Interfaces:**
- Consumes: nada.
- Produces: cobertura nova; o `passed` do gate sobe.

- [ ] **Step 1: Executar as 6 tasks pela sub-skill**

Use `superpowers:subagent-driven-development` ou
`superpowers:executing-plans`, task a task.

⚠️ Esta onda **só escreve testes**. O risco dela não é regressão, é o oposto:
**teste que nasce verde.** Todo teste desta onda tem de ter um RED medido e
citado no commit — se um teste passa na primeira execução, ele não provou nada
e não deve ser commitado como prova.

- [ ] **Step 2: Gate**

Run: `bash run_tests.sh --gate`
Expected: **0 failed**, **skipped ≤ 6**, e o **passed sobe** pelo número de
testes que a onda acrescentou. Se o passed não subir, a onda não entregou.

- [ ] **Step 3: Marcar o plano como fechado**

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-08-25-onda-6-os-testes-prometidos.md
git commit -m "docs(onda-6): a onda fecha, com os testes prometidos entregues"
```

---

### Task 7: Onda 4 — o relatório passa a funcionar

> ⚠️ **DEPENDE DA TASK 4** (Onda 2). Não comece antes de ela fechar.
>
> 🔬 As Tasks 4 e 5 daquele plano foram **absorvidas** pelas Tasks 2 e 3 deste
> — as duas eram as bloqueadas por D4 e D3, e as duas já estarão feitas.
> Restam **5 das 7**.

**Files:**
- Execute: `docs/superpowers/plans/2026-08-25-onda-4-o-relatorio-passa-a-funcionar.md` (Tasks 1, 2, 3, 6, 7)

**Interfaces:**
- Consumes: o resolvedor de tenant corrigido pela Task 4 deste plano.
- Produces: nada.

- [ ] **Step 1: Marcar as duas tasks absorvidas, antes de executar**

Em `2026-08-25-onda-4-o-relatorio-passa-a-funcionar.md`, marque as Tasks 4 e 5
como executadas por este plano, com o commit, para que o executor não as refaça:

```markdown
### Task 4: [título original]

> ✅ **ABSORVIDA pelo plano de fecho (31/08), Task 2** — decisão D4 resolvida
> como "apagar". Commit: [hash do commit da Task 2].

### Task 5: Apagar as seis rotas mortas de veículos

> ✅ **ABSORVIDA pelo plano de fecho (31/08), Task 3** — decisão D3 resolvida
> como "apagar". Commit: [hash do commit da Task 3]. ⚠️ O escopo executado foi
> **as seis rotas quebradas**, não o módulo inteiro: as outras 18 rotas de
> `views/vehicles.py` estão mortas pela interface mas funcionam, e a remoção
> delas é decisão que ninguém tomou.
```

- [ ] **Step 2: Executar as cinco tasks restantes pela sub-skill**

⚠️ **A Task 2 daquele plano é a que dependia da Onda 2.** Confirme que a Task 4
deste plano fechou antes de tocá-la.

- [ ] **Step 3: Gate**

Run: `bash run_tests.sh --gate`
Expected: **0 failed**, **skipped ≤ 6**.

- [ ] **Step 4: Marcar o plano como fechado**

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/2026-08-25-onda-4-o-relatorio-passa-a-funcionar.md
git commit -m "docs(onda-4): a onda fecha, com as duas tasks absorvidas pelo plano de fecho"
```

---

### Task 8: Resgate da Espinha Financeira — as nove tasks que não dependem do viga I

> 🔬 **O bloqueio deste plano é de UMA task, não do plano.** O cabeçalho diz
> "uma única task presa a decisão de negócio", e a própria Task 8 dele instrui:
> *"Se o Cássio não decidir, entregue as Tasks 1–7 e 9–10 e deixe esta nomeada
> como resíduo."* Nove das dez entram.
>
> Não é feature nova: é **porte de 2.542 linhas já escritas e testadas** no
> PR #6 (`design/espinha-financeira-obra`), contra uma árvore que evoluiu 476
> commits em paralelo, do outro lado da fratura de linhagem de 22/07.
> 🔬 7 de 20 arquivos prometidos já existem na árvore.

**Files:**
- Execute: `docs/superpowers/plans/2026-08-24-resgate-espinha-financeira.md`,
  Tasks **1–7 e 9–10**. A **Task 8** fica de fora (migration 319: `verba`,
  `lucro`, `pai` em `rdo_subempreitada_apontamento`)

**Interfaces:**
- Consumes: nada deste plano.
- Produces: o *Resultado por Atividade* (valor agregado − custo incorrido, por
  atividade do cronograma), com alarme, EVM, lente de caixa, roll-up de
  portfólio e o importador de obra por planilha.

- [ ] **Step 1: Ler o plano e as specs que ele cita, antes de portar**

```bash
sed -n '1,60p' docs/superpowers/plans/2026-08-24-resgate-espinha-financeira.md
```

🔬 As specs que o porte argumenta contra:
`docs/superpowers/specs/2026-06-14-espinha-financeira-obra-design.md` (D1–D6),
o contrato cross-cutting em
`docs/superpowers/plans/2026-06-15-espinha-financeira-plano-mestre.md`
(DC1–DC11), `docs/adr/0004-*` (granularidade serviço→N atividades) e
`docs/adr/0005-*` (orçado = baseline congelado da Proposta).

- [ ] **Step 2: Marcar a Task 8 daquele plano como resíduo, ANTES de executar**

Para que o executor não pare no meio nem tente adivinhar a regra:

```markdown
### Task 8 — Fatia 2 §D: verba, lucro e pai na subempreitada (migration 319)

> ⏸️ **RESÍDUO NOMEADO — não executar.** Bloqueada pela decisão VIGA-I (verba,
> lucro %, opção A/B/C, com a venda total travada), escalada em
> `docs/superpowers/plans/2026-08-31-decisoes-pendentes.md`. As Tasks 1–7 e
> 9–10 foram entregues pelo plano de fecho de 31/08, Task 8.
```

- [ ] **Step 3: Executar as nove tasks pela sub-skill**

Use `superpowers:subagent-driven-development` ou
`superpowers:executing-plans`, task a task.

⚠️ **Porte não dispensa RED.** O plano é explícito: *"Cada módulo portado ganha
teste antes de entrar — os testes da branch vêm junto, mas **não substituem o
RED**."* Um teste que veio pronto do PR #6 e passa na primeira execução contra
a árvore de hoje não provou que o porte funcionou; provou que o teste existe.
Rode-o contra a árvore **antes** do módulo entrar e veja o RED.

⚠️ **A Task 5 remove um ramo que a Task 8 devolveria.** Como a Task 8 não vai
rodar, esse ramo fica removido — é o resíduo esperado, não um erro. Os testes
da Fatia 2 (`tests/test_resultado_fatia2_custo_nao_mo.py`) **continuam com
`xfail`**; não os tire.

- [ ] **Step 4: Gate**

Run: `bash run_tests.sh --gate`
Expected: **0 failed**, **skipped ≤ 6**, e os `xfailed` sobem (os da Fatia 2
entram como esperados-a-falhar). Passed sobe pelo porte.

- [ ] **Step 5: Marcar o plano como parcialmente fechado**

⚠️ **Não marque como `✅ FECHADO`** — nove de dez não é dez. Use:

```markdown
> **Estado em [data]:** 🟢 **9/10 TASKS ENTREGUES** — Tasks 1–7 e 9–10 pelo
> plano de fecho de 31/08. A **Task 8 continua aberta**, bloqueada por VIGA-I.
> Gate: [números reais].
```

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/plans/2026-08-24-resgate-espinha-financeira.md
git commit -m "docs(espinha): 9 das 10 tasks entregues; a task 8 fica como residuo do viga I"
```

---

### Task 9: As oito issues de arquitetura viram plano, ou ficam adiadas por escrito

> 🔬 `docs/superpowers/issues/` tem **8 issues** derivadas do plano de
> remediação de saúde de 08/06 (A a H), e **nenhum plano aberto as endereça**.
> Elas não são achados de review — são dívida de arquitetura: cache de
> instância ORM, `create_app()` único, fonte única do plano de contas,
> precificação única, N+1 de config por request, infra de testes e migrações.
>
> Adiar é uma resposta legítima. Adiar **sem registrar** é como elas chegaram
> a 31/08 sem ninguém notar.

**Files:**
- Create: `docs/superpowers/plans/2026-08-31-issues-de-arquitetura.md`
- Modify: `docs/superpowers/issues/README.md`

**Interfaces:**
- Consumes: nada.
- Produces: nada.

- [ ] **Step 1: Reconferir cada issue contra a árvore de hoje**

As oito, com prioridade e dependência declaradas no próprio README:

```bash
cat docs/superpowers/issues/README.md
```

| # | Issue | Prio | Depende de |
|---|---|---|---|
| A | Cache de instância ORM | P1 | — |
| B | Falhas silenciosas → sinais acionáveis | P2 | parte de D |
| C | `create_app()` único | P3 | — |
| D | Fonte única do plano de contas (+ADR) | P4 | — |
| E | Precificação única | P5 | — |
| F | N+1 de config por request | P6 | A (padrão) |
| G | Onboarding / prontidão do tenant | P7 | B |
| H | Infra de testes + migrações | P8 | C |

⚠️ **As issues são de 08/06 — quase três meses.** Antes de planejar qualquer
uma, confirme que o defeito ainda existe. 🔬 A issue **D (fonte única do plano
de contas)** tem sobreposição direta com a **Fase 8**, que está travada por D6
— não planeje as duas em paralelo sem resolver a sobreposição.

- [ ] **Step 2: Escrever o plano das que sobreviverem à reconferência**

Crie `docs/superpowers/plans/2026-08-31-issues-de-arquitetura.md` cobrindo
**apenas** as issues cujo defeito você confirmou na árvore, começando por **A**
(o README já a recomenda: bug latente real, risco baixo, RED claro). Para cada
uma: o RED, a correção mínima, o gate.

Para as que **não** sobreviverem, ou que você decidir adiar, registre no mesmo
documento uma seção "Adiadas, e por quê" — com o motivo e o que precisaria
mudar para elas voltarem à fila. Uma issue adiada com motivo escrito é
gerenciável; uma issue esquecida não é.

- [ ] **Step 3: Atualizar o README das issues**

Em `docs/superpowers/issues/README.md`, acrescente à tabela uma coluna de
estado apontando para o plano novo ou para a seção de adiadas.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-08-31-issues-de-arquitetura.md docs/superpowers/issues/README.md
git commit -m "docs(issues): as oito issues de arquitetura ganham plano ou adiamento por escrito"
```

---

### Task 10: O índice volta a valer, o gate consolida, a branch entra

> A última. Só aqui a branch integra — decisão registrada em 31/08: **merge ao
> fim de tudo**, não por onda.

**Files:**
- Create: `docs/planos-em-aberto-2026-08-31.md`
- Modify: `docs/planos-em-aberto-2026-08-25.md` (marcar como substituído)

**Interfaces:**
- Consumes: o estado final de todas as tasks anteriores.
- Produces: o índice de estado que passa a valer.

- [ ] **Step 1: Rodar o gate consolidado**

Run: `bash run_tests.sh --gate`
Expected: **0 failed**, **skipped ≤ 6**, passed ≥ 2854.

⚠️ **Se o skipped subiu em qualquer ponto desde o piso de 31/08, pare aqui e
descubra por quê.** 🔬 Foi exatamente assim que 4 testes saíram do gate em
28/08 sem que nada sinalizasse.

- [ ] **Step 2: Rodar a suíte inteira, incluindo browser**

Run: `bash run_tests.sh --suite`
Expected: verde. ⚠️ O gate deseleciona 201 testes de browser; a Task 3 mexeu
em rotas de veículo e `tests/test_browser_all_modules.py:647` exercita
`/veiculos/relatorios`. **Esta é a única etapa que prova que ele sobreviveu.**

- [ ] **Step 3: Escrever o índice de estado novo**

Crie `docs/planos-em-aberto-2026-08-31.md`, no formato do de 25/08 (que ele
substitui), com o veredito de cada plano **provado por existência de arquivo na
árvore e por git, nunca por contagem de checkbox** — a regra que o próprio
índice antigo estabelece.

Ele tem de registrar, no mínimo:
- os planos fechados por esta rodada (Tasks 4, 5, 6, 7) com commit e gate;
- **Fase 8 e Resgate da Espinha Financeira como ABERTOS**, travados por D6,
  FASE8-T1 e VIGA-I, apontando para `2026-08-31-decisoes-pendentes.md`;
- as 18 rotas restantes de `views/vehicles.py` como **pendência conhecida** —
  mortas pela interface, funcionando, sem decisão tomada;
- o estado das oito issues de arquitetura, conforme a Task 9.

No topo de `docs/planos-em-aberto-2026-08-25.md`, acrescente:

```markdown
> ⛔ **SUBSTITUÍDO por `docs/planos-em-aberto-2026-08-31.md`.** Este documento
> foi escrito contra `main` em `657326c4` e não conhece a Onda 5, a onda "A
> Porta Irmã" nem os planos de 28/08. Continua válido como registro histórico.
```

- [ ] **Step 4: Commit do índice**

```bash
git add docs/planos-em-aberto-2026-08-31.md docs/planos-em-aberto-2026-08-25.md
git commit -m "docs(indice): o estado de todos os planos volta a valer, medido contra a arvore"
```

- [ ] **Step 5: Integrar a branch**

```bash
git checkout main
git merge --no-ff sdd/a-porta-irma
bash run_tests.sh --gate
```

Expected: gate verde **em `main`**, com os mesmos números do Step 1.

⚠️ **Só faça o merge com o gate verde no Step 1 e a suíte verde no Step 2.** Se
qualquer um falhou, o merge não acontece — a branch continua sendo o lugar do
trabalho.

⚠️ 🔬 `main` estava **25 commits à frente do `origin`** em 25/08, e a branch
soma mais 30. **Confirme com o usuário antes de empurrar** — este plano não
autoriza `git push`.

---

## Notas de execução

**Ordem obrigatória:** 1 (escala, e NÃO bloqueia as demais) → 2, 3
(independentes entre si) → **4 (Onda 2)** → 5, 6, 8 (independentes entre si) →
**7 (Onda 4 — depende da Task 4)** → 9 → 10.

**A Task 8 (Espinha) é a maior desta rodada** — porte de 2.542 linhas. Ela não
depende de nenhuma outra e pode correr em paralelo com 5 e 6, mas some o gate
dela ao consolidado da Task 10.

**O que este plano NÃO fecha, e por quê:**

| Item | Motivo |
|---|---|
| Fase 8 — plano de contas canônico (10 tasks) | Travado por **D6** e **FASE8-T1**. 🔬 O plano se contradiz sobre poder cortar na Task 3, e a metade insegura age sobre dados de todos os tenants |
| Resgate da Espinha — **só a Task 8 de 10** | Travada por **VIGA-I**. As outras nove são entregues pela Task 8 deste plano |
| As 18 rotas restantes de `views/vehicles.py` | Mortas pela interface mas **funcionando**. A D3 decidiu sobre as seis quebradas; ninguém decidiu sobre estas |
| `templates/medicao/gestao_itens.html:510` | O form aponta para a rota que a onda "A Porta Irmã" fechou com `@admin_required`. Se GESTOR alcança a página, o botão virou beco. Decisão de produto |
| `git push` | Fora do escopo. `main` já estava 25 commits à frente do `origin` antes desta rodada |

**A regra que esta rodada herda, e que vale mais que qualquer task:** 🔬 na onda
"A Porta Irmã", **três** dos testes propostos pelo plano teriam passado verdes
sem nunca alcançar o código sob teste — e teriam sido commitados como prova de
correção. Aquela onda nasceu porque testes anteriores provavam por
`inspect.getsource()`; proibir a técnica não bastou, porque o vício reapareceu
noutra forma. **Antes de aceitar qualquer verde nesta rodada, pergunte se o
teste chegaria ao código sob teste caso o defeito não existisse.** Se a
resposta for sim, o teste é andaime.
