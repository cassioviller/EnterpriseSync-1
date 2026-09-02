# A janela que andou — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o fixture de `PedidoCompra` dos testes de alçada nascer com data RELATIVA a hoje, para que a janela rolante do acumulado pare de derrubar testes verdes quando o calendário anda.

**Architecture:** Uma linha de fixture, uma guarda de comportamento e uma varredura da família copiada. A correção NÃO toca produção: `services/alcada_compras.py` está certo e não muda. O que muda é a data que o teste escreve no banco — de absoluta para relativa — mais uma guarda que falha com mensagem de fixture vencido em vez de mensagem de faixa errada.

**Tech Stack:** pytest 8.4.1, SQLAlchemy 2.x, Flask, PostgreSQL. Suíte roda por `bash run_tests.sh --gate` (= `pytest tests/ -m "not browser"`).

**Spec:** Não há spec — este plano nasce de um diagnóstico. A evidência que faz as vezes de spec está na seção "Evidência" abaixo, e é dela que cada task argumenta.

## Evidência

`tests/test_alcadas_avancadas.py:853` grava data ABSOLUTA:

```python
p = PedidoCompra(fornecedor_id=fornecedor_id, data_compra=date(2026, 8, 1), ...)
```

`services/alcada_compras.py:670` filtra por janela ROLANTE:

```python
PedidoCompra.data_compra >= date.today() - timedelta(days=dias),
```

`dias` vem de `janela_de_fracionamento(admin_id)`, que cai no default da coluna
`ConfiguracaoEmpresa.janela_fracionamento_dias` = **30** quando o tenant não
configura (é o caso de `_cfg_tenant`, que não passa o campo).

| data de execução | corte `today - 30` | `2026-08-01 >= corte` | resultado |
|---|---|---|---|
| 2026-08-31 | 2026-08-01 | True (comparação inclusiva) | gate verde |
| 2026-09-01 | 2026-08-02 | **False** | 2 testes vermelhos |

Sonda executada em 01/09/2026 (`probe_janela.py`), isolando a janela como
única variável do cenário do teste que falha:

```
PROBE janela=   30d  faixa_efetiva=#1  esperado=#3  FALHA
PROBE janela= 3650d  faixa_efetiva=#3  esperado=#3  OK
```

Cadeia causal completa: acumulado do fornecedor cai a 0 → `valor_para_alcada`
devolve a linha (4.900) em vez de 40.000 → `decisao_de_alcada` não vê
`por_acumulado` diferente da base → sem `MOTIVO_FRACIONAMENTO`, sem degrau →
`faixa_efetiva` devolve a faixa #1 onde o teste espera a #3.

Os dois testes atingidos:
- `test_o_acumulado_por_fornecedor_aparece_so_na_emissao` (linha 1510)
- `test_emissao_recusa_quando_o_acumulado_do_fornecedor_sobe_a_faixa` (linha 1662)

**Nenhuma linha de produção mudou entre o gate verde e o vermelho.** O único
arquivo de produção commitado no intervalo foi `views/admin.py` (0c6590a4), que
não toca alçada. O fixture venceu sozinho.

**Por que o assert vizinho continuou passando:** o teste chama
`acumulado_do_fornecedor(adm.id, obra.id, forn.id, 3650)` com a janela
explícita de 3650 dias. Esse parâmetro fura a janela do tenant. O caminho de
produção (`valor_para_alcada` → `acumulado_do_fornecedor` sem `dias`) não tem
como recebê-lo, e é ele que quebrou. O teste já continha a pista.

**Precedente no mesmo arquivo:** `_req_na_etapa` (linha 1372) JÁ resolve isso
para `RequisicaoCompra.created_at`, que tem janela rolante idêntica
(`services/alcada_compras.py:598`), com o parâmetro `dias_atras` e
`datetime.utcnow() - timedelta(days=dias_atras)`. O padrão certo já existe no
arquivo; `_pedido` ficou de fora dele.

## Global Constraints

- **Produção não muda.** `services/alcada_compras.py` está correto. Qualquer
  task que proponha alterá-lo está resolvendo o sintoma errado.
- **Data em fixture é sempre relativa a `date.today()`/`datetime.utcnow()`**
  quando a coluna alimenta filtro de janela rolante. Data absoluta só onde o
  teste precisa de um mês/ano específico e nenhuma janela a lê.
- **Nada de prova por `inspect.getsource`.** O commit 915462d0
  (`fix(teste): reuso por chave natural para de provar por inspect.getsource`)
  tirou esse padrão do repo de propósito. As guardas deste plano são de
  COMPORTAMENTO: escrevem no banco e perguntam ao código de produção.
- **Janela padrão = 30 dias**, e o número vem de
  `ConfiguracaoEmpresa.__table__.c.janela_fracionamento_dias.default.arg`,
  nunca de um literal repetido no teste.
- **Commits sem acento no assunto**, seguindo o histórico do repo.

---

### Task 1: A guarda de calendário e a data relativa

O fixture passa a nascer dentro da janela, e uma guarda passa a dizer isso em
voz alta. A guarda vem PRIMEIRO e tem de falhar antes da correção — é ela que
prova que o diagnóstico está certo, e não a volta dos dois testes ao verde
(que voltariam ao verde por qualquer mudança que inflasse o acumulado).

**Files:**
- Modify: `tests/test_alcadas_avancadas.py:852-858` (helper `_pedido`)
- Test: `tests/test_alcadas_avancadas.py` (guarda nova, inserida imediatamente
  antes de `def test_o_acumulado_por_fornecedor_aparece_so_na_emissao():`,
  hoje na linha 1510)

**Interfaces:**
- Consumes: `_admin()`, `_obra(admin_id)`, `_cfg_tenant(admin_id, **flags)`,
  `_fornecedor(admin_id)` — todos já existentes no arquivo; `date`, `timedelta`
  e `Decimal` já estão importados (linhas 24-25).
- Produces: `_pedido(admin_id, fornecedor_id, obra_id=None, valor='100.00',
  dias_atras=0) -> PedidoCompra`. A assinatura GANHA um parâmetro com default;
  as 5 chamadas existentes (linhas 1094, 1098, 1526, 1527, 1556, 1682, 1683)
  seguem válidas sem edição.

- [ ] **Step 1: Escrever a guarda que falha**

Inserir imediatamente antes de `def test_o_acumulado_por_fornecedor_aparece_so_na_emissao():`:

```python
def test_o_pedido_do_fixture_nasce_dentro_da_janela_do_tenant():
    """Guarda de calendário: o fixture tem de contar para o acumulado HOJE.

    A janela do acumulado é ROLANTE (`data_compra >= today - janela`), e data
    absoluta em fixture sai dela sozinha quando o calendário anda. Aconteceu em
    01/09/2026: `date(2026, 8, 1)` era exatamente o limite em 31/08 (janela
    padrão de 30 dias, comparação inclusiva) e caiu fora no dia seguinte,
    derrubando dois testes sem que uma linha de produção mudasse.

    O sintoma aparecia longe da causa — faixa #1 onde se esperava #3 — e essa
    é a razão desta guarda existir: aqui a mensagem diz "fixture vencido", que
    é o que de fato aconteceu.

    A janela não é literal: sai do default da coluna, mesma fonte que
    `janela_de_fracionamento` usa.
    """
    from services.alcada_compras import (acumulado_do_fornecedor,
                                         janela_de_fracionamento)
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        _cfg_tenant(adm.id)
        forn = _fornecedor(adm.id)
        janela = janela_de_fracionamento(adm.id)

        _pedido(adm.id, forn.id, obra_id=obra.id, valor='20000.00')
        assert acumulado_do_fornecedor(adm.id, obra.id, forn.id) == \
            Decimal('20000.00'), (
                f'o pedido do fixture caiu FORA da janela de {janela} dias — '
                f'data absoluta em `_pedido` vence sozinha com o calendário')

        # E o botão da borda tem de ser real: mais velho que a janela não soma.
        _pedido(adm.id, forn.id, obra_id=obra.id, valor='700.00',
                dias_atras=janela + 1)
        assert acumulado_do_fornecedor(adm.id, obra.id, forn.id) == \
            Decimal('20000.00'), (
                'pedido mais velho que a janela nao pode entrar na soma')
```

- [ ] **Step 2: Rodar a guarda e ver as DUAS falhas esperadas**

Run:
```bash
python -m pytest tests/test_alcadas_avancadas.py::test_o_pedido_do_fixture_nasce_dentro_da_janela_do_tenant -q -p no:warnings
```

Expected: FAIL. Primeiro por `TypeError: _pedido() got an unexpected keyword
argument 'dias_atras'`. Comentar temporariamente o segundo bloco (as duas
últimas instruções) e rodar de novo para ver a falha que interessa:
`AssertionError: o pedido do fixture caiu FORA da janela de 30 dias`, com
`0 != Decimal('20000.00')`. Descomentar antes do Step 3.

- [ ] **Step 3: Trocar a data absoluta por relativa**

Substituir `tests/test_alcadas_avancadas.py:852-858` inteiro por:

```python
def _pedido(admin_id, fornecedor_id, obra_id=None, valor='100.00',
            dias_atras=0):
    """Pedido emitido há `dias_atras` dias. A data é RELATIVA, de propósito.

    A janela do acumulado é rolante (`acumulado_do_fornecedor`:
    `data_compra >= date.today() - timedelta(days=janela)`), então data
    absoluta aqui é bomba-relógio: o fixture sai da janela sozinho quando o
    calendário anda. Foi o que aconteceu — `date(2026, 8, 1)` era o próprio
    limite em 31/08/2026 e caiu fora em 01/09, derrubando dois testes com o
    código de produção intacto.

    `dias_atras` é o mesmo botão de `_req_na_etapa`, pela mesma razão: a borda
    da janela só se exercita com a distância na mão.
    """
    p = PedidoCompra(fornecedor_id=fornecedor_id,
                     data_compra=date.today() - timedelta(days=dias_atras),
                     obra_id=obra_id, valor_total=Decimal(valor),
                     admin_id=admin_id, tipo_compra='normal')
    db.session.add(p)
    db.session.commit()
    return p
```

- [ ] **Step 4: Rodar a guarda e os dois testes que caíram**

Run:
```bash
python -m pytest tests/test_alcadas_avancadas.py::test_o_pedido_do_fixture_nasce_dentro_da_janela_do_tenant \
  tests/test_alcadas_avancadas.py::test_o_acumulado_por_fornecedor_aparece_so_na_emissao \
  tests/test_alcadas_avancadas.py::test_emissao_recusa_quando_o_acumulado_do_fornecedor_sobe_a_faixa \
  -q -p no:warnings
```

Expected: `3 passed`.

- [ ] **Step 5: Rodar o arquivo inteiro**

Run: `python -m pytest tests/test_alcadas_avancadas.py -q -p no:warnings`

Expected: `0 failed`. Antes da correção o arquivo dava `1 failed, 44 passed`
com `-x`; agora nenhuma falha.

Atenção a um teste que muda de significado sem mudar de cor:
`test_...teto...` (linha ~1556) cria um pedido de R$ 100 e afirma que "o
acumulado é menor que a linha". Com a data vencida o acumulado era 0 e a
afirmação passava vazia; com a correção ele é 100 de verdade e o teste passa a
exercer o que a docstring promete. Se ele ficar vermelho, PARE: significa que
o `max` de `valor_para_alcada` não está fazendo o que a docstring diz, e isso
é achado de produção, não de fixture.

- [ ] **Step 6: Commit**

```bash
git add tests/test_alcadas_avancadas.py
git commit -m "fix(teste): a janela do acumulado e' rolante, e o fixture do pedido tinha data fixa

date(2026, 8, 1) era o proprio limite da janela de 30 dias em 31/08/2026 e caiu
fora em 01/09 — dois testes viraram vermelhos sem uma linha de producao mudar.
A guarda nova falha dizendo fixture vencido, e nao faixa errada."
```

---

### Task 2: A família copiada, e o que sobrou dela

`data_compra=date(2026, 8, 1)` foi copiado para 8 outros sítios. Eles estão
VERDES hoje e não vão quebrar amanhã — uma data absoluta só envelhece, e quem
já está fora da janela continua fora. O risco deles é o oposto: ficaram
silenciosamente VAZIOS, alimentando cenários cuja prosa fala de histórico que o
código de produção já não enxerga.

Esta task é separável da Task 1. Se o tempo for curto, a Task 1 fecha a
regressão sozinha; esta previne a próxima e desfaz o vácuo.

**Files:**
- Modify: `tests/test_alcadas_avancadas.py:1863` (`_pedido_da_emergencia`)
- Modify: `tests/test_fase3_portal_seguranca.py:78`
- Modify: `tests/test_fechamento_pagamentos_rota.py:94`
- Modify: `tests/test_financeiro_dois_fluxos.py:76`
- Modify: `tests/test_recebimento_atesto.py:76`
- Modify: `tests/test_nota_e_liberacao.py:78`
- Modify: `tests/test_onda3_compras.py:76`
- Modify: `tests/test_o_que_nao_persiste.py:88` e `:155`

**Fora de escopo, com razão declarada:** os outros `data_compra` absolutos do
parque — `test_fase06_d2_portal_compra.py:102,161` (2026-07-01),
`test_fase4_destino_custo.py:307` (2026-06-01), `test_painel_financeiro.py:1105`
(2026-06-10), `test_etapa_compra.py:70,376` (2026-01-10/11),
`test_triagem_rotas_fechadas.py:123` (2026-07-01). Não são a família copiada, e
vários são carga útil de painel com mês fixo, onde a data absoluta é o ponto.
Mexer neles sem um cenário que os exija é troca sem medida.

**Interfaces:**
- Consumes: nada da Task 1 em código; consome a DECISÃO da Task 1 (data de
  fixture é relativa quando alimenta janela rolante).
- Produces: nada que outra task leia.

- [ ] **Step 1: Trocar as 9 ocorrências**

Em cada sítio, `date(2026, 8, 1)` vira `date.today()`. Conferir em cada arquivo
que `date` já está importado de `datetime` — todos os 8 já usam `date(...)`
nessa mesma linha, então já está.

Run, para conferir que sobrou zero:
```bash
grep -rn "data_compra=date(2026, 8, 1)" tests/
```
Expected: nenhuma linha.

- [ ] **Step 2: Rodar os 8 arquivos**

Run:
```bash
python -m pytest tests/test_alcadas_avancadas.py tests/test_fase3_portal_seguranca.py \
  tests/test_fechamento_pagamentos_rota.py tests/test_financeiro_dois_fluxos.py \
  tests/test_recebimento_atesto.py tests/test_nota_e_liberacao.py \
  tests/test_onda3_compras.py tests/test_o_que_nao_persiste.py \
  -m "not browser" -q -p no:warnings
```

Expected: `0 failed`.

- [ ] **Step 3: Se algum ficar vermelho, PARE e registre**

Um teste que precisa do pedido VELHO para passar é um teste cuja intenção nunca
foi escrita. NÃO reverta a data para fazê-lo passar e NÃO adivinhe a intenção:
anote qual teste, qual assert e o que ele passa a enxergar com o pedido de
hoje, e leve o achado ao humano antes de qualquer correção. Reverter aqui
recria exatamente a bomba que a Task 1 desarmou, e desta vez com a desculpa de
que "o teste precisava".

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "test(alcadas): a familia copiada de data_compra fixa passa a nascer hoje

Oito sitios herdaram o date(2026, 8, 1) do fixture de alcadas. Nenhum ia
quebrar — data absoluta so envelhece — mas todos ja estavam fora de qualquer
janela rolante, provando com historico que a producao nao enxerga mais."
```

---

### Task 3: O gate inteiro, de uma vez só

O gate de 01/09 nunca terminou — a sessão caiu em 98%, no teste 3088 de 3131, e
o fecho foi costurado rodando os 44 restantes à parte. Resultado costurado não
pega efeito de ordem. Esta task existe para que o número que fecha o plano seja
de UMA corrida.

**Files:**
- Create: nenhum. Só execução e registro.

**Interfaces:**
- Consumes: as correções das Tasks 1 e 2.
- Produces: o relatório em `tests/reports/pytest_output_<timestamp>.txt`.

- [ ] **Step 1: Rodar o gate completo em background**

Run:
```bash
bash run_tests.sh --gate 2>&1 | tee tests/reports/gate_pos_janela.log
```

Expected: ~47 minutos (a corrida de 31/08 levou 2804s). Não interromper.

- [ ] **Step 2: Ler o resumo**

Run: `tail -5 tests/reports/gate_pos_janela.log`

Expected: linha de fecho com `0 failed`. A referência é a corrida costurada de
01/09: 3049 passed, 2 failed, 6 skipped, 74 xfail em 3131. Com as duas falhas
resolvidas, e mais a guarda que a Task 1 acrescenta, o esperado é **3052 passed, 0 failed,
6 skipped, 74 xfail** — que somam os 3132 selecionados do Step 3.

- [ ] **Step 3: Se o total de selecionados não for 3131 + guarda nova, conferir**

A Task 1 acrescenta 1 teste. `3131 + 1 = 3132` selecionados. Número diferente
disso significa coleta diferente da medida — investigar antes de commitar o
número.

- [ ] **Step 4: Commit do registro**

```bash
git add docs/superpowers/plans/2026-09-01-a-janela-que-andou.md
git commit -m "docs(janela): o plano fecha com o gate inteiro numa corrida so"
```

---

## Self-Review

**1. Cobertura da evidência.** A cadeia causal (data absoluta → fora da janela
→ acumulado 0 → sem fracionamento → faixa #1) tem task: a Task 1 corta no
primeiro elo. Os dois testes vermelhos nomeados na evidência estão no Step 4 da
Task 1. A família copiada, medida em 9 sítios, é a Task 2. O gate não terminado,
citado na abertura da Task 3, é a Task 3.

**2. Placeholders.** Nenhum "TBD", nenhum "tratar os casos de borda", nenhum
"similar à Task N". Todo bloco de código está escrito por extenso, inclusive as
docstrings. Todo comando tem saída esperada com número.

**3. Consistência de tipos.** `_pedido` é chamado com `dias_atras=janela + 1` na
guarda da Task 1 e definido com `dias_atras=0` no Step 3 da mesma task — mesmo
nome, mesmo tipo (`int`). `janela_de_fracionamento(admin_id) -> int` e
`acumulado_do_fornecedor(admin_id, obra_id, fornecedor_id, dias=None) ->
Decimal` estão usados na guarda com a aridade real de
`services/alcada_compras.py:641,548`. `Decimal`, `date` e `timedelta` já estão
importados no arquivo (linhas 24-25) — a guarda não precisa de import novo além
das duas funções do serviço.

**4. Ordem das tasks.** A Task 2 depende da decisão da Task 1, não do código
dela; se executadas fora de ordem, o Step 2 da Task 2 falharia nos dois testes
da regressão e o executor leria isso como achado falso. Executar em ordem.

---

## Correções pós-review

O review final do plano achou que o censo de Task 2 cobriu só metade da
família de datas absolutas, e que o corpo do commit `b958f090` faz duas
afirmações que não se sustentam. Esta seção registra o que foi corrigido numa
onda única em `tests/`, sem tocar produção, e por que o histórico do commit
já mesclado não foi reescrito.

**1. O corpo de `b958f090` tem duas afirmações que não se sustentam.**
Decisão do controlador: o histórico NÃO será reescrito — emendar um commit já
revisado sob um SHA registrado invalidaria a trilha de auditoria. As duas
imprecisões ficam registradas aqui, não corrigidas ali:

- A mensagem diz "oito sítios"; eram **nove** linhas — `test_o_que_nao_persiste.py`
  contribui duas, não uma.
- A mensagem diz "todos já estavam fora de qualquer janela rolante" — **falso
  pela porta lateral**. `criar_obrigacao` (`services/financeiro_compra.py:149`)
  chama `_vencimentos` (`compras_views.py:538-556`), e para
  `condicao_pagamento='a_vista'` isso faz `data_vencimento = data_compra`. Com
  `date(2026, 8, 1)` essas `ContaPagar` eram estavelmente vencidas
  (`financeiro_views.py:160`: `data_vencimento < hoje`); com `date.today()`
  elas passaram a vencer HOJE, entrando na faixa "a vencer" `[hoje, hoje+7]` de
  `financeiro_views.py:165-166`. Nenhum dos 8 arquivos assere sobre essa
  classificação, então a troca foi inerte na prática — mas foi uma mudança
  semântica que o commit não analisou nem anunciou.

**2. A variante de formulário existia e o censo original não a conhecia.**
O censo de Task 2 procurou apenas o construtor `data_compra=date(...)` e nunca
a forma de formulário `'data_compra': 'YYYY-MM-DD'` usada em `data=` de
`client.post`. Havia 15 sítios dessa forma. Corrigidos nesta onda: 13, em
`test_alcadas_avancadas.py` (2), `test_fase3_alcada.py` (8),
`test_fase3_matriz_governanca.py` (1) e `test_recebimento_atesto.py` (2).
Deixados de propósito: os 2 de `test_painel_financeiro.py:1205,1253` — mesma
razão pela qual o construtor irmão desse arquivo já tinha sido excluído do
censo original: teste de painel financeiro com mês fixo é o caso em que a
data absoluta É o ponto, não carga acidental.

**3. O critério do plano estava mais forte do que a evidência sustenta.**
O plano original disse "data absoluta só envelhece, logo quem saiu da janela
continua fora". Isso vale só para predicados do tipo `col >= today - N`
(janela rolante para trás) — é exatamente o caso que quebrou em 01/09 e que
esta onda persegue. Não vale em geral: o achado do item 1 acima é um
predicado do tipo `today <= col <= today + N` (faixa em torno de hoje), onde
uma data absoluta pode ENTRAR na faixa com o tempo, não só sair dela.

O critério correto — e a regra que a próxima onda deve citar antes de decidir
se um sítio de data em fixture precisa de correção — é:

> Uma data de fixture é segura quando nenhum predicado de produção que a lê
> depende de `today`. Janelas para trás (`col >= today - N`) toleram data
> absoluta velha — ela só se afasta da borda. Faixas em torno de hoje (como
> `data_vencimento < hoje` versus `hoje <= data_vencimento <= hoje + 7`) não
> toleram nem data absoluta nem data relativa sem análise — o fixture pode
> atravessar a faixa com o tempo em qualquer sentido.

Registre-se também que a janela de fracionamento é DADO, não constante:
`configuracao_empresa.janela_fracionamento_dias`, alterável por UPDATE. "Está
seguramente fora da janela" é, portanto, uma afirmação sobre um número
configurável — não uma verdade fixa do código.
