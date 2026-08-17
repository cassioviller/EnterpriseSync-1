# FECHO — Sessão de 2026-08-05: B3.6–B3.10 e o E02

> Data: **2026-08-05**. Escopo executado: bloco **B3 inteiro** (as cinco Tasks
> restantes) e **B4.8/B4.9** (E02). Plano de referência:
> `docs/superpowers/plans/2026-08-04-plano-consolidado.md`, que é a fonte de
> verdade — este documento é o resumo, não o registro.
>
> Marcas de procedência conforme `ESTADO-ATUAL.md`: 🔬 medido · 📖 lido no código
> · 🧮 deduzido · ⚠️ dev (banco de desenvolvimento, prova a forma e não o volume).

## Commits (13, todos locais — **nada foi enviado ao remoto**)

| Commit | Conteúdo |
|---|---|
| `01883756` | B3.6 — gate de partida dobrada loga quando pula por falta de conta contábil |
| `0fc44bc6` | B3.7 — conta a receber já liquidada não aceita nova baixa |
| `95912e7c` | B3.8 — baixa de conta a receber grava `FluxoCaixa` ENTRADA |
| `976c416a` | plano: fecha B3.6–B3.8 |
| `352719a0` | B3.9 — CR de medição nasce com conta contábil |
| `b0667136` | plano: fecha B3.9 |
| `9e72db82` | B3.10 — teste do A03 pelo caminho de produção |
| `948bece0` | plano: fecha B3.10 + correção de proveniência |
| `9b62d073` | plano: marca B3.1–B3.5 retroativamente |
| `ebea71ca` | plano: marca B2.12 e B2.20 retroativamente |
| `ab626765` | B4.8 — remove `NotificacaoCliente` e os três pontos de limpeza |
| `84e17260` | B4.9 — migração 279 com guard de contagem |
| `0e152e0b` | plano: fecha B4.8/B4.9 e marca o Step 1 como NÃO cumprido |
| `3ba7937c` | o **quarto** ponto do E02, que o arreio pegou |

**Gate final:** 🔬 `1937 passed, 6 skipped, 2 xfailed, 0 falhas` em 21min27
(`tests/reports/pytest_output_20260805_193809.txt`). Um teste a mais que o gate
anterior — o cenário 1, escrito nesta sessão.

---

## 🔴 A ÚNICA COISA QUE PRECISA DE AÇÃO ANTES DO DEPLOY

**O gate absoluto do E02 não foi cumprido.** O Step 1 da B4.8 exige
`SELECT count(*) FROM notificacao_cliente` no banco de **PRODUÇÃO**, e a Task diz
explicitamente que a contagem do ambiente de desenvolvimento não vale como
evidência. Ela não foi obtida — o agente não tem acesso a produção.

⚠️ dev: a contagem local (`helium/heliumdb`) é **0**. O usuário, depois de o risco
ser enunciado, decidiu tratar esse 0 como gate. **A decisão é dele**; está
registrada no plano e em `ab626765` para que ninguém a leia como evidência de
produção.

🔬 **Medido, e é mais afiado do que o risco previa:** com **uma** linha em
`notificacao_cliente` apontando para o RDO, a exclusão depois da B4.8 **falha em
silêncio** — a rota responde **200**, o RDO **sobrevive**, nada é anulado. Sem o
modelo, o SQLAlchemy perdeu o `relationship` que anulava a FK `NO ACTION`. Não há
erro visível: o sintoma é alguém reclamar que o RDO não some.

**No deploy, conferir o log de boot:**

* migração 279 → `success` ⇒ a tabela estava vazia, o E02 está correto, nada a fazer;
* migração 279 → `failed` ⇒ **`git revert ab626765`**. A migração protege o dado
  (não dropa), mas **não conserta a exclusão**, porque o código já saiu sem a
  limpeza. E ela retenta a cada boot, repetindo o erro no log.

---

## O que ficou provado, e como

**B3.10 — as mutações que mediram o defeito.** 🔬 Trocar a conta da CR de medição
para `4.1.01.001` (a que o documento do A03 sugeria) derruba três dos quatro
testes, e o do DRE **mede a dupla contagem**: receita bruta de **1.000 → 1.500**
por causa de um recebimento. 🔬 Atribuir o código sem confirmar em `plano_contas`
derruba o quarto com `ForeignKeyViolation` → `PendingRollbackError` — o modo de
falha em cascata do risco 1 da B3.9, reproduzido.

**B3.8 — Step 5 cumprido nos dois braços.** 🔬 Trocar `name="criar_fluxo_caixa"`
derruba só o teste do modal; remover `obra_id=conta.obra_id` derruba só o do fluxo
por obra. Cada mutação, um teste e nenhum outro.

**B4.9 — três caminhos.** 🔬 Com 1 linha semeada: levanta `DROP ABORTADO` e a
tabela sobrevive. Vazia: dropa. Sem a tabela: no-op. 📖 A segurança por construção
foi conferida no código, não presumida: `run_migration_safe` grava `'failed'` sem
propagar (`migrations.py:186-199`) e `is_migration_executed` só aceita `'success'`
(`:83-85`).

---

## O que este fecho NÃO atesta

**As marcações retroativas.** B3.1–B3.5, B2.12 e B2.20 estavam entregues no código
e com as caixas em branco no plano. Foram marcadas nesta sessão, **por quem não as
executou**. O que sustenta cada uma é a implementação conferida 📖 âncora por
âncora (citada em cada `Status`) e o gate verde. **Não atesta** que cada Step foi
cumprido na ordem, que os testes foram vistos vermelhos antes, ou que não houve
desvio silencioso.

**O vermelho do Step 1 da B3.8.** O teste chegou junto com a implementação, numa
sessão anterior. As mutações são a prova retroativa de que ele não é vacuoso — não
são a mesma coisa que ter visto o vermelho.

---

## Achado de método, que vale para as próximas aposentadorias

A B4.8 tinha um **quarto ponto vivo** que o plano não lista e que o método do
recorte não podia achar: as três edições prescritas saíram de grep pelo **modelo**
`NotificacaoCliente`; três outras referências citam a tabela por **string**
(`views/obras.py:TABELAS_DEPENDENTES_OBRA`, percorrida a cada exclusão de obra;
`utils/database_diagnostics.py:MIGRATION_48_TABLES`;
`fix_all_admin_id_universal.py:BACKFILL_STRATEGIES`, que roda no boot).

Nenhum grep do símbolo Python as encontrava. Quem pegou foi
`test_lista_nao_tem_tabela_fantasma`, que já existia — o argumento do próprio plano
sobre por que teste textual não serve contra remoção, confirmado pelo lado bom.

**Num bloco de REMOÇÃO, procurar só pelo símbolo deixa passar tudo que referencia a
estrutura por string.**

---

## Em aberto

| Item | Estado |
|---|---|
| **B2.13** | 🔴 bloqueada — Step 1 é rodar a consulta do invariante da folha em **produção** |
| **Lado PAGAR do `FluxoCaixa`** | 🟡 **sem Task no plano**. 📖 Mesmo defeito do A02: `contas_pagar.html` não manda `criar_fluxo_caixa`, então o `FluxoCaixa` SAIDA só nasce por URL digitada à mão — e sem `obra_id` |
| **Curva planejada da baseline** | 🟡 **sem Task no plano** (risco 6 da B2.20). Depois do A06 a linha "planejado" da Curva S é plano corrente, não compromisso: a curva nunca mais mostra atraso contra o plano original. Falta uma derivada da `CronogramaBaseline` |
| **`rdo_crud.listar_rdos`** | 🟡 sombreada por `views/rdo.py:rdos()` — quatro rotas do `main_bp` resolvem antes. Decidir se as rotas irmãs do `rdo_crud_bp` são aposentadas (registrado na B2.12) |

## Consultas que destravam o que sobrou

```sql
-- Gate do E02 (confirma ou derruba a substituição aceita nesta sessão)
SELECT count(*) FROM notificacao_cliente;

-- B2.13 — invariante da folha
SELECT count(*) FILTER (WHERE encargos_inss_patronal > 0) AS com_inss,
       count(*) FILTER (WHERE encargos_inss_patronal > 0
         AND ROUND(encargos_fgts + encargos_inss_patronal, 2)
          <> ROUND(custo_total_empresa - salario_bruto, 2)) AS violam
FROM folha_processada;
```
