# [Refactor G] Onboarding / prontidão do tenant (checklist + avisos)

> Bloco G do plano de remediação. Prioridade P7 — baixo risco. Reusa o registro
> de pendências do Bloco B.

## Problem Statement

A cadeia folha→contabilidade só funciona com parâmetros legais do ano, plano de
contas completo e funcionários cadastrados. Um tenant novo (e o próprio tenant
demo) cai nas mesmas falhas silenciosas porque nada sinaliza que a configuração
está incompleta. Não há uma visão de "o que falta para a empresa operar".

## Solution

Um serviço de "prontidão do tenant" que avalia os pré-requisitos e expõe um
checklist com status e deep-links, mais avisos contextuais nas telas que
dependem de configuração (ex.: processar folha avisa se faltam parâmetros
legais do ano).

## Commits

1. Serviço de prontidão: dado um tenant, retorna a lista de itens (parâmetros do
   ano, plano de contas essencial, BDI, ≥1 funcionário) com status e ação.
2. Card "Configuração da empresa: X% pronta" na home do gestor, ligado ao
   serviço.
3. Avisos contextuais nas telas dependentes (folha, contabilidade) antes da ação
   que falharia.
4. Verde: e2e — tenant sem parâmetros mostra checklist incompleto e CTA; após
   configurar, 100%.

## Decision Document

- Há um único serviço que define "o que torna um tenant pronto para operar".
- O checklist é derivado (não um estado persistido) — sempre reflete o banco.
- Os avisos contextuais reutilizam os deep-links de correção do Bloco B.

## Testing Decisions

- Testar comportamento externo: "tenant sem item X → checklist marca X
  incompleto com link"; "supre X → checklist completa".
- Prior art: testes de página/smoke da suíte all-modules (render autenticado).

## Out of Scope

- Wizard de onboarding passo-a-passo com persistência de progresso.
- Bloqueio rígido de funcionalidades antes da configuração (apenas avisos).

## Further Notes

Depende conceitualmente do Bloco B (deep-links de correção), mas o serviço de
prontidão pode ser construído antes e ligado aos avisos depois.
