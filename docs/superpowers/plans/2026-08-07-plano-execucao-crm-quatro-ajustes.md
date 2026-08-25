# Plano de execução — CRM, os quatro ajustes — 2026-08-07

> **Estado em 2026-08-25 (varredura de fecho):** ✅ **FECHADO** — entregue. 🔬 5/5 dos arquivos prometidos existem na árvore.
>
> Não há trabalho pendente aqui. **As caixas `- [ ]` abaixo não foram marcadas de propósito:** elas são
> rascunho de execução, não registro de estado. Quem carrega a verdade é este bloco,
> o `ESTADO-ATUAL.md`, o código e o git. O veredito acima foi dado por **existência de
> arquivo na árvore**, nunca por contagem de caixa.


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

- [x] **Step 1 (red):** escrever os testes 1, 1b, 1c e 3 do spec:
  - tenant com `crm_origem` populada e **sem** `DropdownGrupo` → `_listas_para_form`
    devolve as origens legadas (hoje `[]`);
  - grupo criado por `ensure_grupo` e **sem nenhuma linha** em `dropdown_opcao` → idem;
  - grupo com opções **todas com `ativo=False`** → devolve `[]` (não ressuscita);
  - `_migration_282` num tenant torto cria grupo + opções com `ext_id` = id legado.
  Rodar e **ver os quatro vermelhos**.
- [x] **Step 2:** fallback em `get_dropdown_options` (`services/dropdown_service.py`):
  quando `slug in _CRM_MODELO_MAP` e (grupo ausente **ou** `DropdownOpcao` com zero
  linhas no grupo — contando inativas), ler o modelo legado via `_CRM_MODELO_MAP`,
  filtrar `ativo=True`, devolver wrappers com `id` (id legado), `nome`, `valor`,
  `ativo`. Log `INFO` com slug e admin_id.
- [x] **Step 3:** migração **282** em `migrations.py` —
  `_migration_282_backfill_dropdown_crm`, registrada na lista de migrações com o número
  282 (⚠️ conferir `migration_history` antes: lição da B6.1 — o 281 já estava aplicado
  no dev antes do commit existir). Para cada slug de `CRM_GRUPOS_META`: `INSERT` do
  grupo por `SELECT DISTINCT admin_id` da tabela legada `WHERE NOT EXISTS` o grupo;
  depois o mesmo `INSERT ... SELECT ... WHERE NOT EXISTS` da 174 (que agora casa,
  porque o grupo existe). Idempotente nas duas etapas.
- [x] **Step 4 (green + mutação):** os quatro testes verdes + teste 2 (rodar a 282 duas
  vezes não duplica). Mutação de sanidade: inverter o predicado "zero linhas" para
  "zero ativas" e confirmar que o teste 1c **mata** a mutação.
- [x] **Step 5:** aplicar a 282 no banco de dev, conferir por psql: grupos `crm_*`
  criados, opções com `ext_id`, contagens batendo com as tabelas legadas.
- [x] **Step 6:** commit — `fix(crm): dropdowns voltam a aparecer — migracao 282 faz o
  backfill que a 174 pulou e o leitor ganha fallback ao legado`

## C2 — A tag "Validado" some de Enviado em diante

- [x] **Step 1 (red):** testes 4 e 5 do spec: lead `validacao_aprovada=True` em
  **Enviado** → HTML do kanban sem "Validado" (hoje contém); o mesmo lead em
  **Validação** → HTML **com** "Validado" (guarda contra esconder demais). Cobrir
  também a lista (`crm.lista`). Vermelho.
- [x] **Step 2:** lista positiva num único lugar — `pode_exibir_validado(lead)` em
  `crm_views.py` (status em `{EM_FILA, EM_ANDAMENTO, VALIDACAO}`), exposta aos dois
  templates. Aplicar no badge do card (`kanban.html`, classe `crm-card--validado` e o
  `crm-validado-badge`), no badge da `lista.html` e no botão "Marcar como Validado"
  (`btn-validar-lead`), que sai de lead pós-envio.
- [x] **Step 3 (green):** testes verdes. `validacao_aprovada`, `validado_por_id` e
  `validado_em` **intocados** — conferir no diff que nenhum escritor foi criado.
- [x] **Step 4:** commit — `fix(crm): a tag Validado e o botao de validar somem do lead
  ja enviado; auditoria preservada`

## C3 — Prazo de 3 dias úteis

- [x] **Step 1 (red):** testes 6, 7 e 8 do spec: lead novo por POST sem `prazo` →
  `prazo == data_chegada + 3 úteis` (hoje `None`); **chegada quinta → prazo terça**
  (o caso que mata a soma de dias corridos); editar lead existente sem tocar no prazo
  não recalcula. Vermelho.
- [x] **Step 2:** `somar_dias_uteis(data, n)` em `utils.py`, ao lado dos cálculos de
  `dias_uteis` que já existem lá (`weekday() < 5`, sem feriado). Teste unitário
  próprio da travessia de fim de semana.
- [x] **Step 3:** garantia no servidor — em `_salvar_lead` (`crm_views.py`), no ramo
  `is_new`, depois de `data_chegada` resolvida: `prazo` vazio recebe
  `somar_dias_uteis(lead.data_chegada, 3)`.
- [x] **Step 4:** pré-preenchimento visual — a rota `novo` passa `default_data_chegada`
  (hoje) e `default_prazo` ao template; os inputs `data_chegada` e `prazo` de
  `lead_form.html` usam o default quando `lead` é `None` (hoje renderizam em branco).
- [x] **Step 5 (green):** os três verdes. Sem backfill — nenhum UPDATE em lead
  existente no diff (D-CRM.4).
- [x] **Step 6:** commit — `feat(crm): lead novo nasce com prazo sugerido de 3 dias
  uteis apos a chegada, editavel`

## C4 — Exportação Excel

- [x] **Step 1 (red):** testes 9, 10 e 11 do spec: admin de um tenant com N leads
  recebe xlsx (abrir com `openpyxl` no teste) com aba **`Leads`**, N linhas e as 37
  colunas do spec, **ignorando** `?status=`/`?busca=` na query string; lead do
  segundo tenant ausente; não-admin barrado com redirect. Vermelho (rota não existe).
- [x] **Step 2:** rota `GET /crm/exportar` em `crm_views.py`, admin-only no padrão de
  `exportar_modelo` (`flash` + redirect). Query: `_query_leads_visiveis(admin_id)`
  **sem** `_aplicar_filtros`, ordem da lista (`data_chegada` desc, `id` desc).
- [x] **Step 3:** a planilha do spec — aba `Leads`; 37 colunas na ordem dos grupos;
  FKs pelo nome; `Sim`/`Não` para booleanos; número `R$ #,##0.00` no valor; datas
  `DD/MM/AAAA`; cabeçalho `1F4E79` branco/negrito; **AutoFiltro** na faixa toda;
  `freeze_panes='D2'`; larguras por tipo de coluna; zebra; célula de `Status` tingida
  com as cores do kanban (as mesmas dos seletores `.status-*` de `kanban.html`:
  `#6c757d`, `#0dcaf0`, `#0d6efd`, `#6f42c1`, `#198754`, `#fd7e14`, `#495057`,
  `#dc3545`); `Dias parado no status` derivado de `status_changed_at`; arquivo
  `leads_crm_AAAA-MM-DD.xlsx`. Sem lead → só cabeçalho, sem erro.
  Evitar N+1: `joinedload`/`selectinload` das nove relações de lista + cliente,
  proposta, obra, criado_por, validado_por.
- [x] **Step 4:** botão "Exportar Leads" em `lista.html`, dentro do bloco
  `{% if is_admin %}` existente, ao lado de "Baixar Modelo".
- [x] **Step 5 (green):** os três verdes.
- [x] **Step 6:** commit — `feat(crm): exportacao xlsx de todos os leads com todos os
  campos, com autofiltro e paineis congelados`

## Fecho

- [x] **F1:** suíte do arquivo novo inteira + `tests/test_cadeia_crm_proposta_obra_lead.py`
  (vizinho direto do módulo) verdes.
- [x] **F2:** gate completo. Linha de base herdada da B6: 1981 passed / 2 failed
  alheias (`test_custo_diario` ordem-dependente; `test_excluir_obra` ponta solta da
  E02). **Falha nova = investigar antes de fechar.**
- [x] **F3:** rodar `python scripts/rastreio_modulos.py` — a rota nova muda a contagem
  do CRM no `MODULOS.md`, e contador de região gerada não se edita à mão (lição WF-4).
  Atualizar a tabela manual de rotas do CRM no mesmo arquivo (22 → 23 rotas).
- [x] **F4:** Status/checkboxes neste plano + commit de docs. Push espera o Cássio.

## Registro

Preenchido durante a execução — um hash por item, nenhum antes do commit existir.

| Item | Commit | Status |
|---|---|---|
| C1 dropdowns | `328218c1` | **FEITO** |
| C2 tag Validado | `6fbcd9a3` | **FEITO** |
| C3 prazo 3 úteis | `add4ce72` | **FEITO** |
| C4 exportação | `b008c9fc` | **FEITO** |
| Fecho/docs | — | **FEITO** (este commit) |

## FECHO — 2026-08-07

**Os quatro ajustes entregues, red-first em todos.** 18 testes novos em
`tests/test_crm_quatro_ajustes.py` (os casos do spec + guardas), todos verdes;
`tests/test_cadeia_crm_proposta_obra_lead.py` intacto (31 passed no conjunto).

**O gate completo: 2001 passed, 1 failed, 6 skipped, 2 xfailed (30:48).**
A única falha é a **CONHECIDA**: `test_excluir_obra::
test_lista_cobre_toda_fk_no_action_para_obra`, a FK do `notificacao_cliente` —
ponta solta da E02, pré-existente, decisão do Cássio pendente (item 14 do §4 da
rodada B6). A `test_custo_diario::test_4` desta vez **passou** — consistente com
o diagnóstico de dependência de ordem (item 15 do mesmo §4): ela oscila com a
ordem do gate, não com este trabalho. **Nenhuma falha nova.**

**Desvios do plano: nenhum de comportamento.** Três notas de execução:

1. ⚠️ **`from utils import ...` resolve para o PACOTE `utils/`, não para
   `utils.py`.** O `__init__` do pacote carrega `utils.py` por spec-loader e
   reexporta uma lista CURADA de funções — helper novo em `utils.py` é invisível
   até entrar na lista. `somar_dias_uteis` entrou, e o ramo de fallback do try
   ganhou implementação real em vez de dummy (um dummy plantaria prazo errado em
   silêncio). Primeira rodada a tropeçar nisso; fica o aviso para as próximas.
2. **Desvio a menor no C2:** o botão "Marcar como Validado" já estava confinado
   à coluna Validação (`{% if col.nome == 'Validação' %}` no kanban) — não havia
   o que consertar; o teste do botão ficou como guarda. Só os badges (kanban +
   lista) precisavam da regra nova.
3. **A mutação do C1 matou como previsto:** trocar "zero linhas" por "zero
   ativas" no predicado do fallback derruba o teste 1c. A lição da WF-4 (guarda
   sem o dado que ela guarda é guarda vazia) aplicada ANTES do erro, não depois.

**A migração 282 está APLICADA e registrada no dev** (`migration_history`,
07/08), conferida por psql: tenant 1 com 7 grupos `crm_*` e 36 opções, `ext_id`
1:1 com as tabelas legadas. Os ~355 tenants-fantasma (1 lead avulso, nenhuma
linha em `crm_*`) corretamente não ganharam grupo — e se algum usar o CRM um
dia, o fallback do leitor cobre.

**`MODULOS.md` regenerado** pelo `rastreio_modulos.py` — CRM em **23 rotas**
com `/exportar`; nenhum contador editado à mão.

**O que este trabalho NÃO tocou:** `views/obras.py`, `propostas_consolidated.py`,
`frota_views.py`, `views/rdo.py` e `rdo_editar_sistema.py` — os arquivos da F2
da rodada B6 seguem virgens; a pausa não contaminou a rodada. **`RETOMAR ARREIO
B6` continua válida**, e o gate que ela manda re-rodar deve encontrar
**2001/1 como nova linha de base** (a segunda falha da base velha era a
ordem-dependente, que oscila).

## Histórico

- **2026-08-07** — plano escrito a partir do spec aprovado; execução autorizada
  pelo Cássio ("pode seguir") na mesma sessão e concluída. Fecho acima.
