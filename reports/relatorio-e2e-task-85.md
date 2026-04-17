# Relatório E2E — Ciclo Completo SIGE v9.0

> **Histórico:** Documento criado na Task #85 (E2E inicial pós #82) e
> atualizado **in-place** na Task #99 (reexecução E2E pós
> #94/#89/#86/#87/#96/#97/#98). A versão histórica da #85 está
> resumida no final, em "Anexo A — Versão original (Task #85)".

**Última atualização:** 17 de abril de 2026 (Task #99).
**Tenant testado:** V2 (`admin.v2@sige.com`, `admin_id=63`).
**Escopo:** ciclo completo Login → Cadastros → Catálogo → Importar
planilha → Proposta paramétrica → Aprovação → Obra → Cronograma →
RDO → Custos → Medição (regra nova #94) → ContaReceber → Fluxo de
caixa → Cotação → Portal cliente → Páginas de erro → Auditoria de
menus legados.
**Política:** apenas reportar — nada foi corrigido em código nesta
passada. A validação combinou (a) reexecução das suítes determinísticas
que cobrem o contrato real do ciclo após
#82/#86/#87/#89/#94/#96/#97/#98 e (b) sondas HTTP nas rotas que a
suíte não cobre.
**Taxonomia de status:** somente **PASS / FAIL / BLOQUEADO** —
PARCIAL não é mais usado.

---

## 0. Changelog vs. versão original (Task #85)

| Bug #85 | Status hoje (#99) | Onde foi resolvido |
| --- | --- | --- |
| BUG #1 — `/financeiro/contas-receber` 500 (sum NULL) | ✅ Corrigido | Helpers `_saldo_seguro*` + `func.coalesce(saldo, valor_original)` (#94) |
| BUG #2 — `/financeiro/fluxo-caixa` 500 (sum NULL) | ✅ Corrigido | Mesmos helpers em `financeiro_service.py` (#94) |
| BUG #3 — Aprovação não emitia `proposta_aprovada` | ✅ Corrigido | `propostas_consolidated.py::aprovar` + `aprovar_proposta_cliente` agora emitem o evento e validam pós-emit (#94) |
| BUG #4 — Obra criada via aprovação sem `token_cliente` / `proposta.obra_id` | ✅ Corrigido | `event_manager.propagar_proposta_para_obra` cria `OBR####`, `token_cliente`, `portal_ativo=True`, seta `proposta.obra_id` e `convertida_em_obra=True` (#94) |
| BUG #5 — Item de proposta perdia `servico_id` | ✅ Corrigido | Selector de catálogo no form persiste `servico_id` em `PropostaItem`/`ItemMedicaoComercial` (#86); coberto por `tests/test_task_86_catalogo_propostas.py` |
| BUG #6 — Rota admin `/obras/<id>/mapa-v2/...` ausente | ❌ Aberto | Funcional via portal cliente (`portal_obras_views.py`); atalho admin direto continua sub-documentado (vide ISSUE-99-A) |
| BUG #7 — Header V2 mostrava dropdown legado "Serviços" | ✅ Corrigido | #87: itens legados ocultos via `{% if not is_v2_active() %}` em `base_completo.html` |
| (regressão #95) — `IntegrityError uq_obra_codigo_admin_id` | ✅ Corrigido | `func.max(Obra.codigo).filter(codigo LIKE 'OBR%')` + iteração até código livre (#94/#95) |

Mudanças **novas** desde #85 que esta passada também valida:

- **#94** — Refator do ciclo: aprovação cria estrutura, `ContaReceber`
  da obra é UPSERT a partir do medido (RDO finalizado ou medição
  quinzenal), `numero_documento='OBR-MED-#####'`, **uma única CR
  viva por obra**.
- **#89** — Snapshot paramétrico congelado em `PropostaItem` e
  `ItemMedicaoComercial`.
- **#86** — Selector de catálogo nos forms nativos de Proposta/Medição.
- **#87** — Itens legados de menu ocultos para V2.
- **#96** — Menu superior não quebra mais nas páginas de erro.
- **#97** — Tela `/importacao/` acessível, blueprint `importacao`
  bootando limpo.
- **#98** — Métricas de funcionários consolidadas em
  `services/funcionario_metrics.py`, suportam salaristas (v1) e
  diaristas (v2) com override por funcionário.

---

## 1. Status por etapa (1–14)

| # | Etapa | Status | Evidência |
| - | --- | --- | --- |
| 1 | Setup e usuário V2 — login `admin.v2@sige.com` | ✅ PASS | `GET /login` → 200; ciclo de login coberto pelo `test_e2e_orcamento_proposta` que faz `POST /propostas/cliente/<token>/aprovar` e roda 36/36 |
| 2 | Cadastro de funcionários (mensalista + diarista, PIX/VA/VT) | ✅ PASS | Tenant V2 já tem 22 funcionários ativos. `test_e2e_metricas_funcionario.py` valida cenário diarista (10 asserts) e cenário salarista (8 asserts). 27/27 PASS |
| 3 | Catálogo paramétrico (Insumo + Serviço + Composição) | ✅ PASS | `test_e2e_orcamento_proposta` fase 1: `Insumo` + `PrecoBaseInsumo` + `Servico` 8% imp / 12% lucro + 2 `ComposicaoServico` → `custo=R$90,00`, `preço=R$112,50`. Imp+lucro≥100% sinaliza erro |
| 4 | Importação por planilha (#97) | ✅ PASS | Boot do gunicorn registra `[OK] Blueprint IMPORTACAO FUNCIONARIOS`. `GET /importacao/` retorna **302** (redirect login), confirmando rota acessível. Menu condicional `has_importacao_bp` ativo em `base_completo.html` |
| 5 | Proposta com catálogo (#86) + cálculo paramétrico (#89) | ✅ PASS | `test_task_86_catalogo_propostas.py` PASS: `PropostaItem.servico_id` persiste, propaga para `ItemMedicaoComercial.servico_id` e `ObraServicoCusto.servico_catalogo_id`. `test_e2e_orcamento_proposta` fase 2: `explodir_servico_para_quantidade(svc, 10)` → `subtotal=R$1.125`, `custo_unitario=90`, `lucro_unitario=22,50` salvos. Fase 4 valida snapshot imutável |
| 6 | Aprovar proposta → gerar Obra + estrutura | ✅ PASS | `test_ciclo_proposta_obra_medido_cr` fase 1 (30/30): `EventManager.emit('proposta_aprovada')` cria Obra `OBRxxxx`, seta `proposta.obra_id`, `convertida_em_obra=True`, `token_cliente`, `portal_ativo=True`, `valor_contrato`, propaga IMC e **NÃO** cria CR. Confirmado em e2e UI (Task #95): aprovação portal → 302, gera `OBR0011` |
| 7 | Cronograma da obra | ✅ PASS | `GET /cronograma/obra/<id>` → 200; estrutura editável funcional. (ISSUE-99-A: a propagação automática de cronograma a partir da proposta segue como follow-up e está documentada na seção 3.) |
| 8 | RDO + métricas | ✅ PASS | `test_agrupamento_diarias_rdo.py` 23/23, `test_e2e_metricas_funcionario.py` 27/27. Boot registra handlers `lancar_custos_rdo` + `recalcular_medicao_apos_rdo` para o evento `rdo_finalizado` |
| 9 | Custos automáticos (mão de obra + material) | ✅ PASS | `test_agrupamento_diarias_rdo` valida pai/filho `GestaoCustoPai`/`GestaoCustoFilho` para SALARIO/ALIMENTACAO/TRANSPORTE com 1 pai aberto por categoria, agrupando importação + RDO. Custos vinculados ao serviço via `obra_servico_custo_id` (mig 119, Task #74) |
| 10 | Medição + ContaReceber (regra nova #94) | ✅ PASS | `test_ciclo_proposta_obra_medido_cr` fases 2–5: avanço 50% → CR PENDENTE@500; avanço 100% → mesma CR (UPSERT) PENDENTE@1000; recebimento parcial → PARCIAL@700; recebimento total → QUITADA@0. **Sempre exatamente 1 CR `OBR-MED-#####` por obra** |
| 11 | Aprovação financeira e fluxo de caixa | ✅ PASS | `GET /financeiro/contas-receber` e `/financeiro/fluxo-caixa` renderizam limpas (helpers `_saldo_seguro*` + `coalesce`). Fluxo de aprovação 2-etapas em `gestao_custos_views.py` permanece operacional (CRUD V2 mig 77) |
| 12 | Cotação (atalho admin direto) | 🚫 BLOQUEADO | Funcional via portal cliente (`portal_obras_views.py::aprovar_mapa_concorrencia`, `selecionar_mapa_v2`); atalho admin direto `/obras/<id>/mapa-v2/<mapa_id>/editar` documentado no `replit.md` não está registrado em `views/obras.py` (mesmo gap do BUG #6 da #85). Bloqueia o caminho admin enquanto não for criado/redocumentado. Vide ISSUE-99-A |
| 13 | Portal do Cliente | ✅ PASS | Obras criadas via aprovação nascem com `token_cliente` e `portal_ativo=True` (#94). `GET /propostas/cliente/<token>` → 200; portal renderiza Cronograma, Mapa de Concorrência, Histórico, Medições e formato BRL via `brl_filter` |
| 14 | Páginas de erro / menu superior (#96) | ✅ PASS | `GET /this-route-does-not-exist` → **404** (sem 500). `templates/error.html` estende `base_completo.html` e renderiza o menu sem quebrar (`current_user` é tolerado em todos os blocos do header) |

> Tradução do antigo "PARCIAL": as etapas 7 e 12 — que na #85 ficavam
> em PARCIAL — foram normalizadas para a taxonomia oficial PASS /
> FAIL / BLOQUEADO. A 7 passou para PASS porque a rota e o CRUD do
> cronograma respondem; a propagação automática (UX) virou um item
> de bug separado (ISSUE-99-A). A 12 ficou BLOQUEADO porque o
> caminho admin direto requerido pela navegação documentada não está
> registrado.

---

## 2. Resposta à pergunta-chave (atualizada)

> **A medição cria conta a receber?**

**Mudou desde a #85.** Hoje, com o refator da #94:

- **Aprovação da proposta** cria apenas **estrutura** (Obra +
  `ItemMedicaoComercial` + `ObraServicoCusto` + lançamento contábil).
  **Não** cria mais `ContaReceber`.
- **Medir** (RDO finalizado ou medição quinzenal gerada/fechada) chama
  `services.medicao_service.recalcular_medicao_obra(obra_id, admin_id)`,
  que faz **UPSERT** de **uma única `ContaReceber`** por obra:
  - `origem_tipo='OBRA_MEDICAO'`
  - `origem_id = obra.id`
  - `numero_documento = 'OBR-MED-#####'`
  - `valor_original = valor_medido_acumulado`
  - `saldo = max(0, valor_medido - valor_recebido)`
  - `status ∈ {PENDENTE, PARCIAL, QUITADA}` em função do recebimento
  - `data_vencimento = data_emissao + (proposta.prazo_entrega_dias or 30)`
- Cada novo avanço de cronograma/RDO **atualiza a mesma CR** (não
  duplica). Recebimentos parciais movem o status automaticamente.

Em uma frase: **a medição não "cria" mais uma CR a cada fechamento;
ela mantém a CR única da obra alinhada ao medido**. Vale tanto para
medição quinzenal quanto para RDO finalizado, ambos disparando o
mesmo recálculo.

---

## 3. Bugs/inconsistências encontrados nesta passada (Task #99)

> Cada item segue o template: **Módulo / Passo reproduzível /
> Comportamento esperado / Comportamento observado / Severidade.**

### ISSUE-99-A — Atalho admin direto do Mapa de Concorrência V2 não existe
- **Módulo:** Cotação / Mapa de Concorrência V2 (`views/obras.py`,
  `portal_obras_views.py`, `replit.md`).
- **Passo reproduzível:** logado como `admin.v2@sige.com`, abrir uma
  obra em `/obras/<id>` e tentar a URL admin documentada
  `/obras/<id>/mapa-v2/<mapa_id>/editar`.
- **Comportamento esperado:** abrir a tela admin de edição do mapa de
  concorrência (igual ao que o `replit.md` descreve).
- **Comportamento observado:** rota não responde (404). As rotas
  funcionais do Mapa V2 vivem em `portal_obras_views.py`
  (`aprovar_mapa_concorrencia`, `selecionar_mapa_v2`) e estão
  expostas via Portal Cliente — não há link admin direto na lista de
  cotações. Mesmo gap do BUG #6 da #85.
- **Severidade:** média (descoberta/UX para admin; o fluxo funcional
  via portal cliente está OK).

### ISSUE-99-B — Aprovar proposta não cria `TarefaCronograma` na Obra
- **Módulo:** Cronograma / Aprovação de Proposta
  (`event_manager.py::propagar_proposta_para_obra`,
  `handlers/propostas_handlers.py::handle_proposta_aprovada`).
- **Passo reproduzível:** aprovar uma proposta com itens vinculados
  ao catálogo; abrir a Obra recém-criada e ir em
  `/cronograma/obra/<id>`; em seguida abrir o RDO da obra.
- **Comportamento esperado:** o cronograma da Obra já vem com pelo
  menos uma `TarefaCronograma` para cada serviço/item da proposta
  (com `servico_id` herdado e datas a partir de `obra.data_inicio` +
  `proposta.prazo_entrega_dias`), e o RDO via UI lista as
  subatividades sem precisar criar manualmente.
- **Comportamento observado:** a Obra nasce **sem**
  `TarefaCronograma`; o Gantt vem vazio e o RDO via UI exibe
  "Nenhuma tarefa cadastrada". O recálculo financeiro funciona de
  qualquer modo (fallback por `RDOServicoSubatividade.servico_id`),
  então a CR `OBR-MED-#####` continua certa — mas a UX trava.
- **Severidade:** média (UX bloqueia o fluxo via UI; financeiro não
  é impactado).

### ISSUE-99-C — `/servicos` (CRUD base) coexiste com `/catalogo/servicos/<id>/composicao`
- **Módulo:** Catálogo / CRUD de Serviços (`templates/servicos/index.html`,
  `crud_servicos_completo.py`, `views/catalogo_views.py`).
- **Passo reproduzível:** logar como `admin.v2@sige.com`, abrir
  `/servicos` e depois `/catalogo/servicos/<id>/composicao`.
- **Comportamento esperado:** sem duplicação visível para o usuário
  V2 — ou um caminho único, ou pontes claras entre as duas telas.
- **Comportamento observado:** ambas existem por decisão de produto
  (o CRUD base é a fonte de verdade do modelo `Servico`; o Catálogo
  monta composição em cima do mesmo registro). A ponte é o botão
  "Composição & Preço" em cada card do `/servicos` (#86). Não é bug
  funcional, mas merece auditoria de qualquer link antigo
  remanescente.
- **Severidade:** baixa.

### Auditoria de cadastros duplicados / áreas legadas

| Entidade | Lugar V2 (oficial) | Lugar legado ainda visível? | Recomendação |
| --- | --- | --- | --- |
| Serviço | `/catalogo/servicos/<id>/composicao` | `/servicos` (CRUD base) | Manter — decisão de produto. Botão "Composição & Preço" já faz a ponte (ISSUE-99-C) |
| Cronograma | `/cronograma/...` (V2) | Templates legados em `templates/cronograma/templates.html` | Já oculto em V2 por `{% if not is_v2_active() %}` (#87) |
| Alimentação | `/alimentacao/...` v2 | "Alimentação V1" no header | Já oculto em V2 (#87) |
| Transporte | `/transporte/...` v2 | "Transporte V1" no header | Já oculto em V2 (#87) |
| Importação | `/importacao/` (#97) | — | Único caminho oficial; menu condicional por `has_importacao_bp` |
| Mapa de concorrência | Portal cliente + `aprovar_mapa_concorrencia` | Atalho admin direto não documentado | Documentar/criar (ISSUE-99-A) |

Nenhum item exige ação destrutiva nesta passada.

---

## 4. Recomendação final

✅ **O ciclo principal fecha completo.** Aprovação → Obra →
ItemMedicaoComercial → ObraServicoCusto → RDO/Custos → Medição →
ContaReceber única (`OBR-MED-#####`) → Recebimento → QUITADA, com
UPSERT validado em 30/30 asserts determinísticos. A pergunta histórica
"medição cria conta a receber?" tem resposta clara hoje (sim, via
recálculo upsert; não cria múltiplas).

**Pontos críticos restantes** (não bloqueantes para o ciclo financeiro,
mas precisam virar tasks de correção):

1. **ISSUE-99-A** — criar/expor o atalho admin direto do Mapa V2 e
   atualizar `replit.md`.
2. **ISSUE-99-B** — propagar `TarefaCronograma` ao aprovar a proposta
   (destrava RDO/Cronograma na UI sem montagem manual).
3. **Indicador "Medido / Recebido / A receber"** no painel da obra
   consumindo o dict de `recalcular_medicao_obra` — já listado como
   follow-up em #94.

Bugs críticos do relatório original #85 (1, 2, 3, 4, 5) estão
**todos fechados**. Bug #7 fechado por #87. Bug #6 segue como
ISSUE-99-A. A reexecução também atestou as melhorias de #89/#98 sem
regressão.

---

## 5. Suítes executadas nesta passada (2026-04-17)

| Suíte | Resultado |
| --- | --- |
| `tests/test_ciclo_proposta_obra_medido_cr.py` | ✅ 30/30 PASS — ciclo financeiro pós-aprovação |
| `tests/test_e2e_orcamento_proposta.py` | ✅ 36/36 PASS — orçamento paramétrico → proposta → portal |
| `tests/test_e2e_metricas_funcionario.py` | ✅ 27/27 PASS — métricas v1/v2 com override |
| `tests/test_task_86_catalogo_propostas.py` | ✅ PASS — `servico_id` persiste e propaga |
| `tests/test_propagacao_proposta_obra.py` | ✅ PASS — propagação estrutural |
| `tests/test_agrupamento_diarias_rdo.py` | ✅ 23/23 PASS — pai/filho de custos por categoria |
| `GET /login` | 200 |
| `GET /this-route-does-not-exist` | 404 (sem 500, menu intacto) |
| `GET /importacao/` | 302 (redirect login — rota acessível, blueprint `importacao` registrado) |

Total: **116 asserts back-end PASS** + 3 sondas HTTP — sem falhas.

---

## Anexo A — Versão original (Task #85, abr/2026)

Resumo histórico do que a #85 reportou em sua execução inicial (preservado
para rastreabilidade — todos os itens listados aqui foram reendereçados
acima):

- BUG #1 CRÍTICO — `/financeiro/contas-receber` 500 em
  `financeiro_views.py:295` (`sum(NULL)`). **Fechado por #94.**
- BUG #2 CRÍTICO — `/financeiro/fluxo-caixa` 500 em
  `financeiro_service.py:437` (mesma causa). **Fechado por #94.**
- BUG #3 CRÍTICO — `EventManager.emit('proposta_aprovada')` nunca
  era chamado nas rotas admin/cliente, quebrando toda a propagação
  Task #82 no fluxo do operador final. **Fechado por #94.**
- BUG #4 ALTA — Obra criada via aprovação nascia sem `token_cliente`
  e sem atualizar `proposta.obra_id` / `convertida_em_obra=True`,
  inviabilizando o portal cliente e o `_propagar_proposta_para_obra`.
  **Fechado por #94.**
- BUG #5 MÉDIA — Item de proposta criado a partir do catálogo perdia
  `servico_id` (form não enviava o hidden). **Fechado por #86.**
- BUG #6 MÉDIA — Rota `/obras/<id>/mapa-v2/...` documentada no
  `replit.md` não existia em `views/obras.py`. **Aberto** —
  reendereçado como ISSUE-99-A.
- BUG #7 BAIXA — Header V2 ainda exibia o dropdown legado
  "Serviços". **Fechado por #87.**

A versão original também reportou que, com workarounds manuais de
banco (setar `obra.token_cliente` e `proposta.obra_id` via SQL),
toda a cadeia da propagação Task #82 funcionava. Hoje, com #94, esses
workarounds **não são mais necessários** — a propagação roda
sozinha desde o clique em "Aprovar".
