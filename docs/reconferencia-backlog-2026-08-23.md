# Reconferência do backlog de automações — 2026-08-23

> Reconfere, item a item e contra o código de HOJE (`main` em `2e40f8b0`), os
> 25 itens de `docs/reconferencia-backlog-2026-08-04.md` §3 — que estava com
> 19 dias e "zero entregues, 25 vivas". Método: 4 auditores independentes
> (A01-07, A08-13, A14-19, A20-25), cada citação `arquivo:linha` reaberta no
> código atual e o histórico dos arquivos varrido desde 04/08.
>
> ⚠️ **Nota de método que vale para o repositório inteiro:** `git log
> --since=<data>` aqui **omite commits silenciosamente** (histórico não
> estritamente cronológico pós-rebase; confirmado com `060146ac`). As
> conferências usaram `git log --date=short | awk '$2 >= "2026-08-04"'`.

## A manchete

Dos 25 itens "vivos" em 04/08: **9 foram entregues** pelo trabalho das últimas
semanas (sem ninguém atualizar a lista), **7 estão parciais** (vários com
recorte bem menor que o registrado) e **9 seguem exatamente como estavam**.

| Veredito hoje | Itens |
|---|---|
| ✅ **ENTREGUE** (9) | A02, A03, A05, A06, A07, A09, A10, A14, A19 |
| 🟡 **PARCIAL** (7) | A11, A13 (quase fechado), A15, A16, A18*, A22, A24* |
| 🔴 **ABERTO** (9) | A01, A04*, A08, A12, A17, A20, A21, A23, A25* |

\* Travados por decisão humana ou credencial, não por falta de braço:
**A04** (conta de débito da despesa geral — pergunta do contador),
**A18** (Decisão 4), **A24** (rateio dos encargos: o pipeline está correto
desde 05/08 — bug aritmético corrigido — mas **segue sem nenhum chamador**;
a mão de obra continua ~28% subestimada até alguém decidir ligá-lo),
**A25** (`N8N_WEBHOOK_URL` + job no scheduler — segura toda notificação).

## O placar por lote

| Item | 04/08 → hoje | Uma linha |
|---|---|---|
| A01 | ABERTO → ABERTO | Confirm da importação segue sem ler `payload['transferencias']` |
| A02 | ABERTO → ✅ | Baixa de ContaReceber grava `FluxoCaixa` ENTRADA (`95912e7c`, 05/08) |
| A03 | ABERTO → ✅ | CR de medição nasce com `conta_contabil_codigo` (`352719a0`, 05/08) |
| A04 | ABERTO → ABERTO | `MAPEAMENTO_CONTABIL` segue sem `DESPESA_GERAL` (decisão do contador) |
| A05 | PARCIAL → ✅ | Os 4 caminhos emitem `rdo_finalizado`; fechado em 21/08 (`ee1c99b5`), 15/15 verdes |
| A06 | ABERTO → ✅ | `_replanejar_pos_commit` nos 7 pontos de escrita do editor v2 (05/08), 16/16 |
| A07 | ABERTO → ✅ | `?cliente_id=`/`?lead_id=` pré-preenchem proposta/obra (`1394d907`, 05/08), 13/13 |
| A08 | ABERTO → ABERTO | Importação de alimentação segue sem gerar custo |
| A09 | ABERTO → ✅ | `entrada_ja_lancada` guarda as 2 rotas de entrada manual (resta só bug em código morto sem chamador) |
| A10 | MUDOU_DE_FORMA → ✅ | `/novo_ponto` reusa o registro do dia; perda de custo do turno partido resolvida, com testes |
| A11 | PARCIAL → 🟡 menor | Chave cruzada unificada; falta só a guarda RDO×ponto no ramo horista |
| A12 | ABERTO → ABERTO | Reprocesso de folha segue `delete()` puro, sem estorno |
| A13 | PARCIAL → 🟡 quase | Os 5 consumidores residuais corrigidos; falta a origem (decisão adiada) + edge de 3,2% |
| A14 | PARCIAL → ✅ | 3º caminho de `handle_proposta_aprovada` semeia serviços e fecha lead; 27 testes |
| A15 | PARCIAL → 🟡 | Portal ainda gera `MedicaoObra` paralela sem itens/recalculo |
| A16 | PARCIAL → 🟡 menor | Ausência classificada preservada; sync alocação→ponto segue sem evento |
| A17 | ABERTO → ABERTO | `novo_rdo` segue carregando todos os funcionários do tenant |
| A18 | PARCIAL → 🟡 | Travado pela Decisão 4; rota legada segue sem `subatividade_mestre_id` |
| A19 | PARCIAL → ✅ | As 7 variantes V1 convergiram (`progresso_v1_acumulado`/`obra_em_modo_v2`); 25 testes |
| A20 | ABERTO → ABERTO | Pedido segue lendo `fornecedor_id` cru, sem tocar mapa V2 |
| A21 | ABERTO → ABERTO | `RDOEquipamento` sem `veiculo_id`; kwargs inválidos em função sem rota |
| A22 | ABERTO → 🟡 | Select de cliente entregue (05/08); CPF/CNPJ segue sem coluna |
| A23 | ABERTO → ABERTO | Rotas do portal seguem sem aviso interno (sem canal para plugar) |
| A24 | ABERTO → 🟡 | Aritmética corrigida (05/08); pipeline segue SEM CHAMADOR — MO ~28% subestimada |
| A25 | ABERTO → ABERTO | Zero commits; travado por `N8N_WEBHOOK_URL` + `add_job` |

## A lista de trabalho real que sobra (sem decisões humanas)

Em ordem de dor provável: **A12** (reprocesso de folha sem estorno — risco de
custo duplicado), **A11** (guarda RDO×ponto no ramo horista), **A01**
(transferências do extrato), **A15** (medição do portal paralela), **A17**
(RDO carregando o tenant inteiro), **A08**, **A23**, **A20**, **A21**, **A22**
(cauda), **A13/A16** (recortes finais).

Decisões que destravam o resto: **A24** (um chamador liga rateio de encargos
já pronto), **A04** (uma resposta do contador), **A25** (uma credencial),
**A18** (Decisão 4).

---

# Detalhamento por item (evidência atual, commits, o que sobra)


## Reconferência A01–A07 — 2026-08-23

> Contra `main` (HEAD atual, branch de trabalho no momento da auditoria era
> `feat/regua-status-unificado`, mas este agente rodou em `main`, que é onde
> vive o grosso do trabalho pós-04/08). Base do documento original:
> `docs/reconferencia-backlog-2026-08-04.md` §3, commit `a723babe` (03/08).
>
> **Nota de método:** `git log --since=<data>` neste repositório **omite
> silenciosamente commits** cujo committer-date é posterior ao `--since` mas
> que aparecem cedo na travessia topológica (rebase/histórico não
> estritamente cronológico) — confirmado com `060146ac` (04/08 16:28 UTC),
> que `--since=2026-08-04` e até `--since=2026-08-03` não devolviam, mas que
> existe e está no histórico de `HEAD`. Toda conferência abaixo usa
> `git log --format='%h %ad %s' --date=short -- <arquivo> | awk '$2 >= "2026-08-04"'`
> em vez de `--since`, para não repetir a omissão.

---

### A01 — ABERTO (04/08) → **ABERTO** (hoje)

Nada mudou. Zero commits em `services/importacao_excel.py`,
`importacao_views.py` ou `templates/importacao/preview_fluxo.html` desde
04/08 (nenhum aparece no log completo do arquivo com data ≥ 2026-08-04).

Evidência atual (linhas driftaram um pouco por edições em rotas vizinhas,
mesmo arquivo/mesma forma):
- `importacao_views.py:773-982` — `fluxo_caixa_confirmar()` (era citada como
  `783-946`). Continua sem tocar `payload['transferencias']` nem ler
  `transf_origem_<i>`/`transf_destino_<i>` do form. Só processa
  `saidas_auto`, `saidas_manual`, `entradas` (linhas 786-788) e chama
  `svc.importar({'entradas':..., 'saidas':..., 'batch_id':...}, admin_id)`
  em `:942-946` — mesmas 3 chaves de antes.
- `services/importacao_excel.py:2129-2137` — docstring do `importar()` do
  service de fluxo de caixa segue documentando só `entradas`/`saidas`/
  `batch_id`; a chave `transferencias` não é aceita.
- `importacao_views.py:453,473,515,550,701` — a detecção e o payload de
  preview continuam existindo (igual ao citado em 04/08), só que nunca são
  lidos no confirm.

O que sobra: exatamente o que o documento original listava — ler o payload +
os campos de form de transferência em `importacao_views.py:773-982`, validar
banco contra o tenant, e fazer `ImportacaoFluxoCaixa.importar` aceitar
`transferencias`.

---

### A02 — ABERTO (04/08) → **ENTREGUE** (hoje)

Entregue por completo em `95912e7c` (05/08, "feat(financeiro): baixa de
conta a receber grava FluxoCaixa ENTRADA") — commit explicitamente rotulado
`B3.8/A02` na própria mensagem.

Evidência atual:
- `financeiro_views.py:792-911` — `receber_conta()`. Depois de
  `FinanceiroService.baixar_recebimento(...)` (`:864-871`), em bloco de
  `try` **próprio** (não desfaz a baixa se falhar), grava
  `FluxoCaixa(tipo_movimento='ENTRADA', categoria='receita',
  referencia_tabela='conta_receber', referencia_id=conta.id,
  obra_id=conta.obra_id, ...)` condicionado a
  `request.form.get('criar_fluxo_caixa') == '1'` (`:883-909`).
- `templates/financeiro/contas_receber.html:260-313` — o modal
  `formBaixaRecebimento` (o POST vivo real, não `receber_conta.html`, que
  segue inalcançável por link — o commit registra essa correção de premissa)
  tem o checkbox `criar_fluxo_caixa` **marcado por padrão** (`:302 checked`)
  e o `<select name="categoria_fluxo_caixa_id">` (`:312`).
- Comentários no próprio código (`financeiro_views.py:798-811`, `:873-882`)
  documentam por que a guarda de conta já liquidada vem *antes* da escrita
  do FluxoCaixa (evita dupla contagem) e por que `obra_id` é preenchido
  (diferente do lado "pagar", que não preenche).

Nada sobra do recorte original. Não roda teste específico neste passo (não
verificado por execução de suíte, só por leitura), mas o código bate
linha a linha com o que o documento pedia.

---

### A03 — ABERTO (04/08) → **ENTREGUE** (hoje)

Entregue em `352719a0` (05/08, "fix(medicao): CR de medicao nasce com conta
contabil (liquidacao de cliente)") — commit rotulado `B3.9/A03`.

Evidência atual:
- `services/medicao_service.py:363-462` — `recalcular_medicao_obra()`
  (função que hoje concentra a criação/UPSERT da CR de medição; a
  numeração de linha do documento original — `:369-383` — havia mudado de
  função entre 03/08 e 04/08, mas é a mesma responsabilidade). Calcula
  `_codigo_alvo = '1.1.02.001' if proposta_origem_id else '4.1.01.001'`
  (`:428`) e resolve via `_resolver_conta_contabil_medicao` (`:311-360`,
  nova função). `conta_contabil_codigo=conta_contabil` é passado no
  construtor da CR nova (`:435`) e, no ramo de update, só preenche quando
  `NULL` — não sobrescreve valor posto à mão (`:461-462`).
- `_resolver_conta_contabil_medicao` (`:311-360`) nunca levanta exceção;
  na falha (conta não confirmada mesmo após seed) loga
  `logger.warning(f"⚠️ [A03] conta contábil {codigo} não existe...")`
  (`:349-353`) — resolve exatamente o "sem log de aviso" que o item citava
  como falta no gate de `financeiro_service.py:332`.
- Único ponto de criação de `ContaReceber(` em `services/medicao_service.py`
  (confirmado por grep) — não há um segundo caminho que ficou de fora.

Nada sobra.

---

### A04 — ABERTO (04/08) → **ABERTO** (hoje, sem mudança)

Nenhum commit tocou `MAPEAMENTO_CONTABIL` desde 04/08 — `contabilidade_utils.py`
só recebeu um commit no período (`08f2ee88`, 06/08, sobre estorno de
recebimento), que não mexe nesse dicionário.

Evidência atual (linhas driftaram):
- `contabilidade_utils.py:1536-1543` — `MAPEAMENTO_CONTABIL` continua com
  exatamente as mesmas seis chaves (`compra_material`,
  `pagamento_fornecedor`, `despesa_alimentacao`, `despesa_transporte`,
  `folha_pagamento`, `pagamento_salario`); `DESPESA_GERAL` **não existe**.
- `gestao_custos_views.py:844` e `:996` (antes `:839-845`/`:987-993`) —
  os dois pagamentos continuam chamando com `tipo_operacao='DESPESA_GERAL'`.
- `contabilidade_utils.py:1695-1698` (antes `1685-1688`) — gate
  `if not mapeamento: logger.warning(...); return False` intacto — falha
  silenciosa idêntica, os `except` dos chamadores não capturam nada porque
  não há exceção, só um `False` de retorno.
- Confirmado que não existe um segundo dicionário/entrada de
  `DESPESA_GERAL` em nenhum lugar do repo (grep vazio fora de `archive/`).

Sem mudança nenhuma. Decisão 5 do `PLANO-NUCLEO.md` segue sem marca de
resolvida (não reverificado aqui além do grep — está fora do escopo do
arquivo de código).

---

### A05 — PARCIAL (04/08) → **ENTREGUE** (hoje)

Os quatro itens do "o que sobra" de 04/08 foram fechados por uma sequência
de commits, a maioria no próprio 04/08 (depois do corte do documento) e o
fechamento final em `ee1c99b5` (21/08):

- `cefba5e7` (04/08) — handler de custo passa a ler `RDOCustoDiario` em vez
  de recalcular por `valor_diaria` → fecha o item (c), a regressão de
  dinheiro perdido para mensalista/horista.
- `060146ac` (04/08) — payload ganha `obra_id`; emit pós-commit → fecha o
  item (a).
- `95041413` (04/08) — mecanismo único de custo, chave larga aprende a
  contar o dia.
- `ee1c99b5` (21/08) — fecha o item (b): `views/rdo.py:3436-3451`
  (`rdo_salvar_unificado`, a rota `POST /rdo/salvar`) agora **emite**
  `rdo_finalizado` com `obra_id`, condicionado a `publica_custos(rdo)`
  (rascunho não lança custo/evento — refinamento novo, não parte do A05
  original, mas não contradiz o recorte).

Evidência atual:
- `event_manager.py:663-728` — `lancar_custos_rdo()`. Comentário explícito
  em `:707-720` narra a própria regressão do B1.1 e a correção: agora chama
  `gravar_custo_funcionario_rdo(rdo, admin_id)` (`:721-728`), que é o único
  lugar que sabe a fórmula por tipo de remuneração (`services/rdo_custos.py`
  via `_custo_diario_rdo`) — mensalista e horista voltam a custear.
- `views/rdo.py:3413-3451` — `rdo_salvar_unificado`: grava custo diário e
  emite `rdo_finalizado` com `{'rdo_id': rdo.id, 'obra_id': rdo.obra_id,
  'data_relatorio': ...}` (`:3440-3444`), ambos guardados por
  `publica_custos(rdo)`.
- `crud_rdo_completo.py:475-497`, `rdo_editar_sistema.py:557-572` — os
  outros três caminhos (`salvar_rdo`, `atualizar_rdo`, `salvar_edicao_rdo`)
  seguem emitindo com `obra_id` no payload (confirmado — já vinha de
  `060146ac`), agora também sob a mesma guarda de `publica_custos`.
- Teste dedicado (parte do item (d), "funcionário `tipo_remuneracao=salario`,
  `valor_diaria=0`"): `tests/test_arreio_custo_rdo_rotas.py` (criado em
  `35975e7a`, 04/08, expandido nos commits seguintes) — helper de perfil
  padrão em `:76-78` usa exatamente `tipo_remuneracao='salario'`,
  `valor_diaria=0.0`. Rodei a suíte agora:
  `pytest tests/test_arreio_custo_rdo_rotas.py tests/test_rdo_rascunho_nao_lanca_custo.py`
  → **15 passed**.

O que sobra fora do recorte original (mencionado como "fora do recorte
literal" no doc de 04/08, e continua fora): `views/rdo.py:771`
(`criar_rdo`, endpoint legado) ainda marca `rdo.status = 'Finalizado'` sem
lançar custo nem emitir evento — mas isso já era explicitamente listado como
fora do escopo do item A05 em 04/08, não como parte do "o que sobra".

---

### A06 — ABERTO (04/08) → **ENTREGUE** (hoje)

Entregue em dois commits de 05/08, ambos rotulados A06/T7 na mensagem:
`318b294d` ("editor v2 replaneja a curva planejada apos recalcular datas" —
cria o helper `_replanejar_pos_commit` e liga em `atualizar_tarefa`) e
`19be5ea8` ("replanejamento nos cinco pontos restantes do editor — T7
FECHA" — liga nos 5 pontos restantes).

Evidência atual:
- `cronograma_views.py:123-169` — `_replanejar_pos_commit(obra_id, admin_id,
  cliente_mode)`, o ponto único que chama
  `replanejar_curvas_obra(obra_id, admin_id, com_relatorio=False,
  sincronizar=False)` (`:159-161`). Implementa exatamente o padrão exigido
  pelo documento original: roda **pós-commit** (a função interna já commita
  por dentro, conforme `utils/cronograma_engine.py:1285+`), e o `except`
  faz `db.session.rollback()` + `logger.exception(...)` **sem desfazer a
  edição já commitada** (`:162-169`, comentário explícito nas linhas
  143-148).
- 7 call-sites confirmados por grep: `cronograma_views.py:929, 1224, 1242,
  1340, 1397, 1509, 1778` — cobrindo as mesmas 7 rotas de escrita do editor
  v2 citadas em 04/08 (`:866-868, :1150-1152, :1261, :1308, :1416-1418,
  :1666-1668, :1710-1712`, que driftaram para essas linhas).
- Testes: `tests/test_replanejamento_editor_v2.py` — rodei agora,
  **16 passed**.

Nada sobra.

---

### A07 — ABERTO (04/08) → **ENTREGUE** (hoje)

Entregue em `1394d907` (05/08, "feat(crm): a cadeia CRM->proposta->obra
carrega o cliente, e o form usa select" — Tasks B3.1/B3.2/B3.3, rotuladas
principalmente A22 mas B3.1/B3.2 são literalmente A07) e reforçado por
comentários explícitos `# A07` espalhados no código.

Os três consertos do "o que sobra" de 04/08, todos confirmados no código
atual:
1. **Repassar query string no redirect** —
   `propostas_consolidated.py:1272-1290` (`nova_proposta()`, o alias citado
   como `:1183-1188` em 04/08, agora com docstring `"A07 — este alias é o
   ÚNICO chamador de produção vindo do CRM"`): monta `_args` por allowlist
   explícita de `cliente_id`/`lead_id` (evita o risco de `**request.args`
   como MultiDict injetar `_external`/`_scheme`) e faz
   `redirect(url_for('propostas.nova', **_args))` (`:1290`).
2. **Ler os args em `propostas_consolidated.py`** —
   `nova()` (`:507-568`, era `:507-540`) lê `request.args.get('cliente_id')`
   (`:550-557`) e `request.args.get('lead_id')` (`:558-559`), valida
   `cliente_id` contra o tenant (`admin_id=admin_id` no filtro, `:554-555`),
   e manda `cliente_pre`/`lead_id_pre` ao template (`:567-568`). O template
   `templates/propostas/nova_proposta.html:83-100` usa `cliente_pre` para
   marcar a `<option selected>` e grava `lead_id_pre` num
   `<input type="hidden" name="lead_id">`.
3. **Mesma leitura em `views/obras.py`** — bloco próprio (fora do
   `try`/`except` que zera funcionários/serviços em caso de falha),
   comentado `# A07 (perna da obra)` em `:422-443` (era `:292-294`/render
   em `:518-523`): lê `cliente_id`/`lead_id` de `request.args`, valida
   `cliente_id` contra `admin_id`, manda `cliente_pre`/`lead_id_pre` ao
   `render_template('obra_form.html', ...)` (`:447-454`). O template
   `templates/obra_form.html:395-408` usa os dois quando `not obra` (só
   aplica no formulário de criação, não sobrescreve edição existente).

Emissor do lado CRM (já estava OK em 04/08, confirmado sem regressão):
`crm_views.py:1010` — `url_for(endpoint, cliente_id=lead.cliente_id,
lead_id=lead.id)`.

Teste dedicado: `tests/test_cadeia_crm_proposta_obra_lead.py` (menciona A07
no próprio arquivo) — rodei agora, **13 passed**.

Nada sobra.

---

## Resumo do que mudou de fato

- **A02, A03, A05, A06, A07** saltaram de ABERTO/PARCIAL para **ENTREGUE**,
  todos com evidência de código + teste passando hoje, não só presença de
  código.
- **A01, A04** seguem **ABERTO**, sem nenhum commit nos arquivos citados
  desde 04/08 — confirmado por leitura linha a linha, não só por ausência de
  commit.

## Reconferência A08–A13 — 2026-08-23 contra doc de 2026-08-04

Base de comparação: `docs/reconferencia-backlog-2026-08-04.md` §3 (linhas 132–137) e §5.
HEAD atual: branch `feat/regua-status-unificado`. Todos os commits abaixo confirmados
com `git log --format=%ci` (datas reais, não confiar em `--since=YYYY-MM-DD` sem hora —
esse formato deu resultado inconsistente neste ambiente; usar `--since="YYYY-MM-DD 00:00:00"`).

---

### A08 — Import de alimentação gerar custo — **ABERTO → ABERTO (inalterado)**

**Evidência atual:** `services/importacao_excel.py` (classe `ImportacaoAlimentacao`,
método `importar`, ~linhas 883–920) continua criando só `AlimentacaoLancamento` +
INSERT cru na M2M `alimentacao_funcionarios_assoc`. `grep -n "registrar_custo_automatico|CustoObra"
services/importacao_excel.py` só devolve os usos do módulo de TRANSPORTE (linhas
656/747/768/781/1019/1025) — o de alimentação não tem nenhum. `MODULO_MAP` (linha 2546)
segue mapeando `'alimentacao': ImportacaoAlimentacao`, consumido por `importacao_views.py`.

**O que mudou:** nada. `git log --since="2026-08-04 00:00:00" -- services/importacao_excel.py`
e `-- alimentacao_views.py` vazios — zero commits nos 19 dias.

**O que sobra:** exatamente o que o doc de 04/08 descrevia — chamar
`registrar_custo_automatico(tipo_categoria='ALIMENTACAO', ...)` dentro do savepoint da
`importar`, e resolver o insumo que falta (`restaurante` como texto livre sem
`entidade_id`, sem `centro_custo_id`/`obra_servico_custo_id`). Bloqueio de negócio
citado no doc (rateio por centro de custo × agregado por obra) segue sem decisão.

---

### A09 — Dedup de NF na entrada manual de almoxarifado — **ABERTO → ENTREGUE**

**Evidência atual:** `views/almoxarifado/movimentos.py:16-49` — nova função
`entrada_ja_lancada(nota_fiscal, item_id, admin_id)`, chave `(admin_id, nota_fiscal,
item_id, tipo_movimento='ENTRADA')`, nota vazia tratada como "sem chave" (`if not
nota_fiscal: return None`). Chamada antes de qualquer insert em `processar_entrada`
(linha ~100, antes da criação de `AlmoxarifadoMovimento`) e em
`processar_entrada_multipla` (linha ~307, na fase de validação prévia — carrinho é
tudo-ou-nada). Recusa com flash/erro explícito, nada é gravado.

**O que mudou (commits):**
- `bbe74f00` (2026-08-04 19:40) — `feat(almox): dedup de nota fiscal; escopo de
  tenant no catálogo e no progresso` — introduz `entrada_ja_lancada` e a guarda nas
  duas rotas. Testes: `tests/test_arreio_almoxarifado_e_tenant.py`.
- `96cce753` (2026-08-05) — `fix(tenant): fornecedor de outro tenant responde 404 na
  entrada múltipla` (tangencial, mas no mesmo arquivo).
- `940e759e` (2026-08-05) — remoção de dead code (emissores inertes de
  `material_saida`), não afeta o dedup.

**Verificação:** `pytest tests/test_arreio_almoxarifado_e_tenant.py` → 6 passed
(inclui `test_reenviar_a_mesma_nota_fiscal_nao_duplica_estoque`,
`test_nota_fiscal_vazia_nao_e_chave_de_dedup`,
`test_fornecedor_de_outro_tenant_na_entrada_multipla_responde_404`).

**O que sobra:** o "de brinde" do doc de 04/08 — `almoxarifado_utils.py:257`
(`processar_xml_nfe`, consulta `NotaFiscal` por `xml_hash` **sem filtrar
`admin_id`**) continua sem filtro de tenant. Confirmado com
`grep -rn "processar_xml_nfe" --include=*.py . | grep -v archive | grep -v test`:
só a própria definição aparece — **sem chamador vivo em produção**, e o próprio
docstring do teste de dedup registra essa constatação explicitamente ("deliberadamente
NÃO cobre... confirmado que processar_xml_nfe não tem chamador vivo"). Bug real, mas
código morto — não é caminho de produção hoje.

---

### A10 — Idempotência no custo de horista do ponto — **MUDOU_DE_FORMA (derrubado em §5) → ENTREGUE**

O defeito específico que o cético usou para derrubar o veredito (dois lançamentos
manuais no mesmo dia via `POST /novo_ponto` criando dois `RegistroPonto` e o segundo
sobrescrevendo o custo do primeiro) foi corrigido de forma direcionada, com decisão de
negócio registrada e testes dedicados.

**Evidência atual:**
- `views/admin.py:100-290` (`novo_ponto`) — passou a **reusar** o `RegistroPonto` do
  dia (`RegistroPonto.query.filter_by(funcionario_id=..., data=..., admin_id=...)
  .order_by(RegistroPonto.id).first()`) em vez de criar incondicionalmente. Implementa
  regra de "turno partido" decidida por Cássio: lançamento que começa depois do
  registrado termina vira a segunda metade do dia (mescla como almoço); lançamento que
  se sobrepõe é correção (vale o último); terceiro turno não cabe (correção +
  WARNING). `obra_id` vazio não zera a obra já gravada. Emit olha o objeto após commit,
  não a variável local do POST.
- `event_manager.py:504-578` (handler `ponto_registrado`, ramo horista/B1.6) — a chave
  de idempotência do `CustoObra` categoria `PONTO_ELETRONICO` **perdeu `obra_id`**
  (era funcionário+data+obra+admin+categoria) e ganhou `.order_by(CustoObra.id)`
  explícito — resolve também o achado adjacente "`.first()` sem `order_by`" citado
  no doc. Ao atualizar, `custo.obra_id = registro.obra_id` segue a obra do registro do
  dia (não deixa dinheiro preso na obra antiga).

**Commits:** `3710b864` (2026-08-04 18:45) `fix(ponto): /novo_ponto reusa o registro
do dia — turno partido vira almoço` (Task B1.7) e `cdf18195` (2026-08-04 18:11)
`fix(ponto): custo de ponto é um por funcionário-dia e segue a obra do registro`
(B1.6).

**Verificação:** `pytest tests/test_arreio_presenca_rotas.py
tests/test_p1_fallback_e_idempotencia.py` → 21 passed, 1 xfailed (o xfail restante é
rotulado A16-a, fora de escopo). Testes chave:
`test_dois_lancamentos_no_mesmo_dia_custeiam_as_horas_das_duas_metades`,
`test_trocar_a_obra_do_dia_nao_cobra_o_dia_duas_vezes`,
`test_corrigir_o_horario_do_mesmo_registro_continua_dando_uma_linha`.

**O que sobra (achados "adjacentes" do doc, não fechados, mas fora do escopo estrito
de A10):**
- `ponto_views.py:1509` e `views/api.py:406` — import/lote de ponto só emite
  `ponto_registrado` quando `tipo_remuneracao == 'diaria'`; horista importado/lançado
  em lote continua sem gerar custo. **Confirmado ainda presente**, sem commit desde
  04/08.
- Quiosque facial (`ponto_views.py` ~2178-2494) e os dois deletes sem cascata de
  `CustoObra` não foram reverificados a fundo nesta rodada (fora do foco A08-A13), mas
  não há commits recentes nesses trechos que sugiram correção.

---

### A11 — Unificar os dois mecanismos de custo do RDO — **PARCIAL → PARCIAL (recorte encolheu bastante)**

O núcleo do recorte que faltava em 04/08 — `services/rdo_custos.py` e
`event_manager.py` com chaves cruzadas (`rdo_custo_diario` × `rdo_mao_obra`) — foi
resolvido por uma sequência de commits no mesmo dia 04/08 à tarde/noite, incluindo a
correção da regressão do p1 citada na manchete do próprio doc.

**Evidência atual:**
- `event_manager.py:1005` — `_ORIGENS_RDO_FOLHA = ('rdo_custo_diario', 'rdo_mao_obra')`
  usado tanto no bloqueio cruzado (linha do handler de RDO se abstém se há lançamento
  de OUTRA origem) quanto na reconciliação de valor entre "irmãs" (RDOs do mesmo dia,
  linhas 1030-1075: atualiza o valor das linhas irmãs quando o rateio do dia muda,
  puxando de `RDOCustoDiario`).
- `services/rdo_custos.py:414-427` — agora lê `RDOCustoDiario` (`_custo_diario_rdo`)
  como fonte de verdade quando existe (`_origem_folha='rdo_custo_diario'`,
  `_origem_id=custo_dia.id`), com fallback legado (`_origem_folha='rdo_mao_obra'`)
  só quando não há `RDOCustoDiario`. Isso também fecha a regressão citada na manchete
  do doc de 04/08 (handler `lancar_custos_rdo` que ignorava mensalista/horista).
- `event_manager.py:356-372` (ramo diarista) — guarda inversa agora usa
  `.in_(['rdo_mao_obra', 'rdo_custo_diario'])` em vez de só `'rdo_mao_obra'` — o
  primeiro "buraco" que o cético listava (guarda só contra uma origem) está corrigido
  no ramo diarista.

**Commits:** `cefba5e7` (04/08 16:22, B1.1+B1.2 — handler lê RDOCustoDiario),
`060146ac` (04/08 16:28, B1.x — guarda de ponto só cobre CustoObra + payload com
obra_id + emit pós-commit), `95041413` (04/08 18:00, B1.5b — "mecanismo único de
custo, a chave larga aprende a contar o dia" — introduz `_ORIGENS_RDO_FOLHA` e a
reconciliação de irmãs), `cdf18195` (04/08 18:11, B1.6, compartilhado com A10).

**Verificação:** `pytest tests/test_arreio_custo_rdo_rotas.py
tests/test_p1_dedup_cross_origem.py tests/test_auto_link_servico_rdo.py` → 18 passed,
1 xfailed (rotulado A16, fora de escopo: "ponto sem custo faz o RDO abster-se em favor
de um lançamento que nunca chega").

**O que sobra (dos "quatro buracos" que o cético listou em 04/08):**
1. ~~Guarda inversa só contra `rdo_mao_obra`~~ — **corrigida** (ramo diarista).
2. **Ainda aberto:** o ramo horista (`event_manager.py:504-578`, B1.6) segue **sem**
   guarda cruzada contra `CustoObra` categoria `'RDO'` — só verifiquei/atualizei
   idempotência dentro da própria categoria `PONTO_ELETRONICO`. Não encontrei
   `categoria='RDO'` referenciado nesse trecho (`grep -n "categoria='RDO'" event_manager.py`
   só aparece uma vez, no bloco de criação de `CustoObra` do lado RDO, linha ~960 —
   não há leitura cruzada a partir do lado ponto/horista).
3. **Resolvido de outra forma:** a "chave larga sem `obra_id`" (funcionário em duas
   obras no mesmo dia contado diferente pelos dois trilhos) não foi corrigida
   *adicionando* `obra_id` à chave — foi resolvida *removendo* `obra_id` da chave
   (B1.6) e garantindo (via B1.7 em A10) que só existe um `RegistroPonto`/um
   `CustoObra` de ponto por dia, que **segue** a obra atual do registro. É uma solução
   de desenho diferente da que o cético sugeriu, mas ataca a mesma consequência
   (contagem dupla por obra).
4. `tests/test_p1_dedup_cross_origem.py` — ainda não teria cobertura direta de
   `views/rdo.py` isolada (não confirmei a fundo; o arreio mais relevante virou
   `tests/test_arreio_custo_rdo_rotas.py`, que toca `views/rdo.py` via commit
   `95041413`).

Bloqueio de negócio do doc ("qual mecanismo é canônico") permanece sem decisão restante
explícita a este ponto, mas a chave cruzada já não produz números diferentes por
origem — o ponto residual é técnico (guarda RDO×ponto no ramo horista), não mais de
decisão de negócio pura.

---

### A12 — Reprocesso de folha estornar antes de recriar — **ABERTO → ABERTO (inalterado)**

**Evidência atual:** `folha_pagamento_views.py:141-153` — `reprocessar == 'true'`
ainda faz só `FolhaPagamento.query.filter_by(...).delete()` + commit (linha ~148-152).
Nenhum estorno dos efeitos colaterais: `GestaoCustoPai`/`GestaoCustoFilho` continuam
sendo criados sem checar existência prévia (linhas ~226-266), o evento
`folha_processada` continua sendo emitido a cada reprocesso (linha ~198,
`event_manager.py` cria Lançamento/Partida no handler), e
`gerar_lancamento_contabil_automatico` continua sendo chamado sem estorno do anterior
(linhas ~278-288).

**O que mudou:** nada na lógica de reprocesso. `git log --since="2026-08-04 00:00:00"
-- folha_pagamento_views.py` só devolve `5ee845da` e `9a64256c`, ambos sobre CPF
opcional no cadastro de funcionário — não tocam o bloco de reprocesso/delete.

**O que sobra:** tudo, exatamente como em 04/08. Cada reprocesso continua duplicando
(a) o par Pai/Filho por funcionário — os antigos ficam órfãos apontando `folha_id` já
deletado —, (b) o lançamento do handler de `folha_processada`, (c) o agregado
contábil. Bloqueio de negócio (estornar lançamento emitido × lançar contrapartida;
pai já pago não pode sumir) segue sem decisão.

---

### A13 — Orçado deixa de herdar venda — **PARCIAL → PARCIAL (mas praticamente fechado no consumo; só falta a origem, que é decisão adiada)**

Este item recebeu o maior volume de trabalho dos seis reconferidos: uma sequência de
6 tasks (B2.1–B2.6) em 05/08, todas com teste dedicado e "sabotagem" (reverter o fix
e confirmar que o teste cai) documentada no commit.

**Evidência atual — os 5 pontos "residuais" listados no doc de 04/08, um a um:**

1. `utils/notifications.py` (`servico_estourou`) — **corrigido**. Commit `25ce59d9`
   (05/08 11:53, B2.2): a função ganhou parâmetro `projecao` (que já vem calculado a
   partir de `services/custo_orcado.py`, B2.1) e compara contra custo, não venda. Teste
   prova que o alarme falso (estouro disparando a 11% do custo real) sumiu.
2. `views/catalogo_views.py:675-676` (histórico de serviço) — **corrigido**. Commit
   `d66a087e` (05/08 12:20, B2.5): `/catalogo/servicos/<id>/historico-obras` agora
   compara `realizado` contra custo orçado (memoizado por obra, evitando N+1), não
   venda. Teste escolhido troca o SINAL do delta (-7,9% verde → +2,6% vermelho) para
   provar que não é "teste que mede o vazio".
3. `models.py:7198-7200` (property `saldo`) — **removida**. Comentário em
   `models.py:7874-7879` (Task B2.4): a property fazia `valor_orcado - realizado -
   a_realizar` com `valor_orcado` = venda; foi excluída, com nota explícita para não
   recolocá-la como chamada a `custo_orcado.py` (geraria N+1 em lista).
4. `templates/obras/planejamento_custos/lista.html:95/98` — **corrigido**. Commit
   `8553e0cb` (05/08, "tela de planejamento passa a exibir custo, e a coluna Saldo
   sai"). Confirmado no template atual: linha do "Orçado" agora usa
   `p.orcado if p else s.valor_orcado` (custo vindo da projeção, com fallback
   documentado "nunca zero"), e a coluna Saldo (que dependia da property removida)
   saiu da tela.
5. `services/resumo_custos_obra.py:192-198` (rateio do realizado não vinculado por
   peso de venda) — **corrigido**. Commit `31f30159` (05/08 12:46, B2.6, deliberadamente
   por último por ser o único ponto do item que **escreve** no banco). Peso trocado de
   `valor_orcado` (venda) para custo orçado real. Teste separa as duas réguas ao
   máximo (duas etapas, mesma venda, custos opostos 50k/150k) e confirma que a soma
   redistribuída continua batendo.

**Verificação:** `pytest tests/test_p3_p9_orcado_e_contrato.py` → 15 passed.

**O que sobra — confirmado ainda intacto:**
- **Origem** (Decisão 3 de 03/08, "consertar no consumo", explicitamente adiada, não
  revertida): `models.py:7544-7546` (`valor` calculado a partir de `valor_base`/
  `pct` no `MedicaoContrato` — não é o ponto certo; o ponto real dos 3 escritores é
  `medicao_views.py:314` (`par.valor_orcado = item.valor_comercial`) e
  `views/catalogo_views.py:902` (`par.valor_orcado = it.valor_comercial`, linha
  drift de 886→902) — ambos **ainda gravam venda** em `valor_orcado`. Nenhum backfill
  das obras já gravadas.
- **Edge case medido em dev pelo próprio autor do fix**: serviço **sem nenhuma linha
  de custo cadastrada** ainda usa `valor_orcado` (venda) como proxy de custo nos seis
  pontos, porque `custo_orcado_por_servico` cai para esse campo quando não há linhas.
  Medido em 2.459 de 76.004 `ObraServicoCusto` (3,2%) — só a correção na origem resolve.

**Leitura:** o rótulo PARCIAL do doc de 04/08 continua correto tecnicamente (a origem
não foi corrigida), mas o "o que sobra" encolheu de 5 consumidores residuais + origem
para só origem + o 3,2% de edge case sem linha — praticamente todo o recorte de
"consumo" fechou, com testes e reversão-de-sabotagem documentados em cada commit.

---

## Tabela resumo

| item | veredito 04/08 → hoje | uma linha |
|---|---|---|
| A08 | ABERTO → ABERTO | Zero mudança: importação de alimentação segue sem nenhuma chamada a `registrar_custo_automatico`/`CustoObra`. |
| A09 | ABERTO → ENTREGUE | `entrada_ja_lancada` (admin_id+nota_fiscal+item_id) guarda as duas rotas de entrada manual, testado; só sobra bug de tenant em código morto (`processar_xml_nfe`, sem chamador). |
| A10 | MUDOU_DE_FORMA (derrubado) → ENTREGUE | `/novo_ponto` passou a reusar o registro do dia (turno partido vira almoço) e a chave de custo perdeu `obra_id` + ganhou `order_by`, resolvendo a perda de custo que o cético achou; testes dedicados passam. |
| A11 | PARCIAL → PARCIAL (recorte bem menor) | Chave cruzada `rdo_custo_diario`×`rdo_mao_obra` unificada e regressão do p1 corrigida; falta só a guarda cruzada RDO×ponto no ramo horista. |
| A12 | ABERTO → ABERTO | Zero mudança: reprocesso de folha continua `delete()` puro, sem estornar Pai/Filho, evento ou lançamento contábil anteriores. |
| A13 | PARCIAL → PARCIAL (quase fechado) | Os 5 consumidores residuais citados em 04/08 (notifications, catálogo, saldo, template, rateio) foram todos corrigidos com teste; só falta a origem (decisão adiada) e o edge case de 3,2% sem linha de custo. |

## Reconferência A14–A19 — 23/08/2026 (base: doc de 04/08/2026)

Metodologia: leitura do veredito de 04/08 (§3 e §5 do documento), abertura dos
arquivos citados no HEAD atual de `main` (`git log --oneline -3`:
`2e40f8b0`, `05c2c639`, `410835ef`), `git log --since=2026-08-04T00:00:00`
nos arquivos-chave (o `--since=2026-08-04` sem hora perdeu dois commits reais
de 04/08 à noite — usar sempre com `T00:00:00`), e execução dos testes
dedicados de cada item quando existiam.

---

### A14 — Aprovação semeia serviços e fecha o lead — **PARCIAL → ENTREGUE**

**Veredito 04/08:** PARCIAL. `handle_proposta_aprovada` tinha um terceiro
ramo (`if valor_total <= 0 or skip_contabil: ... return`) que saía ANTES de
chamar `_semear_servicos_reais`/`_fechar_lead_da_proposta` — por ali passava
toda importação físico-financeira e proposta de valor zero. Além disso,
`_fechar_lead_da_proposta` era inalcançável: filtrava por `Lead.proposta_id`
e nada em produção escrevia esse campo. Dependia do A07 (redirect
`propostas_consolidated.py:1188` perdia `?lead_id=`).

**O que mudou (commits):**
- `1394d907` (05/08) — `propostas_consolidated.py`: `nova()` passa a ler
  `cliente_id`/`lead_id` de `request.args`; alias `/nova-proposta`
  (hoje `propostas_consolidated.py:1272-1290`) repassa os dois por
  allowlist; `criar()` grava `_args_form['lead_id']` para sobreviver a um
  retorno ao form em erro. **Isto fecha o A07** (verificado: o template
  `templates/propostas/nova_proposta.html:99-100` tem
  `<input type="hidden" name="lead_id" value="{{ lead_id_pre ... }}">`).
- `27a823f0` (05/08) — "E05 FECHA": dois escritores novos de FK —
  `propostas_consolidated.py:764-778` grava `Lead.proposta_id` em `criar()`
  logo após o flush; `views/obras.py:336-345` grava `Lead.obra_id` em
  `nova_obra()`. E as duas chamadas (`_semear_servicos_reais`,
  `_fechar_lead_da_proposta`) entraram dentro do ramo `if valor_total <= 0
  or skip_contabil:` — hoje em `handlers/propostas_handlers.py:392-393`
  (o `return` do ramo é logo depois, em `:394`).

**Evidência atual:**
- `handlers/propostas_handlers.py:378-394` — as duas chamadas estão dentro
  do ramo de skip/valor-zero, antes do `return`.
- `handlers/propostas_handlers.py:246-282` (`_fechar_lead_da_proposta`) —
  hoje alcançável: `propostas_consolidated.py:764-778` é o primeiro
  escritor real de produção de `Lead.proposta_id`.
- Teste-guarda textual atualizado e documentado como tal:
  `tests/test_p5_aprovacao_semeia_obra.py:207-230`
  (`test_forma_o_handler_chama_os_dois_nos_tres_caminhos_conhecidos`),
  contagem `== 3` (era 2, o próprio docstring registra o furo antigo).
- Prova de comportamento (não só de forma):
  `tests/test_cadeia_crm_proposta_obra_lead.py` (22 testes, T3–T6) e
  `tests/test_arreio_aprovacao_proposta_rotas.py` (5 testes) —
  **rodados agora: 22 passed / 5 passed**, incluindo o cenário do terceiro
  caminho (`test_t5_terceiro_caminho_do_handler_semeia_e_fecha`, importação
  e valor zero) e lead PERDIDO não reaberto.
- O xfail(strict=True) antigo saiu (virava XPASS→FAILED); hoje o teste passa
  limpo.

**O que sobra:** nada do recorte original. Residual não citado no item:
sobrescrita de `proposta_id` quando o lead troca de proposta é só logada
(`propostas_consolidated.py:768-774`), comportamento deliberado e
documentado, não um defeito.

---

### A15 — Unificar a medição do portal com o trilho ponderado — **PARCIAL → PARCIAL (inalterado)**

**Veredito 04/08:** PARCIAL. A rota do portal (`portal_obras_views.py`,
hoje `gerar_medicao`, linhas 796-857) continua sendo um gerador paralelo:
cria `MedicaoObra` direto, sem `MedicaoObraItem`, sem escrever
`ItemMedicaoComercial.percentual_executado_acumulado`, sem chamar
`recalcular_medicao_obra`. Grava **acumulado** (`valor_contrato × perc/100`)
enquanto `services/medicao_service.py` grava o valor do **período** — duas
semânticas na mesma tabela. As duas fórmulas de origem (`progresso_ponderado_armazenado`
vs `calcular_percentual_item`) continuam divergentes por construção.

**git log --since=2026-08-04T00:00:00:**
- `portal_obras_views.py`: `1e05326d`, `2126f050`, `fac2e321`, `fe3477a6` —
  nenhum toca `gerar_medicao`/`MedicaoObra` (confirmado com
  `git log -p` filtrado por essas strings: zero ocorrências). `fac2e321` é
  cosmético (remove marca da construtora do PDF/portal) e mexeu em
  `services/medicao_service.py` só para adicionar o parâmetro `com_marca`
  em `gerar_pdf_extrato_medicao` — não toca a lógica de cálculo.
- `services/medicao_service.py`: `352719a0` (conta contábil da CR — é o
  A03, não o A15) e `fac2e321` (idem acima).
- `templates/obras/detalhes_obra_profissional.html` e
  `templates/medicao/gestao_itens.html`: os dois botões (linhas citadas no
  doc) não foram tocados por nenhum commit desde 04/08 relacionado a
  medição — os dois geradores seguem vivos.

**Evidência atual:** `portal_obras_views.py:851-857` (construção de
`MedicaoObra` sem itens, sem `recalcular_medicao_obra`);
`services/medicao_service.py:48` (`calcular_percentual_item`) e
`utils/cronograma_engine.py:1208` (`progresso_ponderado_armazenado`, renomeada/
deslocada por causa da A19, mas com a mesma fórmula divergente).

**O que sobra:** exatamente o mesmo recorte de 04/08. Nenhum trabalho
alocado a este item nos últimos 19 dias — decisão 4 do `PLANO-NUCLEO.md`
(medições históricas) segue travando, como o próprio plano interno já
registra (`docs/superpowers/plans/2026-08-04-plano-consolidado.md:4736`).

---

### A16 — Consertar o sync alocação → ponto — **PARCIAL → PARCIAL (recorte reduzido)**

**Veredito 04/08 (rótulo mantido, recorte corrigido em §5):** três defeitos
vivos: (a) guarda `bool(hora_entrada or hora_saida)` classifica ausência sem
hora como "vazio" e o plano sobrescreve — atestado vira 8h de trabalho em
silêncio; (b) nenhum `EventManager.emit('ponto_registrado', ...)` nos dois
ramos de criação nem no preenchimento do registro vazio — RDO perde o custo
duas vezes (não lança porque "já tem ponto", e o handler que lançaria nunca
roda); (c) outros pontos de criação (`ponto_views.py:2369`,
`ponto_service.py:344`) também não emitem.

**O que mudou:** defeito **(a) foi corrigido**, por commits datados
04/08 à noite (mesma data do documento, aparentemente posteriores à
redação — `--since` sem hora os omitia):
- `7a33a7f6` (04/08 18:49) — nova função `registro_ponto_tem_fato_humano`
  (`models.py:867-905`), lista branca fechada `TIPOS_PONTO_NEUTROS_PARA_O_PLANO`,
  fail-closed (tipo desconhecido = fato humano, não sobrescreve).
- `f425742d` (04/08 19:20) — `sincronizar_com_ponto` (hoje
  `models.py:4775` em diante) passa a chamar `registro_ponto_tem_fato_humano`
  em vez do `bool(hora_entrada or hora_saida)` antigo (`models.py:4818-4855`),
  e a busca do registro existente ganha `admin_id` no filtro
  (`models.py:4794-4797`).
- Teste dedicado: `tests/test_a16_fato_humano.py` (unidade, sem banco) +
  `tests/test_arreio_presenca_rotas.py` (rota `POST /equipe/api/sync-ponto`)
  — **rodados agora: 56 passed, 1 xfailed** (o xfailed é de outro recorte,
  não do A16).

**O que NÃO mudou — defeitos (b) e (c) seguem abertos, intactos:**
- `grep -n "EventManager\|\.emit(" models.py` → **zero ocorrências**. A
  sincronização criada/preenchida por `AlocacaoEquipe.sincronizar_com_ponto`
  (`models.py:4775-4930`) não emite `ponto_registrado` em nenhum dos dois
  ramos de criação nem no preenchimento do registro vazio.
- `equipe_views.py` (rota `/api/sync-ponto`, hoje `equipe_views.py:1213`) —
  `grep emit` → zero. Chama `processar_lancamentos_automaticos` e não emite
  nada.
- `ponto_service.py:321` (`registrar_falta`) — ainda sem emit (o único
  `EventManager.emit` do arquivo está em `bater_ponto_obra`,
  `ponto_service.py:144-150`).
- `ponto_views.py:2369` (fluxo do quiosque facial, criação de
  `RegistroPonto` por geolocalização) — ainda sem emit.
- `services/rdo_custos.py` (guarda "já tem ponto, custo virá pelo handler")
  — zero commits desde 04/08; a lógica de `gerar_custos_mao_obra_rdo`
  (`services/rdo_custos.py:355-380` e adjacências) é a mesma.

**Esforço:** o próprio doc já previa "M → P" — com (a) fechado, o que resta
é só emitir o evento nos pontos certos, tarefa menor.

---

### A17 — Pré-carregar a mão de obra do RDO da presença do dia — **ABERTO → ABERTO (inalterado)**

**Veredito 04/08:** ABERTO. `views/rdo.py` (`novo_rdo`) carrega a lista
inteira de funcionários do tenant sem recorte de dia/obra; zero
`RegistroPonto` em `views/rdo.py`, `crud_rdo_completo.py`,
`rdo_editar_sistema.py`; template não passa nada de presença.

**git log --since=2026-08-04T00:00:00 -- templates/rdo/novo.html:**
`9f361e13`, `11d82e1f`, `f8abe648`, `e39e901e` — nenhum sobre presença/ponto:
- `f8abe648` (20/08) — filtra o seletor de efetivo para "só pessoal
  operacional" via `?operacional=1` em `/api/obras/<id>/funcionarios` (não é
  pré-carga por dia/obra a partir de ponto/alocação).
- `11d82e1f`, `9f361e13` — equipe de terceiro e linhas de
  ocorrência/equipamento pertencerem ao formulário (fora do escopo do A17).
- `e39e901e` (10/08) — funcionários "voltam a aparecer" nas atividades
  (regressão de seleção múltipla/CRUD de fotos), não pré-carga por presença.

**Evidência atual:** `views/rdo.py:609-694` (`novo_rdo`) — `funcionarios =
Funcionario.query.filter_by(admin_id=admin_id, ativo=True)...` em `:617`,
sem filtro de dia/obra; `grep -n "RegistroPonto" views/rdo.py
crud_rdo_completo.py rdo_editar_sistema.py` → **zero ocorrências**, igual a
04/08.

**O que sobra:** o item inteiro, exatamente como descrito em 04/08 —
nenhum trabalho alocado.

---

### A18 — Derivar progresso entre trilhos via `subatividade_mestre_id` — **PARCIAL → PARCIAL (inalterado)**

**Veredito 04/08:** PARCIAL. Leitor entregue (`services/progresso_subatividade.py`),
mas com um único consumidor de produção (`services/medicao_service.py`), e
ainda atrás de um gate de fallback (`if perc_atual <= 0 and
getattr(item, 'servico_id', None)`). Escrita segue dual em ~15 pontos; a
rota legada `POST /rdo/salvar` (`views/rdo.py`, então 3190-3200/3251) não
grava `subatividade_mestre_id`.

**O que mudou:** nada no núcleo do item.
- `grep -rn "tarefa_da_subatividade\|from services.progresso_subatividade"`
  → ainda **um único** consumidor de produção
  (`services/medicao_service.py:279`).
- `services/medicao_service.py:277-286` — gate de fallback idêntico
  (`if perc_atual <= 0 and ...`), agora em `:277`, mesma lógica.
- Rota legada `POST /rdo/salvar` = `rdo_salvar_unificado`
  (`views/rdo.py:2769`, ainda logada como `[LEGACY-RDO]` em `:2784`) — o
  bloco que cria `RDOServicoSubatividade` (hoje `views/rdo.py:3190-3216`)
  **continua sem setar `subatividade_mestre_id`** em nenhum dos dois ramos
  (nem no ramo principal `:3191-3216`, nem no de compatibilidade JSON
  `:3234-3260`). Confirmado por leitura direta do código hoje.
- `git log --since=2026-08-04T00:00:00 --grep="A18"` → só um commit de
  documentação (`fcc06fb2`, sem mudança de código); `git log -S
  "subatividade_mestre"` não traz nenhum commit novo tocando o elo desde
  04/08 (os hits são todos anteriores).
- Confirmado no plano interno: `docs/superpowers/plans/2026-08-04-plano-consolidado.md:4739`
  registra A18 como aberto, bloqueado pela Decisão 4 do `PLANO-NUCLEO.md`
  (mesma decisão que trava A15) — "escrita segue dual em ~15 pontos".

**Nota lateral (não muda o A18, mas é adjacente):** os leitores "crus"
citados em 04/08 mudaram de forma sem resolver o elo: `services/rdo_pdf_service.py`
e as leituras em `views/rdo.py`/`crud_rdo_completo.py` foram todos migrados
para `progresso_v1_acumulado`/`obra_em_modo_v2` (trabalho do **A19**, ver
abaixo) — isso resolve a inconsistência de FÓRMULA entre eles, mas não cria
elo por `subatividade_mestre_id` nem toca o gate de `medicao_service.py`.
`views/obras.py:744-756` (SQL cru sem `admin_id`, citado em 04/08) foi
**removido inteiramente** (commit `db85ba04`, escopo A19: a função
`calcular_progresso_real_servico` foi apagada por calcular um número
descartado — não migrada para o elo do A18).

**O que sobra:** o mesmo recorte de 04/08 — escrita dual, rota legada sem
elo, gate estreito. Trabalho de 19 dias não tocou este item; foi
explicitamente adiado pela mesma decisão de negócio.

---

### A19 — Fórmula única de progresso — **PARCIAL → ENTREGUE (com duas ressalvas residuais)**

**Veredito 04/08:** PARCIAL. As cinco fórmulas do p4 já tinham sumido, mas
a família V1 (sete variantes A–F, nomeadas em §5.2 do plano interno)
continuava reimplementada em 4+ lugares sobre 2 fontes; F
(`views/obras.py`) calculava progresso por SERVIÇO e o número era
descartado; o "sexto gerador" (`medicao_service.py`) e a contradição do
portal (mostra ao cliente uma fonte, fatura por outra) ficaram registrados
como achados novos.

**O que mudou (commits, todos 05/08, Tasks B2.7–B2.12):**
- `utils/cronograma_engine.py:1107` — nova função `progresso_v1_acumulado`
  (MAX por chave composta `(servico_id, nome_subatividade)`, com teto de
  data `ate_data` e filtro `admin_id` obrigatórios — resolve os defeitos
  específicos de cada variante antiga: A não filtrava tenant, B/C/E
  colapsavam homônimos, C não tinha teto de data).
- `utils/cronograma_engine.py:1171` — `obra_em_modo_v2`, predicado único
  substituindo os quatro predicados V2 divergentes que existiam.
- `db85ba04` — variante F (`calcular_progresso_real_servico`,
  `views/obras.py`) **removida** (não convergida): o número que calculava
  já era descartado (nenhum template lê `servico['progresso']`).
- `584a2d8c` ("listar_rdos converge, e o A19 FECHA") — última variante
  (`crud_rdo_completo.listar_rdos`) migrada; achado lateral registrado no
  próprio commit: essa função está **sombreada** (rota nunca alcançada por
  URL, todas as quatro rotas de listagem vão para `views/rdo.py:rdos()`) —
  corrigida mesmo assim, mas o código morto propriamente dito fica como
  item aberto separado no plano interno.
- Todos os call-sites de produção hoje passam por
  `progresso_v1_acumulado`/`obra_em_modo_v2`: `views/rdo.py` (linhas 164-165,
  335, 1252-1253, 2478-2479, 2643 — 5 pontos), `crud_rdo_completo.py:96-97`,
  `services/rdo_pdf_service.py:201-211`.

**Evidência de comportamento, não só de forma:**
`tests/test_a19_progresso_v1_ponto_unico.py` +
`tests/test_a19_progresso_v1_convergencia.py` +
`tests/test_cronograma_engine_unificado.py` — **rodados agora: 25 passed**
(unidade das duas funções novas + convergência entre PDF/detalhe/lista/
consolidada para a mesma obra).

**Ressalvas residuais (não fecham o item, mas valem registro):**
1. `views/dashboard.py:446-467` zera `obra.progresso_atual` quando não há
   RDO algum (`else: obra.progresso_atual = 0`), mesmo que o cronograma
   mostre avanço via import `.mpp`/planilha — comportamento pré-existente
   a 04/08 (já fixado pelo p4, fora do recorte B2.7-B2.12) e não tocado
   agora.
2. O "sexto gerador" (`services/medicao_service.py`, fórmula por valor) e
   a contradição do portal seguem fora de escopo por decisão explícita
   registrada no plano interno — são tratados como A15/Decisão 4, não A19.

**Conclusão:** o núcleo do item (família V1 de leitura, 7 variantes, 2
predicados V2 divergentes) está genuinamente unificado e testado. As duas
ressalvas acima pertencem a outros itens (dashboard isolado, e a fonte de
medição que é explicitamente A15), não ao recorte do A19.

---

## Resumo rápido

| item | veredito 04/08 → hoje | uma linha |
|---|---|---|
| A14 | PARCIAL → **ENTREGUE** | A07 fechou o `?lead_id=`, e as duas chamadas (`_semear_servicos_reais`/`_fechar_lead_da_proposta`) entraram no 3º caminho — 27 testes de comportamento verdes. |
| A15 | PARCIAL → **PARCIAL** (sem mudança) | Portal ainda gera `MedicaoObra` paralela, sem itens e sem `recalcular_medicao_obra`; zero commits no núcleo desde 04/08. |
| A16 | PARCIAL → **PARCIAL** (recorte menor) | Defeito (a) corrigido (`registro_ponto_tem_fato_humano` já não sobrescreve atestado/falta); defeitos (b)/(c) — zero emissão de evento no sync alocação→ponto — seguem intactos. |
| A17 | ABERTO → **ABERTO** (sem mudança) | `novo_rdo` continua carregando todos os funcionários do tenant sem RegistroPonto/AllocationEmployee do dia; zero commits no núcleo. |
| A18 | PARCIAL → **PARCIAL** (sem mudança) | Único consumidor (`medicao_service.py`) segue atrás do mesmo gate; rota legada `POST /rdo/salvar` ainda não grava `subatividade_mestre_id`; travado pela mesma Decisão 4. |
| A19 | PARCIAL → **ENTREGUE** | As sete variantes V1 convergiram para `progresso_v1_acumulado`/`obra_em_modo_v2` (Tasks B2.7–B2.12, 05/08); F foi removida por ser número descartado; 25 testes de convergência verdes. |

Arquivo completo: `/tmp/claude-1000/-home-runner-workspace/190e3039-a423-42c8-a7f7-4d248e85802a/scratchpad/reconf-A14-A19.md`

## Reconferência A20–A25 — 23/08/2026

Base: `docs/reconferencia-backlog-2026-08-04.md` §3 (datado 04/08). Reconferido
linha a linha contra o código de hoje (23/08), 19 dias depois. Notas de
`docs/planos-em-aberto-2026-08-23.md` §5 usadas como ponto de partida para A24/A25.

---

### A20 — Pré-preencher o pedido com o vencedor da cotação: **M (aberto)** → **M (aberto), sem mudança**

**Evidência atual:**
- `models.py:7579-7597` — `MapaFornecedor` continua guardando o fornecedor só
  como `nome = db.Column(db.String(200), nullable=False)`, **sem FK para
  `Fornecedor`**. O obstáculo estrutural apontado em 04/08 permanece intacto.
- `models.py:7599-7621` — existe `MapaItemCotacao.fornecedor_escolhido_id` (FK
  para `mapa_fornecedor.id`), mas essa coluna **já existia desde 22/07**
  (`git log -S fornecedor_escolhido_id` → `b30923b5`, pré-04/08) e serve a um
  fluxo diferente (seleção por item no portal do cliente,
  `portal_obras_views.py:925-928`) — não ao pedido de compra.
- `compras_views.py:2692-2900` (`requisicao_emitir_pedido`, a rota viva que
  cria `PedidoCompra` a partir da requisição) continua lendo `fornecedor_id`
  cru do form via `_fornecedor_do_form` (`:128-146`), sem olhar para
  `requisicao.mapa_v2` nem para `fornecedor_escolhido_id`.
- `templates/compras/requisicao_detalhe.html:411-415` — o `<select
  name="fornecedor_id">` continua sem nenhum `selected`/pré-seleção.
- `compras_views.py:2839-2860` — preços dos itens do pedido continuam vindo de
  `item.preco_estimado` (fallback), nunca de `MapaCotacao.valor_unitario`.

**O que mudou:** nada no recorte do A20. Os 19 dias de commits em
`compras_views.py`/`models.py` foram todos da régua de status e das alçadas de
compra (fase 4), não tocaram este fluxo.

**O que sobra:** exatamente o que o doc de 04/08 já apontava — decidir entre
casar `MapaFornecedor.nome` → `Fornecedor` por nome (frágil) ou acrescentar
`MapaFornecedor.fornecedor_id` + migração + tela de amarração, e então ligar
isso ao formulário de emissão do pedido.

---

### A21 — FK de frota no equipamento do RDO + TypeError de kwargs: **M (aberto)** → **M (aberto), sem mudança**

**Evidência atual:**
- `models.py:1443-1452` — `RDOEquipamento` continua sem FK para `Veiculo`;
  campo `nome_equipamento` é texto livre.
- `utils/rdo_equip_ocorr.py` — zero commits desde 04/08 (`git log --since`
  vazio); sem `veiculo_id`/`Veiculo` em lugar nenhum do arquivo.
- `templates/rdo/novo.html` e `templates/rdo/editar_rdo.html` — sem
  `veiculo_id`/`Veiculo`, continuam com texto livre.
- `crud_rdo_completo.py:439-460` (linhas deslocaram de 428/429/449, mesmo
  bloco) — os três kwargs inexistentes continuam lá: `horas_utilizacao=`,
  `observacoes=`, `descricao_completa=`.
- `crud_rdo_completo.py:247-254` — comentário explícito confirma que a rota
  `/rdo/salvar` deste blueprint foi **removida** (não a função) porque colidia
  com `@main_bp.route('/rdo/salvar')` em `views/rdo.py:2511`, que sempre
  venceu no `url_map`. `salvar_rdo()` (`:254`) segue **sem rota**, chamada só
  em teste — o TypeError permanece código morto.

**O que mudou:** nada. Os commits em `crud_rdo_completo.py` desde 04/08
(`ee1c99b5`, `a2db4fa6`, `e3ca534c`) tratam de emissão de custo em rascunho e
remoção de rotas de API mortas — não tocam o bloco de equipamento/veículo nem
os três kwargs.

**O que sobra:** igual ao original — (a) coluna `veiculo_id` + migração +
selects nos dois templates + parse/persistência; (b) os três kwargs, ainda
latentes em código sem rota.

---

### A22 — Select de cliente na proposta manual + persistir CPF/CNPJ: **P (aberto)** → **PARCIAL (metade entregue)**

**Evidência atual — parte (a), select + `cliente_id`, ENTREGUE:**
- `templates/propostas/nova_proposta.html:83-96` — o `<input name="cliente_nome">`
  foi substituído por `<select class="form-select" name="cliente_id" id="cliente_id" required>`,
  populado com os `Cliente` do tenant e marcando `selected` quando `cliente_pre`
  bate (linha 89).
- `propostas_consolidated.py:510-566` (`nova()`) — agora carrega `clientes =
  Cliente.query.filter_by(admin_id=admin_id)...` e resolve `cliente_pre` a
  partir de `request.args.get('cliente_id')`, com o comentário explícito "A07
  + A22" (linha 534).
- `propostas_consolidated.py:590-616, 700-712` (`criar()`) — lê
  `request.form.get('cliente_id')`, resolve `cliente_ref` com escopo de
  tenant, e agora `proposta.cliente_id = cliente_ref.id if cliente_ref else
  None` (linha 712), com comentário "A22 — a FK que faltava" (linha 710).
- Commit `1394d907` (05/08, "feat(crm): a cadeia CRM->proposta->obra carrega o
  cliente, e o form usa select") — Tasks B3.1–B3.3, mensagem cita A22
  explicitamente e descreve exatamente essa troca de input por select.

**Evidência atual — parte (b), persistir CPF/CNPJ, CONTINUA ABERTA:**
- `propostas_consolidated.py:590` — `cliente_documento =
  request.form.get('cliente_cpf_cnpj', ...)` é lido, mas essa variável **nunca
  é usada depois** (só essa ocorrência no arquivo) — não é atribuída a
  `proposta` em nenhum lugar de `criar()` (`:690-720`).
- `models.py:3710+` (`class Proposta`) — ainda **sem coluna** `cliente_cpf_cnpj`
  (só tem `cliente_id` FK, linha 9 da classe, "Migração 43").
- `templates/propostas/editar.html:97` e
  `templates/propostas/detalhes_proposta.html:159-160` — ainda leem
  `proposta.cliente_cpf_cnpj`, atributo inexistente → Jinja resolve
  silenciosamente como Undefined, o dado nunca aparece.
- `services/cliente_resolver.py` — zero ocorrências de `cnpj`/`documento`;
  dedup continua só por e-mail/nome, como no doc de 04/08.

**O que mudou:** a metade estrutural (select de cliente cadastrado + FK
`cliente_id` persistida) foi entregue em 05/08 (commit `1394d907`,
explicitamente rotulado A22). A metade do CPF/CNPJ não foi tocada.

**O que sobra:** persistir o documento — via `cliente_id` → `Cliente.cnpj`
(`models.py:3354`, a rota mais simples agora que `cliente_id` já está gravado)
ou coluna nova + migração — e depois arrumar os dois templates que leem
`cliente_cpf_cnpj`. Dedup por CNPJ em `cliente_resolver.py` segue sem existir.

---

### A23 — Aviso interno de comprovante e decisão de compra do portal: **P (aberto)** → **P (aberto), sem mudança**

**Evidência atual:**
- `portal_obras_views.py:529-609` (`aprovar_compra`) — termina em
  `logger.info(...)` + `flash(...)`, sem qualquer emissão de evento/notificação
  interna, inclusive no ramo "governança ativa" (linhas 578-583).
- `portal_obras_views.py:612-641` (`recusar_compra`) — idem, `logger.info` +
  `flash`.
- `portal_obras_views.py:643-682` (`upload_comprovante`) — idem, `logger.info`
  + `flash` (linha 680-682).
- `grep -n "notific\|emit\|EventManager" portal_obras_views.py` — zero
  ocorrências de código (só dois comentários não relacionados, em `:568-569`,
  sobre a cadeia de alçada interna, não sobre notificação).
- Commits em `portal_obras_views.py` desde 04/08 (`1e05326d`, `2126f050`,
  `fac2e321`, `fe3477a6`) — conferidos por `git show --stat`: cargas de
  RDO/JSON, manual de assinatura em PDF, remoção de marca do portal e
  alinhamento de cronograma. Nenhum toca as três rotas do A23.

**O que mudou:** nada.

**O que sobra:** exatamente o que o doc de 04/08 apontava — não existe canal
interno genérico para plugar (`NotificacaoOrcamento` é específica de estouro
de orçamento; `NotificacaoCliente` está morta/E02). Decisão de produto
(canal n8n vs. notificação in-app nova) segue em aberto e A23 segue
bloqueado por ela tanto quanto por código.

---

### A24 — Ligar o pipeline de encargos patronais: **M (aberto)** → **PARCIAL (bug aritmético corrigido; ainda sem chamador)**

**Evidência atual:**
- `services/folha_service.py:1112` (`salvar_folha_processada`) — ainda tem
  **um único chamador**, em `:1447`, dentro de
  `processar_e_salvar_folha_obra` (`:1410`).
- `grep -rn "processar_e_salvar_folha_obra" --include=*.py .` (fora de
  archive) — só a própria definição e dois `logger.error` internos. **Zero
  chamadores em rota, CLI ou job** — a função inteira (a que finalmente
  chamaria `salvar_folha_processada` com `obra_id`) continua órfã, exatamente
  como em 04/08.
- `folha_pagamento_views.py:172-189` (a rota viva de processar folha) monta
  `FolhaPagamento` (modelo diferente de `FolhaProcessada`) com `inss`, `fgts`
  etc., mas **sem `encargos_patronais` nem `obra_id`** — confirma que o
  achado do E07 ("a rota viva descarta esses dois campos") continua válido.
- **Mudança real, fora do escopo original do A24 mas dentro do arquivo:**
  commit `43f7cf8c` (05/08, "fix(folha): INSS patronal gravado por subtração,
  não por fator 0.7", Task B2.14/"A24a") corrigiu exatamente o bug que o doc
  de 04/08 apontou como "recorte adicional" — a gravação por `× Decimal('0.7')`
  que produzia 27,6% em vez de 28%. Confirmado: a lógica em
  `services/folha_service.py` (em torno de `:1142`/`:1171` no doc antigo) foi
  trocada por subtração exata, testada com FGTS a alíquota não-8% para provar
  que não é só outro fator mágico.

**O que mudou:** a distorção aritmética (27,6% vs 28%) que o doc de 04/08
registrou como problema NOVO dentro do A24 foi corrigida em 05/08. O pedido
central do item — "um chamador (rota, CLI ou job)" — **não foi atendido**:
`processar_e_salvar_folha_obra`/`salvar_folha_processada` seguem sem
nenhum caminho de produção que os alcance.

**O que sobra:** o chamador em si (rota/CLI/job) e a ponte do resultado para
o custo da obra — hoje `FolhaProcessada` com `obra_id` e `encargos_patronais`
corretos ainda nasceria e nada leria. Decisão 6 (critério de rateio por obra
para funcionário em várias obras no mês) segue pendente, como nota de
`planos-em-aberto-2026-08-23.md` §2 confirma.

---

### A25 — Ativar o canal externo: `N8N_WEBHOOK_URL` + cron D-3: **P (aberto)** → **P (aberto), sem mudança**

**Evidência atual:**
- `utils/webhook_dispatcher.py:224-231` (`dispatch_webhook`) — mesma ordem: se
  `get_webhook_url()` (`:97-100`) devolve vazio, `return False` na linha 230,
  **antes** de `_persist_pending` (chamado só na linha 239) — sem a variável
  de ambiente, nenhuma linha de auditoria em `WebhookEntrega` é criada.
- `utils/webhook_dispatcher.py:374-380, 428-434` — `reentregar_pendentes` e
  `reentregar_uma` continuam abortando cedo via `is_enabled()` (`:110`).
- `git log --since=2026-08-04 -- utils/webhook_dispatcher.py` → **vazio**.
  Zero commits no arquivo em 19 dias.
- `notificacoes_cli.py` — `git log --since=2026-08-04` → **vazio**. O comando
  D-3 continua registrado do jeito descrito (janela em `:32-34`).
- `app.py:1031-1032, 1047-1087` — `git log --since=2026-08-04 -- app.py` traz
  3 commits (`8c0c71a3`, `f5d17209`, `940e759e`), nenhum toca o bloco do
  APScheduler: são sobre guarda de boot/endpoint, guarda de DDL/timeout, e
  remoção de estruturas mortas. O scheduler continua registrando **um único**
  job, `cobertura_ociosa_mensalistas` (`:1076-1083`) — nenhum `add_job` novo
  para o lembrete D-3.

**O que mudou:** nada.

**O que sobra:** exatamente o que o doc de 04/08 e o `planos-em-aberto`
apontam — Decisão 7 (infra: `N8N_WEBHOOK_URL` provisionada e n8n no ar) é
pré-requisito para o canal inteiro, inclusive o que A23 precisaria; e falta o
`add_job` do lembrete D-3 ao lado do job existente. Nenhum dos dois é trabalho
de código pendente — infra/segredo de um lado, uma linha de `add_job` do
outro (o scheduler já roda no processo).

---

## Resumo

| item | veredito 04/08 → hoje | uma linha |
|---|---|---|
| A20 | ABERTO (M) → ABERTO (M) | `MapaFornecedor` ainda sem FK de fornecedor; pedido ainda lê `fornecedor_id` cru do form, sem tocar `mapa_v2`/preços da cotação. |
| A21 | ABERTO (M) → ABERTO (M) | `RDOEquipamento` ainda sem `veiculo_id`; os 3 kwargs inválidos seguem intactos em `crud_rdo_completo.py:439-460`, função ainda sem rota. |
| A22 | ABERTO (P) → PARCIAL | Select de cliente + `proposta.cliente_id` entregues em 05/08 (commit `1394d907`, A22 explícito); persistência de CPF/CNPJ segue sem coluna e sem uso do valor lido. |
| A23 | ABERTO (P) → ABERTO (P) | Nenhuma das 3 rotas do portal (aprovar/recusar/comprovante) emite aviso interno; ainda não existe canal genérico para plugar. |
| A24 | ABERTO (M) → PARCIAL | Bug aritmético (27,6% vs 28%) corrigido em 05/08 (commit `43f7cf8c`); pipeline continua sem qualquer chamador em rota/CLI/job. |
| A25 | ABERTO (P) → ABERTO (P) | Zero commits em `webhook_dispatcher.py`/`notificacoes_cli.py`; scheduler ainda só com um job; segue travado por `N8N_WEBHOOK_URL` + `add_job` faltante. |
