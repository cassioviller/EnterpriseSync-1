# [Refactor D] Fonte única do plano de contas (+ ADR registrando a PK global)

> Bloco D do plano de remediação. Prioridade P4. **Decisão tomada:** consolidar
> os seeders sem mexer na chave primária agora; o ADR registra o porquê.

## Problem Statement

Existem dois seeders divergentes do plano de contas, com definições conflitantes
para os mesmos códigos (ex.: o nível "5.1.01" significa coisas diferentes em cada
um). O tenant demo ficou com um plano incompleto (faltava todo o ramo de
despesas), o que travava silenciosamente a folha→contabilidade. Além disso, o
código da conta é **chave primária global** — o plano de contas é, na prática,
compartilhado entre tenants, o que é um cheiro de multi-tenancy.

## Solution

Escolher uma definição canônica do plano de contas e um único seeder
idempotente que **completa lacunas por tenant** (criando contas-pai faltantes),
em vez de pular quando já existem contas. A questão da chave primária é
registrada num ADR que documenta a decisão de **não** migrar o schema agora
(consolidar primeiro, reavaliar depois).

## Commits

1. Escolher a definição canônica (a que contém a cadeia de despesas exigida pelo
   handler de folha) e marcar a outra como deprecada.
2. Transformar o seeder canônico em "completar lacunas": idempotente por código,
   criando pais ausentes em ordem hierárquica.
3. Migração de saneamento: para cada tenant, garantir o conjunto de contas
   essenciais (incluindo a conta de despesa de pessoal usada pela folha).
4. Escrever o ADR comparando "código como PK global" vs "(admin_id, código)";
   registrar a decisão de manter a PK atual por ora e os critérios para revisar.
5. Verde: todo tenant tem as contas essenciais; folha→lançamento funciona para
   um tenant recém-saneado.

## Decision Document

- Há uma única definição canônica do plano de contas e um único seeder.
- O seeder completa lacunas idempotentemente em vez de tudo-ou-nada.
- A chave primária do plano de contas **permanece** como está nesta entrega; a
  alternativa (chave composta por tenant) fica documentada em ADR como decisão
  adiada, com gatilhos de reavaliação.
- O saneamento dos tenants existentes é feito por migração idempotente.

## Testing Decisions

- Testar comportamento externo: "um tenant sem o ramo de despesas, após o
  seeder, tem as contas essenciais" e "folha processada gera lançamento".
- Prior art: o teste de integração folha→lançamento da suíte all-modules (que
  hoje semeia a conta faltante manualmente — passará a depender do seeder).

## Out of Scope

- Migrar a chave primária para `(admin_id, código)` (apenas decidido no ADR).
- Redesenhar a árvore de contas / relatórios contábeis.

## Further Notes

O seed de teste que adicionei na suíte all-modules cria a cadeia de despesas
manualmente; após este refactor, ele pode passar a confiar no seeder canônico.
