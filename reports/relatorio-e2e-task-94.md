# Task #94 — Ciclo Proposta → Obra → Medido → ContaReceber (relatório de implementação)

## Escopo entregue

Refatoração do ciclo financeiro/operacional do ERP para que **a aprovação
da proposta crie apenas estrutura** (Obra + token público + IMC + OSC) e
para que **a `ContaReceber` nasça/atualize automaticamente conforme o
medido avança** (RDO finalizado ou medição quinzenal fechada). Existe
agora **uma e apenas uma** `ContaReceber` viva por obra com
`origem_tipo='OBRA_MEDICAO'`, `origem_id=obra.id` e
`numero_documento='OBR-MED-#####'`.

## Componentes alterados

| Camada | Arquivo | Função | Mudança |
| --- | --- | --- | --- |
| Aprovação admin | `propostas_consolidated.py::aprovar` | Setar `status='APROVADA'`, emitir `proposta_aprovada` e validar pós-emit que `proposta.obra_id` ficou setado |
| Aprovação cliente | `propostas_consolidated.py::aprovar_proposta_cliente` | Resolver `admin_id` via `Usuario.admin_id` (igual `portal_cliente()`) e validar pós-emit que `proposta.obra_id` ficou setado |
| Handler estrutural | `event_manager.py::propagar_proposta_para_obra` | Cria/atualiza Obra (OBR####, `token_cliente`, `portal_ativo=True`, `valor_contrato`), seta `proposta.obra_id` e `convertida_em_obra=True`. **Não cria ContaReceber** |
| Handler comercial | `handlers/propostas_handlers.py::handle_proposta_aprovada` | Lança contábil dupla (1.1.02.001 / 4.1.01.001) e propaga itens (IMC + OSC). **Removida criação de ContaReceber** e o respectivo import |
| Recálculo IMC | `services/medicao_service.py::_recalcular_imc_avanco` | Nova: recalcula `percentual_executado_acumulado`/`valor_executado_acumulado` por IMC via cronograma ponderado (`ItemMedicaoCronogramaTarefa`) com fallback por `servico_id` em `RDOServicoSubatividade` (RDOs finalizados da obra) |
| UPSERT CR | `services/medicao_service.py::recalcular_medicao_obra` | Nova: roda `_recalcular_imc_avanco`, faz UPSERT da CR única com `valor_original = valor_medido`, `saldo = max(0, valor_medido - valor_recebido)`, `data_vencimento = hoje + (proposta.prazo_entrega_dias or 30)`, status `PENDENTE`/`PARCIAL`/`QUITADA`. Retorna dict `{valor_medido, valor_recebido, valor_a_receber, conta_receber_id}` |
| Medição quinzenal | `services/medicao_service.py::gerar_medicao_quinzenal` / `fechar_medicao` | Removida criação de `ContaReceber MED-`; ambos chamam `recalcular_medicao_obra` e gravam `medicao.conta_receber_id` a partir do dict |
| RDO → CR | `event_manager.py::recalcular_medicao_apos_rdo` | Novo handler do evento `rdo_finalizado` (irmão de `lancar_custos_rdo`) que chama `recalcular_medicao_obra` |
| Tolerância NULL | `financeiro_views.py`, `financeiro_service.py` | Helpers `_saldo_seguro/_saldo_seguro_cr`, `func.coalesce(saldo, valor_original)` nas agregadas e fallback no detalhamento do fluxo de caixa |

## Fluxo final

1. Operador (ou cliente via portal) aprova a proposta.
2. `propagar_proposta_para_obra` cria/recupera a Obra, gera `token_cliente`,
   marca `portal_ativo=True`, vincula `proposta.obra_id`/`convertida_em_obra`.
3. `handle_proposta_aprovada` lança contábil dupla e propaga itens
   (`PropostaItem → ItemMedicaoComercial`); listener `after_insert` em
   `ItemMedicaoComercial` cria o `ObraServicoCusto` pareado.
4. Conforme RDOs avançam, `recalcular_medicao_apos_rdo` recalcula IMC e
   atualiza a única `ContaReceber OBRA_MEDICAO` da obra.
5. Ao gerar/fechar a medição quinzenal, o mesmo `recalcular_medicao_obra`
   é executado, mantendo a CR sempre alinhada ao medido acumulado.
6. Recebimentos parciais reduzem `saldo`; `status` flui automaticamente
   para `PARCIAL` e, ao zerar saldo, para `QUITADA`.

## Validações

- Boot do gunicorn limpo (`HTTP 200` em `/login`).
- `python tests/test_agrupamento_diarias_rdo.py`: 23/23 PASS.
- Eventos confirmados na inicialização: `propagar_proposta_para_obra`,
  `handle_proposta_aprovada`, `lancar_custos_rdo`,
  `recalcular_medicao_apos_rdo`.

## Itens deixados como follow-up (não bloqueantes)

- Sub #9: indicador "Medido / Recebido / A receber" no painel da obra
  consumindo o dict retornado por `recalcular_medicao_obra`.
- Sub #11: bateria runTest e2e dos 5 cenários (aprovar admin, aprovar
  portal, RDO+CR, fechamento de medição, recebimento parcial).
