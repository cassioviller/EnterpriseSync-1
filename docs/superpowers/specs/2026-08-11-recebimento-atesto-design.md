# Recebimento e atesto — o material que chega passa a ser um fato registrado

**Data:** 2026-08-11
**Origem:** pedido do Cássio em sessão — "ciclo completo de compras, da solicitação no
campo até o lançamento no fluxo de caixa, com rastreabilidade por um número único".
**Escopo:** a **primeira** das cinco fases em que o pedido foi decomposto. Cobre
recebimento, atesto, entrega parcial e a entrada de estoque que passa a nascer daí.

---

## Por que este spec é só um pedaço

O pedido original tem sete seções (SC, cotação, alçadas, pedido/recebimento, financeiro
em dois fluxos, status, relatórios). Boa parte já existe no repositório, em graus
diferentes — e o que falta não cabe num diff só. Levantamento feito antes de desenhar:

| Seção pedida | Já existe | Falta |
|---|---|---|
| **1. SC** | `RequisicaoCompra` (models.py:5682) — nº por tenant, obra NOT NULL, solicitante, data de necessidade, itens com quantidade/unidade/catálogo, máquina de estados + trilha `RequisicaoTransicao` | urgência normal/urgente com justificativa obrigatória |
| **2. Cotação** | `MapaConcorrenciaV2` (models.py:7000) — N itens × N fornecedores, prazo, fornecedor escolhido por item, PDF | corte configurável exigindo 3 cotações; frete; validade da proposta; **condição de pagamento estruturada**; justificativa de não-menor-preço |
| **3. Alçadas** | `FaixaAlcada` por tenant editável, N aprovações distintas, exige admin, exige mapa, segregação de funções, votos escopados por rodada (services/alcada_compras.py) | as 4 condições que sobem um degrau; anti-fracionamento; rito de emergência 48h |
| **4. Recebimento** | — | **tudo** — `atesto` e `recebido_por` não aparecem em lugar nenhum do código |
| **5. Financeiro** | `ContaPagar` criado na emissão do pedido (compras_views.py:265) | tríade PC+NF+atesto; adiantamento a fornecedor; segregação lançar/liberar; liberação em lote |
| **6. Status** | 6 estados de requisição | a régua de 9 etapas ponta a ponta |
| **7. Relatórios** | — | os 5 |

**Ordem acordada:** recebimento/atesto → financeiro em dois fluxos → alçadas → status
unificado → relatórios. Recebimento vem primeiro porque é a fundação: sem atesto não
existe a tríade do Fluxo A nem a baixa do adiantamento do Fluxo B. Cada fase seguinte
ganha spec próprio.

---

## Por que existe — e o defeito que já está em produção

O recebimento não é terreno virgem. Existem **dois** pontos que dão entrada de estoque
para o mesmo pedido:

- **na emissão** — `_gerar_entrada_almoxarifado` (compras_views.py:94), chamado em
  compras_views.py:287 e :398, lança a quantidade **inteira** do pedido;
- **na rota `/receber/<pedido_id>`** (compras_views.py:923), com botão em
  `templates/compras/detalhe.html:24`, que lança **o que ainda falta**.

Como a emissão já lançou tudo, o `qtd_pendente` calculado em compras_views.py:975 dá
zero e o laço pula todos os itens (`[SKIP] Item {id}: já totalmente recebido`). O botão
"Receber" é, na prática, **um no-op para todo pedido `tipo_compra='normal'`** — e a tela
não diz isso a quem clica.

Duas consequências que este spec resolve:

1. **O estoque mente.** Material entra no almoxarifado no instante em que alguém
   registra a compra, não quando o caminhão chega. Entre uma coisa e outra pode haver
   semanas, e nesse intervalo o saldo diz que o material está lá.
2. **Não há onde registrar a conferência.** Quem recebe na obra não tem como dizer
   "chegaram 48 dos 50 sacos, dois vieram rasgados". Sem esse registro, a fase seguinte
   não tem como bloquear pagamento de material que não chegou.

Além disso, os dois caminhos só enxergam item com `almoxarifado_item_id`. Item de texto
livre — o "outro" que o próprio pedido do Cássio prevê na SC — não gera movimento nenhum
e hoje não deixa rastro de recebimento em lugar algum.

---

## Decisões tomadas na conversa

| Pergunta | Decisão | Consequência |
|---|---|---|
| O atesto vira o gatilho da entrada de estoque? | **Sim** | O estoque passa a refletir o que fisicamente chegou. Mexe no almoxarifado junto e exige flag por tenant |
| Quem pode atestar? | **Qualquer um vinculado à obra, inclusive quem solicitou e quem emitiu** | Decisão consciente de abrir mão da segregação de pessoas neste ponto. Em obra de equipe pequena quem pede é quem recebe o caminhão, e travar isso deixaria material parado. **O controle compensatório passa a ser a trilha** — quem atestou, quando, com que divergência — não a separação de papéis |
| Como fecha o saldo? | **Encerramento explícito com motivo** | Vários atestos acumulam; enquanto faltar quantidade o pedido fica parcial. Uma ação de encerrar saldo, com motivo, fecha o pedido, e o valor a pagar passa a ser o atestado |
| Nota fiscal entra aqui? | **Não — fica na fase financeira** | Esta fase é testável sozinha. A NF chega junto com o bloqueio do contas a pagar, que é quem precisa dela |
| Pedidos legados? | **A regra nova vale só para pedidos novos** | Ver "regime de virada" abaixo |

---

## Regime de virada

Em vez de comparar `created_at` com uma data de corte, **o pedido carrega o próprio
regime**: a coluna `pedido_compra.exige_atesto` é carimbada na criação, a partir da flag
do tenant.

Isso importa porque a flag é um booleano que alguém pode desligar e religar. Com
comparação de data, cada toggle reinterpretaria retroativamente pedidos já fechados — um
pedido recebido sob o regime antigo passaria a ser cobrado pelo novo. Carimbar a linha é
o mesmo raciocínio do `valor_no_momento` em `RequisicaoTransicao` (models.py:5835), que
existe no repositório exatamente para impedir que editar o presente reescreva o passado.

A flag é `configuracao_empresa.recebimento_atesto_ativo`, irmã de
`compras_governanca_ativa` (models.py:4374), com `scripts/flag_recebimento_atesto.py` no
formato de `scripts/flag_compras_governanca.py`: consulta / `--ligar` / `--desligar`, e
um guard que recusa ligar em tenant sem uso de almoxarifado — ligar ali criaria pedidos
que ninguém consegue receber.

---

## Modelo de dados

```
RecebimentoPedido
  id, admin_id, pedido_id → pedido_compra (ondelete=CASCADE)
  sequencia            int      # 1, 2, 3… dentro do pedido → rótulo "PC-1234/2"
  recebido_por_id      → usuario
  data_recebimento     date     # data do FATO, não do registro
  observacao           text     # divergência de quantidade ou qualidade
  encerra_saldo        bool     default False
  motivo_encerramento  text
  created_at           datetime

  UNIQUE (pedido_id, sequencia)
  INDEX  (pedido_id)

RecebimentoPedidoItem
  id, admin_id, recebimento_id → recebimento_pedido (ondelete=CASCADE)
  pedido_item_id           → pedido_compra_item
  quantidade_recebida      Numeric(12,3)   # > 0
  almoxarifado_movimento_id → almoxarifado_movimento (ondelete=SET NULL)

  UNIQUE (recebimento_id, pedido_item_id)   # uma linha por item por recebimento
  INDEX  (pedido_item_id)
```

Colunas novas em `pedido_compra`:

- `exige_atesto` — bool, NOT NULL, default False (ver regime de virada);
- `situacao_recebimento` — string, NOT NULL, default `nao_recebido`.

### Três decisões de modelagem

**O recebimento não tem número global próprio.** `PC-1234/1`, `PC-1234/2` lê-se sozinho
e amarra ao pedido sem uma terceira sequência para manter em sincronia. A
rastreabilidade pedida já vem da cadeia `RC-2026-0001 → PC-1234 → PC-1234/2`.

**`almoxarifado_movimento_id` guarda o movimento que aquela linha gerou.** É o que
permite auditar "esta entrada de estoque veio deste atesto" e o que torna o estorno
possível sem adivinhação. Item de texto livre fica com `NULL`: tem atesto, não tem
movimento.

**`situacao_recebimento` é persistida, não derivada em tempo de leitura.** Derivar por
soma a cada listagem seria N+1 na tela de pedidos. Persistir cobra uma consistência, e
por isso vai junto o `scripts/verificar_consistencia_recebimento.py`, espelhando o
`scripts/verificar_consistencia_progresso.py` que já é o sensor de drift do cronograma:
compara o persistido com o recalculado e sai com código 1 se divergirem.

Valores: `nao_recebido` · `parcial` · `recebido` · `encerrado_com_saldo`.

---

## Fluxo

Hoje, para um pedido `normal`:

```
emissão ──> _gerar_entrada_almoxarifado (lança TUDO)
/receber ──> lança o pendente ──> pendente = 0 ──> não faz nada
```

Com `exige_atesto=True`:

```
emissão ──> nenhum movimento de estoque
atesto 1 (30 sacos)                          ──> ENTRADA 30 + lote   situação: parcial
atesto 2 (18 sacos, encerra saldo: "forne-   ──> ENTRADA 18          situação: encerrado_com_saldo
          cedor não entrega o resto")
```

### Caminho único de escrita

`services/recebimento_pedido.py`, espelhando o chokepoint que a Fase 3 já usa em
`services/requisicao_compra.py`:

```python
registrar_recebimento(pedido, usuario, linhas, data,
                      observacao=None, encerra_saldo=False,
                      motivo=None, permitir_sobre_entrega=False)
```

Numa única transação: valida, cria o `RecebimentoPedido` e seus itens, gera
`AlmoxarifadoMovimento` + `AlmoxarifadoEstoque` (lote FIFO) para cada item de catálogo,
grava o `almoxarifado_movimento_id` de volta na linha, e atualiza
`situacao_recebimento`.

`permitir_sobre_entrega` não é invenção deste spec: é o mesmo par
bloqueio-com-liberação-explícita do `permitir_sobreexecucao` que o RDO já usa em
`registrar_apontamento` (services/atualizacao_rdos.py:290). Chegar mais do que foi
pedido é comum e legítimo; o que não pode é passar despercebido.

### Quem atesta

`GESTOR`, `APONTADOR`, `COMPRADOR` e `ALMOXARIFE` vinculados à obra, mais
`ADMIN`/`SUPER_ADMIN` do tenant — que já enxergam todas as obras por definição
(`utils/autorizacao.obras_visiveis`). `LEITOR` não atesta: é só leitura em toda a Fase 1,
e atestar é escrita que libera dinheiro.

Não há checagem de "quem pediu" nem de "quem emitiu": foi decisão explícita (ver tabela
acima). Um novo helper `pode_receber_na_obra(obra_id)` entra em `utils/autorizacao.py`
junto dos irmãos `pode_requisitar_na_obra` e `pode_apontar_na_obra`, para que a regra
viva onde as outras vivem.

### Derivação da situação

| Condição | Situação |
|---|---|
| Nenhum recebimento | `nao_recebido` |
| Algum item com soma recebida < quantidade pedida | `parcial` |
| Todos os itens com soma ≥ quantidade pedida | `recebido` |
| `encerra_saldo=True` em algum recebimento e ainda falta quantidade | `encerrado_com_saldo` |

### O que a rota antiga faz

A rota `/receber/<pedido_id>` (compras_views.py:923) **não some**. Para pedido legado
(`exige_atesto=False`) ela continua exatamente como está: o estoque daqueles pedidos já
entrou na emissão, e mudar isso reescreveria estoque histórico. O que muda é que a tela
nova **recusa** esses pedidos com a razão dita em português, em vez de aceitar o clique e
não fazer nada — que é o defeito atual.

### Gancho para a fase financeira

`valor_atestado(pedido)` = Σ (quantidade recebida × preço unitário do item) fica exposto
já nesta fase. É o número que o Fluxo A vai usar para pagar o que chegou em vez do que
foi pedido. Barato expor agora, caro descobrir depois que não dá para calcular.

Os movimentos nascem com `pedido_compra_id` preenchido, então a dedup do handler
`material_entrada` do EventManager continua valendo sem alteração.

---

## Casos de borda

| Situação | Comportamento |
|---|---|
| Item de texto livre | Tem atesto, não gera movimento; `almoxarifado_movimento_id` NULL |
| Recebeu mais que o pedido | Recusa, salvo `permitir_sobre_entrega` com justificativa |
| Saldo já encerrado | Recusa novo recebimento, dizendo quem encerrou e quando |
| `encerra_saldo` sem motivo | Recusa — o motivo é o que torna o encerramento auditável |
| Quantidade ≤ 0 | Recusa. Devolução não é recebimento negativo, e não entra nesta fase |
| Dois recebimentos simultâneos | `SELECT … FOR UPDATE` no pedido dentro da transação; sem isso duas telas abertas furam o limite de quantidade |
| Errou a quantidade | Pode excluir **o último** recebimento do pedido, estornando os movimentos que gerou — e recusando se algum lote já teve saída, porque aí o material já foi consumido |
| Pedido cancelado/excluído | Recusa recebimento |
| `LEITOR` da obra tenta atestar | Recusa — `LEITOR` é só leitura em toda a Fase 1 e atestar é escrita que libera dinheiro |
| Tenant sem a flag | Nada muda: emissão lança estoque como hoje, rota antiga como hoje |

---

## Testes

**O comportamento novo:** derivação das quatro situações; soma parcial acumulando entre
recebimentos; sobre-entrega bloqueada e liberada com a flag; encerramento exigindo
motivo; recusa após encerrado; exclusão do último recebimento estornando o movimento, e
recusando quando o lote já teve saída.

**O que não pode mudar:** com a flag desligada, o fluxo de hoje intocado, movimento a
movimento; pedido legado continua recebendo pela rota antiga; e uma **regressão
explícita** de que pedido com `exige_atesto=True` não lança estoque na emissão — é o
teste que impede a dupla escrita de voltar.

**Consistência:** `scripts/verificar_consistencia_recebimento.py`, exit code 1 em drift,
no formato do sensor do cronograma.

Os testes de integração seguem o padrão de `tests/test_fase3_portal_seguranca.py`
(fixtures locais, `pytestmark = pytest.mark.integration`, tenant por `uuid4`).

---

## Migrations

- **267** — cria `recebimento_pedido` e `recebimento_pedido_item`; acrescenta
  `pedido_compra.exige_atesto` (default False) e `pedido_compra.situacao_recebimento`
  (default `nao_recebido`). Backfill: nenhum. Pedido histórico é legado por definição, e
  `exige_atesto=False` é exatamente o que descreve o que aconteceu com ele.
- **268** — `configuracao_empresa.recebimento_atesto_ativo`, default False.

Registradas na lista de `migrations.py:6505` no formato existente. A última migration do
repositório é a 266.

---

## Fora de escopo

Nota fiscal e o vínculo dela com o pedido; bloqueio do contas a pagar pela tríade;
adiantamento a fornecedor e a lista "pago, aguardando entrega"; segregação entre quem
lança e quem libera; liberação em lote; as regras novas de alçada (condições que sobem
um degrau, anti-fracionamento, emergência 48h, corte de 3 cotações); urgência na SC;
condição de pagamento estruturada no mapa; o status unificado de 9 etapas; os 5
relatórios.

Cada um desses entra nas fases seguintes, com spec próprio.
