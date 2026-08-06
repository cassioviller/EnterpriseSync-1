# FECHO — Varredura B5 de 2026-08-06: o registro de execução do workflow

> **O que este documento é.** O registro do **trabalho**: como a varredura foi montada, o
> que cada um dos onze agentes fez, o que custou e o que dá para aprender do método. O
> **produto** dela — as cinco Tasks, os riscos, a ordem de entrega e as perguntas — vive em
> `docs/superpowers/plans/2026-08-06-rodada-b5-varredura.md`, que é a fonte de verdade.
> Este aqui não a substitui e não a resume.
>
> Segue o padrão de `FECHO-SESSAO-2026-08-05.md` e `FECHO-FASE-0.5.md`, e as marcas de
> procedência de `ESTADO-ATUAL.md`: 🔬 medido · 📖 lido no código · 🧮 deduzido · ⚠️ dev.

**Contra o quê:** branch `test/b0-arreio`, HEAD `4b53a6a1`, árvore limpa. Os 63 commits da
execução do plano consolidado seguem **locais — nada foi enviado ao remoto**.

---

## 🔴 A COISA QUE PRECISA DE DECISÃO ANTES DO DEPLOY

**A sessão de 05/08 introduziu um defeito ativo na baixa de conta a pagar, e ele está nos
63 commits que não foram enviados.**

📖 `financeiro_service.py:133` passa `valor_recebido` para o `logger.warning` dentro de
`baixar_pagamento`, onde o parâmetro se chama `valor_pago` (`:73`). É `NameError`. O bloco
inteiro é cópia verbatim do lado receber — o texto diz "ContaReceber" dentro de uma função
de `ContaPagar`.

🔬 `git blame` aponta para **`01883756` — a Task B3.6**, "o gate contábil deixa de ser
mudo". Ela copiou o bloco de log para os dois pontos de baixa e não trocou a variável no
segundo.

📖 A cadeia, conferida elo a elo **fora do workflow**, na redação deste fecho:

1. `financeiro_service.py:118` já deu `db.session.commit()` — valor, saldo, data, forma e
   status **persistidos**;
2. `:133` estoura o `NameError`;
3. o `except` de `:215-218` faz `rollback()` (**no-op**, a transação já fechou) e `raise`;
4. `financeiro_views.py:425-427` pega, faz `flash('Erro ao registrar pagamento','danger')`
   **sem `return`**, e a execução cai no ramo GET, que renderiza a página com **HTTP 200**.

O operador vê "Erro ao registrar pagamento" sobre um pagamento que já aconteceu.

⚠️ dev: **0 de 627** `ContaPagar` têm `conta_contabil_codigo`, e o bloco está sob
`if not conta.conta_contabil_codigo:` (`:127`). No parque de desenvolvimento o defeito
dispara em **toda** baixa. 🔬 A refutação procurou um preenchedor do campo que o
levantamento tivesse perdido e não achou: todos os escritores são de `ContaReceber` ou
`GestaoCustoPai`, e `criar_conta_pagar` — que aceita o parâmetro — não tem chamador.

**Não está em produção.** Por isso a decisão é sobre o que sai no próximo deploy, e não
sobre incidente ativo. A Task B5.1 é a correção, é esforço **P**, e não depende de nenhuma
decisão sua.

**Consequência de método, e ela é desconfortável:** este defeito passou pelo gate de
🔬 1937 testes verdes de 05/08. Nenhum teste exercita a baixa de conta a pagar pelo caminho
de produção. É a mesma classe de buraco que o B0 foi construído para fechar do lado do
custo de RDO — do lado do pagar, o arreio não existe.

---

## 1. Por que este workflow existiu

O plano consolidado de 04/08 fechou **60 de 61 Tasks**. Cinco dívidas ficaram sem Task —
quatro na §8.3 daquele documento, uma na seção "Em aberto" do `FECHO-SESSAO-2026-08-05.md`.
Elas não tinham recorte, e o `FECHO-SESSAO` registra o motivo de cada uma não ter dono.

A varredura foi encomendada para transformar as cinco em recortes executáveis. **O método
foi ditado por um erro nosso**, não escolhido por gosto: o achado de 05/08 registra que a
B4.8 removeu `NotificacaoCliente` a partir de grep pelo **símbolo Python**, e que três
referências citavam a tabela por **string literal** — uma delas percorrida a cada exclusão
de obra. 🔬 O resultado medido foi a exclusão de RDO falhando em silêncio, com a rota
respondendo 200.

Daí as **cinco lentes**, obrigatórias por schema em todo levantamento:

| # | Lente | O que procura |
|---|---|---|
| 1 | **SÍMBOLO** | nome Python da função/classe/atributo |
| 2 | **STRING** | o nome como literal: `'tabela'`, listas de config, chaves de payload |
| 3 | **TEMPLATE** | `templates/**`: `{{ }}`, `{% %}`, `url_for`, `name=` de form, `fetch()` |
| 4 | **ROTA** | `@blueprint.route`, `url_for`, e **qual regra vence no `url_map`** |
| 5 | **SQL/DADO** | SQL cru, `migrations.py`, seeds, `scripts/`, e o dado no banco |

Um agente que só rodasse a lente 1 teria de escrever "nada" nos outros quatro campos do
schema e assinar embaixo.

---

## 2. A forma do workflow

**Pipeline, não barreira.** Cada dívida atravessou levantamento → refutação por conta
própria, sem esperar as irmãs. Só a síntese esperou todas, e ali a barreira é legítima: o
documento precisa das cinco para decidir ordem de entrega e colisão entre Tasks.

```
levantar(dívida) ──→ refutar(levantamento) ──┐
      × 5, cada uma no seu ritmo             ├─→ sintetizar (barreira)
                                             ┘
```

**Os dois papéis eram adversários por construção, não revisor e revisado.** O agente de
refutação não recebeu "revise isto". Recebeu **seis ataques nomeados**, e dois deles vieram
de erros que este projeto já cometeu:

| # | Ataque | De onde veio |
|---|---|---|
| 1 | A dívida existe, ou já foi consertada por uma das 60 Tasks? | — |
| 2 | As âncoras estão certas, ou é **homonímia**? | E10 quase morreu assim |
| 3 | "Morto" está provado ou presumido? | E03 e E11 foram declaradas mortas com consumo vivo |
| 4 | "Vivo" está provado ou presumido? | o espelho do nº3 |
| 5 | A correção isolada **piora** alguma coisa? | foi assim que a B1.14 caiu |
| 6 | O esforço está certo? | "P" que é "M" custa uma sessão |

O schema exigia listar **o que se tentou e falhou** (`confirmacoes`). Concordância passiva
não passava.

**Restrições impostas, e por quê:**

* **read-only no repositório inteiro** — nenhum agente podia editar, criar, apagar ou rodar
  git que mudasse estado;
* **proibido rodar `run_tests.sh`** — 🔬 o gate leva 21min27 contra o `DATABASE_URL`
  **único** de desenvolvimento (`app.py:110`). Cinco agentes fazendo pytest colidiriam no
  mesmo banco. A única exceção autorizada foi a dívida do fixture, onde medir o sintoma
  custa um arquivo;
* **`archive/` fora de toda busca**.

🔬 **A disciplina se sustentou.** `git status` ao final: um único arquivo novo, o documento
da síntese. Os onze `Write` dos agentes foram auditados um a um — dez foram para o
scratchpad (scripts de medição descartáveis), e o décimo primeiro foi o documento.

---

## 3. O que cada agente fez

⚠️ Horários locais da máquina; a coluna "Bash" é a contagem real de chamadas de ferramenta.

| # | Papel | Dívida | Fim | Bash | O que entregou |
|---|---|---|---|---|---|
| 1 | Levantar | curva de baseline | 11:45 | 48 | 23 âncoras · 6 achados fora do símbolo · esforço **M** |
| 2 | Levantar | lado PAGAR do FluxoCaixa | 11:45 | 53 | 28 âncoras · 9 fora do símbolo · esforço **G** |
| 3 | Levantar | blueprint `rdo_crud` | 12:00 | 52 | 30 âncoras · 8 fora do símbolo · **recomenda MANTER** |
| 4 | Levantar | 302 de outro tenant | 12:05 | 75 | 15 âncoras · 9 fora do símbolo · esforço **M** |
| 5 | Levantar | fixture do operacional | 12:10 | 42 | 17 âncoras · 6 fora do símbolo · esforço **P** |
| 6 | Refutar | curva de baseline | 12:19 | 56 | **4 erros** · 10 confirmações que custaram trabalho |
| 7 | Refutar | lado PAGAR | 12:20 | 51 | **6 erros** · 12 confirmações · achou a catraca do banco |
| 8 | Refutar | 302 | 12:30 | 50 | **2 erros** · 8 confirmações · trocou o eixo do item |
| 9 | Refutar | `rdo_crud` | 12:33 | 51 | **6 erros** · 9 confirmações · derrubou o próprio levantamento |
| 10 | Refutar | fixture | 12:38 | 24 | **2 erros** · 10 confirmações · achou o `Timer` do listener |
| 11 | Sintetizar | — | 12:49 | 19 | o documento de 1018 linhas |

**Totais:** 🔬 **113 âncoras** com `arquivo:linha`, **38 achados que só as lentes 2-5
pegaram**, **20 afirmações provadas falsas** pelos adversários, **49 confirmações** que
resistiram a ataque, e **37 superfícies** que os levantamentos não tinham olhado.

**Custo:** 11 agentes · 548 chamadas de ferramenta · 1.279.699 tokens de subagente ·
74min15s de relógio. Zero erros, zero agentes vazios.

---

## 4. O resultado, em uma linha

**As cinco dívidas sobreviveram. O recorte de quatro delas caiu.**

Nenhum adversário conseguiu derrubar uma dívida inteira — todos os cinco vereditos foram
`confirmado_com_correcoes`. Mas o trabalho não foi confirmar o que já sabíamos: foi
descobrir que **quase todas as prescrições do plano e do fecho estavam erradas sobre como
consertar**. As cinco que caíram:

| Prescrição derrubada | Por quê |
|---|---|
| "espelhar a B3.8 no lado pagar" | 🔬 do lado receber o **leitor já existia** antes da B3.8; do lado pagar não há leitor. A Task nasceria inerte |
| "não sobrescrever `percentual_planejado`" | 📖 a Curva S **nunca leu** essa coluna. E aplicar isso desfaria as B2.17-B2.20 |
| "o teste de convergência congela o 302" | 🔬 a asserção 4 da B2.12 **nunca foi entregue** — nada congela nada |
| "aposentar o blueprint `rdo_crud`" | 🔬 9 das 13 rotas são o único handler do seu path, **cinco são o backend de foto do RDO** |
| "criar o operacional no fixture `ctx`" | 📖 deixa um teste verde e **oco** |

**Brinde:** 🔬 o E04 tem **dois** pontos vivos, não três — `crud_rdo_completo.py:557` mora
em rota sombreada. `models.py:2181`, o plano `:4732` e o `ESTADO-ATUAL.md:939` registram
três, e os três estão errados.

**Dois itens novos que são dinheiro em produção hoje**, e que não estavam em lista nenhuma:
🔴 `estornar_conta` **não devolve** `banco.saldo_atual` — e esse número é literalmente o
`saldo_inicial` do fluxo de caixa (📖 `financeiro_service.py:485`); e os dois caminhos de
pagamento discordam sobre debitar o banco, de modo que o saldo inicial depende de **por
qual tela** o pagamento entrou.

O resto — as Tasks B5.1 a B5.5, os 11 itens abertos, os riscos, a ordem de entrega, as 5
contradições registradas e as 5 perguntas — está no documento da rodada.

---

## 5. O que aprendemos sobre o método

**A lente 3 pagou o workflow sozinha.** O corte do blueprint `rdo_crud` estava a um passo de
ser recomendado, e 🔬 as quatro rotas de foto do RDO são consumidas por `fetch()` com **path
literal** em `templates/rdo/editar_rdo.html:1286,1333,1398,1419`. Um `grep -rln 'rdo_crud'
templates/` devolve **um** arquivo, e não é esse. É o padrão E03/E11 aparecendo pela
**terceira vez** — e desta vez ele teria derrubado upload, galeria, legenda e delete de
foto, e transformado `main.visualizar_rdo` em 500.

**Apareceu um padrão novo, e é pior que o do E02.** Lá, o símbolo estava ausente e a string
presente. Aqui: 📖 `views/rdo.py:1587` chama `_rdo_do_tenant_ou_404` de dentro de um `try`
cujo `except Exception` (`:1660`) **engole o `NotFound`**. O símbolo certo está presente e
mentindo — grep pelo símbolo classifica a rota como conforme. **Grep por símbolo não prova
nem morte nem conformidade.**

**A lente 4 exigiu medição, não leitura.** 🔬 Ler `crud_rdo_completo.py` sugere que as 13
rotas sob `url_prefix='/rdo'` estão cobertas pelo `main_bp`; o `url_map` real diz que 9
vencem e 4 perdem. E há uma armadilha embutida: com `from app import app` puro, **nenhuma**
rota de `rdo_crud` existe — os blueprints entram só por `main.py`. Quem medir o `url_map`
sem importar `main` mede um app diferente do que o gunicorn serve.

**"Lente vazia" é resultado.** 🔬 Na dívida do 302 a lente 5 não achou nada — nenhuma
migração, seed ou lista de tabelas cita as rotas. Ao contrário da B4.8, ali não há terceiro
consumidor escondido. Saber isso vale tanto quanto achar.

**A adversarialidade pagou onde a concordância teria custado caro.** Dois vereditos
mudaram o item, não o detalhe: o do 302 trocou o eixo inteiro da Task (**de tenant para
obra** — o 302 não é oráculo, e o Status da própria B1.15 já dizia isso), e o do `rdo_crud`
**derrubou o próprio levantamento** que devia defender, mostrando que o exagero estava no
título comprimido da célula da §8.3 e não no corpo do plano.

**Onde os dois não chegaram a acordo, o documento registra a discordância** em vez de
escolher em silêncio — cinco casos, no formato da §9 do plano consolidado.

---

## 6. O que este fecho NÃO atesta

**As 🔬 desta varredura não são minhas.** Elas foram medidas por agentes cujos passos
intermediários não foram supervisionados um a um. O que reabri e conferi pessoalmente, fora
do workflow, foi: a cadeia inteira da B5.1 (`financeiro_service.py:73`, `:118`, `:133`,
`:215-218` e `financeiro_views.py:402-419`, `:425-427`), o `git blame` que a atribui a
`01883756`, e a auditoria dos onze `Write`. **O resto está sustentado pelo par
levantamento/refutação e pelas âncoras que cada um cita — não por conferência minha.**

**⚠️ Toda medição de dado é de DESENVOLVIMENTO.** Os 0 de 627 `ContaPagar`, as 30.196 obras
com baseline, os 6.647 de 50.966 `rdo_foto` em disco: provam a **forma**, não o volume. É a
mesma ressalva que derrubou o gate do E02 em 05/08, e ela vale aqui inteira.

**Nenhuma Task da B5 foi executada, e nenhuma linha de código foi escrita.** O único
artefato de código deste trabalho é a inexistência dele.

**O gate não foi rodado.** Por desenho — nenhum agente podia rodá-lo. A árvore está como
`4b53a6a1` a deixou, e o último gate verde conhecido segue sendo o de 05/08.

---

## 7. Nota operacional para a próxima vez

🔬 A máquina tem **4 núcleos**, e o teto de concorrência do workflow é
`min(16, núcleos − 2)` = **2**. Com onze agentes e duas vagas, o pipeline degenerou para
quase serial: 74 minutos de relógio para ~10 minutos de trabalho por agente.

**A escolha de pipeline em vez de barreira continua certa** — ela não custou nada e teria
pago sozinha numa máquina maior. Mas o dimensionamento tem de contar com o teto: **onze
agentes aqui são cinco horas-agente espremidas em duas filas**, não onze coisas
acontecendo ao mesmo tempo. Para uma varredura maior, ou se divide em execuções separadas,
ou se aceita o relógio.

E há um detalhe que só apareceu porque a varredura o procurou: 🧮 o item novo nº8 do
documento da rodada — o `Timer` de `models.py:8385-8423`, que abre app_context em **thread
de fundo** sobre a `scoped_session` global — significa que rodar o gate em paralelo com
qualquer outro trabalho contra o mesmo banco não é só lento: é **não-determinístico**.

---

## Ponteiros

| O quê | Onde |
|---|---|
| O produto da varredura (Tasks B5.1-B5.5, riscos, ordem, perguntas) | `docs/superpowers/plans/2026-08-06-rodada-b5-varredura.md` |
| O plano que esta rodada sucede | `docs/superpowers/plans/2026-08-04-plano-consolidado.md` |
| O fecho da sessão anterior, e o gate do E02 ainda pendurado | `FECHO-SESSAO-2026-08-05.md` |
| Transcrições por agente e journal do run `wf_b3388f3b-fc1` | `.claude/projects/-home-runner-workspace/<sessão>/subagents/workflows/` |
