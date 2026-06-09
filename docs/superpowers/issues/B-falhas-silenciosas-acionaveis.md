# [Refactor B] Falhas silenciosas de eventos → sinais acionáveis

> Bloco B do plano de remediação. Prioridade P2. Depende em parte do Bloco D
> (mensagem de plano de contas).

## Problem Statement

Os efeitos colaterais orientados a evento (aprovar proposta → Obra; entrada de
material → GestãoCusto; processar folha → Lançamento contábil) falham em
silêncio quando faltam pré-requisitos. O gestor vê "sucesso" enquanto o efeito
colateral não acontece — por exemplo, folha processada sem lançamento contábil
porque uma conta essencial não existe. A falha só aparece num `logger.warning`
que ninguém lê.

## Solution

Tornar a ausência de pré-requisito **visível e acionável** sem quebrar o fluxo
principal: registrar o resultado de cada evento (ok/falha + motivo + ação de
correção), devolver um aviso no flash da ação do usuário e oferecer um painel de
"integrações pendentes".

## Commits

1. Criar o registro de resultado de evento (status, motivo, referência de
   origem, link de correção) — migração + modelo.
2. Handler de folha→lançamento: ao faltar conta essencial, registrar a pendência
   e propagar a mensagem para a rota de processar.
3. Rota de processar folha: exibir flash de pendência acionável ("lançamento
   contábil pendente — conta X ausente [Configurar]").
4. Aplicar o mesmo padrão a material→GestãoCusto e proposta→Obra (faltando
   fornecedor/cliente/etc.).
5. Painel "Integrações pendentes" listando as falhas não resolvidas, com link de
   correção; marcar como resolvida quando o pré-requisito é suprido.
6. Verde: e2e — processar sem o pré-requisito mostra pendência; com ele, ok e a
   pendência some.

## Decision Document

- Falhas de efeito colateral nunca abortam o fluxo principal; são registradas e
  sinalizadas.
- Cada pendência tem um motivo legível e uma ação de correção (deep-link).
- O registro de eventos é a fonte do painel de pendências e da telemetria.

## Testing Decisions

- Testar o **comportamento observável**: dado um pré-requisito ausente, a ação
  do usuário sinaliza pendência e o registro é criado; suprido o pré-requisito,
  a próxima execução resolve.
- Módulos testados: handlers de folha, material e proposta; a view de processar
  folha; o painel de pendências.
- Prior art: testes de integração da suíte all-modules que verificam efeitos
  colaterais (proposta→obra→lançamento).

## Out of Scope

- Reprocessamento automático/retry de eventos falhos (fica para um follow-up).
- Notificações por e-mail/push das pendências.

## Further Notes

A mensagem de plano de contas incompleto fica melhor após o Bloco D (fonte
única), mas o mecanismo de pendência não depende dele.
