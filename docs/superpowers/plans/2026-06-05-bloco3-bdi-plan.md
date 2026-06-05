# Plano de Implementação — Bloco 3: BDI completo (TCU)

- **Data:** 2026-06-05
- **Spec de origem:** `docs/superpowers/specs/2026-06-05-bloco3-bdi-design.md`
- **ADR:** `docs/adr/0001-bdi-por-dentro-padrao-tcu.md` (accepted)
- **Branch:** `fix/bloco3-bdi`. Push/merge/deploy só sob autorização explícita.

## Princípios

1. **Teste primeiro.** P0 cria os testes de tabela da fórmula/guarda-corpo (falham agora — `pricing.py` não existe) e o **teste de não-disrupção** (com BDI=0 o preço é idêntico ao de hoje). Verde no fim do bloco = "pronto".
2. **Commits minúsculos**, isolados e reversíveis. Fundação (helper) antes de aplicação (delegação/UI).
3. **Helper isolado.** Toda a fórmula e o guarda-corpo vivem em `services/pricing.py` — uma unidade testável sozinha. As 3 funções de cálculo delegam; nada de fórmula duplicada.
4. **Não-disrupção.** Migração com default 0/NULL; snapshots de proposta nunca recalculados; Task #115 (não-vazamento ao cliente) segue verde.

## Decisões de design (do spec — confirmadas)

- BDI único por empresa, override opcional por proposta.
- Cascata: BDI = `proposta → empresa → 0`; T/L = `serviço → empresa → 0`.
- Guarda-corpo: aviso em `bdi_tl_aviso_pct` (60), bloqueio em `bdi_tl_bloqueio_pct` (90), configuráveis.
- Exibição: split completo só em telas internas.

---

## Fase F — Fundação (helper + schema)

### P0 — Testes (RED)
- **Arquivo novo:** `tests/test_bdi_pricing.py`.
- Tabela de `pricing.precificar(custo, aliquotas)`:
  - BDI=0, T=L=0 → preço = custo (e == cálculo atual).
  - Exemplo TCU conhecido (valores calculados à mão no teste).
  - Invariante `custo_direto + indiretos + tributos + lucro == preco`.
  - **D2:** `lucro == L × preco` (não `preco − custo`).
  - **D3:** faixas `ok` / `aviso` / `bloqueio` nos limiares default e custom; bloqueio → `preco=0`, `status='bloqueio'`.
- **Estado agora:** VERMELHO (`pricing.py` não existe).
- **Verificação:** `pytest tests/test_bdi_pricing.py` → ImportError/falhas.
- Commit do teste falhando.

### P1 — `services/pricing.py`: `precificar()` (fórmula + guarda-corpo)
- Value-objects (dataclasses) `Aliquotas(t,l,ac,s,r,g,df, tl_aviso, tl_bloqueio)` e `Precificacao(...)`.
- `precificar(custo, aliquotas)` aplica a fórmula do spec + guarda-corpo; tudo em `Decimal`.
- **Verificação:** as partes de `precificar` do P0 ficam verdes (resolução de alíquotas ainda não).
- Commit isolado.

### P2 — Migração: colunas de BDI (empresa + proposta)
- Nova migração numerada (próximo livre, idempotente): `ADD COLUMN IF NOT EXISTS` em `configuracao_empresa` (5 BDI default 0 + `bdi_tl_aviso_pct` default 60 + `bdi_tl_bloqueio_pct` default 90) e em `propostas_comerciais` (5 BDI nullable).
- Campos correspondentes nos models `ConfiguracaoEmpresa` e `Proposta`.
- **Verificação:** boot aplica a migração (success no `migration_history`); `pré-flight` limpo; colunas existem; linhas antigas com BDI=0/NULL.
- Commit isolado.

### P3 — `pricing.resolver_aliquotas(servico, proposta=None)`
- Cascata: `T,L` por `serviço → empresa → 0`; `AC..DF` por `proposta → empresa → 0`; limiares da empresa.
- **Verificação:** teste de cascata (override de proposta > empresa > 0) verde.
- Commit isolado.

---

## Fase A — Aplicação (delegação, guarda-corpo, UI) — depende de F

### P4 — Delegar as 3 funções de `orcamento_service.py` ao helper
- `calcular_precos_servico`, `calcular_precos_servico_por_quantidade`, `explodir_servico_para_quantidade`: montam `custo_total` como hoje e chamam `resolver_aliquotas` + `precificar`.
- Remover a lógica de cascata duplicada e o `divisor = 1 − T − L` local.
- Corrigir **D2**: `lucro_unitario`/`lucro_total` vêm de `L × preço` (não `preço − custo`).
- Dicts de retorno ganham `custo_direto, indiretos, indiretos_componentes, tributos, lucro, status, mensagem` (mantendo chaves antigas para back-compat).
- **Verificação:** teste de não-disrupção (BDI=0 → preço idêntico ao snapshot atual) verde; suíte de orçamento existente sem regressão.
- Commit isolado.

### P5 — Guarda-corpo nas camadas de escrita
- `recalcular_servico_preco(persistir=True)` e a materialização de item de proposta **não gravam** preço quando `status='bloqueio'`; propagam a mensagem.
- **Verificação:** teste — serviço com `T+L ≥ bloqueio` não persiste preço; com `aviso` persiste e sinaliza.
- Commit isolado.

### P6 — UI de entrada (forms)
- Config da empresa: 5 campos de BDI + 2 limiares (validação `≥ 0`).
- Proposta: seção opcional "BDI desta proposta" (5 campos; vazio = herda).
- **Verificação:** salvar/editar persiste; vazio na proposta herda a empresa.
- Commit isolado.

### P7 — Exibição do split (telas internas)
- Detalhe de orçamento / visão interna da proposta exibem Custo + Indiretos (com os 5 componentes) + Tributos + Lucro = Preço, mais o `aviso` quando houver.
- **Verificação:** render mostra as parcelas; `tests/test_proposta_no_leak.py` (Task #115) **verde** (cliente não vê custo/indiretos).
- Commit isolado.

### P8 — Fechar o bloco
- `pytest tests/test_bdi_pricing.py` + suíte de orçamento + Playwright e2e → sem regressão; testes do bloco todos verdes.
- Commit final.

---

## Sequência de commits (resumo)

```
P0  test(orcamento): tabela do BDI/guarda-corpo (RED)
P1  feat(pricing): precificar() — fórmula BDI + guarda-corpo
P2  feat(schema): colunas de BDI (empresa + proposta) + migração
P3  feat(pricing): resolver_aliquotas() (cascata)
P4  refactor(orcamento): 3 funções delegam ao pricing; corrige lucro=L×preço (D2)
P5  fix(orcamento): guarda-corpo bloqueia persistência (D3)
P6  feat(ui): campos de BDI na empresa e override na proposta
P7  feat(ui): split de preço nas telas internas (Task #115 verde)
P8  test(orcamento): suíte do BDI verde + regressão geral
```

## Riscos e mitigação

| Risco | Mitigação |
|-------|-----------|
| Mudança de preço inesperada no catálogo | BDI default 0 → fórmula reduz ao atual; teste de não-disrupção trava isso |
| Snapshot de proposta antigo recalculado | nenhuma rota recalcula snapshots; sem backfill de preço na migração |
| Vazamento de indiretos/custo ao cliente | split só em template interno; Task #115 guard test |
| Guarda-corpo quebra fluxo legítimo | limiares configuráveis; `aviso` não bloqueia; só `bloqueio` impede gravar |
| Fórmula divergir entre as 3 funções | toda a fórmula no helper; as 3 delegam |

## Gate de deploy (sob autorização)
- Pré-flight de migração (`scripts/preflight_migracao.py`) verde em produção.
- Merge → redeploy → conferir a nova migração como `success` → smoke test do orçamento.
