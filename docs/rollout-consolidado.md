# Rollout consolidado — o que já está pronto e continua desligado

> Escrito em **2026-07-27**, a partir de uma revisão de prontidão das Fases 1
> a 5 mais as entregas de 24/07 (editor de cronograma v2, RDO em porcentagem
> livre). Não propõe código novo: só ordena o que ligar, em que ordem, e o
> que precisa ser decidido ou medido antes.
>
> Os runbooks por fase (`docs/fase-{1,2,3,5}-rollout.md`) continuam sendo a
> fonte dos passos. Este documento é o mapa entre eles.

## O diagnóstico em uma frase

**Cinco fases fecharam com gate verde e quase nada disso está em uso**, porque
tudo o que muda comportamento nasceu atrás de flag desligada — corretamente —
e nenhuma flag foi ligada em nenhum tenant. O gargalo não é código: são **duas
medições em produção que ninguém fez** e **três decisões de negócio**.

## As cinco flags e o que cada uma segura

| Flag | Entrega que ela segura | Runbook | Guard do `--ligar` |
|---|---|---|---|
| `escopo_obra_ativo` | Fase 1.5 — RBAC por obra | `fase-1-rollout.md` | ✅ recusa se `usuario_obra` vazia e há usuário não-admin |
| `compras_governanca_ativa` | Fase 3 — requisição→alçada→pedido | `fase-3-rollout.md` | ✅ recusa sem faixa de alçada; checa o escopo |
| `cronograma_mpp_ativo` | M03 — importação de cronograma .mpp | ❌ **não existe** | — |
| `cronograma_editor_v2` | Editor de cronograma v2 (5 fases, 24/07) | ❌ **não existe** | ⚠️ só avisa (calendário sáb/dom) |
| `rdo_percentual_livre` | RDO em porcentagem livre (24/07) | ❌ **não existe** | ⚠️ **nenhum** — o aviso sai depois de gravar |

Duas fases **não têm flag**, de propósito, e por isso já estão valendo:

- **Fase 4** (centro de custo obrigatório) — a constraint foi validada no
  banco; já está ativa. Pendência: revisar as linhas carimbadas `[FASE4:R5]`.
- **Fase 5 parte A** (ciclo de vida e assinatura do RDO) — aditiva: todo RDO
  nasceu `preenchido`, que é mutável. A imutabilidade só existe quando alguém
  clica em "Assinar". **Mas o controle de quem pode assinar depende de
  `escopo_obra_ativo`.**

## A dependência que ordena tudo

```
escopo_obra_ativo ──┬── compras_governanca_ativa   (Fase 3)
                    └── papéis na assinatura       (Fase 5 parte A)
```

Com `escopo_obra_ativo=FALSE` — o default — `papel_na_obra` devolve **GESTOR
para todo usuário autenticado do tenant**. Consequência: qualquer um aprova
compra, e qualquer um assina, aprova, reabre e retifica RDO. Ligar a
governança de compras sem o escopo é **ligar uma alçada de mentira**.

Ou seja: `escopo_obra_ativo` é a primeira peça, e enquanto ela não subir, as
Fases 3 e 5 estão entregues mas sem o controle que as justifica.

## O que trava `escopo_obra_ativo` — e é decisão sua, não código

O passo 4 do runbook da Fase 1 exige que toda obra tenha um **gestor**: um
`Obra.responsavel_id` que encadeie até um usuário com login. Sem isso, a obra
fica sem ninguém que a edite além do ADMIN no instante em que a flag liga.

⚠️ dev, 21/07: de **8.723 obras**, apenas **4** tinham `responsavel_id`
preenchido e **1** tinha a cadeia completa. O backfill derivaria **zero**
vínculos. Volumetria de desenvolvimento — vale como forma do problema, não
como volume.

**Ninguém rodou essa contagem em produção.** É o número que decide se o
rollout é uma tarde ou um projeto à parte. E se produção estiver igualmente
vazia, *por qual critério atribuir gestor* (quem mais apontou RDO? quem criou
a obra?) vira pré-requisito — e é decisão de negócio.

---

# O plano, em cinco ondas

## Onda 0 — deploy e medição (bloqueia todo o resto)

Nada disso muda comportamento para o usuário.

1. **Confirmar que produção está rodando o código novo.** `origin/main` está
   em `70046475`, mas o EasyPanel builda por conta própria — o
   `docs/plano-deploy-seguro.md` registra que produção já rodou **35 commits
   atrás** do trabalho local. As migrations rodam sozinhas no startup
   (`docker-entrypoint-easypanel-auto.sh`), então **deploy = migrations
   aplicadas**. Confira a maior migration aplicada depois do deploy.
2. **Medir a cadeia de gestor** (o número que trava tudo):

       python scripts/backfill_usuario_obra.py --admin-id <ID>        # dry-run
       python scripts/relatorio_estado_obra.py                        # obras EM EXECUÇÃO sem gestor

3. **Medir os custos sem destino** (Fase 4, já ativa):

       python scripts/relatorio_destino_custo.py

Saída da onda: três números de produção. Sem eles, qualquer estimativa das
ondas seguintes é chute.

## Onda 1 — `escopo_obra_ativo` num tenant piloto

Segue `docs/fase-1-rollout.md` passo a passo. Escolha o tenant **menor** com
uso real, não o maior.

1. Backfill de identidade em dry-run → resolver `ambiguo` no cadastro.
2. Aplicar identidade.
3. Backfill de vínculos em dry-run → **resolver as obras sem gestor** (é aqui
   que o número da Onda 0 vira trabalho).
4. Aplicar vínculos.
5. `python scripts/flag_escopo_obra.py <ID> --ligar` — o guard recusa se a
   tabela de vínculos estiver vazia.
6. Rodar uma semana. O que observar: alguém perdeu acesso a uma obra que
   deveria enxergar?

**Rollback:** `--desligar`. É instantâneo e devolve o comportamento antigo.

## Onda 2 — Fase 5 parte A, no mesmo tenant

Com o escopo ligado, a diferenciação de papel na assinatura passa a existir.
Não há flag: o que muda é **anunciar o fluxo** assinar/aprovar para o tenant.

1. Confirmar que o piloto tem `escopo_obra_ativo=TRUE`.
2. Fazer um ciclo real: preencher → assinar → aprovar, com pessoas diferentes.
3. Confirmar que a trilha `rdo_transicao_estado` registrou autoria.

⚠️ **NÃO faça a parte B (migração das fotos, 16 GB) nesta onda.** Ela tem seis
pré-requisitos humanos de infraestrutura, todos bloqueantes, e nenhum foi
feito: volume ≥ 25 GB, `UPLOADS_PATH` no painel, Task 13 já em produção, dump
completo fora do servidor, snapshot confirmado com a Hostinger e janela de
manutenção para o `VACUUM FULL`. Ver `docs/fase-5-rollout.md` parte B.

## Onda 3 — `compras_governanca_ativa`

Só depois de a Onda 1 ter rodado uma semana sem incidente.

1. **Decisão pendente:** confirmar as faixas de alçada. As semeadas —
   R$ 5.000 / R$ 30.000 / acima — são recomendação do plano, **não** decisão
   do negócio. Trocar é UPDATE em `faixa_alcada`, sem deploy.
2. Conferir que toda obra ativa tem um GESTOR que não seja o solicitante
   habitual, e pelo menos um COMPRADOR.
3. `python scripts/flag_compras_governanca.py <ID> --ligar`.
4. Ciclo completo numa obra piloto, com três pessoas: cria → aprova → emite.

## Onda 4 — as entregas de 24/07 (sem runbook hoje)

Independentes das ondas 1-3; podem correr em paralelo com a 2.

- **`cronograma_editor_v2`** — o guard só *avisa* se o calendário do tenant
  considera sábado ou domingo (o motor novo é seg-sex fixo nesta fase), e o
  aviso sai **depois** de gravar. Confira o calendário antes.
- **`rdo_percentual_livre`** — muda o apontamento de TODA tarefa de TODA obra
  do tenant para percentual acumulado. O percentual atual é preservado, e
  desligar reverte. **O `--ligar` não tem guard nenhum**: o aviso sobre as
  tarefas em modo `quantidade` é impresso depois da gravação.
  ⚠️ Antes de ligar em qualquer tenant, falta a **conferência visual dos dois
  fluxos de RDO** (novo e editar) com a flag ligada — era risco explícito do
  plano e não tem registro de ter sido feita.

---

## Lacunas que esta revisão encontrou

Nenhuma é bug de código; todas são prontidão.

| # | Lacuna | Consequência |
|---|---|---|
| 1 | **Três flags sem runbook** (`cronograma_mpp_ativo`, `cronograma_editor_v2`, `rdo_percentual_livre`) | Ligar vira improviso; não há passo-a-passo nem critério de rollback escrito |
| 2 | **`flag_rdo_percentual_livre --ligar` sem guard** | É a flag de maior alcance (toda tarefa de toda obra) e a única que não recusa nada. O aviso é *post-hoc* |
| 3 | **`flag_cronograma_editor_v2` avisa depois de gravar** | Mesma forma do nº 2, com impacto menor |
| 4 | **Conferência visual do RDO percentual nunca feita** | Risco previsto no plano, em aberto |
| 5 | **Nenhuma medição de produção** | Todo dimensionamento das ondas 1-3 é chute até a Onda 0 |
| 6 | **Linhas `[FASE4:R5]` não revisadas** | 77 filhos órfãos foram carimbados no backfill de dev; produção não foi olhada |

## O que eu recomendo fazer primeiro

**A Onda 0.** São três comandos de leitura, não mudam nada e destravam a
conversa inteira — hoje não dá para estimar nem priorizar sem eles.

Em paralelo, e barato: **escrever os três runbooks faltantes** e **pôr guard
no `flag_rdo_percentual_livre`** (lacunas 1 e 2), para que a Onda 4 não seja
o único rollout sem rede.
