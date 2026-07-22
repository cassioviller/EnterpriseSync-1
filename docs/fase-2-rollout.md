# Fase 2 — Rollout da máquina de estados da Obra

Roteiro de produção. Execute na ordem e anote as saídas. Nada aqui é
automático: as migrations rodam sozinhas no boot, mas os passos de conferência
e a decisão sobre a fila de handoff são humanos.

## 1 · Antes do deploy

```bash
# Censo do que existe HOJE em produção (somente leitura).
python scripts/relatorio_estado_obra.py
```

Anote: total, distribuição de `status`, grafias fora do mapa e divergências
`ativo`×`estado`. Os números de desenvolvimento (22/07: 2.621 em execução,
919 planejamento, 1 grafia desconhecida, 10 divergências) **não valem para
produção** — o censo do plano original já estava errado uma vez por confiar
em números de outra base.

Se aparecerem grafias fora do mapa em volume relevante, acrescente-as a
`services/obra_estado._MAPA_LEGADO` **antes** do deploy — senão a 231 as
derivará só por `ativo` (regra: ativo=false → concluida; resto → em_execucao).

## 2 · O deploy aplica sozinho

Migrations 230 (tabela de histórico), 231 (coluna `estado` + backfill +
NOT NULL + CHECK) e 232 (alinha o texto de `status` ao estado). Idempotentes;
`is_migration_executed` só aceita 'success', então falha é retentada no boot
seguinte.

**Atenção:** falha de migração NÃO derruba o boot (`run_migration_safe` só
loga). Depois do deploy, confira nos logs:

```
MIGRACAO 230 CONCLUIDA / MIGRACAO 231 CONCLUIDA (com a distribuição) /
MIGRACAO 232 CONCLUIDA
```

A 231 loga a distribuição final por estado e avisa se alguma obra caiu na
salvaguarda (`investigar`).

## 3 · Depois do deploy

```bash
python scripts/relatorio_estado_obra.py
```

- `sem estado (NULL)` tem de ser **0**;
- `grafias fora do mapa` tende a zero depois da 232;
- **`EM EXECUÇÃO sem gestor` é a fila de handoff que o backfill criou** —
  toda obra que já estava "Em andamento" antes da Fase 2 nunca passou por
  handoff. Levar esse número ao Cássio: a decisão de quem vira GP de quê é
  de negócio, não de código. Não há prazo técnico — a obra funciona sem
  gestor vinculado; ela só não tem ninguém além do admin autorizado a
  pausar/concluir.

## 4 · O que muda para o usuário no dia

| Quem | O que muda |
|---|---|
| Todo mundo | Obra nova (proposta aprovada ou manual) nasce em **Planejamento**, não "Em andamento". Entra em execução pelo handoff. |
| Quem edita obra | O select de status do formulário virou badge — estado muda pelo painel da obra, com motivo e registro. |
| Quem usa o toggle da listagem | Concluir/reabrir passou pela máquina: obra em Planejamento ou Pausada não conclui pelo botão (mensagem explica), Cancelada não reabre. |
| Dashboard | Contadores passaram a olhar `estado` — obras em Planejamento **contam** como ativas (antes uma obra com esse status sumia dos cards). |
| n8n | Dois eventos novos na allowlist: `obra.estado_alterado` e `obra.handoff` (payload leva o dossiê). `obra.concluida` continua. |

## 5 · Reversão

- **Dados:** a linha de backfill da 231 em `obra_transicao_estado`
  (`estado_de IS NULL`) guarda o `status` e o `ativo` originais verbatim no
  campo `motivo`. Para restaurar o texto antigo de uma obra:

  ```sql
  -- exemplo: ver o valor original
  SELECT obra_id, motivo FROM obra_transicao_estado
   WHERE estado_de IS NULL AND obra_id = :id;
  -- 'backfill migration 231 — status legado=<valor> | ativo=<bool>'
  ```

- **Comportamento:** reverter o deploy volta o código, e as colunas novas
  (`estado`, tabela de histórico) ficam ociosas sem quebrar nada — nenhum
  código antigo as lê. O CHECK `ck_obra_estado` e o NOT NULL só travam
  escrita em `estado`, coluna que o código antigo não escreve.

## 6 · O que a Fase 3 espera daqui

A `Requisicao` de compras vai se pendurar numa obra com estado: é o
`EM_EXECUCAO` que autoriza requisitar, e é o `UsuarioObra(GESTOR)` criado
pelo handoff que aprova a alçada. A fila do passo 3 é, portanto, também a
lista de obras que não terão aprovador quando a Fase 3 chegar.
