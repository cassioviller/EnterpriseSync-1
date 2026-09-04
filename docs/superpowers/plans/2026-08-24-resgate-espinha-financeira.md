# Resgate da Espinha Financeira — trazer o PR #6 para o `main` de hoje

> **Decisão de 01/09** (`2026-09-01-decisoes-respondidas.md` §VIGA-I): a verba
> do telhado viga I segue a **opção B**; a C foi declarada morta. `RATIFICAR`
> pendente — a Task 8 daqui destrava ao ratificar.
>
> **Estado em 2026-09-04:** ✅ **EXECUTADO — as 10 tasks fechadas**, `30287f3b` →
> `b5265988`, 9 commits em `sdd/espinha-financeira`. As caixas `- [ ]` abaixo
> seguem desmarcadas pela convenção deste arquivo: elas são rascunho de execução,
> e quem carrega a verdade é este bloco, o `ESTADO-ATUAL.md` (seção de 04/09), o
> código e o git.
>
> **As cinco emendas que a execução fez ao plano** — todas medidas, nenhuma por
> conveniência:
>
> 1. 🔴 **Faltava uma quarta coluna, e o plano não a via.** A migration 195 da
>    linhagem velha também criava `gestao_custo_filho.tarefa_cronograma_id`; o
>    plano conferiu só `rdo_subempreitada_apontamento` e concluiu "três colunas".
>    Sem ela, `custo_nao_mo_atividade` estoura em `TypeError` e a Fatia 2 inteira
>    não roda. Virou a **migration 321**, e a da subempreitada deslizou para a
>    **322** (máximo real do repo medido no dia, como o próprio plano manda).
> 2. 🔴 **Não havia ramo de subempreitada para remover.** A Task 5 mandava tirá-lo
>    de `custo_nao_mo_atividade` e a Task 8 mandava devolvê-lo. 🔬 `grep -i
>    subempreit` no arquivo da branch devolve **duas linhas, ambas comentário**.
>    O custo chega ao read-model pelo ledger genérico; quem faltava era só o
>    **escritor** (Step 3b), que o plano já tinha achado. Os dois steps são no-op
>    declarado.
> 3. ⚠️ **Um quinto leitor de RDO.** O plano nomeava quatro sítios para o filtro
>    de estado; o `horas_reais` de `indice_horas` é o quinto, e somava horas de
>    rascunho no denominador do índice.
> 4. ⚠️ **Duas metades que faltavam na Task 4/6.** A Task 4 criou
>    `propostas_comerciais.origem` e ninguém a lia — o Delta 2 da ADR 0005 (tirar
>    a proposta de importação do funil e dos KPIs) foi feito na Task 6. E a rota
>    `POST /orcamentos/<id>/importar-obra`, que o teste da Task 6 exercita, não
>    estava em nenhuma lista de arquivos: mora em `views/orcamentos_views.py`, não
>    no blueprint `resultado`.
> 5. ⚠️ **A idempotência do re-import não era testada.** O Step 4 da Task 9 manda
>    cobri-la e o E2E da branch a **afirmava sem exercitar**. Teste novo:
>    `test_reimportar_no_mesmo_tenant_nao_duplica`.
>
> **O que ficou de fora, de propósito** (e está nomeado no `ESTADO-ATUAL.md`):
> importador genérico (trabalho novo), datas por atividade / SPI (depende do
> `.mpp`), material direto na UI, refino do EVM F3-4, e o `RATIFICAR` comercial
> do telhado viga I — cujo schema entrou, mas cujos números não.
>
> Índice de estado de todos os planos e specs: `docs/planos-em-aberto-2026-08-25.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para executar este plano task a task. Os passos usam checkbox (`- [ ]`) para acompanhamento.

**Goal:** Trazer para o `main` o *Resultado por Atividade* — valor agregado menos custo incorrido, por atividade do cronograma, com alarme, EVM, lente de caixa e roll-up de portfólio — junto com o importador de obra por planilha, que hoje vivem apenas na branch `design/espinha-financeira-obra` (PR #6), do outro lado da fratura de linhagem de 22/07.

**Architecture:** Não é feature nova: é **porte** de 2.542 linhas já escritas e testadas, contra uma árvore que evoluiu **722 commits** em paralelo (🔬 medido em 03/09 com `git rev-list --count origin/fix/fase-0-estancar..main`; o **476** escrito em 24/08 e o **706** do pré-voo de 02/09 estão os dois vencidos — meça no dia). O porte é feito em ondas, da menor dependência para a maior: primeiro os dois módulos que entram sem tocar em nada, depois as duas colunas que faltam, depois o read-model, o importador, as telas, e por último a Fatia 2 de subempreitada. **Cada módulo portado ganha teste antes de entrar** — os testes da branch vêm junto, mas não substituem o RED.

**Tech Stack:** Flask + SQLAlchemy 2.x, PostgreSQL, pytest, Jinja2, Playwright para as telas.

**Spec:** `docs/superpowers/specs/2026-06-14-espinha-financeira-obra-design.md` (D1–D6) · contrato cross-cutting em `docs/superpowers/plans/2026-06-15-espinha-financeira-plano-mestre.md` (DC1–DC11) · `docs/adr/0004-*` (granularidade serviço→N atividades) e `docs/adr/0005-*` (orçado = baseline congelado da Proposta) · glossário em `CONTEXT.md`.

---

## 🔴 O achado que muda o porte: o read-model não filtra estado de RDO

Isto **não** está em nenhum documento da branch, e é a razão pela qual este porte não pode ser `git checkout` seguido de commit.

📖 `services/resultado_atividade_service.py` na branch: 🔬 **zero** ocorrências de `status`, `estado` ou `'Finalizado'` no arquivo inteiro. Ele soma `RDOCustoDiario` e `RDOMaoObra` de **todo** RDO que encontrar.
📖 `services/aprendizado_produtividade.py` filtra `RDO.status == 'Finalizado'`.

O problema é que 📖 `models.py`, na classe `RDO`: `status = db.Column(db.String(20), default='Finalizado')  # Task #12: RDO sempre Finalizado`. **Esse filtro não filtra nada** — todo RDO nasce `'Finalizado'`. O ciclo de vida real chegou na Fase 5 e mora em `RDO.estado`, com os valores válidos em `services/rdo_ciclo_vida.ESTADOS` — 🔬 `rascunho`, `preenchido`, `assinado`, `aprovado`, `retificado`. **Não existe `submetido`**: o estado de "dia submetido" chama-se `preenchido`, e é o `ESTADO_LEGADO` em que os RDOs históricos caíram no backfill da migration 260.

Em 15/06, quando a branch foi escrita, `RDO.estado` **não existia** — os dois arquivos estavam certos para a árvore deles. Hoje, portados como estão, eles fazem **RDO em rascunho contar como custo real**, alimentando alarme, CPI/EAC e o catálogo de produtividade com um documento que o autor ainda não submeteu.

🔴 **É exatamente o defeito que o `main` acabou de fechar em 24/08 do outro lado** (`95eb585f`, "RDO em rascunho para de mover o percentual"). Portar sem corrigir seria reabrir por baixo o bug que se fechou por cima, e o `ESTADO-ATUAL.md` passaria a ter duas afirmações contraditórias verdadeiras ao mesmo tempo.

**Regra deste plano, e ela é inegociável:** todo leitor de RDO portado filtra por `estado`, com **teste próprio** provando que um RDO em rascunho não entra na conta. Nunca por `RDO.status`.

## ⚠️ Os outros três achados de porte

1. **`FETCH_HEAD` é efêmero.** O código só está acessível enquanto o ref durar. Task 1 resolve isso antes de tudo.
2. **Três colunas não existem hoje** — as migrations 193/194/195 são da linhagem velha e nunca chegaram. Sem elas, o importador quebra em `AttributeError`.
3. **A numeração das migrations colide com a Fase 8.** Este plano escreveu **317, 318, 319** assumindo que a Fase 8 levou 315/316. ⚠️ **Renumerado em 03/09 para 319, 320 e 321** — as 317 e 318 foram gastas em 01/09 (A09 e A24); o máximo real medido no dia era **318**. Esta linha guarda o número original de propósito: o resto do plano fala 319/320/321. **Confira o máximo do repo no dia do commit** e numere em sequência real. Nunca reserve faixa: 📖 o `ESTADO-ATUAL.md` registra que a reserva por faixa foi furada três vezes e que o fantasma do 270 nasceu de renumerar para "organizar".

## Global Constraints

- **Nenhum leitor de RDO portado usa `RDO.status`.** Filtre por `RDO.estado`, e prove com teste.
- **MO nunca conta 2× (DC3).** O read-model lê mão de obra do `RDOCustoDiario`; do ledger `GestaoCustoFilho` lê **só não-MO** (exclui `SALARIO`, `MAO_OBRA_DIRETA`, `VALE_*`). Há teste de regressão guardando isso — ele vem junto e não pode ser afrouxado.
- **Competência ≠ Caixa (D4/ADR 0003).** Resultado é competência; Realizado/Previsto é caixa. Lentes separadas, **nunca somadas** num número só.
- **Orçado = baseline congelado da Proposta** (`PropostaItem.composicao_snapshot`), nunca o Orçamento operacional — senão o alarme pode ser mascarado por revisão (ADR 0005). ⚠️ A Fase 6 fechou em 24/08 e mexeu justamente em revisão de proposta e trava de orçamento: **reconfirme esta premissa contra `services/orcamento_versao.py` antes da Task 5.**
- **Peso Serviço→Atividade = `ItemMedicaoCronogramaTarefa.peso`** (D6/DC8), fonte única para venda e orçado. 🔬 24/08: a coluna existe (`models.py`, classe `ItemMedicaoCronogramaTarefa`).
- **Telas gated por v2** (`is_v2_active`). Sem v2, redireciona.
- **CSRF:** os forms POST dependem do JS global de `base_completo.html`. Em teste, `WTF_CSRF_ENABLED=False`; teste HTTP precisa `import main` para registrar blueprints.
- **TDD sem exceção**, inclusive no porte: escreva o teste, veja o RED, **então** traga o código. Colar o arquivo e rodar o teste que veio junto é teste-depois com passo extra.

---

## File Structure

| Arquivo | Linhas na branch | Ação |
|---|---|---|
| `services/caixa_obra_service.py` | 27 | Portar como está |
| `services/aprendizado_produtividade.py` | 63 | Portar **com** correção de estado |
| `services/resultado_atividade_service.py` | 537 | Portar **com** correção de estado, **menos** o ramo de subempreitada |
| `services/importar_obra_completa.py` | 291 | Portar; depende das migrations 319 e 320 |
| `resultado_views.py` | 174 | Portar; registrar blueprint |
| `templates/resultado/{por_atividade,caixa_obra,portfolio,importar_obra}.html` | 4 arquivos | Portar |
| `scripts/{criar_orcamento_baia_rev10,seed_templates_baia_rev10,importar_baia_easypanel}.py` | 3 arquivos | Portar (Task 8) |
| `migrations.py` | — | 319, 320, 321 |
| `tests/test_{resultado_atividade_service,resultado_fatia2_custo_nao_mo,importar_obra_completa,caixa_obra,fatia5_inteligencia,import_baia_e2e,rdo_edicao_preserva_tarefa}.py` | 7 arquivos | Portar em ondas |
| `ESTADO_design_espinha_financeira.md` | 111 | Aposentar na Task 10 |

---

### Task 1 — tirar o código de cima de um ref efêmero

**Files:**
- Create: `docs/superpowers/plans/resgate-espinha/INVENTARIO.md`

- [ ] **Step 1: Trazer a branch para um ref durável**

🔬 A leitura do `origin` é **anônima** — não depende do `gh auth login`.

⚠️ **Emenda de 03/09:** o `git fetch` **já não é necessário** — o ref
`origin/design/espinha-financeira-obra` já é remote-tracking local
(🔬 tip `a18f86e7`, de 15/06, congelado) e `git cat-file -p` lê todos os blobs
hoje. **Mas a tag continua faltando** (🔬 `git tag | grep espinha` → vazio), e
sem ela **todo** `git show espinha-pr6-origem:…` das Tasks 2-9 falha. Não pule
esta parte:

```bash
git tag espinha-pr6-origem origin/design/espinha-financeira-obra
git tag | grep espinha    # tem de devolver: espinha-pr6-origem
```

⚠️ A branch **não pode ser empurrada** para o `gitsafe-backup`: 📖 `remote: Error: Only pushes to main branch are allowed`. Enquanto o porte não for mesclado, ele existe nesta máquina e no GitHub, e em nenhum outro lugar.

- [ ] **Step 2: Conferir o inventário arquivo a arquivo**

```bash
for f in services/resultado_atividade_service.py services/importar_obra_completa.py \
         services/caixa_obra_service.py services/aprendizado_produtividade.py \
         resultado_views.py; do
  echo "$f: $(git cat-file -p espinha-pr6-origem:$f | wc -l) linhas"
done
git ls-tree --name-only espinha-pr6-origem templates/resultado/
```

Esperado (🔬 24/08): 537, 291, 27, 63, 174 linhas e 4 templates. **Se divergir, pare** — significa que a branch mudou desde esta medição, e todo o resto deste plano foi escrito sobre outra coisa.

- [ ] **Step 3: Registrar o inventário e commitar**

```bash
git add docs/superpowers/plans/resgate-espinha/INVENTARIO.md
git commit -m "docs(espinha): inventario conferido do PR #6 e ref duravel para o porte"
```

---

### Task 2 — as duas peças que entram sem tocar em nada (com a correção de estado)

`caixa_obra_service` (27 linhas) porta **sem tocar em nada**: 🔬 chama `FinanceiroService.calcular_fluxo_caixa(admin_id, data_inicio, data_fim, obra_id=None)` e `agregar_fluxo_mensal(detalhes, saldo_inicial=0.0)`, e as duas assinaturas batem exatamente com as de hoje. `aprendizado_produtividade` (63 linhas) **não** entra como está — é o segundo caso do achado do rascunho.

**Files:**
- Create: `services/caixa_obra_service.py`, `services/aprendizado_produtividade.py`
- Test: `tests/test_caixa_obra.py`, `tests/test_espinha_rascunho_nao_conta.py`

**Interfaces:**
- Produces: `fluxo_caixa_obra(admin_id, obra_id, data_inicio, data_fim) -> dict` com `fluxo`, `meses`, `kpis`, `serie_chart`; `produtividade_observada(subatividade_mestre_id, admin_id) -> tuple[Decimal | None, int]`; `atualizar_catalogo_produtividade(admin_id) -> int`.

- [ ] **Step 1: Escrever o teste do rascunho — este é o RED que importa**

```python
# tests/test_espinha_rascunho_nao_conta.py
"""O porte do PR #6 atravessa a Fase 5: em 15/06 não existia RDO.estado, e
os módulos filtravam por RDO.status == 'Finalizado' — que não filtra nada,
porque todo RDO nasce 'Finalizado' (models.py, classe RDO).

Portado como estava, o aprendizado leria RASCUNHO. É o mesmo defeito que o
main fechou em 24/08 do outro lado (95eb585f)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db  # noqa: E402


def test_rdo_em_rascunho_nao_entra_na_produtividade_observada():
    from services.aprendizado_produtividade import produtividade_observada
    with app.app_context():
        admin_id, sub_id = _catalogo_de_teste()
        _rdo_com_produtividade(admin_id, sub_id, estado='rascunho',
                               produtividade=99.0, horas=8)
        media, n = produtividade_observada(sub_id, admin_id)
        assert n == 0 and media is None, (
            'RDO em rascunho é documento que o autor ainda não submeteu — '
            f'entrou assim mesmo no catálogo (n={n}, media={media})')


def test_rdo_preenchido_entra_normalmente():
    from services.aprendizado_produtividade import produtividade_observada
    with app.app_context():
        admin_id, sub_id = _catalogo_de_teste()
        _rdo_com_produtividade(admin_id, sub_id, estado='preenchido',
                               produtividade=12.0, horas=8)
        media, n = produtividade_observada(sub_id, admin_id)
        assert n == 1 and float(media) == 12.0
```

(`_catalogo_de_teste()` e `_rdo_com_produtividade()` — copie o molde de fixture de `tests/test_rascunho_nao_move_cronograma.py` e `tests/test_rdo_rascunho_nao_lanca_custo.py`, os dois arquivos do lado do `main` que já sabem criar RDO com `estado` explícito. Fixture que cria RDO **sem** `estado` nasce rascunho e produz falso vermelho: foi a "dívida de fixture" que fez o trabalho de 24/08 parecer que quebrava dezenas de testes.)

- [ ] **Step 2: Rodar e ver falhar**

Run: `.pythonlibs/bin/pytest tests/test_espinha_rascunho_nao_conta.py -v`
Expected: FAIL com `ModuleNotFoundError: services.aprendizado_produtividade`. Depois do Step 3 sem a correção, falharia com `n == 1`; **não pule direto para o código corrigido** — traga o arquivo como está, veja o `n == 1`, e só então corrija. Esse é o RED que prova que a correção é necessária.

- [ ] **Step 3: Portar os dois módulos, corrigindo o filtro**

```bash
git show espinha-pr6-origem:services/caixa_obra_service.py > services/caixa_obra_service.py
git show espinha-pr6-origem:services/aprendizado_produtividade.py > services/aprendizado_produtividade.py
```

Em `aprendizado_produtividade.py`, troque o filtro e **deixe o motivo escrito no código**:

```python
        .filter(
            # PORTE 24/08 — era `RDO.status == 'Finalizado'`, escrito em
            # 15/06, antes de RDO.estado existir. `status` nasce
            # 'Finalizado' para todo RDO (models.py, classe RDO), então
            # aquele filtro não filtrava nada e o catálogo aprenderia com
            # rascunho. Estados válidos em services/rdo_ciclo_vida.
            RDO.estado != 'rascunho',
            RDOMaoObra.admin_id == admin_id,
```

- [ ] **Step 4: Rodar e ver passar**

```bash
.pythonlibs/bin/pytest tests/test_espinha_rascunho_nao_conta.py -v
git show espinha-pr6-origem:tests/test_caixa_obra.py > tests/test_caixa_obra.py
.pythonlibs/bin/pytest tests/test_caixa_obra.py -v
```
Expected: PASS nos dois arquivos.

- [ ] **Step 5: Commit**

```bash
git add services/caixa_obra_service.py services/aprendizado_produtividade.py tests/test_caixa_obra.py tests/test_espinha_rascunho_nao_conta.py
git commit -m "feat(espinha): porta caixa_obra e aprendizado_produtividade — rascunho deixa de alimentar o catalogo"
```

---

### Task 3 — `cronograma_template_item.peso_medicao` (migration 319)

📖 É o **coração** do importador (`importar_obra_completa.py:214`): o peso explícito de cada atividade dentro do serviço (DC8/ADR 0004). 🔬 24/08: `peso_medicao` tem **zero** ocorrências em `models.py`.

**Files:**
- Modify: `models.py` (classe `CronogramaTemplateItem`, `__tablename__ = 'cronograma_template_item'`)
- Modify: `migrations.py`
- Test: `tests/test_espinha_migrations_porte.py`

- [ ] **Step 1: O teste que falha**

```python
def test_template_item_tem_peso_medicao_e_nasce_nulo():
    from models import CronogramaTemplateItem
    with app.app_context():
        assert hasattr(CronogramaTemplateItem, 'peso_medicao'), (
            'sem esta coluna o importador quebra em AttributeError na '
            'materialização multi-atividade')
```

- [ ] **Step 2: Rodar e ver falhar** — `AssertionError`.

- [ ] **Step 3: Coluna e migration**

```python
# models.py, em CronogramaTemplateItem
    # Espinha financeira (ADR 0004/DC8) — peso EXPLÍCITO da atividade dentro
    # do serviço. Nullable: template antigo não tem peso e cai no fallback
    # 1:1 do importador; um default numérico fingiria um peso que ninguém
    # definiu. Era a migration 193 da linhagem velha, que nunca chegou aqui.
    peso_medicao = db.Column(db.Numeric(5, 2), nullable=True)
```

```python
def _migration_319_template_item_peso_medicao():
    """Resgate da Espinha Financeira — cronograma_template_item.peso_medicao.

    Reposição da migration 193 da linhagem velha (o repo foi recomeçado em
    22/07 e ela nunca chegou). Idempotente. Nullable de propósito: NULL
    significa "template sem peso definido" e o importador cai no 1:1.
    """
    from sqlalchemy import text as sa_text
    try:
        with db.engine.begin() as conn:
            conn.execute(sa_text("""
                ALTER TABLE cronograma_template_item
                    ADD COLUMN IF NOT EXISTS peso_medicao NUMERIC(5,2)
            """))
        logger.info('[Migration 319] cronograma_template_item.peso_medicao criada.')
        return True
    except Exception as e:
        logger.error(f'[Migration 319] Falha: {e}', exc_info=True)
        return False
```

Registre **na ordem**, conferindo antes o máximo real do repo:

```python
            (319, "Resgate Espinha — cronograma_template_item.peso_medicao (repoe a 193 da linhagem velha)", _migration_319_template_item_peso_medicao),
```

- [ ] **Step 4: Rodar, ver passar, provar idempotente por dupla execução.**

- [ ] **Step 5: Commit**

```bash
git add models.py migrations.py tests/test_espinha_migrations_porte.py
git commit -m "feat(espinha): peso_medicao no template de cronograma (migration 319)"
```

---

### Task 4 — `propostas_comerciais.origem` (migration 320)

📖 `importar_obra_completa.py:68` grava `origem='importacao_obra'` para manter a Proposta de importação **fora do funil comercial** (ADR 0005).

⚠️ **`Proposta.proposta_origem_id` já existe hoje e é outra coisa** — é o elo de linhagem entre revisões, reforçado pela Fase 6 (`origem_id`, `revisao_de_id`). Não reaproveite: `origem` é *de onde a proposta veio como documento*, `proposta_origem_id` é *de qual proposta ela é revisão*. Confundir os dois faria a proposta de importação aparecer como revisão de si mesma no comparador da Fase 6.

**Files:**
- Modify: `models.py` (classe `Proposta`, `__tablename__ = 'propostas_comerciais'`)
- Modify: `migrations.py`
- Test: `tests/test_espinha_migrations_porte.py`

- [ ] **Step 1: O teste que falha**

```python
def test_proposta_tem_origem_e_ela_nao_se_confunde_com_linhagem():
    from models import Proposta
    with app.app_context():
        assert hasattr(Proposta, 'origem')
        assert hasattr(Proposta, 'proposta_origem_id'), (
            'as duas coexistem e querem dizer coisas diferentes: origem é '
            'de onde o documento veio; proposta_origem_id é de qual '
            'proposta esta é revisão (linhagem da Fase 6)')
```

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Coluna + migration 320**, no mesmo molde da 319: `ADD COLUMN IF NOT EXISTS origem VARCHAR(30)`, nullable, sem default — proposta que nasce pelo funil não tem origem especial e `NULL` diz isso melhor que `'funil'`.

- [ ] **Step 4: Rodar, ver passar, dupla execução.**

- [ ] **Step 5: Commit**

```bash
git add models.py migrations.py tests/test_espinha_migrations_porte.py
git commit -m "feat(espinha): propostas_comerciais.origem (migration 320) — proposta de importacao fora do funil"
```

---

### Task 5 — o read-model (537 linhas), sem o ramo de subempreitada

**Files:**
- Create: `services/resultado_atividade_service.py`
- Test: `tests/test_resultado_atividade_service.py`, `tests/test_resultado_fatia2_custo_nao_mo.py`, e **um teste novo** em `tests/test_espinha_rascunho_nao_conta.py`

**Interfaces:**
- Produces (F1): `valor_agregado_atividade(tarefa)`, `custo_mo_atividade(tarefa)`, `custo_mo_orcado_atividade(tarefa)`, `alarme_mo(tarefa)`, `indice_horas(tarefa)`, `resultado_obra(obra_id)`
- Produces (F2): `custo_orcado_unitario(composicao_snapshot, tipos=None)`, `custo_nao_mo_atividade(tarefa)`, `custo_incorrido_atividade(tarefa)`, `alarme_custo(tarefa)`, `custo_orcado_atividade_por_tipos(tarefa, tipos=None)`
- Produces (F3): `venda_total_atividade(tarefa)`, `evm_atividade(tarefa, admin_id, data_ref=None)`, `evm_obra(obra_id, admin_id, data_ref=None)`
- Produces (F5): `resultado_portfolio(admin_id, data_ref=None)`

- [ ] **Step 1: Reconfirmar a premissa do orçado ANTES do código**

📖 Leia `services/orcamento_versao.py` e `handlers/propostas_handlers.py` no `main` de hoje e confirme que `PropostaItem.composicao_snapshot` continua sendo o baseline congelado que a ADR 0005 descreve. A Fase 6 fechou em 24/08 mexendo em revisão de proposta, trava de orçamento e linhagem de item. **Se a semântica mudou, pare e leve ao Cássio** — o alarme inteiro depende disso, e a ADR existe justamente para o alarme não poder ser mascarado por revisão.

- [ ] **Step 2: O teste do rascunho para o custo — acrescente ao arquivo da Task 2**

```python
def test_rdo_em_rascunho_nao_entra_no_custo_de_mao_de_obra():
    """O read-model da branch não filtra RDO de forma nenhuma (🔬 zero
    ocorrências de status/estado no arquivo). Custo de rascunho entrando no
    alarme e no CPI é o mesmo defeito que 95eb585f fechou do outro lado."""
    from services.resultado_atividade_service import custo_mo_atividade
    with app.app_context():
        tarefa = _tarefa_com_rdo(estado='rascunho', custo_dia=1000.0)
        assert float(custo_mo_atividade(tarefa)) == 0.0, (
            'rascunho entrou no custo incorrido — alarme e EAC passam a '
            'reagir a documento não submetido')
```

- [ ] **Step 3: Rodar e ver falhar** — `ModuleNotFoundError`.

- [ ] **Step 4: Portar o arquivo e corrigir os leitores de RDO**

```bash
git show espinha-pr6-origem:services/resultado_atividade_service.py > services/resultado_atividade_service.py
```

Depois, **duas** edições obrigatórias:

1. Em `custo_mo_atividade`, `_horas_obra_no_dia`, `_horas_atividade_no_dia` e `_horas_func_no_rdo` — todo `join`/`filter` que alcança `RDO` ganha `RDO.estado != 'rascunho'`, com o mesmo comentário de porte da Task 2.
2. **Remova o ramo de subempreitada de `custo_nao_mo_atividade`** (Fatia 2 §D): ele espera `rdo_subempreitada_apontamento.verba/lucro/pai`, que só chegam na Task 8. Deixe no lugar um comentário nomeando a Task 8 — **não** um `TODO` solto, e **não** um `try/except AttributeError`, que esconderia a ausência.

- [ ] **Step 5: Rodar e ver passar**

```bash
git show espinha-pr6-origem:tests/test_resultado_atividade_service.py > tests/test_resultado_atividade_service.py
git show espinha-pr6-origem:tests/test_resultado_fatia2_custo_nao_mo.py > tests/test_resultado_fatia2_custo_nao_mo.py
.pythonlibs/bin/pytest tests/test_resultado_atividade_service.py tests/test_resultado_fatia2_custo_nao_mo.py tests/test_espinha_rascunho_nao_conta.py -v
```

⚠️ Os testes da Fatia 2 que cobrem o ramo de subempreitada **vão falhar** — é esperado, ele foi removido no Step 4. Marque-os com `@pytest.mark.xfail(reason='Fatia 2 §D volta na Task 8 — migration 321')` **nomeando a task**, nunca com `skip` silencioso. O teste do DC3 (MO não conta 2×) **tem de passar**; se ele falhar, pare.

- [ ] **Step 6: Commit**

```bash
git add services/resultado_atividade_service.py tests/test_resultado_atividade_service.py tests/test_resultado_fatia2_custo_nao_mo.py tests/test_espinha_rascunho_nao_conta.py
git commit -m "feat(espinha): porta o read-model de resultado por atividade, com filtro de estado de RDO"
```

---

### Task 6 — o importador de obra por planilha

**Files:**
- Create: `services/importar_obra_completa.py`
- Test: `tests/test_importar_obra_completa.py`

**Interfaces:**
- Consumes: `CronogramaTemplateItem.peso_medicao` (Task 3), `Proposta.origem` (Task 4).
- Produces: `importar_obra_completa(orcamento_id, admin_id) -> Obra` — cria Proposta(`origem='importacao_obra'`) → Obra → IMC 1:1 → Cronograma. **Idempotente.**

- [ ] **Step 1: O teste que falha** — porte `tests/test_importar_obra_completa.py` e rode; ele falha em `ModuleNotFoundError`.
- [ ] **Step 2: Ver o RED.**
- [ ] **Step 3: Portar o arquivo.**
- [ ] **Step 4: Rodar e ver passar.** ⚠️ Ponto de atenção do porte: o importador cria Proposta e Obra, e a **Fase 6 mudou quem pode mexer em `valor_contrato`** — 📖 `services/contrato_obra.definir_valor_contrato` é escritor único e abre `ObraContratoVersao`. Se o importador gravar `obra.valor_contrato` direto, ele fura o versionamento e a obra nasce sem versão nº1. **Corrija chamando o escritor único**, e cubra com teste.
- [ ] **Step 5: Commit**

```bash
git add services/importar_obra_completa.py tests/test_importar_obra_completa.py
git commit -m "feat(espinha): porta o importador de obra por planilha, passando pelo escritor unico de contrato"
```

---

### Task 7 — as telas e o blueprint

**Files:**
- Create: `resultado_views.py`, `templates/resultado/{por_atividade,caixa_obra,portfolio,importar_obra}.html`
- Modify: `app.py` (registro do blueprint), `templates/obras/detalhes_obra_profissional.html` (abas Resultado/Caixa), `templates/orcamentos/editar.html` (botão)
- Test: `tests/test_espinha_rotas.py`

**Interfaces:**
- Produces: blueprint `resultado` com `/obras/<id>/resultado`, `/obras/<id>/caixa`, `/resultado/portfolio`, `/resultado/importar-obra`, `/resultado/aprender-produtividade`.

- [ ] **Step 1: Teste de rota que falha** — 200 para quem pode, **404 para tenant alheio** (o teste de vazamento, não de existência), e redireciona sem v2.
- [ ] **Step 2: Ver o RED.**
- [ ] **Step 3: Portar views e templates.**

⚠️ **Registre o blueprint junto dos vizinhos de obra em `app.py`, não no topo.** 📖 A ordem de import ali é contrato não declarado (`ESTADO-ATUAL.md`, armadilha 5) e a Fase 6 já tropeçou nisso. Deixe o motivo escrito no próprio bloco. O documento da branch diz "registrado em `main.py`" — 🔬 confira onde os blueprints são registrados hoje antes de seguir a instrução de 15/06.

- [ ] **Step 4: Rodar e ver passar.**
- [ ] **Step 5: Commit**

```bash
git add resultado_views.py templates/resultado app.py templates/obras/detalhes_obra_profissional.html templates/orcamentos/editar.html tests/test_espinha_rotas.py
git commit -m "feat(espinha): telas de resultado, caixa, portfolio e importacao + blueprint"
```

---

### Task 8 — Fatia 2 §D: verba, lucro e pai na subempreitada (migration 321)

> ✅ **DESTRAVADA em 01/09 — opção B (markup uniforme).** O ajuste move um
> único parâmetro declarado (`orcamento.margem_pct_global`, 📖 `models.py`,
> `db.Numeric(5, 2), nullable=True` — existe e é executável) até a venda total
> voltar a R$ 1.720.796,75. **Não** reduza margens item a item (opção A): isso
> muda a margem de itens que ninguém tocou e contamina a própria medida que
> esta fase entrega. A **opção C está morta** — citada em quatro documentos,
> definida em nenhum. ⚠️ `RATIFICAR` com o dono segue **pendente**: é escolha
> comercial, e **não bloqueia o porte**. Nomeie-a como resíduo no fecho.
>
> 🔬 A decisão de 01/09 responde **a opção** e **a venda travada**, mas não dá
> `verba` nem `lucro %` em número. Os Steps 3-5 desta task **não precisam**
> deles: ali `verba` e `lucro` são **colunas de schema**, e o teste da branch
> usa valores próprios (`{'verba_unica': 10000, 'lucro_pct': 20}`). Quem
> precisa dos números é o seed da Baia, na Task 9.

**Files:**
- Modify: `models.py` (classe do `rdo_subempreitada_apontamento`), `migrations.py`, `services/resultado_atividade_service.py` (devolve o ramo removido na Task 5), 🔴 **`cronograma_views.py`** (o escritor que falta — ver Step 3b)
- Test: `tests/test_resultado_fatia2_custo_nao_mo.py` (tira os `xfail`)

- [x] **Step 1: A decisão já existe** — opção B (markup uniforme), respondida em
      01/09 (📖 `2026-09-01-decisoes-respondidas.md`). ⚠️ O `RATIFICAR` com o
      dono segue pendente e é escolha comercial, mas **não bloqueia o porte**.
      **Não pare aqui.**
- [ ] **Step 2: Tirar o `xfail` dos testes da Fatia 2 e ver o RED.** 🔬 O arquivo
      tem 6 testes e **1** deles toca subempreitada: o `xfailed` do gate sobe
      **1** na Task 5 e volta **1** aqui. Com `strict=True`, marcador que sobra
      depois do conserto **falha o gate por XPASS**.
- [ ] **Step 3: Migration 321** — `verba`, `lucro`, `pai` em `rdo_subempreitada_apontamento` (repõe a 195; 🔬 a tabela já tem `tarefa_cronograma_id`, faltam os três).
- [ ] **Step 3b: 🔴 Portar `_registrar_custo_subempreitada` — o escritor que esta task pressupõe e que NÃO existe na `main`**

🔬 Achado do pré-voo de 02/09, e **nenhum dos dois planos o via**:
📖 `tests/test_resultado_fatia2_custo_nao_mo.py:184` (na branch) faz
`from cronograma_views import _registrar_custo_subempreitada`, e 🔬 a função tem
**zero** ocorrências na `main` (`grep -rn "_registrar_custo_subempreitada" --include=*.py .`
→ vazio). Na branch ela existe: `cronograma_views.py:917` (definição) e `:1035`
(chamada). E 🔬 `cronograma_views.py` **não é citado nenhuma vez** no corpo
original deste plano.

⚠️ **Não porte por cópia do arquivo.** As linhagens são disjuntas e os dois
`cronograma_views.py` não têm nada a ver: `main` tem 4396 linhas / 186.853
bytes; a branch, 103.217 bytes. A `main` **já tem** as rotas de subempreitada
(`apontar_subempreitada` e vizinhas) — o que falta nelas é **gravar custo com
verba/lucro**, que é exatamente o que o teste exercita.

Porte **só a função**, localizando o sítio **por conteúdo** (junto de
`apontar_subempreitada`, nunca por número de linha), e adapte ao
`GestaoCustoFilho` de hoje — 📖 o mapa de tipos (`SALARIO → MAO_OBRA_DIRETA`) é o
de hoje, não o de 15/06.

⚠️ **Sem este step a Task 8 não fecha:** mesmo com a migration 321 e o ramo
devolvido no Step 4, falta o escritor, o Step 5 não vê passar, o `xfail` não sai
e — por ser `strict=True` — o gate fecha vermelho dos dois lados, por XPASS ou
por falha.

- [ ] **Step 4: Devolver o ramo de subempreitada em `custo_nao_mo_atividade`.**
- [ ] **Step 5: Rodar e ver passar, dupla execução da migration.**
- [ ] **Step 6: Commit**

```bash
git add models.py migrations.py services/resultado_atividade_service.py cronograma_views.py tests/test_resultado_fatia2_custo_nao_mo.py
git commit -m "feat(espinha): Fatia 2 §D — verba/lucro/pai na subempreitada (migration 321)"
```

---

### Task 9 — os scripts da Baia e o E2E

Os três scripts são **Baia-específicos** por desenho (`gerar_importacao_baia_rev10.SERVICOS`). Portá-los é portar um caso de produção real, não uma feature genérica — o importador genérico é trabalho novo e **fica fora deste plano**.

**Files:**
- Create: `scripts/{seed_templates_baia_rev10,importar_baia_easypanel}.py`
- 🔴 **Sobrescrever, não criar:** `scripts/criar_orcamento_baia_rev10.py` — 🔬 **já existe e diverge** (103 linhas de diferença): a `main` tem o `main()` velho, que pega o primeiro ADMIN; a branch tem `criar_orcamento_baia(admin_id, xlsx_path)`, a forma reusável que o E2E chama. Trate como **merge consciente**, não como arquivo novo.
- Test: `tests/test_import_baia_e2e.py`, `tests/test_fatia5_inteligencia.py`
- ✅ **Nada a fazer:** `tests/test_rdo_edicao_preserva_tarefa.py` 🔬 **já está portado, byte a byte idêntico** à branch (chegou em `b30923b5`, 22/07).

- [ ] **Step 1: O xlsx já está na árvore.** 🔬 24/08: `obra_kabod/IMPORTACAO_Baia_REV10_completa.xlsx` existe no `main` de hoje — sobreviveu à fratura porque estava versionado.

🔴 **Emenda de 03/09 — não confira por hash, a conferência falha.** 🔬 O md5 da
`main` é `607941960fb37cd9d772b2352650b2f4` e o da branch é
`7338367d9f23341337c0f43bb3c6025d`; os blobs são distintos e os tamanhos são
**14609** vs **14608** bytes. São arquivos diferentes, quase certamente o mesmo
conteúdo regravado (xlsx é zip e carimba timestamps). Quem ler este Step como
"pare se o hash divergir" **para sem motivo**. **Confira por conteúdo** — as
abas e a lista de serviços —, nunca por byte.
- [ ] **Step 2: Portar os testes primeiro e ver o RED.**
- [ ] **Step 3: Portar os três scripts.**
- [ ] **Step 4: Rodar e ver passar** — inclusive a idempotência do re-import no mesmo tenant, que a branch garantia.
- [ ] **Step 5: Commit**

```bash
git add scripts/criar_orcamento_baia_rev10.py scripts/seed_templates_baia_rev10.py scripts/importar_baia_easypanel.py tests/test_import_baia_e2e.py tests/test_fatia5_inteligencia.py tests/test_rdo_edicao_preserva_tarefa.py
git commit -m "feat(espinha): scripts de importacao da Baia REV10 e o E2E ponta a ponta"
```

---

### Task 10 — gate, e aposentar o documento que engana

- [ ] **Step 1: Gate completo sobre a árvore que vai ser integrada**

```bash
bash run_tests.sh --gate
```
Referência: o gate do `main` do mesmo dia. Registre passed/skipped/deselected/xfailed e o tempo. **Mescle o `main` na branch ANTES do gate** — a Fase 8 e este porte tocam contabilidade e cronograma, e um gate sobre uma árvore que já não existe não vale nada.

- [ ] **Step 2: `ruff` medido contra a base da branch, com a MESMA config.** Quantas você acrescentou, não quantas existem.

- [ ] **Step 3: Dupla execução das migrations 319, 320 e 321 no banco de dev.**

- [ ] **Step 4: Aposentar `ESTADO_design_espinha_financeira.md`**

O arquivo já ganhou em 23/08 um aviso 🔴 de que descreve a branch e não o sistema. Com o porte feito, **o aviso vira falso pela metade** e o documento passa a enganar de novo — parte do que ele descreve existe, parte não.

Reescreva o cabeçalho dizendo, com procedência: o que foi portado e em que commit; o que **não** foi (importador genérico; e a Fatia 2 §D, se a Task 8 tiver sido cortada); e que os "PRÓXIMOS PASSOS" de 15/06 são de outra árvore. O item 6 daquela lista ("Merge do PR #6") deixa de existir: o PR não é mesclável — 🔬 as linhagens são disjuntas, `git rev-list --count origin/fix/fase-0-estancar..main` devolve **722** (🔬 03/09; meça no dia, o número anda), e `git merge-base` devolve **vazio** — nada em comum. **Diga isso por escrito**, senão alguém vai tentar mesclar.

- [ ] **Step 5: `ESTADO-ATUAL.md`** — registre o porte e **nomeie os resíduos** em vez de dizer que ficou redondo. Comece por: importador genérico (não feito, é trabalho novo); Fatia 2 §D se cortada; SPI ainda `None` porque as datas por atividade dependem do MPP; e a decisão do telhado viga I.

- [ ] **Step 6: Commit de fecho**

```bash
git add ESTADO-ATUAL.md ESTADO_design_espinha_financeira.md
git commit -m "chore(espinha): fecho do resgate — o que entrou, o que nao entrou, e por que o PR #6 nao e mesclavel"
```

---

## Self-review deste plano

**Cobertura:** os cinco módulos, os quatro templates, os três scripts, os sete arquivos de teste e as três colunas ausentes da medição de 23/08 têm task. As decisões travadas D1, D3/DC3, D4, D5, D6/DC8 e as ADRs 0004/0005 estão como Global Constraints, e a mais frágil delas (orçado = baseline congelado) tem um passo de reconfirmação explícito antes do read-model.

**O que este plano NÃO faz, de propósito:**
1. **Importador genérico** — o `importar_baia` é Baia-específico; "qualquer obra pela planilha" precisa de parser novo. É trabalho novo, não porte.
2. **Datas/durações por atividade** (o que ligaria o SPI, hoje `None`) — depende de exportar o `.mpp` para XML. Frente própria.
3. **Material direto na UI** e o refino do EVM F3-4 — refinos listados em 15/06, sem dono.
4. **Mesclar o PR #6.** Não é possível: as linhagens são disjuntas. O que este plano faz é **portar**, e a Task 10 escreve isso onde alguém vai procurar.

**Os dois bloqueios que você deve conhecer antes de começar:**
1. A **Task 8** depende de uma decisão de negócio (verba, lucro %, opção A/B/C). As demais não.
2. A **numeração das migrations** colide com a Fase 8. Confira o máximo real do repo no dia do commit; não reserve faixa.
