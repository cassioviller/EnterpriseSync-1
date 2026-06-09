# [Refactor F] Caching de config do tenant por request (eliminar N+1)

> Bloco F do plano de remediação. Prioridade P6 — baixo risco.

## Problem Statement

A configuração da empresa é consultada repetidamente dentro de fluxos por-item
(materializar itens de proposta, render de medição, cronograma, portal de
obras). Isso gera um padrão N+1: N itens → N consultas idênticas à mesma linha
de configuração do tenant. Um caso já foi resolvido na precificação BDI via
cache por-request.

## Solution

Um helper compartilhado de configuração do tenant com **cache por request**
(escopo de aplicação), adotado nos pontos quentes de loop. Uma consulta por
request em vez de uma por item.

## Commits

1. Promover o cache por-request de configuração (já existente no helper de
   precificação) a um utilitário compartilhado.
2. Substituir as consultas em loop nos pontos quentes (materialização de
   proposta, medição, cronograma, portal) pelo utilitário.
3. Medir a contagem de consultas à configuração antes/depois num fluxo
   representativo e registrar o ganho.
4. Verde: a configuração é consultada uma vez por request nos fluxos tocados;
   sem regressão funcional.

## Decision Document

- Configuração do tenant é resolvida no máximo uma vez por request.
- O cache é por contexto de aplicação (request), não de processo (evita o bug de
  instância detached do Bloco A).
- O helper é a forma padrão de obter a configuração do tenant em código novo.

## Testing Decisions

- Testar comportamento externo + uma asserção de eficiência: "duas chamadas no
  mesmo request resultam em uma consulta".
- Prior art: a verificação de contagem de consultas usada para validar o cache
  de configuração do BDI.

## Out of Scope

- Cache entre requests / invalidação distribuída.
- Outras configurações além da configuração da empresa do tenant.

## Further Notes

Composição direta com o Bloco A: o padrão correto é "cache por request de
valores/configuração", nunca instância ORM em cache de processo.
