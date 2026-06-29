# Realizado por lançamentos (Pedaço 1)

> Data: 2026-06-29. Obra-piloto: Baia.
> Parte 1 de uma iniciativa maior ("custo realizado por lançamentos amarrados à etapa").
> Contexto de partida: `2026-06-29-custos-unificados-modulo-periodos-design.md`
> (custos unificados por grupo + modal Previsão/Realizado, já implementado em 8 commits).

## A iniciativa (visão completa) e a decomposição

O usuário quer que o **custo realizado** de cada etapa venha de **lançamentos reais** (Contas a
Pagar), e não de um número digitado à mão. A visão completa:

1. **Todo módulo de custo ganha um campo "Etapa"** (compras, alimentação, transporte, mão de
   obra/diárias do RDO, folha…) — o gasto nasce ligado à obra **e** à etapa.
2. Na aba Realizado, um botão **"Novo lançamento"** abre um menu de **tipos** (Compra,
   Transporte, Mão de obra, Alimentação…); cada tipo abre o formulário daquele módulo, já
   amarrado a obra/etapa/período, e **cria um Contas a Pagar**.
3. O Realizado **se soma sozinho** a partir desses lançamentos.

Isso atravessa vários módulos independentes, então é quebrado em pedaços, cada um
entregável e testável sozinho:

- **Pedaço 1 (ESTE doc):** Realizado deixa de usar o número manual e passa a **somar os
  lançamentos (`GestaoCustoFilho`) ligados à etapa**, agrupados por período. Mais um
  **"+ Novo lançamento" manual** que cria um Contas a Pagar amarrado à etapa.
- **Pedaço 2 (futuro):** o menu de **tipos** ("Novo lançamento" → Compra/Transporte/…) e o
  contrato de abrir o formulário do módulo já amarrado a obra/etapa/período. Implementa **um**
  tipo de ponta a ponta (Compra) para validar o padrão.
- **Pedaços 3…N (futuro):** cada módulo restante ganha o campo "Etapa" e se pluga no menu.

## Problema (Pedaço 1)

Hoje a aba Realizado tem **um valor solto por período** (`ObraServicoCustoItem.valor_realizado`,
adicionado na migração 202). Isso é um número digitado, desconectado dos custos reais da obra
(compras, folha, RDO), e não há rastro de **o que** compõe aquele realizado.

## Objetivo (Pedaço 1)

1. O realizado de cada etapa passa a ser a **soma dos lançamentos de custo** (`GestaoCustoFilho`)
   ligados àquela etapa (`obra_servico_custo_id`), distribuídos por período pelo **mês da
   `data_referencia`**.
2. A aba/área **Realizado** vira uma **tela de visualização** desses lançamentos por período,
   no **nível da etapa** (não por grupo de previsão).
3. Um botão **"+ Novo lançamento"** (versão manual genérica) **cria um Contas a Pagar** real
   amarrado a obra+etapa, que aparece somado no realizado na hora.

## Decisões (acordadas no brainstorming)

- **Lançamento = `GestaoCustoFilho` real** (reaproveita a entidade existente; sem tabela nova).
  Manual e "puxado do sistema" são o mesmo tipo de registro — um Contas a Pagar de verdade que
  **aparece em Gestão de Custos, Fluxo de Caixa, Curva S e relatórios**, sem dupla contagem.
- **Realizado é por ETAPA × período (mês), não por grupo de previsão.** Um lançamento se liga à
  etapa (`ObraServicoCusto`), não ao grupo `(descrição, fonte)`. Portanto:
  - O **modal do `▸`** (por grupo: Escritório, Carro…) passa a ter **só a aba Previsão**.
  - O **Realizado** sobe para o **painel da etapa**, como uma área "Realizado — lançamentos".
- **Realizado é independente da Previsão.** Um custo **não previsto** é registrado direto
  ("+ Novo lançamento"); a previsão dele fica 0 e o realizado conta no total da etapa. Não é
  preciso criar previsão antes para lançar realizado.
- **Realizado manual nesta versão** é o "+ Novo lançamento" genérico (categoria única). O **menu
  de tipos** e o campo "Etapa" nos módulos de origem são os **Pedaços 2…N** (fora de escopo aqui).

## Modelo de dados

Nenhuma tabela nova. Reaproveita `GestaoCustoPai` (cabeçalho do Contas a Pagar) +
`GestaoCustoFilho` (lançamento), que já têm:

- `GestaoCustoFilho`: `data_referencia`, `descricao`, `valor`, `obra_id`,
  **`obra_servico_custo_id`** (a etapa), `origem_tabela`, `origem_id`, `admin_id`.
- `GestaoCustoPai`: `tipo_categoria`, `entidade_nome`, `fornecedor_id`, `status`, `valor_total`…

### Criação do lançamento manual

Via o helper existente `utils/financeiro_integration.registrar_custo_automatico(...)`, que já
acha/cria o `GestaoCustoPai` em aberto, anexa o `GestaoCustoFilho`, recalcula o `valor_total` e
dá flush. Parâmetros do lançamento manual:

- `tipo_categoria='OUTROS'` (categoria única nesta versão; cada tipo terá a sua no Pedaço 2),
- `entidade_nome` = fornecedor digitado **ou** `'Lançamento manual'`; `entidade_id=None`
  (ou `fornecedor_id` se o usuário escolher um fornecedor — opcional),
- `data` = data do lançamento, `descricao`, `valor`,
- `obra_id` = obra, **`obra_servico_custo_id` = osc da etapa**,
- `origem_tabela='lancamento_periodo_manual'`, `origem_id=None`,
- `force_v2=False` (roda em request com `current_user`; `is_v2_active()` resolve).

### Faseamento por período

Realizado de um período (mês) = Σ `GestaoCustoFilho.valor` da etapa cuja `data_referencia` cai
naquele mês. Um lançamento cujo mês não tem período de previsão **ainda conta** no total da etapa
e aparece sob uma **linha de mês derivada** na área Realizado.

### Limpeza do que foi feito antes

- **Reverter** as somas de `valor_realizado` nos indicadores (do design 2026-06-29):
  `realizado_por_etapa` e `curva_realizado` **já** somam `GestaoCustoFilho` — voltam a ser a
  única fonte; remover o helper `realizado_manual_por_osc` e a soma no KPI `custo_realizado`.
- **Migração 203:** `ALTER TABLE obra_servico_custo_item DROP COLUMN IF EXISTS valor_realizado`
  (idempotente). Remover `valor_realizado` do modelo.
- **Endpoint de itens** (`POST .../etapa/<osc_id>/itens`) deixa de ler/gravar `valor_realizado`
  (reverte o parse/persistência do design anterior). Ele continua servindo a **Previsão**.

## UI

### Modal do grupo (`▸`) — só Previsão

O modal `#fin-periodos-modal` perde a aba **Realizado** e todo o conteúdo dela; vira **seção
única de Previsão** (sem as `nav-tabs`): mês | início | fim | previsto, + adicionar/remover
período, total previsto. O reparent ao `<body>` (correção de backdrop) é mantido.

### Painel da etapa — duas abas no nível da etapa

O painel da etapa (`#fin-etapa-det`) passa a ter **duas abas de etapa**:

- **"Previsão (por grupo)"** — a tabela de grupos `(descrição, fonte)` já existente, com o `▸`
  que abre o modal de períodos (agora só Previsão). Inalterada salvo a remoção do realizado.
- **"Realizado — lançamentos"** (nova) — lista de lançamentos por mês + "+ Novo lançamento".

A aba Realizado é carregada sob demanda (lazy) ao ser aberta, via o `GET .../lancamentos`:

```
Indiretos / gestão (período)            Realizado: R$ 5.100 / Previsto: R$ 457.000
[ Previsão (por grupo) ]                [ Realizado — lançamentos ]
Escritório  Veks  5  R$ 220.000  ▸      jun/26
Carro       Veks  5  R$  12.500  ▸        05/06  Aluguel sala     Manual   R$   900  ✎ ×
…                                          12/06  Compra cimento   Compra   R$ 4.200
                                          Subtotal jun/26: R$ 5.100
                                        + Novo lançamento
                                        Total realizado: R$ 5.100
```

- Lançamentos **manuais** (`origem_tabela='lancamento_periodo_manual'`): editáveis/excluíveis
  aqui (✎ / ×). Demais (compra, RDO, folha…): **só leitura** (badge da origem; edita no módulo).
- **"+ Novo lançamento"** abre um mini-formulário: **data, descrição, valor** (+ fornecedor
  opcional). Salvar → cria o Contas a Pagar e recarrega a aba + o painel.

## Endpoints (novos / alterados)

- `GET  /obras/<id>/financeiro/etapa/<osc_id>/lancamentos` → lista
  `[{id, data, descricao, valor, origem, origem_label, editavel}]` (ordenada por data),
  para a área Realizado montar os meses e somar. `osc_id` valida obra+tenant (404 senão).
- `POST /obras/<id>/financeiro/etapa/<osc_id>/lancamentos` → cria lançamento manual via
  `registrar_custo_automatico(...)`. Body `{data, descricao, valor, fornecedor?}`; valida valor
  ≥ 0 e data; responde o lançamento criado + `painel_financeiro` recalculado.
- `PATCH /obras/<id>/financeiro/etapa/<osc_id>/lancamentos/<filho_id>` → edita um lançamento
  **manual** (`data/descricao/valor`); recalcula o `valor_total` do pai. 403/404 se não for
  manual ou não pertencer à obra/tenant.
- `DELETE /obras/<id>/financeiro/etapa/<osc_id>/lancamentos/<filho_id>` → remove um lançamento
  **manual**; recalcula o pai; remove o pai se ficar sem filhos. 403/404 nas mesmas guardas.
- `POST /obras/<id>/financeiro/etapa/<osc_id>/itens` (existente) → **remover** o tratamento de
  `valor_realizado` do payload e da persistência.

## Indicadores (sem dupla contagem)

`realizado_por_etapa(obra)` e `curva_realizado(obra)` já agregam `GestaoCustoFilho`
(excluindo `FATURAMENTO_DIRETO`). Removidas as somas de `valor_realizado`, o realizado da etapa,
a Curva S e o KPI "custo realizado"/verba passam a refletir **exatamente** os lançamentos — cada
um contado uma vez (pela sua `obra_servico_custo_id`). O painel da etapa mostra
`realizado = realizado_por_etapa[osc_id]` (já é assim, agora sem o termo manual).

## Fora de escopo (Pedaço 1)

- Menu de **tipos** no "Novo lançamento" (Compra/Transporte/Mão de obra/Alimentação…) — Pedaço 2.
- Campo "Etapa" nos formulários dos módulos de origem (compras, alimentação, transporte, RDO,
  folha) — Pedaços 2…N.
- Editar/excluir aqui lançamentos vindos de outros módulos (só leitura nesta área).
- Vincular em massa lançamentos antigos já criados sem etapa (backlog) — futuro.
- Mudança em Previsão (continua igual), cronograma físico, RDO ou portal.

## Invariantes da Baia

- **Previsto inalterado:** veks 800.960 / fat 550.775 / lucro 24.976 / imposto 128.903 /
  contrato 1.505.613,76 / data_fim 08/10.
- **Realizado começa em 0** para as etapas da Baia (nenhum `GestaoCustoFilho` ligado a elas
  ainda) — coerente com o novo modelo: realizado só existe quando há lançamento.

## Testes

- **Realizado por etapa = soma de lançamentos:** criar `GestaoCustoFilho` com
  `obra_servico_custo_id` da etapa e datas em meses distintos; `painel_financeiro` mostra o
  realizado da etapa e a Curva S somando-os por mês; sem o termo `valor_realizado`.
- **Lançamento manual (endpoint):** `POST .../lancamentos` cria `GestaoCustoPai`+`Filho` ligado à
  etapa (`origem_tabela='lancamento_periodo_manual'`), aparece somado no realizado e como Contas
  a Pagar; valor inválido/negativo → 400.
- **Editar/excluir manual:** `PATCH` altera valor e recalcula o pai; `DELETE` remove e recalcula
  (pai some se vazio); lançamento de outra origem → 403.
- **Custo não previsto:** lançamento num grupo/mês sem previsão entra no total da etapa
  (Realizado > Previsto visível no cabeçalho), sem exigir previsão prévia.
- **Coluna removida:** `valor_realizado` não está mais em `ObraServicoCustoItem.__table__`;
  `realizado_manual_por_osc` removido; endpoint de itens ignora `valor_realizado`.
- **Multitenant:** `lancamentos` de obra de outro admin → 404.
- **Invariantes da Baia** preservados; suíte financeira verde:
  `pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`.
