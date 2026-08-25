# RDO em porcentagem livre — design

> **Estado em 2026-08-25 (varredura de fecho):** ✅ **REALIZADA** — o plano correspondente foi executado e o código está na árvore.
>
> Veredito dado por **existência de código na árvore**, não por checkbox nem por
> mensagem de commit. Índice completo em `docs/planos-em-aberto-2026-08-25.md`.


Data: 2026-07-24. Aprovado em conversa com o usuário (abordagem A).

## Resumo

Todo apontamento de produção no RDO passa a ser feito em **percentual
acumulado livre**, para toda tarefa de toda obra — em vez de derivado do
quantitativo acumulado (`quantidade_acumulada / quantidade_total`). O
quantitativo cadastrado na tarefa vira informação de referência, não o
meio de apontar. Tudo atrás de uma flag de tenant nova
(`rdo_percentual_livre`); flag desligada = comportamento atual,
byte-idêntico.

Fora de escopo: medições (`ItemMedicaoCronogramaTarefa`), importador
físico-financeiro (grava apontamentos direto no formato antigo, com % já
calculado), portal do cliente, app mobile e qualquer mudança de schema em
`rdo_apontamento_cronograma`.

## Contexto atual (verificado no código)

- Cada tarefa tem `modo_apontamento` (migração 220): `'quantidade'`,
  `'percentual'` ou NULL. `modo_da_tarefa`
  (`services/cronograma_apontamento_service.py`) resolve: marco →
  percentual binário; escolha explícita; senão dedução legada —
  `quantidade_total > 0` e `unidade_medida` preenchida → `'quantidade'`.
- Obra tem `regime_medicao` (migração 201); `'percentual'` só muda o
  default de tarefas NOVAS criadas pela rota do cronograma.
- **Dupla escrita**: todo apontamento grava SEMPRE `percentual_realizado`
  (nas linhas quantitativas, o % derivado do total da época; nas
  percentuais, o digitado clampado em 100). É o que torna a mudança de
  derivação segura para o histórico.
- **Inconsistência atual** (bug que este design corrige de brinde): as
  funções de derivação em `utils/cronograma_engine.py` decidem por
  `tarefa.quantidade_total > 0`, ignorando o modo. Tarefa com
  quantitativo cadastrado mas apontada em % grava quantidades 0.0 e o
  sync recalcula `0/total = 0%`.

## 1. Flag e rollout

- Coluna `rdo_percentual_livre BOOLEAN NOT NULL DEFAULT FALSE` em
  `configuracao_empresa` (migração nova, idempotente, padrão da 222).
- Script `scripts/flag_rdo_percentual_livre.py` (`--status/--ligar/
  --desligar`), no molde de `flag_cronograma_editor_v2.py`.
- Helper único de leitura da flag (mesmo padrão `_editor_v2_on()`),
  usado por serviço, engine e views — nada de consultar a coluna
  espalhado.

## 2. Resolvedor de modo

Com a flag ligada, `modo_da_tarefa` devolve:

1. marco → `'percentual'` (binário 0/100, validação `MarcoApenasZeroOuCem`
   intacta);
2. qualquer outra tarefa → `'percentual'`.

A escolha explícita `modo_apontamento='quantidade'` e a dedução legada
passam a ser ignoradas — mas a coluna **não é reescrita**: desligar a
flag restaura o comportamento atual. O seletor de modo na edição de
tarefa some da UI com a flag ligada; a API continua aceitando
`modo_apontamento` (validação atual), apenas sem efeito prático
enquanto a flag estiver ligada.

## 3. Derivação de percentual

Com a flag ligada, as três funções de `utils/cronograma_engine.py` que
hoje ramificam por `quantidade_total > 0` passam a usar o
`percentual_realizado` do apontamento mais recente (por
`data_relatorio`) para TODA tarefa:

- `calcular_progresso_rdo`
- `sincronizar_percentuais_obra`
- `atualizar_percentual_tarefa`

Flag desligada: ramo quantitativo intacto (caracterização atual). O
rollup de pais (média ponderada por duração) e o
`calcular_progresso_geral_obra_v2` não mudam de fórmula.

Continuidade: como as linhas quantitativas históricas já têm
`percentual_realizado` gravado, uma tarefa que estava em 62% continua em
62% ao ligar a flag, e o próximo apontamento parte de 62%.

## 4. UI do RDO (apontamento)

- Campo único de **% acumulado** para todas as tarefas (o que o modo
  percentual já oferece hoje).
- Quantitativo como **referência de leitura** apenas quando
  `quantidade_total > 0` e `unidade_medida` não vazia (ex.: "150 m³").
  Vazio ou zero → não exibe nada (pedido explícito do usuário: sem "0").
- O campo `saldo` (exclusivo do modo quantidade) deixa de ser calculado
  e exibido com a flag ligada (`tarefas-rdo` devolve `saldo: null`, que
  é o valor atual para tarefas percentuais — sem mudança de contrato).
- Validações mantidas exatamente como hoje: retrocesso exige
  `permitir_retrocesso` + justificativa (auditada em log); >100 exige
  `permitir_sobreexecucao` (agregado clampa em 100); marco só 0 ou 100.

## 5. O que não muda

- Dupla escrita permanente do modo percentual: `quantidade_executada_dia`
  e `quantidade_acumulada` gravam 0.0; `percentual_acumulado` raw;
  `percentual_realizado` clampado.
- Medições, importador físico-financeiro, portal do cliente, mobile.
- Schema de `rdo_apontamento_cronograma` e de `tarefa_cronograma`.

## 6. Testes

- Resolvedor: flag on/off × (marco, escolha explícita 'quantidade',
  dedução por quantitativo, NULL sem quantitativo).
- Derivação: tarefa com histórico quantitativo mantém o % ao ligar a
  flag (continuidade); apontamento % seguinte atualiza; tarefa com
  quantitativo + modo % deixa de mostrar 0% (regressão do bug atual).
- `tarefas-rdo`: referência de quantitativo presente quando cadastrado,
  ausente quando vazio; `saldo` null com flag ligada.
- Validações: retrocesso/sobreexecução/marco idênticos com flag ligada.
- Flag off byte-idêntico: resposta de `tarefas-rdo` e tela de
  apontamento iguais às de hoje.

## Decisões registradas

| Decisão | Escolha |
|---|---|
| Alcance | Tudo em % (toda tarefa, toda obra, com a flag do tenant ligada) |
| Quantitativo na tela do RDO | Só referência de leitura; oculto quando vazio (sem "0") |
| Validações do % | Mantidas (retrocesso c/ justificativa, sobreexecução, marco 0/100) |
| Estratégia | A — resolvedor + derivação, atrás de flag; sem reescrever dados |
| Backfill de `modo_apontamento` | Não (reversibilidade; coluna fica como está) |
