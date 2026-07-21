# Fase 1 — runbook de rollout

A Fase 1 é aditiva enquanto `escopo_obra_ativo` estiver `FALSE`. Todo o
risco está em **ligar a flag**. A ordem abaixo não é sugestão.

## Por tenant, nesta ordem

1. **Backfill de identidade em dry-run**

       python scripts/backfill_identidade_funcionario.py --admin-id <id>

   Leia `ambiguo` e `sem_correspondencia`. Ambíguo é e-mail repetido no
   RH — resolver no cadastro antes de seguir.

2. **Aplicar a identidade**

       python scripts/backfill_identidade_funcionario.py --admin-id <id> --aplicar

3. **Backfill de vínculos de obra em dry-run**

       python scripts/backfill_usuario_obra.py --admin-id <id>

   O número que importa é **obras sem gestor**. Cada uma dessas obras,
   com a flag ligada, fica sem ninguém que a edite além do ADMIN.

4. **Resolver as obras sem gestor.** Preencher `Obra.responsavel_id`
   com um funcionário que tenha login, ou criar o vínculo à mão.

   > ⚠️ **Este passo é maior do que parece — meça antes de estimar.**
   >
   > 🔬 Dry-run no banco de **desenvolvimento** em 21/07:
   >
   > | | |
   > |---|---|
   > | obras totais | 8.723 |
   > | obras com `responsavel_id` preenchido | **4** |
   > | obras com a cadeia completa (responsável → funcionário → usuário) | **1** |
   > | vínculos que o backfill conseguiu derivar | **0** |
   >
   > A cadeia de onde o backfill deriva o GESTOR está praticamente vazia,
   > porque `Obra.responsavel_id` quase nunca foi preenchido. Em dev, o
   > passo 5 não teria nada a aplicar e o passo 6 seria recusado pelo
   > script — corretamente.
   >
   > ⚠️ Volumetria de DEV, dominada por carga de suíte. **Rode as mesmas
   > contagens em produção antes de dimensionar**: lá `responsavel_id` pode
   > estar bem mais preenchido, e é isso que decide se este passo é uma
   > tarde de trabalho ou um projeto à parte.
   >
   > Se o número em produção for igualmente baixo, a decisão de por qual
   > critério atribuir gestor (quem mais apontou RDO? quem criou a obra?)
   > vira pré-requisito do rollout, e é decisão de negócio — não do script.

5. **Aplicar os vínculos**

       python scripts/backfill_usuario_obra.py --admin-id <id> --aplicar

6. **Ligar a flag**

       python scripts/flag_escopo_obra.py <id> --ligar

   O script recusa se `usuario_obra` estiver vazia para o tenant.

## Rollback

Um comando, sem tocar em schema:

    python scripts/flag_escopo_obra.py <id> --desligar

Volta ao comportamento pré-Fase 1 imediatamente. As tabelas e as FKs
continuam lá, inertes.

## O que a Fase 1 deliberadamente NÃO fez

- Não migrou as 177 rotas `@admin_required` nem as 587 `@login_required`
  para o novo eixo. Elas continuam com autorização só de tenant. Cada
  fase seguinte migra a sua fatia.
- Não tocou nos dois portais por token (`portal_obras_views.py`,
  `propostas_consolidated.py`), que continuam sendo um sistema de
  identidade paralelo, sem expiração e sem escopo de ação. Cinco rotas
  POST que mutam estado seguem alcançáveis só com a URL. Isso é dívida
  conhecida — candidata natural à Fase 9a, junto da assinatura de
  medição.
- Não resolveu `GESTOR_EQUIPES`, que segue sendo sinônimo de ADMIN em
  `views/metricas_views.py:44` e `crm_views.py:83`.
- Não criou `PapelObra.COMPRADOR`. Entra na Fase 3, com rota que o use.
```

- [ ] **Step 4: Rode a suíte inteira do gate**

```bash
bash run_tests.sh --gate 2>&1 | tail -40
```

Esperado: nenhuma regressão contra a baseline anotada no início da fase. Anote o número final de passados/falhados.

- [ ] **Step 5: Commit**

```bash
git add tests/test_fase1_matriz_autorizacao.py docs/fase-1-rollout.md
git commit -m "test(fase1): matriz papel x obra x acao + runbook de rollout

7 atores x 3 acoes numa tabela so, mais o teste de que /obras/<id>
devolve 404 (nao 403) para quem nao alcanca. Runbook documenta a ordem
obrigatoria do backfill e o rollback de um comando."
