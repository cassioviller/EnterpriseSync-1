# Onda 4 — O Relatório Passa a Funcionar Implementation Plan

> **Estado em 2026-08-25 (varredura de fecho):** 🟡 **ABERTO — duas tasks bloqueadas** — 7 tasks. As Tasks 4 e 5 esperam **D4** (apagar ou consertar `relatorios_financeiros_avancados.py`) e **D3** (as seis rotas mortas de veículos). ⚠️ A Task 2 **torna exploitável** um furo que a Onda 2 fecha — não a execute antes dela.
>
> Escrito na varredura de 25/08. Índice de estado de todos os planos e specs em
> `docs/planos-em-aberto-2026-08-25.md`.


> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) ou superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer a DRE e o balancete fecharem entre si, e devolver ao ar os quatro relatórios que **nunca funcionaram** — cada um quebrado por atributo ou classe inexistente, e cada um com o erro engolido por um `except` que devolve forma vazia.

**Architecture:** Duas naturezas diferentes. **(a) A contabilidade erra de aritmética**: a DRE conta um lado das partidas e o balancete decide a coluna depois de já ter normalizado o sinal — os dois estão errados de formas que se cancelam na leitura casual e nunca na conferência. **(b) O resto erra de existência**: `km_rodado` quando a coluna é `km_percorrido`, `ativo=True` numa tabela sem `ativo`, `AlocacaoVeiculo` que não existe no repo. Estes só precisam de um teste que os **chame**, porque nenhum era chamado por teste nenhum — foi assim que sobreviveram.

**Tech Stack:** Flask, SQLAlchemy 2.0.41, PostgreSQL, pytest.

**Spec:** `docs/superpowers/plans/2026-08-25-fecho-dos-114-achados.md` (Onda 4) — evidência em `docs/auditoria/achados-code-review-2026-08-25.md` §2, §5, §4, §9.

## Global Constraints

- **Relatório não esconde o que não sabe.** Não classificado aparece **como não classificado, com o valor**. DRE que não fecha **mostra a diferença**. Indicador sem base sai como "sem base", nunca `0%` nem `inf`. É a regra que a Fase 8 já escreveu — vale desde já.
- **Nenhum `except` devolve forma vazia com `success: true`.** 📖 É o que manteve `relatorios_financeiros_avancados.py` inteiro morto sem ninguém notar. Erro vira 500 ou mensagem, nunca `{}`.
- **Todo relatório desta onda ganha um teste que o CHAMA.** Não basta testar a função pura: 🔬 os quatro quebravam na primeira linha da rota, e passavam em teste de fumaça com base vazia.
- **TDD sem exceção**, com o RED citado no commit.
- **Gate ao fim:** `bash run_tests.sh --gate`. Régua: **2560 passed, 6 skipped, 201 deselected, 2 xfailed**.

---

## 🔴 Decisões antes de começar

### D3 — `views/vehicles.py`: apagar ou consertar?

🔬 **Nenhum template ou JS referencia a família `main.*` de veículos.**
`veiculos_editar.html` posta para `frota.editar`; `/veiculos` redireciona para
`frota.lista`. As rotas estão registradas e alcançáveis por URL, mas mortas pela
interface — e 📖 **seis delas quebram na primeira requisição**: `:192`
(`PassageiroVeiculo` não importado no escopo do módulo → NameError → `-1` →
rollback com a mensagem **falsa** "já estavam registrados como passageiros"),
`:716` (`form.km_custo`/`form.litros` não existem em `CustoVeiculoForm` — **a
edição de custo nunca gravou**), `:925` (`from sqlalchemy import Funcionario,
Obra` → ImportError em toda requisição), `:1321` (`aprovado` não é coluna →
commit vazio com flash de sucesso), `:834` (dashboard/relatórios leem campos
inexistentes), `:665` (BuildError **depois** do commit → "Erro ao excluir uso"
numa exclusão que funcionou).

**Recomendação: apagar.** Consertar código que nenhuma tela chama é criar
manutenção para uma funcionalidade que ninguém pediu. A **Task 5** assume apagar.
Se você preferir consertar, diga — vira um plano próprio, porque são seis
correções independentes com telas a reconstruir.

### D4 — `relatorios_financeiros_avancados.py` tem dono?

🔴 🔬 O módulo é **inteiramente inoperante**, por seis defeitos independentes, e
responde `{"success": true, "dados": {}}` em vez de errar. Se ninguém o usa —
e o fato de ninguém ter reclamado em meses sugere que não — **apagar é mais
honesto que consertar**. A Task 4 pergunta antes de agir.

---

## File Structure

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `contabilidade_utils.py` | Modificar `:621`, `:871`, `:457`, `:534`, `:221` | Tasks 1-2 |
| `contabilidade_views.py` | Modificar `:619`, `:463` | Task 1 |
| `views/almoxarifado/relatorios.py` | Modificar `:39`, `:286` | Task 3 |
| `views/almoxarifado/movimentos.py` | Modificar `:1239`, `:1302` | Tasks 3, 6 |
| `relatorios_financeiros_avancados.py` | Apagar **ou** modificar | Task 4 — depende da D4 |
| `views/vehicles.py` | Apagar seis rotas | Task 5 — depende da D3 |
| `services/evm.py` | Modificar `:130`, `:100` | Task 7 |
| `services/medicao_service.py` | Modificar `:178` | Task 7 |
| `services/custo_orcado.py` | Modificar `:84` | Task 7 |
| `tests/test_onda4_relatorio_funciona.py` | **Criar** | Todos os testes desta onda |

---

### Task 1: A DRE e o balancete passam a fechar

> 🔴 **Os dois erram, de formas diferentes, e o resultado é que discordam
> permanentemente entre si no mesmo mês.**

**Files:**
- Modify: `contabilidade_utils.py:621` (DRE), `:871` (balancete), `:457` (Balanço)
- Modify: `contabilidade_views.py:619` (o mesmo defeito do balancete, copiado)
- Test: `tests/test_onda4_relatorio_funciona.py` (criar)

**Interfaces:**
- Consumes: `models.PartidaContabil`, `models.LancamentoContabil`, `models.PlanoContas`.
- Produces: nada. As três funções mantêm assinatura e forma de retorno.

📖 **O defeito da DRE** (`:621`): `if tipo_esperado: if partida.tipo_partida ==
tipo_esperado: total += valor`. Só um lado entra. Estornar uma despesa de R$ 840
grava a partida inversa **correta** (`contabilidade_views.py:479-487`), mas o
crédito é filtrado fora — **a DRE reporta os R$ 840 para sempre.**

📖 **O defeito do balancete** (`:871`): `saldo_atual` já foi normalizado pela
natureza da conta (`if devedora: debito - credito; else: credito - debito`), e
**depois** disso vem `'saldo_devedor': saldo_atual if saldo_atual > 0`. O saldo
credor normal de uma conta CREDORA é positivo e cai na **coluna de débito**. Um
lançamento D Caixa 1.000 / C Receita 1.000 dá `total_saldo_devedor = 2.000`,
`total_saldo_credor = 0`. **Um balancete de verificação que nunca amarra.**

- [ ] **Step 1: Write the failing test**

Create `tests/test_onda4_relatorio_funciona.py`:

```python
"""Onda 4 — o relatório passa a funcionar.

A regra desta onda: todo teste CHAMA o relatório. Os quatro que nunca
funcionaram quebravam na primeira linha da rota e passavam em teste de fumaça
com base vazia — foi assim que sobreviveram meses.
"""
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

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
        app.secret_key = 'test-onda4-relatorio'
    yield


def _lancamento_balanceado(admin_id, conta_debito, conta_credito, valor,
                           quando=None):
    """Um lançamento de partida dobrada, pelo caminho normal."""
    from models import LancamentoContabil, PartidaContabil

    lanc = LancamentoContabil(
        admin_id=admin_id, data_lancamento=quando or date(2026, 7, 15),
        historico=f'teste {uuid.uuid4().hex[:6]}', valor_total=valor)
    db.session.add(lanc)
    db.session.flush()
    db.session.add(PartidaContabil(
        admin_id=admin_id, lancamento_id=lanc.id, conta_codigo=conta_debito,
        tipo_partida='DEBITO', valor=valor))
    db.session.add(PartidaContabil(
        admin_id=admin_id, lancamento_id=lanc.id, conta_codigo=conta_credito,
        tipo_partida='CREDITO', valor=valor))
    db.session.flush()
    return lanc


# ---------------------------------------------------------------------------
# Task 1 — DRE e balancete
# ---------------------------------------------------------------------------

def test_balancete_de_um_lancamento_balanceado_amarra():
    """🔴 `contabilidade_utils.py:871` — a coluna era decidida DEPOIS de o
    sinal já ter sido normalizado pela natureza da conta.

    D Caixa 1.000 / C Receita 1.000 dava devedor 2.000, credor 0.
    """
    from contabilidade_utils import gerar_balancete

    with app.app_context():
        t = um_tenant('onda4_balan', com_fatos=False)
        _lancamento_balanceado(t.admin_id, '1.1.01', '4.1.01',
                               Decimal('1000.00'))
        db.session.commit()

        balancete = gerar_balancete(t.admin_id, 2026, 7)
        totais = balancete['totais']
        assert Decimal(str(totais['total_saldo_devedor'])) == \
            Decimal(str(totais['total_saldo_credor'])), (
                f"balancete não amarra: devedor "
                f"{totais['total_saldo_devedor']} × credor "
                f"{totais['total_saldo_credor']}")


def test_estorno_some_da_dre():
    """🔴 `contabilidade_utils.py:621` — a DRE contava só um lado.

    O estorno grava a partida inversa correta, mas o crédito era filtrado
    fora: a DRE reportava a despesa PARA SEMPRE, discordando do balancete no
    mesmo mês.
    """
    from contabilidade_utils import gerar_dre

    with app.app_context():
        t = um_tenant('onda4_dre', com_fatos=False)
        # despesa de 840, e o estorno dela
        _lancamento_balanceado(t.admin_id, '6.1.01', '1.1.01',
                               Decimal('840.00'))
        _lancamento_balanceado(t.admin_id, '1.1.01', '6.1.01',
                               Decimal('840.00'))
        db.session.commit()

        dre = gerar_dre(t.admin_id, date(2026, 7, 1), date(2026, 7, 31))
        despesas = Decimal(str(dre.get('despesas_operacionais', 0)))
        assert despesas == Decimal('0'), (
            f'a despesa estornada ainda soma {despesas} na DRE')
```

⚠️ **Confirme os nomes reais das funções e das chaves do retorno antes de
rodar** — este teste é escrito contra a forma que o review descreveu, e o nome
pode diferir:

```bash
grep -n "^def gerar_dre\|^def gerar_balancete\|^def gerar_balanco" contabilidade_utils.py
```

E confirme que os códigos `1.1.01`, `4.1.01` e `6.1.01` existem no plano semeado
para o tenant do fixture; se o seed não os criar, crie-os no teste.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_onda4_relatorio_funciona.py -v`
Expected: FAIL — balancete devedor 2000 × credor 0, e despesa estornada ainda somando 840.

- [ ] **Step 3: Write minimal implementation**

**3a.** DRE (`:618-628`) — o `tipo_esperado` passa a dizer qual é o **lado
positivo**, não qual é o único lado que conta:

```python
                for partida in partidas:
                    valor = Decimal(str(partida.valor))

                    if tipo_esperado:
                        # `tipo_esperado` diz qual lado SOMA, não qual lado é o
                        # único que conta. Ignorar o outro fazia o estorno —
                        # que grava a partida inversa correta — nunca reduzir
                        # o resultado: a DRE reportava a despesa para sempre e
                        # discordava permanentemente do balancete.
                        if partida.tipo_partida == tipo_esperado:
                            total += valor
                        else:
                            total -= valor
                    else:
                        if partida.tipo_partida == 'CREDITO':
                            total += valor
                        else:
                            total -= valor
```

**3b.** Balancete (`:869-882`) — a coluna sai da **natureza**, não do sinal já
normalizado:

```python
            # `saldo_atual` JÁ foi normalizado pela natureza logo acima
            # (devedora: D-C; credora: C-D), então "positivo" significa
            # "saldo normal da conta", não "devedor". Decidir a coluna pelo
            # sinal punha o saldo credor normal de uma conta CREDORA na coluna
            # de débito: D Caixa 1.000 / C Receita 1.000 dava devedor 2.000 e
            # credor 0 — um balancete de verificação que nunca amarra.
            e_devedora = (conta.natureza or '').upper().startswith('DEV')
            if e_devedora:
                saldo_devedor = saldo_atual if saldo_atual > 0 else Decimal('0')
                saldo_credor = abs(saldo_atual) if saldo_atual < 0 else Decimal('0')
            else:
                saldo_credor = saldo_atual if saldo_atual > 0 else Decimal('0')
                saldo_devedor = abs(saldo_atual) if saldo_atual < 0 else Decimal('0')
```

usando `saldo_devedor`/`saldo_credor` no dicionário **e** nos dois totais.

⚠️ Confirme o vocabulário real de `PlanoContas.natureza`:
`grep -n "natureza" models.py | head -5` — se for `'DEVEDORA'`/`'CREDORA'`, o
`startswith('DEV')` serve; se for outro, ajuste.

**3c.** O mesmo defeito está copiado em `contabilidade_views.py:619` — aplique lá.

**3d.** Balanço (`:457`) — acumular as contas de resultado no PL, e parar de usar
`abs(saldo)`, que soma **prejuízo acumulado ao patrimônio**.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_onda4_relatorio_funciona.py -v`
Expected: PASS

Run: `python -m pytest tests/ -k contabil -q`
Expected: PASS, mesma contagem de antes.

- [ ] **Step 5: Commit**

```bash
git add contabilidade_utils.py contabilidade_views.py tests/test_onda4_relatorio_funciona.py
git commit -m "fix(contabilidade): a DRE e o balancete passam a fechar

RED: balancete devedor 2000 x credor 0; despesa estornada somando 840 na DRE

A DRE contava so um lado das partidas: o estorno grava a inversa correta, mas
o credito era filtrado fora e a despesa ficava para sempre.

O balancete decidia a coluna pelo SINAL, depois de o sinal ja ter sido
normalizado pela natureza da conta. Saldo credor normal de conta CREDORA caia
na coluna de debito.

Os dois erravam de formas diferentes, e o resultado era discordarem
permanentemente entre si no mesmo mes."
```

---

### Task 2: A integração contábil para de dar 500

**Files:**
- Modify: `contabilidade_utils.py:221`, `:182`, `:201`, `:206`, `:534`
- Test: `tests/test_onda4_relatorio_funciona.py` (acrescentar)

📖 As três funções `contabilizar_*` leem atributos que **não existem**:
`f.salario_bruto` (`FolhaPagamento` tem `salario_base`/`total_proventos`),
`proposta.data_aprovacao`, `nota.fornecedor_nome`, `nota.valor_icms`. **`POST
/contabilidade/api/processar-integracao` dá 500 nos três tipos.**

🔴 E mesmo corrigido, `contabilizar_entrada_material` debita `valor_produtos +
valor_icms` contra crédito de `valor_total`, disparando "Lançamento
desbalanceado" **sempre que o ICMS está embutido no preço — que é a norma
brasileira.**

📖 `:534` — o mapa de prefixos da DRE está **invertido** em relação a
`criar_plano_contas_padrao` e deslocado um grupo em relação a
`financeiro_seeds.py`: locação de equipamento reporta como CMV.

> ⚠️ **Este item conversa com a Fase 8.** O plano de 24/08
> (`2026-08-24-fase-8-plano-de-contas-canonico.md`) canoniza o plano de contas e
> resolve a divergência entre os seeders na raiz. **Se a Fase 8 for executada
> antes, refaça o mapa depois dela, não agora** — senão você conserta o mapa
> contra um vocabulário que vai mudar.

- [ ] **Step 1-5:** um teste que **chama** o endpoint para cada um dos três
  tipos, RED (500), correção dos nomes de atributo contra `models.py`, a
  aritmética do ICMS, verde, commit.

⚠️ 🔴 **A Task 2.7 da Onda 2 depende desta.** 📖 `contabilidade_views.py:1377`
aceita `origem_id` do request e lança sob o `admin_id` **do documento** — hoje só
o 500 desta task impede a escrita cross-tenant de aterrissar. **Quando esta task
fechar, aquilo vira exploitável.** Confirme que a Onda 2 já entrou antes de
fechar esta.

---

### Task 3: Os dois relatórios do almoxarifado que nunca rodaram

**Files:**
- Modify: `views/almoxarifado/relatorios.py:39`, `:286`; `views/almoxarifado/movimentos.py:1239`
- Test: `tests/test_onda4_relatorio_funciona.py` (acrescentar)

🔴 📖 `relatorios.py:39` — `AlmoxarifadoEstoque.query.filter_by(admin_id=...,
ativo=True)`, e `AlmoxarifadoEstoque` (`models.py:5546`) **não tem coluna
`ativo`**. 🔬 Reproduzido: `InvalidRequestError: Entity namespace for
"almoxarifado_estoque" has no property "ativo"`. Nada captura na rota — **500
seco. O relatório "Posição de Estoque" nunca funcionou.**

🔴 📖 `movimentos.py:1239` — `filter_by(id=..., funcionario_id=...)`; a coluna é
`funcionario_atual_id`. 🔬 A rota de item único (`:1019`) **acerta**. Esta é
engolida pelo `except Exception` de `:1381` → **toda devolução de carrinho
serializado devolve 500 "Erro ao processar operação"** sem mensagem útil.

- [ ] **Step 1: Write the failing test**

```python
# ---------------------------------------------------------------------------
# Task 3 — o almoxarifado
# ---------------------------------------------------------------------------

def test_relatorio_de_posicao_de_estoque_abre():
    """🔴 `relatorios.py:39` — `ativo=True` numa tabela sem coluna `ativo`.

    InvalidRequestError, 500 seco, nada captura. Nunca funcionou.
    """
    with app.app_context():
        t = um_tenant('onda4_posic', com_fatos=False)
        admin_id = t.admin_id

    resposta = cliente_de(admin_id).get(
        '/almoxarifado/relatorios?relatorio_tipo=posicao_estoque')
    assert resposta.status_code == 200, (
        f'relatório de posição de estoque devolveu {resposta.status_code}')


def test_relatorio_de_alertas_sobrevive_a_estoque_minimo_nulo():
    """`relatorios.py:286` — `estoque_minimo` é nullable e aqui não há guarda.

    `dashboard.py:52` e `itens.py:61` guardam; aqui uma linha NULL derruba.
    """
    from models import AlmoxarifadoItem

    with app.app_context():
        t = um_tenant('onda4_alerta', com_fatos=False)
        suf = uuid.uuid4().hex[:8]
        item = AlmoxarifadoItem(
            admin_id=t.admin_id, nome=f'Sem mínimo {suf}', codigo=f'SM{suf}',
            tipo_controle='CONSUMIVEL', unidade_medida='UN',
            estoque_minimo=None)
        db.session.add(item)
        db.session.commit()
        admin_id = t.admin_id

    resposta = cliente_de(admin_id).get(
        '/almoxarifado/relatorios?relatorio_tipo=alertas')
    assert resposta.status_code == 200
```

⚠️ Confirme a URL e o nome do parâmetro:
`grep -n "route.*relatorios\|relatorio_tipo" views/almoxarifado/relatorios.py | head`

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_onda4_relatorio_funciona.py -k almoxarifado -v`
Expected: FAIL — 500 nos dois.

- [ ] **Step 3: Write minimal implementation**

**3a.** `relatorios.py:39` — tirar o `ativo=True`. 🔬 Confirme antes qual é o
filtro que se **queria** ali: `grep -n "class AlmoxarifadoEstoque" -A 30 models.py`.
Se a intenção era "lote não descartado", o filtro é por `status`, não por `ativo`.

**3b.** `movimentos.py:1239` — `funcionario_id` → `funcionario_atual_id`, igual à
rota irmã de `:1019`.

**3c.** `relatorios.py:286` — guarda de `None`, no mesmo formato de
`dashboard.py:52`.

- [ ] **Step 4-5:** verde, e commit.

---

### Task 4: `relatorios_financeiros_avancados.py` — apagar ou consertar

> ⚠️ **BLOQUEADA PELA DECISÃO D4.**

🔬 Seis defeitos independentes, todos verificados: `UsoVeiculo.km_rodado` (a
coluna é `km_percorrido`, em **seis** lugares — `:154`, `:246`, `:407`, `:516`,
`:683`, `:810`); `UsoVeiculo.horas_uso` (`:812`) e `CustoVeiculo.km_atual`
(`:830`), que não existem (`km_veiculo` existe); `AlocacaoVeiculo` (`:470`,
`:472`) — **classe inexistente no repo**; `case([(cond, val)], else_=0)`
(`:220-225`) — a forma de lista **saiu no SQLAlchemy 2.0** e o ambiente roda
2.0.41 (`ArgumentError`, reproduzido); `NameError` em `:876` (`custo_per_km` × o
parâmetro `custo_por_km`); e um **produto cartesiano** em `:512` que junta
`CustoVeiculo` e `UsoVeiculo` pelo mesmo `Veiculo` e soma os dois num GROUP BY,
inflando `custo_por_km` ~10×.

- [ ] **Se D4 = apagar:** apagar o módulo, a rota e o template; um teste que prove
  que a URL devolve 404; commit explicando que **seis meses de `success: true`
  sobre `{}` é a prova de que ninguém consumia**.
- [ ] **Se D4 = consertar:** seis correções, seis testes que chamam o endpoint, e
  o `except` que devolvia `{}` vira erro de verdade. **Nesse caso isto vira plano
  próprio** — é grande demais para uma task.

---

### Task 5: Apagar as seis rotas mortas de veículos

> ⚠️ **BLOQUEADA PELA DECISÃO D3.**

- [ ] **Step 1:** provar que estão mortas, antes de apagar:

```bash
grep -rn "main\.detalhes_veiculo\|main\.editar_veiculo\|main\.lancamentos_veiculos\|main\.dashboard_veiculo\|main\.historico_veiculo\|main\.relatorios_veiculos" templates/ static/ --include=*.html --include=*.js
```
Expected: **nenhuma ocorrência**. Se aparecer alguma, **pare** — a rota não está morta e a D3 muda.

- [ ] **Step 2-4:** teste que prova 404 nas seis URLs, apagar, verde, commit.

---

### Task 6: O vocabulário partido do almoxarifado

**Files:**
- Modify: `views/almoxarifado/movimentos.py:1302`
- Test: `tests/test_onda4_relatorio_funciona.py` (acrescentar)

📖 Grava `'EM_MANUTENCAO'` e `'INUTILIZADO'`, fora do vocabulário de
`models.py:5560` (`MANUTENCAO`, `DESCARTADO`). `funcionario_perfil.html:977` e
`itens_detalhes.html:246` testam `'MANUTENCAO'`; `dashboard.py:93` e
`relatorios.py:296` casam `EM_MANUTENCAO`. **O vocabulário está partido no meio**
— item devolvido avariado não mostra selo em duas telas.

- [ ] **Step 1-5:** escolher **um** vocabulário (o de `models.py`, que é a
  definição), migrar o dado existente com contagem antes e depois, alinhar as
  quatro leituras, e deixar teste guardando que só um vocabulário existe.

⚠️ Isto **precisa de migration** se houver linha gravada com o vocabulário
errado. Meça primeiro:
`SELECT status, count(*) FROM almoxarifado_estoque GROUP BY status;`

---

### Task 7: EVM e medição param de mentir

**Files:**
- Modify: `services/evm.py:130`, `:100`; `services/medicao_service.py:178`; `services/custo_orcado.py:84`
- Test: `tests/test_onda4_relatorio_funciona.py` (acrescentar)

🔴 📖 `evm.py:130` — `_pv_ate_hoje` soma só `etapa['meses']`, que
`montar_fisico_financeiro` preenche **exclusivamente para etapas `entregavel`**,
enquanto o BAC (`custo_orcado_da_obra`) soma **toda** linha de custo, inclusive
`periodo`. Qualquer obra com custo indireto recebe **SPI estruturalmente
inflado** e SV positivo mesmo estando em dia.

📖 `evm.py:100` — `eac = (bac / _d(cpi)) if cpi else bac`. `cpi == 0.0` (EV=0,
AC>0 — **o pior cenário possível**) é falsy e vira "ainda sem CPI": reporta
`vac = 0`, exatamente no orçamento. E o payload emite `cpi: 0.0`,
**indistinguível de desempenho zero real**, enquanto `None` significa "sem dado".

🔴 📖 `medicao_service.py:178` — `gerar_medicao_quinzenal` usa
`calcular_percentual_item` (0 sem vínculo de cronograma) mas **omite o fallback
`percentual_do_servico_na_obra`** que `_recalcular_imc_avanco` tem. Essas obras
geram **medição vazia para sempre** (`perc_periodo = max(0, 0 - 60) = 0` a cada
ciclo), com extrato PDF em 0%.

- [ ] **Step 1: Write the failing test**

```python
# ---------------------------------------------------------------------------
# Task 7 — EVM
# ---------------------------------------------------------------------------

def test_cpi_zero_nao_e_confundido_com_ausencia_de_cpi():
    """🔴 `services/evm.py:100` — `if cpi` trata 0.0 como "sem dado".

    EV=0 com AC>0 é o PIOR cenário possível, e era reportado como
    `vac = 0` — exatamente no orçamento.
    """
    import inspect

    from services import evm
    fonte = inspect.getsource(evm)
    assert 'if cpi else bac' not in fonte, (
        'cpi == 0.0 ainda cai no ramo de "sem CPI"')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_onda4_relatorio_funciona.py -k cpi -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
        # `if cpi` era falsy para cpi == 0.0 — EV=0 com AC>0, o pior cenário
        # possível — e o relatório dizia "exatamente no orçamento". `None`
        # significa "nada gasto ainda"; 0.0 significa "gastou e não entregou".
        # Os dois precisam de tratamento diferente.
        if cpi is None:
            eac = bac
        elif cpi == 0:
            eac = None          # sem projeção possível: EV é zero
        else:
            eac = bac / _d(cpi)
        etc = (eac - ac) if eac is not None else None
        vac = (bac - eac) if eac is not None else None
```

e o payload passa a emitir `None` em vez de número para `eac`/`etc`/`vac` nesse
caso — 📖 a regra da casa: *"indicador sem base sai como 'sem base', nunca 0% nem
inf"*.

⚠️ **Confira os consumidores do payload antes** — uma tela que faça
`float(eac)` sem checar `None` passa a quebrar:
`grep -rn "'eac'\|\.eac" templates/ static/ --include=*.html --include=*.js | head`

**3b.** `_pv_ate_hoje` — somar as mesmas linhas que o BAC soma, ou documentar
explicitamente que PV cobre só `entregavel` **e** fazer o BAC do SPI cobrir o
mesmo recorte. **Os dois lados da razão precisam vir do mesmo conjunto.**

**3c.** `medicao_service.py:178` — acrescentar o fallback
`percentual_do_servico_na_obra`, igual ao de `_recalcular_imc_avanco`.

- [ ] **Step 4: Run the full gate**

Run: `bash run_tests.sh --gate`
Expected: **2560 passed, 6 skipped, 201 deselected, 2 xfailed** — ou mais verdes.

- [ ] **Step 5: Commit**

---

## Fecho da onda

- [ ] `bash run_tests.sh --gate` verde, com a contagem registrada.
- [ ] D3 e D4 registradas aqui, com o que foi decidido e por quê.
- [ ] `docs/auditoria/achados-code-review-2026-08-25.md` — marcar os 11 achados.
- [ ] 🔬 Nenhum `except` desta onda devolve `success: true` sobre forma vazia:
      `grep -rn "'success': True" --include=*.py . | grep -v __pycache__ | grep -v tests/`
      — conferir um a um os que sobrarem.
