# [Refactor H] Infra de testes (fixtures, fim dos skips silenciosos) + migrações

> Bloco H do plano de remediação. Prioridade P8 — baixo risco. Recomendado após
> o Bloco C (create_app único).

## Problem Statement

A suíte mistura testes pytest e scripts standalone (com `sys.exit`), alguns com
identificadores de tenant hardcoded e **skip silencioso** quando falta dado de
ambiente — o que chegou a esconder nove testes de integração inteiros. O arquivo
de migrações tem mais de 13 mil linhas, com numeração manual ("próximo número
livre") e lacunas, frágil para colaboração.

## Solution

Uma camada de fixtures que garante os pré-requisitos dos testes (eliminando
skips por dado ausente) e a organização incremental das migrações (extrair o
registro, documentar a convenção), sem big-bang.

## Commits

1. Fixture de tenant de teste que garante os pré-requisitos (generalizar o seed
   idempotente já adicionado à suíte all-modules), removendo os skips por dado
   ausente.
2. Converter os scripts standalone críticos em testes pytest de verdade (sem
   `sys.exit`), preservando as asserções.
3. Migrações: extrair a lista-registro das migrações para um módulo próprio e
   documentar a convenção de numeração.
4. (Opcional/futuro) Avaliar split das migrações por domínio, mantendo o
   histórico aplicado intacto.
5. Verde: `pytest` sem skips por dado de ambiente; suíte estável.

## Decision Document

- Pré-requisitos de teste são providos por fixture, não por dado ambiente —
  testes não pulam em silêncio por falta de seed.
- Scripts de verificação críticos viram testes pytest coletáveis.
- O registro de migrações é separado das definições; a numeração tem convenção
  documentada.

## Testing Decisions

- Este bloco **é** infra de teste; o critério é "a suíte não pula por dado
  ausente e roda determinística em execuções repetidas".
- Prior art: o seed idempotente `_garantir_dados_e2e` e a fixture de sessão da
  suíte all-modules.

## Out of Scope

- Reescrever todas as migrações históricas.
- Trocar o runner/orquestração de CI.

## Further Notes

Fica melhor depois do Bloco C: com a fábrica única, a fixture pode subir a app
completa (todos os blueprints) sem o contorno de import atual.
