# Alçadas — o valor deixa de ser a única pergunta

**Data:** 2026-08-15
**Origem:** pedido do Cássio — "ciclo completo de compras, da solicitação no campo até o
lançamento no fluxo de caixa, com rastreabilidade por um número único".
**Escopo:** a **terceira** das cinco fases em que o pedido foi decomposto. Cobre as quatro
condições que sobem um degrau, o anti-fracionamento, o rito de emergência 48h e o corte
configurável de cotações.
**Depende de:** Fase 1 (recebimento e atesto) e Fase 2 (financeiro em dois fluxos)
mescladas. O rito de emergência consome `situacao_liberacao` da `ContaPagar`, que nasceu
na Fase 2.

---

## ⚠️ Este spec inventa requisito. Leia isto primeiro.

As Fases 1 e 2 nasceram de defeito verificável em produção. **Esta não.** Os quatro
elementos da Fase 3 aparecem no repositório inteiro **quatro vezes**, sempre como rótulo
de backlog ou linha de "fora de escopo" — nunca como enunciado de regra:

| Elemento | Texto de requisito |
|---|---|
| as 4 condições que sobem um degrau | 📖 **não existe** — nunca são enumeradas em lugar nenhum |
| anti-fracionamento | 📖 **não existe** — nenhum doc define janela, agrupamento ou efeito |
| emergência 48h | 📖 **não existe** — só o rótulo "rito de emergência 48h" |
| corte de 3 cotações | 📖 **não existe** como valor — só "corte configurável exigindo 3 cotações" (`docs/superpowers/specs/2026-08-11-recebimento-atesto-design.md:20`), e atribuído à seção 2 (Cotação), não à 3 |

E a pergunta original segue aberta desde julho — 📖 `DEVOLUTIVA.md:293-295`: *"Alçada de
aprovação: qual o valor de X? E a dupla aprovação (GP + Guilherme) é por valor absoluto,
por % do orçamento da obra, ou por categoria?"*. O plano da Fase 3 do núcleo registrou a
recusa de responder por conta própria (📖 `docs/superpowers/plans/2026-07-21-fase-3-compras-governanca.md:122-134`:
*"Não invento número como se fosse fato"*).

Este spec **propôs** as regras, no formato da casa: cada uma virou uma decisão D com
recomendação. O código as trata como **dado editável por tenant**, nunca como `if valor >
5000` — o invariante que a Fase 3 do núcleo já fixou (📖 mesmo plano, `:103`). Trocar os
números depois é UPDATE em tabela, não deploy. Mas **a semântica** (o que conta como
fracionamento, o que a emergência dispensa) é código, e por isso precisava de resposta
antes da A4.

🔬 **15/08: as sete decisões foram fechadas na sessão, todas na recomendação** — ver a
seção "Decisões". Nada aqui espera resposta. O aviso acima fica porque a **origem** das
regras não muda com a confirmação: elas continuam sendo desenho nosso, ratificado, e não
levantamento de processo existente. Quem for medir se a fase acertou tem que medir contra a
operação real, não contra este documento.

---

## O que já existe — e o teto em que ela bate

O motor de alçada está inteiro em `services/alcada_compras.py` (263 linhas) e responde
bem a **uma** pergunta: dado um valor, quantas aprovações e de quem.

- 📖 `services/alcada_compras.py:73` `faixa_para_valor(admin_id, valor)` — faixa ativa de
  menor teto que cobre o valor; `valor_ate IS NULL` é o teto aberto; falha **fechada** numa
  `_FaixaSeguranca` (2 aprovações, exige admin) quando o tenant não tem faixa (`:37-51`).
- 📖 `services/alcada_compras.py:123` `votos_de_aprovacao` — votos da **rodada corrente**,
  escopados desde o achado nº 2 da revisão de 23/07.
- 📖 `services/alcada_compras.py:190` `pode_aprovar` — solicitante nunca aprova (nem ADMIN),
  ninguém vota duas vezes, não-admin precisa de papel na obra.
- 📖 `models.py:6224` `FaixaAlcada` — `ordem`, `valor_ate`, `aprovacoes_necessarias`,
  `exige_admin`, `exige_mapa_concorrencia`, `ativo`, por tenant. Semeada pela migration 243
  a partir de `FAIXAS_RECOMENDADAS` (📖 `services/alcada_compras.py:29-34`): 5k → 1
  aprovação; 30k → 2 + admin; acima → 2 + admin + mapa.

**Três limites, e o terceiro é um bloqueio de verdade:**

1. **A faixa só sabe olhar o valor da linha.** `faixa_para_valor` recebe
  `requisicao.valor_estimado` e mais nada (📖 chamadas em `services/alcada_compras.py:162`,
  `compras_views.py:1766`, `:1789`, `:2016`). Fornecedor novo, preço que não é o menor,
  compra fora do orçamento da etapa — nada disso muda a exigência.

2. **Não existe nenhuma noção de acumulado.** 📖 Zero `group_by` sobre `fornecedor_id` no
  domínio de compras; `RequisicaoCompra` tem índice por `(obra_id, estado)` e
  `(admin_id, estado)` mas **nenhum por data**; `PedidoCompra` não tem índice sobre
  `data_compra`. Dez requisições de R$ 4.900 na mesma semana passam com uma aprovação cada.

3. 🔴 **A faixa de topo é hoje um bloqueio permanente.** `exige_mapa_concorrencia` chama
  `_mapa_serve_de_concorrencia` (📖 `services/alcada_compras.py:146-158`), que exige
  `requisicao.mapa_v2_id`. A rota lê esse campo do form (📖 `compras_views.py:1693`) e o
  grava (`:1735`) — mas **nenhum template tem o input**: 📖 grep por `mapa_v2_id` em
  `templates/` retorna zero. Toda requisição acima de R$ 30.000 fica com uma pendência que
  o usuário **não tem como resolver pela tela**. Isso não é dívida desta fase; é defeito
  aberto da Fase 3 do núcleo, e esta fase é onde ele morre.

> ✅ **15/08, A3: o 🔴 morreu — e precisou de DOIS pontos de escrita, não de um.**
> O spec e o plano falam do campo como se fosse um só, no formulário de criação. Ao
> executar ficou claro que um não basta: quem descobre que a faixa exige concorrência é
> quem abre o **detalhe** da requisição, depois de ela existir — a pendência é exibida lá.
> Com input só na criação, a única saída de uma requisição já criada seria cancelá-la e
> abrir outra, que é a mesma pendência sem saída com outro nome. Ficaram:
>
> 1. `templates/compras/requisicao_nova.html` — select `mapa_v2_id` com os mapas
>    concluídos das obras visíveis, filtrado por obra no cliente; a rota `requisicao_nova`
>    (GET) carrega os elegíveis. O plano nomeia só `requisicao_detalhe` no Step 5, mas o
>    select do Step 4 mora na tela de criação, e ela também precisa da lista.
> 2. `compras.requisicao_vincular_mapa` (POST, novo) e o bloco de mapa em
>    `requisicao_detalhe.html`: vincular um mapa concluído que já existe, **ou** o link
>    para criar um na obra (`/obras/detalhes/<id>#tab-mapa`). Só em RASCUNHO e
>    AGUARDANDO_APROVACAO — depois de virar pedido o mapa é registro histórico da decisão,
>    e trocá-lo reescreveria a justificativa de uma compra já feita.
>
> Os **dois** conferem `obra_id` e `admin_id` do mapa na rota, antes de gravar, além da
> conferência que `services.alcada_compras.mapa_da_requisicao` já fazia. O serviço protege
> a decisão de alçada; a rota impede que o vínculo indevido chegue a existir na linha.

E o mínimo de cotações é 📖 `len(mapa.fornecedores) >= 2`, **literal no código**
(`services/alcada_compras.py:159`) — a única regra de alçada que não é dado.

---

## Modelo de dados

### `faixa_alcada.minimo_cotacoes` — o corte deixa de ser literal

Integer NOT NULL default 0. `0` = não exige mapa. `>= 2` = exige mapa concluído com pelo
menos esse número de fornecedores. Substitui a leitura de `exige_mapa_concorrencia`, que
**permanece na tabela** e passa a ser derivada (`minimo_cotacoes > 0`) — coluna antiga não
se remove no mesmo release que muda o leitor, e há tenant com faixa editada por SQL.

Backfill: onde `exige_mapa_concorrencia = true`, `minimo_cotacoes = 2` — o número que o
código aplicava. **Não** 3: o backfill preserva o comportamento, e subir para 3 é decisão
D6, aplicada por UPDATE depois.

> 📌 **O backfill cobre o tenant que já existe; o SEED cobre o que nascer amanhã.**
> Descoberto ao executar a A3: `FAIXAS_RECOMENDADAS` (📖 `services/alcada_compras.py`) é
> a lista de onde saem as faixas de tenant novo, por `garantir_faixas_do_tenant` e pela
> migration 243. Com o leitor trocado, deixá-la sem `minimo_cotacoes` faria a faixa de
> topo de todo tenant criado a partir de agora nascer com 0 — isto é, **deixando de
> exigir mapa**, silenciosamente, exatamente na faixa em que ele importa. A lista ganhou
> um sexto campo, e o valor semeado é **2**, pelo mesmo motivo do backfill: preservar o
> comportamento. A migration 243 desempacota o campo e o ignora, porque a coluna só nasce
> na 297, que roda depois dela. Subir a faixa de topo para 3 continua sendo a D6, por
> UPDATE, no passo 1 do runbook — e agora vale para tenant novo e antigo pelo mesmo
> caminho.
>
> Na mesma linha, `_FaixaSeguranca` (a falha fechada de tenant sem faixa nenhuma) recebeu
> `minimo_cotacoes = 0`, e **não** 2: ela exige o máximo do que consegue cobrar, e um
> tenant sem faixa configurada também não tem quem monte mapa. Exigir ali travaria a
> compra em vez de endurecê-la.

### `faixa_alcada.condicoes_ativas` — quais das quatro valem neste tenant

String(120) NOT NULL default `''`. Lista separada por vírgula com os códigos das condições
(`fornecedor_novo`, `sem_cotacao`, `nao_menor_preco`, `fora_do_orcamento`). Vazio = a faixa
não sobe degrau por condição nenhuma — que é o comportamento de hoje, e o default.

Por que texto e não quatro booleanos: as condições vão mudar de número (esta fase entrega
quatro; a lista de backlog da seção 2 já tem frete e validade da proposta esperando), e
quatro colunas viram oito sem que ninguém decida por isso.

### `requisicao_compra` — quatro colunas

- `regime_alcada` String(12) NOT NULL default `'simples'` — **o carimbo na linha**.
  `'simples'` = o motor de hoje; `'avancado'` = condições, acumulado e emergência valem.
  Gravado na criação, a partir da flag. Desligar a flag **não** reescreve requisição já
  criada, de propósito — mesma decisão das Fases 1 e 2.
- `emergencial` Boolean NOT NULL default False — invocação do rito.
- `ratificada_em` DateTime nullable — quando os aprovadores da faixa ratificaram a
  emergência. NULL numa requisição emergencial = pendente ou vencida; a diferença é o
  relógio, não uma terceira coluna.
- `degrau_aplicado` String(200) NOT NULL default `''` — **por que** esta requisição subiu:
  os códigos das condições que dispararam mais `fracionamento` se foi o acumulado. É trilha,
  não decisão: quem reabre a requisição seis meses depois precisa ver o motivo sem
  recalcular uma janela que já passou.

### Índices

`ix_requisicao_obra_etapa_criada (obra_id, obra_servico_custo_id, created_at)` e
`ix_pedido_admin_fornecedor_data (admin_id, fornecedor_id, data_compra)`. Sem eles o
acumulado do anti-fracionamento faz varredura por tenant a cada envio de requisição.

---

## Regime de virada

Flag `alcadas_avancadas_ativa` em `configuracao_empresa`, nasce OFF, no molde de
`scripts/flag_financeiro_dois_fluxos.py`.

**A cadeia passa a ter cinco elos:** `alcadas_avancadas_ativa` → `compras_governanca_ativa`
→ `escopo_obra_ativo`. O `--ligar` **recusa tenant sem `compras_governanca_ativa`**, e a
recusa imprime o comando exato da flag que falta.

⚠️ **A dependência é dura, não estética.** Com `escopo_obra_ativo` OFF,
`papel_de_usuario_na_obra` devolve GESTOR a **todo** autenticado do tenant (📖
`utils/autorizacao.py:147-160`) — qualquer um aprova, e só o ADMIN emite. Foi o achado
🔴 nº 1 da revisão de 23/07. Alçada avançada sobre esse chão não endurece nada: só
multiplica as pendências que a mesma pessoa pode resolver sozinha.

Com a flag OFF, `faixa_efetiva()` devolve exatamente `faixa_para_valor()` e nenhuma coluna
nova é lida. É isso que o teste de paridade prova.

---

## Fluxo, com a flag ligada

### O motor ganha uma pergunta, não um segundo motor

`faixa_para_valor(admin_id, valor)` continua existindo, intocado, e continua sendo a
resposta para "que faixa cobre este valor". A regra nova mora numa função acima dela:

```
faixa_efetiva(requisicao) →
    base   = faixa_para_valor(admin_id, valor_para_alcada(requisicao))
    degrau = quantas condições ativas dispararam  (0 se regime 'simples')
    retorna a faixa de ordem (base.ordem + degrau), limitada à de topo
```

Duas propriedades que isso preserva e que uma segunda máquina de regras perderia:
o degrau nunca inventa exigência que o tenant não configurou (só anda entre faixas que
existem na tabela), e nunca **desce** — teto é teto.

> 📌 **15/08, A4: o degrau anda POSIÇÕES na escada, não números de `ordem`.**
> O pseudocode acima diz "a faixa de ordem (base.ordem + degrau)". Ao executar ficou
> claro que somar à `ordem` só funciona enquanto a numeração do tenant não tiver buraco —
> e nada a impede de ter, porque `ordem` é digitada (a tela da A7 valida o que nasce
> nela, não o que já está no banco). Num tenant com faixas 1, 2 e 9, um degrau a partir
> da 2 procuraria uma faixa 3 que não existe e o resultado seria "nenhuma faixa", isto é,
> um degrau que **desce**. `faixa_efetiva` ordena as faixas ativas por `ordem`, acha a
> posição da base na lista e anda N posições, saturando na última. O efeito é o mesmo
> quando a numeração é contígua, que é o caso semeado.
>
> Na mesma execução, duas escolhas que o spec não fixava e que passam a estar fixadas:
>
> 1. **`degrau_aplicado` só cresce.** Nenhuma passada apaga código já gravado, nem
>    quando a condição deixou de disparar. É o que a própria seção "Modelo de dados"
>    pede ("é trilha, não decisão") e recalcular daria outra resposta: depois da emissão
>    o fornecedor novo já não é novo, e apagar o código apagaria justamente o motivo da
>    exigência que a compra cumpriu. O campo também preserva código que este módulo não
>    conhece, para que `fracionamento` (A5) não seja varrido por uma passada de condições.
> 2. **Quem manda é o `regime_alcada` da linha, e a flag não é consultada na decisão.**
>    É a leitura literal de "Regime de virada" + "Rollback", e vale nos dois sentidos:
>    requisição `'simples'` não sobe degrau ainda que a flag esteja ligada hoje.

### `valor_para_alcada` — onde o acumulado entra

Não é `valor_estimado`; é o maior entre o valor da linha e o **acumulado da janela**:

- **Na requisição** (chokepoint `requisicao_enviar`, 📖 `compras_views.py:1817`): soma o
  `valor_estimado` das requisições da mesma `(obra_id, obra_servico_custo_id)`, nos últimos
  N dias, em estado não terminal ou já convertido. Agrupa por etapa porque **a requisição
  não tem fornecedor** — ele só é escolhido na emissão (📖 `PedidoCompra.fornecedor_id` NOT
  NULL, `models.py:5664`; a requisição não tem a coluna).
- **Na emissão** (chokepoint `requisicao_emitir_pedido`, 📖 `compras_views.py:1974`): soma
  o `valor_total` dos pedidos do mesmo `(admin_id, fornecedor_id)` na mesma obra, nos
  últimos N dias. É aqui que o fracionamento por fornecedor aparece, e só aqui pode aparecer.

Quando o acumulado cruza um teto que a linha sozinha não cruzaria, a requisição **sobe de
faixa e grava `fracionamento` em `degrau_aplicado`**. Não bloqueia: bloquear compra
legítima de obra grande gera contorno por fora do sistema, que é exatamente o que a fase
quer evitar. O que ela faz é **tirar a decisão de quem estava dividindo**.

> 📌 **15/08, A5: quatro coisas que o spec deixava em aberto e que passam a estar fixadas.**
>
> 1. **O acumulado move a BASE; as condições andam a partir dela — e o fracionamento não
>    é contado duas vezes.** `decisao_de_alcada` faz `partida = faixa_para_valor(
>    valor_para_alcada(...))` e depois anda `len(condições disparadas)` posições a partir
>    de `partida`. O campo `base` da `DecisaoAlcada` continua sendo a faixa **do valor da
>    linha**, porque é ele que a tela mostra como "pelo valor, cairia em" — sobrescrevê-lo
>    com a faixa do acumulado esconderia justamente o fato que gerou a exigência.
>    `condicoes_disparadas` recebe `partida`, e não `base`: `sem_cotacao` pergunta o
>    mínimo de cotações **da faixa**, e depois do fracionamento a faixa é outra.
> 2. **Etapa NULA é um grupo, não "todas as etapas".** Requisição sem centro de custo
>    apontado acumula com as outras requisições sem centro de custo da mesma obra. É a
>    leitura literal de "mesma `(obra, etapa)`" quando a etapa é NULL, e é a que o
>    fracionamento precisa: omitir a etapa é a forma mais fácil de dividir uma compra.
> 3. **`acumulado_da_etapa` inclui a própria requisição; `acumulado_do_fornecedor` não
>    inclui a compra que está sendo emitida.** A assimetria é do mundo, não do código: a
>    requisição já é uma das linhas da `(obra, etapa)`; o pedido ainda não existe. É por
>    isso que `valor_para_alcada` é `max` e não uma soma — sem o `max`, a emissão de uma
>    compra grande num fornecedor de histórico pequeno cairia numa faixa **abaixo** da do
>    próprio valor.
> 4. **A janela nunca é literal no código, nem no fallback.** `janela_de_fracionamento`
>    lê `configuracao_empresa.janela_fracionamento_dias` e, quando não há linha de
>    configuração, cai no **default da própria coluna**
>    (`ConfiguracaoEmpresa.__table__.c.janela_fracionamento_dias.default.arg`), e não num
>    `30` repetido no serviço. Duas fontes para o mesmo número é como elas passam a
>    divergir. Valor 0 ou negativo (digitação) também cai no padrão: desligar o acumulado
>    por acidente seria pior que ignorá-lo.

### As quatro condições

| Código | Dispara quando | De onde sai o dado |
|---|---|---|
| `fornecedor_novo` | o fornecedor não tem pedido anterior emitido neste tenant | `PedidoCompra` por `(admin_id, fornecedor_id)` — só avaliável na emissão |
| `sem_cotacao` | a faixa exige `minimo_cotacoes > 0` e a requisição não tem mapa que sirva | `_mapa_serve_de_concorrencia`, que já existe |
| `nao_menor_preco` | o mapa tem fornecedor escolhido que não é o de menor valor no item | `MapaCotacao.selecionado` × `valor_unitario` (📖 `models.py:7442`) |
| `fora_do_orcamento` | a requisição não aponta etapa, ou a soma da etapa passa o previsto | `RequisicaoCompra.obra_servico_custo_id` (nullable, 📖 `models.py:6055`) |

> 📌 **15/08, A4: duas das quatro colunas "de onde sai o dado" estavam desatualizadas.**
> As condições entraram como estão na tabela; o que mudou foi de onde cada uma lê.
>
> 1. **`nao_menor_preco` lê `MapaItemCotacao.fornecedor_escolhido_id`, não
>    `MapaCotacao.selecionado`.** `selecionado` é o campo anterior à Task #21: a migration
>    142 o usou como ORIGEM de backfill para a coluna nova e, desde então, **nenhum
>    caminho de escrita o alimenta** — nem a tela do mapa (📖 `views/obras.py`), nem o
>    portal do cliente (📖 `portal_obras_views.py`), nem o PDF, que já lê a coluna nova.
>    Ler `selecionado` faria a condição não disparar nunca em mapa montado depois da 142,
>    isto é, em todos. O código lê a coluna canônica e mantém `selecionado` como segunda
>    leitura, para os mapas anteriores àquela migration. Comparação só entre cotações de
>    valor positivo: fornecedor que não cotou o item tem zero na célula, e zero não é o
>    menor preço do mundo.
> 2. **`fora_do_orcamento` não lê `ObraServicoCusto.valor_orcado`.** Aquele campo guarda
>    **preço de venda** nesta cadeia — herdado do item comercial pelo listener — e lê-lo
>    como custo é o defeito que a A13/B2.4 já pagou uma vez (📖 `services/custo_orcado.py`,
>    cabeçalho). O previsto vem de `custo_orcado_por_servico`, que é o ponto único da regra
>    "linha de custo vence agregado". A soma que se compara com ele é a das requisições da
>    mesma etapa em estado que ainda consome orçamento (RASCUNHO, AGUARDANDO, APROVADA,
>    CONVERTIDA), mais o valor da própria — mesma lista de estados do acumulado da A5.
>
> E uma consequência de desenho que o spec deixava implícita: **`fornecedor_novo` devolve
> "não avaliada", e não "não disparou", quando não há fornecedor.** A requisição não tem
> a coluna, então no envio a resposta honesta é que não dá para saber; o único ponto que
> consegue avaliá-la é a guarda 2 de `requisicao_emitir_pedido`, que é onde o fornecedor
> é escolhido. Consequência prática, e ela é boa: a aprovação passa pela faixa do valor, e
> é a EMISSÃO que descobre que o fornecedor é novo e cobra o degrau.

`sem_cotacao` merece o parágrafo que os outros não precisam: ela **não** substitui a
pendência de mapa. A pendência continua (a compra não sai sem mapa); a condição existe para
o caso de **dispensa** — fornecedor único, item sem concorrente — que hoje não tem caminho
nenhum e por isso vira requisição travada. Com o degrau, dispensar é possível **e** custa
uma aprovação a mais, registrada.

### O rito de emergência 48h

Uma requisição pode nascer `emergencial` com **justificativa obrigatória** (a coluna
`justificativa` já existe, 📖 `models.py:6055`; a diferença é o `NOT NULL` lógico na rota).

O que a emergência **dispensa**: a aprovação *ex ante*. A requisição vai de RASCUNHO
direto a APROVADA, sem votos, e pode virar pedido na hora. É o ponto inteiro do rito —
material que a obra precisa hoje.

O que a emergência **não** dispensa: nada mais. A alçada continua sendo a mesma, só que
*ex post*: os mesmos `aprovacoes_necessarias` da faixa efetiva, contados pelos mesmos
`votos_de_aprovacao`, dentro de **48 horas corridas** a partir da aprovação emergencial.
Ratificou → `ratificada_em` carimbado, fim. Não ratificou em 48h → **a `ContaPagar` derivada
não libera**.

> 📌 **Por que a sanção é a conta e não a compra.** A alternativa óbvia — reverter a
> requisição, bloquear novos pedidos da obra — pune a obra por um ato administrativo e
> chega tarde: o material já chegou. A Fase 2 acabou de construir o lugar certo:
> `conta_pagar.situacao_liberacao` (📖 migration 288), e `pagar_conta` já tem **uma** porta
> que a consulta. Emergência não ratificada vira conta que ninguém paga até alguém assinar
> embaixo. Não inventamos punição nova: reusamos a que existe, que é onde o dinheiro para.

Consequência de acoplamento, e ela é assimétrica: **se `financeiro_dois_fluxos_ativo`
estiver OFF, a sanção não tem onde morder** (a conta nasce `liberada`). Por isso o
`--ligar` da flag nova **avisa** — sem recusar — quando o tenant não tem os dois fluxos.
Recusar seria errado: as outras três regras funcionam sem eles.

> 📌 **Como o "avisa sem recusar" ficou no código (A2).** `pode_ligar` devolve
> `(bool, motivo)` como no molde da Fase 2, mas aqui o segundo elemento passou a carregar
> **duas** coisas: com `ok=False` é o motivo da recusa; com `ok=True` e texto não vazio é o
> aviso, que o `main()` imprime **antes** de ligar. Foi a forma de não inventar um terceiro
> valor de retorno para uma distinção que é de grau, não de tipo. Quem for ler no passo 2 do
> runbook vai ver a linha começando por `AVISO (não impede ligar):` — a ausência dela é que
> significa cadeia inteira ligada.

### Onde a régua de estados **não** muda

Nenhum estado novo em `EstadoRequisicao` (📖 `models.py:80-99`). Emergência é atributo, não
estado: um `PENDENTE_RATIFICACAO` obrigaria a mexer em `TRANSICOES_VALIDAS` (📖
`services/requisicao_compra.py:74-94`), nos badges, nos filtros e na matriz de governança,
para exprimir o que duas colunas exprimem. A régua unificada de 9 etapas é a **Fase 4** —
e é lá que esse desenho deve ser revisto, com o quadro inteiro à vista.

---

## Decisões — as sete, fechadas em 15/08

🔬 15/08: as sete foram apresentadas uma a uma na sessão, com as alternativas, e **as sete
voltaram na recomendação**. O que segue já é regra, não proposta. A pergunta de
`DEVOLUTIVA.md:293`, aberta desde julho, continua aberta no que ela tem de próprio (alçada
por % do orçamento ou por categoria) — ver "Fora de escopo".

**D1 — as quatro condições. ✅ as quatro recomendadas.**
`fornecedor_novo`, `sem_cotacao`, `nao_menor_preco`, `fora_do_orcamento`. São as quatro
que (a) o código consegue avaliar sem dado novo e (b) descrevem risco de compra, não de
processo. Fracionamento ficou fora da lista de propósito — ele é a regra do acumulado, não
uma condição da linha.

> ⚠️ **`fora_do_orcamento` é a mais ruidosa das quatro, e isso foi dito antes de decidir.**
> `obra_servico_custo_id` é nullable (📖 `models.py:6055`), então requisição que
> simplesmente não aponta etapa dispara a condição. É comportamento **correto** — compra
> sem centro de custo é exatamente o que a Fase 4 do núcleo passou a barrar — mas em tenant
> que ainda não preenche etapa com disciplina ela vai subir quase tudo um degrau. Duas
> saídas, nenhuma delas exigindo código novo: medir antes de ligar (o sensor da A8 conta
> quantas requisições dos últimos 30 dias disparariam) e, se o volume assustar, deixar a
> condição fora de `condicoes_ativas` no primeiro tenant e ligá-la depois. É a razão de as
> condições serem lista editável e não quatro colunas.

**D2 — a janela do anti-fracionamento. ✅ 30 dias corridos.**
Por tenant, em `configuracao_empresa.janela_fracionamento_dias`. Mês é a unidade em que a
obra pensa e em que o financeiro fecha. Semana pega compra sazonal legítima; 90 dias
transforma quase toda obra ativa em faixa de topo.

**D3 — o efeito do fracionamento. ✅ degrau, não bloqueio.**
Sobe de faixa e grava o motivo na trilha; a compra segue. Bloqueio empurra a compra para
fora do sistema, e o sistema deixa de saber o que a obra gastou — pior que uma aprovação a
menos.

> 📌 **15/08, A5: na EMISSÃO, "degrau" precisou de uma recusa — e a volta tem um limite
> que este spec não previa.**
> No envio o degrau é degrau puro: a faixa sobe e a requisição segue o caminho normal. Na
> emissão não dá para ser só isso, porque a aprovação **já aconteceu** sob a faixa do
> valor: sem recusa, o acumulado por fornecedor seria descoberto e ignorado no mesmo
> request, e o degrau viraria decoração. A guarda 2b de `requisicao_emitir_pedido` recusa
> a emissão quando o acumulado do fornecedor põe a compra numa faixa mais exigente do que
> as aprovações que a requisição tem — e o faz do jeito que D3 exige: **não reverte nada**
> (o estado segue APROVADA), grava e commita `fracionamento` na trilha, e a mensagem
> nomeia o número (quanto o fornecedor já levou, em quantos dias), o que falta e as duas
> saídas.
>
> ⚠️ **O limite, registrado porque é real:** a saída "volte para aprovação na faixa nova"
> passa por REJEITADA → RASCUNHO → AGUARDANDO (📖 `TRANSICOES_VALIDAS`; de APROVADA não
> se volta para AGUARDANDO), e nesse caminho quem recalcula é o acumulado **da etapa** —
> a requisição continua sem fornecedor. Quando as compras irmãs são da mesma etapa, o
> reenvio cobra a faixa nova e o ciclo fecha. Quando são de etapas diferentes, o reenvio
> devolve a mesma faixa de antes e a emissão recusaria de novo: aí a saída real é emitir
> com outro fornecedor, reduzir o pedido, ou o ADMIN ajustar a faixa. Fechar isso de
> verdade exigiria ou uma requisição com fornecedor candidato (mudança de modelo) ou ler
> `degrau_aplicado` como entrada de decisão — e a seção "Modelo de dados" diz que ele é
> trilha, não decisão. **Fica para a Fase 4**, que revê a régua com o quadro inteiro à
> vista; até lá, a mensagem da recusa é o que impede o beco sem saída.

**D4 — o rito de emergência. ✅ GESTOR da obra e ADMIN; 48 horas corridas.**
Corridas porque a emergência não respeita fim de semana — horas úteis dariam a uma compra
de sexta o mesmo prazo que uma de segunda tem em três dias.

**D5 — a sanção da não-ratificação. ✅ a conta a pagar não libera.**
Pelo motivo do 📌 acima: o material já chegou, e o dinheiro é onde ainda dá para parar.
A alternativa "só avisa" foi oferecida e recusada — sanção que depende de alguém olhar
relatório não é sanção.

**D6 — o corte de cotações. ✅ 3 acima de R$ 30.000.**
Herda o teto da faixa 2, que já existe e já foi semeado: não cria número novo no mundo.
`minimo_cotacoes = 2` nas faixas de baixo, como o backfill deixa — é o que o código faz
hoje, e mudá-lo junto misturaria duas viradas.

> 📌 **O backfill continua sendo 2, inclusive na faixa de topo.** A migration 297 preserva
> comportamento; a subida para 3 é **UPDATE na faixa de topo do tenant**, feito no passo 1
> do runbook, com o Cássio olhando a tela da A7. Migration que muda regra de negócio junto
> com estrutura é migration que ninguém consegue reverter pela metade.

**D7 — a tela de faixas. ✅ entra nesta fase (A7).**
`FaixaAlcada` nunca teve CRUD — 📖 as faixas só existem via migration 243 e UPDATE manual.
Esta fase acrescenta duas colunas com semântica; confirmar os números "antes de ligar a
flag" sem tela para vê-los seria confiar num SELECT que alguém rodou. **Deixa de ser a
task cortável** — o passo 1 do runbook e o UPDATE da D6 dependem dela.

---

## Casos de borda

- **Requisição rejeitada e reenviada** — o acumulado conta a rodada nova, não as duas. O
  filtro é por estado não terminal *ou* CONVERTIDA; REJEITADA e CANCELADA ficam fora.
- **Faixa de topo já é a base** — degrau não tem para onde subir. `faixa_efetiva` satura
  na de maior `ordem`, e grava a condição em `degrau_aplicado` mesmo assim: a trilha
  registra que disparou, ainda que não tenha mudado a exigência.
- **Tenant com uma faixa só** — `_FaixaSeguranca` e faixa única são casos em que o degrau
  é sempre saturado. Não é erro; é tenant com política simples.
- **Emergência em requisição que nunca vira pedido** — não há conta para bloquear; a
  ratificação vence e fica registrada. Aparece no sensor, não numa notificação.
- **Ratificação por quem invocou** — recusada. `pode_aprovar` já barra o solicitante (📖
  `services/alcada_compras.py:206-208`) e a ratificação passa pelo mesmo caminho, de
  propósito.
- **Fornecedor novo emitido duas vezes no mesmo dia** — a segunda já não é novo. É o
  comportamento certo e o teste registra que é intencional.
- **`valor_ate` NULL** — o acumulado nunca cruza um teto que não existe; a faixa aberta
  absorve.

---

## Migrations

A última existente é a **296** (📖 `migrations.py:6889`). 290-295 é faixa reservada da
Fase 8 e 300-307 da Fase 9 — nenhuma das duas aplicada, ambas reservadas em plano de
2026-07-21. Esta fase usa **297, 298, 299**, a única faixa contígua livre, pelo mesmo
motivo que a Fase 2 usou 296 e não 290.

| Nº | O que faz |
|---|---|
| 297 | `faixa_alcada.minimo_cotacoes` (default 0) e `condicoes_ativas` (default `''`); backfill `minimo_cotacoes = 2` onde `exige_mapa_concorrencia` é true |
| 298 | `requisicao_compra.regime_alcada` / `emergencial` / `ratificada_em` / `degrau_aplicado`, com defaults que descrevem o registro histórico; os dois índices do acumulado |
| 299 | `configuracao_empresa.alcadas_avancadas_ativa` (default FALSE) + `janela_fracionamento_dias` (default 30, decisão D2 editável) |

⚠️ Conferir `migration_history` de novo antes de fixar — a conferência já falhou duas vezes
(B6.1 e R1), e a 296 existe justamente por causa disso.

> ✅ **15/08, A1: conferido, e os números não mudaram.** `migration_history` do dev tem a
> **296** como maior aplicada (14/08 17:33) e nada entre 290 e 307. 297-299 seguem livres e
> foram usadas. Repositório e dev concordam.

> 📌 **`migration_history.migration_name` é VARCHAR(200), e estourar isso falha em
> silêncio.** Descoberto ao executar a A1: as descrições longas de 297 (430 chars) e 298
> (249) fizeram o `INSERT` do histórico estourar, e `record_migration` (📖
> `migrations.py:136-144`) **engole a exceção** — a migration rodou, o schema mudou, e ela
> ficou **fora** do histórico. Consequência: seria re-executada a cada boot, e o histórico
> mentiria sobre o estado do banco. Aqui isso foi inofensivo porque as três são idempotentes
> (`IF NOT EXISTS`, e o backfill tem `AND minimo_cotacoes = 0`) — mas numa migration
> destrutiva seria o defeito. A 296 passou raspando, com 180 chars.
>
> **A regra que fica:** a descrição da tupla cabe em 200 caracteres; o "porquê" longo mora
> na **docstring** da função, que é onde ele já morava. Não é dívida desta fase consertar o
> silêncio de `record_migration` — mas é candidato claro a um teste-guarda que compare o
> tamanho das descrições com o limite da coluna.

---

## Testes

`tests/test_alcadas_avancadas.py`, molde de `tests/test_financeiro_dois_fluxos.py`:
fixtures locais, tenant por `uuid4()`, `pytestmark = pytest.mark.integration`, sem depender
de seed. As fixtures **ligam `escopo_obra_ativo` e `compras_governanca_ativa`** — sem isso
todo autenticado é GESTOR e a matriz não distingue ninguém (o tropeço que a Fase 3 do
núcleo já pagou uma vez, 📖 registrado em `tests/test_fase3_matriz_governanca.py:1-11`).

Os que não podem faltar:

- **Paridade:** com a flag OFF, `faixa_efetiva` devolve o mesmo objeto que
  `faixa_para_valor` para uma grade de valores que cruza os três tetos.
- **Falha fechada:** flag ilegível → tratada como OFF.
- **Guarda do `--ligar`:** recusa tenant sem `compras_governanca_ativa`, com o comando na
  mensagem; **avisa e não recusa** quando falta `financeiro_dois_fluxos_ativo`.
- **Carimbo:** `test_todo_ponto_que_cria_requisicao_carimba_o_regime_alcada` — teste-guarda
  que varre o repositório carregando por escrito a lista de pontos conhecidos, no padrão da
  C9. Hoje o ponto é um só (📖 `compras_views.py:1652`); o teste existe para o dia em que
  for dois.
- **Desligar não reescreve o passado:** requisição criada com `'avancado'` continua
  avançada depois do `--desligar`.
- **Degrau:** uma condição sobe uma faixa; duas condições sobem duas; na faixa de topo
  satura e mesmo assim grava `degrau_aplicado`.
- **Acumulado:** três requisições de R$ 4.900 na mesma etapa dentro da janela levam a
  terceira à faixa de 30k; a mesma terceira **fora** da janela fica na faixa de 5k.
- **Fracionamento por fornecedor** só aparece na emissão, nunca no envio.
- **Emergência:** vai a APROVADA sem voto; ratificação dentro de 48h carimba; fora de 48h
  a `ContaPagar` derivada fica `bloqueada`; quem invocou não ratifica.
- **A faixa de topo destravada:** requisição acima de 30k com mapa concluído de 3
  fornecedores **passa pela tela** — o teste que prova que o 🔴 morreu.

---

## Runbook — ligar a flag num tenant

```bash
# 0a. Medir ANTES de decidir: quantas requisições dos últimos 30 dias
#     subiriam de faixa, e por qual condição. Roda com a flag desligada.
python scripts/verificar_consistencia_alcadas.py <ADMIN_ID> --simular

# 0b. Onde o tenant está. A cadeia tem cinco elos e ligar fora de ordem
#     produz requisição travada sem caminho para destravar.
python scripts/flag_escopo_obra.py <ADMIN_ID>
python scripts/flag_compras_governanca.py <ADMIN_ID>     # precisa estar ON
python scripts/flag_recebimento_atesto.py <ADMIN_ID>
python scripts/flag_financeiro_dois_fluxos.py <ADMIN_ID> # OFF só tira o dente da emergência

# 1. Conferir as faixas ANTES de ligar, na tela (A7): Configurações ›
#    Alçadas de compra. Três coisas, nesta ordem:
#    a. os tetos (5k / 30k / aberto) continuam valendo para este tenant?
#    b. subir a faixa de topo para minimo_cotacoes = 3 — é a decisão D6, e
#       ela é UPDATE aqui, não migration. O backfill deixou 2.
#    c. quais condições ficam ativas. Se o tenant ainda não preenche etapa
#       com disciplina, deixe fora_do_orcamento de fora nesta primeira
#       volta (ver o ⚠️ da D1) e ligue depois de medir com o sensor.

# 2. Ligar.
python scripts/flag_alcadas_avancadas.py <ADMIN_ID> --ligar

# 3. Ciclo completo numa obra piloto, conferindo em ordem:
#    a. requisição comum, valor baixo → mesma exigência de antes
#    b. requisição com fornecedor novo → uma aprovação a mais, e o motivo
#       aparece em degrau_aplicado
#    c. três requisições pequenas na mesma etapa → a terceira sobe de faixa
#    d. requisição acima de 30k com mapa de 3 fornecedores → emite (o
#       bloqueio permanente da faixa 3 tem que ter morrido aqui)
#    e. requisição emergencial → aprova na hora; sem ratificar em 48h, a
#       conta derivada não paga

# 4. Sensor.
python scripts/verificar_consistencia_alcadas.py <ADMIN_ID>
```

### Rollback

`--desligar`. Requisição já criada mantém `regime_alcada = 'avancado'` e continua exigindo
o que exigia — de propósito: rebaixar alçada de requisição em curso é o contrário do que a
fase faz. Emergência pendente continua contando as 48h. O que volta ao normal é a
requisição **nova**.

---

## Fora de escopo

A régua unificada de 9 etapas e os 5 relatórios (Fases 4 e 5). Urgência na SC como campo de
prazo (a `data_necessidade` já existe e não é a mesma coisa). Frete, validade da proposta e
condição de pagamento estruturada no mapa — backlog da seção 2, não desta fase. Notificação
de emergência prestes a vencer: depende de `N8N_WEBHOOK_URL` e cron, que são 🔴 decisão 7
em aberto. Alçada por categoria de insumo e alçada como % do orçamento da obra: as duas
alternativas que a `DEVOLUTIVA.md:293` levanta e que esta fase **não** implementa — o valor
absoluto continua sendo a base, pelo motivo já registrado em 21/07 (`Obra.orcamento` é
`Float, default=0.0` e não é confiável como denominador).
