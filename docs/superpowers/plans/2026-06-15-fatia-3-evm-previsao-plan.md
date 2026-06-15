# Plano — Fatia 3: Motor de previsão (EVM)

> Data: 2026-06-15. Obedece ao plano-mestre (DC1, DC7). Depende da Fatia 2 (custo incorrido completo).
> **Sem migration.** Spec §Fatia 3.

## Objetivo
Resultado **projetado** no fechamento, por atividade e obra: CPI, SPI, EAC e margem projetada, com a
alavanca ("faltam +N un/HH ou realocar equipe"). É **puro cálculo sobre o read-model** das Fatias 1–2
e sobre o baseline de cronograma que já existe — **não há motor novo** (DC7).

## O que já existe (reúso — DC7)
- **CPI (R$)** já é o `alarme_custo` da Fatia 2: `EV/AC = orcado_para_avanço / real`.
- **SPI** já vem de `utils/cronograma_engine.calcular_progresso_rdo(tarefa_id, data, admin_id)`
  (retorna `percentual_planejado` e `percentual_realizado`) e
  `calcular_progresso_geral_obra_v2(obra_id, data_ref, admin_id)` (obra).
- **Curva-S** planejado×realizado já é servida por `views/obras.py:2312 curva_avanco_obra`.
- **BAC** (custo orçado total) = `custo_orcado_atividade_por_tipos(tarefa, None)` (Fatia 2).
- **Venda total da atividade** = agregado a 100% (helper `venda_total_atividade`, Task F3-1).

## Arquivos
- `services/resultado_atividade_service.py` — `venda_total_atividade`, `evm_atividade`, `evm_obra`.
- `templates/resultado/por_atividade.html` — colunas EAC / CPI / SPI / resultado projetado.
- `tests/test_evm.py`.

---

### Task F3-1 — `venda_total_atividade` (RED→GREEN)
- [ ] Teste: tarefa 100% do item com `valor_comercial=1000`, peso 100 → `venda_total_atividade == 1000`.
- [ ] Implementar (o agregado quando perc=100, reúso da cadeia de peso/D6):

```python
def venda_total_atividade(tarefa):
    """Venda (valor_comercial) alocada à atividade pelo peso da medição (D6),
    independente do avanço — é o BAC de receita da atividade."""
    total = Decimal('0')
    for link in _links_da_tarefa(tarefa):
        item = db.session.get(ItemMedicaoComercial, link.item_medicao_id)
        if not item:
            continue
        soma_peso = _soma_peso_item(item.id)
        if soma_peso <= 0:
            continue
        total += (_D(link.peso) / soma_peso) * _D(item.valor_comercial)
    return _q(total)
```
- [ ] **Commit:** `feat(evm): venda_total_atividade (BAC de receita)`

### Task F3-2 — `evm_atividade` (CPI/SPI/EAC/resultado projetado) (RED→GREEN)
- [ ] Teste: com avanço 50%, BAC custo 1000, AC 700 → CPI=0.714; planejado X realizado → SPI; EAC=BAC/CPI; resultado projetado = venda_total − EAC.
- [ ] Implementar (puro sobre o read-model + cronograma_engine):

```python
def evm_atividade(tarefa, admin_id, data_ref=None):
    """Earned Value por atividade. CPI=EV/AC (reusa alarme_custo); SPI via
    cronograma_engine; EAC=BAC/CPI; resultado projetado = venda − EAC."""
    from datetime import date as _date
    from utils.cronograma_engine import calcular_progresso_rdo
    data_ref = data_ref or _date.today()

    a = alarme_custo(tarefa)                      # EV=orcado_para_avanço, AC=real
    bac_custo = a['orcado_total']                 # custo orçado total
    ev = a['orcado_para_avanco']
    ac = a['real']
    cpi = a['indice_rs']                          # = EV/AC (None se AC=0)

    prog = calcular_progresso_rdo(tarefa.id, data_ref, admin_id)
    plan = _D(prog.get('percentual_planejado'))
    real = _D(prog.get('percentual_realizado'))
    spi = (real / plan).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP) if plan > 0 else None

    eac = (bac_custo / cpi).quantize(CENTAVO, rounding=ROUND_HALF_UP) if (cpi and cpi > 0) else None
    venda = venda_total_atividade(tarefa)
    resultado_proj = _q(venda - eac) if eac is not None else None

    return {
        'bac_custo': bac_custo, 'ev': ev, 'ac': ac,
        'cpi': cpi, 'spi': spi, 'eac': eac,
        'venda_total': venda, 'resultado_projetado': resultado_proj,
        'percentual_planejado': float(plan), 'percentual_realizado': float(real),
    }
```
- [ ] **Commit:** `feat(evm): evm_atividade (CPI/SPI/EAC/resultado projetado, puro reuso — DC7)`

### Task F3-3 — `evm_obra` (rollup + SPI da obra) (RED→GREEN)
- [ ] Teste: soma BAC/EV/AC das folhas; SPI da obra de `calcular_progresso_geral_obra_v2`; EAC e resultado projetado da obra.
- [ ] Implementar:

```python
def evm_obra(obra_id, admin_id, data_ref=None):
    from datetime import date as _date
    from utils.cronograma_engine import calcular_progresso_geral_obra_v2
    data_ref = data_ref or _date.today()

    bac = ev = ac = venda = Decimal('0')
    itens = []
    for t in _folhas_da_obra(obra_id):
        e = evm_atividade(t, admin_id, data_ref)
        bac += e['bac_custo']; ev += e['ev']; ac += e['ac']; venda += e['venda_total']
        itens.append({'tarefa_id': t.id, 'nome': t.nome_tarefa, **e})

    cpi = (ev / ac).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP) if ac > 0 else None
    agg = calcular_progresso_geral_obra_v2(obra_id, data_ref, admin_id)
    plan = _D(agg.get('progresso_planejado_pct')); realz = _D(agg.get('progresso_geral_pct'))
    spi = (realz / plan).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP) if plan > 0 else None
    eac = (bac / cpi).quantize(CENTAVO, rounding=ROUND_HALF_UP) if (cpi and cpi > 0) else None
    return {
        'obra_id': obra_id, 'itens': itens,
        'bac_custo': _q(bac), 'ev': _q(ev), 'ac': _q(ac), 'venda_total': _q(venda),
        'cpi': cpi, 'spi': spi, 'eac': eac,
        'resultado_projetado': _q(venda - eac) if eac is not None else None,
    }
```
- [ ] **Commit:** `feat(evm): evm_obra (rollup + SPI da obra)`

### Task F3-4 — Alavanca (quanto falta) + UI
- [ ] Função `alavanca_atividade(tarefa, admin_id)`: dado o CPI<1, quanto de produtividade extra (un/HH)
  ou realocação fecharia a meta. Calcular a partir de `indice_horas` (Fatia 1) quando a MO é horária;
  senão, expressar em R$ (quanto de custo precisa cair). Teste + implementação.
- [ ] Tela: na `por_atividade.html`, colunas EAC, CPI, SPI, resultado projetado, com selo quando
  `resultado_projetado < 0` (vai fechar no vermelho). Opcional: aproveitar `curva_avanco_obra` para
  sobrepor a curva projetada.
- [ ] **Commit:** `feat(evm): alavanca + colunas de previsão na tela`

## Revisão final (Fatia 3)
- [ ] CPI/SPI/EAC ✅ · resultado projetado ✅ · alavanca ✅ · sem migration ✅ · reúso total de alarme_custo + cronograma_engine (DC7) ✅. Contrato do read-model só ganhou funções novas.
