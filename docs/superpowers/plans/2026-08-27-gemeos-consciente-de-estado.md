# Os gêmeos saem da projeção só quando a outra perna entra (D2, saída a)

> **Estado em 2026-08-27:** ✅ **FECHADA 27/08.** Commits `5be4a5bd`+`0d244e48`. É a
> Task 3.6 da spec, destravada pela decisão **D2 (26/08)** registrada em
> `docs/superpowers/plans/2026-08-25-fecho-dos-114-achados.md`. Executou na lane B
> da Onda 3 (mesmo arquivo da Task 6), depois dela e em commit separado. Efeito
> visível: `saldo_final_projetado` **piora** para todo tenant com gêmeo de
> reembolso em aberto — é o ponto da correção, registrado em
> `docs/deploy-checklist-easypanel.md`, seção 9.

**Goal:** `financeiro_service.py:619` exclui os "gêmeos" de reembolso de
`saidas_previstas`, mas `ContaPagar` **nunca** alimenta essa soma — a obrigação
não muda de lado: **evapora**. Um pedido de R$ 100k pendente projeta saída zero.
O comentário do próprio código mede a exposição: *"580 gêmeos, R$ 490.950, 24%
do valor aberto"*. A correção decidida (D2, saída **a**): **a exclusão vira
consciente de estado** — o gêmeo sai de `saidas_previstas` somente quando a
outra perna do par realmente entra na projeção; enquanto ela não entrar, a
obrigação continua projetada.

**Spec:** `docs/superpowers/plans/2026-08-25-fecho-dos-114-achados.md` (D2 e
Task 3.6) — evidência em `docs/auditoria/achados-code-review-2026-08-25.md`.

## Global Constraints

- ⚠️ **A alteração de `tests/test_b5_fluxo_gemeos_e_orfaos.py:100` está
  autorizada pela D2** — é o teste verde que afirma o defeito como intencional.
  O commit **deve citar a decisão D2 de 26/08**. Nenhum outro teste verde muda.
- TDD: RED primeiro, citado no commit.
- Nenhuma migration.
- A mudança é localizada na exclusão dos gêmeos (`_gemeos_reembolso` /
  `financeiro_service.py:619` e vizinhança). Não mexer no fluxo de caixa além
  disso — a saída (b), que faria `ContaPagar` alimentar `saidas_previstas`, foi
  **rejeitada** na D2.

### Task 1: A exclusão vira consciente de estado

**Files:**
- Modify: `financeiro_service.py` (região de `:619`, subquery `_gemeos_reembolso`)
- Modify: `tests/test_b5_fluxo_gemeos_e_orfaos.py:100` (autorizado pela D2)
- Test: `tests/test_onda3_financeiro.py` (acrescentar — arquivo da lane B)

- [ ] **Step 1 — RED:** teste provando que um par gêmeo cujo lado `ContaPagar`
  está **pendente** (a outra perna ainda não entra em projeção nenhuma)
  **continua** contando em `saidas_previstas`. Hoje ele evapora — o teste nasce
  vermelho. Escopar tudo por `admin_id` do tenant do teste (arreio
  `tests/helpers_tenant.py`).
- [ ] **Step 2 — implementação:** a exclusão do gêmeo passa a ser condicionada
  ao estado do par — leia o código para determinar o marcador de estado real
  (situação da `ContaPagar` gêmea / status de baixa). A pergunta que o código
  responde: *"a outra perna deste par já entra na projeção?"* Se não, o gêmeo
  fica.
- [ ] **Step 3 —** ajustar `tests/test_b5_fluxo_gemeos_e_orfaos.py:100` para
  afirmar o comportamento novo, citando a D2 em comentário no próprio teste.
- [ ] **Step 4 — verde:** `python -m pytest tests/test_b5_fluxo_gemeos_e_orfaos.py tests/test_onda3_financeiro.py -v`
- [ ] **Step 5 — commit** citando: RED, a decisão D2 de 26/08 (plano-mãe), e que
  a mudança de teste verde está autorizada por ela. Mencionar o efeito visível:
  `saldo_final_projetado` piora — que é o ponto.
