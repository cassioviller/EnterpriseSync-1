# Alçadas avançadas — a exigência de aprovação para de olhar só o valor

**Data:** 2026-08-16
**Origem:** pedido do Cássio — "ciclo completo de compras, da solicitação no campo até o
lançamento no fluxo de caixa". Seção 3 do pedido original (alçadas), mais os dois restos
da seção 1 (urgência) e da seção 2 (corte de cotações).
**Escopo:** as regras que o motor de alçada da Fase 3 não tem. O que ele já faz bem
**não** é reescrito.

---

## Onde esta fase entra

A ordem acordada em 11/08 era: recebimento/atesto → financeiro em dois fluxos →
**alçadas** → status unificado → relatórios. O recebimento fechou e foi mesclado em
`main` em 16/08. A fase financeira foi **adiada por decisão do Cássio na mesma data**:
alçadas vem antes. Nada nesta fase depende do financeiro — a dependência real era a
outra (o financeiro precisa do atesto, que já existe).

---

## O que já existe — e por que não se mexe nele

📖 `services/alcada_compras.py` (263 linhas) responde a três perguntas e só a essas:
em que faixa cai o valor, quem pode aprovar, o que ainda falta. O desenho está certo
nos pontos que costumam sair errados:

| O que já está resolvido | Onde |
|---|---|
| Falha **fechada**: tenant sem faixa nenhuma cai na `_FaixaSeguranca`, que exige o MÁXIMO (2 aprovações, uma de admin) | `:37-52` |
| Voto é `RequisicaoTransicao` AGUARDANDO→AGUARDANDO, não tabela nova | `:237-263` |
| Votos **escopados à rodada**: reenvio depois de rejeição não herda aprovação velha | `:102-134` |
| Separação de funções sem exceção, nem para ADMIN — o solicitante não aprova a própria SC | `:190-227` |
| Faixas por tenant, editáveis sem deploy | `models.py:faixa_alcada` |
| Pendência devolvida como TEXTO, porque é o que a tela mostra | `:161-186` |

O que falta é o que o motor não tem como saber hoje: que a compra foi fracionada, que
estoura o orçamento da etapa, que o mapa tem proposta mais barata, e que alguém marcou
a SC como urgente — 📖 confirmado em 16/08 que `urgencia` não aparece em nenhum arquivo
do repositório, e que não há nada de fracionamento nem de emergência no serviço.

---

## Decisões tomadas na conversa

| Pergunta | Decisão | Consequência |
|---|---|---|
| Quais condições sobem um degrau? | **As quatro**: sem concorrência, estoura o orçamento, não escolheu o menor preço, urgente | Nenhuma delas é o valor — é o que torna a fase necessária |
| Elas somam? | **Somam**, com teto na faixa mais alta do tenant | Duas condições sobem dois degraus. Um teto impede degrau que aponta para faixa inexistente |
| O que é "a mesma compra fracionada"? | **Obra + etapa, janela de 30 dias** | Pega item de texto livre junto, porque não depende do catálogo. SC sem etapa cai num balde único da obra |
| O que o fracionamento faz? | **Julga pela SOMA acumulada**, não por degrau fixo | A SC de R$ 4 mil que fecha R$ 32 mil no período passa a exigir o que a faixa de 30 mil+ exige |
| Emergência: o que dispensa? | **Um admin aprova sozinho agora**; 2ª aprovação e mapa viram dívida de 48h | Sempre existe um responsável com nome. O rito afrouxa o número, nunca a autoria |
| Vencido o prazo, o que trava? | **Nova emergência na obra** | A SC em curso não é travada e a compra normal segue livre. Ataca o abuso, não o trabalho |
| Orçamento: medido contra o quê? | **Etapa quando houver, obra quando não**, contando SC aberta | Contar o comprometido faz a condição disparar antes de o estouro virar fato |
| Quando a alçada é decidida? | **Carimbada ao entrar em aprovação** | A barra não se move debaixo de quem aprova |
| Flag nova? | **Não** | Ver "Duas escolhas contra o óbvio" |
| Sensor de drift? | **Não** | Idem |

---

## 1. Dados — migração 287

🔬 16/08: a maior migração registrada em `main` é a **286** (timbre dos PDFs), depois do
merge que trouxe 283-285 do recebimento. **287 e 288 estão livres.** Conferir
`migration_history` antes de fixar continua sendo a regra da casa (lição da B6.1,
repetida na R1 do plano de compras e confirmada no merge de 16/08).

### `requisicao_compra`

| Coluna | Tipo | Default | Para quê |
|---|---|---|---|
| `urgencia` | VARCHAR(10) NOT NULL | `'normal'` | `normal` \| `urgente` |
| `justificativa_urgencia` | TEXT | NULL | Obrigatória quando urgente |
| `faixa_exigida_id` | FK `faixa_alcada` | NULL | O carimbo: qual faixa vale para esta SC |
| `alcada_degraus` | SMALLINT NOT NULL | `0` | Quantos degraus as condições somaram |
| `alcada_motivos` | JSONB | NULL | As condições que dispararam, com os números que as provam |
| `alcada_carimbada_em` | TIMESTAMP | NULL | Quando. NULL = SC anterior a esta fase |
| `emergencia_ativada_em` | TIMESTAMP | NULL | Quando o rito foi acionado |
| `emergencia_prazo` | TIMESTAMP | NULL | `ativada_em + 48h`, gravado (não calculado na leitura) |
| `emergencia_por_id` | FK `usuario` | NULL | Quem acionou — a autoria que o rito troca pelo afrouxamento |
| `emergencia_regularizada_em` | TIMESTAMP | NULL | Quando a dívida foi paga |

**Por que `justificativa_urgencia` não é NOT NULL:** a validação é do serviço, não do
schema. `NOT NULL` obrigaria backfill em SC legada que nunca teve urgência, e um default
inventado ("—") seria pior do que a ausência. A regra "urgente exige justificativa" vale
para quem escreve daqui em diante.

**Por que `emergencia_prazo` é gravado e não derivado:** 48h é parâmetro de hoje. Se
amanhã virar 72h, a SC já acionada tem de manter o prazo com que foi acionada — o mesmo
princípio do carimbo.

### `faixa_alcada`

| Coluna | Tipo | Default | Para quê |
|---|---|---|---|
| `fornecedores_minimos` | SMALLINT NOT NULL | `2` | Quantos fornecedores o mapa precisa ter para servir de concorrência nesta faixa |

É aqui que mora o **corte de 3 cotações** do pedido original. Não existe um segundo
conceito de "valor de corte": as faixas já **são** o corte por valor, e o tenant já as
edita sem deploy. A recomendação semeada passa a ser 2 / 2 / **3** — a faixa aberta
(acima de R$ 30 mil) exige três.

📖 Isso troca o número fixo de `_mapa_serve_de_concorrencia` (`alcada_compras.py:146-160`,
hoje `len(mapa.fornecedores) >= 2`) por um número da faixa. O comentário de lá — "um
fornecedor só não é concorrência, é orçamento" — continua valendo como piso.

---

## 2. O motor — `avaliar_alcada(requisicao)`

Módulo novo, `services/alcada_regras.py`, importado por `alcada_compras.py`. Separado
porque as quatro condições consultam quatro subsistemas diferentes (mapa, custo orçado,
outras SCs, a própria SC) e inchar o motor de faixas com isso o tornaria o arquivo que
ninguém mais entende — o defeito que este repositório já paga em `compras_views.py`.

Devolve uma estrutura, não um número:

```
Avaliacao(
    valor_estimado,        # o da SC
    valor_efetivo,         # + soma da janela de fracionamento
    somadas,               # [{numero, valor, data}] das SCs que entraram na soma
    faixa_base,            # a faixa de valor_efetivo
    condicoes,             # [{codigo, texto, numeros}] — as que dispararam
    degraus,               # len(condicoes), com teto
    faixa_final,           # faixa_base + degraus, limitada à faixa mais alta ativa
)
```

### Passo 1 — valor efetivo (anti-fracionamento)

Soma `valor_estimado` das SCs do mesmo `admin_id`, mesma `obra_id` e mesmo
`obra_servico_custo_id` (inclusive ambos NULL, que é o balde da obra), com
`created_at >= agora - 30 dias`, nos estados **AGUARDANDO_APROVACAO, APROVADA e
CONVERTIDA**.

📖 Estados em `models.py:EstadoRequisicao`. **RASCUNHO fica de fora de propósito:** um
rascunho abandonado elevaria a exigência de quem está trabalhando, e rascunho não é
compromisso. **REJEITADA e CANCELADA idem** — são justamente a prova de que aquele
dinheiro não vai sair.

A janela é de 30 dias **corridos**, ancorada em `created_at`. Não é mês-calendário: mês
fechado convida a esperar o dia 1º.

**A própria SC fica de fora da soma** (`id != requisicao.id`), e entra uma vez só, no
`valor_efetivo`. No momento do carimbo ela já está em AGUARDANDO_APROVACAO — sem essa
exclusão, ela se somaria a si mesma e todo valor contaria em dobro.

### Passo 2 — as quatro condições

| Código | Dispara quando | Fonte |
|---|---|---|
| `sem_concorrencia` | A SC não tem mapa que sirva de concorrência: ausente, aberto, de outra obra/tenant, ou com **menos de 2** fornecedores — o piso, não o `fornecedores_minimos` da faixa | 📖 `alcada_compras.py:146-160` |
| `estoura_orcamento` | `realizado + comprometido + esta SC > orçado` da etapa (ou da obra, se a SC não tem etapa) | 📖 `services/custo_orcado.py:143` — `projecao_de_custo_por_servico` devolve `{osc_id: {orcado, realizado, …}}`; `custo_orcado_da_obra` (`:51`) para o caso sem etapa |
| `nao_menor_preco` | Existe cotação de valor unitário menor que a selecionada, em qualquer item do mapa | 📖 `MapaCotacao.selecionado` + `valor_unitario` (`models.py`, tabela `mapa_cotacao`); zeros ignorados, porque valor 0 é "não cotou", não "de graça" |
| `urgente` | `requisicao.urgencia == 'urgente'` | A própria SC |

**`comprometido`** = a mesma soma do Passo 1. Reusar o número, e não recalcular por outro
caminho, é o que impede as duas regras de discordarem entre si — a lição do p3 (fonte
única do custo orçado) aplicada aqui.

**Por que `sem_concorrencia` usa o piso fixo de 2, e não o `fornecedores_minimos` da
faixa.** A versão intuitiva — "dispara quando a faixa final exige mapa e o mapa não
serve" — é circular: a faixa final depende dos degraus, que dependem dessa condição. E é
inútil: só dispararia em faixa que **já** exige mapa, onde a pendência de
`exige_mapa_concorrencia` já barra a aprovação. Então as duas coisas são separadas de
propósito, e cada uma responde a uma pergunta diferente:

| | Pergunta | Efeito |
|---|---|---|
| **Condição** `sem_concorrencia` (piso 2) | "Esta compra teve concorrência?" | Sobe um degrau. Vale em qualquer faixa, inclusive a mais baixa |
| **Pendência** `exige_mapa_concorrencia` + `fornecedores_minimos` | "Esta faixa aceita fechar sem mapa de N fornecedores?" | Impede a aprovação até o mapa existir |

Sem laço a resolver, e uma passada só.

### Passo 3 — degraus e teto

`faixa_final` = a faixa de ordem `faixa_base.ordem + degraus`, entre as ativas do tenant.
Se não existir faixa nessa ordem, vale **a mais alta ativa**. Nunca desce: um degrau só
sobe exigência.

Sem faixa ativa nenhuma, tudo isto é curto-circuitado pela `_FaixaSeguranca` que já
existe — falha fechada continua sendo o comportamento de borda, e nenhuma condição pode
torná-la mais frouxa.

---

## 3. O carimbo

`carimbar_alcada(requisicao)` roda na transição **para AGUARDANDO_APROVACAO** — no envio
e a cada reenvio depois de rejeição. É a mesma fronteira que o motor de votos já usa para
abrir rodada (📖 `alcada_compras.py:102-121`), então carimbo e rodada nascem e morrem
juntos, sem uma terceira noção de "quando começou".

Grava `faixa_exigida_id`, `alcada_degraus`, `alcada_motivos` e `alcada_carimbada_em`.

`pendencias_de_aprovacao` passa a ler o carimbo. **Fallback:** sem carimbo
(`alcada_carimbada_em IS NULL`), recalcula como hoje — é o que mantém a SC anterior a
esta fase funcionando sem backfill.

**O que o carimbo protege**, concretamente: entre a 1ª e a 2ª aprovação, um custo lançado
na etapa poderia fazer `estoura_orcamento` deixar de disparar, e a SC fecharia com uma
aprovação a menos do que foi pedido a quem aprovou primeiro. Com carimbo, a régua é a
mesma para os dois.

---

## 4. O rito de emergência

`ativar_emergencia(requisicao, usuario, motivo)`:

- exige `TipoUsuario.ADMIN`/`SUPER_ADMIN` do tenant — 📖 mesma checagem de
  `pode_aprovar` (`alcada_compras.py:213-219`);
- exige motivo escrito (não há emergência sem explicação);
- recusa se a obra tiver **dívida vencida** — ver abaixo;
- grava `emergencia_ativada_em`, `emergencia_prazo = +48h`, `emergencia_por_id`;
- registra uma `RequisicaoTransicao` com marca própria, para a trilha contar a história
  inteira sem uma segunda tabela.

Com a emergência ativa, `esta_totalmente_aprovada` passa a aceitar **uma** aprovação de
admin, independentemente de `aprovacoes_necessarias` e de `exige_mapa_concorrencia` da
faixa. As exigências não somem: viram pendências marcadas como dívida, com o prazo.

`regularizar_emergencia` não é ação de tela — é consequência: assim que as pendências
originais somem (a 2ª aprovação chega, o mapa é vinculado), `emergencia_regularizada_em`
é gravado.

**Dívida vencida** = `emergencia_ativada_em IS NOT NULL AND emergencia_regularizada_em IS
NULL AND emergencia_prazo < agora`. Com uma dessas na obra, `pode_ativar_emergencia`
recusa a próxima, nomeando a SC devedora. Nada mais é travado: a SC em curso anda, e a
compra normal da obra segue livre.

---

## 5. O que aparece na tela

Nenhuma tela nova. Três mudanças nas que existem:

1. **Formulário da SC** — seletor de urgência (normal/urgente) e o campo de justificativa,
   que só aparece e só é exigido quando urgente.
2. **Detalhe da requisição** — um bloco "por que esta SC exige o que exige", montado do
   `alcada_motivos`: a faixa base e o valor efetivo, as SCs somadas com número e valor, o
   quanto do orçado da etapa já está comprometido, qual proposta era a mais barata. A
   pendência já é texto hoje (`:161-186`); o bloco é o **porquê** dela.
3. **Botão de emergência** — visível só para admin, com confirmação e campo de motivo. Ao
   lado, quando houver, o aviso de dívida vencida na obra, com o número da SC devedora.

---

## 6. Testes

Arquivo `tests/test_alcada_regras.py`, no molde de `tests/test_recebimento_atesto.py`.

**Cada condição isolada** — quatro testes, cada um provando que a faixa sobe exatamente
um degrau e que o motivo gravado nomeia o número que a disparou.

**Combinação** — duas condições sobem dois degraus; três ou mais respeitam o teto da
faixa mais alta ativa.

**Anti-fracionamento** — SC no dia 30 soma, SC no dia 31 não (a borda exata); SC
CANCELADA e REJEITADA não somam; RASCUNHO não soma; SC sem etapa cai no balde da obra e
não se mistura com as que têm etapa; SC de outra obra e de outro tenant nunca entram.

**Carimbo** — custo lançado na etapa depois do envio não muda a exigência; rejeitar e
reenviar recarimba com a régua nova; SC sem carimbo (legada) continua sendo avaliada na
leitura.

**Emergência** — um admin aprova sozinho e a SC fecha; não-admin não aciona; sem motivo
não aciona; a 2ª aprovação regulariza e grava a data; dívida vencida trava a próxima
emergência da obra **e não trava** SC normal nem a SC em curso.

**Falha fechada** — tenant sem faixa ativa continua na `_FaixaSeguranca` com todas as
condições disparando; nenhuma condição consegue reduzir exigência.

**Regressão da Fase 3** — os 4 invariantes que já existem (solicitante não aprova, voto
não conta duas vezes, rodada nova não herda voto, tenant alheio não aprova) rodam de novo
com as regras novas ligadas.

---

## Duas escolhas contra o óbvio

**Sem flag nova.** O padrão da casa é uma flag por fase — e aqui ela seria peso morto:
🔬 `compras_governanca_ativa` (migração 246) está **desligada em todo o parque**, e o
`--ligar` recusa tenant sem `escopo_obra_ativo`
(📖 `scripts/flag_compras_governanca.py:99-100`), que também não foi ligado em lugar
nenhum. Uma segunda flag criaria uma combinação que ninguém vive e mais um estado para
testar. A reversibilidade que importa já vem do carimbo: SC carimbada não muda de regra,
e o fallback cobre a SC sem carimbo.

**Sem sensor de drift.** O sensor do recebimento
(`scripts/verificar_consistencia_recebimento.py`) vigia um número que continua sendo
escrito por fora — o estoque. Aqui é o oposto: o carimbo registra uma decisão que, **por
desenho**, não deve acompanhar a realidade depois de tomada. Divergência entre carimbo e
recálculo é a regra funcionando. Um sensor que gritasse a cada custo lançado seria um
sensor que ninguém lê — e este repositório já registrou essa armadilha uma vez, no
próprio spec do recebimento ("um sensor que grita sempre não é lido nunca").

---

## Riscos

| Risco | Mitigação |
|---|---|
| A condição de orçamento derruba a tela quando `projecao_de_custo_por_servico` falha | A função já engole exceção e devolve `{}` (📖 `custo_orcado.py:137-139`). Orçado ausente = condição **não** dispara, e o motivo registra "orçamento indisponível" em vez de mentir |
| Anti-fracionamento vira ruído em obra grande | A chave é obra+**etapa**, não obra. Se ainda assim gritar demais, a janela é constante num só lugar — mexer é uma linha, e a decisão volta para o negócio |
| Emergência vira rotina | É exatamente o que a dívida vencida trava. O relatório de exceções (fase 5 do ciclo) vai contar quantas houve por obra |
| Número da migração colidir | Conferir `migration_history` antes de fixar 287. É a terceira vez que esta lição aparece por escrito |
| Carimbo envelhecer errado numa SC parada há meses | Reenvio recarimba; SC parada em AGUARDANDO por muito tempo é problema de fluxo, não de alçada — e o carimbo diz *quando* foi tirado |

---

## Fora de escopo

Condição de pagamento estruturada no mapa; frete e validade da proposta; o financeiro em
dois fluxos (tríade PC+NF+atesto, adiantamento, segregação lançar/liberar, liberação em
lote); o status unificado de 9 etapas; os 5 relatórios. Cada um entra numa fase seguinte,
com spec próprio.

---

## Runbook

Não há flag para ligar. O que muda de comportamento só é visível em tenant com
`compras_governanca_ativa` ligada — hoje, nenhum. Para exercitar em dev:

1. `python scripts/flag_escopo_obra.py <ID> --ligar` (pré-requisito duro: o `--ligar` da
   governança recusa sem ele).
2. `python scripts/flag_compras_governanca.py <ID> --ligar`.
3. Criar duas SCs de R$ 4 mil na mesma obra e etapa, aprovar a primeira, e conferir que a
   segunda passa a exigir a faixa de R$ 5 mil+ — com o bloco de motivos nomeando a
   primeira.
4. Marcar uma SC como urgente sem justificativa: tem de recusar.
5. Acionar emergência como admin, aprovar sozinho, conferir a dívida na tela; forçar o
   prazo para o passado no banco e conferir que a próxima emergência da obra é recusada,
   **e** que uma SC normal da mesma obra continua andando.
