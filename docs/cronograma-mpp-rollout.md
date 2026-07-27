# Importação de cronograma (.mpp/.xml) — runbook de rollout

> Flag `configuracao_empresa.cronograma_mpp_ativo` (migração 211, default
> `FALSE`). Módulos M08/M09/M10.
>
> É a flag mais antiga das cinco e a de menor risco: ela governa **a borda
> visual**, não o acesso.

## O que a flag faz — e o que ela não é

Ligada, a **aba Cronograma da página da obra** passa a mostrar a área de
importação (.mpp/.xml → prévia com decisão de mapeamentos → Aplicar →
Restaurar versão).

> ⚠️ **Não é controle de acesso.** Os endpoints de importação seguem
> protegidos por `cronograma_import_required` + escopo de tenant. Desligar a
> flag **esconde a área**, não fecha a porta.

## O bloqueio nº 1 vem antes da flag

O tenant precisa ser **`versao_sistema = 'v2'`**. Sem isso, `_check_v2()` faz
flash + redirect em **todas** as rotas de cronograma e o menu "Obras →
Cronograma" some — a flag ligada não muda nada.

São pelo menos cinco portas independentes. Antes de mexer em qualquer uma,
rode o diagnóstico, que responde as cinco de uma vez:

    python scripts/diagnostico_cronograma_tenant.py <ID>
    python scripts/diagnostico_cronograma_tenant.py <ID> --json

| # | Porta | Efeito quando fechada |
|---|---|---|
| 1 | `Usuario.versao_sistema != 'v2'` | esconde o módulo INTEIRO |
| 2 | `cronograma_mpp_ativo = FALSE` | esconde só a aba de importação |
| 3 | `escopo_obra_ativo = TRUE` sem `usuario_obra` | usuário deixa de enxergar a obra |
| 4 | `obra.cronograma_revisado_em IS NULL` + proposta de origem | a obra cai no gate de revisão inicial |
| 5 | `Servico.template_padrao_id` ausente | a obra nasce sem tarefa nenhuma |

## A ordem

1. **Diagnostique** (comando acima) e resolva o que ele apontar — na ordem em
   que ele lista, porque a porta 1 mascara todas as outras.
2. **Ligue.**

       python scripts/flag_cronograma_mpp.py <ID> --ligar

3. **Importe um .mpp numa obra de homologação** e confira a prévia: quantas
   tarefas casaram, quantas ficaram pendentes de mapeamento, quantas seriam
   removidas.
4. **Aplique e verifique a equivalência.** Este é o passo que o M09 tornou
   obrigatório para a Baia e vale para qualquer obra:

       python scripts/verificar_equivalencia_obra.py <obra_id> --salvar antes.json
       # importe e aplique pela aba
       python scripts/verificar_equivalencia_obra.py <obra_id> --comparar antes.json

   Qualquer divergência ⇒ **Restaurar versão anterior** pela própria aba e
   investigar antes de seguir.

## Consequência importante: a obra passa a recusar reimport de JSON

Depois que uma obra é versionada por upload (.mpp/.xml aplicado), o reimport
físico-financeiro por JSON é **recusado** — ele é destrutivo e apagaria o
histórico de versões. É o guard `_recusar_se_versionada_pelo_fluxo_novo`.

Para acrescentar **RDOs** a uma obra nesse estado, use o caminho
não-destrutivo (27/07):

    python scripts/atualizar_rdos_obra.py <admin> <codigo_obra> payload.json --dry-run

Ver `RDO.md` e `ESTADO_ATUALIZACAO_BAIA.md`.

## Rollback

    python scripts/flag_cronograma_mpp.py <ID> --desligar

Esconde a aba de novo. **Não desfaz importação já aplicada** — para isso, use
"Restaurar versão" na própria aba, enquanto ela ainda está visível. Ou seja:
restaure **antes** de desligar a flag.

## O que este módulo deliberadamente NÃO fez

- **Não substitui o import físico-financeiro por JSON** na criação inicial da
  obra — só na atualização de cronograma.
- **Não é controle de acesso** (ver o aviso no topo).
- **Não sincroniza custo.** A importação traz cronograma; o custo por etapa
  continua vindo do caminho comercial.
