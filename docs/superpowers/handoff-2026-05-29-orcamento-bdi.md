# Handoff — Orçamento / BDI / Lucro / Impostos (sessão grill-with-docs)

**Data:** 2026-05-29 · **Para:** retomar em nova sessão

## Objetivo

Corrigir e repensar o cálculo de preço do orçamento do SIGE, focado em **impostos e lucro**. Gatilho: bug em que lucro perto de 90% gera preço astronômico. Estamos numa sessão de **`grill-with-docs`** atacando a proposta de solução.

## Artefatos deste trabalho

- **Proposta de solução:** `docs/superpowers/specs/2026-05-29-orcamento-bdi-lucro-impostos-proposta.md` (diagnóstico das 5 falhas P1–P5, BDI explicado com fontes, Opções A/B/C, 6 pontos abertos).
- **Glossário:** `CONTEXT.md` (raiz) — termos Custo direto, BDI, Lucro, Tributos, Percentual de nota fiscal.
- **Decisão registrada:** `docs/adr/0001-bdi-por-dentro-padrao-tcu.md`.

## Diagnóstico (resumo)

Fórmula atual `services/orcamento_service.py:100`: `preço = custo / (1 − imposto% − lucro%)`. É um **BDI degenerado**; explode quando imposto+lucro→100% (90%L+8%T → divisor 0,02 → 50× o custo). 5 falhas: P1 sem validação; P2 descasamento conceitual (lucro é % do preço, não markup sobre custo); P3 "Lucro" exibido = preço−custo (inclui imposto); P4 não há BDI real (faltam AC/seguro/risco/garantia/desp. financeira); P5 `percentual_nota_fiscal` confunde.

## Decisões TRAVADAS

1. **Público vs privado → "os dois".** ⇒ BDI no padrão TCU, lucro e tributo **"por dentro"**. Crava **Opção A** (BDI completo); descarta B e C. Registrado no ADR 0001.

## Onde paramos (próxima pergunta — PENDENTE)

Estava perguntando a **definição canônica de "lucro"** e o que a tela deve mostrar. O usuário pediu para pausar e gerar este handoff antes de responder. **Retomar exatamente por aqui:**

> Quando você digita "lucro 10%", o que significa e o que a tela mostra como "Lucro"?
> - (rec.) **Lucro bruto sobre o preço (L do BDI)** — 10% = parcela do preço de venda; tela mostra Lucro = 10%×preço, separado do imposto; não desconta IR/CSLL.
> - Lucro bruto **+ estimativa de líquido** (exige cadastrar regime + alíquota IR/CSLL).
> - Outra definição (conflita com a decisão de BDI/TCU).

## Árvore de decisão restante (depois da pergunta acima)

1. Definição/exibição de "lucro" (bruto vs +líquido) ← **próxima**
2. **Granularidade do BDI**: por empresa (default), por orçamento (global) e/ou override por serviço/item? (cascata atual: item→global→serviço→0 em `orcamento_view_service.py:64`)
3. **`percentual_nota_fiscal`**: vira o `tributos_pct` (fonte única) ou continua só texto no PDF?
4. **Validação**: bloqueio rígido (não salva) vs aviso, e qual limite seguro de T+L (proposta sugere 85%). Mostrar o BDI% resultante ao lado dos campos.
5. **Migração/compat**: mapear `imposto_pct→tributos_pct`, `margem_lucro_pct→lucro_pct`, demais componentes default 0; não recalcular snapshots já gravados; recalcular rascunhos ao mudar BDI?
6. Faixa de BDI de referência (20–30%) como guia visual?

## Para retomar

1. Reabrir a `grill-with-docs` apontando para a proposta.
2. Continuar pela "próxima pergunta" acima; ir atualizando `CONTEXT.md` e abrindo ADRs conforme cada ramo fecha.
3. Ao fim, a proposta vira spec final → `writing-plans` → implementação (a fórmula deve ficar centralizada em `services/orcamento_service.py`).

## Notas de ambiente (importantes)

- Servidor roda `gunicorn --reload` (observa só `.py`); auto-reload de template do Jinja está OFF → **após editar template, `touch main.py`** para recarregar. (memória: [[gunicorn-template-cache-reload]])
- Skills do `mattpocock/skills` foram instaladas em `.claude/skills/` (inclui `grill-me`, `grill-with-docs`) — estão **untracked** no git.
- Trabalho de teste E2E (não relacionado) está commitado na branch `spec/e2e-jornada-proposta-cronograma`, incluindo um fix real (template não propagava prazo/validade).

## Arquivos-chave do cálculo

- `services/orcamento_service.py` — `calcular_precos_servico` (fórmula:100), `explodir_servico_para_quantidade` (lucro_unitario:344), `calcular_precos_servico_por_quantidade`.
- `services/orcamento_view_service.py:64` — cascata de alíquotas (item→global→serviço→0).
- `models.py` — `Servico.imposto_pct/margem_lucro_pct` (428-429), `ConfiguracaoEmpresa.imposto_pct_padrao=8/lucro_pct_padrao=10` (3620), `Proposta.percentual_nota_fiscal=13.5` (2930), `Orcamento`/`OrcamentoItem` (6182+).
