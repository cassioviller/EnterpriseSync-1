# Relatório E2E — Task #85 (SIGE v9.0)

**Data:** 17 de abril de 2026  
**Tenant testado:** V2 (admin.v2@sige.com, admin_id=63)  
**Escopo:** ciclo completo Login → Catálogo → Proposta → Aprovação → Obra → Cronograma → RDO → Custos → Medição → Fluxo de Caixa → Cotação → Portal Cliente.  
**Política:** apenas reportar bugs — nada foi corrigido em código. Onde necessário, o estado do banco foi ajustado manualmente apenas para destravar a continuidade do teste (esses ajustes estão marcados como **[workaround de teste]** e devem virar correção futura).

---

## 1. Status por etapa

| # | Etapa | Status | Observação principal |
|---|-------|--------|----------------------|
| 1 | Login + navegação V2 | ✅ OK | Sessão e tour de rotas funcionam |
| 2 | Cadastro de funcionários | ⏭️ Não executado nesta passada | Tenant V2 já tem 22 funcionários ativos suficientes para o teste |
| 3 | Catálogo: Insumos + Serviço + Composição | ✅ OK | Insumos 213/214 e Serviço 355 com cálculo paramétrico validado (custo R$55,25 → preço R$78,93 com 10% imposto + 20% margem) |
| 4 | Proposta a partir do catálogo | ⚠️ PARCIAL | Proposta #115 criada (R$ 5.446,50) mas `servico_id` no item ficou NULL; tive que vinculá-lo via SQL |
| 5 | Aprovar proposta → gerar Obra + ContaReceber + ItemMedicaoComercial + ObraServicoCusto | ❌ QUEBRADO no fluxo do admin | **Bug crítico #3** — nenhuma rota admin emite o evento `proposta_aprovada`. Após disparar manualmente o evento + setar `obra_id`, a propagação rodou 100% (Obra 342, ContaReceber 49, IMC 156/157, OSC 153/154 com `servico_catalogo_id=355` herdado). |
| 6 | Cronograma da obra | ✅ OK | `/cronograma/obra/342` retorna 200 |
| 7 | Vínculo cronograma↔serviço | ⏭️ Não exercitado (nenhuma tarefa criada) | Depende da etapa 6 com dados |
| 8 | RDO consolidado | ✅ OK (rota) | `/rdo` e `/funcionario/rdo/consolidado` retornam 200 |
| 9 | Custos automáticos | ⚠️ Apenas rota | `/gestao-custos/` retorna 200 — fluxo de RDO→GCF não foi exercitado |
| 10 | Medição quinzenal lendo IMC do catálogo | ✅ OK | `/medicao/obra/342` exibe os 2 itens criados pela propagação Task #82 (Alvenaria 1/2 vez R$3.946,50, Item manual R$1.500,00) |
| 11 | Contas a receber + Fluxo de caixa | ❌ QUEBRADO | **Bugs #1 e #2** — ambas as listagens explodem em 500 (TypeError `sum(NULL)`). ContaReceber 49 foi criada corretamente no banco, mas é impossível visualizá-la na UI. |
| 12 | Cotação / Mapa de Concorrência V2 | ⏭️ Pulado | Rota admin `/obras/<id>/mapa-v2/<mapa_id>/editar` documentada no `replit.md` não foi localizada via grep em `views/obras.py`; precisa ser verificada antes de escrever passo-a-passo |
| 13 | Portal do Cliente | ⚠️ PARCIAL | Portal renderiza 200 e mostra "Construção teste E2E", Cronograma e Mapa — **mas Bug #4**: a obra criada via propagação fica com `token_cliente=NULL`, então o link nunca é gerável até alguém atribuir o token via SQL ou outro fluxo |
| 14 | Auditoria de duplicações de menu | ✅ Identificado | Dropdown legado "Serviços" no header convive com a aba "Catálogo" — Task #87 já proposta |
| 15 | Manual + Relatório + entrega | ✅ Concluído | Este relatório + `docs/manual-ciclo-completo.md` |

---

## 2. Resposta à pergunta-chave

> **A medição cria conta a receber automaticamente?**

**Não.** O ciclo atual cria a `ContaReceber` no momento da **aprovação da proposta** (handler `gerar_contas_receber_proposta` no `event_manager.py`), não no fechamento da medição. A medição quinzenal (`services/medicao_service.py::fechar_medicao`) gera apenas o **extrato em PDF** e marca a medição como FECHADA — não há criação adicional de `ContaReceber` por parcela. Isso significa que:

- Existe **uma única** ContaReceber por proposta aprovada, com valor igual ao total da proposta e vencimento padrão de 30 dias após a aprovação.
- A medição quinzenal serve hoje apenas para **medir o avanço físico/financeiro**; ela não particiona a ContaReceber em parcelas pelos valores medidos.
- Se a regra de negócio desejada for "cada medição fechada vira uma parcela a receber", isso ainda **não está implementado** e deve virar uma task nova.

---

## 3. Bugs encontrados (alta para baixa severidade)

### 🔴 BUG #3 — CRÍTICO — Aprovação de proposta nunca dispara o evento `proposta_aprovada`
- **Arquivo/linhas:** `propostas_consolidated.py:551-613` (rota `/<id>/status`, JSON) e `propostas_consolidated.py:994-1027` (rota `/aprovar/<id>`, form). Versão legada `propostas_views.py:954` idem.
- **Sintoma:** clicar "Aprovar" na UI altera o status da proposta mas **NÃO** cria Obra, **NÃO** cria ContaReceber, **NÃO** cria lançamento contábil, **NÃO** cria `ItemMedicaoComercial` e **NÃO** cria `ObraServicoCusto`. Toda a propagação Task #82 fica morta. Os handlers `gerar_contas_receber_proposta` e `handle_proposta_aprovada` estão registrados em `EventManager._handlers['proposta_aprovada']` (2 listeners), mas nenhuma rota chama `EventManager.emit('proposta_aprovada', …)`.
- **Evidência:** grep `EventManager.emit.*proposta_aprovada` no código vivo do app não retorna nenhum match (apenas em `attached_assets/` e `archive/`). Ao emitir manualmente via shell Python, todos os handlers funcionaram e Obra 342 + ContaReceber 49 + IMC + OSC foram criados corretamente.
- **Impacto:** quebra ponta-a-ponta o ciclo proposta→obra→custos→financeiro para qualquer admin no fluxo padrão.
- **Correção sugerida:** acrescentar `EventManager.emit('proposta_aprovada', {...}, admin_id)` logo após `db.session.commit()` em `alterar_status` quando `novo_status == 'APROVADA'`, e idem em `aprovar()` (que ainda usa `'aprovada'` lowercase — também precisa ser uppercase).

### 🔴 BUG #1 — CRÍTICO — `/financeiro/contas-receber` retorna 500
- **Arquivo/linha:** `financeiro_views.py:295` — `sum(c.saldo for c in contas)` falha quando `c.saldo` é `None`.
- **Sintoma:** página inteira não abre. ContaReceber 49 (legítima, criada pelo handler) está no banco mas é invisível na UI.
- **Stacktrace:** `TypeError: unsupported operand type(s) for +: 'int' and 'NoneType'`.
- **Correção sugerida:** `sum((c.saldo or 0) for c in contas)` ou COALESCE no SQL.

### 🔴 BUG #2 — CRÍTICO — `/financeiro/fluxo-caixa` retorna 500
- **Arquivo/linha:** `financeiro_service.py:437` (chamado por `financeiro_views.py:519`). Mesma causa do bug #1 — soma com `None`.
- **Impacto:** módulo de fluxo de caixa todo inacessível.

### 🟠 BUG #4 — ALTA — Obra criada via aprovação de proposta nasce sem `token_cliente`
- **Arquivo:** `event_manager.py::gerar_contas_receber_proposta` (linhas ~798/825) — cria a `Obra` mas não popula `token_cliente`. Também não atualiza `proposta.obra_id` nem marca `proposta.convertida_em_obra=True`.
- **Sintoma:** o portal do cliente é inacessível para a obra recém-criada (a rota `/portal/obra/<token>` não tem token para receber). Ainda, como `proposta.obra_id` continua NULL, a Task #82 (`_propagar_proposta_para_obra`) sai imediatamente no early-return e **nenhum** `ItemMedicaoComercial` é criado mesmo que o evento seja emitido.
- **Workaround usado no teste:** `UPDATE obra SET token_cliente='e2eq13qr5tok' WHERE id=342;` e `UPDATE propostas_comerciais SET obra_id=342, convertida_em_obra=true WHERE id=115;`.

### 🟡 BUG #5 — MÉDIA — Item de proposta criado a partir do catálogo perde o `servico_id`
- **Sintoma:** ao criar a proposta #115 com 2 itens (item 1 "Alvenaria 1/2 vez" oriundo do serviço 355), o campo `servico_id` em `proposta_itens` ficou NULL para os dois itens, embora a UI exibisse o serviço selecionado no item 1.
- **Hipótese:** o form de "Nova Proposta" (`templates/propostas/...`) provavelmente não envia o `servico_id` do row do catálogo (input hidden ausente ou nome divergente do esperado em `propostas_consolidated.py`).
- **Impacto:** quebra a rastreabilidade catálogo → proposta → medição comercial; o ObraServicoCusto correspondente perde `servico_catalogo_id` e a comparação de margem real não funciona.

### 🟡 BUG #6 — MÉDIA — Rota `/obras/<id>/mapa-v2` não existe (esperada pelo `replit.md`)
- **Sintoma:** `GET /obras/342/mapa-v2` → 404; o `replit.md` documenta `/obras/<obra_id>/mapa-v2/<mapa_id>/editar` em `views/obras.py`, mas grep não encontra `@obras_bp.route(...mapa...)` lá.
- **Provável causa:** rotas residem em outro blueprint não localizado nesta sessão; a documentação ou o registro do blueprint precisa ser corrigido. Bloqueou a etapa 12.

### 🟢 BUG #7 — BAIXA — Header V2 ainda exibe dropdown legado "Serviços"
- Já existe Task #87 proposta para esconder o menu antigo. O caminho oficial é a aba "Catálogo".

---

## 4. O que ficou validado de ponta a ponta (apesar dos bugs)

Quando os ajustes manuais de banco (apenas dados) são aplicados, **a propagação Task #82 funciona 100%**:

```
Proposta 115 (status=APROVADA, obra_id=342)
  └─ EventManager.emit('proposta_aprovada', ..., admin_id=63)
      ├─ handler gerar_contas_receber_proposta  → Obra 342 + ContaReceber 49 (R$ 5.446,50)
      └─ handler handle_proposta_aprovada
          ├─ LancamentoContabil + 2 PartidaContabil (1.1.02.001 / 4.1.01.001)
          └─ _propagar_proposta_para_obra
              ├─ ItemMedicaoComercial 156 "Item manual q13qr5"   R$ 1.500,00
              └─ ItemMedicaoComercial 157 "Alvenaria 1/2 vez"   R$ 3.946,50  servico_id=355
                  └─ listener after_insert ObraServicoCusto:
                      ├─ OSC 153 "Item manual q13qr5"   valor_orcado=1.500,00
                      └─ OSC 154 "Alvenaria 1/2 vez"   valor_orcado=3.946,50  servico_catalogo_id=355
```

A página `/medicao/obra/342` lê esses itens corretamente e o portal cliente (`/portal/obra/<token>`) renderiza com os dados certos. Ou seja, **a arquitetura do ciclo está implementada — falta apenas conectar o gatilho na rota de aprovação e ajustar 4 pontos para que o operador final consiga usar sem intervenção manual**.

---

## 5. Tarefas de follow-up sugeridas

1. **Fix #3** — emitir `proposta_aprovada` em `propostas_consolidated.py::alterar_status` quando status novo for `APROVADA` (e padronizar `aprovar()` para uppercase). _(maior prioridade)_
2. **Fix #1/#2** — usar `(x or 0)` ou `COALESCE` em `financeiro_views.py:295` e `financeiro_service.py:437`.
3. **Fix #4** — em `gerar_contas_receber_proposta`, ao criar a `Obra`: setar `token_cliente=secrets.token_urlsafe(16)` e atualizar `proposta.obra_id` + `proposta.convertida_em_obra=True` antes do commit.
4. **Fix #5** — auditar o form de proposta para garantir que o `<input type="hidden" name="servico_id">` seja enviado para cada linha vinda do catálogo, e que `propostas_consolidated.py` persista o campo em `PropostaItem.servico_id`.
5. **Fix #6** — confirmar/criar as rotas admin do Mapa V2 documentadas no `replit.md` (ou atualizar o `replit.md` para refletir onde realmente vivem).
6. **Esclarecer regra de negócio:** medição quinzenal deve gerar parcela em ContaReceber? Hoje não gera.
