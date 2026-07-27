# Editor de cronograma v2 — runbook de rollout

> Flag `configuracao_empresa.cronograma_editor_v2` (migração 222, default
> `FALSE`). Cinco fases entregues em 24/07: `73f58d3e` → `8fda59f5`.
>
> Com a flag desligada, o cronograma se comporta como sempre. Todo o risco
> está em ligar — e aqui o risco é de **datas mudarem sozinhas**.

## O que a flag liga

| Fase | Entrega |
|---|---|
| 1 | Motor de agendamento estilo MS Project: `tarefa_vinculo` (N predecessoras com tipo TI/II/TT/IT + lag), recálculo em cascata em dias úteis, folga total, caminho crítico, detecção de ciclo com rollback |
| 2 | Grade tipo planilha |
| 3 | Desfazer/refazer |
| 4 | Linha de base (`CronogramaBaseline`) — congela o planejado para comparar com o real |
| 5 | Manual de uso em PDF |

A flag governa as rotas de tarefa, o CRUD de vínculos e o frontend
(`EDITOR_V2`). Com ela desligada há **dual-write** de vínculo TI/0, então o
dado novo já vem sendo alimentado sem que o motor novo esteja no comando.

## ⚠️ Pré-requisitos, por tenant

1. **O tenant precisa ser `versao_sistema = 'v2'`.** Com a flag ligada num
   tenant v1, o motor novo fica inativo — o script avisa, mas o rollout não
   acontece de fato.

2. **O calendário do tenant não pode considerar sábado ou domingo.** O motor
   novo é **seg–sex fixo nesta fase**. Se o `CalendarioEmpresa` do tenant
   considerar fim de semana, ligar a flag faz o recálculo **ignorar essa
   configuração e mover as datas do cronograma**.

   O `--ligar` recusa nesse caso:

       python scripts/flag_cronograma_editor_v2.py <ID> --ligar
       # ABORTADO: o CalendarioEmpresa do tenant 42 considera sábado e/ou domingo…

   Decida antes: ou o tenant abre mão do fim de semana no cronograma (ajuste
   o calendário), ou espere a fase que suportar calendário configurável. O
   `--forcar` existe, mas leia o parágrafo do rollback antes de usá-lo.

## A ordem

1. **Consulte.**

       python scripts/flag_cronograma_editor_v2.py <ID> --status

2. **Escolha um tenant piloto com cronograma pequeno e vivo.** Não comece
   pelo maior: o recálculo em cascata toca todas as sucessoras.

3. **Guarde o estado do cronograma antes.** É o que permite comparar depois:

       python scripts/verificar_equivalencia_obra.py <obra_id> --salvar antes.json

4. **Ligue.**

       python scripts/flag_cronograma_editor_v2.py <ID> --ligar

5. **Compare.** Mova uma tarefa na grade e confira que as sucessoras andaram
   como o MS Project andaria — e que nenhuma tarefa **já iniciada** foi
   movida (o motor ancora as iniciadas de propósito).

       python scripts/verificar_equivalencia_obra.py <obra_id> --comparar antes.json

6. **Crie uma linha de base** antes de o tenant começar a editar de verdade —
   sem ela, a comparação planejado × real da Fase 4 não tem referência.

7. **Entregue o manual em PDF** (Fase 5) a quem vai usar a grade.

## Rollback

    python scripts/flag_cronograma_editor_v2.py <ID> --desligar

Devolve o motor antigo **imediatamente**. Mas atenção ao limite:

> ⚠️ **Desligar a flag reverte o MOTOR, não o DADO.** Se o motor novo já
> recalculou e gravou datas, elas continuam gravadas. Por isso o passo 3
> (snapshot antes) não é burocracia — é o único jeito de voltar as datas.
> `CronogramaVersao` também permite restaurar, se a obra for versionada.

Vínculos criados na tabela `tarefa_vinculo` permanecem; com a flag desligada
o sistema volta a usar `predecessora_id` (TI/0), que o dual-write manteve
alimentado.

## O que estas cinco fases deliberadamente NÃO fizeram

- **Calendário configurável.** Seg–sex fixo. É a razão do guard.
- **Substituir `CronogramaVersao`.** A linha de base (Fase 4) é uma estrutura
  separada; o versionamento por .mpp segue como estava.
- **Mexer no cálculo de progresso físico.** O editor mexe em datas e
  dependências, não em % executado.
