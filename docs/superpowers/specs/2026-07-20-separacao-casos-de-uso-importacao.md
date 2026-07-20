# Separação de casos de uso — importação, cronograma, RDO, custos e medições

> Módulo 01 passo 8 do plano `2026-07-17-cronograma-mpp-rdo-master-plan.md`.
> Este documento fixa QUEM é responsável por QUAL escrita. Um caso de uso não
> pode "aproveitar" o serviço de outro — foi exatamente esse aproveitamento
> (import recriando RDOs para consertar FKs) que gerou o acoplamento que o
> plano mestre desmonta.

## Os cinco casos de uso

| # | Caso de uso | Quando acontece | Serviço responsável | Destrutivo? |
|---|---|---|---|---|
| 1 | **Criação inicial de obra completa** | Uma vez por obra, a partir do JSON físico-financeiro (piloto baias) | `services/importacao_fisico_financeiro.importar_fisico_financeiro` | **Sim, por design** — `_limpar_derivados` zera derivados e recria tudo (idempotência por sobrescrita) |
| 2 | **Importação/substituição de cronograma** | Sempre que chega um `.mpp`/`.xml` novo de uma obra que JÁ existe | Novo pipeline M3→M5 (`mpp_parser` → normalização → reconciliação → aplicação transacional) | **Não** — ids de `TarefaCronograma` são estáveis; versões são snapshots; RDOs/custos/medições intocados |
| 3 | **Registro de RDO** | Diário, pela UI (`/salvar-rdo-flexivel`) ou API | `services/cronograma_apontamento_service.registrar_apontamento` (fórmula única desde `d60e107`) + handlers de `views/rdo.py` | Não — só acrescenta/atualiza apontamentos do próprio RDO |
| 4 | **Atualização de custos** | Ao revisar OSC/OSCItem de uma etapa | `services/cronograma_fisico_financeiro.recalcular_osc_dos_itens` e afins | Não |
| 5 | **Atualização de medições** | Fechamento de medição de contrato | `services/medicao_service` | Não |

## Tabela de responsabilidade por escrita

Quem pode ESCREVER em cada família de tabelas. Leitura é livre; escrita fora
desta tabela é bug de arquitetura.

| Tabela(s) | Caso 1 (criação inicial) | Caso 2 (subst. cronograma) | Caso 3 (RDO) | Caso 4 (custos) | Caso 5 (medições) |
|---|---|---|---|---|---|
| `Orcamento*`, `Proposta*` | cria (`_importar_comercial`) | — | — | — | — |
| `TarefaCronograma` | cria (`_importar_cronograma`) | atualiza in-place / cria novas (M5); **nunca deleta** | atualiza `percentual_concluido` via `sincronizar_percentuais_obra` | — | — |
| `ItemMedicaoComercial`, `ItemMedicaoCronogramaTarefa` | cria (`_importar_comercial`/`_importar_custos`) | revincula etapa→tarefa quando o match muda (M5) | — | — | — |
| `ObraServicoCusto*` | cria (`_importar_custos`) | — | — | atualiza | — |
| `MedicaoContrato` | cria (`_importar_medicoes`) | — | — | — | cria/atualiza |
| `RDO`, `RDOMaoObra`, `RDOServicoSubatividade` | cria (`_importar_rdos`) | **intocado** | cria/atualiza | — | — |
| `RDOApontamentoCronograma` | cria (via `_materializar_rdos`) | **intocado** | `registrar_apontamento` (UPSERT por rdo+tarefa) | — | — |
| Versões/snapshot de cronograma (M2) | — | cria (M5) | — | — | — |

## Regras que decorrem da tabela

1. **O caso 1 não roda duas vezes na mesma obra viva.** Ele apaga e recria
   RDOs (fotos preservadas por snapshot). Para obra com RDOs criados pela UI,
   substituição de cronograma é SEMPRE o caso 2. A fronteira é decidida na
   UI/rota, não por heurística no serviço.
2. **O caso 2 nunca escreve em tabelas de RDO.** É essa regra que torna os
   ids de `TarefaCronograma` estáveis e mantém válidas as FKs
   (`RDOApontamentoCronograma.tarefa_cronograma_id` CASCADE,
   `RDOMaoObra.tarefa_cronograma_id` SET NULL, etc.).
3. **Toda fórmula de apontamento passa por `registrar_apontamento`.** Os dois
   callers (`views/rdo.py:salvar_rdo_flexivel`, `cronograma_views.py:apontar_producao`)
   já delegam; um terceiro caminho de gravação de apontamento é regressão.
4. **Percentual de progresso é responsabilidade do engine V2**
   (`utils/cronograma_engine.py`). Os caminhos B/C/D/E do diagnóstico
   (§1.2 do mestre) serão unificados no M6; até lá, nenhum caminho novo.
5. **Autorização das rotas do caso 2**: `decorators.cronograma_import_required`
   (autenticado + ADMIN/SUPER_ADMIN + tenant resolvido). Os bypasses legados
   de `decorators.py` não valem para rotas novas.

## O que o Módulo 01 já entregou desta separação

- Fórmula de apontamento única: `services/cronograma_apontamento_service.py`
  (`c58b98e`, `d60e107`), com caracterização congelada (`3d94224`).
- Importador do caso 1 organizado em blocos nomeados espelhando as colunas
  da tabela acima (`6782960`) — sem mudança de comportamento.
- Rota `/rdo/salvar` com dono único (`1f7997f`).
- Decorator do caso 2 pronto (`decorators.cronograma_import_required`).

Os casos 2 (pipeline novo) e a unificação de progresso são entregues pelos
Módulos 2–6; este documento é o contrato que eles devem respeitar.
