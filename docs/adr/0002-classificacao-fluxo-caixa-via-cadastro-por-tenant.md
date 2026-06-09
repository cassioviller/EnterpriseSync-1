---
status: accepted
---

# Classificação da importação de Fluxo de Caixa via cadastro por tenant (não hardcode)

## Contexto

A classificação dos lançamentos da importação de Fluxo de Caixa
(`services/importacao_excel.py`) era feita por ~300 regras **hardcoded** —
`_classificar_categoria_nomeada` e mapas de plano/keywords. Para importar os dados
específicos da Veks, faltavam muitas associações (ex.: o subempreiteiro "maranhão"),
e cada falta exigia editar código. Não havia forma de o usuário ensinar o sistema,
nem de rastrear o que ficou sem classificar.

## Decisão

Migrar **toda** a classificação nomeada para um cadastro de **Regras de
Classificação** por tenant (tabela `palavra_chave_categoria`), lido em memória a cada
importação. O hardcode é aposentado (mantido só como oráculo de teste de regressão).
O macro `tipo_categoria` passa a ser **derivado** da categoria nomeada. O conflito
entre regras é resolvido por **prioridade** (menor vence) com desempates explícitos,
substituindo a ordem que antes era fixa no código.

## Considered Options

- **A (escolhida)** — Migração total para o banco. Fonte única, tudo visível e
  editável pelo usuário; exige reproduzir fielmente as regras compostas (exceções,
  condição de obra, ordenação) e um teste de regressão como rede de segurança.
- **B** — Camada por cima + semear (banco roda primeiro, hardcode de fallback).
  Mais rápido e menos arriscado, mas mantém duas fontes de verdade e as regras
  compostas continuam no código. Rejeitada: o usuário quer ser dono total do motor.
- **C** — Camada pura (cadastro vazio sobre o hardcode intacto). Mínimo esforço, mas
  o usuário não enxerga as regras existentes. Rejeitada: sem visibilidade.

## Consequences

- **Mudança de comportamento intencional:** "Auto vs Pendente de Classificação" passa
  a depender de ter casado uma **categoria específica** (não mais de o macro
  `tipo_categoria` ser não-nulo). A contagem do split muda — validada à parte do teste
  de regressão.
- A **fidelidade do seed** é crítica; o teste de regressão contra o motor antigo sobre
  o Excel real é a salvaguarda.
- Abre caminho para **aprendizado**: Correções de linha viram Memória Exata
  (automática) e Sugestões de regra refinada (confirmadas pelo usuário) — detalhado no
  spec, fora do escopo deste ADR.
- Regras passam a ser **por tenant**: cada admin recebe sua cópia editável; o seed é
  idempotente por `admin_id`.
