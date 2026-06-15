# Plano — Fatia 4: Lente de caixa (Realizado/Previsto por obra)

> Data: 2026-06-15. Obedece ao plano-mestre (DC4 — competência ≠ caixa; ADR 0003). Depende da
> Fatia 2 (custos completos viram ContaPagar; medição vira ContaReceber). **Sem migration.**
> Spec §Fatia 4.

## Objetivo
Mostrar, **por obra**, quando ela fica no vermelho de **caixa** (não de competência): curva de
**Realizado/Previsto** no tempo — Valor agregado → medição → `ContaReceber` vs Custo → `ContaPagar`.
Lente **distinta** do Resultado (competência), nunca fundida (DC4).

## Regra (ADR 0003)
A série de caixa **parte de 0** e mostra a **variação acumulada** (só Realizados); **Realizado e
Previsto nunca são somados**. Esta regra já está implementada no agregador existente — só reusamos.

## O que já existe (reúso integral)
- `FinanceiroService.calcular_fluxo_caixa(admin_id, data_inicio, data_fim, obra_id=None)`
  (financeiro_service.py:430) — já aceita **filtro por obra**; retorna `detalhes` com flag `realizado`.
- `FinanceiroService.agregar_fluxo_mensal(detalhes, saldo_inicial)` (financeiro_service.py:682) —
  função **pura**: meses, KPIs, `serie_chart` (var_acum_real / var_acum_proj), variação a partir de 0.
- Dados já alimentados pelas fatias anteriores:
  - Receita: `ContaReceber` única por obra (`origem_tipo='OBRA_MEDICAO'`, criada em
    `medicao_service.recalcular_medicao_obra:275`).
  - Custos: `ContaPagar` (alimentação `event_manager:1236`, compras `compras_views:236`, etc.) +
    `GestaoCustoPai` (previsto) + `FluxoCaixa` (realizado).
- View base e filtro de período: `financeiro_views.py:677 fluxo_caixa` (default mês corrente,
  `?data_inicio&data_fim&obra_id`).

## Arquivos
- `resultado_views.py` — nova rota `/obras/<id>/caixa` (aba "Caixa da obra") que chama o
  `FinanceiroService` já existente filtrado pela obra.
- `templates/resultado/caixa_obra.html` — gráfico Realizado/Previsto (mesma estrutura do
  `financeiro/fluxo_caixa.html`).
- `tests/test_caixa_obra.py`.

---

### Task F4-1 — Wrapper fino `fluxo_caixa_obra` (RED→GREEN)
- [ ] Teste: para uma obra com 1 ContaReceber recebida e 1 ContaPagar paga, a série começa em 0 e a
  variação acumulada bate; Previsto fica separado do Realizado (ADR 0003).
- [ ] Implementar (delegação pura — não reimplementar caixa):

```python
# em services/resultado_atividade_service.py (ou um caixa_service.py)
def fluxo_caixa_obra(admin_id, obra_id, data_inicio, data_fim):
    """Lente de caixa de UMA obra (DC4). Reúso integral do FinanceiroService;
    não funde com a lente de competência."""
    from financeiro_service import FinanceiroService
    fluxo = FinanceiroService.calcular_fluxo_caixa(
        admin_id, data_inicio, data_fim, obra_id=obra_id
    )
    agg = FinanceiroService.agregar_fluxo_mensal(fluxo['detalhes'], saldo_inicial=0.0)
    return {'fluxo': fluxo, 'meses': agg['meses'], 'kpis': agg['kpis'],
            'serie_chart': agg['serie_chart']}
```
  *(Nota: `saldo_inicial=0.0` por obra — a variação de caixa da obra parte de 0, ADR 0003; o saldo
  bancário absoluto não é por obra.)*
- [ ] **Commit:** `feat(caixa): fluxo_caixa_obra (reuso do FinanceiroService, ADR 0003)`

### Task F4-2 — Rota + template da aba "Caixa da obra"
- [ ] `resultado_views.py`: rota `/obras/<int:obra_id>/caixa` (com `_check_v2()`), default mês
  corrente, aceita `?data_inicio&data_fim` (copiar o parser de `financeiro_views.py:677`).
- [ ] `templates/resultado/caixa_obra.html`: reusar a estrutura de `financeiro/fluxo_caixa.html`
  (gráfico de barras entradas/saídas + 2 linhas: var_acum_real, var_acum_proj). Deixar **explícito**
  no título que é a **lente de caixa**, distinta do Resultado (competência) — DC4.
- [ ] Registrar a rota (já no `resultado_bp` da Fatia 1, sem novo blueprint).
- [ ] Smoke test: `GET /obras/<id>/caixa` → 200.
- [ ] **Commit:** `feat(caixa): aba Caixa da obra (Realizado/Previsto)`

### Task F4-3 — Link na obra + separação visual das lentes
- [ ] No detalhe da obra (`detalhes_obra_profissional.html`, grupo de abas ~L875), adicionar a aba
  "Caixa" ao lado de "Resultado por Atividade". Deixar claro: **Resultado = competência**,
  **Caixa = quando o dinheiro entra/sai** (DC4).
- [ ] Teste de fumaça da navegação.
- [ ] **Commit:** `feat(caixa): aba no detalhe da obra; rótulos competência×caixa`

## Revisão final (Fatia 4)
- [ ] Realizado/Previsto no tempo ✅ · parte de 0, nunca soma (ADR 0003) ✅ · por obra ✅ · lente
  distinta de competência (DC4) ✅ · sem migration ✅ · reúso integral do FinanceiroService ✅.
