# Spec de design — as automações que sobraram

> **Data:** 2026-09-02 · **Origem:** Task 14 de
> `docs/superpowers/plans/2026-08-31-fecho-do-que-esta-aberto.md`
> **Medição que a sustenta:** `docs/reconferencia-backlog-2026-09-02.md`
> (11 itens, cada um reaberto no código de hoje)
>
> Esta é uma **spec de design**: descreve o problema, as opções e a decisão.
> **Não tem tasks.** Os planos vêm depois, um por família, escritos com
> `superpowers:writing-plans`.

---

## 1. O problema

Sobraram 11 automações do lote de 25 de 04/08. Elas são a maior massa de
trabalho aberto do repositório **sem plano próprio** — vivem numa lista, e uma
lista não diz por onde começar nem o que não fazer.

A reconferência de hoje mediu as 11 contra a árvore. **Nenhuma mudou de
veredito** em 10 dias: 6 abertas, 5 parciais, zero entregues. O que mudou foi
o **entorno** — e é aí que está o achado que ordena esta spec.

### 1.1 O achado que reorganiza tudo

🔴 **Duas das seis "bloqueadas por decisão" foram destravadas em 01/09, e
ninguém levou a resposta de volta para a lista de automações.**

| Item | Trava escrita em 04/08 | 🔬 Estado real hoje |
|---|---|---|
| **A15** | "Decisão 4 do `PLANO-NUCLEO.md` (medições históricas)" (`2026-08-04-plano-consolidado.md` §8.2) | ✅ **RESPONDIDA em 01/09** — 📖 `docs/superpowers/plans/2026-09-01-decisoes-respondidas.md:160-186`: *"congelar as históricas. Unificar só da vigência em diante"*, e a resposta **nomeia o conserto**: *"a rota do portal passa a delegar a `gerar_medicao_quinzenal` para as novas"* |
| **A23** | "Não existe canal interno para plugar... a decisão de qual canal (Decisão 7) nem foi tomada" (§8.1) | ✅ **RESPONDIDA em 01/09** (`:212-231`: n8n + cron externo) **e a premissa técnica está falsa**: 📖 o canal existe inteiro — `utils/webhook_dispatcher.py:203` (`dispatch_webhook`), allowlist em `:59`, listener universal registrado no boot (`app.py:434-440`), com teste (`tests/test_webhook_dispatcher.py`) |

O item A23 é o caso mais nítido: foi **cortado em 04/08 com a razão "não existe
canal"**, e 🔬 `utils/webhook_dispatcher.py` tem mtime de **22/07** — o canal já
existia quando o corte foi escrito. A razão do corte estava errada no dia em
que foi escrita, e ninguém reabriu porque ninguém remediu.

**Consequência de método, e ela vale além destas 11:** uma lista de itens
travados por decisão apodrece de um jeito específico — a decisão é respondida
noutro documento, e o item continua marcado como travado. É o mesmo
apodrecimento que o ledger da casa já registrou duas vezes com cabeçalhos de
plano (Onda 1 em `d5a0e9bd`, Onda 2 em `fed8f19b`), agora na forma de trava em
vez de checkbox.

### 1.2 O segundo achado: o eixo de agrupamento

A Task 14 manda agrupar **por família de domínio**. A medição diz que o eixo
que realmente separa o trabalho é **o que bloqueia cada item**:

| Bloqueio | Itens | O que falta |
|---|---|---|
| **Nada — só braço e teste** | A01, A11, A16, A17, A21(b), A22 | Escrever o código e o teste |
| **Decisão já respondida, não colhida** | A15, A23 | Colher a resposta e executar |
| **Decisão de verdade em aberto** | A08, A13 (origem), A20, A21(a) | Uma resposta humana **antes** do código |

**Decisão desta spec: uso os dois eixos, e o de domínio manda no plano.** As
famílias são de domínio (é o que faz o executor não trocar de contexto a cada
task); o bloqueio decide **a ordem** entre elas e **o que sai da fila**.

---

## 2. As opções consideradas para o recorte

### Opção A — um plano só, com as 11
❌ **Descartada.** É o que a Task 14 já proíbe, e a medição confirma a razão:
as 11 tocam 14 arquivos de 6 domínios diferentes. Um plano único obriga o
executor a trocar de domínio a cada task, e o custo real disso não é tempo — é
que o julgamento sobre "este teste realmente alcança o código?" fica raso
quando o contexto muda toda hora. 🔬 Esta linhagem de planos já registrou
**nove ocorrências** de andaime de teste que passa verde sem tocar o código sob
teste (ledger de `2026-08-31-fecho-do-que-esta-aberto`, entradas de 31/08).
Trocar de domínio a cada task é como se produz a décima.

### Opção B — um plano por item (11 planos)
❌ **Descartada.** Cinco dos itens compartilham arreio de teste
(`tests/test_arreio_custo_rdo_rotas.py`, `tests/test_arreio_presenca_rotas.py`)
e três compartilham arquivo. Onze planos duplicariam a mesma preparação de
cenário onze vezes, e cada duplicação é uma chance de os cenários divergirem —
que é como se produz dois testes que afirmam coisas incompatíveis sobre o mesmo
código.

### Opção C — três planos por família de domínio, ordenados por bloqueio ✅
✅ **Escolhida.** Cada família tem superfície, risco e arreio próprios; a ordem
entre elas segue o bloqueio, não o número do item.

---

## 3. A decisão: o que fazer, e em que ordem

### Família 1 — RDO × ponto  ·  **A11, A16, A17**  ·  *primeira*

**Por que primeira.** É a família com a maior alavanca de teste já construída e
é a única cuja lacuna **tem guarda ativa**: 🔬 dois `xfail(strict=True)`
nomeiam a metade que falta do A16 —
`tests/test_p1_dedup_cross_origem.py:98` e
`tests/test_arreio_presenca_rotas.py:391`. `strict=True` significa que o dia em
que alguém corrigir e esquecer de tirar a marca, **o gate falha por XPASS**. É
o único lugar destas 11 onde o repositório acusa sozinho.

**A ordem interna não é negociável, e a razão está escrita desde 04/08**
(`2026-08-04-plano-consolidado.md:4765`):

1. **A11** — a guarda cruzada no ramo horista (`event_manager.py:494-578`).
   📖 Hoje a idempotência olha só `categoria='PONTO_ELETRONICO'` (`:523-533`);
   a única `categoria='RDO'` do arquivo é `:960`, e é escrita. A forma do
   conserto já existe pronta no ramo diarista (`:356-372`).
2. **A16** — emitir `ponto_registrado` nos três sítios que faltam
   (`models.py:4791`, `equipe_views.py:1201`, `ponto_service.py:324`).
   ⚠️ **Depois do A11, nunca antes**: emitir do ramo do plano antes de a guarda
   existir é lançar custo por cima de um atestado. O próprio plano de 04/08
   escreveu essa ordem, e ela continua certa.
3. **A17** — pré-carregar a mão de obra do RDO da presença do dia
   (`views/rdo.py:617`). É a única funcionalidade nova da família, e ela senta
   em cima do custo que as duas anteriores estabilizam.

**🔬 A trava do A17 caiu.** O plano de 04/08 (`:4761`) adiou o A17 "**depois de
B1 estabilizado e com o arreio de B0 verde nas rotas de RDO e ponto**". B1 está
entregue (A05 e A10 ✅ desde 23/08) e os dois arreios existem. **A condição
escrita para destravar está cumprida** — o A17 não espera mais nada.

**⚠️ A armadilha desta família** é o perfil de remuneração. O ramo horista do
`event_manager` só é alcançado com o perfil certo semeado; um teste escrito com
o perfil errado passa verde sem tocar o ramo. O helper existe
(`tests/helpers_tenant.py`, `um_tenant()` parametriza remuneração) — **o plano
tem de exigir prova de RED**, não de GREEN.

**Decisão pendente que NÃO bloqueia a família:** a **D6** do plano consolidado
(`:4978` — "ponto SEMEADO pelo plano deve gerar custo?") segue **sem resposta**.
📖 Ela tem **default escrito**: *"manter como está (não emitir) e executar só a
guarda"*. **Decisão desta spec: seguir o default e registrar o buraco nomeado.**
Se o dono responder depois, o A16 ganha um sítio a mais; nada do que for feito
sob o default precisa ser desfeito.

⚠️ **Colisão de nomenclatura, registrada para não custar uma hora a alguém:**
"D6" designa **duas decisões diferentes** neste repositório — a D6 do plano
consolidado (`:4978`, ponto semeado, **aberta**) e a Decisão 6 do
`PLANO-NUCLEO.md:542` (rateio de encargos patronais, **respondida em 01/09**).
🔬 Confirmei que `PLANO-NUCLEO.md` **não contém as strings "D6" nem "D7"** — as
citações cruzadas do plano consolidado ("D6 (§10)", "Decisão 7 do
`PLANO-NUCLEO.md`") apontam para rótulos que só existem no documento de origem
de cada uma.

---

### Família 2 — Portal × medição  ·  **A15, A23**  ·  *segunda*

**Por que segunda, e por que juntas.** As duas foram destravadas em 01/09 e
nenhuma das duas respostas foi colhida. É a família onde a decisão já está
tomada e o que falta é **executar o que foi decidido** — trabalho de risco
baixo e valor alto, porque não precisa de mais nenhuma pergunta ao dono.

**A15 — a medição do portal deixa de ser um gerador paralelo.**

📖 O defeito, medido: existem exatamente **dois** escritores de `MedicaoObra`
(🔬 `grep -rn "MedicaoObra(" --include=*.py .` fora de `archive/`/`tests/`):
- `portal_obras_views.py:942` — grava **acumulado** (`:940`, `valor_contrato ×
  perc / 100`), sem `MedicaoObraItem`, sem `recalcular_medicao_obra`;
- `services/medicao_service.py:140` — grava o valor do **período** (`:198`).

**Duas semânticas na mesma coluna da mesma tabela, e nenhum teste afirma qual é
a certa.** 🔬 Os dois testes que tocam a rota guardam outra coisa:
`tests/test_escopo_cronograma_interno.py` guarda o *escopo* do percentual
(cópia-cliente e tarefa arquivada não contam) e `tests/test_porta_irma.py:262`
guarda o `@admin_required`.

📖 A decisão de 01/09 já diz o que fazer: **congelar as históricas** (com
marcador de versão de cálculo na `MedicaoObra`, dizendo qual fórmula gerou cada
linha) e **a rota do portal delega a `gerar_medicao_quinzenal`** para as novas.

⚠️ **O risco desta task é o único desta spec que move dinheiro já comunicado ao
cliente.** `valor_medido` está gravado em produção com a semântica acumulada.
O marcador de versão **não é enfeite**: sem ele, depois da unificação ninguém
consegue dizer qual linha do histórico veio de qual fórmula, e a pergunta vai
ser feita.

**A23 — o aviso interno passa pelo canal que já existe.**

📖 O estado, medido do jeito mais limpo possível: em `portal_obras_views.py`,
🔬 `grep -c` de `notific` = **0**, de `EventManager` = **0**, de `.emit(` =
**0**. As três rotas (`:577` aprovar, `:685` recusar, `:723` comprovante)
terminam em `logger.info` + `flash`. O arquivo não tem sequer o vocabulário.

📖 O canal existe: `utils/webhook_dispatcher.py` — allowlist explícita (`:59`),
`dispatch_webhook` (`:203`), listener universal registrado por evento da
allowlist no boot (`:488-506`, chamado de `app.py:434-440`), entrega auditada
em `WebhookEntrega` com retry e backoff, e **nunca propaga exceção para o
handler chamador** (best-effort por desenho). **O recorte do A23 encolheu de
"construir um canal" para "emitir três eventos e acrescentá-los à allowlist".**

⚠️ **A trava que sobra do A23 não é código: é a credencial.** Sem
`N8N_WEBHOOK_URL` o despachante é no-op silencioso (`:230`). Emitir os eventos
é útil de qualquer forma — eles ficam no `EventManager` e passam a existir para
qualquer consumidor futuro — mas **ninguém vê aviso nenhum até a variável
entrar**. Isso tem de estar escrito no plano, ou a task será dada como entregue
e o dono vai perguntar por que não recebeu nada.

---

### Família 3 — Cauda de conserto barato  ·  **A22, A21(b), A01**  ·  *terceira*

⚠️ **Esta família é uma exceção deliberada à regra "agrupar por domínio".** Os
três itens não compartilham domínio nenhum — propostas, RDO e importação. Estão
juntos por **tamanho**: cada um é uma task, num arquivo próprio, sem
sobreposição com nada. Agrupá-los por domínio produziria três planos de uma
task cada, e o custo de escrever três planos supera o de executar os três
itens. **Digo isso aqui para que ninguém leia o agrupamento como afirmação de
parentesco técnico.**

- **A22 — persistir o CPF/CNPJ da proposta.** 📖 `models.py:3716` (`class
  Proposta`) não tem a coluna; `propostas_consolidated.py:599` lê o valor numa
  variável que 🔬 nunca é usada (único acerto de `cliente_documento` no
  arquivo); dois templates leem `proposta.cliente_cpf_cnpj` e o Jinja resolve
  como Undefined em silêncio (`templates/propostas/editar.html:97`,
  `templates/propostas/detalhes_proposta.html:159-160`).
  🔬 **Achado que barateia a task:** o evento `proposta_aprovada` **já reserva a
  chave** e manda `None` nos três sítios de aprovação
  (`propostas_consolidated.py:1150`, `:2511`, `:2693`). O contrato do consumidor
  não muda.
  ⚠️ **Armadilha:** `cliente_cpf_cnpj` **existe** em `models.py:2543` — em
  `ContaReceber`, com índice próprio em `:2579`. Um grep apressado conclui que a
  coluna já existe na proposta.
  📖 **A escolha entre as duas saídas é a D8** (`2026-08-04-plano-consolidado.md:5017`):
  ponteiro (`Cliente.cnpj` via `proposta.cliente_id`, sem coluna nova) ou
  snapshot (coluna + migration). A pergunta **não é técnica** — é se corrigir o
  cadastro pode reescrever retroativamente uma proposta já assinada.
  **Decisão desta spec: executar a saída PONTEIRO**, que é a mais barata, não
  cria migration e é reversível; e **escalar a D8 como ratificação**, não como
  bloqueio. Se a resposta vier "snapshot", o que se perde é uma task pequena.
- **A21(b) — os três kwargs inválidos.** 📖 `crud_rdo_completo.py:427`
  (`horas_utilizacao=`) e `:428` (`observacoes=`) contra `RDOEquipamento`
  (`models.py:1443-1452`, que tem `horas_uso` e nenhuma `observacoes`); `:448`
  (`descricao_completa=`) contra `RDOOcorrencia` (`models.py:1466` é
  `descricao_ocorrencia`). Função sem rota desde `b30923b5`.
  🔴 **A razão de isto entrar agora, e não continuar adiado:** o commit
  `ce331094` (27/08) **diz na mensagem** ter consertado "kwargs de colunas
  inexistentes" em `salvar_rdo` — e 🔬 o diff mostra que consertou os do
  construtor de `RDO`, não estes três. **A função está meio consertada, e o log
  do repositório afirma que está inteira.** Um estado meio consertado com
  registro dizendo o contrário é pior que qualquer um dos dois estados puros.
- **A01 — o confirm da importação lê as transferências.** 📖
  `importacao_views.py:942-947` manda três chaves; o payload de transferências
  é montado (`services/importacao_excel.py:1840`, `:1964`, `:2122`), exibido no
  preview (`importacao_views.py:453`, `:473`, `:515`, `:550`, `:701`) e
  **descartado no confirm**. Zero commits nos dois arquivos em 10 dias.
  ⚠️ **A armadilha é o tenant:** uma transferência aceita com conta de outro
  admin move dinheiro entre empresas. O teste tem de afirmar a **recusa**, não
  só o caminho feliz.

---

## 4. O que decidiu-se NÃO fazer — e para onde cada um vai

Esta seção é a razão de a spec existir. Cada linha abaixo é **decisão**, com
destino escrito — não esquecimento.

### 4.1 A08 — importação de alimentação gerar custo · **FORA. Destino: fila de decisão do dono.**

📖 Medido: `services/importacao_excel.py:883-919` cria `AlimentacaoLancamento`
e a M2M, e nada mais. 🔬 `registrar_custo_automatico` aparece no arquivo em
`:656/:747/:768/:781` (diárias) e `:1019/:1025` (transporte) — **nenhum na
janela `:807-924`** da alimentação.

**Por que não entra:** a metade mecânica é pequena; a outra metade não é código.
📖 `restaurante` é texto livre, sem `entidade_id`, sem `centro_custo_id`, sem
`obra_servico_custo_id`, e a regra de rateio (por centro de custo × agregado por
obra) segue sem resposta desde 04/08 (`2026-08-04-plano-consolidado.md:4767`).

⚖️ **O critério que decide:** custo lançado no lugar errado é pior que custo não
lançado. O não lançado é um buraco visível; o errado se esconde dentro de um
número plausível e contamina resultado por obra, margem e preço. **Escrever o
código antes da regra é a forma cara de errar.**

**Destino:** entra na próxima rodada de decisões do dono, junto com a pergunta
escrita: *"o custo de alimentação importado é rateado por centro de custo ou
agregado por obra?"*.

### 4.2 A13, a origem · **FORA desta onda. Destino: plano próprio, depois da decisão.**

🔴 **A medição de hoje aumentou o item, não o diminuiu.** A origem tem **três**
escritores de venda em `valor_orcado`, não os dois registrados em 23/08:

| Sítio | Natureza |
|---|---|
| `medicao_views.py:316` | rota — alguém clica |
| `views/catalogo_views.py:905` | rota — alguém clica |
| **`models.py:8424`** | 🔴 **listener `after_insert` de `ItemMedicaoComercial`** — dispara sozinho a cada aprovação de proposta, pelo caminho `handlers/propostas_handlers.py:55` |

Some-se o fallback deliberado de `services/custo_orcado.py:137` (serviço sem
linha de custo usa `valor_orcado`, isto é, venda) e o backfill das obras já
gravadas.

**Por que não entra:** ⚖️ a Decisão 3 do `PLANO-NUCLEO.md:539` foi respondida
em 03/08 — *"consertar no CONSUMO"* — e o consumo **está fechado com teste**
(`tests/test_a13_orcado_de_custo_no_consumo.py`, que afirma o estado do banco
depois de um GET). Consertar a origem agora, sem backfill, cria **duas
populações** no banco (gravadas antes e depois) que nenhum consumidor sabe
distinguir. Isso é estritamente pior que a situação de hoje, em que a origem
está errada mas **uniformemente** errada e ninguém a lê como custo.

**Destino:** plano próprio, e só depois de o dono responder *"a origem passa a
gravar custo, e o que se faz com o já gravado?"*. 📖 O plano de 04/08 registra a
origem como "a saída definitiva" — ela não foi descartada, foi sequenciada.

### 4.3 A20 — pré-preencher o pedido com o vencedor · **FORA. Destino: reabrir o corte com o dono.**

📖 Foi **cortado** em 04/08 (`2026-08-04-plano-consolidado.md` §8.1) com a razão:
*"custa coluna + migração + tela de amarração para poupar um preenchimento"*.

🔬 **Uma das três parcelas do custo já não existe.** `RequisicaoCompra.mapa_v2_id`
é coluna real desde 23/07 (`models.py:6223`, relacionamento em `:6277`) e há
rota viva que a preenche (`compras_views.py:2351`). **O elo requisição → mapa
não precisa ser construído.** Falta o elo mapa → `Fornecedor`
(`models.py:7787` — o fornecedor ainda é `nome = String(200)`, sem FK) e a
leitura no momento de emitir (`compras_views.py:2891` usa `preco_estimado`,
nunca `MapaCotacao.valor_unitario`).

**Por que não entra mesmo assim:** ⚖️ **um corte por custo>benefício não se
reverte porque o custo caiu — se reverte porque o dono do produto decidiu que
vale.** O benefício continua sendo o mesmo de 04/08 (poupar um preenchimento e
evitar erro de digitação de preço). Esta varredura não tem mandato para
reavaliar benefício.

**Destino:** vai ao dono com o fato novo escrito, como pergunta de uma linha:
*"o custo do A20 caiu — o elo requisição→mapa já existe. Reabrir?"*.

### 4.4 A21(a) — FK de frota no equipamento do RDO · **FORA. Destino: continua cortado.**

📖 `RDOEquipamento` (`models.py:1443-1452`) segue com `nome_equipamento` como
texto livre; 🔬 zero `veiculo_id` em `utils/rdo_equip_ocorr.py` e nos dois
templates. A razão do corte de 04/08 era *"integração **sem dor relatada**"* —
🔬 **nada mudou nisso em 10 dias.** Coluna + migration + dois templates + parse,
para um problema que ninguém reportou.

**Destino:** continua cortado. Volta se, e só se, aparecer dor relatada — e aí
vira plano próprio, não task de cauda.

### 4.5 A18, A24, A25 · **FORA DO ESCOPO desta spec.**

⚠️ A Task 14 enumera ~13 itens e inclui os três. A reconferência mediu **11** —
os três mudaram de estado em 01/09 (`9f169c0d` para A18, `9aead796` para A24, o
runbook `docs/operacao-agendamentos.md` para A25) e o registro de 01/09 já os
move para a faixa de **RATIFICAR / credencial**. **Não foram medidos hoje**, e
esta spec não afirma nada sobre eles.

**Destino:** quem escrever o plano decide se voltam. A decisão é sobre
ratificação humana, não sobre código.

---

## 5. Decisões a escalar — não são tasks

### 5.1 ⚠️ `obra.progresso_conclusao` — decisão do dono, não item de fila

📖 O card de obra tenta exibir um atributo que não existe em Python nenhum:
- `templates/obras/detalhes_obra.html:51` e `:54`
- `templates/obras_moderno.html:717`, `:721`, `:724`

🔬 Medido: `class Obra` (`models.py:360`) não tem `progresso_conclusao`. O
`{% if %}` de `obras_moderno.html:717` engole o Undefined e **a barra de
progresso nunca aparece** — sem erro, sem log, sem sintoma além da ausência.
(⚠️ Não confundir com `rdo.progresso_conclusao`, que é outro objeto e aparece
em `detalhes_obra.html:750` e `detalhes_obra_profissional.html:2162` — esse
existe.)

📖 O registro é explícito e vem sendo repetido desde 23/08
(`docs/planos-em-aberto-2026-08-23.md:254`,
`docs/planos-em-aberto-2026-08-25.md:230`,
`2026-08-31-fecho-do-que-esta-aberto.md:114`,
`2026-09-01-as-decisoes-viram-codigo.md:1218`): **"funcionalidade nova, não
conserto — entra na onda das automações ou morre; decisão do dono."**

**Esta spec NÃO decide.** Escala como pergunta de uma linha:

> **Q:** a barra de progresso no card de obra deve passar a funcionar? Se sim,
> ela mostra o progresso ponderado do cronograma (`progresso_ponderado_armazenado`,
> `utils/cronograma_engine.py:1222`) ou o percentual da última medição? São
> números diferentes, e a escolha define qual.

⚖️ **Por que é decisão e não task:** ligar a barra é escolher **qual número o
dono da obra vê primeiro ao abrir a tela**. Há pelo menos dois candidatos vivos
com semânticas diferentes, e a A15 (nesta mesma spec) está prestes a mexer num
deles. Escolher errado é pior que a barra continuar ausente — uma barra ausente
não engana ninguém.

### 5.2 D8 — CPF/CNPJ: ponteiro ou snapshot? · **ratificação, não bloqueio**

📖 `2026-08-04-plano-consolidado.md:5017`. Quem responde: quem responde pelo
documento contratual. Esta spec **decide executar a saída ponteiro** (§3,
Família 3) e escala a pergunta como ratificação. Se a resposta for "snapshot",
o que se perde é uma task pequena e nenhuma migration.

### 5.3 D6 (plano consolidado) — ponto semeado gera custo? · **default seguido**

📖 `2026-08-04-plano-consolidado.md:4978`, ainda sem resposta. Tem default
escrito, e esta spec o segue: **não emitir do ramo do plano; executar só a
guarda, e registrar o buraco nomeado.** Nada do que for feito sob o default
precisa ser desfeito se a resposta vier depois.

---

## 6. O que esta spec exige de qualquer plano que saia dela

Três constraints, cada uma com a cicatriz que a produziu:

1. **🔬 Teste que prova RED antes de GREEN.** Esta linhagem de planos registrou
   **nove ocorrências** de andaime que passa verde sem alcançar o código sob
   teste (ledger de `2026-08-31-fecho-do-que-esta-aberto`). A causa é sempre a
   mesma: o autor do plano escolhe um gatilho que uma validação anterior
   intercepta. **Nenhuma task destas famílias é dada por feita sem RED
   capturado.**

2. **🔬 Teste que afirma comportamento no banco, nunca texto no fonte.** O
   repositório já pagou por isso: um teste que contava ocorrências da string
   `".ativa = True"` via `inspect.getsource` **reprovou uma correção correta**
   (registrado no ledger, corrigido em `915462d0`). Um teste que conta strings
   não distingue "removeram a funcionalidade" de "substituíram por algo melhor"
   — e nesse modo empurra quem corrige de volta para a implementação ruim.

3. **⚠️ Localizar por conteúdo, nunca por número de linha.** As citações desta
   spec são de 02/09 e vão andar. 🔬 Já andaram nesta própria varredura:
   `medicao_views.py:314` → `:316`, `views/catalogo_views.py:902` → `:905`,
   `models.py:6887` → `:7780`.

---

## 7. Resumo executável

| Ordem | Família | Itens | Bloqueio | Saída |
|---|---|---|---|---|
| **1ª** | RDO × ponto | A11 → A16 → A17 | nenhum (D6 pelo default) | 1 plano, 3 tasks + arreio |
| **2ª** | Portal × medição | A15, A23 | ✅ respondidos em 01/09 | 1 plano, 2 tasks |
| **3ª** | Cauda barata | A22, A21(b), A01 | nenhum (D8 pelo ponteiro) | 1 plano, 3 tasks |
| — | **NÃO fazer** | A08, A13(origem), A20, A21(a) | decisão do dono | 4 perguntas escritas, §4 |
| — | **Escalar** | `obra.progresso_conclusao`, D8, D6 | decisão do dono | §5 |

**Três planos. Oito tasks. Quatro itens fora com destino escrito. Três
perguntas para o dono.**
