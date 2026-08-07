# Plano de execução — CRM, os quatro ajustes — 2026-08-07

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans`.

**O que é.** O plano de execução do spec
`docs/superpowers/specs/2026-08-07-crm-quatro-ajustes-design.md`. As decisões
(D-CRM.1 a D-CRM.6) e o diagnóstico vivem lá e não são repetidos; quando divergirem,
**o spec vence**.

**Contexto de rodada.** Este trabalho é parte dos "ajustes específicos" da **pausa da
rodada B6** (07/08) — a frase `RETOMAR ARREIO B6` segue válida e reabre a F2 daquele
plano depois. A B6 exigirá re-rodar o gate ao retomar **por causa deste trabalho**.

**As fronteiras de sempre:**
1. **`main` não anda.** Tudo em `test/b0-arreio`; push e fast-forward esperam o Cássio.
2. **Âncoras por símbolo + literal**, nunca número de linha (política da WF-4).
3. **Red-first**: nenhum conserto sem ver o teste vermelho antes.

## Ordem e independência

C1 (dropdowns) → C2 (badge) → C3 (prazo) → C4 (exportação). As quatro são
independentes; a ordem é do spec (defeito que trava cadastro primeiro, feature maior
por último). C3 e C4 tocam `crm_views.py` em regiões distintas (`_salvar_lead` × rota
nova) — sem conflito, mas serial mesmo assim.

Os testes novos vivem em **`tests/test_crm_quatro_ajustes.py`**, no molde de
`tests/test_cadeia_crm_proposta_obra_lead.py` (fixtures `um_tenant`/`dois_tenants` de
`helpers_tenant`, `pytestmark = pytest.mark.integration`, um único tenant autor dos
requests por teste).

---

## C1 — Dropdowns vazios (migração 282 + fallback)

- [ ] **Step 1 (red):** escrever os testes 1, 1b, 1c e 3 do spec:
  - tenant com `crm_origem` populada e **sem** `DropdownGrupo` → `_listas_para_form`
    devolve as origens legadas (hoje `[]`);
  - grupo criado por `ensure_grupo` e **sem nenhuma linha** em `dropdown_opcao` → idem;
  - grupo com opções **todas com `ativo=False`** → devolve `[]` (não ressuscita);
  - `_migration_282` num tenant torto cria grupo + opções com `ext_id` = id legado.
  Rodar e **ver os quatro vermelhos**.
- [ ] **Step 2:** fallback em `get_dropdown_options` (`services/dropdown_service.py`):
  quando `slug in _CRM_MODELO_MAP` e (grupo ausente **ou** `DropdownOpcao` com zero
  linhas no grupo — contando inativas), ler o modelo legado via `_CRM_MODELO_MAP`,
  filtrar `ativo=True`, devolver wrappers com `id` (id legado), `nome`, `valor`,
  `ativo`. Log `INFO` com slug e admin_id.
- [ ] **Step 3:** migração **282** em `migrations.py` —
  `_migration_282_backfill_dropdown_crm`, registrada na lista de migrações com o número
  282 (⚠️ conferir `migration_history` antes: lição da B6.1 — o 281 já estava aplicado
  no dev antes do commit existir). Para cada slug de `CRM_GRUPOS_META`: `INSERT` do
  grupo por `SELECT DISTINCT admin_id` da tabela legada `WHERE NOT EXISTS` o grupo;
  depois o mesmo `INSERT ... SELECT ... WHERE NOT EXISTS` da 174 (que agora casa,
  porque o grupo existe). Idempotente nas duas etapas.
- [ ] **Step 4 (green + mutação):** os quatro testes verdes + teste 2 (rodar a 282 duas
  vezes não duplica). Mutação de sanidade: inverter o predicado "zero linhas" para
  "zero ativas" e confirmar que o teste 1c **mata** a mutação.
- [ ] **Step 5:** aplicar a 282 no banco de dev, conferir por psql: grupos `crm_*`
  criados, opções com `ext_id`, contagens batendo com as tabelas legadas.
- [ ] **Step 6:** commit — `fix(crm): dropdowns voltam a aparecer — migracao 282 faz o
  backfill que a 174 pulou e o leitor ganha fallback ao legado`

## C2 — A tag "Validado" some de Enviado em diante

- [ ] **Step 1 (red):** testes 4 e 5 do spec: lead `validacao_aprovada=True` em
  **Enviado** → HTML do kanban sem "Validado" (hoje contém); o mesmo lead em
  **Validação** → HTML **com** "Validado" (guarda contra esconder demais). Cobrir
  também a lista (`crm.lista`). Vermelho.
- [ ] **Step 2:** lista positiva num único lugar — `pode_exibir_validado(lead)` em
  `crm_views.py` (status em `{EM_FILA, EM_ANDAMENTO, VALIDACAO}`), exposta aos dois
  templates. Aplicar no badge do card (`kanban.html`, classe `crm-card--validado` e o
  `crm-validado-badge`), no badge da `lista.html` e no botão "Marcar como Validado"
  (`btn-validar-lead`), que sai de lead pós-envio.
- [ ] **Step 3 (green):** testes verdes. `validacao_aprovada`, `validado_por_id` e
  `validado_em` **intocados** — conferir no diff que nenhum escritor foi criado.
- [ ] **Step 4:** commit — `fix(crm): a tag Validado e o botao de validar somem do lead
  ja enviado; auditoria preservada`

## C3 — Prazo de 3 dias úteis

- [ ] **Step 1 (red):** testes 6, 7 e 8 do spec: lead novo por POST sem `prazo` →
  `prazo == data_chegada + 3 úteis` (hoje `None`); **chegada quinta → prazo terça**
  (o caso que mata a soma de dias corridos); editar lead existente sem tocar no prazo
  não recalcula. Vermelho.
- [ ] **Step 2:** `somar_dias_uteis(data, n)` em `utils.py`, ao lado dos cálculos de
  `dias_uteis` que já existem lá (`weekday() < 5`, sem feriado). Teste unitário
  próprio da travessia de fim de semana.
- [ ] **Step 3:** garantia no servidor — em `_salvar_lead` (`crm_views.py`), no ramo
  `is_new`, depois de `data_chegada` resolvida: `prazo` vazio recebe
  `somar_dias_uteis(lead.data_chegada, 3)`.
- [ ] **Step 4:** pré-preenchimento visual — a rota `novo` passa `default_data_chegada`
  (hoje) e `default_prazo` ao template; os inputs `data_chegada` e `prazo` de
  `lead_form.html` usam o default quando `lead` é `None` (hoje renderizam em branco).
- [ ] **Step 5 (green):** os três verdes. Sem backfill — nenhum UPDATE em lead
  existente no diff (D-CRM.4).
- [ ] **Step 6:** commit — `feat(crm): lead novo nasce com prazo sugerido de 3 dias
  uteis apos a chegada, editavel`

## C4 — Exportação Excel

- [ ] **Step 1 (red):** testes 9, 10 e 11 do spec: admin de um tenant com N leads
  recebe xlsx (abrir com `openpyxl` no teste) com aba **`Leads`**, N linhas e as 37
  colunas do spec, **ignorando** `?status=`/`?busca=` na query string; lead do
  segundo tenant ausente; não-admin barrado com redirect. Vermelho (rota não existe).
- [ ] **Step 2:** rota `GET /crm/exportar` em `crm_views.py`, admin-only no padrão de
  `exportar_modelo` (`flash` + redirect). Query: `_query_leads_visiveis(admin_id)`
  **sem** `_aplicar_filtros`, ordem da lista (`data_chegada` desc, `id` desc).
- [ ] **Step 3:** a planilha do spec — aba `Leads`; 37 colunas na ordem dos grupos;
  FKs pelo nome; `Sim`/`Não` para booleanos; número `R$ #,##0.00` no valor; datas
  `DD/MM/AAAA`; cabeçalho `1F4E79` branco/negrito; **AutoFiltro** na faixa toda;
  `freeze_panes='D2'`; larguras por tipo de coluna; zebra; célula de `Status` tingida
  com as cores do kanban (as mesmas dos seletores `.status-*` de `kanban.html`:
  `#6c757d`, `#0dcaf0`, `#0d6efd`, `#6f42c1`, `#198754`, `#fd7e14`, `#495057`,
  `#dc3545`); `Dias parado no status` derivado de `status_changed_at`; arquivo
  `leads_crm_AAAA-MM-DD.xlsx`. Sem lead → só cabeçalho, sem erro.
  Evitar N+1: `joinedload`/`selectinload` das nove relações de lista + cliente,
  proposta, obra, criado_por, validado_por.
- [ ] **Step 4:** botão "Exportar Leads" em `lista.html`, dentro do bloco
  `{% if is_admin %}` existente, ao lado de "Baixar Modelo".
- [ ] **Step 5 (green):** os três verdes.
- [ ] **Step 6:** commit — `feat(crm): exportacao xlsx de todos os leads com todos os
  campos, com autofiltro e paineis congelados`

## Fecho

- [ ] **F1:** suíte do arquivo novo inteira + `tests/test_cadeia_crm_proposta_obra_lead.py`
  (vizinho direto do módulo) verdes.
- [ ] **F2:** gate completo. Linha de base herdada da B6: 1981 passed / 2 failed
  alheias (`test_custo_diario` ordem-dependente; `test_excluir_obra` ponta solta da
  E02). **Falha nova = investigar antes de fechar.**
- [ ] **F3:** rodar `python scripts/rastreio_modulos.py` — a rota nova muda a contagem
  do CRM no `MODULOS.md`, e contador de região gerada não se edita à mão (lição WF-4).
  Atualizar a tabela manual de rotas do CRM no mesmo arquivo (22 → 23 rotas).
- [ ] **F4:** Status/checkboxes neste plano + commit de docs. Push espera o Cássio.

## Registro

Preenchido durante a execução — um hash por item, nenhum antes do commit existir.

| Item | Commit | Status |
|---|---|---|
| C1 dropdowns | — | pendente |
| C2 tag Validado | — | pendente |
| C3 prazo 3 úteis | — | pendente |
| C4 exportação | — | pendente |
| Fecho/docs | — | pendente |

## Histórico

- **2026-08-07** — plano escrito a partir do spec aprovado. **Execução ainda não
  autorizada** — aguarda o "vai" do Cássio.
