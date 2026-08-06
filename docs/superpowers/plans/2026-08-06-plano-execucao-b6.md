# Plano de execução da rodada B6 — 2026-08-06 (execução autônoma autorizada)

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans`.

**O que é.** O plano de execução da rodada B6. Os recortes vivem em
`docs/superpowers/plans/2026-08-06-rodada-b6-varredura.md` e não são repetidos; quando
divergirem, o recorte vence.

**Autorização.** O Cássio autorizou em 06/08, por escrito na sessão ("eu não vou estar
na frente da tela para aprovar, já estou dando autorização"): documentar, criar o plano
e **executar sem aprovação por etapa**. As decisões D-B6.1 a D-B6.4 executam pelos
defaults do §9 da rodada — todos decidíveis com dev + código, por exigência da decisão
anterior dele (sem consultas de produção) — e ficam registradas como decisão dele por
delegação, no padrão da B5.

**As duas fronteiras da autorização** (mantidas mesmo autorizado):
1. **`main` não anda sozinha** — o fast-forward dispara o deploy; ao final, a branch
   `test/b0-arreio` sobe para o remoto e a `main` espera o Cássio.
2. **Decisão sem default executável não é chutada** — a Task para, o resto segue, o
   motivo fica escrito (precedente B1.14).

## Fases

- **F1 — sessão principal, serial** (as delicadas: migração, dinheiro, remoção):
  - [ ] F1.1 — **B6.1** estorno de recebimento (migração **281**, alocada na rodada §3)
  - [ ] F1.2 — **B6.2** família 2 + guard do migrar (serializada após B6.1: mesmos arquivos)
  - [ ] F1.3 — **B6.3** vehicles, remoção provada (P)
  - [ ] F1.4 — gate completo + revisão adversarial WF (read-only, em paralelo ao gate)
- **F2 — os cinco lotes 404 (B6.4-B6.8), por SUBAGENTES SEQUENCIAIS**:
  - Um agente por lote, um de cada vez (o banco de dev é único — paralelismo de teste
    é não-determinismo, §2 do plano da B5). Cada agente recebe o molde da B5.3 e o
    recorte do lote; implementa red-first e roda SÓ os testes do lote.
  - A sessão principal **não terceiriza a evidência**: depois de cada agente, re-roda
    os testes do lote, roda as mutações ela mesma, revisa o diff e commita. Agente não
    commita.
  - Serialização interna: B6.5 antes de B6.7 (`views/obras.py` compartilhado).
  - [ ] F2.1 B6.4 · [ ] F2.2 B6.5 · [ ] F2.3 B6.6 · [ ] F2.4 B6.7 · [ ] F2.5 B6.8
- **F3 — fecho**: gate completo final + revisão WF dos lotes + Status/checkboxes na
  rodada + FECHO da sessão + **push da branch**.

## Registro das decisões (por delegação, 06/08)

| Decisão | Executada como |
|---|---|
| **D-B6.1** | estorno e cinto **excluem** `OBRA_MEDICAO` (recusa por origem); as 24 QUITADA legadas ficam inestornáveis e registradas |
| **D-B6.2** | `apenas_pagamento` segue editável; chore de texto nomeando o risco por extenso |
| **D-B6.3** | `novo_veiculo_OLD` sai no lote de vehicles |
| **D-B6.4** | destino do 404 = `error.html`; rotas fetch ganham JSON 404 (precedente D-B5.3) |

## Histórico

- **2026-08-06, noite** — escrito e disparado em execução autônoma, logo após a
  varredura B6 (9 agentes, 8 Tasks, vereditos 4× confirmado_com_correcoes).
