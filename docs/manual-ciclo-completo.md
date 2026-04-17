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

## E2E backend determinístico do ciclo (`tests/test_ciclo_proposta_obra_medido_cr.py`)

Bateria executada após o refator: **30 PASS / 0 FAIL**. Roda em
`python tests/test_ciclo_proposta_obra_medido_cr.py` e cobre as 5
fases do ciclo financeiro novo:

1. **Aprovação cria estrutura, não dinheiro**: emite `proposta_aprovada`
   e valida que Obra (`OBRxxxx`), `token_cliente`, `portal_ativo`,
   `valor_contrato`, `proposta.obra_id` e o `ItemMedicaoComercial` da
   proposta foram criados — e que **nenhuma** `ContaReceber OBRA_MEDICAO`
   apareceu nesse momento.
2. **Avanço 50% via cronograma**: cria `TarefaCronograma` com
   `percentual_concluido=50` ligada ao IMC (peso 100). Chama
   `recalcular_medicao_obra` e valida que a CR `OBR-MED-#####` nasceu
   com `valor_original=R$ 500`, `saldo=R$ 500`, `status='PENDENTE'` e o
   payload retornado contém `valor_medido=500` / `valor_a_receber=500`.
3. **Avanço 100% (UPSERT)**: tarefa vai para 100%, `recalcular_medicao_obra`
   é chamado de novo e a função atualiza a **mesma** CR (id idêntico)
   para `valor_original=R$ 1.000`/`saldo=R$ 1.000`. Continua com **uma
   única** linha `OBR-MED-#####` para a obra (UPSERT, não duplica).
4. **Recebimento parcial → PARCIAL**: setando `valor_recebido=R$ 300`,
   o recálculo aplica `saldo=R$ 700` e `status='PARCIAL'`.
5. **Recebimento total → QUITADA**: com `valor_recebido=R$ 1.000`, o
   recálculo zera o saldo e marca `status='QUITADA'`. A obra continua
   com exatamente uma CR `OBR-MED-#####`.

> **Resultado real do último run**: obra `OBR0005` (id=398), CR
> `OBR-MED-00398` evoluiu PENDENTE@500 → PENDENTE@1000 → PARCIAL@700 →
> QUITADA@0 sem nunca duplicar.

## E2E Orçamento + Proposta (`tests/test_e2e_orcamento_proposta.py`)

Bateria nova introduzida pela Task #95: **35 PASS / 0 FAIL**. Roda em
`python tests/test_e2e_orcamento_proposta.py` e cobre o ciclo do
catálogo paramétrico até a aprovação da proposta — pega o trecho que o
ciclo Proposta→CR (acima) **não** cobre, porque aquele só começa
depois da aprovação.

1. **Setup catálogo paramétrico** — cria `Insumo` (mão de obra +
   material), `PrecoBaseInsumo`, `Servico` (8% imposto + 12% lucro) e
   duas `ComposicaoServico`. Valida `custo_unitario=R$ 90,00` e
   `preco_venda=R$ 112,50`. Quando `imposto+lucro ≥ 100%`, o cálculo
   sinaliza `erro` e zera o preço (proteção contra divisão por zero).
2. **Proposta rascunho com explosão de insumos** — chama
   `explodir_servico_para_quantidade(svc, 10)` e grava o `PropostaItem`
   com `servico_id`, `quantidade_medida=10`, `custo_unitario=90.0000`,
   `lucro_unitario=22.5000` e `subtotal=R$ 1.125,00`.
3. **Recálculo do Servico** — `recalcular_servico_preco(svc)` persiste
   `Servico.preco_venda_unitario`; o `PropostaItem` antigo **não** é
   alterado.
4. **Snapshot imutável** — encerra os `PrecoBaseInsumo` antigos (com
   `vigencia_fim`), insere preços novos vigentes, recalcula o serviço
   (custo sobe para R$ 180 / preço para R$ 225) e confirma que o
   `PropostaItem` original mantém custo R$ 90 / subtotal R$ 1.125. É a
   regra de negócio do orçamento paramétrico: o que valeu na hora da
   proposta vira foto.
5. **Transição rascunho → enviada + portal** — muda o status da
   proposta para `enviada`, popula `data_envio` e valida que
   `GET /propostas/cliente/<token>` responde **200**. Token inválido
   não resolve para nenhuma `Proposta`.
6. **Aprovação portal cliente + isolamento multi-tenant** —
   `POST /propostas/cliente/<token>/aprovar` retorna 302; o status vira
   `APROVADA`, `convertida_em_obra=True`, `obra_id` populado, a `Obra`
   nasce com `OBRxxxx` e `token_cliente`, o `ItemMedicaoComercial` é
   propagado 1:1 herdando o `servico_id` do catálogo. Outro `admin_id`
   consultando a mesma proposta recebe `None` — sem leak entre tenants.

> **Resultado real do último run**: proposta `P-E2E95-…`, `Servico`
> id=360, `Obra` id=404 com código `OBR0007`. Snapshot do `PropostaItem`
> resistiu à mudança de preço do insumo (`custo=R$ 90,00` enquanto o
> `Servico` foi para `R$ 225,00`).

### Bug regressivo descoberto e corrigido pelo teste

O e2e UI inicial expôs uma `IntegrityError` em
`uq_obra_codigo_admin_id`: o gerador de `codigo` em
`event_manager.propagar_proposta_para_obra` usava
`func.max(Obra.codigo)` sem filtrar pelo padrão `OBR%`. Quando o admin
tinha alguma `Obra` com `codigo` NULL/vazio, o `max` não retornava
nenhum `OBR####`, o gerador caía em `numero=1` e tentava inserir
`OBR0001` — colidindo com um registro pré-existente. Corrigido
filtrando `Obra.codigo.like('OBR%')` e iterando até encontrar um
código livre. Após a correção, o e2e backend acima passa 30/30.

## Solução de problemas comuns

| Sintoma | Causa provável | Ação |
| --- | --- | --- |
| Aprovou proposta e não vê obra | Handler falhou — flash de warning surgiu | Verificar logs (`propagar_proposta_para_obra`); reaprovar |
| `ContaReceber` da obra com valor desatualizado | RDO não chegou a `Finalizado` ou IMC sem cronograma/serviço | Conferir status do RDO e vínculos no cronograma; chamar `recalcular_medicao_obra` manualmente |
| `data_vencimento` "errada" | Proposta sem `prazo_entrega_dias` | Sistema cai no default de 30 dias |
| Status ainda `PARCIAL` após receber tudo | `saldo` ficou positivo por arredondamento | `recalcular_medicao_obra` ajusta no próximo gatilho; status vira `QUITADA` |
