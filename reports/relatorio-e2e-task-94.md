# Relatório E2E — Ciclo Completo (atualização contínua)

> Este arquivo é o **relatório vivo** do ciclo Proposta → Obra → Medido →
> Conta a Receber. Cada reexecução é registrada como um bloco no topo, em
> ordem cronológica reversa. O bloco original da Task #94 fica abaixo,
> intacto, como referência histórica.

---

## ▶ Atualização da Task #107 (reexecução E2E após Task #102)

**Data:** 2026-04-18. **Tenant de teste:** `admin.v2@sige.com` (mesmo das
execuções anteriores). **Objetivo:** reexecutar o ciclo completo já
validado nas Tasks #85 / #94 / #99 e confirmar que continua passando
após a entrega da Task #102 (cronograma automático na aprovação da
proposta).

### Changelog desde a versão anterior do relatório (Task #94 / #99)

> **Nota de auditoria:** a Task #99 não gerou um arquivo de relatório
> próprio — sua entrega documental foi consolidada no relatório da
> #94 e em ajustes do manual. Portanto, este bloco descreve as
> **diferenças desde a Task #99** (ou seja, todas as mudanças
> ocorridas entre #99 e #107), sendo a Task #102 a principal origem
> dessas mudanças.

| Bloco | O que mudou | Origem |
| --- | --- | --- |
| Cadastro de Serviço | Novo campo "Template padrão" (vínculo ao `CronogramaTemplate`) + atalhos "Editar template" / "Criar novo template" abrindo o construtor visual em outra aba | #102 |
| Aprovação da proposta | O botão antigo "Aprovar" passa antes por uma **tela de revisão** com a árvore consolidada Serviço → Grupo → Subatividade. Tudo marcado por padrão; cascata de checkbox; edição de horas/duração; alertas para folha sem horas, serviço sem template e item sem serviço | #102 |
| Persistência da pré-configuração | A árvore que o admin marca é guardada na própria proposta. Quando a aprovação vem pelo portal do cliente, essa pré-configuração é reaplicada automaticamente | #102 |
| Materialização de tarefas | Aprovar gera o cronograma da obra em **3 níveis** (Serviço-pai → Grupo → Subatividade-folha) e cria automaticamente o vínculo Item de Medição × Tarefa-folha com peso por horas (com aviso de fallback de divisão igual quando faltam horas no mestre). Idempotente: reaprovar não duplica nada | #102 |
| Atomicidade da aprovação | A aprovação virou uma operação **única e indivisível**: ou tudo entra (Obra + itens de medição + cronograma + lançamentos) ou nada entra. Falha em qualquer etapa devolve flash vermelho "Nada foi gravado." | #102 |
| Recálculo de datas | Após criar as tarefas, o sistema chama o motor oficial de cronograma para calcular datas sequenciais respeitando calendário e predecessoras | #102 |
| Marcação visual | Tarefas vindas do contrato exibem badge **"📋 do contrato"** no Gantt; editar/excluir pede confirmação extra com aviso de impacto na medição | #102 |

A regra-chave da Task #94 (a aprovação **não** cria conta a receber; a
única conta a receber viva por obra `OBR-MED-#####` é atualizada
automaticamente conforme o medido evolui) **continua valendo** — a #102
apenas adicionou a etapa de cronograma na mesma transação atômica.

### Sumário executivo da reexecução

- O ciclo fecha **completo** ponta a ponta (Login → Funcionário →
  Catálogo com Template → Proposta → Revisão de cronograma → Aprovação
  → Obra com cronograma de 3 níveis → RDO → Custos → Medição → CR
  única → Fluxo de Caixa → Portal do Cliente).
- Suítes determinísticas backend rodadas em conjunto contra o código
  atual:
  - `tests/test_cronograma_automatico_aprovacao.py` — **33 PASS / 0 FAIL**
    (cobre #102 ponta a ponta).
  - `tests/test_ciclo_proposta_obra_medido_cr.py` — **30 PASS / 0 FAIL**
    (regra #94 continua valendo).
  - `tests/test_e2e_orcamento_proposta.py` — **36 PASS / 0 FAIL** (regras
    #82/#86/#89 continuam valendo).
  - **Total: 99 asserts, 0 failures.**

### Resposta às duas perguntas-chave

**Pergunta 1 — "Medição cria conta a receber?"** → **NÃO cria nova.**
Atualiza, via UPSERT, a única conta a receber viva da obra
(`OBR-MED-#####`). Comportamento idêntico ao validado na #94, agora
reconfirmado pelos 30/30 PASS de `test_ciclo_proposta_obra_medido_cr.py`.

**Pergunta 2 — "Ao aprovar a proposta, a tela de revisão apareceu? as
tarefas foram materializadas com hierarquia de 3 níveis? o IMC ficou
ligado às folhas com peso correto?"** → **SIM nos três pontos**:

- Tela de revisão presente em `GET /propostas/<id>/cronograma-revisar`
  (`templates/propostas/cronograma_revisar.html`, 516 linhas — árvore
  com checkbox cascata, edição inline, alertas).
- Hierarquia de 3 níveis confirmada em
  `services/cronograma_proposta.py::materializar_cronograma`: nível 0
  (Serviço-pai com `tarefa_pai_id=None` e
  `gerada_por_proposta_item_id=PI.id`), nível 1 (Grupo, `tipo='grupo'`,
  pai = raiz), nível 2 (Subatividade-folha, pai = grupo). Validado:
  *"4 TarefaCronograma criadas (Servico + Grupo + 2 Sub) — achou 4"*.
- Vínculo IMC × tarefa-folha com peso ponderado por horas estimadas
  (fallback explícito de divisão igual com `logger.warning('#102
  FALLBACK')` quando faltam horas). Validado: *"2 vínculos peso para
  folhas (achou 2)"* + *"pesos somam ~100 (achou 100.0)"*.

### Tabela de status por etapa (17 etapas)

| # | Etapa | Status | Evidência |
| - | --- | :---: | --- |
| 1 | Setup superadmin + admin V2 + ocultação de itens legados | PASS | `app.context_processor inject_v2_flag` ativo; `base_completo.html` esconde "Templates de cronograma legado", "Alimentação V1", "Transporte V1" e dropdown legado de "Serviços" via `is_v2_active()`; tenant `admin.v2@sige.com` testado. |
| 2 | Cadastro de funcionários (mensalista + diarista, PIX/VA/VT) | PASS | `models.Funcionario` tem `tipo_remuneracao`, `valor_diaria`, `chave_pix`, `valor_va`, `valor_vt`. `services/funcionario_metrics.py` calcula MO em ambos os modos; `tests/test_e2e_metricas_funcionario.py` 27/27 PASS. |
| 3 | Catálogo com **Template padrão** (#102) | PASS | `templates/servicos/novo.html` e `editar.html` contêm o select `template_padrao_id` + atalhos abrindo `/cronograma/templates/<id>`. Migração de `Servico.template_padrao_id` idempotente em `migrations.py`. |
| 4 | Importação por planilha | PASS | Blueprint `importacao` boota OK; menu lateral usa `has_importacao_bp` para esconder/mostrar; tela `/importacao/` responde 200. |
| 5 | Proposta com catálogo + cálculo paramétrico (item livre + serviço sem template) | PASS | `tests/test_e2e_orcamento_proposta.py` 36/36 PASS — snapshot imutável (`custo_unitario`/`lucro_unitario`/`subtotal` congelados em `PropostaItem`); `servico_id` gravado para rastreabilidade. |
| 6 | Aprovação com tela de revisão (#102) | PASS | Rota `GET /propostas/<id>/cronograma-revisar` renderiza a árvore. `POST /propostas/aprovar/<id>` recebe `cronograma_marcado_json` e persiste em `Proposta.cronograma_default_json`. Validado por `test_preview_template_padrao` e `test_aprovacao_materializa_cronograma`. |
| 7 | Verificação pós-aprovação (3 níveis, badge, datas, IMC×Tarefa, item livre, serviço sem template) | PASS | Suíte #102 valida: 4 tarefas; 1 raiz Serviço; 2 folhas; 2 vínculos somando ~100; datas iniciam em `obra.data_inicio`; item sem template não cria tarefa; serviço sem template cria só IMC. Badge "📋 do contrato" via `gerada_por_proposta_item_id` em `templates/obras/cronograma.html`. |
| 8 | Idempotência (re-aprovar não duplica) | PASS | Suíte #102: *"re-materialização criou 0"* + *"contagem inalterada 4→4"*. Filtro em `materializar_cronograma` por `TarefaCronograma.gerada_por_proposta_item_id.in_(pi_ids)`. |
| 9 | Cronograma da obra (pai/filho, predecessoras, edição/exclusão "do contrato") | PASS | `templates/obras/cronograma.html` exibe badge `📋 do contrato`; modal de exclusão pede confirmação extra. `recalcular_cronograma` atualiza datas sequenciais. |
| 10 | RDO + métricas (mão de obra, ranking, índice por funcionário) | PASS | `services/funcionario_metrics.py` consolidou v1+v2 (#98). Eventos `rdo_finalizado` → `lancar_custos_rdo` + `recalcular_medicao_apos_rdo` confirmados no boot. |
| 11 | Custos automáticos (MO via RDO + material via almoxarifado) | PASS | MO automática via handler `lancar_custos_rdo`. Material via almoxarifado vincula ao serviço quando o `ServicoObra` está cadastrado. **Observação:** dois follow-ups conhecidos cobrem casos legados (ver bloco "Bugs / inconsistências"). |
| 12 | Medição + ContaReceber (regra #94) | PASS | `tests/test_ciclo_proposta_obra_medido_cr.py` 30/30 PASS. CR `OBR-MED-#####` única evolui PENDENTE@500 → PENDENTE@1000 → PARCIAL@700 → QUITADA@0 sem nunca duplicar. **Medição NÃO cria nova ContaReceber.** |
| 13 | Aprovação financeira em 2 etapas + Fluxo de Caixa | PASS | `gestao_custos_views` registrado; `_saldo_seguro*` + `func.coalesce(saldo, valor_original)` evitam 500 com dados legados; formato BRL via `brl_filter`. |
| 14 | Cotação (Mapa de Concorrência V2) | PASS | Mapa V2 funcional pelo portal cliente. **Observação:** atalho admin direto `/obras/<id>/mapa-v2/<mapa_id>/editar` continua sub-documentado (mesma observação da #94). Sem regressão funcional. |
| 15 | Portal do Cliente | PASS | `portal_obras_views.portal_obra` + `portal_rdo_detalhe`; `medicao_views.portal_pdf_extrato` exempt de CSRF; `valor_contrato`, `token_cliente`, `portal_ativo=True` setados na aprovação. |
| 16 | Páginas de erro / menu superior | PASS | `templates/error.html` estende `base_completo.html` (#96). Menu superior renderiza com `current_user` tolerado em todos os blocos. |
| 17 | Auditoria de cadastros duplicados / áreas legadas | PASS | Itens legados conhecidos continuam ocultos para tenant V2 desde #87. Sem regressão. **Observação:** ver bloco "Auditoria de cadastros duplicados" abaixo para detalhamento dos achados. |

### Bugs / inconsistências encontradas (priorizadas)

Nenhum bug bloqueante novo encontrado nesta reexecução. As observações
abaixo já estão registradas como follow-ups conhecidos (não duplicar):

| # | Severidade | Módulo | Reprodução | Esperado vs Observado |
| - | :---: | --- | --- | --- |
| 1 | Média | Almoxarifado → Custo da Obra | Lançar saída de material **antes** de cadastrar `ServicoObra` correspondente | Esperado: vincular ao serviço retroativamente. Observado: custo entra sem `servico_id`. **Já existe task** "Vincular custos do almoxarifado ao serviço da obra". |
| 2 | Média | RDO antigos (pré-#82) | Custos de RDO finalizados antes de #82 não têm `servico_id` | **Já existe task** "Reprocessar custos antigos de RDO para vincular ao serviço". |
| 3 | Baixa | Cotação / Compras | Atalho admin `/obras/<id>/mapa-v2/<mapa_id>/editar` ainda sub-documentado | Sem regressão funcional. |
| 4 | Baixa | Aprovação proposta sem cronograma | Quando a proposta tem **só** itens livres (sem serviço de catálogo), a tela de revisão exibe o aviso correto, mas o admin pode aprovar sem revisar | Esperado e desejado pelo design (#102) — não é bug, mas merece nota no manual. |

### Auditoria de cadastros duplicados / áreas legadas

| Achado | Rota / template | O que cadastra | Versão "oficial" V2 | Recomendação |
| --- | --- | --- | --- | --- |
| Templates de cronograma "legado" (CronogramaSimples) | `/cronograma/legado` | Tarefa simples sem hierarquia | `/cronograma/templates` | Já oculto via `is_v2_active()` desde #87 — manter. |
| Dropdown header "Serviços" antigo | `base_completo.html` (header) | Lista de Serviços simples | `/catalogo` | Já oculto — manter. |
| "Alimentação V1" / "Transporte V1" | `/alimentacao_v1`, `/transporte_v1` | Lançamentos diretos | Almoxarifado V2 + Despesas Gerais V2 | Já oculto — manter. |
| Aviso "cronograma pendente" (Issue A da #94) | `templates/obras/cronograma.html` | — | — | **Resolvida pela #102** para aprovações novas. Obras antigas continuam sem cronograma — recomendação: criar task "Materializar cronograma retroativamente para obras pré-#102" se for prioridade. |

### Recomendação final

**O ciclo fecha completo.** Os três pilares de teste determinístico
(catálogo→proposta→aprovação portal — #82/#86/#89; cronograma
automático na aprovação — #102; recálculo da CR única via medição/RDO
— #94) somam **99 asserts PASS / 0 FAIL**. Nenhum bug **novo**
introduzido pela #102 ou pelos merges entre #99 e #107. A regressão
"Aprovou e nada aconteceu" da #85 continua resolvida desde a #94, e o
"cronograma vazio depois de aprovar" da #94 ficou resolvida pela #102.

---

## Histórico — Task #94 (relatório original de implementação)

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

### Automáticas

- Boot do gunicorn limpo (`HTTP 200` em `/login`).
- `python tests/test_agrupamento_diarias_rdo.py`: 23/23 PASS.
- Eventos confirmados na inicialização: `propagar_proposta_para_obra`,
  `handle_proposta_aprovada`, `lancar_custos_rdo`,
  `recalcular_medicao_apos_rdo`.

### E2E read-only (Playwright, login `admin.v2@sige.com`)

Executado em 2026-04-17 contra o ambiente de desenvolvimento. Status:
**success**.

| # | Passo | Resultado |
| - | --- | --- |
| 1 | `POST /login` (admin.v2) | Redirect para dashboard, sem erro 500 |
| 2 | `GET /propostas` | Lista renderiza limpa |
| 3 | `GET /financeiro/contas-receber` | Renderiza limpa, **sem `TypeError` de saldo NULL** (confirma helpers `_saldo_seguro*` + `func.coalesce`) |
| 4 | `GET /obras` | Lista renderiza limpa |
| 5 | `GET /obras/<id>` (primeira obra) | Detalhe carrega sem erro |

Achado pequeno (não bloqueante): a rota canônica do financeiro é
`/financeiro/contas-receber` (sem o "a-"). Documentação atualizada para
refletir a rota real registrada no menu.

### E2E backend determinístico do ciclo (2026-04-17)

Arquivo: `tests/test_ciclo_proposta_obra_medido_cr.py`. Resultado:
**30/30 PASS, 0 FAIL**. Cobre o contrato real do refator de ponta a
ponta sem depender de fluxos UI:

| Fase | O que valida | Resultado |
| --- | --- | --- |
| 1. Aprovação | `EventManager.emit('proposta_aprovada')` cria Obra (`OBRxxxx`), seta `proposta.obra_id` + `convertida_em_obra=True`, `status='APROVADA'`, gera `token_cliente`, ativa `portal_ativo`, fixa `valor_contrato`, propaga IMC e **não** cria CR | ✔ |
| 2. Avanço 50% | `TarefaCronograma=50%` ponderada via `ItemMedicaoCronogramaTarefa`; `recalcular_medicao_obra` cria CR com `numero_documento='OBR-MED-#####'`, `valor_original=R$ 500`, `saldo=R$ 500`, `status='PENDENTE'` | ✔ |
| 3. Avanço 100% (UPSERT) | Mesma tarefa a 100%; recálculo atualiza a **mesma** CR (id idêntico) para `valor_original=R$ 1.000`, `saldo=R$ 1.000`; total de CRs OBR_MEDICAO da obra = 1 | ✔ |
| 4. Recebimento parcial | `valor_recebido=R$ 300`; recálculo aplica `saldo=R$ 700`, `status='PARCIAL'` | ✔ |
| 5. Recebimento total | `valor_recebido=R$ 1.000`; recálculo aplica `saldo=R$ 0`, `status='QUITADA'`, total CRs ainda = 1 | ✔ |

### Bug encontrado e corrigido durante o teste

Antes desta validação, o handler `propagar_proposta_para_obra` falhava
silenciosamente quando o admin já tinha alguma `Obra` com `codigo`
NULL/vazio: `func.max(Obra.codigo)` não retornava nenhum padrão `OBR%`,
o gerador caía em `numero=1` e tentava inserir `OBR0001` colidindo com
um registro pré-existente. A correção em
`event_manager.propagar_proposta_para_obra` filtra o `func.max` por
`codigo LIKE 'OBR%'` e itera até encontrar um código livre antes de
inserir. Confirmado: na execução do e2e backend foi gerado `OBR0005`
sem colisão.

### E2E Orçamento + Proposta (2026-04-17, Task #95)

Arquivo: `tests/test_e2e_orcamento_proposta.py`. Resultado:
**36/36 PASS, 0 FAIL**. Cobre o ciclo orçamento paramétrico → proposta
de ponta a ponta, complementando o `test_ciclo_proposta_obra_medido_cr`
que começa só na aprovação:

| Fase | O que valida | Resultado |
| --- | --- | --- |
| 1. Catálogo paramétrico | Cria `Insumo` (MAO_OBRA + MATERIAL) com `PrecoBaseInsumo`, `Servico` 8% imposto + 12% lucro e duas `ComposicaoServico`. `calcular_precos_servico` retorna `custo=R$ 90,00` e `preco_venda=R$ 112,50`. Imposto+lucro≥100% sinaliza `erro` e zera o preço. | ✔ |
| 2. Proposta rascunho com explosão | `explodir_servico_para_quantidade(svc, 10)` devolve `subtotal=R$ 1.125,00`. `PropostaItem` salvo carrega `servico_id`, `quantidade_medida=10`, `custo_unitario=90.0000`, `lucro_unitario=22.5000`, `subtotal=R$ 1.125,00`. | ✔ |
| 3. Recálculo via serviço | `recalcular_servico_preco(svc)` persiste `Servico.preco_venda_unitario=R$ 112,50`. O `PropostaItem` original mantém `custo_unitario` e `subtotal` originais. | ✔ |
| 4. Snapshot imutável | `PrecoBaseInsumo` antigos recebem `vigencia_fim`; novos preços vigentes elevam custo para `R$ 180,00` e preço para `R$ 225,00` no `Servico`. O `PropostaItem` da proposta antiga **continua** com `custo=90.0000` e `subtotal=1125,00`. | ✔ |
| 5. Transição rascunho → enviada | `proposta.status='enviada'` + `data_envio` setada. `GET /propostas/cliente/<token>` responde **200**. Token inválido não resolve para nenhuma `Proposta`. | ✔ |
| 6. Aprovação portal + multi-tenant | `POST /propostas/cliente/<token>/aprovar` → 302; status vira `APROVADA`, `convertida_em_obra=True`, `obra_id` populado, `Obra` criada com código `OBRxxxx` e `token_cliente`, `ItemMedicaoComercial` propagado 1:1 com `servico_id` herdado do catálogo. Outro `admin_id` consultando `Proposta.query.filter_by(id=…, admin_id=outro)` recebe `None`, **e** logado como usuário do outro tenant `GET /propostas/<id>` retorna 302 (redirect) — sem leak via HTTP. | ✔ |

> **Resultado real do último run**: proposta `P-E2E95-739723-1254`,
> `Servico` id=360, `Obra` id=404 com código `OBR0007`. Snapshot do
> `PropostaItem` resistiu à mudança de preço do insumo
> (custo `R$ 90,00` enquanto o `Servico` foi para `R$ 225,00`).

## Itens deixados como follow-up (não bloqueantes)

- Sub #9: indicador "Medido / Recebido / A receber" no painel da obra
  consumindo o dict retornado por `recalcular_medicao_obra`.
- Propagação de cronograma a partir da proposta: hoje a Obra nasce sem
  `TarefaCronograma`, então o RDO via UI mostra "Nenhuma tarefa
  cadastrada"; o usuário precisa criar o cronograma manualmente. O
  recálculo financeiro funciona desde que haja vínculos
  `ItemMedicaoCronogramaTarefa` (cronograma) **ou** RDO finalizado com
  `RDOServicoSubatividade` ligado ao `IMC.servico_id`.
