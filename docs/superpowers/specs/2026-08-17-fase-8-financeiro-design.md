# Fase 8 — o plano de contas passa a significar uma coisa só

**Data:** 2026-08-17
**Origem:** o plano aprovado (Fase 8, *"Financeiro avançado + exportação Domínio"*), com o
escopo ampliado pela análise `docs/maturidade-financeira-rfa.md`.
**Escopo:** unificar os planos de contas concorrentes, classificar gasto fixo × variável,
derivar DFC e indicadores do que já é lançado, e a exportação Domínio.

---

## ⚠️ A régua é nossa, e isso muda o peso do documento

A ampliação do escopo nasceu de medir o SIGE contra o método RFA de um ebook institucional.
🔬 17/08, do Cássio: **a consultoria NÃO foi contratada.** Então não existe diagnóstico
externo sobre a operação da Veks — o que existe é uma régua conceitual que nós escolhemos
usar.

Consequência prática, e ela vale para quem for cobrar esta fase: **as lacunas apontadas são
reais no código e todas foram conferidas com `caminho:linha`; que elas importem para quem
usa o sistema é hipótese nossa.** Mesma classe de ressalva do spec das alçadas — requisito
de desenho próprio, ratificado, não levantado com o usuário.

> 📄 **Material de aprovação:** `caminho-do-dinheiro.pdf`, na raiz, gerado por
> `scripts/gerar_pdf_caminho_dinheiro.py`. É este spec traduzido para quem decide — dois
> fluxogramas, os campos novos e as cinco decisões, sem jargão de código. **Ele é gerado
> por comando de propósito:** quando a medição da Task 1 mudar os números, eles mudam no
> script e o PDF é refeito. PDF anexado à mão é PDF que envelhece calado.

---

## O que a medição mudou no diagnóstico

O diagnóstico de julho dizia *"o sistema tem QUATRO planos de contas concorrentes"*. É
verdade **no código** e enganoso **no dado**. 🔬 Medido no banco de dev em 17/08:

| | |
|---|---|
| linhas em `plano_contas` | 115.920 |
| tenants com plano | 3.371 |
| tenants **só** com `6.1.x` (o seed V2) | **3.168** (94%) |
| tenants com `5.1.x` **e** `6.1.x` (misturados) | **112** |
| tenants sem nenhum dos dois | 91 |
| partidas contábeis | 4.481 lançamentos |
| partidas em contas `6.x` | 741 |
| partidas em contas `5.x` | **164** (das quais 112 em `5.1.x`) |
| partidas **órfãs** (conta inexistente no plano do tenant) | 🔬 **0** |

> ⚠️ **Isto é ⚠️ dev, e o banco de dev é dominado por carga de suíte.** Prova a *forma* do
> problema, não o volume. As "60 contas `5.1.01` chamadas *Salários (agrupador)*" que a
> consulta encontra vêm de `tests/test_fase06_d3_dre_despesas_v2.py:108` — não são um
> quinto plano, são fixture. **Medir em produção é pré-requisito da Task 1**, e a pergunta
> é uma só: quantas partidas vivem em `5.x` lá.

**A leitura que sai daí:** o `_V2_CONTAS_SEED` **já venceu na prática**. Não é uma
unificação entre quatro iguais — é reconhecer um vencedor e aposentar os perdedores, com um
de-para para a minoria que ficou do outro lado.

---

## O mecanismo do defeito — três semeadores vivos, e quem chega primeiro decide

Esta é a parte que o diagnóstico de julho não tinha, e é ela que torna a fase pequena.

📖 Três pontos vivos criam plano de contas, cada um com um conteúdo diferente:

| # | Gatilho | Semeador | `5.1.01` vira |
|---|---|---|---|
| 1 | abrir `/contabilidade/plano-contas` (`contabilidade_views.py:94`) | `contabilidade_utils.criar_plano_contas_padrao` | **"Materiais Diretos"** |
| 2 | botão em `/financeiro/plano-contas/inicializar` (`financeiro_views.py:1329`) | `financeiro_seeds.criar_plano_contas_padrao` | **"MÃO DE OBRA"** |
| 3 | **qualquer lançamento automático** (`contabilidade_utils.py:1705`) | `seed_plano_contas_if_needed` (`_V2_CONTAS_SEED`) | *(não existe)* |

Os três são idempotentes por `(admin_id, codigo)`, que é a PK. Logo: **para cada código, o
primeiro semeador a rodar decide o significado, e os outros dois são descartados em
silêncio.** Dois tenants podem ter `5.1.01` querendo dizer coisas opostas, e todo relatório
que assume um significado está errado para uma parte do parque.

O nº 3 vence quase sempre porque dispara em qualquer evento contábil automático — e 📖 desde
a correção D4 da Fase 0.6 ele é **incondicional**, garantindo as 28 contas V2 mesmo em
tenant que já tinha conta avulsa.

> 📖 **O DRE já contorna isto, e o contorno é a melhor prova do problema.**
> `contabilidade_utils.py:536-540` declara em linha do DRE **apenas** os prefixos *"cujo
> significado é o MESMO nos planos que os definem"*, e deixa `6.1.02` de fora por escrito.
> O que não casa cai no residual `outras` — nunca some. Quem escreveu o DRE já bateu nesta
> parede, contornou com honestidade e registrou a dívida como Fase 8. Esta spec é o
> pagamento dela.

---

## Modelo de dados

### `plano_contas.classificacao_gasto` — o que destrava a margem de contribuição

`VARCHAR(12)`, NOT NULL, default `'nao_classificado'`. Valores: `fixo` | `variavel` |
`nao_aplicavel` | `nao_classificado`.

📖 `PlanoContas` (`models.py:3234`) tem hoje `tipo_conta`, `natureza`, `nivel`,
`conta_pai_codigo`, `aceita_lancamento`, `ativo` — **e nada que diga se o gasto é fixo ou
variável**. Sem isso, margem de contribuição não é calculável a partir do que está gravado,
e é por isso que ela dá 🔬 zero ocorrências no repositório.

Três escolhas que valem comentário:

* **`nao_classificado` como default, e não `fixo`.** Um default que já classifica produz um
  número de margem que parece pronto e está errado. Não classificado **aparece no
  relatório como não classificado** — a mesma lógica da linha residual `outras` do DRE.
* **Por tenant, e não constante de código.** A PK já é `(admin_id, codigo)`. Empresas
  classificam o mesmo gasto de formas diferentes e legítimas (frota é fixa para quem tem
  frota própria, variável para quem aluga por obra). Mesmo desenho de `FaixaAlcada`, pelo
  mesmo motivo: número que é regra de negócio não entra em `if`.
* **`nao_aplicavel` existe** para ativo, passivo, patrimônio e receita. Sem ele, "conta sem
  classificação" misturaria o que falta classificar com o que nunca será classificado, e o
  indicador de completude não significaria nada.

### `plano_contas.atividade_dfc` — o que destrava o Passo 1

`VARCHAR(14)`, NOT NULL, default `'operacional'`. Valores: `operacional` | `investimento` |
`financiamento`.

O default **não** é neutro de propósito: na esmagadora maioria das contas de uma
construtora a atividade é operacional, e um default `nao_classificado` faria o DFC nascer
com quase tudo fora dos três grupos — inutilizável no dia 1. Investimento e financiamento
são a exceção e são poucas contas; classificá-las é trabalho de minutos, e é o que a Task 4
faz por seed.

> 📌 **Duas colunas e não uma tabela de-para.** Uma tabela `conta → atividade` seria mais
> "certa" e criaria um segundo lugar onde a verdade sobre uma conta mora. A conta já tem
> `tipo_conta` e `natureza` como colunas; estas duas são da mesma natureza e ficam ao lado.

### O que NÃO ganha coluna

**Nada em `partida_contabil` nem em `lancamento_contabil`.** 📖 `PartidaContabil`
(`models.py:3332`) já tem `conta_codigo`, `admin_id`, `tipo_partida` e `valor` — tudo o que
DFC, margem e indicadores precisam. **As Tasks 4, 5 e 6 são leitura pura**: nenhuma cria
caminho de escrita novo, e por isso nenhuma carrega o risco que as fases do ciclo de
compras carregaram.

---

## Regime de virada

**Esta fase não tem flag de comportamento, e a razão é que ela não muda comportamento
nenhum** — ela conserta o significado do dado e acrescenta leitura.

O que muda para o usuário:

| Mudança | Efeito |
|---|---|
| Os dois semeadores concorrentes saem | Ninguém mais recebe um plano diferente por ter clicado noutra tela |
| Contas `5.x` sem partida ficam `ativo = False` | Somem dos selects; **não são apagadas** |
| Contas `5.x` **com** partida são remapeadas | Ver Task 3 — é o único ponto que toca dado histórico |
| DFC, margem e indicadores | Telas novas; nada existente muda |

---

## As tasks

### Task 1 — Medir em produção. **Antes de qualquer código.**

🔴 Bloqueante, e é humano: depende do acesso a produção, que é pré-requisito de quase toda
medição pendente deste repositório. `scripts/medir_producao.py` ganha uma sétima pergunta:

* quantos tenants têm `5.1.x`, `6.1.x`, ambos, nenhum;
* **quantas partidas vivem em `5.x`** — é este número que decide se a Task 3 é um de-para de
  algumas centenas de linhas ou um projeto próprio;
* existe partida órfã? (🔬 dev: zero — se produção divergir, pare e reveja tudo).

> ⚠️ **Se produção mostrar `5.x` dominante, esta spec está errada** e o canônico tem de ser
> reavaliado. A Task 1 existe para poder descobrir isso barato.

### Task 2 — O canônico, e os dois semeadores aposentados

* `_V2_CONTAS_SEED` vira o **plano canônico**, com o nome dito no código (D1).
* `financeiro_views.inicializar_plano_contas` e o auto-seed de
  `contabilidade_views.plano_contas` passam a chamar **`seed_plano_contas_if_needed`** —
  um semeador só.
* As duas funções `criar_plano_contas_padrao` **não são apagadas**: ficam marcadas
  `EM APOSENTADORIA` com ponteiro para esta spec, pelo mesmo motivo da `AlocacaoEquipe` no
  p7 — remover função e mudar leitor no mesmo release é duas mudanças difíceis de bissetar.
* **Teste-guarda**: varre o repositório por `ast` e falha se aparecer um segundo criador de
  `PlanoContas` fora da lista conhecida. Mesmo molde do guarda da C9 da Fase 2, que já
  provou o valor dele.

### Task 3 — O de-para das contas `5.x`, e é aqui que mora o risco

Único ponto que toca dado histórico.

* Um de-para **explícito e revisável em tabela no spec** (`5.1.01 → 6.1.01`, etc.),
  escrito à mão e conferido conta a conta — **não derivado por heurística de nome**. Os
  nomes são justamente o que está inconsistente; derivar deles seria usar a doença como
  diagnóstico.
* A migração reescreve `partida_contabil.conta_codigo` **dentro de uma transação só**, com
  contagem antes e depois. 📖 A lição da migração 218 (Fase 0.6) vale aqui: numa troca de
  significado, a ordem dos atos decide se o backfill é real ou no-op silencioso.
* Conta `5.x` **sem** partida: `ativo = False`. Não se apaga linha de plano de contas —
  histórico de relatório aponta para ela.
* **Nenhuma partida é apagada ou somada.** Se um código não tiver destino óbvio no de-para,
  a migração **falha** e nomeia o código. Ficar `'failed'` e retentar a cada boot é o
  comportamento certo (📖 é o que a 279 deveria ter feito e não fez — ver a lição da
  migração 309).

### Task 4 — Fixo × variável, e a margem de contribuição

* A coluna, com seed de classificação para as 28 contas do canônico.
* Tela de edição por tenant (molde de `/configuracoes/alcadas`, que já é o padrão da casa
  para "dado que é regra de negócio").
* **DRE Gerencial**: receita − variáveis = **margem de contribuição**; − fixos = resultado.
* A linha **"não classificado"** aparece sempre que houver, com o valor. Relatório que
  esconde o que não sabe classificar é relatório que mente devagar.

### Task 5 — DFC pelos três grupos

* A coluna `atividade_dfc`, com seed.
* O DFC é montado pelo **método direto, olhando a contrapartida**: para cada lançamento que
  toca caixa ou bancos (`1.1.01.x`, `1.1.02.x`), a natureza do movimento vem da **outra
  perna** da partida. 🔬 dev: `1.1.02.001` é a conta com mais partidas do sistema (3.061),
  então o dado para isso existe e é o mais denso que temos.
* Confere contra o saldo: a soma dos três grupos tem de bater com a variação de caixa do
  período. **Se não bater, a tela mostra a diferença** em vez de escondê-la.

### Task 6 — Indicadores e ciclos

Derivados do balanço e do DRE que já existem, por período:

| Grupo | Indicadores |
|---|---|
| Liquidez | corrente, seca |
| Estrutura | endividamento, imobilização do PL |
| Rentabilidade | margem líquida, ROE, giro do ativo |
| Ciclos | prazo médio de recebimento, de pagamento, ciclo financeiro |

⚠️ Cada indicador exibe **a data-base e as contas que o compõem**. Indicador sem
procedência é o defeito de fabricação que abre o `ESTADO-ATUAL.md`, agora em forma de
número na tela.

### Task 7 — Exportação Domínio

Escopo original da fase, **inalterado**. Depende da Task 3: exportar para a contabilidade
externa um plano que significa duas coisas é exportar o defeito para fora de casa.

---

## Decisões que precisam do Cássio

**D1 — O canônico é o `_V2_CONTAS_SEED`?**
*Recomendado:* **sim.** ⚠️ dev 17/08: 94% dos tenants já estão nele, é o único que os
lançadores automáticos usam, e é o único dos três que a Fase 0.6 revisou e corrigiu (D4).
Escolher outro seria migrar a maioria para agradar a minoria.

**D2 — As 164 partidas em `5.x` migram ou congelam?**
*Recomendado:* **migram**, por de-para explícito (Task 3). Congelar deixaria dois
significados vivos para sempre e a Fase 8 não teria fechado nada.
⚠️ Recomendação **condicionada à Task 1**: se produção mostrar volume muito maior, a
decisão volta à mesa.

**D3 — Quem classifica fixo × variável?**
*Recomendado:* **padrão semeado, editável por tenant**, e o padrão erra para
`nao_classificado` quando não houver consenso óbvio. O que não pode é o sistema **decidir
por conta própria** e o empresário descobrir depois que a margem dele foi calculada com uma
premissa que ele não viu.

**D4 — Numeração das migrations.**
*Recomendado:* **310+**, e **liberar a faixa 290-295**. 🔬 17/08 a maior aplicada é a
**309** — numerar em 290 agora colocaria a migração da Fase 8 abaixo do topo, e o
`ESTADO-ATUAL.md` já documenta que **a reserva por faixa foi furada três vezes** e que o
fantasma do 270 nasceu exatamente de renumerar para "organizar". Numerar em sequência real
é mais honesto que respeitar uma reserva de julho.

**D5 — Os passos 4 e 5 do RFA entram?**
*Recomendado:* **não.** Orçamento empresarial, business plan e perpetuidade são **produto
novo**, não dívida técnica, e nenhum cliente pediu. Esta fase paga a fundação; andar novo é
outra conversa.

---

## Casos de borda

| Situação | Comportamento |
|---|---|
| Tenant sem plano de contas nenhum (🔬 dev: 91) | Recebe o canônico na primeira necessidade, como hoje |
| Tenant com contas avulsas criadas à mão | Preservadas, `nao_classificado`, e aparecem na tela de classificação |
| Conta `5.x` com partida e **sem** destino no de-para | A migração **falha e nomeia o código** — nunca chuta |
| DFC cujos três grupos não fecham com a variação de caixa | A tela **mostra a diferença**, não a esconde |
| Margem de contribuição com contas não classificadas | Linha própria com o valor; o indicador sai com asterisco |
| Tenant sem receita no período | Margem não é exibida como 0% — é exibida como "sem base" |

---

## Migrations

**310** — `plano_contas.classificacao_gasto` + `atividade_dfc`, com os defaults acima.
**311** — o de-para da Task 3: `partida_contabil.conta_codigo` reescrito e as `5.x` sem
partida desativadas. Transação única, contagem antes e depois, falha ruidosa.

⚠️ **310 e não 290.** Ver D4. A faixa 290-295 é liberada nesta spec.

---

## Testes

* **Task 2:** o guarda por `ast` (nenhum criador novo de `PlanoContas`); dois tenants
  semeados por caminhos diferentes recebem **o mesmo** plano.
* **Task 3:** de-para com contagem — nenhuma partida perdida, nenhuma somada duas vezes;
  código sem destino **falha** o teste; conta desativada não some da tabela.
* **Task 4:** margem de contribuição de um caso montado à mão, conferido na calculadora;
  conta não classificada aparece na linha própria; mutação — classificar tudo como fixo
  tem de matar o teste da margem.
* **Task 5:** DFC de um período com os três grupos; o teste **soma os três e compara com a
  variação de caixa**.
* **Task 6:** cada indicador com um caso de valor conhecido; divisão por zero vira
  "sem base", nunca `inf` na tela.
* **Paridade:** DRE e balanço de um tenant **antes e depois** da fase inteira, conferidos
  por `SELECT` — os números que já existem não podem mudar. É o teste que impede esta fase
  de reescrever o passado enquanto conserta o vocabulário.

---

## Fora de escopo

Passos 4 e 5 do RFA (orçamento empresarial, cultura financeira, business plan,
perpetuidade) — ver D5. Consolidação entre tenants. Conversão de moeda. Regime de
competência × caixa como opção de relatório: o sistema hoje é competência no contábil e
caixa no financeiro, e reconciliar os dois é fase própria, maior que esta.

**Também fora:** a `NotaFiscal` legada × `nota_fiscal_pedido` e o UNIQUE global de
`chave_acesso` — dívida registrada no fecho da Fase 2, vizinha desta, e que continua sem
dono.
