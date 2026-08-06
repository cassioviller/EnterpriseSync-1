# Rodada B6 — varredura dos quatro itens que a B5 deixou citados — 2026-08-06

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development`
> ou `superpowers:executing-plans`. Os passos usam checkbox (`- [ ]`).

**O que é:** a rodada que sucede a
`docs/superpowers/plans/2026-08-06-rodada-b5-varredura.md`, fechada em 06/08 com **6
Tasks entregues e 1 cortada** (HEAD `26dff528`, `test/b0-arreio == origin/main`). A B5
deixou quatro itens citados por escrito e sem Task: a **família flash+redirect-em-vez-de-404**
(medida e recortada fora de propósito na B5.3), o **estorno de recebimento** (que não
existe — item (i) do "NÃO faz" da B5.6), as **rotas irmãs mortas de vehicles** (risco 3
da B5.7) e a **família 2 de gêmeos + o import `apenas_pagamento`** (registrados na B5.7
sem regra, de propósito). Cada um foi varrido com **cinco lentes** e submetido a um
adversário cuja tarefa era derrubar cada achado. Este documento é o produto dos oito
trabalhos.

**Contra o quê:** árvore `26dff528`, limpa, com a rodada B5 inteira dentro
(B5.1–B5.4 + B5.6/B5.7 + apertos WF-1/WF-3). Fatos de estado que invalidam registros
antigos: a migração **280 está GASTA** pela B5.6 (`conta_pagar.banco_id`); o escritor de
FC `'conta_pagar'` foi **removido** (`f69cb359`) e `GestaoCustoPai` é a única fonte da
SAÍDA do fluxo (D-B5.1(a)); compras ficam fora do realizado (D-B5.7(2)); a guarda de
re-baixa do lado pagar dispara por `valor_pago > 0`; `views/rdo.py` já responde 404 por
tenant E obra nas rotas principais (B5.3).

🔴 **REGRA DE CONTORNO desta rodada — decisão do Cássio de 06/08: ele NÃO roda consultas
em produção.** Nenhum Step, gate ou decisão desta rodada depende de medição em produção.
Todos os defaults das D-B6.x são decidíveis com **dev + código**. As consultas ⚠️ dev
citadas foram todas **somente-leitura**, e **toda medida ⚠️ dev leva data** — a regra da
casa nº "toda medida envelhece" da contradição 9 da B5 foi demonstrada de novo nesta
rodada (a nota "194 CRs" de 06/08 virou 239 **no mesmo dia**).

**As cinco lentes** (o método da B5, mantido — neste repo o grep por símbolo já deixou
passar consumo por string 3x, por template/fetch 2x, e um símbolo presente MENTINDO 1x):

| # | Lente | O que procura |
|---|---|---|
| 1 | **SÍMBOLO** | nome Python da função/classe/atributo |
| 2 | **STRING** | o nome como literal: `'nome_tabela'`, listas de config, `referencia_tabela`/`origem_tabela` |
| 3 | **TEMPLATE** | `templates/**/*.html`: `{{ }}`, `url_for` por endpoint, `name=` de form, `fetch()` e `form.action` com path literal |
| 4 | **ROTA** | o `url_map` real — quem vence o despacho; só `main.py` registra tudo |
| 5 | **SQL/DADO** | `migrations.py`, seeds, `scripts/`, consultas ⚠️ dev somente-leitura |

**Marcas de procedência** (regra da casa): 🔬 medido · 📖 lido no código com
`arquivo:linha` · 🧮 deduzido · ⚠️ dev (prova a forma, não o volume — e envelhece: a
suíte roda contra o banco único; **toda medida leva data**). Onde a marca não é minha, o
texto diz de quem é ("🔬 medido na refutação").

---

## 1. O que a varredura DERRUBOU

**Nenhum dos quatro itens caiu inteiro: os quatro sobreviveram como
`confirmado_com_correcoes`. Mas o placar contra os levantamentos é pesado — inclusive
uma correção que, executada como escrita, quebraria fluxo vivo em produção (o cinto da
B6.1) e outra que quebraria o botão de excluir da UI viva da frota (o satélite de
vehicles).**

### 1.1 O que os adversários tentaram, e falhou

| Ataque | Contra o quê | Resultado |
|---|---|---|
| Reproduzir os censos da família 404 com **scanner AST independente** (padrões A e B reescritos do zero) | os números do levantamento B6-1 | 🔬 Falhou em derrubar: família A **39 hits em 12 arquivos, contagens por arquivo idênticas**; família B reproduzida handler a handler, inclusive as exclusões corretas (`:2358/:2379/:2403` fora de try; portal por token fora) |
| Derrubar os dois falso-positivos declarados | `compras_views.py:1055` e `medicao_views.py:368` | 🔬📖 Falhou: o GCP resolve com `first_or_404` FORA do try (`:1048`) e o id de medição vem do FORM (`:361`) — o levantamento os excluiu **corretamente** |
| Achar teste que congele 302 para recurso alheio/inexistente na família | "nenhum teste congela" | 🔬 Falhou: os hits de `== 302` são happy-path do próprio tenant, login/portal; `test_fase1_escopo_obra.py:415` congela o **404** de `/obras/<id>` (confirma o FP de `detalhes_obra:1540`) |
| Re-medir TODAS as medidas ⚠️ dev do estorno e da família 2 por psql independente | levantamentos B6-2 e B6-4 | 🔬 Falhou em derrubar: **todos os números reproduzem** (239 liquidadas; 21/239 com FC; ZERO FC `'conta_receber'` com `banco_id` no parque; 20 LC `FINANCEIRO_RECEBER`; OBRA_MEDICAO 337; família 2 com **0 exemplares**; anomalia 102 PENDENTE/`valor_recebido>0` = R$ 422.127,00 exato) |
| Achar um chamador de `gerar_lancamento_contabil_automatico` em `baixar_recebimento` | o "DERRUBADO" do levantamento B6-2 | 🔬 Falhou: 7 chamadores (alimentação, folha, transporte, compras, pagar, GCP×2) — **receber ausente**. A previsão da B5.6 de "origem dupla de LC no receber" **não se materializou**: o LC único já nasce carimbado (`financeiro_service.py:405-406`) |
| Ressuscitar as três rotas de vehicles por símbolo, string, template, teste e SQL | morte das irmãs + `novo_veiculo_OLD` | 🔬 Falhou nas três: únicos hits são as próprias defs, o comentário `:837` e `MODULOS.md`. E o form do próprio template que a rota morta renderiza **posta para `frota.novo_custo`** |
| Reproduzir por leitura o clone do 1º clique do `migrar_contas_pagar` | levantamento B6-4 | 📖 Falhou em derrubar: guard 1 (`:1344`) só vê clones DESTA rota; guard 2 (`:1363`) só pula `'COMPRA'` — CP `'gestao_custo_pai'` PENDENTE **é clonada no 1º clique**, confirmado |
| Conferir que `views/rdo.py` zerou nos dois padrões | fecho da B5.3 | 🔬 Falhou em derrubar: 0 ocorrências, 8 ramos `except HTTPException` presentes |

### 1.2 O que CAIU — correções dos adversários adotadas nesta síntese

Cada linha é uma prescrição ou afirmação que **não vai virar Step como estava escrita**.

| Prescrição/afirmação derrubada | Onde estava | Por que caiu |
|---|---|---|
| **"Colisão interna nova: o alias `/editar/<id>` POST de `upload_arquivo` — congelar que `atualizar` vence"** | levantamento B6-1 (lote a + pergunta aberta 4) | 📖 `upload_arquivo` tem **UM** decorador (`propostas_consolidated.py:2890` = `/<int:id>/upload-arquivo` POST). As duas únicas regras `/editar/<int:id>` diferem por **MÉTODO** (GET `:1308` `editar`, POST `:1600` `atualizar`) — despacho normal, não sombreamento. O Step congelaria colisão inexistente: **teste verde-e-oco por construção**. Saiu do recorte |
| **"`views/vehicles.py` está morto — satélite de limpeza das 15 rotas sem consumidor"** | levantamento B6-1 (proposta de satélite) | 📖 O layer contém o **caminho VIVO de exclusão da frota**: `templates/veiculos_lista.html:761` monta `form.action = '/veiculos/${veiculoId}/excluir'` por **path literal** — página renderizada pela rota viva `frota.lista` (`frota_views.py:109`) — despachando para `main.excluir_veiculo` (`views/vehicles.py:162`, redirect 307 para `frota.deletar_veiculo`). É o modo de falha da lente 3 que este repo já sofreu 2x. E 🔬 `tests/test_browser_all_modules.py:640` exercita `/veiculos/relatorios`; e o teste congelado da B5.4 (`tests/test_b5_rdo_crud_url_map.py:60-62`) **exige as sombreadas registradas** — remover `crud_rdo.excluir` não é limpeza neutra, é reverter decisão da B5.4 por escrito. → o satélite **encolhe para o P provado** (Task B6.3) e o destino do layer inteiro vira item M na fila (§7), com condições escritas |
| **"Família A em `views/obras.py`: 10"** | levantamento B6-1 | 📖🔬 São **≥11 handlers / 13 sítios**: `criar_signatario_cliente` (`views/obras.py:3996`) resolve a obra por **helper** `_obra_do_tenant` (`:4002`) e escapa do scanner AST — cegueira **compartilhada e provada por reprodução** (o scanner da refutação também não o devolve); e os dois handlers de signatário (`:4045`, `:4080`) têm **dois** ramos 302 cada. **O censo de 39 da família A é PISO, não teto** → Step 0 do lote de obras: censo de lookups via helper nos 12 arquivos |
| **"Família B: 43 em 8 arquivos"** | levantamento B6-1 | 🔬 São **7 arquivos**, e a unidade está misturada: **45 chamadas / 43 handlers** (`views/vehicles.py` `:1345`+`:1347` no mesmo try; `views/dashboard.py` 3 aborts em 2 trys). → a asserção estática dos lotes conta **TRYs corrigidos por arquivo, com número re-medido pelo scanner na hora do lote** — nunca o número herdado deste documento |
| **"Espelhar o cinto multi-banco de `financeiro_service.py:96-107` como está ('mesmo banco ou estorne')"** | levantamento B6-2, Step 3(i) | 📖 A CR `OBRA_MEDICAO` é **acumulador de vida longa** com múltiplas baixas legítimas (o recalc reabre o saldo a cada medição nova e volta o status a PARCIAL — `medicao_service.py:467-477`; o modal tem "Sem vínculo bancário" como default, `contas_receber.html:271-272`). Após a 1ª baixa, `valor_recebido>0` é permanente: a 2ª medição recebida por outro banco dispararia o raise **para sempre** — e o próprio default D-B6.1 recusa estorno de OBR-MED: conta travada **sem saída**. 🔬 104 OBR-MED liquidadas provam fluxo vivo. → **cinto E gravação de `banco_id` escopados fora de `OBRA_MEDICAO`** (a D-B6.1 cobre os dois, não só o estorno) |
| **"O flash da guarda aponta 'mesmo banco ou estorne'"** | levantamento B6-2, Step 5 | A frase prometeria estorno em **três populações onde a guarda recusa** (OBR-MED por origem; as 102 PENDENTE/`valor_recebido>0`; as 24 QUITADA legadas de origem NULL). → padrão condicional da B5.1 (`financeiro_views.py:466-467`): a frase do estorno **só entra onde ele cumpre** |
| **"A gêmea `frota.novo_custo` usa o MESMO `CustoVeiculoService`"** | levantamento B6-3 | 📖 A frota só **importa** o service (`frota_views.py:14`); `frota.novo_custo` grava `FrotaDespesa` (alias de `CustoVeiculo`) **direto** (`:609-627`) e integra V2 via `registrar_custo_automatico` (`:630-653`). 🔬 O **único** caller de `criar_custo_veiculo` no repo é a própria rota morta (`views/vehicles.py:1849`) — a remoção **ORFANA** o método (`veiculos_services.py:388`), o oposto do afirmado. A morte da rota segue provada; o argumento era falso e **não pode ir para o comentário-registro** |
| **"`/veiculos/executivo` — link para rota inexistente do layer"** | levantamento B6-3 | 📖 O literal real é `/dashboards/veiculos/executivo` (`templates/dashboards/especificos.html:81`) — débito do módulo **dashboards**, não do layer `/veiculos`. Link quebrado confirmado (nenhum blueprint tem a rota); endereçamento corrigido no §7 |
| **"Censo: TODOS os `main.*` de vehicles têm zero refs externas exceto `excluir_veiculo` e os shims"** | levantamento B6-3 | 🔬 `tests/test_browser_all_modules.py:640` faz `_check_page(browser_session, "/veiculos/relatorios")` — `main.relatorios_veiculos` **tem** consumidor (suíte browser-noturno). Não afeta as 3 rotas do P; muda o tamanho e o mapa do item M |
| **"o import `:1586` segue usado por `lista_custos_veiculo:1702`"** | levantamento B6-3 (âncora) | 📖 `:1702` está dentro de `detalhes_veiculo` (`:1670`); `lista_custos_veiculo` é `:1048` e não usa o service. Conclusão (o import fica) sobrevive; a atribuição estava errada |
| **"Superfície da CP gêmea = tela de contas a pagar + fluxo"** | levantamento B6-4 | 📖 Há uma **segunda tela**: `fechamento_pagamentos` (`financeiro_views.py:1398-1437`) lista a CP gêmea PENDENTE no ciclo de pagamento e tem dropdown idêntico por `DISTINCT origem_tipo` (`:1433-1437`) + filtro por igualdade (`:1422-1423`). O chore do literal minúsculo em um só dropdown ficaria meio-feito, e a gêmea tem superfície de **pagamento em lote** não mapeada |
| **"⚠️ dev 06/08: 194 CRs liquidadas sem reversão"** | Task B5.6 (item (i) do "NÃO faz") | ⚠️ dev re-medido **no mesmo dia**: **239** (RECEBIDO 140 + QUITADA 99). Demonstração ao vivo da regra "toda medida leva data" |
| **"quem criar o estorno de recebimento herda a armadilha de origem dupla de LC do lado pagar"** | Task B5.6 (previsão escrita) | 🔬 A previsão **não se materializou**: `baixar_recebimento` não chama `gerar_lancamento_contabil_automatico`; o LC único já nasce carimbado `origem='FINANCEIRO_RECEBER'`/`origem_id` (`financeiro_service.py:405-406`). O delete-por-origem do molde B5.6 **casa de primeira, sem Step de carimbo** — o estorno do receber é MAIS simples que o do pagar nesse eixo, e mais complexo em dois outros (FC vivo; CR de medição) |
| **"Lote d (cauda) cabe num M"** | levantamento B6-1, proposta de recorte | Com o subcenso corrigido são ~19-22 sítios em 7 arquivos heterogêneos, um deles com censo de helpers pendente. **G disfarçado** → partido em dois (B6.7 obras; B6.8 cauda), cada um M de verdade |

**Consequência de método desta rodada:** o padrão "morto AFIRMADO derrubado pela lente
3" apareceu pela **terceira** vez (`form.action` com path literal em template-literal JS,
invisível a `url_for`/fetch-grep), e apareceu um padrão novo: **a cegueira compartilhada
de scanners AST a lookups via helper** — dois scanners independentes concordando não é
prova de teto, é prova de que os dois têm o mesmo ponto cego. Censos AST desta família
são **pisos**; o red-first paramétrico por rota×(alheio,inexistente) é quem fecha.

---

## 2. Os achados que só as lentes 2-5 pegaram

| Lente | Achado | Âncora | Por que a lente 1 não pegava |
|---|---|---|---|
| **3 TEMPLATE** | O caminho de exclusão da frota VIVA passa pelo layer "morto": `form.action` montado por template-literal JS com path literal `/veiculos/${id}/excluir` | `templates/veiculos_lista.html:761` (página renderizada por `frota_views.py:109`) | Zero `url_for`, zero fetch — grep por endpoint devolve vazio e autorizaria matar o delete da UI viva |
| **2 STRING** | O **único oráculo de enumeração vivo** da família 404: lookup **sem tenant** (`db.session.get`) seguido de mensagens distintas ("Entrega não encontrada" × "sem permissão") — admin de A enumera IDs de entregas de B | `views/admin.py:441-446` + `_admin_can_see_entrega` (`:364`) | Os dois ramos devolvem 302; só a comparação das strings de flash revela |
| **2 STRING** | `str(e)` nos excepts largos **vaza o texto do werkzeug no flash**: "404 Not Found: ..." aparece para o usuário como mensagem de erro | `ponto_views.py:719`, `propostas_consolidated.py:1031` | É formatação de string; o símbolo (`first_or_404`) está certo e presente |
| **3 TEMPLATE** | 4 rotas de propostas são consumidas por `fetch()` com `.json()` incondicional (3 de 4; a de whatsapp é fire-and-forget) — e o handler 404 global **não negocia JSON** (`error_handlers.py:48-53` renderiza `error.html` sempre) | `templates/propostas/detalhes_proposta.html:642,688,781,825` | → no lote a, essas rotas ganham `jsonify` 404 explícito, senão o 404 novo vira HTML dentro de `.json()` |
| **3 TEMPLATE** | `crud_servico_obra_real.py` (`:30`, `:65`): 2 rotas despacháveis com 🔬 **zero consumidor** em `templates/` + `static/js` | grep `'servicos-reais|servico-real'` → só o próprio `.py` | Indeterminadas — decisão barata no lote da cauda |
| **4 ROTA** | O despacho real do `/rdo` está **congelado por teste**: `crud_rdo.excluir` sombreada por `main.excluir_rdo` (já 404 pela B5.3); `crud_rdo.finalizar_rdo` e `rdo_editar.editar_rdo_form` **vencem** e estão na família | `tests/test_b5_rdo_crud_url_map.py:55-56,71` | Ler os decoradores sugere o contrário; o teste da B5.4 é a fonte |
| **4 ROTA** | `rdo_editar_sistema.py` (`:41`, `:188`) escopa por `RDO.admin_id` **direto** — o risco 4 da B5.3 herda: o lote põe `abort(404)` no ramo `if not`, **não troca a chave** | `rdo_editar_sistema.py:41-42,188-189` | O símbolo `filter_by` está presente e correto; o que muda é o **conjunto** de RDOs alcançáveis se alguém "unificar" |
| **5 SQL/DADO** | ⚠️ dev 06/08: a **família 2 está VAZIA** — 0 CPs `origem_tipo='gestao_custo_pai'`, 0 `'[REEMBOLSO]%'`, 0 `import_batch_id` em `conta_pagar`/`fluxo_caixa`/`gestao_custo_pai`: o caminho de gravação do import de fluxo **nunca rodou em dev**. A B6.2 é prevenção pré-deploy da FORMA, não incidente | ⚠️ dev (reproduzido pela refutação) | Nenhuma leitura de código diz se o parque tem exemplar |
| **5 SQL/DADO** | ⚠️ dev 06/08: **ZERO** FCs `'conta_receber'` com `banco_id` no parque inteiro (91 FCs totais), e só 21/239 CRs liquidadas têm FC algum — a hipótese "FC como fonte do estorno" morre pela mesma via (D) da B5.6 | ⚠️ dev | Idem — o esquema tem a coluna; o dado não |
| **5 SQL/DADO** | ⚠️ dev 06/08: **anomalia legada** — 102 CRs PENDENTE com `valor_recebido>0` (todas `origem_tipo` NULL, soma **R$ 422.127,00**) que **nenhum escritor atual produz**; e 🔬 **24 QUITADA de origem NULL** (99 − 75 OBR-MED) — QUITADA hoje só nasce em `medicao_service`, logo são de escritor extinto, **liquidadas e inestornáveis sem ninguém ter decidido isso** | ⚠️ dev + 🧮 (conferência dos escritores) | Só o GROUP BY revela; surfaceado pelo adversário a partir das próprias medidas do levantamento |
| **2 STRING** | O literal **minúsculo** `'gestao_custo_pai'` como `origem_tipo` de CP tem um único escritor (`importacao_excel.py:2427`) e **zero leitores** — e vazaria cru em **DOIS** dropdowns de categorias (`financeiro_views.py:251-255` e `:1433-1437`), onde todos os demais valores são MAIÚSCULOS | `importacao_excel.py:2427` | Homonímia perigosa: as outras 16 ocorrências do literal são `referencia_tabela` de FC e `ReembolsoFuncionario.origem_tabela` (outra tabela, outro fluxo) |
| **2 STRING** | A chave da gêmea da família 2 é **escrita uma vez e lida em lugar nenhum**: `ContaPagar.origem_id` → `gcp.id`, direta (mais forte que a da família 1, que passa por GCF) — a exclusão da B6.2 será o **primeiro leitor** | grep `ContaPagar.origem_id` → vazio | — |
| **3 TEMPLATE** | O texto do resultado do import **mente**: "apenas Fluxo de Caixa e Conta a Pagar foram criados" — o modo `apenas_pagamento` **não cria ContaPagar** (só FC) | `templates/importacao/resultado_fluxo.html:82-83` × `importacao_excel.py:2327-2346` | — |
| **5 SQL/DADO** | O rollback do batch do import apaga as gêmeas **juntas** (FC, CR, CP, GCF via pai, GCP — por `import_batch_id`, esquema da migração 103); um clone do `migrar` (sem batch) sobreviveria **órfão** | `importacao_views.py:980-1020`, `migrations.py:6279,9410-9433` | — |

**Onde as lentes vieram vazias, e isso é resultado:** 🔬 nenhum JS do repo trata
`status === 404` (grep vazio em `templates/` + `static/js`); 🔬 nenhum teste congela 302
para recurso alheio/inexistente nas rotas da família; 🔬 a lente 5 da família 404 não
achou **nada** (nenhuma migração/seed/script referencia essas rotas) — a família é forma
de **resposta HTTP**, sem superfície de dado. E a varredura suplementar do padrão
`if x.admin_id != ...` → redirect (o formato onde moraria oráculo) veio **VAZIA** — o
oráculo de `views/admin.py` é o único vivo.

---

## 3. As Tasks

Oito Tasks, na ordem de entrega recomendada (§5). O dinheiro primeiro (o precedente da
B5); a família 404 vira **cinco lotes** (B6.4–B6.8) com critério explícito de loteamento:
**por arquivo e por homogeneidade de correção** — lote a = "404 já escrito, engolido"
num arquivo só; lote b = idem, multi-arquivo pequeno; lote c = "404 não escrito" num
arquivo só; lotes d/e = a cauda partida (a correção do adversário: como um M só era G
disfarçado). Onde o adversário corrigiu o levantamento, **o texto da Task usa a versão
corrigida** e a correção fica visível na nota ao final.

**O molde comum dos lotes 404 (B6.4–B6.8) — escrito uma vez, válido para os cinco:**

- **Destino** (D-B6.4, default SIM): 404 HTML via `templates/error.html`, sem flash e sem
  redirect, com **corpo idêntico** para alheio e inexistente (o critério-oráculo da
  B5.3); rotas consumidas por fetch devolvem **JSON 404 explícito** (o handler global
  não negocia JSON — `error_handlers.py:48-53`).
- **A ordem dos Steps é lei** (risco 1 da B5.3, vale para todos): o ramo
  `except HTTPException: raise` — no formato de `views/rdo.py:303`, com o comentário —
  entra **ANTES** do Step das guardas. `abort(404)` dentro de try sem o ramo fecha a
  Task **verde sem mudar nada**.
- **Arreio red-first paramétrico por lote**: tabela rota×método×(alheio, inexistente)
  com dois tenants; asserção 404 + corpo idêntico entre os dois casos + **efeito nulo**
  nos deletes/POSTs (o registro alheio sobrevive).
- **Mutação amostrada** (declarada: o que foi amostrado e o que foi conferido um a um) +
  **asserção estática de contagem dos TRYs corrigidos por arquivo, com o número
  re-medido pelo scanner na hora do lote** — nunca o número herdado deste documento
  (contradição 11, §8).
- **Fora da família, com critério escrito:** (i) lookups cujo id vem do **FORM** —
  validação de formulário, flash+redirect é a UX correta (precedente: Step 5 da B5.3);
  (ii) APIs JSON já conformes; (iii) falso-positivos provados (`compras_views.py:1055`,
  `medicao_views.py:368`, `views/obras.py:1540` — este congelado por
  `tests/test_fase1_escopo_obra.py:415`); (iv) o **eixo OBRA fora de RDO**
  (`pode_ver_obra` em leitura) — é OUTRA guarda, não a forma da resposta: item próprio
  na fila (§7); (v) `views/vehicles.py` — as 2 da família A provadas mortas saem na
  B6.3; as demais aguardam o item M (§7), **alcançáveis por URL até lá** (risco
  declarado, não escondido).
- **PROIBIDO rodar a suíte na sessão de recorte** — o red-first roda na execução de cada
  lote (banco único).

---

### Task B6.1: o estorno de recebimento nasce inteiro — debita o banco, apaga FC e LC

**Files:** Modify `migrations.py` — **migração 281, alocada POR ESCRITO neste documento**
(`_migration_281_conta_receber_banco_id`, espelho textual da 280 em `:6116-6145`);
Modify `models.py` — `ContaReceber` (`:2471-2514`) ganha `banco_id` nullable;
Modify `financeiro_service.py` — `baixar_recebimento` (`:342-452`);
Modify `financeiro_views.py` — rota nova `POST /financeiro/contas-receber/<int:conta_id>/estornar`
+ flash condicional da guarda B3.7 (`:763-775`);
Modify `templates/financeiro/contas_receber.html` — botão/form de estorno **próprio**;
Create `tests/test_b6_estorno_recebimento.py`

**O fato.** 🔬 grep `estorn` fora de archive/tests: só `estornar_conta`
(`financeiro_views.py:298`), `estornar_gcp` (`:367`) e `contabilidade.estornar_lancamento`
(`contabilidade_views.py:438`) — **não existe estorno de recebimento**, e
`baixar_recebimento` tem chamador único (`financeiro_views.py:787`).

**A pergunta central, e a resposta é NÃO — o retrato exato da B5.6.** O banco do crédito
**não é recuperável** por nenhuma das três vias: (1) 📖 `ContaReceber` não tem `banco_id`
(`models.py:2471-2514`, conferido coluna a coluna); a baixa recebe `banco_id` por
parâmetro, credita `banco.saldo_atual += valor` (`financeiro_service.py:370`) e **o
descarta**; (2) o FC ENTRADA existe **só por checkbox** do modal
(`financeiro_views.py:806`; checked por default no modal vivo,
`contas_receber.html:284`, mas ausente na página órfã `receber_conta.html` e no import),
e ⚠️ dev 06/08: das 239 liquidadas só **21** têm FC, e **ZERO** FCs `'conta_receber'` do
parque têm `banco_id`; (3) o LC `FINANCEIRO_RECEBER` não carrega banco
(`:400-437` — banco só como texto no histórico). **Resposta: migração 281** —
`conta_receber.banco_id` nullable, gravado na baixa apenas quando o crédito de fato
ocorreu; NULL avisa e debita **zero** (nunca inventar débito, simétrico ao "nunca
inventar crédito" da 280).

**O que o receber tem a MAIS que o pagar** (e a B5.6 não tinha): (a) o **FC ENTRADA é
vivo** — escritor no modal com checkbox checked, leitor `rr_query`
(`financeiro_service.py:774-796`) no fluxo realizado: estorno sem delete de FC deixa
**entrada fantasma** (o simétrico do vazamento nº3 da B5.6) → o passo-FC de
`estornar_gcp` (`:387-397`) é obrigatório aqui; (b) a CR de **medição**
(`origem_tipo='OBRA_MEDICAO'`, 🔬 337 no parque, 104 liquidadas) é um **acumulador com
UPSERT** que o recalc reescreve (`medicao_service.py:363-489`; `valor_original` =
`valor_medido`, **móvel**; QUITADA só nasce em `:443`/`:473`) e é exibida no portal do
cliente (`portal_obras_views.py:276`).

**O que o receber tem a MENOS:** 🔬 a "armadilha de origem dupla de LC" prevista pela
B5.6 **não existe** — o LC único da baixa já nasce carimbado
`origem='FINANCEIRO_RECEBER'`/`origem_id=conta_id` (`financeiro_service.py:405-406`),
zero leitores hoje; o delete-por-origem casa de primeira, sem Step de carimbo. Partidas
caem por cascade (`models.py:3263`). Nenhum FK aponta para FC `'conta_receber'` — o
delete de FC não precisa de limpeza de ponteiro (🔬 único FK para `fluxo_caixa` é
`GestaoCustoPai.fluxo_caixa_id`).

⚠️ **Correção do adversário, adotada, e ela é a mais séria da rodada:** o cinto
multi-banco **não pode ser espelho literal** de `financeiro_service.py:96-107`. Num
acumulador de múltiplas baixas, "o banco do crédito" em coluna única é mal-definido, e o
cinto por valor congelaria o caminho bancário da 1ª baixa **para sempre** — com o
estorno (a válvula de escape do lado pagar) **recusado por origem** pelo próprio default
D-B6.1. O risco real não era o estorno errado: era a **baixa de medição** — fluxo vivo e
recorrente — passar a falhar com ValueError engolido em flash genérico
(`financeiro_views.py:837-839`) na primeira obra que trocasse de banco entre medições.
→ **cinto e gravação de `conta.banco_id` NÃO se aplicam quando
`origem_tipo='OBRA_MEDICAO'`** (a CR de medição segue como hoje: credita e descarta).

**Comportamento novo.**
1. Migração 281 + `ContaReceber.banco_id` nullable (comentário-molde de
   `models.py:2444-2449`).
2. `baixar_recebimento`: cinto da coluna única **escopado** (raise se
   `valor_recebido > 0` e `banco_id` difere — gatilho por VALOR, lição (ii) da WF-3 —
   **exceto** OBR-MED) e `conta.banco_id = banco_id` só quando o crédito ocorreu
   (espelho de `:128-131`), **exceto** OBR-MED.
3. Rota `estornar_recebimento`, molde `estornar_conta` FUNDIDO com o passo-FC de
   `estornar_gcp`: guarda `status in ('RECEBIDO','PARCIAL')` **e**
   `origem_tipo != 'OBRA_MEDICAO'` (D-B6.1); capturar `_valor` e `_banco_id` **antes**
   de zerar; zerar `valor_recebido`/`data_recebimento`/`forma_recebimento`,
   `saldo = valor_original`, status PENDENTE; **DEBITAR** `banco.saldo_atual -= valor`
   (direção invertida do pagar — é o único débito novo do sistema; o par é
   `financeiro_service.py:127`) com aviso-sem-inventar-débito quando banco NULL/sumido;
   `conta.banco_id = None` no mesmo movimento; DELETE FCs
   `referencia_tabela='conta_receber'`/`referencia_id=conta_id`; DELETE LCs
   `origem='FINANCEIRO_RECEBER'`/`origem_id=conta_id`; commit único.
4. Flash da guarda B3.7 do receber: **condicional** — a frase "para refazer, estorne" só
   entra quando o estorno de fato cumpre (não em OBR-MED, não nas legadas fora da
   guarda). Padrão da B5.1 (`financeiro_views.py:466-467`).
5. Botão/form de estorno em `contas_receber.html`, form **PRÓPRIO** — não repetir o
   `formEstorno` compartilhado de `contas_pagar.html:449-465`, a armadilha registrada
   na hipótese B da B5.6.

**Teste que prova.** Tenant próprio com `BancoEmpresa` de saldo conhecido; molde de
`tests/test_b5_estorno_devolve_banco.py`. ⚠️ O oráculo do caso 3 (`rr_query`) filtra por
`data_movimento` e `obra_id` — o arreio **fixa data dentro da janela consultada e
`obra_id` coerente**, senão o caso fica verde-e-oco por filtro (achado do adversário).

| # | Ação | Asserção |
|---|---|---|
| 1 | baixa de R$ 1.000 com `banco_id` → estorno | `saldo_atual` volta; `conta.banco_id` limpo; status PENDENTE; `saldo = valor_original` |
| 2 | baixa **sem** banco → estorno | débito **zero** + aviso — nenhum débito inventado |
| 3 | baixa com FC ENTRADA (checkbox) → estorno | FC some do `rr_query` (data/obra **dentro da janela** — cão de guarda do verde-e-oco) |
| 4 | baixa de CR com conta contábil → estorno | LC `FINANCEIRO_RECEBER` apagado (partidas via cascade); re-baixa **não dobra** |
| 5 | parcial de 400 no banco A → parcial de 600 no banco B (CR comum) | recusa com flash; 600 no banco A completa RECEBIDO |
| 6 | CR `OBRA_MEDICAO` (mesmo em RECEBIDO) → tentativa de estorno | recusada com flash **por origem** |
| 7 | CR `OBRA_MEDICAO`: 2ª baixa com **outro** banco | **passa** — o cinto não se aplica (cão de guarda do escopo; é o caso que quebraria produção) |
| 8 | ciclo estornar → re-baixar | passa a guarda B3.7 (PENDENTE, saldo cheio); nada dobra (banco, FC, LC) |
| 9 | CR legada RECEBIDO com `banco_id` NULL (forma do import, `importacao_excel.py:2469-2503`) → estorno | débito zero + aviso — o import nunca creditou `saldo_atual` |

Mutações cirúrgicas (espelho da B5.6): débito desligado derruba só 1; delete de FC
removido derruba só 3; delete de LC removido derruba só 4; cinto removido derruba só 5;
**escopo do cinto removido derruba só 7**.

**Riscos → mitigação.**
1. **O cinto sem escopo trava a baixa de medição em produção** (o erro derrubado). → o
   escopo OBR-MED é parte da D-B6.1 e o caso 7 é o cão de guarda.
2. **Flash prometendo estorno onde a guarda recusa** (OBR-MED; 102 PENDENTE anômalas; 24
   QUITADA legadas). → frase condicional (comportamento 4).
3. **Verde-e-oco no oráculo `rr_query`** por janela de data/obra. → fixação explícita no
   arreio (caso 3).
4. **`contabilidade.estornar_lancamento`** (`contabilidade_views.py:438`) pode já ter
   revertido manualmente um LC `FINANCEIRO_RECEBER`; o delete-por-origem apagaria o
   original e deixaria a reversão órfã — contabilidade revertida duas vezes. Baixa
   probabilidade (20 LCs no parque); **registrado**, sem caso de teste nesta Task.
5. **Migração é recurso disputado.** A 281 fica **gasta por alocação neste documento**;
   quem tocar `migrations.py` antes confere o §5. 282-283 seguem livres; 271-276
   reservadas da Fase 6.
6. **As 24 QUITADA de origem NULL** ficam liquidadas e inestornáveis pela guarda por
   status — **sem ninguém ter decidido**. → uma linha na D-B6.1 e no inventário da
   anomalia (§7); não muda o recorte.

**O que esta Task NÃO faz.** Estorno de CR de medição (a alternativa — chamar
`recalcular_medicao_obra` após zerar + decidir a exibição no portal — fica escrita como
recorte futuro na D-B6.1); a anomalia das 102 PENDENTE/`valor_recebido>0` (inventário
próprio, §7); a página órfã `receber_conta.html` (candidata ao tratamento que a D-B5.1
deu ao lado pagar, §7); a validação de overpay (`valor_recebido <= saldo` — registrada,
§7).

- [ ] **Step 0:** decisão **D-B6.1** (§9, default escrito) — a Task executa o default sem esperar
- [ ] **Step 1:** escrever `_migration_281_conta_receber_banco_id` (espelho da 280: nullable, IF NOT EXISTS, FK `banco_empresa` sem cascade) — a alocação já está feita **aqui**
- [ ] **Step 2:** `models.py` — `ContaReceber.banco_id` + comentário-molde
- [ ] **Step 3:** escrever o teste e ver vermelhos os casos 1/3/4 (e 6/7 vermelhos por rota inexistente); 2/5/8/9 nascem com a implementação
- [ ] **Step 4:** `baixar_recebimento` — cinto escopado + gravação escopada (fora de OBR-MED)
- [ ] **Step 5:** rota `estornar_recebimento` completa (captura → zera → debita → apaga FC → apaga LC → commit único)
- [ ] **Step 6:** flash condicional da guarda B3.7 + form próprio no template
- [ ] **Step 7:** nove casos verdes; as cinco mutações medidas, cada uma derrubando só o seu caso
- [ ] **Step 8:** commit — `feat(financeiro): estorno de recebimento debita o banco e apaga FC e LC (migracao 281)`

**Esforço: M** (o ajuste do cinto é um if de escopo, não recorte novo — conferido pelo
adversário). **Migração: SIM — 281, alocada por escrito NESTE documento.**

> **Nota — o que o adversário corrigiu neste levantamento.** (a) O cinto espelhado sem
> escopo quebraria a baixa de medição (fluxo vivo, 104 liquidadas) — corrigido para
> escopo por origem, e a D-B6.1 passou a cobrir o cinto além do estorno. (b) O flash do
> Step 5 prometia estorno em três populações onde a guarda recusa — virou condicional.
> (c) As 24 QUITADA de origem NULL (derivável das medidas do levantamento, nunca
> surfaceado) entram na D e no inventário. (d) O oráculo `rr_query` do caso de FC
> precisa de janela fixada, senão verde-e-oco. (e) A interação com
> `contabilidade.estornar_lancamento` registrada. Todas as medidas ⚠️ dev reproduzidas
> pela refutação (inclusive R$ 422.127,00 exato).

---

### Task B6.2: a família 2 de gêmeos ganha regra — e o `migrar` para de clonar no 1º clique

**Files:** Modify `gestao_custos_views.py` — guard de `migrar_contas_pagar` (`:1363`);
Modify `financeiro_views.py` — exclusão da família 2 em `listar_contas_pagar`
(`:196-217`, KPIs `:242-245`); Modify `financeiro_service.py` — `calcular_fluxo_caixa`
(previstas `:571`, fallback `:629`, detalhes/buckets por derivação);
Modify `templates/importacao/resultado_fluxo.html` — `:83`;
Create `tests/test_b6_familia2_reembolso_import.py`

**O fato, com a correção de tamanho na frente:** ⚠️ dev 06/08 (reproduzido pela
refutação): a família 2 tem **ZERO exemplares** — o caminho de gravação do import de
fluxo nunca rodou em dev. **É prevenção pré-deploy da forma, não incidente medível.** O
teste É o exemplar.

**O mecanismo.** 📖 `services/importacao_excel.py:2400-2431`: no modo normal com
checkbox de reembolso (pré-marcado por keyword 'reembolso'/'adiantamento', `:1352-1354`;
`preview_fluxo.html:571-577`), o import cria GCP (`:2353-2365`) + GCF **sem
`origem_tabela`** (`:2368-2376` — invisível a toda exclusão por GCF) + FC
`'gestao_custo_pai'` se PAGO (`:2379-2397`) + **CP gêmea** com
`origem_tipo='gestao_custo_pai'` (minúsculo, `:2427`) e `origem_id=gcp.id` —
chave **direta**, mais forte que a da família 1.

**A dupla contagem é real e na MESMA tela:** 📖 `financeiro_views.py:196-208` só exclui
GCP com filho `'pedido_compra'` — o GCF do import tem origem NULL, então a GCP do
reembolso **entra** em `custos_v2` junto da CP na tabela principal, e o KPI soma as
duas (`resumo['pendentes'] = pendentes(CP) + valor_v2(GCP)`, `:245`; idem
vencidas/a_vencer `:243-244`). No **fluxo**, a GCP PENDENTE entra em `saidas_previstas`
(exclusão de `financeiro_service.py:556-571` restrita por escrito a `'pedido_compra'`,
com o comentário `:550-552` remetendo as famílias 2 e 3 a regra própria) enquanto a CP é
invisível — pagar a CP pela tela debita banco e deixa a prevista **eterna**: o defeito
exato que a B5.7 fechou para a família 1. ⚠️ E o adversário mapeou a **segunda tela**: a
CP gêmea PENDENTE entra em `fechamento_pagamentos` (`financeiro_views.py:1398-1425`) e
pode ser paga **em ciclo**.

**O buraco do migrar, reproduzido por leitura:** 📖 `gestao_custos_views.py:1337-1365` —
a query pega toda CP PENDENTE/PARCIAL; guard 1 (`:1344-1351`) só vê clones desta rota
(pega no 2º clique); guard 2 (`:1363`) só pula `upper()=='COMPRA'`. CP
`'gestao_custo_pai'` PENDENTE é **clonada no 1º clique** e o clone escapa de todas as
exclusões → tripla contagem. E o botão promete "Esta ação é segura e pode ser repetida"
(`templates/custos/gestao.html:21-26`).

**O `apenas_pagamento` NÃO é defeito** — é o modo anti-duplicação funcionando como
desenhado (📖 `:2327-2346`: cria SÓ FC SAIDA com referência NULL, que cai no `fd_query`
como "Lançamento Direto" editável; sugerido quando o custo já existe, `:2072-2081`). O
único erro objetivo é o **texto** de `resultado_fluxo.html:83`, que promete uma
ContaPagar que o modo não cria. Veredito: **registro + chore de texto**, não Task de
correção (D-B6.2).

**Comportamento novo.**
1. Guard do migrar vira skip incondicional:
   `if (conta.origem_tipo or '').upper() in ('COMPRA', 'GESTAO_CUSTO_PAI')` — o
   `.upper()` normaliza o minúsculo do import; estende o comentário-precedente de
   `:1353-1362` ("sem id não há como provar que NÃO tem gêmea; o lado seguro é não
   clonar").
2. Exclusão da família 2 nas MESMAS pontas da B5.7, com a subquery
   `SELECT origem_id FROM conta_pagar WHERE admin_id=:a AND
   upper(origem_tipo)='GESTAO_CUSTO_PAI' AND origem_id IS NOT NULL` — **`admin_id` não
   opcional** (regra da casa da contradição 9 da B5): `custos_v2`/`custos_v2_abertos`
   da tela (`financeiro_views.py:204-217` + KPIs) e as pontas do fluxo (previstas
   `:571`; fallback `:629` — quase redundante para a família 2, pois GCP PAGO do import
   sempre tem FC e o dedup `ids_gc_no_fluxo` (`:719-735`) já o pega, mas entra por
   simetria com a B5.7; detalhes/buckets por derivação). Comentário datado remetendo a
   este documento.
3. Chore: `resultado_fluxo.html:83` perde a menção à ContaPagar inexistente. Opcional P:
   origem "Importação (extrato)" no detalhe quando `fc.import_batch_id` não-nulo
   (`financeiro_service.py:759-770`).

**Teste que prova.** Montagem por ORM da forma EXATA do import (GCP PENDENTE + GCF sem
origem + CP gêmea minúscula com `origem_id=gcp.id`) — dev não tem exemplar; fixture v2
ativa. Molde: `tests/test_b5_fluxo_gemeos_e_orfaos.py`.

| # | Ação | Asserção |
|---|---|---|
| 1 | `POST /gestao-custos/migrar-contas-pagar` 1x | **zero** GCP novo (hoje: clona no 1º clique — vermelho) |
| 2 | tela de contas a pagar | GCP fora de `custos_v2`; `resumo['pendentes']` conta a obrigação **uma** vez (hoje vermelho) |
| 3 | fluxo de caixa | GCP fora de `saidas_previstas` e dos buckets (vermelho **nas previstas**, não no fallback) |
| 4 | GCP sem gêmea (origem manual) | continua em custos_v2 e nas previstas (guarda verde) |
| 5 | CP gêmea de OUTRO tenant com `origem_id` colidindo | **não** exclui (cão de guarda do `admin_id`) |
| 6 | rollback do batch | apaga CP+GCP+GCF+FC **juntos** (guarda verde do mecanismo) |

Mutações: restaurar o guard antigo derruba só 1; tirar o `admin_id` da subquery derruba
só 5; restaurar uma ponta derruba só o caso da ponta.

**Riscos → mitigação.**
1. **Subquery sem `admin_id` = misjoin** (o erro que a B5.7 mediu duas vezes). → caso 5.
2. **A CP gêmea segue pagável em DUAS telas** (contas a pagar e fechamento) e o GCP na
   tela própria de gestão — **pagamento duplo em dinheiro** segue possível sem
   acoplamento de status (assimetria herdada de D-B5.7(1), default (2) mantido). O nome
   do risco vai por extenso na D-B6.2 e no §7 — não é só "prevista eterna". E como o
   escritor de FC `'conta_pagar'` morreu (`f69cb359`), o lado CP do pagamento duplo nem
   aparece no realizado.
3. **O chore do literal minúsculo** (se um dia for feito) tem de cobrir os DOIS dropdowns
   (`:251-255` e `:1433-1437`) + o filtro `:1422-1423` — registrado no §7, muda dado
   gravado, não entra aqui.
4. **Teto de M**: os casos 2/3 exigem fixture v2 completa; sem folga para escopo extra
   na mesma sessão (conferido pelo adversário).
5. **`saidas_v2_pagas` (`:645`) agrega sem o dedup do detalhe** — buraco pré-existente
   que a ponta `:629` tangencia; nenhum caso de teste desta Task o lê (conferir na
   escrita do arreio).

**O que esta Task NÃO faz.** Acoplamento de status entre gêmeas (a mesma pergunta da
D-B5.7(1) — default (2) mantido, buraco declarado); a possível **quarta família**
ALIMENTACAO (§7); qualquer mudança no comportamento do import; a normalização do
literal minúsculo no escritor.

- [ ] **Step 0:** registrar a **D-B6.2** (§9); a Task executa o default sem esperar
- [ ] **Step 1:** escrever o teste (a forma do import montada por ORM) e ver vermelhos 1/2/3; 4/5/6 nascem como guardas
- [ ] **Step 2:** guard do migrar — skip incondicional `('COMPRA', 'GESTAO_CUSTO_PAI')`
- [ ] **Step 3:** exclusão da família 2 na tela (custos_v2 + KPIs) e no fluxo (previstas; fallback por simetria; buckets)
- [ ] **Step 4:** chore de `resultado_fluxo.html:83` (+ rótulo opcional de origem)
- [ ] **Step 5:** seis casos verdes; três mutações medidas
- [ ] **Step 6:** dois commits — `fix(financeiro): familia 2 de gemeos sai da tela e do fluxo; migrar nao clona reembolso` e `chore(importacao): o texto do apenas_pagamento para de prometer ContaPagar`

**Esforço: M** (teto). **Migração: não** (a 103 já deu `import_batch_id` às 4 tabelas —
📖 `migrations.py:6279`, `:9410-9433`).

> **Nota — o que o adversário corrigiu neste levantamento.** (a) A superfície da CP
> gêmea tem uma segunda tela — `fechamento_pagamentos` — com dropdown e filtro próprios,
> e pagamento em lote; o risco real é **pagamento duplo em dinheiro**, silencioso e sem
> FC do lado CP, não só exibição. (b) A ponta do fallback `:629` é quase redundante para
> esta família (FC sempre existe se PAGO; dedup `:719-735`) — o vermelho do caso 3 é
> nas previstas. (c) `saidas_v2_pagas` sem dedup registrado. Tudo o mais confirmado
> letra a letra, incluindo o clone do 1º clique e a família vazia em dev.

---

### Task B6.3: vehicles — as três rotas mortas saem, com a morte PROVADA

**Files:** Modify `views/vehicles.py` — deletes `:765-820`
(`novo_custo_veiculo_lista` + cabeçalho), `:1626-1667` (`novo_veiculo_OLD`, sob
D-B6.3), `:1791-1869` (`novo_custo_veiculo_form` + cabeçalho); Edit `:825-838`
(comentário-registro da B5.7); Modify `MODULOS.md` — linhas **258, 259, 270, 273**;
Modify `tests/test_b5_fluxo_gemeos_e_orfaos.py` — estender o caso 6 (`:204-205`)

**O fato.** A B5.7 removeu `main.novo_custo_veiculo` e deixou as irmãs **citadas** para
limpeza própria (risco 3) — morte AFIRMADA, não provada. Esta rodada provou, pelas cinco
lentes, na árvore `26dff528` (🔬 06/08, reproduzido pela refutação):
1. **`main.novo_custo_veiculo_lista`** (`views/vehicles.py:766-820`, POST
   `/veiculos/custo`): zero consumo em todas as lentes; POST-only sem nenhum form/fetch
   apontando — inalcançável até por URL digitada.
2. **`main.novo_custo_veiculo_form`** (`:1792-1869`, `/veiculos/<id>/custo/novo`): zero
   consumo; a frota tem rota viva de mesma capacidade (`frota.novo_custo`,
   `frota_views.py:548`, linkada 2x por `url_for`) usando o **mesmo template** — e 📖 o
   form do próprio template que a rota morta renderiza **posta para
   `frota.novo_custo`** (`custo_veiculo_novo.html:419`): até quem chegasse ao GET morto
   acabaria na frota no submit.
3. **`main.novo_veiculo_OLD`** (`:1627-1667`): o próprio comentário `:1626` diz "ROTA
   ANTIGA DESATIVADA"; zero refs; template `veiculos_novo.html` compartilhado com a
   frota viva (fica). Entra sob a D-B6.3 (default SIM).

**O que NÃO morre junto** (conferido): `custo_veiculo_novo.html` (usado por
`frota_views.py:579/601/667`); `veiculos_novo.html` (`frota_views.py:137/153/186`); o
import de `:1586` (usado por `detalhes_veiculo` via `:1702`); os shims deliberados
`:1610-1624` (`/veiculos`→`frota.lista`, `/veiculos/novo`→`frota.novo`);
`main.excluir_veiculo` (`:162` — **vivo por path literal**, `veiculos_lista.html:761`).

⚠️ **Correção do adversário, adotada, e ela muda o texto que vai para o código:**
`CustoVeiculoService.criar_custo_veiculo` fica **ÓRFÃO** com a remoção — o único caller
do repo é a rota morta (`:1849`); a frota **não** usa o método (grava `FrotaDespesa`
direto + V2, `frota_views.py:609-653`). O comentário-registro **não pode** dizer "mesmo
service da frota" (afirmação falsa que viraria verdade de referência — o mecanismo
exato que fez a B5.7 herdar morte afirmada); o método órfão fica **registrado como
pendência** no comentário e no §7.

**Comportamento novo.**
1. As três rotas saem inteiras (ranges acima, incluindo os comentários-cabeçalho).
2. O comentário-registro `:825-838` perde as linhas 837-838 e ganha uma linha datada: as
   irmãs e a `novo_veiculo_OLD` saíram nesta Task; a família `main.*` de registro de
   custo está extinta; a viva é `frota.novo_custo` (**mesmo template; service NÃO — a
   frota grava direto**); `criar_custo_veiculo` (`veiculos_services.py:388`) ficou órfão
   — pendência registrada.
3. `MODULOS.md`: saem **258** (lista), **273** (form), **270** (`novo_veiculo_OLD`) e a
   **259** — stale desde a B5.7 (ainda lista `main.novo_custo_veiculo`), consertada no
   mesmo commit.
4. O caso 6 de `tests/test_b5_fluxo_gemeos_e_orfaos.py:204-205` é estendido para afirmar
   a **ausência no url_map** dos 4 endpoints (`main.novo_custo_veiculo`,
   `..._lista`, `..._form`, `main.novo_veiculo_OLD`) — congela a família extinta.
   Escrever, **não rodar** localmente (banco único; o gate roda no CI —
   `.github/workflows/gate.yml:55,115`).

**Teste que prova.**

| # | Ação | Asserção |
|---|---|---|
| 1 | url_map após o corte | nenhum dos 4 endpoints existe; nenhuma outra regra muda de despacho |
| 2 | os compartilhados | `frota.novo_custo` segue no map; `custo_veiculo_novo.html`/`veiculos_novo.html` seguem renderizáveis pela frota |
| 3 | o teste congelado da B5.4 | `tests/test_b5_rdo_crud_url_map.py` **intocado e verde** (as remoções não tocam `rdo_crud`) |

**Riscos → mitigação.**
1. **Plantar afirmação falsa no registro** ("mesmo service") — corrigido acima; é o
   risco subestimado nº1 do veredito.
2. **`criar_custo_veiculo` órfão vira símbolo presente que mente** (import usado pela
   classe, método sem caller) — o padrão que já enganou o grep 1x. → pendência
   registrada por escrito (comentário + §7).
3. **MODULOS.md:270 esquecida** criaria exatamente a linha stale que o Step conserta na
   259. → as quatro linhas no mesmo commit.
4. **Não tocar** em `excluir_veiculo`, nos shims, nem em nada do item M — matar rota ≠
   consertar resposta, e o layer tem caminho vivo (§1.2).

- [ ] **Step 0:** **D-B6.3** (§9, default SIM) — a Task executa o default
- [ ] **Step 1:** estender o caso 6 do teste (4 endpoints ausentes) e vê-lo **vermelho** (as rotas ainda existem)
- [ ] **Step 2:** deletes dos três ranges; Edit do comentário-registro com o texto corrigido (sem "mesmo service"; pendência do método órfão)
- [ ] **Step 3:** MODULOS.md — as quatro linhas (258, 259, 270, 273)
- [ ] **Step 4:** commit — `chore(vehicles): remove as tres rotas mortas provadas e corrige o registro (MODULOS 259 stale)`

**Esforço: P.** **Migração: não.**

> **Nota — o que o adversário corrigiu neste levantamento.** (a) "Mesmo
> CustoVeiculoService" era falso — a frota grava direto + V2; a remoção orfana
> `criar_custo_veiculo` (registrado). (b) O link quebrado é
> `/dashboards/veiculos/executivo` (módulo dashboards), não do layer. (c) O censo "zero
> refs em tudo" está furado para `relatorios_veiculos` (teste browser) — muda o item M,
> não este P. (d) A âncora do consumidor do import era `detalhes_veiculo`, não
> `lista_custos_veiculo`. (e) MODULOS.md:270 entrou no Step. As cinco lentes da morte
> das três rotas foram reproduzidas e confirmadas.

---

### Task B6.4: 404 — lote a: `propostas_consolidated.py` (18 handlers com 404 escrito e engolido)

**Files:** Modify `propostas_consolidated.py` — import de `HTTPException` + ramo
`except HTTPException: raise` nos 18 excepts (handlers iniciando em
`:978,:1041,:1059,:1160,:1322,:1365,:1516,:1584,:1607,:1957,:2257,:2280,:2327,:2447,:2519,:2897,:3003,:3103`
— 🔬 reproduzidos pela refutação; re-medir na hora); `jsonify` 404 explícito nas 4
rotas fetch; Create `tests/test_b6_404_propostas.py`

**O fato.** 📖 18 `first_or_404` tenant-scoped **dentro** de try com `except Exception`
que flasha/jsonifica e redireciona — o 404 está escrito e é engolido; 🔬 zero
`except HTTPException` no arquivo. As 6 demais ocorrências do arquivo estão corretamente
fora (3 fora de try; 3 do portal por token). 📖 4 consumidores fetch
(`detalhes_proposta.html:642,688,781,825` — 3 com `.json()` incondicional; o de whatsapp
é fire-and-forget) e o handler global não negocia JSON (`error_handlers.py:48-53`).
Bônus da correção: some o vazamento de `str(e)` ("404 Not Found: ...") no flash
(`:1031`).

**Comportamento novo.** O ramo `except HTTPException: raise` no formato de
`views/rdo.py:303` (com o comentário) em cada um dos 18 excepts; as 4 rotas fetch
(status, whatsapp/registrar, upload-arquivo, arquivo/delete) devolvem
`jsonify(...), 404` explícito (padrão de `api_dados_veiculo`). **Sem** step de "congelar
o alias `/editar/<id>`" — a colisão não existe (§1.2).

**Teste que prova** (o molde comum do §3): tabela rota×método×(alheio, inexistente),
404 + corpo idêntico + efeito nulo nos POSTs/deletes; as 4 fetch asseridas com
`content_type` JSON. Mutação amostrada em 3 handlers (um HTML GET, um JSON POST, um
delete) — **declarado o que foi amostrado**; asserção estática: contagem de TRYs com o
ramo novo, número re-medido pelo scanner na hora.

**Riscos → mitigação.** (1) risco 1 da B5.3 — ramo antes das guardas (aqui as guardas já
existem; só o ramo falta); (2) a homogeneidade dos corpos dos 18 excepts (HTML × JSON ×
`success:false`) foi olhada **por amostra** — o desenho do paramétrico confere rota a
rota na escrita do arreio; (3) rotas do portal por token ficam fora (critério escrito).

- [ ] **Step 0:** re-medir o censo do arquivo com o scanner (asserção estática usa ESTE número)
- [ ] **Step 1:** teste paramétrico red-first — ver os 302/200 atuais vermelhos
- [ ] **Step 2:** import + ramo `except HTTPException: raise` nos 18
- [ ] **Step 3:** `jsonify` 404 nas 4 rotas fetch
- [ ] **Step 4:** verdes; mutação amostrada (3 handlers) + asserção estática de TRYs
- [ ] **Step 5:** commit — `fix(propostas): 404 escrito deixa de ser engolido; rotas fetch devolvem JSON 404`

**Esforço: M.** **Migração: não.**

---

### Task B6.5: 404 — lote b: a miscelânea homogênea (14 handlers, 5 arquivos)

**Files:** Modify `ponto_views.py` (5: `:637,:731,:1027,:1101,:1228`; excepts
`:717,:755,:1088,:1120,:1278`), `configuracoes_views.py` (5: `:341,:498,:625,:754,:779`),
`alimentacao_views.py` (1: `:151`), `views/obras.py` (1: `excluir_obra` `:1276`, except
`:1379`), `views/dashboard.py` (2 trys: `:231/:475` e `:528/:944` — variante
401/403-engolido); Create `tests/test_b6_404_miscelanea.py`

**O fato.** 📖 Mesma mecânica do lote a: `first_or_404`/`abort` tenant-scoped engolidos
por except largo, em arquivos com poucos casos cada. A variante de `views/dashboard.py`
engole `abort(401)`/`abort(403)` (3 aborts em 2 trys — a contagem por TRY é a que vale).
Bônus: some o `str(e)` vazando no flash (`ponto_views.py:719`).

**Comportamento novo.** Ramo `except HTTPException: raise` antes, formato
`views/rdo.py:303`; nota escrita sobre a posição do ramo relativa ao `rollback` (risco 2
da B5.3). Em `views/obras.py`, tocar **só** `excluir_obra` — o resto do arquivo é do
lote d (B6.7), serialização no §5.

**Teste que prova:** o molde comum; para o dashboard, caso extra: destravar o 401 **não
muda o fluxo de login** (hoje o 401 era mascarado como página com flash — confirmar em
execução).

**Riscos → mitigação.** (1) ordem ramo × rollback documentada por handler; (2)
`excluir_obra` tem efeito destrutivo — o caso de efeito nulo é obrigatório; (3) o número
de TRYs por arquivo re-medido na hora.

- [ ] **Step 0:** re-medir o censo dos 5 arquivos
- [ ] **Step 1:** teste paramétrico red-first
- [ ] **Step 2:** ramos `except HTTPException: raise` (por TRY, não por chamada)
- [ ] **Step 3:** verdes; caso do login do dashboard conferido; mutação amostrada + asserção estática
- [ ] **Step 4:** commit — `fix(views): 404/403 escritos deixam de ser engolidos em ponto, configuracoes, alimentacao, obras.excluir e dashboard`

**Esforço: M.** **Migração: não.**

---

### Task B6.6: 404 — lote c: `frota_views.py` (10 rotas onde o 404 NÃO está escrito)

**Files:** Modify `frota_views.py` — os 10 ramos `if not` →`abort(404)`
(`:214,:314,:395,:432,:563,:695,:797,:864,:950,:985` — 🔬 reproduzidos pela refutação) +
ramo `except HTTPException: raise` nos excepts largos do arquivo;
Create `tests/test_b6_404_frota.py`

**O fato.** 📖 10 rotas vivas da família A: query tenant-scoped, `if not` → flash única +
redirect; mensagem **idêntica** para alheio e inexistente (sem oráculo — o corpo
idêntico já está garantido de fábrica). UI ativa (`base.html:859-939` aponta
`frota.*`) — é o lote onde a D-B6.4 (UX: error.html em vez de flash) mais aparece para
usuário real.

**Comportamento novo.** Trocar o ramo `if not` por `abort(404)` **e** pôr o ramo
HTTPException nos excepts largos do arquivo (senão o abort novo é engolido — risco 1 da
B5.3, aqui em dose dupla porque o 404 não existia).

**Teste que prova:** o molde comum, 10 rotas × (alheio, inexistente); efeito nulo no
`deletar_veiculo`.

**Riscos → mitigação.** (1) o ramo HTTPException vem no MESMO Step que os aborts (não
antes nem depois — o arquivo não tinha 404 nenhum); (2) `main.excluir_veiculo`
(`views/vehicles.py:162`) redireciona 307 para `frota.deletar_veiculo` — o caso alheio
do delete cobre o caminho do botão vivo por tabela (path literal,
`veiculos_lista.html:761`).

- [ ] **Step 0:** re-medir o censo do arquivo
- [ ] **Step 1:** teste paramétrico red-first (os 10 devolvem 302 hoje)
- [ ] **Step 2:** aborts + ramos HTTPException no mesmo commit lógico
- [ ] **Step 3:** verdes; mutação amostrada + asserção estática
- [ ] **Step 4:** commit — `fix(frota): recurso alheio ou inexistente responde 404, nao flash+redirect`

**Esforço: M.** **Migração: não.**

---

### Task B6.7: 404 — lote d: `views/obras.py` (11+ handlers, 13+ sítios — com o censo de helpers na frente)

**Files:** Modify `views/obras.py` — os 10 POSTs da família A do censo AST **mais**
`criar_signatario_cliente` (`:3996`) e os ramos-obra dos dois handlers de signatário
(`:4045-4055`, `:4080-4090`); Create `tests/test_b6_404_obras.py` (+ o script de censo
no scratchpad, não versionado)

**O fato, com a correção do adversário na frente.** O scanner AST devolve 10 handlers —
e é **PISO**: `criar_signatario_cliente` resolve a obra por `_obra_do_tenant` (`:4002`)
e escapa (cegueira compartilhada, provada por reprodução); os handlers de signatário têm
**dois** ramos 302 cada (obra via helper + signatário via query) e só um foi contado.
📖 O sub-lookup dos signatários é sem tenant MAS o pai vem de `_obra_do_tenant` — sem
vazamento cross-tenant; as mensagens distintas só distinguem dentro do próprio tenant.

**Comportamento novo.** **Step 0 obrigatório: censo de lookups via helper** (padrão
`_obra_do_tenant` e análogos) nos 12 arquivos da família — fecha o teto que o AST não
fecha; o resultado corrige a lista de sítios DESTE lote e alimenta o B6.8. Depois, a
mecânica do lote c (abort no ramo `if not` + ramos HTTPException), cobrindo **todos** os
ramos de cada handler (o paramétrico rota×(obra alheia, obra inexistente, filho alheio,
filho inexistente) pega o ramo esquecido — é o cão de guarda contra o piso).

**Teste que prova:** o molde comum, com o eixo duplo dos signatários (obra × filho).

**Riscos → mitigação.** (1) corrigir só o ramo do filho deixa obra-alheia em 302 no
MESMO handler — o paramétrico de eixo duplo é obrigatório; (2) `excluir_obra` já saiu no
lote b — não retocar (serialização §5); (3) o censo de helpers roda ANTES de escrever o
teste, não depois.

- [ ] **Step 0:** censo de lookups via helper nos 12 arquivos (o número final de sítios deste lote sai daqui)
- [ ] **Step 1:** teste paramétrico red-first com eixo duplo nos signatários
- [ ] **Step 2:** aborts + ramos HTTPException em todos os sítios do censo
- [ ] **Step 3:** verdes; mutação amostrada + asserção estática (número do Step 0)
- [ ] **Step 4:** commit — `fix(obras): recurso alheio ou inexistente responde 404 nos POSTs da familia`

**Esforço: M** (era metade de um "M" que o adversário mediu como G — daí o corte).
**Migração: não.**

---

### Task B6.8: 404 — lote e: a cauda heterogênea + o único oráculo de enumeração

**Files:** Modify `equipe_views.py` (`:108`), `views/api.py` (`:550`),
`crud_rdo_completo.py` (`finalizar_rdo`, `:585`), `rdo_editar_sistema.py` (`:42`,
`:189`), `views/admin.py` (`:441-446`), e a decisão de `crud_servico_obra_real.py`
(`:30`, `:65`); Create `tests/test_b6_404_cauda.py`

**O fato.** 📖 A cauda da família A fora dos arquivos-núcleo. Três pontos com regra
própria:
1. **`views/admin.py:441-446` é o ÚNICO oráculo de enumeração vivo da família**:
   `db.session.get` **sem tenant** + mensagens distintas ("Entrega não encontrada" ×
   "sem permissão") — admin de A enumera IDs de entregas de B. Correção: mensagem única
   + 404, citando a regra da casa (`views/almoxarifado/movimentos.py:276-280`).
2. **`rdo_editar_sistema.py`** escopa por `RDO.admin_id` DIRETO (risco 4 da B5.3,
   herdado): o lote põe `abort(404)` no ramo `if not` e **NÃO troca a chave**.
3. **`crud_rdo_completo.finalizar_rdo`** e `rdo_editar.editar_rdo_form` **vencem o
   despacho** (congelado por `tests/test_b5_rdo_crud_url_map.py:55-56,71`) — estão
   vivas, na família; `crud_rdo.excluir` está sombreada (fora — o vencedor já é 404).
4. **`crud_servico_obra_real.py`**: 2 rotas despacháveis com 🔬 zero consumidor —
   decisão barata na hora: corrigir (10 linhas) ou reclassificar como morta e mandar
   para o item M. Registrar a escolha por escrito no commit.

**Teste que prova:** o molde comum; para o admin, o caso extra do oráculo: **corpo e
mensagem idênticos** entre entrega inexistente e entrega de outro tenant.

**Riscos → mitigação.** (1) trocar a chave do `rdo_editar_sistema` muda o conjunto de
RDOs alcançáveis — proibido por escrito; (2) o teste congelado da B5.4 não pode
vermelhar — as correções não mexem em decorador nenhum; (3) o caso do admin é
admin-only — o fixture usa dois admins.

- [ ] **Step 0:** consumir o censo de helpers do B6.7 (sítios extras desta cauda, se houver)
- [ ] **Step 1:** teste paramétrico red-first (+ caso do oráculo do admin)
- [ ] **Step 2:** aborts + ramos HTTPException; mensagem única no admin; decisão escrita de `crud_servico_obra_real`
- [ ] **Step 3:** verdes; `test_b5_rdo_crud_url_map.py` intocado e verde; mutação amostrada
- [ ] **Step 4:** commit — `fix(views): 404 na cauda da familia e fim do oraculo de enumeracao do admin`

**Esforço: M.** **Migração: não.**

> **Nota — o que o adversário corrigiu no levantamento da família 404 (vale para
> B6.4–B6.8).** (a) O step do "alias sombreado" de propostas saiu — a colisão não existe
> (despacho por método). (b) O satélite de vehicles como escrito quebraria o delete vivo
> da frota e o teste congelado da B5.4 — encolheu para a B6.3 + item M. (c) O censo é
> piso (helpers) — Step 0 do B6.7. (d) A unidade de contagem (chamada×handler×try) —
> asserção estática por TRY, re-medida. (e) O lote d era G disfarçado — partido em
> B6.7/B6.8. (f) Janela de estado das rotas de vehicles não corrigidas nem removidas —
> declarada no molde comum, item (v).

---

## 4. Itens ABERTOS que esta rodada descobriu

Fatos novos que apareceram varrendo e não cabem nas oito Tasks. Nenhum vira Task nesta
rodada.

| # | O fato | Âncora | Por que não entrou |
|---|---|---|---|
| 1 | **Anomalia de dado legada no receber:** 102 CRs PENDENTE com `valor_recebido>0` (todas origem NULL, R$ 422.127) que nenhum escritor atual produz + **24 QUITADA de origem NULL** (escritor extinto) — liquidadas e inestornáveis **sem decisão** | ⚠️ dev 06/08 | Inventário próprio; `git log -L` sobre escritores antigos de `valor_recebido` resolve **sem produção** |
| 2 | **Possível QUARTA família de gêmeos:** `event_manager.py:~1725-1748` cria CP `origem_tipo='ALIMENTACAO'` e `alimentacao_views.py:529-540` cria GCP/GCF `'alimentacao_lancamento'` — para o mesmo lançamento? ⚠️ dev: 0 CPs / 112 GCFs (só um lado rodou) | `event_manager.py`, `alimentacao_views.py` | Varredura própria antes de qualquer regra; e `event_manager.py` é ponto de serialização nº1 do plano consolidado |
| 3 | **O destino do layer `/veiculos` (item M):** 21 rotas `main.*` restantes, censo CORRIGIDO (relatorios_veiculos tem teste browser; excluir_veiculo vivo por path literal); duplicidade de delete (frota tem `/frota/<id>/deletar` próprio `:970` mas a lista viva usa `main.excluir_veiculo` por JS literal); templates exclusivos; os shims. Condições escritas para qualquer morte: trocar `veiculos_lista.html:761` para `url_for` ANTES; editar o teste browser; **não** tocar nas sombreadas do teste da B5.4 sem reverter a decisão por escrito | §1.2 desta rodada | Exige análise de cadeias internas + decisão — não cabe no P da B6.3 |
| 4 | **Eixo OBRA fora de RDO:** `pode_ver_obra` em leitura (ponto/obra_dashboard, relatorio, configuracao, POSTs de obras) no padrão de `cronograma_views.py:2695` | herdado da B5.3 | É OUTRA guarda (autorização), não a forma da resposta — misturar inflaria os lotes. Não gateia B6.4-B6.8 |
| 5 | **`receber_conta.html`** — página órfã que baixa SEM criar FC | `contas_receber.html:278-280` (comentário) | Candidata ao tratamento que a D-B5.1 deu ao lado pagar (remover ou equipar) |
| 6 | **Overpay no receber:** `baixar_recebimento` não valida `valor_recebido <= saldo` | `financeiro_service.py:342-452` | A guarda B3.7 fecha a porta principal; o estorno tudo-ou-nada tolera. Registro |
| 7 | **Interação estorno × `contabilidade.estornar_lancamento`** — reversão manual + delete-por-origem = contabilidade revertida duas vezes | `contabilidade_views.py:438` | Baixa probabilidade (20 LCs); registrado no risco 4 da B6.1 |
| 8 | **Literal minúsculo `'gestao_custo_pai'`** vazaria em DOIS dropdowns; normalizar muda dado gravado | `financeiro_views.py:251-255`, `:1433-1437` | Cosmético; decisão de dado, não desta rodada |
| 9 | **Dashboard × tela divergem na fonte do "a pagar":** `obter_kpis_financeiros` soma TODOS os GCPs abertos sem exclusão de gêmeos (nem da família 1); `saidas_v2_pagas` (`:645`) agrega sem o dedup do detalhe | `financeiro_service.py:904-980`, `:645` | Pré-existente; a família 1 já vive nessa incoerência — item de inventário do financeiro |
| 10 | **Link quebrado** `/dashboards/veiculos/executivo` (rota inexistente em qualquer blueprint) | `templates/dashboards/especificos.html:81` | Débito do módulo **dashboards** (endereço corrigido pelo adversário) |
| 11 | **`CustoVeiculoService.criar_custo_veiculo` órfão** após a B6.3 — símbolo presente que mente | `veiculos_services.py:388` | Registrado na B6.3; remoção é do item M ou de limpeza de services |
| 12 | **Clone do migrar criado ANTES do fecho** num tenant que depois faz rollback do batch fica órfão | `importacao_views.py:980-1020` | Limpeza é decisão de dado (mesma forma das 168 órfãs da B5.7) |
| 13 | **`mapear DESPESA_GERAL`** (herdado da B5.6 — decisão de contador) e **`escopo_obra_ativo` em produção** (herdada da B5.3; segue indecidível sem produção, segue fora de qualquer gate) | B5 §Histórico | Herdados; listados para não sumirem |

---

## 5. Riscos e pontos de serialização

**Migrações:** a **281 fica GASTA POR ALOCAÇÃO neste documento** —
`conta_receber.banco_id`, Task B6.1 (o corpo só entra em `migrations.py` no Step 1 da
execução, mas o número está reservado por escrito AQUI, a regra que a corrida de três da
280 ensinou). **282-283 seguem livres; 271-276 reservadas da Fase 6; 270 queimado.**
Nenhuma outra Task da B6 toca `migrations.py`.

**Contra a §11.3 do plano consolidado:**

| Ponto de serialização do plano | Esta rodada |
|---|---|
| nº1 — `event_manager.py` | **Nenhuma Task da B6 abre o arquivo** (a quarta família — item 2 da §4 — fica FORA justamente por isso) |
| nº2 — `migrations.py` | **Só a B6.1** o abre para escrita (281 alocada acima). Ninguém mais |
| nº3 — `views/obras.py:727-770` | O ponto deixou de existir (item nº10 da B5 §4). B6.5/B6.7 tocam outras regiões |

**Colisões internas da B6:**

| Par | Colide? | Por quê / regra |
|---|---|---|
| **B6.1 × B6.2** | **SIM** | `financeiro_views.py` (rota nova + flash × exclusões/KPIs) e `financeiro_service.py` (baixar_recebimento × calcular_fluxo_caixa). Regiões distintas, arquivo único → **serializar: B6.1 → B6.2** (mesma trilha) |
| **B6.5 × B6.7** | **SIM** | as duas tocam `views/obras.py` (`excluir_obra` × POSTs da família A) → serializar b antes de d; B6.7 **não retoca** `excluir_obra` |
| B6.3 × lotes 404 | Não | os lotes excluem `views/vehicles.py` por critério escrito; a B6.3 não toca arquivo de lote nenhum |
| B6.3 × teste da B5.4 | **Evitado por construção** | a B6.3 não mexe em `rdo_crud`; qualquer coisa além (item M) exige reverter a decisão da B5.4 por escrito |
| B6.8 × B5.3/B5.4 | Evitado | `views/rdo.py` fica **intocado**; `rdo_editar_sistema` só ganha abort no ramo (chave proibida de trocar); nenhum decorador muda |
| B6.4/B6.6 × resto | Não | arquivos exclusivos (`propostas_consolidated.py`, `frota_views.py`) |

**Riscos transversais:**
1. 🔴 **Banco único de dev**: nenhuma Task valida rodando a suíte em paralelo com outro
   agente; os red-first rodam na execução de cada Task, um de cada vez. Toda medida
   ⚠️ dev desta rodada é de **2026-08-06** e envelhece.
2. **Janela de estado dos 404**: entre o início da rodada e o fim do B6.8 (e até o item
   M, para vehicles), as rotas não corrigidas seguem alcançáveis por URL com
   flash+redirect. Declarado; a ordem a→b→c→d→e ataca primeiro a maior massa.
3. **Censos AST são pisos** (cegueira a helpers) — os números deste documento NÃO são
   gates; o scanner re-roda na hora de cada lote e o paramétrico de eixo duplo fecha o
   resto.

---

## 6. Ordem recomendada de entrega

| Ordem | Task | Por que nesta posição |
|---|---|---|
| **1** | **B6.1** | É **dinheiro** e é a única com migração (281). O flash da guarda B3.7 do pagar já manda o operador ao estorno; o lado receber nem estorno tem — e a B5.6 deixou o molde fresco. Default D-B6.1 escrito: não trava |
| **2** | **B6.2** | Dinheiro-forma (prevenção pré-deploy: família 2 vazia em dev, mas o clone do migrar está a um clique e o botão promete segurança). Serializada após a B6.1 pelos arquivos compartilhados |
| **3** | **B6.3** | P, morte provada, e **encolhe o inventário** antes dos lotes (as 2 da família A de vehicles saem do mundo em vez de esperar o item M) |
| **4-8** | **B6.4 → B6.5 → B6.6 → B6.7 → B6.8** | Os lotes 404 por massa/homogeneidade: a (18, um arquivo, mecânico) → b (14, mecânico multi-arquivo) → c (10, abort novo) → d (obras + censo de helpers) → e (cauda + oráculo do admin). b antes de d pela serialização de `views/obras.py` |

**O que pode andar em paralelo:**

| Trilha | Tasks | Por que é independente |
|---|---|---|
| **T-B6-a — financeiro** | B6.1 → B6.2 (serializadas entre si) | `financeiro_*`, `migrations.py`, `gestao_custos_views.py`, templates de financeiro/importação |
| **T-B6-b — vehicles** | B6.3 | `views/vehicles.py` + MODULOS.md + 1 teste |
| **T-B6-c — 404** | B6.4 → B6.5 → B6.6 → B6.7 → B6.8 | arquivos de view próprios; internamente serializada só por `views/obras.py` (b→d) |

**As três trilhas podem andar em paralelo entre si** — nenhum arquivo é disputado entre
trilhas. A ressalva transversal: o banco único proíbe rodar os arreios de duas trilhas
**ao mesmo tempo**.

---

## 7. O que esta rodada NÃO cobre

- **Tudo da §4** (13 itens, com endereço).
- **O eixo OBRA fora de RDO** (item 4 da §4) — a pergunta que o recorte da B6-1 deixou
  escrita: quais rotas de leitura sensível seguem o padrão de
  `cronograma_views.py:2695`? Item próprio de rodada futura; não gateia nada da B6.
- **O item M de vehicles** (item 3 da §4) — com as condições escritas.
- **Estorno de CR de medição** — a alternativa fica escrita na D-B6.1; recorte separado
  se a resposta vier "sim".
- **Acoplamento de status das gêmeas** (D-B5.7(1), default (2) mantido) — o buraco
  declarado agora com o nome certo: **pagamento duplo em dinheiro**, possível em duas
  telas de CP + a tela própria de GCP, sem FC do lado CP.
- **Os adiados da §8.2 do plano consolidado e os quatro itens de produção da B5 §7**
  (D11/E02, B2.13, B1.8-q7, E04) — seguem onde estão. **Pela regra de contorno, esta
  rodada não adiciona NENHUMA consulta de produção** — as consultas que a B5 listou
  continuam listadas lá, para o dia em que a decisão de 06/08 mudar.

---

## 8. Contradições registradas

Numeração continua a da B5 (1-9).

**10 — O satélite de vehicles: "morto por desuso" × caminho vivo por path literal.**
O levantamento B6-1 propôs limpar 15 rotas "sem consumidor"; o adversário provou que o
arquivo carrega o caminho vivo de exclusão da frota (path literal invisível às lentes
1/3-por-url_for) e que o teste congelado da B5.4 exige as sombreadas registradas.
**Resolvida a favor do adversário:** o satélite encolheu para o P provado (B6.3); o
resto é item M com condições escritas (§4 item 3). Registrada porque é a **terceira**
vez que "morto afirmado" cai pela lente 3 neste repo.

**11 — A unidade de contagem da família B (43 × 45 × TRYs).**
Levantamento contou por handler e manchetou "43 em 8 arquivos" (são 7); o adversário
contou por chamada (45) e por try. **Resolvida por regra, não por número:** a asserção
estática dos lotes conta **TRYs corrigidos por arquivo, re-medidos na hora** — número
herdado de documento não é gate.

**12 — O cinto do receber: espelho literal × escopo por origem.**
Levantamento prescreveu o espelho de `financeiro_service.py:96-107`; o adversário provou
que ele trava a CR acumuladora de medição sem saída (e que o dano seria na BAIXA, fluxo
vivo, não no estorno). **Resolvida a favor do adversário:** cinto e gravação de
`banco_id` escopados fora de `OBRA_MEDICAO`, e a D-B6.1 cobre **os dois**. Registrada
porque é o caso da rodada em que executar o levantamento como escrito quebraria
produção.

**13 — O tamanho do lote d.**
Levantamento: cauda heterogênea num M. Adversário: G disfarçado (~19-22 sítios, 7
arquivos, censo de helpers pendente). **Resolvida a favor do adversário:** partido em
B6.7 (obras, com o censo como Step 0) e B6.8 (cauda).

**14 — O nome do risco da família 2.**
Levantamento: "prevista eterna" (exibição). Adversário: **pagamento duplo em dinheiro**,
em duas telas de CP + a tela de GCP, silencioso e sem FC do lado CP. **Adotada a
formulação do adversário** no texto da D-B6.2, da Task B6.2 e do §7 — o default (não
acoplar status) não muda, mas o que ele deixa aberto tem de estar nomeado por extenso.

---

## 9. Perguntas para o Cássio

Só as que **mudam o recorte**; todas com default decidível com **dev + código** (regra
de contorno — nenhuma depende de produção).

**D-B6.1 — O estorno de recebimento cobre a CR acumulada de medição
(`origem_tipo='OBRA_MEDICAO'`)? E o cinto multi-banco da baixa se aplica a ela?**
Trava: os Steps 4-5 da B6.1.
**Default se não vier: NÃO aos dois** — a guarda do estorno recusa **por origem** (não
por status QUITADA: ⚠️ dev há 29 OBR-MED paradas em RECEBIDO que o próximo recalc
promoveria — recusar por status trataria a mesma conta de dois jeitos conforme o
timing), e o cinto + gravação de `banco_id` **não se aplicam** a OBR-MED (a CR
acumuladora recebe múltiplas baixas legítimas; coluna única de banco é mal-definida
nela, e o cinto a travaria sem saída — contradição 12).
Razões decidíveis com dev+código: QUITADA só nasce em `medicao_service.py:443/:473`
(semântica de medição); `valor_original` é móvel (= `valor_medido`); o portal do cliente
exibe a CR (`portal_obras_views.py:276`) — reverter dinheiro de medição é decisão de
medição. A alternativa (estorno OBR-MED chamando `recalcular_medicao_obra` após zerar +
decisão de exibição no portal) fica escrita como recorte futuro. **Anexo da decisão:**
as 24 QUITADA legadas de origem NULL ficam inestornáveis pela guarda por status — se
isso incomodar, é inventário (item 1 da §4), não mudança desta guarda.

**D-B6.2 — O lançamento importado como `apenas_pagamento` (FC SAIDA com referência
NULL) continua EDITÁVEL e indistinguível de lançamento manual na tela do fluxo?**
Trava: nada — a B6.2 executa o default; a resposta contrária vira Task própria.
**Default se não vier: SIM, fica como está** — o FC é a única substância desse
lançamento (não há GCP/CP por trás para divergir) e o modo é o anti-duplicação
funcionando como desenhado. O que muda por default é só (i) o texto de
`resultado_fluxo.html:83` (promete ContaPagar que o modo não cria) e (ii) opcionalmente
o rótulo "Importação (extrato)" quando `import_batch_id` não é nulo. Se a resposta for
NÃO (imutável/só-rollback): guard em `editar_fluxo_caixa` por `import_batch_id` — fora
deste recorte. **Nomeado por extenso** (contradição 14): o default da família 2 mantém
possível o pagamento duplo em dinheiro da mesma obrigação (CP em duas telas + GCP na
tela própria), sem acoplamento de status — herdado da D-B5.7(1), não desta decisão.

**D-B6.3 — `main.novo_veiculo_OLD` sai no mesmo lote da B6.3?**
Trava: um range de delete do Step 2.
**Default se não vier: SIM** — zero referências nas cinco lentes (🔬 06/08, árvore
`26dff528`, reproduzido pela refutação), o próprio código a declara "ROTA ANTIGA
DESATIVADA" (`:1626`), a URL não é linkável de lugar nenhum e o template que ela
renderiza é compartilhado com a frota viva (fica). Nenhum dado de produção muda a
resposta.

**D-B6.4 — A família 404 inteira adota o destino da D-B5.3: 404 HTML via
`templates/error.html`, sem flash e sem redirect, com corpo idêntico para alheio e
inexistente — e as rotas fetch de propostas devolvem JSON 404 explícito?**
Trava: os lotes B6.4-B6.8 (têm default; não travam de fato).
**Default se não vier: SIM** — o precedente D-B5.3 já foi aceito para RDO; a regra da
casa (`views/almoxarifado/movimentos.py:276-280`) já está escrita; 🔬 nenhum JS trata
`status === 404` (os `.json()` caem no catch genérico existente) e 🔬 nenhum teste
congela o 302 dos casos ausentes. Duas convenções na mesma família custam mais que uma
tela feia — o argumento da D-B5.3, inalterado.

---

## Histórico

- **2026-08-06, noite** — Rodada B6 aberta sobre a árvore `26dff528` (B5 fechada
  inteira). Quatro itens varridos com cinco lentes e refutação adversarial; **os quatro
  sobreviveram como `confirmado_com_correcoes`**. Nasceram **oito Tasks**: B6.1 (estorno
  de recebimento, **migração 281 alocada por escrito**, com o cinto escopado que o
  adversário salvou de quebrar a baixa de medição), B6.2 (família 2 + guard do migrar +
  chore do `apenas_pagamento`), B6.3 (as três rotas mortas de vehicles, morte PROVADA),
  e B6.4-B6.8 (a família 404 em **cinco lotes** por arquivo/homogeneidade — 62 rotas
  vivas; 18 candidatas caíram fora com prova). Derrubados: a colisão inexistente do
  alias de propostas, o satélite de vehicles como escrito (path literal vivo + teste
  congelado da B5.4), o espelho literal do cinto, o censo-teto da família A (helpers), a
  previsão de origem dupla de LC no receber (não se materializou — o estorno do receber
  é mais simples nesse eixo). Regra de contorno cumprida: **zero dependência de
  produção** em qualquer Step ou default. Contradições 10-14 registradas. Quatro
  decisões na fila (D-B6.1 a D-B6.4), todas com default executável.
