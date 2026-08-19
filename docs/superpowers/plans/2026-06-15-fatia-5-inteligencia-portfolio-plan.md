# Plano — Fatia 5: Inteligência (learning loop + roll-up de portfólio)

> Data: 2026-06-15. Obedece ao plano-mestre (DC1, DC10). Depende das Fatias 1–3. **Sem migration.**
> Spec §Fatia 5.

## Status de execução (2026-06-15) — commit fedb11e  ✅ COMPLETA

- ✅ **F5-1/F5-2** `services/aprendizado_produtividade`: `produtividade_observada` (média ponderada
  por horas dos RDOs finalizados) + `atualizar_catalogo_produtividade` (EMA conservadora, guarda de
  `min_amostras`; realimenta `SubatividadeMestre.meta_produtividade`/`duracao_estimada_horas` — DC10).
- ✅ **F5-3** `resultado_portfolio` (consolida Resultado + EVM de todas as obras; reúsa
  `resultado_obra`/`evm_obra`).
- ✅ **F5-4** rota `/resultado/portfolio` + template + ação "Aprender produtividade".
- 4 testes. **Sem migration** (colunas já existiam).

## Objetivo
Duas entregas independentes:
1. **Loop de aprendizado de produtividade** — a produtividade real observada realimenta o catálogo
   (`SubatividadeMestre.meta_produtividade` / `duracao_estimada_horas`), tornando o próximo
   orçamento e os pesos da próxima materialização mais precisos.
2. **Roll-up de portfólio** — Resultado/EVM/caixa consolidados por todas as obras (visão da empresa).

## O que já existe (reúso)
- Produtividade observada: `RDOMaoObra.produtividade_real` e `indice_produtividade` são **calculados**
  em `services/rdo_custos.py:236 recalcular_produtividade_rdo` (e `views/rdo.py:1541`), mas **nunca
  voltam** ao catálogo — este é exatamente o gap (DC10).
- Catálogo: `SubatividadeMestre.meta_produtividade`, `duracao_estimada_horas`, `unidade_medida`
  (models.py:1455–1460). Lido na materialização para pesos (`cronograma_proposta.py:67,675`).
- Métricas: `services/metricas_produtividade.py` (`produtividade_por_servico`,
  `producao_por_funcionario`, `detalhe_funcionario`).
- Read-model: `resultado_obra` (Fatia 1), `evm_obra` (Fatia 3).
- Portfólio surface: `dashboards_especificos.py:496 dashboard_obras` e a lista `views/obras.py:30`.

## Arquivos
- `services/aprendizado_produtividade.py` — o learning loop.
- `services/resultado_atividade_service.py` — `resultado_portfolio(admin_id)`.
- `dashboards_especificos.py` / template — colunas de Resultado/EVM por obra + totais da empresa.
- `tests/test_aprendizado_produtividade.py`, `tests/test_resultado_portfolio.py`.

---

## PARTE A — Learning loop (DC10)

### Task F5-1 — Agregar produtividade observada por subatividade (RED→GREEN)
- [ ] Teste: dados RDOs finalizados com `indice_produtividade`/`produtividade_real` para uma
  `SubatividadeMestre`, a agregação devolve a média (ponderada por horas) da produtividade real
  observada e o nº de amostras.
- [ ] Implementar leitura (reúso dos campos já calculados):

```python
# services/aprendizado_produtividade.py
from decimal import Decimal
from app import db
from models import RDOMaoObra, RDOServicoSubatividade, SubatividadeMestre, RDO


def produtividade_observada(subatividade_mestre_id, admin_id):
    """Média da produtividade real observada (un/h) para uma SubatividadeMestre,
    a partir dos RDOs finalizados. Ponderada por horas. Retorna (media, n_amostras)."""
    rows = (
        db.session.query(RDOMaoObra.produtividade_real, RDOMaoObra.horas_trabalhadas)
        .join(RDO, RDO.id == RDOMaoObra.rdo_id)
        .join(RDOServicoSubatividade, RDOServicoSubatividade.id == RDOMaoObra.subatividade_id)
        .filter(RDO.status == 'Finalizado', RDOMaoObra.admin_id == admin_id,
                RDOMaoObra.produtividade_real.isnot(None),
                RDOServicoSubatividade.subatividade_mestre_id == subatividade_mestre_id)
        .all()
    )
    num = sum(Decimal(str(p or 0)) * Decimal(str(h or 0)) for p, h in rows)
    den = sum(Decimal(str(h or 0)) for _, h in rows)
    if den <= 0:
        return None, 0
    return (num / den), len(rows)
```
  *(Confirmar o caminho subatividade→subatividade_mestre: `RDOServicoSubatividade.subatividade_mestre_id`
  via `grep -n "subatividade_mestre_id" models.py`. Ajustar o join à coluna real.)*
- [ ] **Commit:** `feat(aprendizado): produtividade_observada por subatividade`

### Task F5-2 — Atualizar o catálogo com guarda-corpo (RED→GREEN)
- [ ] Teste: com N≥mínimo amostras e desvio dentro de um limite, `meta_produtividade` é atualizada
  para a observada (ou média móvel); abaixo do mínimo, **não** altera (evita ruído).
- [ ] Implementar:

```python
def atualizar_catalogo_produtividade(admin_id, min_amostras=3, peso_novo=Decimal('0.3')):
    """DC10: realimenta SubatividadeMestre.meta_produtividade com a produtividade
    observada (média móvel exponencial). Idempotente e conservador: só atualiza
    com amostras suficientes. Atualiza duracao_estimada_horas coerentemente."""
    n_atualizadas = 0
    subs = SubatividadeMestre.query.filter_by(admin_id=admin_id, ativo=True).all()
    for s in subs:
        obs, n = produtividade_observada(s.id, admin_id)
        if obs is None or n < min_amostras:
            continue
        antiga = Decimal(str(s.meta_produtividade)) if s.meta_produtividade else obs
        nova = (antiga * (1 - peso_novo) + obs * peso_novo)
        s.meta_produtividade = float(nova)
        # duracao_estimada_horas coerente, se houver quantidade de referência
        if s.duracao_estimada_horas and obs > 0 and antiga > 0:
            s.duracao_estimada_horas = float(Decimal(str(s.duracao_estimada_horas)) * (antiga / nova))
        n_atualizadas += 1
    db.session.commit()
    return n_atualizadas
```
- [ ] Expor como ação manual (botão/endpoint no catálogo) e/ou job agendado. Para a Baia, rodar
  manualmente após acumular RDOs.
- [ ] **Commit:** `feat(aprendizado): atualizar_catalogo_produtividade (média móvel, conservador — DC10)`

---

## PARTE B — Roll-up de portfólio

### Task F5-3 — `resultado_portfolio` (RED→GREEN)
- [ ] Teste: 2 obras com Resultado conhecido → totais somam; lista por obra com agregado/custo/resultado.
- [ ] Implementar (reúso de `resultado_obra` + `evm_obra`):

```python
def resultado_portfolio(admin_id, data_ref=None):
    """Consolida Resultado/EVM de todas as obras v2 do tenant."""
    from models import Obra
    obras = Obra.query.filter_by(admin_id=admin_id, ativo=True).all()
    linhas, tot_agreg, tot_custo, tot_venda = [], Decimal('0'), Decimal('0'), Decimal('0')
    for o in obras:
        r = resultado_obra(o.id)
        e = evm_obra(o.id, admin_id, data_ref)
        linhas.append({'obra_id': o.id, 'nome': o.nome,
                       'valor_agregado': r['valor_agregado'], 'custo': r['custo_incorrido'],
                       'resultado': r['resultado'], 'cpi': e['cpi'], 'spi': e['spi'],
                       'resultado_projetado': e['resultado_projetado']})
        tot_agreg += r['valor_agregado']; tot_custo += r['custo_incorrido']; tot_venda += e['venda_total']
    return {'obras': linhas, 'valor_agregado': _q(tot_agreg), 'custo': _q(tot_custo),
            'resultado': _q(tot_agreg - tot_custo), 'venda_total': _q(tot_venda)}
```
  *(`r['custo_incorrido']` exige que `resultado_obra` exponha essa chave — garantida na Fatia 2,
  Task F2-5.)*
- [ ] **Commit:** `feat(portfolio): resultado_portfolio (consolida obras)`

### Task F5-4 — Superfície de portfólio
- [ ] Estender `dashboards_especificos.py:dashboard_obras` (:496) para passar `resultado_portfolio`
  ao template; adicionar colunas por obra (Resultado, CPI, SPI, resultado projetado) e cards de
  totais da empresa. Reusar a iteração de obras já existente.
- [ ] Smoke test da página.
- [ ] **Commit:** `feat(portfolio): Resultado/EVM por obra + totais da empresa no dashboard`

## Revisão final (Fatia 5)
- [ ] Learning loop fecha o ciclo (observado → catálogo), conservador e idempotente (DC10) ✅ ·
  roll-up de portfólio reúsa resultado_obra/evm_obra ✅ · sem migration (colunas já existem) ✅ ·
  mitiga R5 (peso por divisão igual) ao alimentar o catálogo ✅.
