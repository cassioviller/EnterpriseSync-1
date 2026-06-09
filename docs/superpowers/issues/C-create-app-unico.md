# [Refactor C] Fábrica única create_app() — `app` registra o mesmo que `main:app`

> Bloco C do plano de remediação. Prioridade P3 — risco médio (ordem de boot).

## Problem Statement

A aplicação importável (`from app import app`) registra um conjunto de
blueprints; produção sobe `main:app`, que registra um conjunto **maior** (vários
blueprints extras, como custos de escritório, importação e hubs de cadastro). O
resultado é uma classe inteira de bugs que só aparecem em um dos caminhos — por
exemplo, `url_for` do nav quebrando com `BuildError` quando uma página é
renderizada sob `app` sem os blueprints de `main`. Testes que importam `app`
divergem do que roda em produção.

## Solution

Uma fábrica única que registra **todos** os blueprints, usada tanto pela app
importável quanto pelo entrypoint de produção. Assim os dois caminhos têm o
mesmo `url_map`.

## Commits

1. Extrair o registro de blueprints do entrypoint de produção para uma função
   única e idempotente (mantendo o try/except por blueprint que já existe).
2. Fazer a app importável chamar essa função no boot.
3. Fazer o entrypoint de produção delegar à fábrica (sem re-registrar).
4. Remover contornos de teste que importavam o entrypoint só para registrar
   blueprints faltantes.
5. Verde: a contagem de rotas da app importável passa a igualar a de produção;
   suíte all-modules verde; `url_for` do nav resolve nos dois caminhos.

## Decision Document

- Existe uma única fonte de verdade para o registro de blueprints.
- O registro é idempotente e tolerante a falha por blueprint (um blueprint que
  não importa não derruba o boot).
- A ordem de import/efeitos de boot é preservada (migrações, hooks).

## Testing Decisions

- Testar comportamento externo: "todas as rotas do nav resolvem" e "a app
  importável tem o mesmo conjunto de endpoints de produção".
- Prior art: o teste que renderiza páginas com o nav (no-leak / formato BR) e a
  varredura de console da suíte all-modules.

## Out of Scope

- Reorganizar a estrutura de pastas dos blueprints.
- Mudar o servidor/entrypoint (gunicorn) ou flags de boot.

## Further Notes

Validar a cada passo com a suíte rodando — risco está na ordem de import e em
efeitos colaterais do boot (migrações automáticas).
