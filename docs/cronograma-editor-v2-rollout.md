# Editor de cronograma v2 — runbook de rollout

> Flag `configuracao_empresa.cronograma_editor_v2` (migração 222). Cinco
> fases entregues em 24/07: `73f58d3e` → `8fda59f5`; a Fase 6 (menu de botão
> direito) em 29/07, `fe96d652`.
>
> Com a flag desligada, o cronograma se comporta como sempre. Todo o risco
> está em ligar — e aqui o risco é de **datas mudarem sozinhas**.

## ⚖️ DECISÃO do Cássio — 03/08: liga em todo o parque, de uma vez

> "Todos cronogramas que já estão feitos no deploy virarem no novo formato,
> que pode editar no botão direito."

O rollout piloto-a-piloto descrito abaixo **não é mais o caminho do dia a
dia** — ele foi executado de uma vez pela **migração 277**, que roda no boot
do deploy (`docker-entrypoint-easypanel-auto.sh` → `pre_start.py`). O que a
277 faz, nesta ordem:

1. **congela a linha de base** de toda obra com cronograma interno datado que
   ainda não tinha uma ativa (o passo 4 desta lista, em massa e em lotes de
   200 obras, cada lote commitado — boot que morre no meio não refaz o que já
   ficou pronto);
2. **cria `configuracao_empresa`** para o tenant que tem cronograma e nunca
   teve linha de configuração — sem ela a flag lê FALSE e o tenant ficaria de
   fora do "todos";
3. **liga a flag em todas as linhas da tabela** (a tabela não tem unicidade
   por `admin_id`: ligar só uma deixaria o resultado na sorte do `.first()`);
4. **vira o default da coluna para TRUE** — espelhado em `models.py` — para a
   empresa cadastrada amanhã nascer no formato novo;
5. **denuncia no log** o que ela não resolve: tenants com calendário de fim de
   semana (nominalmente) e a contagem de tenants que não são `versao_sistema='v2'`.

Duas consequências que valem repetir:

- **O guard de calendário virou aviso.** O `--ligar` do script recusa tenant
  com sábado/domingo no `CalendarioEmpresa`; a 277 liga assim mesmo, por
  decisão, com a linha de base do passo 1 como apólice. Confira no log do
  deploy quais tenants saíram nominalmente citados.
- **Ligar a flag não recalcula nada sozinho.** A tela do cronograma só lê. O
  recálculo em cascata acontece na **primeira edição** — é lá que datas de um
  tenant com calendário de fim de semana vão para dias úteis.

Tirar um tenant do formato novo depois do deploy continua sendo uma linha:

    python scripts/flag_cronograma_editor_v2.py <admin_id> --desligar

O resto deste runbook segue válido como **o procedimento por tenant** — para
religar quem foi excluído, para ambiente novo, e porque é onde o risco está
explicado.

## O que a flag liga

| Fase | Entrega |
|---|---|
| 1 | Motor de agendamento estilo MS Project: `tarefa_vinculo` (N predecessoras com tipo TI/II/TT/IT + lag), recálculo em cascata em dias úteis, folga total, caminho crítico, detecção de ciclo com rollback |
| 2 | Grade tipo planilha |
| 3 | Desfazer/refazer |
| 4 | Linha de base (`CronogramaBaseline`) — congela o planejado para comparar com o real |
| 5 | Manual de uso em PDF |
| 6 | Descoberta da estrutura: menu de botão direito na grade, inserção por teclado (`Insert`/`Shift+Insert`/`Alt+Insert`), arrastar-e-soltar **sobre** uma linha para aninhar (`POST .../tarefa/<id>/mover`), criar já como subtarefa (`posicao='dentro'`) e expandir/recolher a árvore inteira |

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

4. **Congele o plano de hoje numa linha de base.** É o registro que sobrevive
   ao recálculo — e, desde 28/07, **condição do `--ligar`**: o script recusa
   enquanto houver obra com cronograma datado e sem linha de base ativa.

       python scripts/flag_cronograma_editor_v2.py <ID> --criar-baseline --status

   > Isto era o passo 6 desta lista, depois de ligar. Estava tarde: o motor
   > novo já teria recalculado as datas, e a linha de base congelaria o
   > resultado do recálculo, não o plano que se queria preservar.

5. **Ligue.**

       python scripts/flag_cronograma_editor_v2.py <ID> --ligar

6. **Compare.** Mova uma tarefa na grade e confira que as sucessoras andaram
   como o MS Project andaria — e que nenhuma tarefa **já iniciada** foi
   movida (o motor ancora as iniciadas de propósito).

       python scripts/verificar_equivalencia_obra.py <obra_id> --comparar antes.json

7. **Entregue o manual em PDF** (Fase 5) a quem vai usar a grade.

## Rollback

    python scripts/flag_cronograma_editor_v2.py <ID> --desligar

Devolve o motor antigo **imediatamente**. Mas atenção ao limite:

> ⚠️ **Desligar a flag reverte o MOTOR, não o DADO.** Se o motor novo já
> recalculou e gravou datas, elas continuam gravadas. Por isso o passo 3
> (snapshot antes) não é burocracia — é o único jeito de voltar as datas.
> `CronogramaVersao` também permite restaurar, se a obra for versionada.

### ⚠️ O que o rollback preserva de DEPENDÊNCIA — e o que ele perde

Este parágrafo estava **errado** na 1ª versão deste runbook (27/07) e foi
corrigido pela varredura P2 do code review no mesmo dia. Ele dizia que o
dual-write mantinha `predecessora_id` alimentado. **Não mantinha**: a
sincronização só existia numa direção (`predecessora_id` → `tarefa_vinculo`,
em `sincronizar_vinculos_de_predecessora_id`), e o CRUD novo gravava só a
tabela nova. 🔬 27/07 (dev): 517 de 722 vínculos (72%) não tinham reflexo no
campo legado.

Desde a correção, o CRUD espelha o vínculo no campo legado — **mas o espelho
é parcial por natureza da coluna**, não por limitação de implementação:

| Vínculo criado com o v2 ligado | Sobrevive ao rollback? |
|---|---|
| Única predecessora, tipo TI, lag 0 | ✅ sim |
| Segunda predecessora da mesma tarefa | ❌ não — a coluna guarda UMA |
| Tipo II, TT ou IT | ❌ não — a coluna é sempre TI |
| Lag diferente de 0 | ❌ não — a coluna não tem lag |

Nos casos ❌ o campo fica **NULL de propósito**: perder a dependência no
rollback é melhor do que reintroduzi-la com o tipo errado.

Consequência prática: **se o tenant usou dependências que só o v2 expressa,
o rollback não é reversão completa.** Os vínculos continuam na tabela
`tarefa_vinculo` (nada é apagado) e voltam a valer quando a flag religar —
mas, enquanto ela estiver desligada, o motor antigo não os enxerga.

## O que estas cinco fases deliberadamente NÃO fizeram

- **Calendário configurável.** Seg–sex fixo. É a razão do guard.
- **Substituir `CronogramaVersao`.** A linha de base (Fase 4) é uma estrutura
  separada; o versionamento por .mpp segue como estava.
- **Mexer no cálculo de progresso físico.** O editor mexe em datas e
  dependências, não em % executado.
