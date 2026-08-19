# Plano — o fechamento do lote passa a valer, pela tela — 2026-08-19

**O que é.** Ligar o único controle que a Fase 2 acrescenta ao passo (e) do
runbook: *quem monta o lote não o fecha*. Hoje ele existe em serviço testado e
**não é alcançável pela tela**.

**Como apareceu.** 🔬 19/08, rodando o runbook da Fase 2 por script
(`scripts/runbook_fase2.py`, escrito para isto): **30 de 34 conferências
passam**, e as 4 falhas são um defeito só.

## O achado

📖 `financeiro_views.fechamento_pagamentos`, ação `fechar` (linhas 1536-1546 no
estado de 19/08, antes do conserto) — a tela faz:

```python
fech.status = 'FECHADO'
db.session.commit()
```

Nunca chama `services.financeiro_compra.fechar_lote()`. 🔬 `financeiro_views.py`
importa daquele módulo **só** `pernas_faltantes` (`:509`); `fechar_lote` e
`reabrir_lote` têm **zero chamadores de produção** — os únicos são
`tests/test_financeiro_dois_fluxos.py`.

O que a rodada de 19/08 mediu, com quatro pessoas distintas no tenant do manual:

| Conferência do runbook | Medido |
|---|---|
| Helena monta o lote → `criado_por_id` | `None` — 📖 `:1516-1522` também não carimba |
| Helena tenta fechar o **próprio** lote → recusa | **fechou** |
| Ana fecha → `fechado_por_id` | `None` |
| `verificar_consistencia_financeiro.py` | **exit 1**, dois lotes `FECHADO` sem autor |

Os dois carimbos ausentes são **duas metades do mesmo buraco**: o guarda é
`if criado_por is not None and quem_fecha is not None` — com `criado_por` sempre
NULL ele passaria calado mesmo se o serviço fosse chamado.

Junto vêm dois efeitos que ninguém pediu: o caminho de liberação do
`fechar_lote` (as contas ainda bloqueadas do lote) nunca roda pela tela, e o
`reabrir` sem `reabrir_lote()` não aplica `LoteImutavel` — **lote com conta paga
volta a ABERTO pela tela**.

🔬 Cobertura: `tests/test_fechamento_pagamentos_render.py` tem **dois** testes,
os dois de render, de 18/08. **Nenhum teste exercita o POST** desta tela — nem
`create`, nem `fechar`, nem `reabrir`.

É a mesma classe do achado de 17/08 sobre `liberar()`: serviço escrito, testado,
sem chamador. E é a terceira vez que este padrão aparece na Fase 2.

## A decisão que este plano carrega, e por que ela não é cosmética

**Carimbar `criado_por_id` LIGA a segregação pela primeira vez.** Antes do
conserto o guarda nunca mordeu porque um dos lados era sempre NULL. Depois dele,
num financeiro de uma pessoa só o lote fica sem quem o feche — e o docstring do
próprio `fechar_lote` avisa: *"regra que atrapalha sem proteger é regra que
morre"*.

**Decisão do Cássio, 19/08: opção (b)** — quem montou o lote PODE fechá-lo
**com justificativa gravada**, e o lote sai marcado no sensor. É exatamente o
padrão da ressalva D6 que `liberar()` já usa: a exceção continua possível, e
deixa de ser silenciosa. Rejeitadas: (a) sem saída, que trava tenant pequeno;
(c) ADMIN sempre pode, que dispensa justamente quem mais convém auditar.

**Decisão do Cássio, 19/08: o piso do sensor** — só entram no achado 3 os lotes
que têm `criado_por_id`. É **auto-datante**: só nasce com autor o que foi criado
depois deste conserto, então o passado não grita. 🔬 19/08 no dev: **32 lotes
`FECHADO` sem autor** de 93 fechados; sem piso, o sensor passaria a acusar drift
para sempre por eles, e `ESTADO-ATUAL.md` já registra o custo — sensor que grita
sempre não é lido nunca. **Sem backfill**: não há como saber quem fechou os 32,
e inventar autor é forjar registro.

## As etapas

### L1 — os cinco testes de rota que não existem (red-first)

Em `tests/test_fechamento_pagamentos_render.py`, que passa a ser a cobertura da
tela e não só do render. Todos vermelhos antes do L2:

1. `create` carimba `criado_por_id` com quem montou
2. `fechar` carimba `fechado_por_id`/`fechado_em` **e libera as contas
   bloqueadas do lote**
3. `fechar` **recusa** quem montou o lote, sem justificativa
4. `fechar` **aceita** quem montou o lote com justificativa, e a grava
5. `reabrir` recusa lote com conta paga (`LoteImutavel`)

Mais o teste de **paridade**: tenant com a flag OFF fecha o lote como sempre
fechou — o bloco novo é inerte para quem não virou, que é o que a Fase 2 mede
desde o começo.

### L2 — a saída da segregação, no serviço

`fechar_lote(fechamento, *, usuario=None, justificativa=None)`, no molde de
`liberar()`:

- mesma pessoa **sem** justificativa → `SegregacaoViolada` (mensagem de hoje,
  mais o que fazer)
- mesma pessoa com texto **curto** → `RessalvaInvalida`, `MINIMO_RESSALVA` = 15
- mesma pessoa com justificativa → fecha, e grava em
  `fechamento_pagamento.segregacao_justificativa`

**Migration 310** — a coluna, `TEXT` nullable, `IF NOT EXISTS`, sem backfill.
Não-nulo **significa** fechamento excepcional, espelhando
`conta_pagar.liberacao_justificativa` da 308. 🔬 19/08: a maior aplicada em dev
é a **309**, e entre 310 e 325 não há nada.

### L3 — a rota passa a chamar o serviço

📖 `financeiro_views.py:1516-1553`. `create` carimba o autor; `fechar` chama
`fechar_lote(..., usuario=current_user, justificativa=...)`; `reabrir` chama
`reabrir_lote(...)`. As duas exceções viram **flash**, não estouro: a mensagem
do serviço já diz o motivo e o que fazer, e é ela que impede a pessoa de
procurar caminho por fora do sistema.

### L4 — a tela oferece a saída

📖 `templates/financeiro/fechamento_pagamentos.html:300-308`. Quando quem olha é
quem montou o lote, o botão vira **"Fechar mesmo assim"** com campo de
justificativa obrigatório — o mesmo desenho de "Liberar com ressalva" na tela do
pedido, que já existe e o time já viu. **O botão nunca some**: sumir é o que faz
alguém concluir que o sistema quebrou.

### L5 — o sensor

Piso no achado 3 (`criado_por_id IS NOT NULL`) e um **quarto item que não é
defeito**: lote fechado por quem o montou, com justificativa. Aparece para ser
lido uma vez por mês e **não conta para o exit code** — mesma regra que a
ressalva do D6 já segue, e pelo mesmo motivo.

### L6 — rodar `scripts/runbook_fase2.py` de novo

Alvo **34/34**. O script é o teste de aceitação deste plano: ele mediu 30/34
antes e é a mesma medida depois.

### L7 — gate completo, `ESTADO-ATUAL.md`, commit

As **duas falhas conhecidas e anteriores** continuam esperadas; qualquer terceira
é desta rodada.

## O que este plano NÃO faz

**`fechar_lote` libera as contas bloqueadas; `reabrir_lote` não as re-bloqueia.**
Reabrir um lote deixa as contas pagáveis. Pode ser de propósito — a liberação
fala da tríade, não do lote, e a conta também pode ter sido liberada pelo botão
do pedido em 17/08 —, mas hoje não está escrito em lugar nenhum nem coberto por
teste. Fica **anotado como pergunta**, não corrigido: mexer nisso sem decidir o
desenho trocaria um silêncio por outro.

Também fora: backfill dos 32 lotes sem autor, e qualquer mudança no que
`pagar_conta` consulta — ele continua com **uma** porta (`situacao_liberacao`),
que é o desvio deliberado do spec registrado em 14/08.
