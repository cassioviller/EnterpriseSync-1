# Rodada B5 — varredura das cinco dívidas sem Task — 2026-08-06

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development`
> ou `superpowers:executing-plans`. Os passos usam checkbox (`- [ ]`).

**O que é:** a rodada que sucede o
`docs/superpowers/plans/2026-08-04-plano-consolidado.md`, que fechou **60 de 61 Tasks**
(a B1.14 foi cortada em 05/08, §8.1 daquele documento). Cinco dívidas ficaram sem Task —
quatro na §8.3 do plano consolidado e uma na seção "Em aberto" do
`FECHO-SESSAO-2026-08-05.md`. Cada uma foi varrida com **cinco lentes** e depois submetida
a um adversário cuja tarefa era derrubar cada achado. Este documento é o produto dos dez
trabalhos.

**Contra o quê:** branch `test/b0-arreio`, HEAD `4b53a6a1`, árvore limpa. Os 63 commits da
execução do plano consolidado são **locais — nada foi enviado ao remoto** (🔬 medido na
refutação da dívida `pagar-fluxocaixa`). Isso importa em duas Tasks: o defeito da B5.1
**ainda não está em produção**, e a decisão sobre ele é sobre o que sai no próximo deploy,
não sobre incidente ativo.

**As cinco lentes, que são o método e não enfeite.** A razão de existirem está no achado
de método de 05/08 (`FECHO-SESSAO-2026-08-05.md`, seção "Achado de método"): a B4.8 removeu
`NotificacaoCliente` a partir de grep pelo **símbolo** Python, e três referências citavam a
tabela por **string literal** — uma delas percorrida a cada exclusão de obra. Consequência
🔬 medida: a exclusão do RDO passou a falhar em silêncio, com a rota respondendo 200.

| # | Lente | O que procura |
|---|---|---|
| 1 | **SÍMBOLO** | nome Python da função/classe/atributo |
| 2 | **STRING** | o nome como literal: `'nome_tabela'`, listas de tabelas, chaves de payload |
| 3 | **TEMPLATE** | `templates/**/*.html`: `{{ }}`, `{% %}`, `url_for`, `name=` de formulário, `fetch()` |
| 4 | **ROTA** | `@blueprint.route`, `url_for`, e **qual regra vence no `url_map` quando há colisão** |
| 5 | **SQL/DADO** | SQL cru, `migrations.py`, seeds, `scripts/`, e o dado no banco |

**Marcas de procedência** (a regra da casa, conforme `ESTADO-ATUAL.md`):
🔬 medido · 📖 lido no código com `arquivo:linha` · 🧮 deduzido · ⚠️ dev (banco de
desenvolvimento: prova a forma, não o volume).
Onde a marca não é minha, o texto diz de quem é ("🔬 medido na refutação"). As âncoras
marcadas 📖 sem atribuição foram **reabertas na redação deste documento** e conferidas
linha a linha.

---

## 1. O que a varredura DERRUBOU

**Nenhuma das cinco dívidas foi derrubada inteira. As cinco sobreviveram como
`confirmado_com_correcoes` — e em quatro delas o RECORTE que o plano/fecho prescrevia foi
derrubado.** Abrir com "5 de 5 confirmadas" sem dizer o que se tentou não valeria nada;
segue o que se tentou e o que caiu.

### 1.1 O que os adversários tentaram, e falhou

| Ataque | Contra o quê | Resultado |
|---|---|---|
| Reconstruir o `NameError` por **symtable** e por **bytecode** (`dis`), conferir ausência de `globals()` e de star-import, e reler o commit `01883756` | `financeiro_service.py:133` | 🔬 Falhou em cinco caminhos independentes. `LOAD_GLOBAL valor_recebido` na linha 133; `co_varnames` traz `valor_pago`, não `valor_recebido` |
| Procurar um preenchedor de `ContaPagar.conta_contabil_codigo` que o levantamento tivesse perdido | premissa "o gate de `:127` é sempre True" | 🔬 Falhou. Os escritores do campo são de `ContaReceber` e `GestaoCustoPai`; `FinanceiroService.criar_conta_pagar` aceita o parâmetro (`financeiro_service.py:28`) e **não tem chamador** |
| Percorrer `calcular_progresso_rdo` inteira (`utils/cronograma_engine.py:734-836`) atrás de qualquer fallback para o snapshot | tese "a Curva S nunca leu `ap.percentual_planejado`" | 🔬 Falhou. Zero acesso ao snapshot no caminho do planejado. 📖 Conferido aqui: `utils/cronograma_engine.py:765-767` passa `tarefa.data_inicio/data_fim/duracao_dias` **vivos** |
| Derrubar o insumo da correção da curva por `data_inicio` NULL e por classificação de marco | `CronogramaBaselineItem` | 🔬 Falhou nas duas. ⚠️ dev: 0 itens sem `data_inicio` em 769.929; 0 divergências de "duração zero" entre tarefa viva e item congelado |
| Provar homonímia na âncora `views/rdo.py:1111-1113` (há **quatro** `if not rdo:` no arquivo) extraindo `git show b32b3629:views/rdo.py` | âncora da dívida `rdo-302-tenant` | 🔬 Falhou. É a mesma `visualizar_rdo`, deslocada 26 linhas. 📖 Conferido aqui: `views/rdo.py:1065` `def visualizar_rdo`, `:1086` `if not rdo:` |
| Ressuscitar as duas rotas de API do `rdo_crud` por **URL relativa** (`fetch('api/funcionarios')` sob `/rdo/...`) | corte proposto nº1 | 🔬 Falhou. Os três hits são absolutos e de outro blueprint |
| Reconstruir o `url_map` **sem importar `main`** (Map estático do werkzeug 3.1.3, na ordem real de registro), para não escrever no banco de dev | placar 4 sombreadas / 9 vencedoras | 🔬 Falhou em derrubar: placar idêntico |
| Consultar `pg_constraint` em vez de acreditar no `CREATE TABLE` da migração | absolvição do quase-E02 em `obra_orcamento_operacional` | 🔬⚠️ dev falhou em derrubar: `confdeltype='c'` (CASCADE) nas três FKs |
| Rodar o teste isolado que o plano **não** registrou | recorte "um teste falha isolado" | 🔬 **Derrubou o recorte: são dois.** `pytest tests/test_e2e_orcamento_operacional_e_metricas_views.py -k test_post_atualizar_do_original_sem_diff_flash_info` → `1 failed, 6 deselected` |

### 1.2 O que CAIU — recortes derrubados dentro de dívidas sobreviventes

No formato da §8.1 do plano consolidado: cada linha abaixo é uma prescrição que **não vai
virar Step**, com a razão.

| Prescrição derrubada | Onde estava escrita | Por que caiu |
|---|---|---|
| **"o recorte deveria ser o espelho da B3.8"** (lado pagar do FluxoCaixa) | `FECHO-SESSAO-2026-08-05.md`, "Em aberto" | 🔬 O espelho **não é literal**: do lado receber o LEITOR já existia antes da B3.8 (`rr_query`, `financeiro_service.py:714-724`, datado em `b30923b5`/2026-07-22 por `git log -L`), e a B3.8 (`95912e7c`) não tocou `financeiro_service.py`. Do lado pagar **não há leitor**: `pr_query` (`:549-559`) só aceita `'gestao_custo_pai'` e `fd_query` (`:688-697`) só aceita `referencia_tabela IS NULL`. Copiar a B3.8 ao pé da letra produz uma linha que nenhuma tela mostra — a Task nasceria inerte pelo outro lado |
| **"não sobrescrever `percentual_planejado`"** como correção da Curva S | risco 6 da Task B2.20, plano `:3405` | 📖 Logicamente incapaz de consertar: a curva **não passa** por essa coluna. Caminho conferido: `views/obras.py:2885` → `calcular_progresso_geral_obra_v2` (`utils/cronograma_engine.py:943`, `:965`) → `calcular_progresso_rdo` (`:765`) → `_planejado_na_data` com datas vivas. E desfaria as Tasks B2.17-B2.20 (`318b294d` + `19be5ea8`) |
| **"A06 degradou a curva"** (a causa que o risco 6 dá) | risco 6 da B2.20 | 🧮 A curva já era plano corrente **desde a Task #141**. A06 alinhou o snapshot ao que a curva já mostrava. A dívida existe; a causa está errada, e com ela a correção |
| **"o teste de convergência da B2.12 congela o 302"** | §8.3 do plano, célula do 302 | 🔬 Falso. `tests/test_a19_progresso_v1_convergencia.py` importa `um_tenant`, tem 5 testes, **zero** ocorrência de 302/404/cross-tenant: a asserção 4 do recorte da B2.12 (plano `:2742`) **nunca foi entregue**. Nada congela o 302 — mas `tests/test_fase5_rdo_ciclo_vida.py:685-694` chama-se `test_visualizar_rdo_de_outro_tenant_devolve_404` e assere `in (302, 404)`: mede os dois lados |
| **"o 302 é vazamento de tenant"** (a justificativa do item) | §8.3 do plano | 🔬 O 302 **não é oráculo**: RDO alheio e RDO inexistente devolvem 302 com o **mesmo** `Location` e a **mesma** flash. E o Status da própria B1.15 (plano `:1806-1809`) diz que "flash+redirect **não é oráculo**, então fica como está". A regra da casa, na forma em que foi aplicada, não condena este 302. **A Task sobrevive por outro motivo** — ver B5.3 |
| **"aposentar o blueprint `rdo_crud`"** | §8.3 do plano, célula do sombreamento | 🔬 9 das 13 rotas são o **único** handler do seu path, incluindo as **cinco de foto**. Aposentar o blueprint derruba o subsistema de foto do RDO e transforma `main.visualizar_rdo` em 500. ⚠️ dev: 6.647 de 50.966 linhas de `rdo_foto` com `armazenamento='disco'` |
| **"consertar é criar o `ObraOrcamentoOperacional` no próprio fixture"** | §8.3 do plano, célula do fixture | 📖 Deixa `test_get_index_clona_lazy_e_renderiza` (`:146`) verde sem exercitar o caminho lazy: `garantir_operacional` devolve o existente no primeiro `if` (`services/orcamento_operacional.py:69-71`) e a asserção `'Itens (1)'` é satisfeita pelo template (`templates/orcamento_operacional/index.html:44`) independentemente de quem criou. **Corrigido pelo adversário:** a perda não é "zero cobertura" — `tests/test_orcamento_operacional.py:301` cobre clonagem **e** idempotência sem fixture nenhum (📖 conferido aqui: `:122`, `:144-149`). O que se perde é a prova do fio **rota → serviço** |
| **"os pontos vivos de `AlocacaoEquipe.rdo_gerado_id` são três"** | plano `:4732` (E04, adiado), `models.py:2181`, `ESTADO-ATUAL.md:939` | 🔬 São **dois**. O terceiro (`crud_rdo_completo.py:557`) vive dentro de `rdo_crud.excluir_rdo`, e `POST /rdo/excluir/<id>` resolve para `main.excluir_rdo`. A rota **nunca recebe requisição**, e o comentário de `models.py:2181` ("Mantido de propósito: é barato e protege bases onde a FK porventura tenha valor") documenta uma proteção que não roda |
| **"a dívida do `rdo_crud` foi enunciada errada no plano"** | levantamento da dívida `rdo-crud-sombreado` | Derrubado **pelo adversário**: o corpo do plano (`:2750-2774`) afirma só que `listar_rodos` está sombreada — o que é verdade — e a linha `:2771` diz "DECIDIR se... as rotas irmãs devem ser aposentadas": **pergunta**, não afirmação. O texto atacável é o título comprimido da célula da §8.3. Registrado para que o exagero não vire precedente |

**Consequência de método desta rodada, que vale para a próxima varredura de "está morto?":**
o padrão E03/E11 (declarado morto, vivo em template/JS) apareceu **de novo**, e desta vez
por `fetch()` com path literal: `templates/rdo/editar_rdo.html:1286,1333,1398,1419`. Um
grep por `rdo_crud` em `templates/` devolve **um** arquivo e teria autorizado matar upload,
galeria, legenda e delete de foto. E apareceu o padrão **inverso**, que é novo e pior: o
símbolo certo presente e mentindo — `views/rdo.py:1587` chama `_rdo_do_tenant_ou_404` de
dentro de um `try` cujo `except Exception` (`:1660`) engole o `NotFound`. Grep pelo símbolo
classifica a rota como conforme.

---

## 2. Os achados que só as lentes 2-5 pegaram

A seção existe para justificar o método. Cada linha é uma referência que um grep pelo
símbolo Python teria perdido.

| Lente | Achado | Âncora | Por que a lente 1 não pegava |
|---|---|---|---|
| **2 STRING** | O oráculo de enumeração **por mensagem**: depois de a query com tenant falhar, uma SEGUNDA query **sem tenant** escolhe entre "Acesso negado: esta obra pertence a outra empresa." e "Obra não encontrada." | `views/rdo.py:719-727` e `:2720-2727` | Os dois ramos devolvem 302. Grep por status code, por `abort(404)` ou por `403` devolve vazio. Achado grepando a string `outra empresa` |
| **2 STRING** | `TABELAS_DEPENDENTES_OBRA` cita `'conta_pagar'`, `'conta_receber'` **e** `'fluxo_caixa'` — a dívida do E02 **não** se repete no financeiro | `views/obras.py:1213-1215` | É lista de strings; nenhum símbolo Python envolvido |
| **2 STRING** | `'rdo_crud'` em **duas** listas `csrf_exempt_blueprints`, e a de `app.py` é **no-op** (o laço de `app.py:1063-1067` roda no `from app import app` de `main.py:1`, antes de o blueprint ser registrado em `main.py:25`) | `app.py:1055`, `main.py:210` | Nome de blueprint como string em lista de config |
| **2 STRING** | `ponto_views.py:849-853` e `:932-940` leem e apagam `FluxoCaixa` com `referencia_tabela='registro_ponto'` — e **nenhum escritor de produção grava esse valor**. ⚠️ dev: 0 linhas | `ponto_views.py:849`, `:932` | É comparação contra literal; o "símbolo" existe e está vivo |
| **3 TEMPLATE** | As quatro rotas de foto do RDO são consumidas por **path literal** em `fetch()` de template-literal | `templates/rdo/editar_rdo.html:1286,1333,1398,1419` | `grep -rln 'rdo_crud' templates/` devolve **um** arquivo, e não é este |
| **3 TEMPLATE** | O modal **vivo** da baixa de conta a pagar não manda `criar_fluxo_caixa` nem `categoria_fluxo_caixa_id` (`grep -c` → 0), enquanto a página **órfã** `pagar_conta.html:93-101` já tem o checkbox `value="1" checked` | `templates/financeiro/contas_pagar.html:402-443` × `pagar_conta.html:93-101` | O símbolo `criar_fluxo_caixa` existe e está certo — no template que ninguém alcança. Espelho exato do que a B3.8 descobriu do lado receber |
| **3 TEMPLATE** | A comparação contra a baseline **já está viva na UI**, só não em curva: barra cinza `gantt-bar-baseline` e coluna "Desvio" | `templates/obras/cronograma.html:2484`, `:203`, `:394`, `:1045` | `grep 'CronogramaBaseline('` devolve vazio nesse arquivo: é Jinja + JS |
| **3 TEMPLATE** | A **terceira família** do "planejado", que nenhum dos dois recortes listou: o planejado **por tarefa** da grade, calculado ao vivo, colorindo a célula Real — na mesma linha da tabela que traz a coluna "Desvio" (baseline) | `cronograma_views.py:512-515` → `_tarefa_to_dict` (`:278`, `:312`) → `templates/obras/cronograma.html:1517`, `:1527` | Nem agregado, nem snapshot: um terceiro caminho |
| **4 ROTA** | `POST /rdo/excluir/<id>` resolve para `main.excluir_rdo`; `rdo_crud.excluir_rdo` está **sombreada** — e é isso que derruba o terceiro ponto vivo do E04 | 🔬 `url_map` + `MapAdapter.match` | Ler o arquivo sugere o contrário: as 13 rotas estão sob `url_prefix='/rdo'` e parecem cobertas pelo `main_bp` |
| **4 ROTA** | `rdo_crud.editar_rdo` (`crud_rdo_completo.py:236-240`) só faz `redirect` para uma rota cujo `url_for` produz **a mesma URL**. Hoje perde o despacho; se a ordem de registro em `main.py` mudar, vira laço 302 | 🔬 `url_for` das duas → `/rdo/editar/1` | — |
| **4 ROTA** | Com `from app import app` puro **nenhuma** rota `rdo_crud`/`rdo_editar` existe: os dois blueprints entram só por `main.py`, que a suíte carrega em `tests/conftest.py:43`. Quem medir `url_map` sem importar `main` mede um app diferente do que o gunicorn serve | `main.py:11`, `:25` | — |
| **5 SQL/DADO** | ⚠️ dev: `SELECT count(*) FILTER (WHERE conta_contabil_codigo IS NOT NULL), count(*) FROM conta_pagar` → **(0, 627)**. O ramo `if not` de `financeiro_service.py:127` é o único que roda | ⚠️ dev | Prova de dado; nenhuma leitura de código sustenta "sempre True no parque" |
| **5 SQL/DADO** | ⚠️ dev: `fluxo_caixa` GROUP BY `(referencia_tabela, tipo_movimento)` → apenas `('gestao_custo_pai','SAIDA',210)` e `('conta_receber','ENTRADA',74)`. **Zero** linhas `'conta_pagar'`: o escritor de `financeiro_views.py:407-418` nunca disparou | ⚠️ dev | — |
| **5 SQL/DADO** | ⚠️ dev: `SELECT origem_tipo, count(*) FROM conta_pagar GROUP BY 1` → `[('COMPRA', 627)]`, todas PENDENTE. A sobreposição GestaoCustoPai × ContaPagar não é parcial: é **100%** | ⚠️ dev | — |
| **5 SQL/DADO** | ⚠️ dev: das 30.196 obras com baseline ativa, **82** têm qualquer divergência entre datas vivas e congeladas, e **uma** delas tem RDO Finalizado. Nessa obra a série de baseline fica **abaixo** da viva nos 20 pontos (Δ máx 1,1 p.p.) | ⚠️ dev | É a medida do valor da B5.5, e ela contradiz o sintoma do risco 6 |
| **5 SQL/DADO** | `obra_orcamento_operacional` **não** está em `TABELAS_DEPENDENTES_OBRA` — mesma forma do E02 — e está **absolvida**: 🔬⚠️ dev `pg_constraint.confdeltype='c'` (CASCADE) nas três FKs. Acusado pela lente 2, absolvido pela lente 5 | `views/obras.py:1198-1239`, `migrations.py:13573`, `models.py:8309` | — |

**Onde as cinco lentes vieram vazias, e isso é resultado:** na dívida `rdo-302-tenant` a
lente 5 não achou **nada** — nenhuma migração, seed, script de boot ou lista de tabelas
cita `/rdo/<id>` ou `exportar_rdo_pdf` (🔬 grep em `migrations.py`,
`utils/database_diagnostics.py`, `fix_all_admin_id_universal.py`). Ao contrário da B4.8,
ali não há terceiro consumidor por string. E a lente 3 na mesma dívida provou que
**nenhum JS quebra com 404**: `grep 'status === 404|status == 404|status === 302'` em
`templates/` e `static/` → vazio; o PDF é disparado por `<a href>`
(`templates/rdo/visualizar_rdo_moderno.html:1130`).

---

## 3. As Tasks

Cinco Tasks, uma por dívida, numeradas na ordem de entrega recomendada (§5). Onde o
adversário corrigiu o levantamento, **o texto da Task usa a versão corrigida** e a correção
fica visível na nota ao final da Task.

---

### Task B5.1: a baixa de conta a pagar volta a funcionar — `NameError` + guarda de re-baixa

**Status: ✅ entregue em `0bc62449`, com dois apertos da revisão WF-1 no commit de
revisão.** Red-first (casos 1-3 vermelhos) e matriz de mutação medida como o Step 4
pede — e reconferida analiticamente pelo revisor. Desvio de forma declarado: login por
`cliente_de()` em vez de POST /login. A revisão achou dois findings baixos, os dois
aplicados: `status` NULL em legado estourava `.lower()` na própria guarda (nos DOIS
lados — o espelho do receber tinha o mesmo latente), e o flash prometia estorno em
ramos (`CANCELADO`, saldo≤0) onde `estornar_conta` recusa — a frase do estorno agora
só entra quando `status == 'PAGO'`.

**Files:** Modify `financeiro_service.py` — `baixar_pagamento`, bloco de log `:127-133`;
Modify `financeiro_views.py` — `pagar_conta`, entre o `first_or_404()` de `:379` e o
`if request.method == 'POST'` de `:381`;
Create `tests/test_b5_baixa_conta_pagar.py`

**O fato, e ele não é o que o fecho registrou.** 📖 Conferido linha a linha nesta redação:
`financeiro_service.py:133` passa `valor_recebido` para o `logger.warning` dentro de
`baixar_pagamento`, onde o parâmetro se chama `valor_pago` (`:73`). O bloco inteiro é cópia
verbatim do lado receber — o texto diz "ContaReceber" dentro de uma função de `ContaPagar`.
Veio da B3.6 (`01883756`), que copiou o bloco para os "dois pontos de baixa".

🔬 Medido na refutação por dois caminhos independentes: `symtable` marca `valor_recebido`
com `is_global=True` no escopo `/top/FinanceiroService/baixar_pagamento`, e `dis` sobre o
code object devolve exatamente um `LOAD_GLOBAL valor_recebido` na linha 133. O módulo não
tem esse global (imports conferidos em `:1-16`), não há star-import e
`grep -n 'globals()' financeiro_service.py` → zero. **`NameError` garantido.**

E não é caso de borda: 📖 o bloco está sob `if not conta.conta_contabil_codigo:`
(`financeiro_service.py:127`), e ⚠️ dev **0 de 627** `ContaPagar` têm o campo preenchido.
🔬 A refutação procurou um preenchedor que o levantamento tivesse perdido e não achou:
todos os escritores de `conta_contabil_codigo` são de `ContaReceber` ou `GestaoCustoPai`, e
`FinanceiroService.criar_conta_pagar` — que aceita o parâmetro — **não tem chamador**.

**A cadeia, e por que ela é pior que um 500.** 📖 `financeiro_service.py:118` já deu
`db.session.commit()` quando o `NameError` estoura em `:133`: `valor_pago`, `saldo`,
`data_pagamento`, `forma_pagamento` e `status` já estão **persistidos**. O `except` de
`:215-218` faz `rollback()` (no-op) e `raise`. 📖 Na rota, `financeiro_views.py:425-427` é
`except Exception` + `logger.error` + `flash('Erro ao registrar pagamento','danger')`
**sem `return`**, e a execução cai no ramo GET de `:429-441`, que renderiza
`pagar_conta.html` com **HTTP 200**. O operador vê "Erro ao registrar pagamento" sobre um
pagamento que já aconteceu.

⚠️ **Correção do adversário, adotada:** o débito bancário **não** é parte do caminho
padrão. 📖 `banco.saldo_atual -= valor_pago` (`financeiro_service.py:114`) só roda dentro
de `if banco_id:` (`:110`) e `if banco:` (`:113`), e o modal vivo oferece
`<option value="">Sem vínculo bancário</option>` como **primeira** opção
(`templates/financeiro/contas_pagar.html:430-434`), que a rota converte para `None`
(`financeiro_views.py:390`). O que é sempre persistido antes do estouro são os cinco campos
da conta.

**A guarda de re-baixa não existe do lado pagar.** 📖 `pagar_conta` vai do `first_or_404()`
de `financeiro_views.py:379` direto ao `if request.method == 'POST'` de `:381` — nada entre
eles. Do lado receber, a guarda da B3.7 (`0fc44bc6`) ocupa `financeiro_views.py:650-677`
(conferido nesta redação: comentário A02/B3.7, `_saldo`, `_liquidada`,
`if _liquidada and request.method == 'POST'` → `flash` + `redirect`). 📖
`financeiro_service.py:97` faz `conta.valor_pago += valor_pago`, exatamente a soma que
motivou a B3.7. E o vetor existe: 📖 `services/importacao_excel.py:2414-2430` cria
`ContaPagar` já com `status='PAGO'`, `valor_pago` cheio e `saldo=0` — espelho literal do
argumento da B3.7 (que citava `importacao_excel.py:2478` do lado receber).

**Comportamento novo.**
1. `financeiro_service.py:129-133` passa a citar `valor_pago` e a dizer `ContaPagar` no
   texto. É uma linha de log e uma palavra.
2. `pagar_conta` ganha a guarda de re-baixa **espelhando `financeiro_views.py:650-677`**:
   `_saldo = conta.saldo if conta.saldo is not None else (conta.valor_original or 0)`;
   `_liquidada = conta.status in ('PAGO','CANCELADO') or _saldo <= 0`; com POST em conta
   liquidada, `logger.warning` + `flash` + `redirect(url_for('financeiro.listar_contas_pagar'))`.
   **Os status são outros** — do lado receber são `RECEBIDO`/`QUITADA`/`CANCELADO`
   (`financeiro_views.py:668-669`); do lado pagar quem grava é
   `financeiro_service.py:104` (`'PAGO'`) e o import (`services/importacao_excel.py:2422`).
   🔬 Confirmado na refutação que não há terceiro escritor de `status='PAGO'` em
   `ContaPagar` fora de `archive/`, `tests/` e `scripts/`.

**As duas saem no MESMO commit.** Consertar só o `NameError` converte um erro barulhento
num pagamento silencioso que continua sem guarda: o operador que hoje vê a mensagem de erro
e repete passaria a pagar duas vezes **sem sinal nenhum**. É o padrão que motivou o corte
da B1.14 (§8.1 do plano consolidado): metade mecânica da correção trocando um sintoma
barulhento por um silencioso.

**Teste que prova.** Tenant próprio (admin ADMIN v2 + Obra + `BancoEmpresa`), uma
`ContaPagar` PENDENTE de R$ 1.000 **sem** `conta_contabil_codigo` (o caso de 627/627 em
⚠️ dev). Login por `POST /login` (padrão de `tests/test_compras_nova_dropdown.py:133-139`)
e `POST /financeiro/contas-pagar/<id>/pagar`.

| # | Ação | Asserção |
|---|---|---|
| 1 | POST de 1.000 **sem** `banco_id` (o caminho padrão do modal) | 302 para a listagem; flash de **sucesso**; `conta.status == 'PAGO'`, `valor_pago == 1000`. **Antes da correção: 200 com "Erro ao registrar pagamento" e a conta já PAGO** |
| 2 | — | `NameError` **não** aparece em `caplog` |
| 3 | 2º POST de 1.000 sobre a mesma conta | contagem inalterada; `valor_pago` continua 1.000; flash de recusa (guarda) |
| 4 | POST de 400 em conta nova (parcial) e depois de 600 | `PARCIAL` → `PAGO`, soma 1.000 — a guarda **não** pode barrar baixa parcial |
| 5 | POST com `banco_id` de um `BancoEmpresa` do tenant | `banco.saldo_atual` debitado uma única vez |

**Por que o gate de 1937 não pegou.** 🔬 `grep -rn 'baixar_pagamento'` fora de `archive/`
devolve **a definição** (`financeiro_service.py:73`) e **uma chamada**
(`financeiro_views.py:393`). `grep -rn 'contas-pagar' tests/` devolve só
`tests/test_browser_all_modules.py:541/544/1793`, todos **GET na listagem**. Nenhum teste
da suíte faz POST na rota de pagamento. O gate ficou verde com o `NameError` dentro.

**Riscos → mitigação.**
1. **Não usar `abort()` dentro do `try` do POST.** O `except Exception` de
   `financeiro_views.py:425` engole `HTTPException` e devolve 200 — mesmo risco 3 da B3.8.
   A guarda tem de ficar **antes** do `if request.method == 'POST'` de `:381`, como está do
   lado receber.
2. **A guarda não pode usar `_saldo <= 0` sozinha.** 📖 `conta.saldo` é recalculado em
   `financeiro_service.py:98` e pode ser NULL em registro legado; o fallback para
   `valor_original` é o mesmo do lado receber. Sem ele, conta legada com `saldo` NULL
   ficaria bloqueada para sempre.
3. **Baixa parcial legítima.** O status `PARCIAL` **não** entra na lista de liquidados —
   caso 4 do teste é o cão de guarda.
4. **`estornar_conta` continua não restaurando `banco.saldo_atual`** (ver §4, item novo
   nº1). Esta Task **não** conserta isso, e não pode dar a impressão de que conserta: com a
   guarda, o operador que quiser refazer uma baixa vai ao estorno, e o estorno tem defeito
   próprio. → o `flash` da guarda diz "esta conta já está paga; para refazer, estorne" e
   **nada mais**; a Task do estorno é separada.

**O que esta Task NÃO faz, e por quê.**
O `FluxoCaixa` SAIDA — que é a dívida como o fecho a enunciou — **fica fora**, bloqueado
pela decisão **D-B5.1** (§8). Razão técnica, não de escopo: 🔬 `ContaPagar` **não aparece
uma única vez** dentro de `calcular_fluxo_caixa` (varredura das linhas 456-760: zero
ocorrências); as saídas previstas vêm de `GestaoCustoPai` (`financeiro_service.py:504-585`)
e as realizadas de `pr_query` (`:549-559`, só `'gestao_custo_pai'`). Conta a pagar está
fora do fluxo de caixa **nas duas pontas**. E 📖 `compras_views.py:207-216` e `:256-275`
criam, para o **mesmo** `PedidoCompra`, um `GestaoCustoPai` **e** uma `ContaPagar` —
⚠️ dev, 627 de 627. Ligar a baixa ao fluxo sem regra de exclusão põe a mesma despesa
simultaneamente como **prevista** (o GCP gêmeo, que ninguém vai pagar) e **realizada**.

⚠️ **Correção do adversário, adotada:** não é o `saldo_final_projetado` que dobra —
📖 `financeiro_service.py:588` calcula `saldo_inicial + entradas_previstas -
saidas_previstas`, só previstas. O que dobra é a lista `detalhes` e os buckets de
`agregar_fluxo_mensal` (`:768-780`), e a despesa prevista **nunca sai**. O sintoma a
procurar é esse, não um KPI errado.

- [x] **Step 1:** escrever o teste e vê-lo **vermelho** no caso 1 (200 + "Erro ao registrar pagamento" com a conta já PAGO) e no caso 3 (soma dobrada)
- [x] **Step 2:** `financeiro_service.py:129-133` — `valor_recebido` → `valor_pago`, `ContaReceber` → `ContaPagar` no texto
- [x] **Step 3:** guarda de re-baixa em `pagar_conta`, entre `:379` e `:381`, espelhando `financeiro_views.py:650-677` com os status do lado pagar
- [x] **Step 4:** os cinco casos verdes; verificar que **desfazer o Step 2** derruba só os casos 1 e 2, e **desfazer o Step 3** derruba só o caso 3
- [x] **Step 5:** commit único — `fix(financeiro): baixa de conta a pagar para de estourar NameError e recusa re-baixa`

**Esforço: P.** **Migração: não.**

> **Nota — o que o adversário corrigiu neste levantamento.** (a) As âncoras do commit e do
> `except` estavam deslocadas: é `financeiro_service.py:118` e `:215-218`, não `:117` e
> `:214-217` — 📖 conferido nesta redação. (b) "O banco é debitado" era incondicional no
> resumo e é **condicional**, e o caminho padrão do modal não o dispara. (c) "Nenhum
> criador preenche o campo, logo é sempre True no parque" estava marcado 📖 e é afirmação
> sobre **dado**: virou ⚠️ dev (0 de 627), e a `migrations.py:16868-16876` prova que o
> esquema previa linhas com o campo preenchido. (d) A âncora `financeiro_views.py:425-441`
> estava marcada 🧮 e é 📖 — não há dedução nenhuma ali.

---

### Task B5.2: fixture `operacional` — tirar a dependência de ordem do módulo

**Status: ✅ entregue em `41ffe37e`.** Sem desvio; a revisão WF-1 não achou finding
nenhum (e conferiu byte a byte que `test_get_index_clona_lazy_e_renderiza` ficou
intocado — o risco 2 não se materializou).

**Files:** Modify `tests/test_e2e_orcamento_operacional_e_metricas_views.py` — acrescentar
fixture após `:131`; assinaturas de `:171` e `:222`

**O sintoma, medido nas duas formas de invocação.** 🔬 Arquivo inteiro: **7 passed** (5.97s
na refutação; 6.59s no levantamento). Isolado:

| Invocação | Resultado |
|---|---|
| `-k test_post_salvar_item_cria_nova_versao_a_partir_de_hoje` | 🔬 `1 failed` — `:175` `AttributeError: 'NoneType' object has no attribute 'id'` |
| `-k test_post_atualizar_do_original_sem_diff_flash_info` | 🔬 `1 failed, 6 deselected in 1.13s` — `:228`, mesmo `AttributeError` |
| `-k "test_get_index... or test_get_metricas or test_detalhe"` | 🔬 `5 passed, 2 deselected` |

**São DOIS testes, não um.** O registro da §8.3 do plano (`:4719`) lista só o da linha 171.

**Qual objeto falta e quem o cria por efeito colateral.** 📖 Conferido nesta redação: o
fixture `ctx` é `@pytest.fixture(scope='module')` em `:41` e entrega admin, outro_admin,
Cliente, Orcamento, OrcamentoItem, Proposta, Obra e Funcionario — **nunca** um
`ObraOrcamentoOperacional`. Quem o cria é o `c.get(f'/obra/{...}/orcamento-operacional/')`
de `:150`, dentro de `test_get_index_clona_lazy_e_renderiza`, que cai em
`garantir_operacional` (`views/orcamento_operacional_views.py:96`).

**Comportamento novo.** Um fixture **intermediário**, não a criação dentro do `ctx`:

```
@pytest.fixture(scope='module')
def operacional(ctx):
    with app.app_context():
        from services.orcamento_operacional import garantir_operacional
        op = garantir_operacional(ctx['obra_id'], criado_por_id=ctx['admin_id'])
        return op.id
```

Pedido **só** pelos testes de `:171` e `:222`. `test_get_index_clona_lazy_e_renderiza`
(`:146`) continua pedindo só `ctx` e continua sendo a **única prova do fio rota → serviço**.
📖 `garantir_operacional` é idempotente (`services/orcamento_operacional.py:69-71`) e sua
assinatura é `(obra_id, criado_por_id=None)` — sem `request` nem `current_user` —, então é
chamável de fixture sem HTTP e não muda nada quando o arquivo roda inteiro.

**Por que não criar no `ctx`.** 📖 O template renderiza
`Itens ({{ operacional.itens|length }})` (`templates/orcamento_operacional/index.html:44`),
então a asserção `'Itens (1)'` de `:156` é satisfeita por **qualquer** operacional com um
item. Com o objeto pronto, `garantir_operacional` retorna no primeiro `if`
(`services/orcamento_operacional.py:69-71`) e as seis asserções do teste 1 seguem
verdadeiras sem que o caminho lazy seja exercitado. **Verde e oco** — o mesmo formato de
falha silenciosa que originou esta rodada.

⚠️ **Correção do adversário, adotada, e ela reduz a severidade:** a perda **não** seria
"zero cobertura". 📖 Conferido nesta redação: `tests/test_orcamento_operacional.py:301` é
entry-point pytest de verdade, coletado pelo gate, e cobre `garantir_operacional` com
tenant próprio e sem fixture — clona 2 itens, 1 versão por item com `vigente_ate is None`,
`composicao_snapshot` copiada, e **idempotência explícita** (`:144-149`,
`op2.id == op.id`). O que se perderia é a prova de que a **rota HTTP** dispara o lazy. O
fixture intermediário continua sendo a escolha porque custa três linhas e preserva as duas
provas — não porque a alternativa seria catastrófica.

**Riscos → mitigação.**
1. **Nenhum dos dois testes usa o valor de retorno** — ambos re-consultam por `obra_id`
   (`:174`, `:227`). O fixture entra pelo efeito colateral. Registrado para que ninguém
   "limpe" o `return` achando que alguém o lê, nem passe a ler achando que precisa.
2. **Não tocar em `:146`.** Se alguém acrescentar `operacional` à assinatura do teste 1 "por
   simetria", a Task vira exatamente o defeito que ela existe para evitar.
3. **Reentrância do fixture `ctx`.** 📖 `:107` monta `codigo=f'OT4{s[:8]}'` — só a parte
   `YYYYMMDD`, idêntica em toda execução do dia. 🔬 Salvo pela unique **composta**
   `UniqueConstraint('codigo','admin_id')` (`models.py:337`) e pelo admin novo a cada run.
   Não é dívida hoje; é a classe de falha vizinha, e quem mexer no fixture precisa saber.

- [x] **Step 1:** rodar as duas invocações isoladas e **ver os dois vermelhos** (`:175` e `:228`)
- [x] **Step 2:** acrescentar o fixture `operacional(ctx)` depois de `:131`
- [x] **Step 3:** trocar as assinaturas de `:171` e `:222`; **não** tocar em `:146`
- [x] **Step 4:** rodar os três testes **separadamente** (três passes) e o arquivo inteiro (7/7)
- [x] **Step 5:** commit — `test(orcamento-operacional): fixture proprio tira a dependencia de ordem do modulo`

**Esforço: P.** **Migração: não.**

> **Nota — o que o adversário corrigiu neste levantamento.** (a) A dramatização "zero
> cobertura" caiu (ver acima). (b) A âncora `run_tests.sh:45` estava lida errado: **não
> existe** caminho com `-k` sobre `tests/` no gate — `--integracao` não mexe em
> `TARGET_FILE` (default `tests/test_browser_all_modules.py`, `run_tests.sh:32`), o ramo de
> `:101` **hardcoda** o arquivo, e o ramo genérico de `:112` **concatena**
> `"${TARGET_FILE}${BLOCO_FILTER}"`. A conclusão ("hoje não dispara") sobrevive; o
> mecanismo era outro. (c) A varredura de estado compartilhado achou o segundo caso
> (jornada Playwright) — ver §4, item novo nº7.

---

### Task B5.3: RDO de outro tenant — e de outra obra — responde 404

**Status: ✅ entregue em `f4857b20`, com três apertos da revisão WF-1 no commit de
revisão.** Sete casos vermelhos antes; três mutações medidas, cada uma derrubando só o
seu caso. Dois desvios de forma: (i) fixture próprio `dois_tenants_com_rdo` em vez do
helper `dois_tenants` — o caso 6 precisa de APONTADOR + `UsuarioObra` + flag, que o
helper não monta (⚠️ não declarado na mensagem do commit; registrado aqui pela
revisão); (ii) quase-erro no meio da Task, pego pelo teste de convergência do A19:
a resolução nova removeu `admin_id_atual` e o `NameError` engolido virava 302 —
reposto antes do commit. A revisão achou e o commit seguinte aplicou: `admin_id`
derivado do RDO resolvido (padrão de `finalizar_rdo`) em `visualizar`/`excluir`, no
lugar do recálculo que divergia para SUPER_ADMIN; e o eager-loading das queries
antigas reposto em `visualizar`/`pdf`.

**Files:** Modify `views/rdo.py` — `visualizar_rdo` (`:1063-1088`), `exportar_rdo_pdf`
(`:1532-1552`), `excluir_rdo` (`:449-476`), e os `except Exception` de `:590`, `:1526`,
`:1565`, `:1660`, `:2069`, `:2150`; `criar_rdo` (`:719-727`) e `rdo_salvar_unificado`
(`:2720-2727`);
Modify `tests/test_fase5_rdo_ciclo_vida.py` — asserções de `:637` e `:693`;
Create `tests/test_b5_rdo_404_cross_tenant_e_cross_obra.py`

**A âncora andou, e não é homônimo.** 📖 Conferido nesta redação: `views/rdo.py:1065` é
`def visualizar_rdo(id)` (rota `@main_bp.route('/rdo/<int:id>')` em `:1063`) e `:1086` é o
`if not rdo:` com `flash` + `redirect('/funcionario/rdo/consolidado')`. O plano aponta
`:1111-1113`. 🔬 Ataque por homonímia (há **quatro** `if not rdo:` no arquivo — `:474`,
`:1086`, `:1550`, `:2702`): `git show b32b3629:views/rdo.py` mostra que a última rota antes
de `:1113` é a mesma `visualizar_rdo`. Deslocamento de 26 linhas, causado pela B2.9.

**O 302 não é o motivo, e o recorte precisa dizer isso.** 🔬 `/rdo/<alheio>` e
`/rdo/<inexistente>` devolvem 302 com o **mesmo** `Location` e a **mesma** flash — não é
oráculo de enumeração. E o Status da própria B1.15 (plano `:1806-1809`) declara que
flash+redirect "não é oráculo, então fica como está". **A regra da casa, na forma escrita
em `views/almoxarifado/movimentos.py:276-280`, é sobre 403 → 404 e tem por critério o
oráculo.** Este item sobrevive por três motivos que **não** são esse:

1. 🔴 **O eixo OBRA da Fase 1 não chegou nestas três rotas.** 📖 Conferido nesta redação:
   `cronograma_views.py:2695-2704` é uma rota de **leitura de RDO** que responde as duas
   perguntas com a **mesma** mensagem de propósito — primeiro
   `RDO.query.filter_by(id=rdo_id, admin_id=admin_id).first()` → 404, depois
   `if not pode_ver_obra(rdo.obra_id):` → 404, com o comentário "LEITURA: escopo de VER,
   não de apontar". 🔬 `grep -n 'pode_ver_obra' views/rdo.py` devolve `:1590`, `:1701`,
   `:1738`, `:1774`, `:1813` (todas de **escrita**) e `:1047-1050` (render de botão) —
   **nenhuma de leitura**. Com `escopo_obra_ativo` ligado num tenant, um APONTADOR
   vinculado só à obra X lê, exporta em PDF e **apaga** o RDO da obra Y da mesma empresa.
   ⚠️ Ressalva honesta, que vai no recorte: 📖 `scripts/flag_escopo_obra.py:23-29` — a flag
   é por tenant (`ConfiguracaoEmpresa.escopo_obra_ativo`) e falha para False, e
   `utils/autorizacao.py:90-92` e `:121-131` devolvem GESTOR para todo mundo com a flag
   desligada. **Num parque com a flag desligada o buraco não é explorável hoje.**
2. 🔴 **O oráculo de verdade está em outro lugar do mesmo arquivo.** 📖 `views/rdo.py:720-727`:
   depois de a query com `admin_id` falhar, o código dispara **de propósito** uma segunda
   query **sem tenant** (`Obra.query.filter_by(id=obra_id).first()`) só para escolher entre
   "Acesso negado: esta obra pertence a outra empresa." e "Obra não encontrada.". Gêmeo em
   `:2721-2727` (`rdo_salvar_unificado`). Os dois caminhos são 302; **o vazamento é na
   mensagem**.
3. **O 404 já está escrito em três rotas e é engolido.** 📖 `views/rdo.py:1587` chama
   `_rdo_do_tenant_ou_404(id)` de dentro do `try` de `finalizar_rdo`, e o `except Exception`
   de `:1660` engole o `NotFound`. 📖 `:1950` (`atualizar_rdo`) e `:2086` (`editar_rdo`)
   usam `.first_or_404()` dentro de `try` com `except` largo (`:2069`, `:2150`). 🔬 As três
   devolvem 302 (Location `/rdo/lista`, `/rdo/<id>/editar`, `/rdo/lista`), enquanto
   assinar/aprovar/reabrir/retificar/duplicar — que chamam o mesmo helper **fora** do try —
   devolvem 404. 🔬 Confirmado por indentação: `:1587` tem 8 espaços; `:1699`, `:1736`,
   `:1772`, `:1811`, `:1868` têm 4.

**A forma da correção já existe no arquivo — não há nada a inventar.** 📖 `views/rdo.py:2`
importa `HTTPException`, e 🔬 `grep -n 'except HTTPException' views/rdo.py` devolve `:303`
(em `rdos()`, com o comentário "p1 Step B — 404/403 são RESPOSTA, não falha a ser
recuperada") e `:2491` (em `funcionario_rdo_consolidado`, "A19/B2.10, Risco 3 — o catch-all
abaixo engoliria um `abort()`"). O padrão, com a justificativa escrita, já foi aplicado
duas vezes por Steps deste mesmo plano.

**Comportamento novo (escopo recomendado).**
1. `visualizar_rdo`, `exportar_rdo_pdf` e `excluir_rdo` passam a resolver o RDO por
   `_rdo_do_tenant_ou_404` (`views/rdo.py:1667-1684`), **chamado antes do `try`**.
2. As três ganham `pode_ver_obra(rdo.obra_id)` com **404 e a mesma mensagem**, copiando
   `cronograma_views.py:2700-2704` — inclusive o comentário que separa "escopo de VER" de
   "escopo de apontar".
3. Os seis `except Exception` (`:590`, `:1526`, `:1565`, `:1660`, `:2069`, `:2150`) ganham
   `except HTTPException: raise` **antes**, no formato de `:303`.
4. `criar_rdo` (`:719-727`) e `rdo_salvar_unificado` (`:2720-2727`) perdem a segunda query
   sem tenant e passam a flashar **uma** mensagem para os dois casos.

**Teste que prova.** Dois tenants (`dois_tenants`), **um request autenticado por
`app_context`** — a regra da §11.5 do plano consolidado, que não é negociável aqui.

| # | Ação | Asserção |
|---|---|---|
| 1 | GET `/rdo/<id do tenant B>` como A | 404 |
| 2 | GET `/rdo/<id inexistente>` como A | 404, **corpo idêntico** ao do caso 1 |
| 3 | GET `/rdo/<alheio>/pdf` como A | 404 |
| 4 | POST `/rdo/excluir/<alheio>` como A | 404 **e o RDO de B sobrevive** |
| 5 | POST `/rdo/<alheio>/finalizar`, `/atualizar`, `/editar` como A | 404 nos três (hoje: 🔬 302) |
| 6 | Tenant com `escopo_obra_ativo=True`: APONTADOR vinculado à obra X pede o RDO da obra Y **do mesmo tenant** | 404 nas três rotas |
| 7 | POST `/rdo/criar` com `obra_id` de outro tenant | a flash **não** distingue "outra empresa" de "não encontrada" |

E o aperto das duas asserções que medem os dois lados: `tests/test_fase5_rdo_ciclo_vida.py:637`
e `:693` passam de `in (302, 404)` para `== 404`.

**Por que o atual não pegava.** 🔬 `tests/test_a19_progresso_v1_convergencia.py` — o teste
de convergência que o plano diz congelar o 302 — importa `um_tenant` e não tem asserção
cross-tenant nenhuma: **a asserção 4 do recorte da B2.12 (plano `:2742`) nunca foi
entregue**. E 🔬 `grep -rn 'rdo' tests/test_fase1_escopo_obra.py tests/test_fase1_matriz_autorizacao.py`
→ **vazio**: existe `test_detalhe_de_obra_sem_vinculo_devolve_404_com_flag_ligada`
(`tests/test_fase1_escopo_obra.py:415`) para `/obras/<id>` e **nada** equivalente para
`/rdo/<id>`.

**Riscos → mitigação.**
1. **Trocar as três linhas por `abort(404)` NÃO produz 404.** 📖 `NotFound` é subclasse de
   `Exception` e cai no `except` de `:1526`, virando "Erro ao carregar RDO." + 302 — o
   comportamento de hoje com outra mensagem, e a Task fecharia verde sem mudar nada. → o
   Step do `except HTTPException: raise` vem **antes** do Step das guardas.
2. **Ordem dentro do handler.** 📖 `excluir_rdo` (`:590`), `finalizar_rdo` (`:1660`) e
   `atualizar_rdo` (`:2069`) começam com `db.session.rollback()`. Pôr o ramo de
   `HTTPException` antes (a forma de `:303`) faz um `abort()` tardio pular o rollback.
   🧮 Inofensivo hoje — não há `abort()` depois da guarda nessas funções, e o teardown do
   Flask-SQLAlchemy faz `session.remove()` —, mas tem de estar escrito, senão vira achado
   de revisão.
3. **Três resoluções de tenant diferentes para o mesmo RDO, no mesmo arquivo.** 📖
   `visualizar_rdo` (`:1074`) usa `current_user.id if ADMIN else current_user.admin_id`;
   `exportar_rdo_pdf` (`:1537-1540`) usa `getattr(current_user,'admin_id',None) or current_user.id`;
   `_rdo_do_tenant_ou_404` (`:1676-1678`) usa `get_tenant_admin_id()`, que devolve
   `current_user.id` também para SUPER_ADMIN. 🧮 Unificar no helper **muda comportamento
   para SUPER_ADMIN** (hoje `admin_id=None` em `/rdo/<id>` e `current_user.id` no PDF). Tem
   de estar no recorte, não ser descoberto depois.
4. **A chave de escopo não é a mesma em toda a família.** 📖 `models.py:1186` —
   `RDO.admin_id` é `nullable=True`, e `views/rdo.py:1588` (`rdo.admin_id or rdo.obra.admin_id`)
   conta com isso. `_rdo_do_tenant_ou_404` escopa por `Obra.admin_id` (join);
   `rdo_editar_sistema.py:41` e `:188` escopam por `RDO.admin_id` **direto**. Trocar a
   guarda pelo helper ali **muda o conjunto** de RDOs alcançáveis. → `rdo_editar_sistema.py`
   **fica fora** desta Task.
5. **UX.** 🔬 Hoje o usuário que clica num link morto cai na consolidada com flash; com 404
   cai em `templates/error.html` (`error_handlers.py:49-54`), sem flash e sem volta. É a
   decisão **D-B5.3** (§8). 🔬 A lente 3 provou que **nenhum JS quebra**: não há `fetch`
   para `/rdo/<id>` nem para `/rdo/<id>/pdf`, e nenhum `status === 404` em `templates/` ou
   `static/`. `scripts/smoke_test_modulos_criticos.py:47-50` extrai o id do **próprio**
   tenant, então não é afetado.
6. **Três URLs chegam na mesma linha 1086.** 📖 `crud_rdo_completo.py:242-246`
   (`/rdo/visualizar/<id>`, **viva** — sem concorrente no `main_bp`, exercitada por
   `tests/test_browser_all_modules.py:1181`) e `views/rdo.py:3355-3359`
   (`/funcionario/rdo/<id>`, `redirect` para `main.visualizar_rdo`). As duas são redirect
   puro e herdam o comportamento — mas o teste precisa saber que existem.

**O que esta Task NÃO faz.** A família completa do padrão flash+redirect-em-vez-de-404 é de
🔬 **35 rotas** (`frota_views.py` + `views/vehicles.py` concentram **14**), mais 🔬 45
candidatas estáticas de "404 escrito e engolido por `except` largo" —
`propostas_consolidated.py` (16), `views/vehicles.py` (11), `ponto_views.py` (5),
`configuracoes_views.py` (5), `views/rdo.py` (3, **as únicas medidas**), `views/obras.py`
(2), `alimentacao_views.py` (1). 📖 Pelo menos uma é falso positivo: `views/obras.py:1541`
é `@obra_required()` **fora** do try, com 404 congelado por
`tests/test_fase1_escopo_obra.py:412`. **A família inteira é Task própria, com arreio
próprio** — incluí-la aqui vira G.

- [x] **Step 1:** escrever o teste e ver os sete casos vermelhos (302 nos casos 1-5, mensagem distinta no 7)
- [x] **Step 2:** `except HTTPException: raise` nos seis handlers, **antes** do `rollback`
- [x] **Step 3:** `_rdo_do_tenant_ou_404` antes do `try` nas três rotas, com a nota de mudança para SUPER_ADMIN no commit
- [x] **Step 4:** `pode_ver_obra` com 404 e mensagem idêntica, copiando `cronograma_views.py:2700-2704`
- [x] **Step 5:** mensagem única em `:719-727` e `:2720-2727`; a segunda query sem tenant **sai**
- [x] **Step 6:** apertar `tests/test_fase5_rdo_ciclo_vida.py:637` e `:693` para `== 404`
- [x] **Step 7:** commit — `fix(rdo): RDO de outro tenant e de outra obra responde 404`

**Esforço: M.** **Migração: não.**

> **Nota — o que o adversário corrigiu neste levantamento.** (a) A conclusão "é convenção,
> não segurança" caiu: era verdadeira só no eixo TENANT, que foi o único que a varredura
> olhou. O eixo OBRA tem regra formada, escrita e aplicada **em rota de leitura de RDO**
> (`cronograma_views.py:2702-2704`), e as três rotas não a seguem. O levantamento chegou a
> ver essas linhas — a lente STRING as relata como "4 já-conformes (jsonify 404) em
> cronograma_views.py" — e as classificou como ruído de grep. (b) A recomendação de escopo
> contradizia o próprio levantamento: **nenhuma** das quatro opções oferecidas continha
> `criar_rdo`/`rdo_salvar_unificado`, isto é, o único achado de segurança de verdade
> ficava de fora da opção recomendada. Aqui ele está dentro. (c) A "forma incerta" da
> correção não é incerta: `except HTTPException: raise` já existe duas vezes no arquivo.

---

### Task B5.4: `rdo_crud` — aposentadoria PARCIAL e correção do registro do E04

**Status: ✅ entregue em `e3ca534c`.** Caracterização verde antes do corte; a medição
corrigiu um chute do recorte (o endpoint sombreado de `/rdo/editar/<id>` é
`rdo_editar.editar_rdo_form`). A revisão WF-1 achou dois findings baixos de TEXTO,
aplicados no commit de revisão: a nota de proveniência do docstring de `models.py`
descrevia errado o que estava errado onde, e "sem decorador como `salvar_rdo`" era
inexato (o `@login_required` permanece — sem decorador de ROTA).

**Files:** Modify `crud_rdo_completo.py` — decoradores de `:653` e `:681`;
Modify `models.py:2179-2183`, `docs/superpowers/plans/2026-08-04-plano-consolidado.md:4732`
e `ESTADO-ATUAL.md:939` (correção de registro);
Create `tests/test_b5_rdo_crud_url_map.py`

**A decisão é MANTER o blueprint.** 🔬 Medido no `url_map` real (e 🔬 reproduzido na
refutação por `Map` estático do werkzeug 3.1.3, **sem importar `main`** — importar dispara
`executar_migracoes()` e `auto_fix_all_admin_id()` contra o banco de dev):

| Placar | Rotas |
|---|---|
| **Sombreadas (4)** | `/rdo/` → `main.rdos`; `/rdo/novo` → `main.novo_rdo`; `/rdo/editar/<id>` → `rdo_editar.*`; `/rdo/excluir/<id>` → `main.excluir_rdo` |
| **Vencedoras (9)** | `visualizar_rdo`, `finalizar_rdo`, `api_subatividades_por_servico`, `api_funcionarios`, `upload_foto_rdo`, `servir_foto`, `listar_fotos_rdo`, `editar_descricao_foto`, `deletar_foto` |
| **Sem rota (1)** | `salvar_rdo()` (`crud_rdo_completo.py:254`) — decorador removido em `b30923b5` |

📖 Os 13 decoradores conferidos nesta redação: `:43`, `:202`, `:236`, `:242`, `:526`,
`:573`, `:653`, `:681`, `:706`, `:859`, `:907`, `:943`, `:971`.

**Cinco das nove vencedoras são o backend de foto de TODAS as telas de RDO**, e o consumo é
invisível a grep pelo símbolo: 📖 `templates/rdo/editar_rdo.html:1286` (`fetch` de
`/rdo/${rdoId}/fotos/upload`), `:1333` (galeria), `:1398` (legenda), `:1419` (delete), e
📖 `templates/rdo/visualizar_rdo_moderno.html:1974/1986/2036/2046`
(`url_for('rdo_crud.servir_foto')`). ⚠️ dev: `rdo_foto` tem 50.966 linhas, **6.647** com
`armazenamento='disco'` — só renderizáveis por `servir_foto`.

**Comportamento novo (o corte que a evidência sustenta).**
1. **Cortar** os decoradores de `/rdo/api/subatividades/<servico_id>` (`:653`) e
   `/rdo/api/funcionarios` (`:681`). As duas **vencem** o despacho e têm 🔬 **zero
   consumidor** em `templates/`, `static/`, `views/`, `services/`, `docs/`, `tests/`,
   `n8n_workflows/` — inclusive contra URL **relativa**, que era o caminho de ressurreição
   mais provável e foi testado. Nenhum `url_for` interno aponta para elas.
2. **Corrigir o registro do E04**, que esta varredura derrubou: os pontos vivos de
   `AlocacaoEquipe.rdo_gerado_id` são **dois** (`views/rdo.py:536-538` e
   `services/importacao_fisico_financeiro.py:372-373`), não três. O terceiro
   (`crud_rdo_completo.py:557`) está numa rota que nunca é despachada. Corrigir também os
   números de linha defasados: o plano `:4732` e `models.py:2181` dizem
   `crud_rdo_completo.py:539` (hoje `:557`) e `views/rdo.py:561-563` (hoje `:536-538`).
3. **Um teste que congela o url_map**, para que a próxima varredura não precise refazer a
   medição: afirma os 4 sombreamentos, as 9 vencedoras e a ausência de regra para
   `salvar_rdo`.

**O que NÃO cortar, e por quê.**
- `/rdo/` (`:43`) e `/rdo/editar/<id>` (`:236`): 📖 a rota **viva** `finalizar_rdo` chama
  `url_for('rdo_crud.listar_rdos')` em `:587` e `url_for('rdo_crud.editar_rdo', ...)` em
  `:595`. `url_for` resolve por **endpoint**, e endpoint sem regra levanta `BuildError`.
  Sombreada por path **não é** inalcançável por `url_for`. (E 📖 há um terceiro par que o
  levantamento não listou: `:645` e `:651` chamam `url_for('rdo_crud.visualizar_rdo', ...)`
  — são **quatro** destinos a reescrever, não dois, se um dia o blueprint encolher.)
- `/rdo/novo` (`:202`): corte limpo em tese, mas sem ganho isolado — vai junto de qualquer
  decisão maior.
- `/rdo/excluir/<id>` (`:526`): 🔴 **não cortar nesta rodada.** `crud_rdo_completo.py:557`
  é um dos pontos catalogados do **E04, que está ADIADO** aguardando contagem em produção
  (plano `:4732`). Cortar a rota **apaga do inventário** um ponto antes do gate. A ordem
  certa é o inverso: usar a medição para **corrigir o registro** (item 2 acima) e só depois
  decidir o corte, junto do E04.
- `rdo_crud.editar_rdo` (`:236-240`): 🔬 `url_for` das duas rotas produz a **mesma** string
  `/rdo/editar/1`, e a função só faz `redirect` para a outra. Hoje perde o despacho; se a
  ordem de registro em `main.py` mudar, vira **laço 302 infinito**. Registrado como bomba,
  não cortado — cortar exige reescrever `:587` e `:595` primeiro.

**Riscos → mitigação.**
1. **A isenção de CSRF é ponto ÚNICO, não duplo.** 📖 `app.py:1052-1067` aplica
   `csrf.exempt` no nível de módulo de `app.py`, isto é, no `from app import app` de
   `main.py:1` — e `rdo_crud_bp` só é registrado em `main.py:25`. Logo
   `app.blueprints.get('rdo_crud')` devolve `None` e o `if bp:` de `:1065` pula: **a entrada
   de `app.py:1055` é no-op**; quem isenta é `main.py:206-219`. Quem apagar a lista de
   `main.py` achando que `app.py` cobre **derruba o upload de foto em produção com 400 de
   CSRF**, sem erro de import e sem teste vermelho de coleta. É o formato exato do incidente
   da B4.8.
2. **Dependência de testes por STRING de nome de arquivo, não por import.** 📖
   `tests/test_p1_dedup_cross_origem.py:207`, `tests/test_fase1_identidade.py:333-335` e
   `tests/test_arreio_custo_rdo_rotas.py:19` abrem `crud_rdo_completo.py` com `open()` e
   afirmam sobre o **texto**. Apagar o arquivo dá `FileNotFoundError` em runtime de teste,
   que `grep 'from crud_rdo_completo'` não anteciparia.
3. **Sobreposição GET/POST dentro do próprio blueprint.** 🔬 `GET /rdo/foto/9/editar` e
   `GET /rdo/foto/9/deletar` despacham para `servir_foto` com `tipo='editar'/'deletar'`
   (a regra catch-all de `:859` cobre o path; `:943` e `:971` são POST-only). Hoje devolve
   400 "Tipo inválido" (📖 `:885-886`) e é inofensivo — mas qualquer variante GET futura
   desses paths **nasce sombreada**.
4. **`servir_foto` não é só sobrevivente: é base de fase planejada.** 📖
   `docs/fase-5-rollout.md:129` registra que a Fase 5 **não** migrou o portal do cliente
   para servir foto por URL porque `servir_foto` exige `@login_required` e o portal é por
   token, e que a rota gêmea por token é **Fase 9a**. Aposentar orfana a 9a.
5. **A superfície de foto é maior que `armazenamento='disco'`.** 📖
   `visualizar_rdo_moderno.html:1986` está no ramo `{% elif foto.thumbnail %}` e `:2046` no
   `{% elif foto.arquivo_otimizado %}` — mesmo numa base 100% `'banco'`, qualquer foto com
   `thumbnail` ou `arquivo_otimizado` cai em `url_for('rdo_crud.servir_foto')`.

- [x] **Step 1:** escrever `tests/test_b5_rdo_crud_url_map.py` congelando o placar 4/9/1 e vê-lo **verde** (é caracterização, não correção)
- [x] **Step 2:** cortar os decoradores de `:653` e `:681`; rodar o teste do Step 1 e ver as duas regras sumirem do map
- [x] **Step 3:** corrigir `models.py:2179-2183`, plano `:4732` e `ESTADO-ATUAL.md:939` — dois pontos vivos, números de linha atuais, e a nota de que a rota sombreada **não** protege base nenhuma
- [x] **Step 4:** commit — `chore(rdo): corta as duas rotas de API mortas do rdo_crud e corrige o registro do E04`

**Esforço: P** para o recorte acima. **Migração: não.**

> **Nota — o que o adversário corrigiu neste levantamento.** (a) A entrada de CSRF em
> `app.py:1055` é **no-op** — o levantamento a apresentou como uma de duas isenções ativas,
> e a consequência prática se inverte. (b) A lente STRING foi rodada sobre `templates` e
> `static` e **não** sobre `tests/`, onde estão os consumidores mais fortes por path
> literal: `tests/test_fase5_rdo_fotos.py:154,209,238,309,316,336,341,360` (inclusive
> `assert '/rdo/foto/' in corpo`), `tests/test_rdo_foto_uploads_path.py:151,174`,
> `tests/test_browser_all_modules.py:1392`. Ironia de método: a varredura declara que o
> furo da B4.8 foi grep por símbolo em vez de string, e roda a lente STRING sem incluir a
> superfície de teste. (c) "Corte seguro" de `/rdo/excluir/<id>` **não é seguro** — colide
> com o E04 adiado (ver acima). (d) "A dívida foi enunciada errada no plano" é exagero:
> o corpo do plano (`:2750-2774`) está correto; o atacável é o título da célula da §8.3.
> (e) A conclusão central já estava escrita no repositório: 📖 `DOSSIE-REPO.md:325` —
> "`crud_rdo_completo.py` **não é descartável**: as rotas de foto continuam vivas... É
> **metade vivo / metade sombreado**".

---

### Task B5.5: curva de baseline — terceira série derivada de `CronogramaBaselineItem`

**Status: ⛔ CORTADA em 06/08 — decisão do Cássio, e o mecanismo foi o previsto no
próprio Step 1 ("a Task pode morrer nele").** O Cássio decidiu não rodar as consultas
de produção; sem a medição, decide a evidência disponível: 🔬⚠️ dev, **uma** obra no
banco inteiro onde a série seria calculável e diferente, com Δ máx **1,1 p.p. na
direção contrária** à do risco 6, e 🔬 o SPI/SV não é exibido a ninguém. Volta se, e
só se, vier fato novo (uma medição, ou usuário reclamando de curva que não mostra
atraso). O recorte abaixo fica como está — é o COMO, se o SE um dia mudar.

🔴 ~~**BLOQUEADA no Step 1: medição em PRODUÇÃO.** Mesma trava da B2.13.~~

**Files:** Modify `utils/cronograma_engine.py` — função nova irmã de
`calcular_progresso_geral_obra_v2`; Modify `views/obras.py:2818-2896` — terceira chave no
payload; Modify `templates/obras/detalhes_obra_profissional.html:3059-3145` — terceiro
dataset; Create `tests/test_b5_curva_baseline.py`

**A dívida existe; a causa do risco 6 está errada, e com ela a correção.** 📖 Caminho
conferido linha a linha nesta redação: `views/obras.py:2885` monta
`'planejado': float(agg.get('progresso_planejado_pct') or 0.0)`; `agg` vem de
`calcular_progresso_geral_obra_v2` (`utils/cronograma_engine.py:943` agrega
`prog.get('percentual_planejado')`, `:965` devolve); `prog` vem de `calcular_progresso_rdo`,
que em `:765-767` chama `_planejado_na_data(tarefa.data_inicio, tarefa.data_fim,
tarefa.duracao_dias, ...)` com as datas **vivas** da tarefa. **A Curva S nunca leu
`ap.percentual_planejado`.** Ela já era plano corrente antes do A06.

🔬 Corroboração encontrada na refutação, e é mais forte que a do levantamento: a docstring
do próprio A06 afirma o contrário do que o código faz. 📖 `cronograma_views.py:127-130` —
"quem a lê — a curva de avanço da obra, o PDF do RDO, o EVM — comparava o realizado com um
planejado órfão". Das três, **só o PDF do RDO** lê o snapshot
(`services/rdo_pdf_service.py:684`); a curva lê o cálculo vivo e o EVM não lê
`percentual_planejado` em ponto nenhum.

**O insumo já existe e está populado — sem migração.** 📖 `models.py:6270-6294`,
`CronogramaBaselineItem` guarda `data_inicio`, `data_fim` e `duracao_dias` por tarefa, com
a docstring "Nunca é reescrito" (conferido nesta redação). ⚠️ dev: 30.374 baselines, 30.196
ativas, 769.929 itens; 🔬 **0** itens sem `data_inicio` (ataque da refutação, que o
levantamento não tinha medido — `_planejado_na_data` devolve `None` sem ele) e **0**
divergências de classificação de marco (`duracao_dias == 0`) entre tarefa viva e item
congelado. 📖 `migrations.py:5709-5790` (migração 277) congelou o parque **antes** de ligar
o editor v2 — é por isso que o insumo existe.

**Comportamento novo.** Uma **terceira série**, derivada na LEITURA, sem escrita e sem
coluna nova:
1. Função nova no **engine** (não na view — ver risco 1), irmã de
   `calcular_progresso_geral_obra_v2`, que reusa `_planejado_na_data`
   (`utils/cronograma_engine.py:368-389`, função **pura**, recebe datas por parâmetro)
   passando as datas do `CronogramaBaselineItem` no lugar das da tarefa.
2. `/obras/<id>/curva-avanco` ganha uma terceira chave no ponto. 🔬 A rota é declarada uma
   única vez (`views/obras.py:2818`, `main_bp`) e tem exatamente três consumidores:
   `templates/obras/detalhes_obra_profissional.html:2082`,
   `scripts/smoke_test_modulos_criticos.py:65` (que só faz GET, `:59-66`) e ela mesma.
   Acrescentar chave não quebra ninguém.
3. Terceiro dataset no Chart.js, ao lado de 'Planejado' e 'Realizado'
   (`templates/obras/detalhes_obra_profissional.html:3100-3110`).

**Riscos → mitigação.**
1. 🔴 **Onde o código mora colide com o p4.** 🔬 O commit `a2321503` estabeleceu
   `calcular_progresso_geral_obra_v2` como fórmula única, e
   📖 `tests/test_p4_formula_unica_progresso.py:1-19` lista as cinco fórmulas mortas.
   "~40 linhas em `views/obras.py`" reimplementa a média ponderada **dentro de uma view** —
   a forma exata que o p4 apagou —, e 📖 as guardas textuais do p4 (`:153-181`) são strings
   específicas (`'set perc_total'`, `'total_percentual / total_sub'`, `'sqlfunc.avg('`) que
   **não** pegariam a reincidência: o gate passaria verde. → a série nasce no engine.
2. 🔴 **De que lado o laço começa.** O agregado itera as **folhas vivas**
   (`utils/cronograma_engine.py:906-914`, `folhas_efetivas`, calculado do `tarefa_pai_id`
   de hoje), enquanto os itens de baseline retratam a árvore da época do congelamento.
   🔬⚠️ dev: **160.472** itens de baseline ativa pertencem a tarefas que **hoje têm
   filhos** — iterar os itens dupla-contaria pai e filha. → laço sobre `folhas_efetivas`,
   lookup por `tarefa_id`.
3. **O efeito é retroativo, não só prospectivo.** 🧮📖 `_planejado_na_data` faz
   `dias_uteis_entre(data_inicio, data_ref)/duracao_dias` (`:387-388`) e a rota recalcula
   para **cada** data de RDO a cada request (`views/obras.py:2874-2879`). Esticar `data_fim`
   **baixa** o planejado de todos os pontos passados: pontos que mostravam atraso na semana
   passada podem mostrar folga hoje. O risco 6 diz "nunca mais mostra atraso"; o
   comportamento real é uma história que se reescreve nos dois sentidos.
4. **Bordas medidas.** 🔬⚠️ dev: **645** tarefas vivas em obras com baseline ativa não têm
   item (criadas depois do congelamento) e **1** item aponta para tarefa arquivada; **95**
   obras têm curva calculável e não têm baseline. → decisão **D-B5.5c** (§8).
5. **Peso.** 📖 `utils/cronograma_engine.py:936-940` pondera por `quantidade_total` quando
   todas as folhas a têm com unidade única, e cai para `duracao_dias`. `CronogramaBaselineItem`
   **não** guarda `quantidade_total` (📖 `models.py:6270-6294`) — mas
   `CronogramaTarefaSnapshot` guarda (📖 `models.py:6432-6474`). É a decisão **D-B5.5a**, e
   é ela que empurraria alguém a pedir coluna nova. **A resposta é escolher o peso, não
   migrar.**
6. **Sem teste hoje, de nenhum tipo.** 🔬 `grep -rn "curva-avanco|curva_avanco|'pontos'" tests/`
   → **vazio**, e `progresso_planejado_pct` só aparece em `utils/cronograma_engine.py`
   (`:863`, `:901`, `:912`, `:965`) e `views/obras.py:2885`. A correção nasce com o
   primeiro teste da rota.

**O risco que decide se esta Task deve existir.** 🔬⚠️ dev, medido na refutação: das 30.196
obras com baseline ativa, **82** têm qualquer divergência entre datas vivas e congeladas
(84 itens em 769.573 pares), e **uma** delas tem RDO Finalizado. Rodadas as duas séries
nessa obra (12219, 83 folhas, 20 datas de RDO, ponderação por `duracao_dias`), a diferença
máxima é **1,1 p.p.** e a linha de baseline fica **abaixo** da viva em todos os 20 pontos —
isto é, as datas foram **antecipadas**, o plano corrente é **mais** exigente que o
congelado, e a curva de hoje já mostra **mais** atraso do que a de baseline mostraria. **O
sintoma que o risco 6 descreve tem zero ocorrências observadas em dev.** Somado ao fato de
que 🔬 o SPI/SV **não é exibido em lugar nenhum** (`grep -rn -i 'evm' templates static` →
zero linhas; as chaves lidas por `static/js/financeiro_obra.js` não incluem `p.evm`), o
quadro é: dívida real, diagnóstico reescrito corretamente, **valor de entrega não medido**.

- [ ] **Step 1:** 🔴 **PRODUÇÃO** — rodar as duas consultas de divergência (§7). Se o número
      for tão pequeno quanto em ⚠️ dev, a decisão muda de "como implementar" para "se
      implementar", e a Task **para aqui**
- [ ] **Step 2:** respostas de **D-B5.5a** (peso), **D-B5.5b** (escopo: só a curva ou também o PV do EVM) e **D-B5.5c** (bordas)
- [ ] **Step 3:** teste da rota `/obras/<id>/curva-avanco` — hoje ela **não tem nenhum**
- [ ] **Step 4:** série de baseline no **engine**, laço sobre `folhas_efetivas` com lookup por `tarefa_id`
- [ ] **Step 5:** terceira chave no payload e terceiro dataset no Chart.js
- [ ] **Step 6:** verificar que o gate do p4 (`tests/test_p4_formula_unica_progresso.py`) continua verde **e** que a fórmula nova não está na view
- [ ] **Step 7:** commit — `feat(cronograma): curva de avanco ganha a serie da linha de base`

**Esforço: M** para o código. **Migração: NÃO** — as datas congeladas já estão em
`cronograma_baseline_item`, 769.929 linhas populadas. A faixa 280-283 **não** é gasta.

> **Nota — o que o adversário corrigiu neste levantamento.** (a) A justificativa do escopo
> maior caiu: "consertar só a curva deixa o painel com duas leituras contraditórias de
> atraso" é falso porque **o painel não exibe SPI/SV/CPI/BAC** — o `evm` é calculado
> (`services/cronograma_fisico_financeiro.py:583`), servido (`views/obras.py:2347-2351`) e
> **descartado pelo front**; o único assert é `tests/test_p10_evm.py:178`. O levantamento
> tinha isso como pergunta aberta e afirmou o contrário sem hedge. (b) A06 são **dois**
> commits (`318b294d` = B2.17+B2.18+B2.19, `19be5ea8` = B2.20), não um. (c) "28.457 obras
> com RDO Finalizado" são 28.463. (d) O SPI já mistura bases independentemente de datas:
> 📖 `services/evm.py:82-84` usa `bac` da baseline e `:87-88` usa totais vivos — revisar o
> orçamento para cima piora o SPI sem nada mudar na obra.

---

## 4. Itens ABERTOS que esta rodada descobriu

No formato da §8.3 do plano consolidado: **fatos novos** que apareceram varrendo e que não
cabem em nenhuma das cinco Tasks. Nenhum vira Task nesta rodada.

| # | O fato | Âncora | Por que não entrou |
|---|---|---|---|
| 1 | 🔴 **`banco.saldo_atual` é catraca de mão única, e é HOJE.** `baixar_pagamento` debita (`financeiro_service.py:114`) e `baixar_recebimento` credita (`:339`); 🔬 varridos todos os escritores de `saldo_atual` fora de `archive/tests/scripts`, **nada credita de volta**. `estornar_conta` (`financeiro_views.py:296-331`) devolve `valor_pago`, saldo, status e apaga os `LancamentoContabil` — e **não** restaura o saldo do banco. `estornar_gcp` (`:334-370`) também não. E 📖 `saldo_inicial` do fluxo de caixa é literalmente `sum(banco.saldo_atual)` (`financeiro_service.py:485`) | `financeiro_views.py:296-331` | Existe um caminho de tela que **reduz permanentemente o saldo inicial do fluxo de caixa** sem lançamento correspondente e sem reversão pela UI. A B5.1 põe a guarda que empurra o operador para o estorno — e o estorno tem este defeito. **Task própria, e é dinheiro** |
| 2 | **Os dois caminhos de pagamento discordam sobre o que é pagar.** `baixar_pagamento` debita o banco quando há `banco_id`; o pagamento de GCP (`gestao_custos_views.py:880-1000`) **exige** banco (`:939-941`), usa o banco no FluxoCaixa (`:969`) e **nunca** toca `saldo_atual` | `gestao_custos_views.py:939-969` | O saldo inicial do fluxo depende de **por qual tela** o pagamento entrou. Entra junto do item 1 |
| 3 | **Escritor de `FluxoCaixa` SAIDA morto por construção, que derruba o `CustoVeiculo` junto.** `views/vehicles.py:922-930` não passa `admin_id`, que é `nullable=False` (📖 `models.py:1130`, e 🔬 confirmado na coluna real: `information_schema.columns` → `is_nullable='NO'`). O try/except de `:921-933` só cobre a construção; o `IntegrityError` vem no commit de `:935` e cai no `except` de `:940-943`, que faz rollback | `views/vehicles.py:922-930` | Fora do escopo da dívida, mas é escritor de SAIDA e a pergunta pedia todos |
| 4 | **Leitores sem escritor — o E02 espelhado na tabela sob investigação.** `ponto_views.py:849-853` e `:932-940` leem e apagam `FluxoCaixa` com `referencia_tabela='registro_ponto'`; nenhum escritor de produção grava esse valor e ⚠️ dev tem 0 linhas | `ponto_views.py:849`, `:932` | Achado da lente STRING; é limpeza, não defeito ativo |
| 5 | **A proteção contra dupla contagem existe numa tela e não no fluxo de caixa.** 🔬 A exclusão `~GestaoCustoPai.id.in_(_compra_gcp_ids)` está só em `listar_contas_pagar`; `calcular_fluxo_caixa` não tem equivalente e os GCPs de pedido de compra entram inteiros em `saidas_previstas` | `financeiro_views.py:195-217` × `financeiro_service.py:504-585` | Antecede e independe de qualquer coisa que se faça com `ContaPagar` |
| 6 | 🔴 **Duas decisões documentadas e CONTRADITÓRIAS sobre qual camada é a fonte da saída de caixa.** 📖 `compras_views.py:250-255`: "ContaPagar = camada de OBRIGAÇÃO FINANCEIRA (payables): contas a pagar, **fluxo de caixa**, Fechamento de Pagamentos". 📖 `gestao_custos_views.py:1315-1317` (docstring de `migrar_contas_pagar`, rota alcançável por botão vivo em `templates/custos/gestao.html:21-26`): "Migra registros ContaPagar PENDENTE/PARCIAL para GestaoCustoPai. Registros já PAGO são mantidos em ContaPagar como histórico" — e ela **não aposenta** a ContaPagar clonada | `compras_views.py:250-255` × `gestao_custos_views.py:1315-1420` | É a matéria-prima da decisão **D-B5.1**. O que vai ao humano não é pergunta virgem: são duas respostas escritas em sentidos opostos que ninguém reconciliou |
| 7 | **Segundo caso de dependência de ordem na suíte, e é o mais severo.** `tests/test_e2e_jornada_proposta_cronograma_playwright.py:69` mantém `CTX = Contexto()` **mutável de módulo**, escrito por `test_01` (`:195`), `test_02` (`:211`), `test_04` (`:297`) e `test_05` (`:341-342`) e lido por 14 dos 19 testes; o fixture `page` é `scope='class'` e não carrega dado nenhum | `tests/test_e2e_jornada_..._playwright.py:69` | É `@pytest.mark.browser`: fora do `--gate`, dentro do `--suite` e alvo do `--jornada`. **Dívida ou cenário sequencial por desenho é chamada do Cássio** — ver D-B5.2 |
| 8 | 🔴 **O maior gerador de não-determinismo da suíte, e ele não é ordem de fixture.** 📖 `_rdo_after_insert_autoclone_operacional` registra `after_commit` `once=True` sobre a **scoped_session global** (`models.py:8393-8397`) e sobe um `Timer(0, ...)` que abre app_context próprio **numa thread de fundo** e chama `garantir_operacional` (`:8417`), gravando em três tabelas; a exceção é engolida por `except Exception` com `logger.warning` (`:8419-8423`). 🔬 42 arquivos de teste instanciam `RDO` | `models.py:8385-8423` | 🧮 Como o listener é sobre a sessão compartilhada e não sobre a transação que o originou, pode disparar num commit de **outro** teste. Com `pytest-xdist` isso é pior que ordem de fixture, porque produz flake e não falha reproduzível |
| 9 | **O gate passa por ordem de coleta determinística, não por desenho.** 🔬 O ambiente tem só pytest 8.4.1, pytest-html, pytest-metadata e pytest-timeout — **nem `pytest-randomly` nem `pytest-xdist`**; `pyproject.toml:80` é `--strict-markers --timeout=300` | `pyproject.toml:80` | No dia em que qualquer um dos dois entrar (paralelizar 21 minutos é a motivação óbvia), os itens 7 e 8 quebram sem que uma linha de produção mude |
| 10 | **O ponto de serialização nº3 do plano consolidado deixou de existir.** 🔬 `views/obras.py:727-770` era `calcular_progresso_real_servico`, removida em `db85ba04` ("o número era descartado"). O registro do plano (`:5168`) aponta para código que não está lá | plano `:5130-5175` | Correção de registro; entra em qualquer Task que abra a §11.3 |
| 11 | **Comentário defasado apontando para linha morta.** `crud_rdo_completo.py:250` e `:260` citam `views/rdo.py:2511` como a rota vencedora de `/rdo/salvar`; hoje é `views/rdo.py:2640` (`@main_bp.route('/rdo/salvar')`) / `:2642` (`def rdo_salvar_unificado`) | `crud_rdo_completo.py:250` | Cosmético, mas é o tipo de defasagem que fez a âncora da B5.3 andar 26 linhas |

---

## 5. Riscos e pontos de serialização

**Nenhuma das cinco Tasks gasta migração.** A 279 continua sendo a última registrada
(📖 conferido nesta redação: `migrations.py:6398-6400` traz 277, 278 e 279). A faixa
**271-276 segue reservada da Fase 6**; a **280-283 segue liberada** pelo corte da Fase 7 e
**esta rodada não a toca**. O número 270 continua queimado.

**Contra a §11.3 do plano consolidado:**

| Ponto de serialização do plano | Esta rodada |
|---|---|
| nº1 — `event_manager.py` | **Nenhuma Task da B5 abre o arquivo.** A armadilha do decorador (`@event_handler` adota a função logo abaixo) não é alcançada |
| nº2 — `migrations.py` | **Nenhuma Task da B5 abre o arquivo** para escrita. B5.4 só o lê |
| nº3 — `views/obras.py:727-770` | 🔬 **O ponto deixou de existir** (item novo nº10). B5.5 toca `views/obras.py:2818-2896`, outra região, e a função apagada não é insumo de nada |

**Colisões internas da B5:**

| Par | Colide? | Por quê |
|---|---|---|
| B5.1 × B5.5 | Não | `financeiro_service.py`/`financeiro_views.py` × `utils/cronograma_engine.py`/`views/obras.py` |
| B5.2 × todas | Não | Um arquivo de teste, nenhum código de produção |
| **B5.3 × B5.4** | **Parcialmente** | B5.3 toca `views/rdo.py`; B5.4 toca `crud_rdo_completo.py`. **Disjuntas no recorte recomendado.** Colidiriam se B5.4 adotasse a opção (A) de D-B5.4 (unificar `finalizar_rdo`), que mexe em `views/rdo.py:1571` e no pipeline de custo |
| **B5.4 × E04 (adiado)** | **Sim** | `crud_rdo_completo.py:557` é ponto catalogado do E04. → B5.4 **corrige o registro** e **não corta** `/rdo/excluir/<id>` |
| B5.3 × `rdo_editar_sistema.py` | Evitado | A chave de escopo é outra (`RDO.admin_id` × `Obra.admin_id`); trocar a guarda ali muda o conjunto de RDOs alcançáveis (risco 4 da B5.3) |

**Risco transversal, que vale para as cinco:** 🔬 nenhuma Task pode ser validada rodando o
gate inteiro em paralelo com outro agente — o `DATABASE_URL` é único e de desenvolvimento,
e o item novo nº8 (o `Timer` do listener de RDO) escreve nele **de uma thread de fundo**
durante os 21 minutos.

---

## 6. Ordem recomendada de entrega

| Ordem | Task | Por que nesta posição (razão técnica) |
|---|---|---|
| **1** | **B5.1** | É a única que é **dinheiro**, e o defeito está na árvore **ainda não deployado** (🔬 63 commits locais). Depois do deploy, toda baixa de conta a pagar persiste os cinco campos e devolve 200 dizendo "Erro". Não depende de decisão humana nenhuma no recorte entregue: as duas edições são mecânicas e o teste é isolado |
| **2** | **B5.2** | P, um arquivo de teste, zero risco de produção — e é **instrumento**. O precedente é o da §11.1 do plano consolidado ("B0 antes de tudo"): quando o custo de arrumar a medida é P, ela vem antes das correções que ela vai medir. Não gateia B5.3/B5.4/B5.5 tecnicamente; vem aqui porque é barata e a próxima Task é a mais cara em teste novo |
| **3** | **B5.3** | M. Precisa de **D-B5.3** (UX), que tem default recomendado (§8) — não trava. Vem antes da B5.4 porque a B5.4 opcional (D-B5.4 opção A) mexeria em `views/rdo.py:1571`, e mexer no arquivo depois de a B5.3 tê-lo estabilizado é mais barato que o inverso |
| **4** | **B5.4** | P no recorte recomendado. Vem depois da B5.3 pela razão acima, e porque o Step 3 (correção do registro do E04) toca o **plano consolidado**, que é a fonte de verdade — melhor editá-lo depois de a rodada ter estabilizado o que vai nele |
| **5** | **B5.5** | 🔴 Bloqueada no Step 1 por medição em produção, e é a única cujo **valor de entrega não foi medido** (🔬⚠️ dev: uma obra no banco inteiro onde a série seria calculável e diferente, com Δ máx 1,1 p.p. **na direção contrária** à do risco 6). Última por bloqueio, não por importância |

**O que pode andar em paralelo** (formato da §11.2):

| Trilha | Tasks | Por que é independente |
|---|---|---|
| **T-B5-a — financeiro** | B5.1 | `financeiro_service.py`, `financeiro_views.py`. Não colide com nada |
| **T-B5-b — suíte** | B5.2 | Um arquivo de teste |
| **T-B5-c — RDO** | B5.3 → B5.4 | `views/rdo.py` e `crud_rdo_completo.py`. **Serializadas entre si** só se D-B5.4 devolver (A) |
| **T-B5-d — cronograma** | B5.5 | `utils/cronograma_engine.py`, `views/obras.py`, `templates/obras/detalhes_obra_profissional.html` |

**T-B5-a, T-B5-b e T-B5-d podem andar em paralelo entre si e com T-B5-c.** A única
serialização real da rodada é B5.3 → B5.4, e só na hipótese (A).

---

## 7. O que esta rodada NÃO cobre

**Os quatro itens que dependem de medição em PRODUÇÃO.** Não repetidos aqui — vivem onde
estão:

| Item | Onde vive | Consulta que destrava |
|---|---|---|
| **D11 / E02** — `notificacao_cliente` | `FECHO-SESSAO-2026-08-05.md`, "🔴 A ÚNICA COISA QUE PRECISA DE AÇÃO ANTES DO DEPLOY"; plano §12 (migração 279) | `SELECT count(*) FROM notificacao_cliente;` |
| **B2.13** — invariante da folha | plano §5, Task B2.13; `FECHO-SESSAO-2026-08-05.md`, "Em aberto" | a consulta de `com_inss`/`violam` no fecho |
| **B1.8 Step 2 (q7)** — duplicatas de `RegistroPonto` | plano §4, Task B1.8; §12 ("o que NÃO vira migração") | a `q7` da B1.8 |
| **E04** — `AlocacaoEquipe.rdo_gerado_id` | plano §8.2 | contagem em produção. ⚠️ **O registro está errado: são dois pontos vivos, não três** — corrigido pela Task B5.4, Step 3 |

**Os adiados da §8.2 do plano consolidado** — A17, A12, A15, A24 completo, A16 segunda
metade, A18, A01/A04/A08/A25, E12 completo, Fase 8, Fase 9a (resto) e 9b — seguem como
estão. **Esta rodada não os toca e não os reabre.**

**As consultas de produção que ESTA rodada acrescenta** (nenhuma delas foi rodada; ⚠️ os
números que aparecem no documento são de dev):

```sql
-- B5.1 — o NameError atinge 100% das baixas? (⚠️ dev: 0 de 627)
SELECT count(*) FILTER (WHERE conta_contabil_codigo IS NOT NULL) AS com_conta,
       count(*) AS total
FROM conta_pagar;

-- B5.1 — alguém chegou a digitar a URL de pagamento à mão? (⚠️ dev: 0)
SELECT count(*), min(data_movimento), max(data_movimento)
FROM fluxo_caixa WHERE referencia_tabela = 'conta_pagar';

-- D-B5.1 — tamanho da sobreposição GCP × ContaPagar (⚠️ dev: 627/627 vindas de COMPRA)
SELECT origem_tipo, status, count(*) FROM conta_pagar GROUP BY 1, 2;

-- B5.5 Step 1 — a curva de baseline seria diferente da atual? (⚠️ dev: 82 obras, 1 com RDO)
SELECT count(DISTINCT b.obra_id)
FROM cronograma_baseline b
JOIN cronograma_baseline_item i ON i.baseline_id = b.id
JOIN tarefa_cronograma t ON t.id = i.tarefa_id
WHERE b.ativa
  AND (t.data_fim IS DISTINCT FROM i.data_fim
    OR t.data_inicio IS DISTINCT FROM i.data_inicio);

-- B5.5 Step 1 — e dessas, quantas têm curva calculável?
SELECT count(DISTINCT r.obra_id)
FROM rdo r
WHERE r.status = 'Finalizado'
  AND r.obra_id IN (/* a lista da consulta acima */);
```

---

## 8. Contradições registradas

Onde levantamento e adversário divergiram e a divergência **não** foi resolvida, ela fica
escrita. Formato da §9 do plano consolidado.

**1 — A dívida do 302 é convenção ou é autorização?**
O levantamento mede que o 302 **não é oráculo** (RDO alheio e inexistente respondem
idêntico) e conclui: "é item de CONVENÇÃO, não de segurança — o recorte não pode vendê-lo
como vazamento". O adversário concorda no eixo TENANT e derruba a conclusão pelo eixo
**OBRA**: as três rotas não chamam `pode_ver_obra`, e a rota irmã de leitura de RDO
(`cronograma_views.py:2702-2704`) chama.
**Não resolvida, e a resolução é um número que não temos:** com `escopo_obra_ativo`
desligado no tenant, 📖 `utils/autorizacao.py:90-92` e `:121-131` devolvem GESTOR para todo
mundo e o buraco **não é explorável**. **Adotado: escrever a Task pelo eixo obra e carregar
a ressalva por escrito** (B5.3). Quantos tenants em produção têm a flag ligada é pergunta
aberta, e ela decide se a B5.3 é higiene ou correção de autorização.

**2 — Qual camada é a fonte da SAÍDA de caixa?**
O levantamento manda a pergunta ao humano como escolha virgem entre (a) `GestaoCustoPai`
única fonte e (b) `ContaPagar` fonte para o que não tem GCP. O adversário mostra que ela
**já foi respondida duas vezes, em sentidos opostos**, e ninguém reconciliou
(`compras_views.py:250-255` × `gestao_custos_views.py:1315-1317` — item novo nº6).
**Adotado: a pergunta vai ao Cássio como reconciliação, não como escolha nova** (D-B5.1).
A discordância sobre *o que* está aberto fica registrada porque muda a forma da pergunta.

**3 — O valor de entrega da curva de baseline.**
O levantamento estima **M** e recomenda executar. O adversário mede que em ⚠️ dev existe
**uma** obra onde a série seria calculável e diferente, com Δ máx 1,1 p.p. **na direção
contrária** à do risco 6, e conclui que "o passo mais barato não é escrever o código — é
rodar as consultas em produção".
**Não resolvida.** **Adotado: o Step 1 da B5.5 é a medição em produção, e a Task pode
morrer nele.** A discordância é sobre "se implementar", não sobre "como" — nesse ponto os
dois concordam (terceira série derivada na leitura, sem migração).

**4 — "A dívida do `rdo_crud` foi enunciada errada no plano".**
Levantamento afirma; adversário derruba mostrando que o corpo do plano (`:2750-2774`)
afirma só o que é verdade e que `:2771` é **pergunta**.
**Resolvido a favor do adversário**, e registrado porque o exagero estava no cabeçalho de
um levantamento inteiro. O texto atacável é o título comprimido da célula da §8.3.

**5 — O que se perde ao criar o operacional no fixture `ctx`.**
Levantamento: "o teste passa a não testar nada". Adversário: há cobertura independente e
ordem-independente em `tests/test_orcamento_operacional.py:301`, então o que se perde é a
prova do fio **rota → serviço**.
**Resolvido a favor do adversário.** A recomendação (fixture intermediário) **não muda** —
muda a severidade, e com ela o fato de que a B5.2 é higiene barata e não decisão urgente.

---

## 9. Perguntas para o Cássio

Só as que **mudam o recorte**. Cada uma diz o que trava e qual é o default se a resposta
não vier.

**D-B5.1 — Qual camada é a fonte da SAÍDA de caixa: `ContaPagar` ou `GestaoCustoPai`?**
✅ **DECIDIDA em 06/08 pelo Cássio: (a), o default** — junto com a D-B5.6(A) e o corte
da B5.5, na mesma decisão que descartou as consultas de produção ("sigo sem elas,
confio no que fez"). Registrada aqui como decisão, não como default assumido — é o
formato do precedente E02 de 05/08. A B5.7 executa sobre ela.
Trava: o `FluxoCaixa` do lado pagar (a dívida como o fecho a enunciou).
Não é pergunta nova — 📖 `compras_views.py:250-255` diz por escrito que **ContaPagar** é a
camada do fluxo de caixa, e 📖 `gestao_custos_views.py:1315-1317` (rota com botão vivo em
`templates/custos/gestao.html:21-26`) migra ContaPagar PENDENTE/PARCIAL **para**
GestaoCustoPai sem aposentar a original. As duas decisões estão escritas e se contradizem;
o código faz uma terceira coisa (🔬 `ContaPagar` não aparece uma única vez em
`calcular_fluxo_caixa`). ⚠️ dev, 627 de 627 `ContaPagar` vêm de `COMPRA`, isto é, têm gêmeo
GCP: **a sobreposição é 100%**.
**Default se não vier:** manter (a) — `GestaoCustoPai` é a única fonte, e a dívida se
resolve **apagando** o escritor de `financeiro_views.py:407-418` em vez de completá-lo.
Razão do default: (b) por omissão é a mesma despesa simultaneamente prevista e realizada, e
é exatamente o que a B3.7/B3.8 gastaram dois commits evitando do outro lado.

**D-B5.3 — 404 na tela HTML `/rdo/<id>`, ou só nos consumidores programáticos?**
Trava: o Step 3 da B5.3.
🔬 Hoje o usuário cai na consolidada com flash "RDO não encontrado."; com 404 cai em
`templates/error.html` (`error_handlers.py:49-54`), sem flash e sem caminho de volta. 🔬 A
lente 3 provou que **nenhum JS quebra** e que o PDF é `<a href>`.
**Default se não vier:** 404 em todas, inclusive na tela — é o que
`cronograma_views.py:2700-2704` e `views/obras.py:1541` (`@obra_required()`) já fazem, e
duas convenções na mesma família custam mais que uma tela feia.

**D-B5.4 — `finalizar_rdo`: unificar ou manter os dois caminhos?**
Trava: o tamanho da B5.4 e a serialização com a B5.3.
Existem dois: `POST /rdo/<id>/finalizar` (`views/rdo.py:1571`, o único que a UI chama, via
`templates/rdo/visualizar_rdo_moderno.html:1085`) e `POST /rdo/finalizar/<id>`
(`crud_rdo_completo.py:573`, que só testes chamam e que o plano `:47` acusa de **não** gerar
`RDOCustoDiario` nem `GestaoCustoFilho` — os R$ 124,00/mensalista/dia).
⚠️ **Correção do adversário:** a opção (A) **não é M**. Ela toca o pipeline de custo,
reescreve **quatro** `url_for` internos (`crud_rdo_completo.py:587`, `:595`, `:645`, `:651`)
e obriga a reescrever `tests/test_arreio_custo_rdo_rotas.py`, que é o **arreio de dinheiro
do A05/A19** e cujo helper `_via_finalizar` (`:121-129`) existe para medir justamente essa
rota. **Arreio de custo reescrito no mesmo commit que muda o custo é o instrumento medindo
o vazio.** Isso é G.
**Default se não vier:** (B) — manter as duas e **não** tocar no custo nesta rodada. A B5.4
fica no recorte P (as duas rotas de API mortas + correção do registro do E04).

**D-B5.5a/b/c — a curva de baseline.**
Trava: os Steps 4 e 5 da B5.5, e só depois do Step 1 (produção).
(a) **Peso**: a série de baseline pondera pelo `duracao_dias` **congelado** (honesto, mas
denominador diferente da curva atual) ou pelo peso **vivo**, variando só as datas (linhas
comparáveis ponto a ponto, mas a "congelada" se mexe quando alguém edita quantitativo)?
📖 `CronogramaBaselineItem` não guarda `quantidade_total`; `CronogramaTarefaSnapshot`
guarda (`models.py:6432-6474`).
(b) **Escopo**: só a Curva S, ou também o PV do EVM (`services/cronograma_fisico_financeiro.py:337`
faseia por datas vivas)? ⚠️ **A justificativa original desta pergunta caiu** — 🔬 o SPI/SV
**não é exibido a ninguém**. A pergunta sobrevive como "vale pagar por um número que hoje
ninguém vê?".
(c) **Bordas**: tarefa criada depois da baseline (🔬⚠️ dev: 645) conta como 0% ou fica fora
do agregado? Obra sem baseline mas com curva calculável (🔬⚠️ dev: 95) — a linha não aparece
com rótulo, ou o card oferece o botão de congelar? (📖 congelar é outra página e outro
blueprint: `POST /cronograma/obra/<id>/baseline`, `cronograma_views.py:2183`.)
**Default se não vier:** peso **vivo** (só as datas variam), escopo **só a Curva S**, e
borda por **exclusão do agregado** com rótulo "sem linha de base".

**D-B5.2 — a jornada Playwright é dívida ou desenho?**
Trava: se o item novo nº7 vira Task na próxima rodada.
📖 19 testes encadeados por um `CTX` global mutável; `@pytest.mark.browser`, fora do
`--gate`. Consertar de verdade é reescrever os 19 com fixtures encadeados; documentar é um
comentário no topo dizendo "este arquivo só roda inteiro, nunca com `-k`".
**Default se não vier:** documentar. Razão: 🔬 sem `pytest-randomly`/`pytest-xdist`
instalados, a ordem é determinística e o custo de reescrever 19 testes de browser não se
paga hoje. **Mas se a paralelização do gate entrar na mesa, o default vira o oposto** — e
aí o item novo nº8 (o `Timer` do listener de RDO) é mais urgente que este.

---

## 10. Apenso de 2026-08-06 — recortes B5.6 e B5.7 (os dois itens de dinheiro)

Este apenso é o produto do **WF-2 `varredura-b5-dinheiro`** (§5 do plano de execução):
dois levantamentos com as cinco lentes e dois adversários, um par por item, sobre os
**itens novos nº1 a nº5 da §4** — a catraca de `banco.saldo_atual` (nº1), a discordância
entre os dois caminhos de pagamento (nº2), o escritor morto de `views/vehicles.py` (nº3),
os leitores órfãos de `'registro_ponto'` (nº4) e a exclusão de gêmeos que existe na tela e
não no fluxo (nº5). Mesmo método da rodada, mesmo formato de recorte. **Escrito contra a
árvore com a Fase 1 já COMMITADA** (B5.1 `0bc62449` … B5.4 `e3ca534c`) — as âncoras abaixo
são da árvore atual, e onde divergem das da §4 a divergência está anotada. **Toda medida
⚠️ dev deste apenso é de 2026-08-06** e envelhece: a própria suíte da B5.1 moveu o banco
de dev no meio da varredura (ver abaixo).

**A má notícia primeiro — o que os adversários derrubaram ou corrigiram.** Os dois itens
sobreviveram (`confirmado_com_correcoes` nos dois), mas o placar contra o levantamento é
pesado:

| O que caiu | Onde estava | O que ficou no lugar |
|---|---|---|
| **As medidas ⚠️ dev centrais da B5.6 ficaram irreprodutíveis no mesmo dia.** "0 ContaPagar PAGO, 42 bancos com drift zero" | levantamento B5.6 | 🔬⚠️ dev (refutação, 06/08): a suíte da B5.1 rodou contra o banco único e deixou resíduo — **25 ContaPagar PAGO** e **5 bancos em drift** (`'Banco B5'`, 5000→4000, casando com `tests/test_b5_baixa_conta_pagar.py:187-201`). Ironia útil: **o resíduo é a catraca demonstrada ao vivo** — 5×R$ 1.000 debitados por teste e jamais devolvidos. A substância ("nenhuma operação real moveu saldo em dev") sobrevive; os números escritos sem data, não |
| **"Achado novo: o delete de LC em `estornar_gcp` é no-op"** | levantamento B5.6 | Correto e **não é novo**: 📖 `docs/estudo-fluxo/analises-2026-07-30.json:1529` já o registrava verbatim, e `:1556` já propunha a correção exata (gravar os LC V2 com `origem='GESTAO_CUSTO_PAI'`/`origem_id=gcp.id`). O levantamento citou `:1532` e `:1559` do mesmo arquivo e não viu `:1529`, três linhas acima. **Proposta por escrito desde 30/07 e esquecida uma vez** — este apenso a põe em Step para não esquecer duas |
| **"`estornar_conta` casa com o escritor"** — apresentado como o lado são | levantamento B5.6 | Meia-verdade: 📖 `baixar_pagamento` cria **dois** LC potenciais — o `FINANCEIRO_PAGAR` (gated por `conta_contabil_codigo`, ⚠️ dev **0 de 652** contas o têm) e o `V2_AUTO` de `financeiro_service.py:196-217`, gravado com `origem_id=None`. `estornar_conta` apaga **só o primeiro**. No parque real (627/627 COMPRA), o único LC que uma baixa de fato gera é **exatamente o que o estorno não apaga**: estornar+re-pagar **dobra a contabilidade** |
| **Duas medidas centrais da B5.7 vieram de join SEM guard de tenant** | levantamento B5.7 | 🔬⚠️ dev (refutação): "621 gêmeos / R$ 503.250" são **580 / R$ 490.950** com `cp.admin_id = p.admin_id` — 41 "gêmeos" casavam com ContaPagar de **outro** tenant. E o "GCP 999 com 168 FC realizados sob pai PENDENTE" **não existe**: as 168 linhas pertencem a **76 admin_ids diferentes** e são órfãs (nenhum desses tenants tem GCP 999). A armadilha é a da própria pergunta aberta do levantamento — a chave canônica do gêmeo |
| **A âncora da hipótese C "os campos já existem"** | levantamento B5.6 | Existem no esquema e **não no dado**: 🔬⚠️ dev `data_saldo_inicial` é NULL em **47 de 47** `banco_empresa`. A borda "(5) banco sem data" não é exceção — é o **caso universal**. O G da hipótese C está subestimado até no G |
| **O inventário de gêmeos tinha DUAS famílias** | levantamento B5.7 | São **três**, e a terceira está a um clique: 📖 `migrar_contas_pagar` (`gestao_custos_views.py:1311-1420`, botão vivo em `templates/custos/gestao.html:21-26`, cujo `confirm` promete "Esta ação é segura e pode ser repetida") clona toda CP PENDENTE/PARCIAL num GCP com filho `origem_tabela='conta_pagar'` — e o guard de idempotência (`:1335-1341`) **não vê a gêmea `'pedido_compra'`**: um clique num tenant com as 627 CPs de compra cria a **segunda** GCP por parcela |
| **Âncoras pré-B5.1 na B5.7** | levantamento B5.7 | O commit `0bc62449` empurrou `financeiro_views.py` ~32 linhas abaixo de `:379`. Posições atuais (📖 conferidas nesta redação): checkbox `:423`, escritor FC `'conta_pagar'` `:434-452` (`FluxoCaixa(` `:439`, `referencia_tabela` `:448`), ENTRADA `:746`, lançamento manual `:886` |

O que os adversários **tentaram e falhou** também fica registrado: ressuscitar a página
órfã `pagar_conta.html` por link (zero href/fetch — só URL digitada); achar um restaurador
de `saldo_atual` (não há); achar um escritor de FC `'registro_ponto'` por homonímia (as
ocorrências de `event_manager.py:327/:396` são `GestaoCustoFilho.origem_tabela`, outra
tabela); e derrubar a hipótese D — que ficou **mais** morta: os 25 POSTs reais da suíte
B5.1 passaram pela rota viva e `fluxo_caixa` `'conta_pagar'` segue com **0 linhas**.

---

### Task B5.6: o estorno devolve o débito bancário — a catraca de `banco.saldo_atual`

**Status: ✅ entregue em `08f2ee88`, sob a D-B5.6=(A) decidida em 06/08; apertada em
`f69cb359` pela revisão WF-3.** Migração 280 gasta. Desvios que a revisão registrou e o
commit de aperto resolveu: (i) a recusa de troca de caminho bancário estava na VIEW e o
recorte a mandava para `baixar_pagamento` — agora está nos dois (flash amigável na view,
raise no service); (ii) o gatilho era `status == 'PARCIAL'` e a janela real do legado
(conta meio-paga sem banco, status NULL/PENDENTE) passava — virou `valor_pago > 0`, com
o caso 8 e mutação própria; (iii) a lista **Files** não declarava `pagar_conta` nem
`gestao_custos_views.py` (os carimbos), tocados pelo commit — registrado aqui. Red-first (casos 1/3/4/5/6/7 vermelhos; o 2 já passava — nada a inventar) e três
mutações cirúrgicas: crédito desligado derruba só 1/4, carimbo removido derruba só o 5,
delete de FC removido derruba só o 6. Um desvio a mais, para menos: o caso 6 descobriu
que **o pagamento de GCP nunca gerou LC** — os dois caminhos passam `'DESPESA_GERAL'`,
que não existe no `MAPEAMENTO_CONTABIL` (`contabilidade_utils.py:1536-1543`), então o
"delete no-op" do estorno era **duplamente** no-op. Mapear é escolher conta contábil =
decisão de contador (lição do A03) — NÃO mapeado; o carimbo de origem deixa o caminho
pronto e o teste vigia a premissa (se alguém mapear, o caso 6 avisa). **Item novo para
a fila do contador: mapear `DESPESA_GERAL`, ou trocar o `tipo_operacao` dos dois
caminhos de GCP por um mapeado.**

~~🔴 **BLOQUEADA no Step 0: decisão D-B5.6.** É o caso F2.3 do plano de execução — a solução
exige migração (A) ou redesenho (C), e as duas são decisão do Cássio. A Task está escrita
**sob o default (A)**; se a resposta for (C), ela reabre como redesenho G.~~

**Files** (sob o default A): Modify `migrations.py` — **uma** migração, número alocado no
Step 1 (faixa 280-283; ver risco 4); Modify `models.py` — `ContaPagar` (`:2412-2463`)
ganha `banco_id` nullable; Modify `financeiro_service.py` — `baixar_pagamento` grava
`conta.banco_id`; Modify `financeiro_views.py` — `estornar_conta` (`:296-331`) e
`estornar_gcp` (`:334-370`); Modify `contabilidade_utils.py` — origem dos LC V2
(`:1721-1722`); Create `tests/test_b5_estorno_devolve_banco.py`

**A pergunta central, e a resposta é NÃO.** Quando uma `ContaPagar` é baixada com
`banco_id`, esse banco **não fica persistido em nenhum lugar recuperável**. 📖 Conferido
nesta redação: `ContaPagar` (`models.py:2412-2463`) e `ContaReceber` (`:2464-2508`) não
têm coluna `banco_id` — a baixa persiste só `forma_pagamento` (string,
`financeiro_service.py:100`); 🔬⚠️ dev `information_schema.columns`: `conta_pagar` e
`conta_receber` sem `banco_id`, `lancamento_contabil`/`partida_contabil` sem coluna de
banco — só `fluxo_caixa` tem. As três vias teóricas de recuperação estão mortas: (1) o FC
`'conta_pagar'` com `banco_id` só nasce pelo escritor de `financeiro_views.py:434-452`,
gated por checkbox que **o modal vivo não envia** (📖
`templates/financeiro/contas_pagar.html:402-443` — banco opcional, primeira opção "Sem
vínculo bancário", sem `criar_fluxo_caixa`), alcançável apenas pela página órfã
`pagar_conta.html:94` — ⚠️ dev **0 linhas**, e o default D-B5.1 **remove** esse escritor;
(2) o LC `FINANCEIRO_PAGAR` não tem coluna de banco e ⚠️ dev tem 0 linhas dessa origem;
(3) `baixar_pagamento` não loga o banco no sucesso. **Consequência: estorno automático do
débito é impossível sem mudança de esquema (A) ou de fonte (C)** — para o histórico e para
o futuro.

**A catraca.** 📖 Conferido nesta redação: `banco.saldo_atual -= valor_pago`
(`financeiro_service.py:114`, sob `if banco_id:`/`if banco:`) é o único débito do sistema;
`+= valor_recebido` (`:345`) o único crédito; criação de banco espelha `saldo_inicial`
(`financeiro_service.py:945`, `financeiro_views.py:992`) e **não existe rota de edição que
reescreva saldo**. `estornar_conta` (`financeiro_views.py:296-331`) devolve
`valor_pago`/saldo/status e apaga LC — **não toca `saldo_atual`**; `estornar_gcp`
(`:334-370`) idem (correto ali: pagar GCP nunca debita — é o item nº2). E `saldo_inicial`
do fluxo de caixa é literalmente `sum(banco.saldo_atual)` dos ativos
(`financeiro_service.py:491`; segundo leitor: KPI `:881`; terceiro: `listar_bancos`
`financeiro_views.py:952`). O flash da guarda B5.1, já commitado, **manda o operador ao
estorno** — o caminho sancionado de refazer carrega este defeito dentro.

**O estorno está mais quebrado do que o item nº1 enuncia** — e é o que o adversário
acrescentou ao recorte:
1. **O delete de LC em `estornar_gcp` é no-op por construção**: busca
   `origem='GESTAO_CUSTO_PAI'` e o escritor real grava `origem='V2_AUTO'`,
   `origem_id=None` (📖 `contabilidade_utils.py:1721-1722`; 🔬⚠️ dev: 0 LC
   `GESTAO_CUSTO_PAI`, 548 `V2_AUTO` todos com `origem_id` NULL). Prior art:
   `analises-2026-07-30.json:1529` e a correção em `:1556`.
2. **`estornar_conta` tem o vazamento simétrico**: não apaga o LC `V2_AUTO` que a baixa de
   uma conta COMPRA gera (`financeiro_service.py:196-217`) — no parque real é o **único**
   LC gerado, e estornar+re-pagar dobra o `pagamento_fornecedor` na contabilidade.
3. **`estornar_gcp` vaza o FluxoCaixa SAIDA** (não apaga; re-pagar cria segundo FC =
   saída dobrada nos buckets) e não limpa `pai.fluxo_caixa_id`/`conta_bancaria`.
4. **Não existe estorno de recebimento** (🔬 grep `estorn` fora de archive/tests: só
   `estornar_conta`, `estornar_gcp` e `contabilidade.estornar_lancamento`): a catraca é
   assimétrica nos dois sentidos — pagar tem estorno que vaza o débito; receber não tem
   estorno nenhum (⚠️ dev 06/08: 194 CRs liquidadas sem reversão pela UI). E 🔬 **zero
   testes citam `estornar`**.

**As quatro hipóteses, atacadas uma a uma:**

| Hipótese | Veredito | O essencial |
|---|---|---|
| **(A)** persistir `banco_id` na `ContaPagar`; estorno credita pelo campo | **Sobrevive — é a menor correção correta.** Custo M | Borda real: baixas **parciais** em bancos diferentes (coluna única lembra o último; estorno é tudo-ou-nada). Histórico pré-migração fica NULL — estorno dessas avisa e não credita (não pior que hoje). O par obrigatório que o adversário acrescentou: o estorno credita **e LIMPA** o campo, senão um segundo ciclo credita banco que não foi debitado |
| **(B)** operador informa o banco no estorno | **Descartada com razão escrita** | Inventa crédito sem rastro (conta paga SEM banco estornada COM banco infla o fluxo); não há contra o que validar — nada foi persistido; e o modal de estorno é **compartilhado** conta/GCP (`contas_pagar.html:449-465`, um só `formEstorno`) — no ramo GCP creditaria débito que nunca houve |
| **(C)** `saldo_atual` vira **derivado** (`saldo_inicial` + Σ FluxoCaixa por banco) | **Sobrevive como destino, não como conserto.** Custo G, **subestimado** | Mata catraca e discordância (nº1+nº2) por construção, e tem prior art (`:1559`). Mas: a âncora (`data_saldo_inicial`, `models.py:2520`) é NULL em **47/47** bancos — exige backfill/convenção universal; o modal vivo de pagar não gera FC e o import de CR gera FC **sem** `banco_id` (`importacao_excel.py:2487-2501`) — o derivado nasceria furado; os estornos teriam de reverter FC (hoje vazam); e 📖 `editar_fluxo_caixa` (`financeiro_views.py:911-940`, âncora pré-B5.1 `:911` ≈ atual `:943`) edita **qualquer** FC inline — sob C, uma edição reescreve o saldo do banco em silêncio |
| **(D)** FluxoCaixa como fonte da reversão (como está) | **Morta por quatro vias** | ⚠️ dev 0 linhas `'conta_pagar'` (re-medido 06/08, **depois** dos 25 POSTs reais da suíte B5.1 — demonstração empírica); escritor só alcançável pela página órfã; D-B5.1 o remove; e mesmo no lado receber, onde o FC existe, `banco_id` é NULL em 100% das linhas de `conta_receber` |

**D-B5.6 — O estorno de conta a pagar passa a devolver o débito bancário por qual
mecanismo?** (formato da §9; **continuação da fila de decisões**)
✅ **DECIDIDA em 06/08 pelo Cássio: (A), o default** — na mesma decisão da D-B5.1 (ver
lá). A migração **280 foi alocada e GASTA** (`08f2ee88`); a corrida de três se resolveu
por desistência dos concorrentes, que dependiam das consultas descartadas. Entregue —
ver o Status da Task B5.6.
Trava: os Steps 1-8 desta Task.
**(A)** `ContaPagar` ganha `banco_id` persistido na baixa e o estorno credita e limpa pelo
campo — **uma migração** (número da faixa 280-283, alocado por escrito), custo M, com a
borda das parciais multi-banco documentada. **(C)** `banco.saldo_atual` deixa de ser
contador mutável e vira derivado de `saldo_inicial` + Σ FluxoCaixa por banco — redesenho G
que também mata o item nº2, já proposto em 30/07, mas que muda o número exibido em todos
os leitores e exige antes: backfill de `data_saldo_inicial` (NULL em 47/47), FC em toda
baixa com banco, estornos que revertem FC e imutabilidade do FC referenciado na edição
inline. (B) e (D) estão descartadas acima, com razão escrita.
**Default se não vier: (A).** Razão: é a menor correção correta; a âncora do derivado de C
**não existe em nenhum banco do parque**; e A não fecha a porta para C — a coluna nova
vira insumo do derivado se C vier depois. **A consulta de produção que dimensiona o dano**
(se produção ≈ dev — 0 PAGO real, drift zero —, a B5.6 é prevenção pré-deploy, não
incidente): `SELECT status, count(*) FROM conta_pagar GROUP BY 1;` ·
`SELECT count(*), count(banco_id) FROM fluxo_caixa WHERE referencia_tabela='conta_pagar';`
· `SELECT count(*), count(*) FILTER (WHERE saldo_atual IS DISTINCT FROM saldo_inicial)
FROM banco_empresa;` — entram no pacote F0.1.

**Comportamento novo (sob o default A).**
1. Migração: coluna `banco_id` nullable em `conta_pagar` (histórico fica NULL — e o
   estorno **avisa** quando `valor_pago > 0` e `banco_id` NULL, em vez de creditar).
2. `baixar_pagamento` grava `conta.banco_id` quando debita; em baixa **parcial**, grava no
   primeiro pagamento e **recusa troca de banco** em conta PARCIAL (a mitigação honesta da
   borda multi-banco — a alternativa, aproximar pelo último banco, só por decisão escrita).
3. `estornar_conta` credita `banco.saldo_atual += valor_pago` pelo campo **e limpa
   `conta.banco_id`** no mesmo movimento.
4. Os LC V2 do pagamento passam a nascer rastreáveis (`origem`/`origem_id` reais — a
   correção de `analises-2026-07-30.json:1556`), e os dois estornos apagam o que a baixa
   criou: `estornar_conta` apaga também o LC do pagamento; `estornar_gcp` passa a ter
   delete que **casa**, apaga/compensa o FC SAIDA vinculado e limpa
   `pai.fluxo_caixa_id`/`conta_bancaria`.

**Teste que prova.** Tenant próprio com `BancoEmpresa` de saldo conhecido; padrão de login
da B5.1 (`tests/test_b5_baixa_conta_pagar.py`).

| # | Ação | Asserção |
|---|---|---|
| 1 | baixa de R$ 1.000 com `banco_id` → estorno | `saldo_atual` volta ao valor inicial; `conta.banco_id` limpo; status PENDENTE |
| 2 | baixa **sem** banco → estorno | nenhum crédito inventado; saldo dos bancos intacto |
| 3 | conta legada PAGO com `banco_id` NULL (forma do import, `importacao_excel.py:2414-2430`) → estorno | crédito **zero** + aviso explícito — é o caso que um teste só-caminho-feliz deixaria verde e oco |
| 4 | estorno → re-baixa com **outro** banco → 2º estorno | o 2º estorno credita o banco da 2ª rodada (prova da limpeza do campo) |
| 5 | baixa de conta COMPRA (admin V2) → estorno → re-baixa | `LancamentoContabil` **não dobra** — o LC do pagamento foi apagado no estorno |
| 6 | pagar GCP com FC → `estornar_gcp` | FC SAIDA removido/compensado; `pai.fluxo_caixa_id` e `conta_bancaria` limpos; LC do GCP apagado (delete agora casa); `saldo_atual` **intocado** (GCP nunca debitou) |
| 7 | baixa parcial de 400 no banco A → tentativa de parcial de 600 no banco B | recusa com flash; mesma conta, parcial de 600 no banco A, completa PAGO |

**Riscos → mitigação.**
1. **Crédito sem limpeza é catraca invertida.** Se `banco_id` sobrevive ao estorno e a
   re-baixa vem sem banco, um segundo estorno credita banco não debitado. → caso 4 é o cão
   de guarda; crédito e limpeza no mesmo Step.
2. **O verde-e-oco espreita no caso NULL.** Teste que só cubra baixa-com-banco→estorno
   fica verde sem provar o aviso da conta legada/importada. → caso 3 obrigatório.
3. **Parciais multi-banco.** O estorno é tudo-ou-nada (zera `valor_pago` inteiro); coluna
   única + troca de banco em parcial = crédito total no banco errado. → recusa de troca
   (caso 7); aceitar a aproximação exige decisão escrita na D-B5.6.
4. **A migração é recurso disputado e o 280 é corrida de TRÊS.** §12 do plano consolidado
   já promete o 280 a dois pretendentes condicionais (índice único de `RegistroPonto` pós-q7;
   A24a pós-B2.13). → alocar o número **por escrito no Step 1**, antes de tocar
   `migrations.py` (§11.3 nº2) — "primeira da faixa liberada" é verdade, "estante vazia" não.
5. **O modal de estorno é compartilhado conta/GCP** (`contas_pagar.html:449-465`).
   Qualquer texto/campo novo tem de existir só no ramo conta — o GCP nunca debitou.
6. **As medidas ⚠️ dev envelhecem a cada rodada de teste** contra o banco único — a B5.1
   moveu 627→652 CPs no mesmo dia. → toda medida deste apenso carrega data; recorte futuro
   que cite "drift zero" sem data afirma coisa falsa.

**O que esta Task NÃO faz.** (i) **Estorno de recebimento** — não existe hoje e não nasce
aqui; ⚠️ dev 06/08: 194 CRs liquidadas sem reversão pela UI. Item próprio; se vier e a
resposta for A, `ContaReceber` ganha `banco_id` junto — quem o criar herda a mesma
armadilha de origem dupla de LC do lado pagar (`FINANCEIRO_RECEBER` +
`gerar_lancamento_contabil_automatico`). (ii) A hipótese C — fica escrita como destino
possível, não é iniciada. (iii) A dupla contagem do fluxo — é a B5.7.

- [x] **Step 0:** 🔴 **decisão D-B5.6** (acima, com default A) + consultas de produção no pacote F0.1. Se (C), a Task reabre como redesenho G e **para aqui**
- [x] **Step 1:** alocar o número da migração **por escrito** (faixa 280-283; corrida de três — risco 4)
- [x] **Step 2:** escrever o teste e ver vermelhos os casos 1 (saldo não volta), 4, 5 (LC dobra) e 6 (FC vaza; delete no-op)
- [x] **Step 3:** migração + coluna `banco_id` em `ContaPagar`
- [x] **Step 4:** `baixar_pagamento` grava `conta.banco_id`; regra da parcial (caso 7)
- [x] **Step 5:** `estornar_conta` credita **e limpa**; aviso no caso NULL
- [x] **Step 6:** origem rastreável dos LC V2 (`:1556` do prior art) + deletes que casam nos dois estornos + FC do GCP removido e ponteiros limpos
- [x] **Step 7:** sete casos verdes; mutação: desfazer o Step 5 derruba só 1/4; desfazer o Step 6 derruba só 5/6
- [x] **Step 8:** commit — `fix(financeiro): estorno devolve o debito bancario e apaga o que a baixa criou`

**Esforço: M** (sob A; sob C é G e reabre). **Migração: SIM — uma**, número alocado no
Step 1 (280-283; gasta: **280**, `08f2ee88`).

> **Nota — o que o adversário corrigiu neste levantamento.** (a) As medidas ⚠️ dev centrais
> ficaram irreprodutíveis no mesmo dia (25 PAGO e 5 bancos em drift por resíduo da suíte
> B5.1 — que é a catraca demonstrada ao vivo). (b) O "achado novo" do LC no-op já estava
> registrado verbatim em 30/07 (`analises-2026-07-30.json:1529`), com a correção proposta
> em `:1556` — lida e não vista pelo levantamento, três linhas acima do que ele citou.
> (c) `estornar_conta` não é o lado são: vaza o LC `V2_AUTO` — no parque real, o único LC
> que a baixa gera. (d) A hipótese C está mais cara que o G da letra: `data_saldo_inicial`
> NULL em 47/47 e a edição inline de FC reescreveria saldo em silêncio. (e) Na hipótese A
> faltava o par crédito+limpeza do campo. (f) A migração 280 tem três pretendentes, não
> estante vazia. (g) Pergunta aberta 7 do levantamento **fechada**: o flash commitado da
> guarda B5.1 (📖 `financeiro_views.py:396-398`, `:409-410`) não promete devolução do
> banco — o texto está correto.

---

### Task B5.7: a exclusão de gêmeos chega ao fluxo de caixa; os escritores/leitores mortos saem

**Status: ✅ entregue em `3288ba84` (fix) + `b5472260` (chore), sob a D-B5.1=(a)
decidida em 06/08 e a D-B5.7 executada pelo default (2); completada em `f69cb359` pela
revisão WF-3** — que pegou DOIS itens do recorte prometidos e não entregues pelos
commits originais: o escritor de FC `'conta_pagar'` (a premissa da D-B5.1(a), "sai em
vez de ser completado") continuava vivo, e a anotação de revogação do comentário
Task #11 em `compras_views.py` não existia. Os dois saíram/entraram no aperto; o guard
do migrar foi simplificado (CP de COMPRA nunca clona, inclusive com `origem_id` NULL) e
a asserção de buckets do caso 1, que era VÁCUA (chave inexistente), foi consertada.

⚠️ **Âncoras deste apenso**: foram medidas na árvore `a69b7464` e os commits da própria
execução as deslocaram (o transversal do WF-3 listou o mapa completo; ex.: o escritor
FC `:434-452` → `:505-523` antes de ser removido). Quem retomar confere contra a árvore
corrente — os Status carregam os commits que servem de âncora estável. Red-first nos casos 1/4/5/6
e três mutações medidas, cada uma derrubando só os seus casos. Registro de método que
vale a pena: o caso 5 nasceu **verde e oco** na primeira forma — a CP de teste não
tinha `obra_id`, o clone falhava no check da Fase 4 (outro motivo que não o guard) e a
contagem ficava igual por acidente. Detectado porque o vermelho esperado não veio;
consertado antes de o teste valer. É a mesma classe de vácuo que a B5.2 fechou, agora
do lado de quem escreve o teste.

**Esta Task está escrita SOB o default (a) da D-B5.1** — `GestaoCustoPai` é a única fonte
da SAÍDA e o escritor de FC `'conta_pagar'` (`financeiro_views.py:434-452`, âncora da §4
`:407-418` **pré-B5.1**) **sai** em vez de ser completado. Se a resposta for **(b)**, esta
Task reabre como o recorte da F2 inteiro (hipótese H3, custo G): previstas de compra
passam a vir de `ContaPagar`, o escritor ganha os campos que faltam (a começar por
`obra_id`) e o serviço passa a ler três fontes de saída.

**Files:** Modify `financeiro_service.py` — `calcular_fluxo_caixa` (`:471-758`: previstas
`:519-545`, fallback PAGO `:569-580` e os detalhes previstos que alimentam
`agregar_fluxo_mensal` `:764-786`); Modify `gestao_custos_views.py` — guard de
idempotência de `migrar_contas_pagar` (`:1335-1341`); Modify `views/vehicles.py` — remoção
da rota `main.novo_custo_veiculo` **inteira** (`:826-946`); Modify `ponto_views.py` —
blocos `:849-863` e `:932-940`; Create `tests/test_b5_fluxo_gemeos_e_orfaos.py`

**O mecanismo, corrigido contra o enunciado da §4.** O caminho **vivo** de pagamento de
GCP não é o `pagar` de `:872+` (legado por comentário próprio, 📖
`gestao_custos_views.py:865-871`, zero referências em template/JS) e sim **`autorizar`**
(`:732-870`, alcançado por path literal `` `/gestao-custos/${paiId}/autorizar` `` em
`templates/custos/gestao.html:647` — lente TEMPLATE): grava FC SAIDA `'gestao_custo_pai'`
com `banco_id` (📖 `:812-825`, banco obrigatório só se `criar_fc`, `:805-808`) e **nunca
toca `banco.saldo_atual`** (🔬 grep no arquivo: zero). `baixar_pagamento` faz o oposto:
debita `saldo_atual` quando há banco (`financeiro_service.py:114`) e não grava FC. E as
linhas FC `'conta_pagar'` são **invisíveis** a `calcular_fluxo_caixa` (`pr_query` filtra
`'gestao_custo_pai'`, `fd_query` filtra `referencia_tabela IS NULL` — um escritor sem
nenhum leitor, em lugar nenhum). **Os dois caminhos erram em direções opostas e o sinal
depende da tela**: pagar a gêmea CP com banco debita o `saldo_inicial` do fluxo E mantém a
prevista do GCP para sempre (dupla subtração de `saldo_final :594`); pagar via GCP tira a
prevista e mostra realizado sem nunca debitar o banco.

**A exclusão de gêmeos existe numa tela e não no fluxo** (item nº5, confirmado intacto):
📖 `financeiro_views.py:190-217` — subquery dos filhos `origem_tabela='pedido_compra'`
aplicada em `:207` e `:216`, **só em `listar_contas_pagar`**. `calcular_fluxo_caixa` não
tem equivalente em nenhuma das pontas. Tamanho, com a medida **corrigida pelo adversário**
(join com guard de tenant): ⚠️ dev 06/08 — **580 GCPs de compra abertos com gêmea CP no
mesmo tenant, R$ 490.950** entrando em `saidas_previstas` (sem o guard, 621/R$ 503.250 —
os 41 extras casavam com CP de outro tenant); na janela default do fluxo (mês corrente):
**341 GCPs, R$ 59.625** (reproduzida exata pela refutação); universo das previstas: 5.081
abertos / R$ 2.046.609 — os gêmeos são **24%** do valor, e 4.202 têm `saldo` NULL (o
fallback é parte obrigatória de qualquer exclusão).

**As três famílias de gêmeos** (o inventário que o levantamento entregou com duas):
1. **`pedido_compra`** — 📖 `compras_views.py:206-276` cria GCP + GCF + ContaPagar para o
   mesmo pedido; ⚠️ dev 627 CPs COMPRA. É a família da exclusão desta Task.
2. **Reembolso do import** — 📖 `importacao_excel.py:2413-2431` cria CP gêmea com
   `origem_tipo='gestao_custo_pai'`, fora do filtro da tela. Registrada; sem regra ainda.
3. **Clones de `migrar_contas_pagar`** — a mais perigosa, a um clique (achado do
   adversário): o guard de idempotência (`:1335-1341`) só olha `origem_tabela='conta_pagar'`
   e **não vê a gêmea `'pedido_compra'`** — um clique cria a segunda GCP por parcela, que
   escapa da exclusão da tela E de qualquer espelho em `calcular_fluxo_caixa`. Qualquer
   recorte que não feche isso **fica errado no dia seguinte ao deploy**. ⚠️ dev: 0 filhos
   `'conta_pagar'` hoje — o botão ainda não foi clicado; a forma está armada.
   (Quarta forma menor: 44 filhos `'compra'` minúsculo, legado de seed, nenhum com gêmea.)

**Vehicles (item nº3): a morte é tripla e o recorte é a rota inteira.** 📖 Conferido nesta
redação (`views/vehicles.py:826-946`): o `FluxoCaixa` de `:922-930` não passa `admin_id`
(`nullable=False`, 📖 `models.py:1130`; 🔬 `is_nullable='NO'` na coluna real) —
`IntegrityError` garantido no commit; o template `veiculos/novo_custo.html` **não existe**
(🔬 nem o diretório `templates/veiculos/`) — GET morre em `TemplateNotFound`; zero
referências à rota em templates, static e tests (nenhum `BuildError` ao remover). O
`except` externo (`:940-943`) faz rollback que derruba o `CustoVeiculo` e o `km_atual`
juntos. **Remover só o bloco FC seria pior que não fazer**: destrava o commit e ressuscita
um escritor de `CustoVeiculo` que nunca persistiu — comportamento novo sem decisão.

**Ponto (item nº4): remoção sem mudança observável.** Nenhum escritor de FC
`'registro_ponto'` em nenhuma lente (homonímia com `GestaoCustoFilho.origem_tabela`
checada); ⚠️ dev 0 linhas; os consumidores JS toleram chave ausente/vazia
(`controle_ponto.html:543-545`, `funcionario_perfil.html:2565+`). Mantém-se a chave
`fluxo_caixa: []` no JSON do preview.

**D-B5.7 — sob o default (a) da D-B5.1: quando a ContaPagar de uma compra é paga, quem
registra a SAÍDA REALIZADA no fluxo de caixa?** (a afiada da D-B5.1 — o default sozinho
não a resolve)
Trava: nada desta Task — ela executa o default abaixo; a resposta pode reabrir um Step.
**(1)** a baixa passa a gravar FC `'gestao_custo_pai'` no GCP gêmeo (ou flipa o status
dele) — acoplamento novo entre camadas, com matching frágil: a chave exige
`admin_id + (pedido_compra_id, parcela_numero) × (filho.origem_id, pai.numero_parcela)` —
`filho.origem_id` é o **mesmo** para todas as parcelas do pedido, e o próprio WF errou o
join duas vezes; e o escritor teria de vir do bloco Fase 4 do legado
(`gestao_custos_views.py:940-957`, o único que atribui `obra_id`/`centro_custo_id`), não
do vivo `autorizar` (`:812-825`, que não atribui — realizados invisíveis ao filtro por
obra e à limpeza de `excluir_obra`). **(2)** compras ficam **fora do realizado do fluxo**
por decisão documentada — revogando por escrito o comentário Task #11
(`compras_views.py:247-255`, "ContaPagar = camada do fluxo de caixa") — e o buraco fica
declarado: ~24% do valor aberto do parque sem realizado no fluxo quando pago pela tela de
contas a pagar.
**Default se não vier: (2).** Razão: (1) cria acoplamento com chave que já se provou fácil
de errar e herdaria o defeito do escritor vivo; um acoplamento novo entre camadas não deve
nascer por default — nasce por resposta. O buraco de (2) é visível e reversível; o
matching errado de (1) é silencioso.

**Comportamento novo.**
1. `calcular_fluxo_caixa` ganha a exclusão de gêmeos — **restrita por escrito à família
   `pedido_compra`**, com a subquery carregando `admin_id` — nas **três** pontas: previstas
   (`:519-545`), fallback PAGO (`:569-580`) e os detalhes previstos que alimentam os
   buckets de `agregar_fluxo_mensal`.
2. O guard de idempotência de `migrar_contas_pagar` passa a reconhecer também a gêmea
   `'pedido_compra'` (CP de compra **não** é clonada — fecha o amplificador de um clique
   sem decidir a fonte).
3. `views/vehicles.py:826-946` — a rota `main.novo_custo_veiculo` sai **inteira**.
4. `ponto_views.py:849-863` e `:932-940` saem; a chave `fluxo_caixa: []` fica no JSON.
5. Sob a D-B5.7 default (2): nenhum realizado novo é escrito; o comentário Task #11 ganha
   a anotação de revogação com ponteiro para este apenso.

**Teste que prova.**

| # | Ação | Asserção |
|---|---|---|
| 1 | GCP-compra aberto com gêmea CP no mesmo tenant | fora de `saidas_previstas` e dos buckets mensais |
| 2 | GCP-compra cujo "gêmeo" só existe em CP de **outro** tenant (colisão de id) | **continua** nas previstas — o guard de tenant na subquery (o erro que a medição cometeu duas vezes) |
| 3 | GCP aberto sem gêmea (origem manual) | continua nas previstas |
| 4 | GCP-compra com `saldo` NULL (4.202/5.081 em dev) | excluído também pelo fallback |
| 5 | `POST /gestao-custos/migrar-contas-pagar` duas vezes, com CPs de compra pendentes | **zero** GCP novo criado nas duas (guard reconhece a gêmea `pedido_compra`) |
| 6 | url_map após o corte de vehicles | `/veiculos/<id>/custo` sem regra; nenhum `url_for` quebra (zero referências) |
| 7 | `GET /ponto/excluir-preview/<id>` e o delete | JSON mantém `fluxo_caixa: []`; comportamento idêntico ao atual |

**Riscos → mitigação.**
1. **Subquery sem `admin_id` = misjoin** — provado: 41 falsos gêmeos em dev. → caso 2 é o
   cão de guarda.
2. **Exclusão só nas previstas deixa os buckets dobrados** — a lista `detalhes` e
   `agregar_fluxo_mensal` são o sintoma real (correção do adversário já adotada na B5.1:
   não é o `saldo_final` que dobra sozinho). → as três pontas no mesmo Step.
3. **Cortar só o bloco FC de vehicles ressuscita um escritor de `CustoVeiculo`** que nunca
   persistiu. → rota inteira (H4). A família tem **três** rotas mortas —
   `/veiculos/custo` (`:766-816`) e `novo_custo_veiculo_form` (`:1899+`) ficam citadas
   como limpeza separada, fora desta Task.
4. **As famílias 2 e 3 de gêmeos escapam do espelho por construção.** O guard do item 2 do
   comportamento fecha a 3; a 2 (reembolso do import) fica **registrada sem regra** — entra
   na resposta da D-B5.1/D-B5.7, não aqui em silêncio.
5. **Se a D-B5.7 devolver (1)**: o escritor de FC vem do bloco Fase 4 do legado, **não**
   de `autorizar` — senão nascem realizados sem `obra_id`, invisíveis ao filtro por obra
   (`pr_query :566-567`) e fora de `excluir_obra` (`views/obras.py:1215`).
6. **As linhas órfãs de dev** (168 FC `referencia_id=999` espalhadas por 76 tenants, 1-3
   cada) aparecem no `pr_query` desses tenants **sem pai nenhum** — é dado de seed/teste,
   não forma de estorno (o misjoin do levantamento está desfeito); limpeza é decisão de
   dado, não código desta Task.

**O que esta Task NÃO faz.** O buraco do **estorno de GCP** (FC retido sob pai reaberto,
delete de LC no-op) é matéria da **B5.6** — provado por leitura de
`financeiro_views.py:334-370`, **sem exemplar em dev** (o "GCP 999" caiu). O escritor vivo
`autorizar` sem `obra_id` fica registrado (⚠️ dev: 0 das 210 linhas FC `'gestao_custo_pai'`
sem obra — nenhuma veio de `autorizar` ainda; prova de forma, não de volume) — consertá-lo
é da resposta (1) da D-B5.7 ou de item próprio. E o import `'apenas_pagamento'`
(`importacao_excel.py:2329-2346`, SAIDA com referência NULL que vira "Lançamento Direto"
**editável** na tela do fluxo) fica como pergunta aberta de produto.

- [x] **Step 0:** registrar a **D-B5.7** na fila do Cássio (com a D-B5.1, de que ela é a afiada); a Task executa o default (2) sem esperar
- [x] **Step 1:** escrever o teste e ver vermelhos os casos 1, 4 e 5 (2, 3 e 7 nascem como guardas verdes; 6 nasce vermelho junto do Step 4)
- [x] **Step 2:** exclusão nas três pontas de `calcular_fluxo_caixa`, subquery com `admin_id`, restrita a `pedido_compra`
- [x] **Step 3:** guard de idempotência de `migrar_contas_pagar` reconhece a gêmea `pedido_compra`
- [x] **Step 4:** rota de vehicles sai inteira (`:826-946`)
- [x] **Step 5:** blocos de ponto saem; chave `fluxo_caixa: []` mantida
- [x] **Step 6:** sete casos verdes; mutação: restaurar a exclusão de uma ponta derruba só o caso 1/4; tirar o `admin_id` da subquery derruba só o 2; restaurar o guard antigo derruba só o 5
- [x] **Step 7:** dois commits — `fix(fluxo-caixa): gemeos de compra saem das previstas do fluxo` e `chore(financeiro): remove o escritor morto de vehicles e os leitores orfaos de ponto`

**Esforço: M.** **Migração: não** (🔬 conferido: `migrations.py` sobre `fluxo_caixa` só
tem o UPDATE de backfill de `admin_id` — nenhum INSERT; ⚠️ nota de 06/08: a última registrada passou a ser a **280**, gasta pela B5.6).

> **Nota — o que o adversário corrigiu neste levantamento.** (a) Âncoras de
> `financeiro_views.py` pré-B5.1 — corrigidas para a árvore atual (`:423`, `:434-452`,
> `:746`, `:886`); o levantamento era internamente inconsistente (metade medida antes do
> commit, metade depois). (b) "621 gêmeos / R$ 503.250" → **580 / R$ 490.950** com guard
> de tenant. (c) O "GCP 999 com 168 realizadas sob pai aberto" **não existe** — misjoin;
> as linhas são órfãs em 76 tenants; a pergunta aberta "seed ou estorno?" morreu com ele.
> (d) A **terceira família** de gêmeos (clones de `migrar_contas_pagar` + guard furado) —
> o levantamento citou a rota zero vezes; a lente STRING dele não pegou
> `origem_tabela='conta_pagar'` em `:1337/:1400`. (e) O escritor vivo `autorizar` **não é
> equivalente** ao legado: perde `obra_id`/`centro_custo_id` — a correção da Fase 4 virou
> código morto no caminho que a UI usa. (f) "627 CPs TOTAIS" → 652 (resíduo da B5.1).
> (g) A família de vehicles tem três rotas mortas, não duas.

---

### 10.1 Contradições registradas (formato da §8; numeração continua a de lá)

**6 — O que é "consertar o estorno" (B5.6).**
O levantamento recorta a catraca bancária e deixa os vazamentos de LC/FC dos estornos como
pergunta aberta ("entram na B5.6 ou na B5.7?"). O adversário sustenta que recortar só a
catraca entrega um estorno "consertado" que ainda mente — mesmo com (A), estornar+re-pagar
uma conta COMPRA dobra o LC `V2_AUTO` que ninguém apaga, e o flash da B5.1 empurra o
operador para lá; agrava que a correção da origem dos LC está proposta por escrito desde
30/07 e já foi esquecida uma vez.
**Adotado: os vazamentos dos DOIS estornos entram na B5.6** (Step 6, casos 5-6), e a
B5.7-H6 do levantamento (que os empurrava para cá) confirma o destino. Registrado porque a
inclusão é escolha desta síntese sobre uma pergunta que o levantamento deixou aberta — e
porque ela sobe o custo dentro do próprio M.

**7 — (A) × (C) na B5.6.**
O levantamento entrega o recorte "pronto nos dois sentidos" e trata A e C como
equivalentes na maturidade. O adversário rebaixa C duas vezes: a âncora do derivado
(`data_saldo_inicial`) é NULL em 47/47 bancos — a borda "(5)" do levantamento é o caso
universal —, e a edição inline de FC reescreveria saldo em silêncio sob C.
**Não resolvida — é a D-B5.6**, com default (A) e a razão escrita. A discordância
registrada é sobre a **simetria** das opções, não sobre a lista: se o Cássio escolher (C),
o recorte de C precisa ser revarrido — o que está pronto nos dois sentidos é a pergunta,
não a implementação.

**8 — O realizado das compras sob o default (a) da D-B5.1 (B5.7).**
O levantamento formula a escolha (1) FC no GCP gêmeo × (2) compras fora do fluxo e não
recomenda lado. O adversário acrescenta que (1), como o levantamento a descreveu, herdaria
dois defeitos (matching sem guard de tenant; escritor vivo sem `obra_id`) — sem se opor a
(1) corrigida.
**Não resolvida — é a D-B5.7**, com default (2) e a razão escrita (o erro de (1) é
silencioso; o buraco de (2) é declarado). A Task executa o default; a resposta pode
reabrir um Step, não a Task.

**9 — As medidas com join sem guard de tenant (B5.7).**
Levantamento: 621 gêmeos/R$ 503.250; "GCP 999 com 168 realizadas sob pai PENDENTE".
Adversário: reproduziu os dois números **e** os refez com `admin_id` — 580/R$ 490.950; e
o GCP 999 é misjoin (168 linhas órfãs em 76 tenants).
**Resolvida a favor do adversário**, e registrada porque vira regra da casa desta rodada:
**todo join de gêmeos CP↔GCP carrega `admin_id`** (caso 2 do teste da B5.7 congela isso), e
**toda medida ⚠️ dev citada em documento carrega a data da medição** — o banco único de dev
é movido pela própria suíte (627→652 CPs no mesmo dia, medido).

---

## Histórico

- **2026-08-06** — Rodada B5 aberta. Cinco dívidas sem Task varridas com cinco lentes cada
  e submetidas a refutação adversarial. **Cinco sobreviveram; quatro tiveram o recorte
  derrubado** (§1.2). Nasceram **cinco Tasks** (B5.1 a B5.5, nenhuma com migração) e
  **onze itens abertos novos** (§4), dos quais dois são dinheiro em produção hoje
  (a catraca de `banco.saldo_atual` e a discordância entre os dois caminhos de pagamento) e
  dois são risco de instrumento (`Timer` em thread de fundo no listener de RDO; ordem de
  coleta determinística sustentando o gate).
- **2026-08-06, tarde** — **Apenso §10: os dois itens de dinheiro viraram as Tasks B5.6 e
  B5.7** (WF-2, levantar/refutar). A pergunta central da B5.6 tem resposta **NÃO** (o banco
  debitado não é recuperável em lugar nenhum) e nasce a **D-B5.6** (default: coluna
  `banco_id` + migração da faixa 280-283) e a **D-B5.7** (a afiada da D-B5.1, default:
  compras fora do realizado do fluxo, documentado). Os adversários derrubaram quatro
  medidas do levantamento (resíduo da suíte B5.1 no banco de dev; dois joins de gêmeos sem
  guard de tenant) e acharam a terceira família de gêmeos (`migrar_contas_pagar`) e o
  vazamento de LC `V2_AUTO` nos dois estornos. Contradições 6-9 registradas na §10.1.
- **2026-08-06, noite** — **A rodada B5 FECHA: 6 entregues, 1 cortada.** O Cássio decidiu
  não rodar as consultas de produção e adotar os defaults (D-B5.1(a), D-B5.6(A); a B5.5
  caiu pelo próprio mecanismo do Step 1). B5.6 entregue (`08f2ee88`, **migração 280
  gasta**) e B5.7 entregue (`3288ba84`+`b5472260`). Itens novos que sobraram desta
  execução, ambos para fila futura: **mapear `DESPESA_GERAL`** (ou trocar o
  `tipo_operacao` dos pagamentos de GCP) — decisão de contador, achado do caso 6 da
  B5.6; e o **estorno de recebimento**, que não existe (194 CRs liquidadas sem reversão
  pela UI, ⚠️ dev). A família flash+redirect (35 rotas) e a limpeza das rotas irmãs de
  vehicles seguem para a rodada B6.
