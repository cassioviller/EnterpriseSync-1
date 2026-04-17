# Manual operacional — Ciclo Proposta → Obra → Medido → ContaReceber (Task #94)

Este manual descreve a regra **vigente** do ciclo comercial/financeiro do
SIGE v9.0 após a refatoração da Task #94.

## Princípio central

> **Aprovar uma proposta cria estrutura, não dinheiro a receber.**
> A `ContaReceber` da obra nasce e se atualiza **somente** conforme o
> medido avança (RDO finalizado, medição quinzenal gerada/fechada).

Existe **uma e apenas uma** `ContaReceber` viva por obra:

- `origem_tipo='OBRA_MEDICAO'`
- `origem_id = obra.id`
- `numero_documento = 'OBR-MED-#####'`
- `valor_original = valor medido acumulado da obra`
- `saldo = max(0, valor_medido - valor_recebido)`
- `status ∈ {PENDENTE, PARCIAL, QUITADA}`
- `data_vencimento = data_emissao + (proposta.prazo_entrega_dias or 30)`

## Eventos e handlers

| Evento | Handler | Responsabilidade |
| --- | --- | --- |
| `proposta_aprovada` | `event_manager.propagar_proposta_para_obra` | Cria/atualiza Obra (`OBR####`, `token_cliente`, `portal_ativo`, `valor_contrato`). Seta `proposta.obra_id` e `convertida_em_obra`. **Não cria ContaReceber.** |
| `proposta_aprovada` | `handlers.propostas_handlers.handle_proposta_aprovada` | Lança contábil dupla (1.1.02.001 / 4.1.01.001). Propaga itens via `_propagar_proposta_para_obra` (cria `ItemMedicaoComercial` por `PropostaItem` — listener `after_insert` cria `ObraServicoCusto` pareado). **Não cria ContaReceber.** |
| `rdo_finalizado` | `event_manager.lancar_custos_rdo` | Cria `GestaoCustoFilho`/`CustoObra` para a mão de obra do RDO. |
| `rdo_finalizado` | `event_manager.recalcular_medicao_apos_rdo` | Chama `services.medicao_service.recalcular_medicao_obra(obra_id, admin_id)`. |

A ordem dos handlers de `proposta_aprovada` é garantida pela ordem de
import em `app.py` (event_manager primeiro, handlers depois).

## API canônica de recálculo

```python
from services.medicao_service import recalcular_medicao_obra

resultado = recalcular_medicao_obra(obra_id, admin_id)
# resultado is None | {
#   'valor_medido': Decimal,
#   'valor_recebido': Decimal,
#   'valor_a_receber': Decimal,
#   'conta_receber_id': int
# }
```

A função:

1. Recalcula `percentual_executado_acumulado`/`valor_executado_acumulado`
   de cada `ItemMedicaoComercial` da obra a partir do estado vivo do
   cronograma (`ItemMedicaoCronogramaTarefa` ponderado) com fallback por
   `servico_id` em `RDOServicoSubatividade` (RDOs finalizados).
2. Faz UPSERT da `ContaReceber` única da obra.
3. Retorna o payload acima para alimentar painéis.

## Aprovação da proposta — fluxo

### Pelo admin (`POST /propostas/aprovar/<id>`)

1. Status passa a `APROVADA` e histórico é registrado.
2. Commit transacional.
3. Emit `proposta_aprovada`.
4. **Validação pós-emit**: refaz `db.session.refresh(proposta)` e checa
   `proposta.obra_id`. Se vazio, exibe flash de warning indicando que a
   estrutura ficou incompleta (handler falhou em algum ponto).

### Pelo cliente (`POST /propostas/cliente/<token>/aprovar`)

1. Status `APROVADA` + `data_resposta_cliente` + `observacoes_cliente`.
2. Resolução de `admin_id` igual à `portal_cliente()`:
   `usuario.admin_id or usuario.id` (via `Usuario.query.get(criado_por)`),
   com fallback para `proposta.admin_id`.
3. Mesmo `emit + refresh + warning` do fluxo admin.

## Tolerância a dados legados

- `financeiro_views.py` e `financeiro_service.py` usam helpers
  `_saldo_seguro` / `_saldo_seguro_cr` e `func.coalesce(saldo, valor_original)`
  para que `ContaReceber` antigas (`origem_tipo='PROPOSTA'`/`'MEDICAO'`)
  com `saldo NULL` não quebrem dashboards de fluxo de caixa.
- Propostas legadas com `status='aprovada'` (lowercase) continuam sendo
  lidas pelos painéis (`dashboard.py`, `resumo_custos_obra.py`); novas
  aprovações usam `'APROVADA'` (uppercase).

## Rotas relevantes (verificadas em 2026-04-17)

| Função | Método/rota |
| --- | --- |
| Login | `POST /login` (campos `email`, `password`) |
| Listagem de propostas | `GET /propostas` |
| Aprovar proposta (admin) | `POST /propostas/aprovar/<id>` |
| Aprovar proposta (cliente) | `POST /propostas/cliente/<token>/aprovar` |
| Listagem de obras | `GET /obras` |
| Detalhe de obra | `GET /obras/<id>` |
| Contas a receber | `GET /financeiro/contas-receber` *(atenção: rota é `contas-receber`, não `contas-a-receber`)* |

## Smoke test e2e (confirmado)

Cenário read-only executado pelo runner Playwright após o refator:

1. Login admin → dashboard, sem 500.
2. `/propostas` renderiza limpa.
3. `/financeiro/contas-receber` renderiza limpa, **sem TypeError de
   `saldo` NULL** (helpers `_saldo_seguro*` + `func.coalesce` ativos).
4. `/obras` renderiza limpa.
5. Detalhe da primeira obra carrega sem erro.

Resultado: **success**. Veja `reports/relatorio-e2e-task-94.md` para a
matriz completa.

## Solução de problemas comuns

| Sintoma | Causa provável | Ação |
| --- | --- | --- |
| Aprovou proposta e não vê obra | Handler falhou — flash de warning surgiu | Verificar logs (`propagar_proposta_para_obra`); reaprovar |
| `ContaReceber` da obra com valor desatualizado | RDO não chegou a `Finalizado` ou IMC sem cronograma/serviço | Conferir status do RDO e vínculos no cronograma; chamar `recalcular_medicao_obra` manualmente |
| `data_vencimento` "errada" | Proposta sem `prazo_entrega_dias` | Sistema cai no default de 30 dias |
| Status ainda `PARCIAL` após receber tudo | `saldo` ficou positivo por arredondamento | `recalcular_medicao_obra` ajusta no próximo gatilho; status vira `QUITADA` |
