# RDO em porcentagem livre — runbook de rollout

> Flag `configuracao_empresa.rdo_percentual_livre` (migração 226, default
> `FALSE`). Entrega de 24/07, commit `bdee680a`.
>
> Com a flag desligada o comportamento é **byte-idêntico** ao de sempre. Todo
> o risco está em ligar — e, ao contrário das outras flags, este risco é de
> **perda visível de avanço físico**, não de acesso.

## O que a flag muda

Todo apontamento de produção do RDO passa a ser em **percentual acumulado**,
para toda tarefa de toda obra do tenant. O quantitativo cadastrado
(`quantidade_total` / `unidade_medida`) vira **referência de leitura** na
tela — deixa de governar o cálculo.

Concretamente, `percentual_concluido` deixa de sair de
`quantidade_acumulada / quantidade_total` e passa a sair do
`percentual_realizado` do apontamento mais recente.

Nada é reescrito: `tarefa_cronograma.modo_apontamento` fica como está. **Por
isso desligar a flag reverte o sistema por completo.**

## ⚠️ O risco real: tarefas que perdem físico

A entrega afirmou que a continuidade estava garantida — *"a linha
quantitativa antiga já grava `percentual_realizado`, então a tarefa em 62%
continua em 62%"*. Isso vale para o que a **dupla escrita do M07 escreve
hoje**, e **não** para toda linha legada.

🔬 27/07, banco de **dev** (⚠️ dominado por carga de suíte — prova a forma do
problema, não o volume de produção): **148 apontamentos** com
`quantidade_acumulada > 0` e `percentual_realizado = 0`, em **133 tarefas de
84 tenants**.

Numa tarefa dessas, hoje a tela mostra (digamos) 50% — vindo de 24/48 un. Com
a flag ligada ela mostraria **0%**, porque o percentual da linha está zerado.
Ninguém apontou nada; a obra simplesmente encolheu na tela.

O `--ligar` **recusa** quando isso existiria, e lista as tarefas.

## Por tenant, nesta ordem

1. **Consulte o estado.**

       python scripts/flag_rdo_percentual_livre.py <ID> --status

2. **Rode o `--ligar` e leia a recusa.** Ele não grava se houver regressão:

       python scripts/flag_rdo_percentual_livre.py <ID> --ligar

   Saída possível:

       ABORTADO: 7 tarefa(s) do tenant 42 PERDERIAM avanço físico ao ligar a flag.
         obra 118 · tarefa 9312 Execução de Ferragens Para Fundação   50.00% →   0.00%
         …

3. **Corrija as tarefas listadas.** O caminho normal é **reapontar o % na
   tela do RDO** — um apontamento novo pelo serviço grava os dois campos e a
   tarefa sai da lista. Não há script de backfill de propósito: reapontar é
   decisão de quem conhece a obra, e um backfill automático inventaria
   percentual.

4. **Ligue.**

       python scripts/flag_rdo_percentual_livre.py <ID> --ligar

   O aviso que sai depois informa quantas tarefas estavam em modo
   `quantidade` e passam a pedir % — é informativo, nada é reescrito.

5. **Confira duas telas** antes de anunciar ao tenant:
   - **Novo RDO** — o card da tarefa pede % acumulado e mostra
     "Total: X un" como referência (some quando a tarefa não tem total ou
     unidade — nunca mostra "0").
   - **Editar RDO** — a mesma coisa. Esta tela era **só-quantidade** até
     24/07 e ganhou o modo percentual na mesma entrega; é a que tem menos
     rodagem.
   - No modal do cronograma, o seletor "Como apontar no RDO" **some** com a
     flag ligada.

   > ✅ **Feita em 27/07**, em dev, no tenant `visual_rdo` com a obra da
   > Baia importada (101 tarefas, 26 RDOs) e a flag ligada pelo CLI (o guard
   > deixou passar — a Baia não tem linha legada sem percentual). Evidências
   > em `docs/img/rdo-pct-*.png`:
   >
   > | Tela | O que a captura mostra |
   > |---|---|
   > | `rdo-pct-novo-card-total-48un.png` | Novo RDO: todos os cards pedem % acumulado; "Total: 48 un" só na tarefa com quantitativo; nenhuma mostra "Total: 0"; "Ant: X%" com o acumulado anterior |
   > | `rdo-pct-editar-continuidade.png` | Editar RDO (a tela que era só-quantidade): campo de % em todos os cards; nivelamento com Ant: 60% → realizado 80%, o histórico real de 21-22/07 |
   > | `rdo-pct-cronograma-sem-seletor.png` | Modal de tarefa-folha no cronograma: seletor "Como apontar no RDO" presente no DOM e **invisível** (2 no DOM, 0 visíveis); Quantidade/Unidade seguem editáveis como referência |

6. **Rode uma semana** com um tenant só. O que observar: alguém reclamou que
   o avanço de uma frente mudou sozinho?

## Rollback

    python scripts/flag_rdo_percentual_livre.py <ID> --desligar

Imediato e completo: nenhuma coluna foi reescrita, então o
`percentual_concluido` volta a ser derivado da quantidade na próxima
sincronização. Apontamentos feitos em % durante a janela **permanecem
gravados** (o `percentual_realizado` da linha), mas deixam de governar o
cálculo nas tarefas com quantitativo.

## O que esta entrega deliberadamente NÃO fez

- **Não reescreve `modo_apontamento`.** O resolvedor sobrepõe a coluna
  enquanto a flag está ligada; a coluna fica intacta para o rollback
  funcionar. (A migração 221 congelou `'quantidade'` na maioria das tarefas —
  sem a sobreposição, ligar a flag não mudaria nada.)
- **Não mexe no peso do progresso geral.** O anel da obra continua ponderando
  por duração; a flag só muda de onde sai o % de cada tarefa.
- **Não tem backfill de `percentual_realizado`.** Ver o passo 3.
- **Não toca no carve-out de terceiros** nem no rollup dos pais.
