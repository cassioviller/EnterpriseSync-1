# SDD ledger — plan: docs/superpowers/plans/2026-08-25-onda-2-o-tenant-para-de-vazar.md

Branch: `sdd/onda-2-o-tenant-para-de-vazar` (de `main` @ c1156cb5, pos-push)
Base da execucao: c1156cb5
Spec: docs/superpowers/plans/2026-08-25-fecho-dos-114-achados.md (Onda 2)
      evidencia por achado em docs/auditoria/achados-code-review-2026-08-25.md

## Varredura de conflitos (pre-flight)

### Consistencia interna de cada task

| Task | Testes x codigo que ela especifica | Achado |
|---|---|---|
| 1 | script de medicao x models | OK — TipoUsuario.GESTOR_EQUIPES (models.py:24) e ALMOXARIFE (:25) existem. So-leitura, sem teste |
| 2 | 3 testes x multitenant_helper.py:10-45 | OK — o helper tem a logica propria nas linhas ditas; utils.tenant.get_tenant_admin_id (utils/tenant.py:15-31) confere com a tabela do plano: ADMIN/SUPER_ADMIN -> id, resto -> admin_id. Ver nota N1 |
| 3 | 2 testes x views/rdo.py:2826-2848 | OK com ressalva — ver C2 |
| 4 | 2 testes x portal_obras_views.py | OK — nao conferido em profundidade, o plano manda o implementador confirmar as rotas por grep |
| 5 | 4 testes x utils/fk_do_tenant.py + 8 chamadores | RUIM — ver C3, C4, C5 |
| 6 | 2 testes x veiculos_services + rdo_editar_sistema | CRITICO — ver C1 |
| 7 | 2 testes x contabilidade_views + almoxarifado_utils | OK — as duas strings dos asserts existem LITERALMENTE hoje (almoxarifado_utils.py:257, contabilidade_views.py:1300) |
| 8 | 2 testes x vinculos_audit + auth | OK — grep de consumidores devolve SO as duas definicoes (auth.py:47, :58). Apagar e a resposta certa |

### Pares de tasks que compartilham arquivo ou interface

| Par | Produz x consome | Achado |
|---|---|---|
| 5 -> 6, 7 | `fk_do_tenant(modelo, valor, admin_id, *, campo, obrigatorio=False)` | OK — assinatura identica nos tres consumidores (6:3b, 6:3c, 7:3d) |
| 2 -> 3, 8 | delegacao para `utils.tenant` | OK — 2 poe a casca em multitenant_helper, 3 e 8 chamam utils.tenant direto. Sem colisao |
| 2,3,4,5,6,7,8 | todos anexam a `tests/test_onda2_tenant_nao_vaza.py` | OK — execucao sequencial; anexo nao colide |
| 2 -> 8 modulos importadores | `get_admin_id() -> int|None` | OK — a casca preserva assinatura e a tolerancia a contexto sem request |
| 6 -> 5 | 6:3b usa `Obra` + `rdo.admin_id` | OK — Obra tem admin_id (models.py:360) |

### CRITICO C1 — a Task 6 se contradiz: o teste proibe a linha que a propria correcao mantem

O Step 1 afirma `assert 'for campo, valor in dados.items():' not in fonte`.
O Step 3a escreve, como correcao, exatamente:
    `for campo, valor in dados.items():`
    `    if campo not in CAMPOS_EDITAVEIS_VEICULO: continue`
Aplicar a correcao do plano deixa o teste do plano VERMELHO. Nao ha ordem de
execucao que satisfaca os dois.

Medido: veiculos_services.py:166-175 tem hoje `for campo, valor in dados.items():`
seguido de `if hasattr(veiculo, campo):`. O DEFEITO e o `hasattr` — que diz sim
para `admin_id` —, nao a iteracao sobre o dicionario.

**Ruling:** o teste passa a afirmar sobre o defeito, nao sobre a linha. Tres
assercoes no lugar da uma: (a) `'if hasattr(veiculo, campo):' not in fonte`;
(b) `CAMPOS_EDITAVEIS_VEICULO` existe e NAO contem 'admin_id' nem 'id';
(c) um teste de COMPORTAMENTO — chamar o servico de edicao com `admin_id` de
outro tenant no dicionario e afirmar que `veiculo.admin_id` nao mudou.
**Porque:** a Onda 1 gastou dois fix rounds e um teste vacuo (Task 5) por
assercao que nao exercitava o caminho vivo. Grep de fonte e guarda, nao prova.
A (c) e a que realmente fecha o achado.
**Custo se errado:** um teste a mais que o necessario, com fixture de veiculo.
Reversivel. O risco oposto — manter o grep do plano — e a task nao poder fechar.

### C2 — existem DOIS `get_admin_id_robusta`, o plano trata um

Medido: `views/rdo.py:7` importa `get_admin_id_robusta` de `views.helpers`, e
`views/rdo.py:2826` define um ANINHADO que sombreia o import dentro daquela
view. O plano so descreve o aninhado.
Conferido em `views/helpers.py:376-408`: o do modulo JA foi corrigido (devolve
None no except, sem `return 10`, sem busca por e-mail). O chamador de
`views/rdo.py:4618` usa o do modulo — ja seguro.
`grep "return 10" views/rdo.py` devolve UMA linha (:2848), entao o assert amplo
do plano sobre o modulo inteiro e seguro.

**Ruling:** a Task 3 fica como esta — o alvo e so o aninhado. O brief leva o
fato explicito, para o implementador nao "consertar" o de views/helpers.py, que
ja esta certo, nem se assustar com o import da linha 7.
**Custo se errado:** nenhum — e informacao, nao mudanca de escopo.

### C3 — os numeros de linha do plano sao anteriores a Onda 1

O plano foi escrito em 25/08 sobre `main` @ f1f57a56. A Onda 1 entrou depois e
mexeu em financeiro_views.py, compras_views.py e views/orcamentos_views.py.
Medido: `financeiro_views.py:895` hoje e uma linha de `db.session.rollback()`;
`gestao_custos_views.py:262` e `Fornecedor.query.get(...)`, nao o `:262` do
plano; `views/almoxarifado/itens.py:110` e `categoria_id=categoria_id` dentro do
construtor, e a leitura do form esta em `:89`.

**Ruling:** os `arquivo:linha` do plano sao PISTA, nao endereco. Todo brief
leva o alvo por SIMBOLO (funcao + padrao a substituir) e a linha entre
parenteses como conferencia. O implementador localiza por grep e reporta se o
que achou diverge do que o brief descreve.
**Custo se errado:** baixo — implementador editando a linha errada e exatamente
o que o review de task pega, e o diff mostra.

### C4 — dois nomes de modelo da Task 5 nao existem

Medido em models.py: nao ha `class Banco` nem `class CategoriaAlmoxarifado`.
Os reais sao `BancoEmpresa` (models.py:2590) e `AlmoxarifadoCategoria` (:5501),
e 🔬 os dois TEM `admin_id`. Os outros sete da tabela conferem: Obra (:360),
CategoriaTransporte (:6481), Funcionario (:297), Veiculo (:5147),
CentroCusto (:1060), Subempreiteiro (:7850), Fornecedor (:2375) — todos com
admin_id.

**Ruling:** o brief da Task 5 leva a tabela corrigida com os nomes reais. O
plano ja mandava conferir; a conferencia esta feita aqui, uma vez, em vez de
cada implementador refazer.
**Custo se errado:** nenhum — ImportError imediato se estiver errado.

### C5 — a Task 5 nomeia 8 chamadores; sao ~12, e um esta no arquivo errado

(a) `financeiro_views.py:895` -> `fornecedor_id` NAO EXISTE. Medido: o unico
`fornecedor_id` em financeiro_views vem de `request.args` (:1605) e filtra uma
query ja escopada — nao e FK de escrita. A spec (achados:215) agrupa
"`gestao_custos_views.py:822`, `:262`, `financeiro_views.py:895` (FKs de
banco/fornecedor/subempreiteiro)". Os TRES sao de gestao_custos_views: banco em
`:760` (`autorizar`) e fornecedor em `:240/:262` (`novo`). O nome do arquivo na
spec e erro de transcricao.

(b) Cada um tem GEMEO na funcao irma, que o plano nao lista:
  - obra_id:          `novo():234`  e  `editar():1074`  (o plano tem os dois)
  - subempreiteiro_id:`novo():241`  e  `editar():1064`  (o plano so tem um)
  - fornecedor_id:    `novo():240`  e  `editar():1063`  (o plano nao tem nenhum, ver (a))
  - banco_id:         `autorizar():760` e `pagar():895` (o plano so tem um)
  - transporte:       `novo():160-168` e `editar():378-383` (o plano so tem um)
  - almoxarifado:     `criar():89`  e  `editar():165`  (o plano tem :110, que e o construtor, nao a leitura)

**Ruling:** a Task 5 cobre os DOZE, e o brief leva o mapa por funcao+simbolo.
**Porque:** o docstring que o proprio plano cita para justificar o helper diz
que "a correcao entrou naquela funcao e nao nas irmas: novo() e editar() do
mesmo arquivo ficaram de fora". Corrigir `novo()` e deixar `editar()` seria
cometer, dentro da task, o defeito que a task existe para acabar. Precedente
direto: a ruling C1 da Onda 1, mesma forma.
**Custo se errado:** a Task 5 fica maior — ~12 sitios em 4 arquivos em vez de 8.
E o unico ponto onde considerei quebrar a task em duas; nao quebrei porque as
doze sao a MESMA substituicao mecanica e um review so as ve juntas.

### C6 — a regua do gate esta velha

O plano (Task 8, Step 6) espera **2560 passed / 6 skipped / 2 xfailed**, regua de
23/08. A Onda 1 mediu **2726 passed, 6 skipped, 201 deselected, 2 xfailed** no
gate de fecho (commit 30e32e3a) — os +166 sao os 67 testes da Onda 1 mais 99 da
Fase 6, que entrou na main entre a regua e a execucao.

**Ruling:** a regua desta onda e **2726**, mais os testes que ela mesma criar.
Qualquer teste hoje verde que cair e achado novo, nao ruido — como o plano ja diz.
**Custo se errado:** nenhum — e a contagem medida dois dias depois da do plano.

### N1 (nota, nao conflito) — o `cliente_de` morto no teste da Task 2

`test_gestor_e_almoxarife_resolvem_o_tenant_do_dono` faz `cliente = cliente_de(uid)`
e `with cliente.session_transaction(): pass`, e depois nao usa `cliente` — a
assercao roda em `app.test_request_context()` com `login_user`. Duas linhas
inertes. Conferido que `cliente_de(user_id)` (tests/helpers_tenant.py:148) toma
id de USUARIO, entao a chamada esta correta, so e inutil.
Nao e ruling: o implementador que remova se quiser, e o review de task decide.

---

## Progresso

Task 1: dispatched (haiku — o brief traz o codigo completo; e transcricao + execucao). BASE c1156cb5
Task 1: implementer DONE (commit 7672f653). Veredito: nenhuma linha no tenant fantasma
  no banco de DEV — a Task 2 entra sem migration de saneamento, com a ressalva de que
  dev nao tem GESTOR_EQUIPES/ALMOXARIFE nenhum, entao ele prova a FORMA, nao o volume.
  Conferido pelo controller: zero escrita no script (grep de INSERT/UPDATE/DELETE/
  db.session.add|commit|delete|merge), zero invisivel literal, arvore limpa.
  Review dispatched (haiku) sobre c1156cb5..7672f653.
Task 1: pendencia do fecho da onda (nao bloqueia): a medicao que DECIDE e a de producao;
  a de dev nao substitui. Entra no fecho como item humano nomeado, como o plano ja preve.
Task 1: review — Spec com ressalva, qualidade "needs fixes". 0 Critical, 1 Important, 0 Minor.
  Important: `scripts/medir_tenant_fantasma.py:68-78` + `:85-89` — o `except Exception` por
  tabela IMPRIME o erro mas nao o REGISTRA, e `total_geral` fica 0. Se as 8 tabelas falharem
  (permissao, tabela ausente, conexao caindo no meio), o script imprime 8x "nao consultavel" e
  depois "VEREDITO: nenhuma linha no tenant fantasma", com exit 0. "Medi tudo e nao achei nada"
  e "nao consegui medir nada" produzem o MESMO veredito e o MESMO exit code.
  O revisor confirmou que os dois caminhos de SUCESSO ja se distinguem (sem usuarios afetados
  x com usuarios e zero linhas); o que nao se distingue e o caminho de FALHA.
  Ruling: CORRIGIR, e o achado e plan-mandated — este codigo veio verbatim do plano, entao a
  origem sou eu/o plano, nao o implementador. Corrijo mesmo assim porque a constraint global da
  spec ("Falha fechada, sempre. Sem tenant resolvido: 403, nunca admin_id IS NULL") e a
  autoridade vinculante e o texto do script e so o argumento dela. E porque a medicao que
  DECIDE e a de PRODUCAO, onde tabela inacessivel por permissao e cenario plausivel — nao
  hipotetico. Um falso "nenhuma linha" ali faz a Task 2 tornar dado real invisivel sem aviso,
  que e exatamente o desastre que esta task existe para prevenir.
  Custo se errado: baixo — sao ~6 linhas de contabilidade de falha e um exit code; se a guarda
  for estreita demais, o script recusa medir e alguem roda de novo. O risco oposto e silencioso.
Task 1: fix round 1/5 dispatched (implementador original retomado). FIX_BASE 7672f653
Controller (26/08, antes de qualquer mudanca de codigo): linhas de base MEDIDAS, nao herdadas.
  Banco de dev acessivel e o arreio tests/helpers_tenant.py funciona — as tasks 2-8 podem
  fazer TDD de verdade. Medido: test_gestao_custo_filho_tenant 3 passed sozinho.
  BASELINE das cinco suites que as tasks 2, 5 e 7 nao podem regredir, em c1156cb5+7672f653:
    test_p1_isolamento_relatorios + test_gestao_custo_filho_tenant + test_b5_baixa_conta_pagar
    + test_arreio_almoxarifado_e_tenant + test_fase06_d4_plano_contas_por_tenant = 42 passed.
  Registrado ANTES de mexer no resolvedor de proposito: medir depois de mudar nao prova nada.
Task 1: fix round 1/5 aplicado (commit 0cbaf652). Guarda de completude: falhas contadas por
  tabela, tres saidas (FALHA sem veredito + exit 1 / VEREDITO PARCIAL nomeando o que faltou +
  exit 1 / VEREDITO completo + exit 0), e o caminho "sem usuario afetado" intocado.
  Re-review escopado despachado (sonnet) sobre 7672f653..0cbaf652, com pedido de refazer a
  prova de mutacao por experimento em copia /tmp e de auditar a contabilidade de completude
  ao longo do laco usuario x tabela.
Task 1: fix round 1/5 re-review — achado ORIGINAL ADDRESSED (`:72-77`), provado por experimento
  refeito pelo revisor em copia /tmp (8 tabelas falhando -> "FALHA: medicao incompleta" + exit 1);
  caminho feliz e caminho "sem usuario afetado" intactos. MAS 1 Important NOVO no proprio diff
  do fix, e e a MESMA falha aberta por outra porta:
  `tabelas_medidas` e `falhas_por_tabela` acumulam ao longo do laco EXTERNO de usuarios, entao
  sao uniao POR TABELA, nao por (usuario, tabela). Uma tabela entra em `tabelas_medidas` se der
  certo para QUALQUER usuario; `tabelas_falhadas` (:71) so pega tabela que falhou para TODOS.
  Tabela X que funciona no usuario 1 e falha no usuario 2 nao aparece em lugar nenhum: sem
  AVISO, sem FALHA, exit 0, veredito "completo" — e as linhas do usuario 2 nunca entram em
  `total_geral`. Reproduzido pelo revisor com 2 usuarios sinteticos.
  E a raiz que torna isso PROVAVEL, nao raro: o `except` (:60-64) nunca chama
  `db.session.rollback()`. Confirmado ao vivo contra o banco de dev (so leitura): uma excecao
  envenena a sessao e TODA query seguinte levanta InFailedSqlTransaction. Entao basta 1 falha
  transitoria no 2o usuario para o resto da corrida inteira falhar em silencio, ja que as 8
  tabelas foram marcadas "medidas" pelo 1o.
  Ruling: entra no round 2, e o rollback entra JUNTO, apesar de o revisor te-lo posto como
  observacao fora de escopo. Motivo: guarda de completude que nao sobrevive a primeira excecao
  nao e guarda de completude — o rollback e a raiz do achado em escopo, nao um vizinho dele.
  Corrigir a contabilidade sem o rollback deixaria o script reportando PARCIAL sempre que
  qualquer coisa falhasse, o que e ruido, nao medicao.
  Custo se errado: baixo — sao duas mudancas pequenas (chave (usuario, tabela) e um rollback no
  except) num script so-leitura que nao esta no caminho de producao do app. O risco oposto ja
  esta medido: veredito falsamente completo na unica corrida que decide, a de producao.
Task 1: fix round 2/5 dispatched. FIX_BASE 0cbaf652
Task 1: fix round 2/5 aplicado (commit 7ad28d84). Os dois achados atacados juntos: `rollback()`
  entrou no except (:67) e a contabilidade virou por par (usuario_id, tabela) — `pares_esperados`
  / `pares_medidos` / `pares_falhados` (:44-46, :55, :62, :66, :75). Implementador reporta os 4
  cenarios provados: 2 usuarios com falha so no segundo -> PARCIAL 15/16 + exit 1; falha total ->
  FALHA + exit 1; caminho feliz dev -> veredito + exit 0; e a prova do rollback (query legitima
  apos excecao passa com rollback, levanta InFailedSqlTransaction sem ele).
  Conferido pelo controller: rollback presente, zero escrita, zero invisivel literal.
  Re-review escopado despachado (sonnet) sobre 0cbaf652..7ad28d84, com pedido de ENUMERAR os
  casos degenerados do calculo novo (inclusive "ha suspeitos mas todos pulados por
  admin_id == id") e dizer o ramo, o texto e o exit code de cada um. Nao adiantei conclusao.
Task 1: fix round 2/5 re-review — os DOIS achados ADDRESSED, provados por experimento proprio do
  revisor, nao por leitura do report: rodou o codigo do round 1 (`git show 0cbaf652:...`) e o
  atual no MESMO cenario sintetico (2 usuarios, falha so no segundo) — round 1 devolveu
  "VEREDITO: nenhuma linha" + exit 0 (o falso negativo), round 2 devolveu "AVISO: medicao parcial
  (15/16 pares)" nomeando usuario 202 e a tabela, + exit 1. Rollback conferido contra o banco de
  dev real: sem ele a query seguinte levanta InFailedSqlTransaction, com ele passa.
  Zero breakage novo do round 2. So-leitura, zero invisivel, commit em portugues — confirmados.
Task 1: ACHADO RESIDUAL, herdado (nao e breakage do round 2): caso degenerado (b) — quando
  existem suspeitos mas TODOS sao pulados por `admin_id == id`, `pares_esperados` fica vazio por
  construcao (o `continue` de :53 acontece antes de :54-55 popular o conjunto), e a linha 76 usa
  `pares_nao_medidos == pares_esperados` como proxy de "falha total": `set() == set()` e
  vacuamente verdadeiro. Sai `FALHA: medicao incompleta` com "0 par(es)" e exit 1, SEM veredito.
  Viola o contrato do proprio brief ("usuario pulado por admin_id == id nao conta como falha").
  O revisor rodou o codigo pre-diff e provou que o defeito ja existia identico no round 1 — o
  round 2 preservou, nao criou. Nenhum dos 4 cenarios do report cobria esse caso.
  Ruling: CORRIGIR no round 3, em vez de deferir. E uma linha (`if pares_esperados and ...`).
  Motivo: a direcao do erro e fail-closed, entao nao e perigoso como o original — mas ele mora
  na guarda que decide a migration de saneamento, e uma guarda que da alarme falso ensina quem
  opera a ignorar alarme. O custo de um FALHA espurio nao e o exit 1: e o proximo FALHA, o de
  verdade, ser lido como "aquele bug do script".
  Custo se errado: um round a mais num script de diagnostico, por uma linha. Barato.
Task 1: fix round 3/5 dispatched. FIX_BASE 7ad28d84
Task 1: fix round 3/5 aplicado (commit 27239e83). Diff de 5 linhas, conferido pelo controller:
  a guarda de :76 virou `if pares_esperados and pares_nao_medidos == pares_esperados`, e entrou
  um ramo `elif not pares_esperados` que devolve veredito + exit 0 com texto proprio ("Nenhum
  usuario de papel afetado distingue os dois resolvedores"), distinguivel de "medi e estava
  limpo". Os outros quatro ramos intocados no diff.
  Implementador reporta os 5 casos com exit code: (a) 0, (b) 0 com texto novo, (c) 0, (d) 1
  parcial, (e) 1 falha. Re-review escopado despachado (haiku) sobre 7ad28d84..27239e83, com
  pedido de refazer os cinco por experimento — (a),(c),(d),(e) como prova de nao-regressao — e
  de conferir se a ordem dos if/elif nao criou ramo inalcancavel.
Controller: medido antes de despachar a Task 2 — `TipoUsuario` tem CINCO papeis (models.py:21-26),
  entao a divergencia e mesmo so GESTOR_EQUIPES e ALMOXARIFE, como a tabela do plano diz. Mas o
  codigo real e pior que a tabela descreve: `multitenant_helper.get_admin_id` so trata
  `tipo == 'funcionario'` (:25) e TODO o resto cai num `return current_user.id` (:31) — nao ha
  ramo por papel nenhum. E ha um SEGUNDO fail-open que o plano nao nomeia: o `except` (:36-42)
  devolve `current_user.id` quando a resolucao falha. A implementacao do plano remove os dois;
  levei isso explicito no dispatch para o implementador nao "restaurar" o fallback achando que
  era descuido.
Task 2: dispatched (haiku — o brief traz teste e implementacao por extenso; e transcricao + TDD).
  BASE 27239e83. Linha de base de regressao no dispatch: 42 passed nas cinco suites, medida por
  mim antes de qualquer mudanca da onda. Instruido a PARAR e reportar se der diferente de 42.
Ruling (paralelismo, a pedido do usuario): a onda passa a rodar em DUAS trilhas, nao em sete.
  Medido: os arquivos de producao das tasks se separam em dois conjuntos DISJUNTOS.
    Trilha A (sequencial): 2 -> 5 -> 6 -> 7. multitenant_helper, utils/fk_do_tenant,
      gestao_custos_views, transporte_views, views/almoxarifado/itens, veiculos_services,
      rdo_editar_sistema, ponto_views, contabilidade_views, almoxarifado_utils, ponto_service.
    Trilha B (sequencial): 3 -> 4 -> 8. views/rdo, portal_obras_views, vinculos_audit_views,
      services/cliente_resolver, auth.
  Por que nao mais que duas: 6 e 7 CONSOMEM o `fk_do_tenant` que a 5 produz — sao dependencia
  real, nao ordem arbitraria. E a 2 e a raiz. Dentro de cada trilha a ordem e obrigatoria.
  Por que as trilhas nao colidem apesar de subagentes compartilharem UM working tree: os
  conjuntos de arquivo acima sao disjuntos, e a trilha B roda em git worktree proprio.
  A UNICA colisao e `tests/test_onda2_tenant_nao_vaza.py`, que o plano manda TODAS as tasks
  usarem. Ruling: a trilha B escreve em `tests/test_onda2_rotas_nao_vazam.py`. O arquivo unico
  e convencao do plano, nao exigencia da spec (o doc de achados nao diz nada sobre layout de
  teste), e convencao perde para execucao paralela correta. Custo se errado: dois arquivos de
  teste da onda em vez de um; cosmetico, e reversivel com um `cat` se alguem quiser juntar.
  RISCO ACEITO, registrado: as duas trilhas rodam pytest contra o MESMO banco de dev ao mesmo
  tempo. O arreio (tests/helpers_tenant.py) marca cada tenant com uuid unico, entao os testes
  da onda nao se enxergam. Suite larga rodando em paralelo pode dar ruido; se aparecer contagem
  estranha, a causa e essa e a resposta e re-rodar em serie, nao "consertar" o teste.
Trilha B, Task 3: dispatched (haiku — o brief traz teste e correcao por extenso). BASE 27239e83
Task 1: fix round 3/5 re-review — ADDRESSED (`:76` ganhou a guarda `pares_esperados and`, e o
  ramo novo `elif not pares_esperados` :84-87 devolve veredito + exit 0). Os cinco ramos
  refeitos por experimento pelo revisor: (a) 0, (b) 0 com o texto novo — antes era FALHA + exit
  1 —, (c) 0, (d) 1 parcial, (e) 1 falha. Ordem dos if/elif conferida: nenhum ramo inalcancavel.
  Zero breakage novo. So-leitura, sem invisivel, commit em portugues.
Task 1: complete (commits c1156cb5..27239e83, review clean apos 3 fix rounds, 0 minors abertos)
  Nota de valor: os 3 rounds nao foram erro do implementador. Round 1 fechou um defeito que veio
  VERBATIM DO PLANO (veredito falhando aberto); round 2 fechou o que o proprio fix do round 1
  reabriu por outra porta, mais a raiz (sessao Postgres envenenada sem rollback); round 3 fechou
  um caso degenerado herdado que nenhum dos dois rounds cobria. Tres defeitos distintos numa
  guarda de 100 linhas que decide se a onda precisa de migration.
Task 2: implementer DONE (commit 44bea17f; 5 passed no arquivo da onda, RED citado com ids reais
  — 196747 != 196745 para GESTOR_EQUIPES, 196750 != 196748 para ALMOXARIFE; regressao 42 passed,
  IGUAL a baseline). Conferido pelo controller: `multitenant_helper.py` nao tem mais NENHUMA
  logica de papel (as unicas mencoes a GESTOR/ALMOXARIFE sao docstring), delega em :29-30 e
  devolve None no except :31-33 — o fallback antigo para `current_user.id` sumiu. `git diff
  --name-only` mostra SO dois arquivos: multitenant_helper.py e o teste. Os oito importadores
  intactos, como a constraint exige.
  Review dispatched (sonnet) sobre 27239e83..44bea17f, com quatro pedidos especificos: o que
  mais o `except Exception` engole; se o fallback velho sumiu mesmo; se o teste de "sem request
  context" passa por acidente; e se os dois testes de papel exercitam o caminho vivo de rota.
Task 5: dispatched (sonnet — 12 sitios em 4 arquivos + helper novo; e integracao, nao
  transcricao). BASE 44bea17f. Brief ja emendado com as rulings C3/C4/C5.
Task 2: review — Spec ✅ CONFORME em todos os requisitos, qualidade APPROVED.
  O revisor provou por EXPERIMENTO (nao por leitura) que o teste da casca defensiva nao e vacuo:
  removeu o try/except numa copia scratch e o teste ficou VERMELHO com AttributeError; restaurou
  e conferiu `git diff --stat` limpo. Depois do teste vacuo da Task 5 da Onda 1, era o pedido.
  Tambem confirmou: o fallback velho `return current_user.id` no except sumiu por completo
  (linhas 72-79 removidas), nenhum caminho devolve id chutado, zero logica de papel sobrou, os 8
  importadores com zero linhas alteradas, e que os testes de papel exercitam o caminho vivo
  (`load_user` em app.py:521-522 e so um `Usuario.query.get`, sem logica extra, entao
  `login_user` em test_request_context == o que a rota ve).
Task 2: 1 Important, PLAN-MANDATED e MAIOR QUE A TASK — nao e defeito da implementacao.
  O `except Exception` da casca converte QUALQUER erro em None, nao so "fora de request": um
  AttributeError por rename de modelo, um OperationalError do SQLAlchemy no meio de uma request
  autenticada. E varios dos 8 chamadores congelados plugam o retorno direto em
  `filter_by(admin_id=admin_id)` — que com None vira `WHERE admin_id IS NULL`, exatamente o que a
  constraint global proibe ("NUNCA admin_id IS NULL").
  MEDIDO POR MIM antes de julgar: os 8 importadores somam 225 usos de admin_id em query e
  ZERO guardas de None (crud_servico_obra_real 10/0, custos_escritorio_views 23/0, ponto_service
  10/0, reembolso_views 17/0, ponto_views 58/0, financeiro_views 72/0, configuracoes_views 32/0,
  views/users 3/0).
  Ruling: Task 2 fecha APROVADA e o achado NAO entra em fix round. Tres razoes, medidas:
  (a) E PRE-EXISTENTE, nao introduzido: o `get_admin_id` velho ja devolvia None para usuario nao
      autenticado (:33), entao o caminho None e os 225 sitios desguarnecidos ja conviviam antes
      desta onda. A Task 2 melhorou o saldo — tirou o id chutado do except — e nao piorou.
  (b) O brief CONGELA os 8 importadores ("nao mudam nenhuma linha"), e com razao: mexer neles
      dentro desta task e o oposto da task, que existe para provar que a casca e transparente.
  (c) 225 sitios em 8 modulos nao cabem numa task desta onda, e inventar uma nona task por conta
      propria seria eu decidir sozinho um alargamento grande de escopo. E decisao do usuario.
  Vai para o FECHO DA ONDA como achado nomeado e medido, e foi levado ao usuario. O plano ja
  conhece o padrao — a Task 8 conserta exatamente isso em vinculos_audit_views com
  `require_tenant()` — mas so num modulo dos nove.
  Custo se errado: o buraco continua aberto mais um ciclo. Mitigado por (a): ele nao e novo, e a
  exposicao e falha-fechada (linhas orfas com admin_id NULL, nao linhas de outro tenant).
Task 2: minor (deferred): tests/test_onda2_tenant_nao_vaza.py:75,99 usam `Usuario.query.get(uid)`,
  que emite LegacyAPIWarning no SQLAlchemy 2.0. Herdado do codigo literal do brief, nao inventado
  pelo implementador. `db.session.get(Usuario, uid)` e o idiomatico. Lint na revisao final.
Task 2: complete (commits 27239e83..44bea17f, review clean — 1 Important roteado ao fecho com
  ruling, 1 minor deferido)
Task 5: implementer PAROU no Step 2, correto e conforme o contrato — nenhum commit, nenhum codigo
  de producao tocado. Dois achados, os DOIS a favor dele:
  (a) `test_lancamento_de_transporte_nao_prende_custo_na_obra_alheia` NASCE VERDE, e pelo motivo
      errado: o payload nao manda `categoria_id`, `transporte_views` faz
      `int(request.form.get('categoria_id'))`, isso levanta TypeError ANTES de chegar em
      `obra_id`, o except generico vira redirect 302, e `vazou == 0` sai de CRASH, nao de
      validacao. O teste do brief prova o oposto do que promete.
      Ruling: reescrever o teste — semear CategoriaTransporte do tenant A, mandar todos os
      campos obrigatorios do tenant A, e forjar SO o `obra_id` para o tenant B. Exigida prova de
      mutacao: comentar a validacao e ver o teste FALHAR. O texto do plano perde para a intencao
      do plano, mesmo precedente da Onda 1 Task 5. Custo se errado: fixture um pouco mais pesada.
  (b) ERRO MEU na emenda C5: eu mandei validar `veiculo_id` contra `class Veiculo`. Conferido
      agora: `LancamentoTransporte.veiculo_id` e `ForeignKey('frota_veiculo.id')`, e
      `frota_veiculo` e `class Vehicle` (models.py:5398), nao `class Veiculo` (:5147, tabela
      `veiculo`). Sao dois modelos distintos, ambos com admin_id, e `transporte_views` ja usa
      `Vehicle` (:11, :131, :227, :283). Eu conferi que Veiculo tinha admin_id e nunca conferi a
      TABELA para onde a FK aponta — validar contra o modelo errado recusaria veiculo valido ou
      aceitaria id invalido.
      Ruling: usar `Vehicle`. E a regra geral vai no dispatch: confirmar todo modelo contra a
      `ForeignKey('<tabela>')` real da coluna, nunca contra o nome do campo.
      Nota de repo (nao e acao): existem DOIS modelos de veiculo. `veiculos_services.py`, da
      Task 6, usa `Veiculo`. Nao e inconsistencia entre as tasks — cada uma usa o seu.
  Task 5 desbloqueada com as duas rulings; implementador retomado.
Trilha B, Task 3: implementer commitou (77e4ab00, worktree
  .claude/worktrees/agent-ae31deb64e9a99280) mas PAROU no meio da rede de RDO tendo detectado um
  teste falhando (F na saida), sem entregar veredito final.
  Conferido pelo controller: o diff esta CERTO — o aninhado delega para get_tenant_admin_id,
  devolve None no except, e o chamador (:2846) ganhou `if admin_id_correto is None: abort(403)`.
  `abort` JA estava importado (views/rdo.py:1), entao nao e essa a falha.
  Rede de RDO re-rodando pelo controller no worktree para identificar o teste que caiu. Ela
  estourou 900s na primeira tentativa — e lenta e esta disputando o banco com a Task 5, que e o
  risco de paralelismo que registrei antes.
Ruling (revisao do paralelismo, medida): as duas trilhas ficam, o paralelismo de TESTE sai.
  O risco que registrei ao abrir as trilhas se materializou, e maior do que estimei. Medido:
  a rede `-k rdo` estourou 900s numa tentativa e 2400s continua rodando; ate o `--collect-only`
  estourou 120s. Nao e so o banco — cada processo pytest importa o app inteiro (649 arquivos,
  286k linhas), e dois deles ao mesmo tempo disputam CPU e conexao.
  Efeito concreto ja pago: o implementador da Task 5 esbarrou no limite de turnos ESPERANDO uma
  rodada larga, e a Task 3 parou no meio da rede sem entregar veredito. Nenhum dos dois foi erro
  do agente — foi eu ter posto os dois para rodar suite larga ao mesmo tempo.
  Ruling: (1) as trilhas A e B continuam separadas para EDICAO, que e onde elas nao colidem;
  (2) nenhum implementador roda mais rede larga — so a suite da onda e a suite-alvo especifica,
  com contagem registrada; (3) as redes largas e o gate viram trabalho MEU, em serie, entre
  tasks, nao dentro delas.
  Porque: o paralelismo comprou tempo na edicao e perdeu mais do que isso na verificacao. Editar
  em paralelo e barato porque os arquivos sao disjuntos; testar em paralelo nao e, porque o
  recurso disputado (banco + import do app) e unico e nao se particiona.
  Custo se errado: as verificacoes largas serializam e a onda anda um pouco mais devagar no
  fim — mas anda, em vez de travar agentes em timeout.
Correcao de registro: a BASE da Task 3 nao foi 27239e83 como anotei — o worktree partiu de
  c1156cb5 (base pre-onda), que e o normal para worktree isolado. O diff dela contra 27239e83
  aparecia "deletando" scripts/medir_tenant_fantasma.py; e artefato de comparar branches
  divergentes, nao reversao. Conferido: o diff REAL (c1156cb5..77e4ab00) sao 2 arquivos,
  74 insercoes — views/rdo.py e tests/test_onda2_rotas_nao_vazam.py. E `comm` entre os conjuntos
  de arquivo das duas trilhas devolveu VAZIO: disjuntas como planejado.
Trilha B, Task 3: implementer DONE (commit 77e4ab00; 2 testes novos verdes; rede de RDO 130
  passed, 4 deselected, 0 failed). O "F" que o agente viu na primeira passada NAO reapareceu na
  rodada completa — consistente com o ruido de concorrencia que registrei, e e a evidencia que
  justifica a ruling de serializar teste.
  Merge da trilha B na branch da onda: LIMPO (commit d5491653), 2 arquivos, zero conflito.
  Conferido apos o merge que o fix do round 3 da Task 1 sobreviveu (`pares_esperados and` ainda
  presente). Review dispatched (sonnet) sobre c1156cb5..77e4ab00.
Task 5: implementer DONE (commit 42f48247; 9/9 testes novos verdes com prova de mutacao no teste
  de transporte — passa com fk_do_tenant, FALHA com a validacao de obra_id comentada; rede
  gestao_custo + arreio almoxarifado 9 passed, baseline mantida; varredura larga 29 passed,
  colhida antes do aviso de concorrencia).
  Conferido pelo controller ANTES da revisao: 18 aplicacoes do helper cobrindo os 12 sitios
  (gestao_custos novo/editar/autorizar/pagar = 8; transporte novo/editar; almoxarifado
  criar/editar), `Vehicle` usado no transporte (ruling 2 respeitada), e `financeiro_views.py`
  NAO tocado (ruling C5 respeitada).
  Achado extra do proprio implementador, dentro do sitio: em autorizar()/pagar() havia um SEGUNDO
  uso cru de banco_id indo direto para FluxoCaixa.banco_id — o filter_by(admin_id) que existia
  ali servia so para montar o texto de exibicao, nao para o valor gravado. Mesma classe, mesmo
  sitio, sem sitio novo criado. Mandei o revisor confirmar a cobertura e procurar iguais.
  Review dispatched (sonnet) sobre 44bea17f..42f48247.
Controller: rede de RDO re-rodada por MIM, em serie, sobre a mudanca da Task 3 —
  **426 passed, 2510 deselected, 1 xfailed, 0 failed**, 984s (16min24).
  Encerra a duvida do "F": nao havia regressao, era contencao de banco/CPU entre as duas trilhas.
  Nota de discrepancia registrada: o agente reportou 130 passed e eu obtive 426 na mesma
  expressao `-k rdo -m "not browser"`. A diferenca e de SELECAO, nao de resultado (os dois deram
  0 failed) — provavelmente o agente rodou antes de o merge trazer arquivos, ou colheu uma
  colecao parcial apos o timeout. Nao investigo mais: o numero que vale para o fecho e o meu,
  medido em serie e com a arvore ja mergeada.
Trilha B, Task 3: review — Spec ✅ CONFORME, qualidade APPROVED. 0 Critical, 1 Important
  (plan-mandated), 1 Minor.
  O revisor conferiu por escopo lexico que a aninhada vai so ate :3509 e que :4615 esta noutra
  funcao (`api_rdo_ultima_dados`), entao o import de views.helpers realmente nao e alvo — a
  ruling C2 foi honrada. Confirmou o guard `if admin_id_correto is None: abort(403)` (:2847-2848)
  imediatamente apos a atribuicao, cobrindo os ~20 usos seguintes porque abort levanta. E fez a
  comparacao papel a papel do caminho feliz: ADMIN e FUNCIONARIO/GESTOR/ALMOXARIFE coincidem
  exatos com o comportamento antigo; SUPER_ADMIN convergia via `get_admin_id_dinamico`, que ja
  delegava. Sem regressao para nenhum papel.
Task 3: Important (plan-mandated) — os dois testes sao `inspect.getsource` + `not in`, e NAO
  cobrem o mecanismo de seguranca real. Nao pegam reintroducao por forma sintatica diferente
  (`FALLBACK = 10; return FALLBACK`, `return 7`, o filtro de e-mail reescrito como
  `.filter(Funcionario.email == ...)`), e sobretudo NAO pegam a remocao do guard `abort(403)` do
  chamador — que e onde o fechamento de fato acontece agora, porque a funcao em si so devolve
  None. Um "clean up" futuro que apague duas linhas faz `admin_id_correto=None` fluir para as
  queries (`Obra.admin_id == None`), devolvendo zero linhas em silencio em vez de 403 — exatamente
  o que a constraint global proibe.
  Ruling: CORRIGIR, fix round 1. Consistencia: e o TERCEIRO caso do mesmo padrao nesta onda —
  o teste vacuo da Onda 1 Task 5, a minha propria ruling C1 que trocou grep de fonte por teste de
  comportamento na Task 6, e agora este. Se eu exijo comportamento da Task 6, exijo aqui.
  E a assimetria e pior aqui: a Task 3 MOVEU o ponto de fechamento da funcao para o chamador, e
  deixou o ponto novo sem cobertura nenhuma.
  Custo se errado: um teste a mais, com fixture de funcionario orfao. Barato. O risco oposto e a
  guarda sumir sem ninguem notar.
Task 3: minor (deferred): o `abort(403)` nao traz flash, enquanto o resto da mesma view usa
  flash+redirect. Conformidade estrita com o brief; polimento de UX. Triagem na revisao final.
Task 3: fix round 1/5 dispatched (implementador original retomado no worktree). FIX_BASE 77e4ab00
Task 5: review — Spec ✅ CONFORME (com a emenda governando sobre o brief base), qualidade
  APPROVED. 0 Critical, 0 Important, 1 Minor.
  O revisor nao acreditou em nada de palavra:
  - Refez a prova de mutacao num `git worktree` ISOLADO em d5491653, reverteu SO o `obra_id` para
    parse cru, e o teste ficou vermelho com `assert 1 == 0` e log `CustoObra criado para
    obra_id=147548` — a obra do tenant vitima. Depois removeu o worktree. O teste prova o que
    promete.
  - Conferiu os 12 modelos contra a `ForeignKey(...)` VIVA em models.py e o `__tablename__`, nao
    contra a minha tabela. Confirmou o `Vehicle` (frota_veiculo, :5398) contra `Veiculo`
    (veiculo, :5147) e registrou que a minha emenda estaria errada ali — o implementador parou e
    escalou em vez de adivinhar, que era o processo certo.
  - Traçou os ramos do helper com valores de borda: `0`/`'0'`/`False` -> int 0 -> query nunca casa
    (serial comeca em 1) -> 400; `'  '` -> ValueError -> 400 (nao vira vazio silencioso);
    `'12abc'` -> 400; `admin_id=0` -> `not 0` -> 403, falha fechada. Nenhum ramo permite chegar a
    um ramo mais permissivo que o pretendido.
  - Confirmou que o `banco_id` VALIDADO (nao o `int(banco_id_str)` cru) e o que chega em
    `FluxoCaixa(banco_id=...)` em :158 e :234 — o segundo uso cru que o implementador achou esta
    genuinamente fechado, e nao ha outro igual no diff.
  - Mensagem generica confirmada: `'{campo} inválido.'` e identica para id malformado, ausente ou
    de outro tenant. Sem oraculo.
Task 5: minor (deferred, mas informativo): nos DOZE sitios, o handler POST inteiro esta dentro de
  um `try/except Exception` pre-existente. Como `flask.abort()` levanta HTTPException, que e
  subclasse de Exception, o 400/403 do helper NUNCA chega ao cliente: vira rollback + flash com
  200 (gestao_custos novo/editar) ou 302 (autorizar, pagar, os dois de transporte, os dois de
  almoxarifado). Verificado como SEGURO — o rollback ocorre, a escrita forjada nao aterrissa, e o
  texto do flash continua generico. Mas o contrato documentado do helper ("aborta com 400/403") e
  invisivel na pratica. Pre-existente ao diff, e o proprio teste aceito ja tolera
  (`status_code in (400, 403, 302)`). Para o fecho da onda.
Task 5: complete (commits 44bea17f..42f48247, review clean sem fix round, 1 minor deferido)
Task 6: dispatched (sonnet — brief ja emendado com a ruling C1, que troca o grep de fonte por
  teste de comportamento). BASE d5491653 (a branch da onda, ja com a trilha B mergeada).
Padrao operacional observado (TERCEIRA vez) e corrigido no dispatch: agentes travam esperando
  rodada de teste em segundo plano. Aconteceu com a Task 5, com a Task 3 e agora com a Task 4 —
  os tres com a implementacao pronta na arvore e sem commit. A causa e a mesma que ja registrei
  (suite lenta + contencao), e a licao para os dispatches restantes e explicita: proibir suite
  larga NO TEXTO do dispatch, exigir so o arquivo da propria task em foreground, e dizer que a
  verificacao larga e minha. As tasks 6, 7 e 8 ja sairam/sairao com essa instrucao.
Trilha B, Task 4: implementer parou sem commit (implementacao na arvore do worktree:
  portal_obras_views.py modificado, tests/test_onda2_portal_nao_vaza.py criado). Retomado com
  ordem de matar a rodada de fundo, rodar so o proprio arquivo, entregar a prova de mutacao do
  filtro `tipo_compra`, e commitar. Instruido a NAO inventar numero de rede: se nao rodou, deixa
  em branco que eu rodo.
Task 3: fix round 1/5 aplicado (commit a0a2db23) — mas a PROVA DE MUTACAO FALHOU, e o
  implementador reportou isso honestamente: "com guard 3 passed, sem guard 3 passed". Ele marcou
  DONE mesmo assim, o que esta errado — prova de mutacao que nao distingue e prova que nao houve.
  Investigado por mim: o teste afirma `status_code == 302`, nao 403. E afirma 302 porque o
  `except Exception` EXTERNO de `rdo_salvar_unificado` engole a HTTPException que `abort(403)`
  levanta, e a converte em flash + redirect. Com ou sem guard sai 302: o teste nao consegue
  distinguir, por construcao.
  Medido, e e a chave: `views/rdo.py` JA USA o idioma `except HTTPException: raise` em OITO
  lugares (:303, :594, :1553, :1593, :1781, :2220, :2306, :2650) e `HTTPException` ja esta
  importado (:2). O que falta e exatamente esse re-raise no except externo desta rota.
  Ruling: fix round 2 — acrescentar `except HTTPException: raise` antes do `except Exception`
  externo de `rdo_salvar_unificado`, e o teste passa a afirmar 403 de verdade.
  Porque isso nao e alargamento de escopo: sem o re-raise, o guard que a Task 3 criou e
  INVISIVEL e INTESTAVEL — ele existe mas nao produz efeito observavel nenhum. Nao estou
  acrescentando funcionalidade, estou fazendo a funcionalidade da propria task chegar ao cliente.
  E o idioma nao e invencao minha: e o padrao do proprio arquivo, em oito ocorrencias.
  Custo se errado: a rota passa a devolver 403 onde antes redirecionava com flash — mudanca de UX
  num caminho que so um usuario orfao alcanca. Reversivel numa linha.
  NOTA DE PADRAO: e a SEGUNDA confirmacao do mesmo defeito estrutural na onda. O Minor da Task 5
  diz que nos DOZE sitios dela o `try/except Exception` engole o 400/403 do fk_do_tenant do mesmo
  jeito. O padrao "handler engole HTTPException e neutraliza abort()" e sistemico neste repo, nao
  local. Vai para o fecho da onda como achado proprio.
Task 3: fix round 2/5 dispatched. FIX_BASE a0a2db23
Task 3: fix round 2/5 aplicado (commit 2d94cae3) — prova de mutacao AGORA DISTINGUE: com guard
  403 (3 passed), com o guard comentado `AssertionError: deveria receber 403, recebeu 302`
  (FAILED). O `except HTTPException: raise` entrou em views/rdo.py:3490-3495 com comentario
  explicando por que existe. Merge da trilha B na branch: limpo (4b65200d).
  Re-review escopado despachado (sonnet) sobre 77e4ab00..2d94cae3, com pedido especifico de
  ATACAR o risco do round 2: o re-raise faz TODOS os abort() daquela rota chegarem ao cliente,
  nao so o novo 403 — o revisor tem que enumerar os outros abort() do corpo de
  `rdo_salvar_unificado` e dizer o que muda para cada um.
Trilha B, Task 4: implementer DONE (commit 63857dfb; 2 passed, prova de mutacao do filtro
  `tipo_compra` feita). Merge limpo (f13ca8eb). Conferido: filtro em :311 e
  `_get_compra_do_portal` cobrindo :536, :619, :650, :725.
  DUAS divergencias factuais do plano achadas pelo implementador: (a) a URL `/comprovante/ver`
  NAO existe — GET e POST dividem o mesmo caminho; (b) o payload de PedidoCompra do brief nao
  tinha `fornecedor_id`/`data_compra`, que sao NOT NULL. Sem eles o GET batia 404 POR ACIDENTE e
  mascarava o defeito — a mesma armadilha pela 3a vez, e desta vez o implementador a pegou
  sozinho, antes de eu perguntar. Review dispatched (sonnet).
Task 6: implementer DONE (commit af913fce; 4 testes novos, 13 passed no arquivo da onda,
  7 passed em `-k "veiculo or frota"` sem queda; prova de mutacao OK — com 'admin_id' na lista
  branca o teste de comportamento cai).
  Assinatura real encontrada: `VeiculoService.atualizar_veiculo(veiculo_id, dados, admin_id)`,
  staticmethod de classe, nao funcao de modulo — o brief nao dizia.
  DIVERGENCIA DELIBERADA da lista branca do brief, e conferida por mim: tirou `status` e
  `observacoes` (nao sao colunas de Veiculo) e acrescentou `combustivel`,
  `data_ultima_manutencao`, `data_proxima_manutencao` — que SAO colunas reais (models.py:5167,
  :5173, :5174) e campos do formulario que o brief omitia. Se ficassem de fora, parariam de
  salvar em silencio. O implementador acertou contra o brief.
  Lacuna declarada por ele: o item 3c (ponto_views) foi implementado por leitura de codigo, SEM
  teste — a emenda nao prescreveu um. Conferido que `fk_do_tenant` esta aplicado em ponto_views
  :781, :783 (api_bater_ponto) e :1016 (api_registrar_falta). Mandei o revisor pesar essa lacuna
  explicitamente, porque 3c e o achado mais grave dos tres (devolve o NOME do funcionario alheio).
  Review dispatched (sonnet) sobre f13ca8eb..af913fce.
Task 7: dispatched (sonnet — quatro correcoes locais, sem helper, por desenho do plano).
  BASE af913fce.
Trilha B, Task 4: review — Spec ✅ CONFORME, qualidade APPROVED. 0 Critical, 0 Important, 1 Minor.
  O revisor reproduziu o vazamento em worktree isolado proprio: reverteu SO o filtro
  `tipo_compra` e o teste falhou com `'INTERNA-ONDA2_PORTALA2CAFBC' is contained here` — a compra
  interna renderizada na vitrine. Rastreou ate `templates/portal/_portal_compras.html:17`, que
  imprime `{{ c.numero }}` para cada linha, mostrando POR QUE a query sem filtro chega a tela.
  Confirmou as duas divergencias que o implementador levantou: `/comprovante/ver` nao existe em
  lugar nenhum (GET e POST dividem `/obra/<token>/compra/<int:compra_id>/comprovante`, :647 e
  :715), e `fornecedor_id`/`data_compra` sao nullable=False (models.py:5754-5755).
  Confirmou que a armadilha do falso-verde foi REALMENTE resolvida, nao so alegada: o RED novo
  mostra `assert 200 == 404` — o arquivo sendo SERVIDO a cliente anonimo antes da correcao.
  Confirmou o caminho anonimo de verdade (test_client sem sessao, so token) e varreu o arquivo
  atras de outra resolucao de PedidoCompra por parametro de URL fora do helper: nao ha. As quatro
  rotas (:536, :619, :650, :725) passam pelo `_get_compra_do_portal`.
  E achou corroboracao independente: `tests/test_fase06_d2_portal_compra.py:17-21`, de uma task
  ANTERIOR e sem relacao, ja documentava no proprio docstring que `compras_resolvidas` vazava
  `tipo_compra='normal'` e que aquela task NAO o corrigiu.
Task 4: minor (deferred): `tests/test_onda2_portal_nao_vaza.py:139` faz
  `obra.portal_cliente_ativo = True`, mas a coluna real e `portal_ativo` (models.py:415). O
  atributo nao existe no modelo — a linha seta um atributo Python solto e nao faz nada. O teste
  so passa porque `portal_ativo` ja tem default True. Inofensivo hoje, mas e codigo morto que
  mascararia bug se o default mudasse. Correcao de uma linha. Para a revisao final.
Task 4: complete (commits c1156cb5..63857dfb, review clean sem fix round, 1 minor deferido)
Trilha B, Task 8: dispatched (sonnet). BASE af913fce (worktree parte da main, c1156cb5).
Task 6: review — Spec ✅ CONFORME, qualidade APPROVED. 0 Critical, 1 Important, 2 Minor.
  O revisor fez o CRUZAMENTO completo que pedi, e nao copiou do report: listou as colunas reais
  de `Veiculo` (models.py:5147-5195), listou os `name=` de `templates/veiculos_editar.html`, e
  cruzou campo a campo. Resultado: o unico campo do form fora da lista branca e `status`, que NAO
  e coluna de Veiculo (so existe `ativo`) — logo ja nao era persistido nem com o `hasattr` antigo.
  **Nenhum campo que e (a) enviado pelo form e (b) coluna real ficou de fora.** E achou a razao do
  engano do brief: o `observacoes` que o grep pega em models.py:5261 pertence a `UsoVeiculo`,
  outra classe, nao a `Veiculo`. As duas divergencias do implementador estao certas.
  Prova de mutacao refeita por ele em worktree isolado: com 'admin_id' na lista branca,
  `AssertionError: o veiculo mudou de tenant... assert 198484 == 198483`; revertido, 13 passed.
  Confirmou tambem que `api_registrar_falta` nao recebe `obra_id` do form (o servico resolve
  internamente via FuncionarioObrasPonto ja filtrado por admin_id), entao nao ha brecha ali.
Task 6: Important — o item 3c (`ponto_views.py`) nao tem NENHUM teste: nem source-guard, nem
  comportamento. E e o achado mais grave dos tres, porque `PontoService.bater_ponto_obra` devolve
  `funcionario_nome` (ponto_service.py:166) — vazamento de PII de outro tenant, nao so escrita
  errada. Cenario de regressao concreto que o revisor nomeia: alguem trocar a ordem dos argumentos
  para `fk_do_tenant(Funcionario, admin_id, funcionario_id, ...)` e nada acusar.
  Ruling: CORRIGIR, fix round 1. Consistencia com o que ja decidi duas vezes nesta onda (a ruling
  C1 desta mesma task trocou grep por comportamento; a Task 3 ganhou teste de comportamento no
  round 1). Seria incoerente exigir prova de comportamento para o veiculo — que corrompe escrita —
  e aceitar leitura de codigo para o unico que VAZA DADO PESSOAL.
  Custo se errado: um teste a mais com fixture de ponto. Barato. O risco oposto e o item mais
  sensivel da task ficar sem rede.
Task 6: minor (deferred): `ponto_views.py:796-798` e `rdo_editar_sistema.py:417-419` — o
  `abort(400)` do fk_do_tenant e engolido pelo `except Exception` do handler e vira **500** no
  ponto e flash+redirect no RDO. TERCEIRA confirmacao do padrao sistemico (Task 5 nos 12 sitios,
  Task 3 na rota de RDO, agora aqui). Sem regressao de seguranca — a escrita continua bloqueada —
  mas no ponto o resultado e 500, que e pior que redirect. Para o fecho.
Task 6: minor (deferred): o teste de RDO continua so source-guard. Dentro do escopo da emenda C1,
  que so trocou o de veiculo. Risco baixo: a correcao do RDO delega inteiramente a fk_do_tenant,
  ja provado na Task 5.
Task 6: fix round 1/5 dispatched. FIX_BASE af913fce
ERRO MEU, detectado e sem dano: despachei o fix round da Task 6 e o implementador da Task 7 ao
  MESMO TEMPO, os dois no working tree PRINCIPAL, e os dois escrevendo em
  `tests/test_onda2_tenant_nao_vaza.py`. Isso contradiz a minha propria ruling de trilhas — a
  regra era "trilhas disjuntas", e eu rodei duas coisas da MESMA trilha em paralelo.
  Verificado: nao houve escrita perdida. O commit da Task 7 (22343233) tem as 4 secoes intactas
  (Task 2 :48, Task 5 :114, Task 6 :207, Task 7 :331) e o diff nao-commitado do fix da Task 6 e
  puramente ADITIVO (+65 linhas, 0 remocoes, so as duas funcoes de ponto). Escapou porque os dois
  agentes anexaram em vez de reescrever o arquivo.
  Ruling: nao repetir. Daqui ate o fecho, dentro de uma trilha e um agente por vez. O paralelismo
  que sobrevive e so entre trilhas com arquivos disjuntos, e o arquivo de teste compartilhado e
  justamente o que nao e disjunto dentro da trilha A.
  Custo se tivesse dado errado: perda silenciosa dos testes de uma das duas tasks, que so
  apareceria no gate ou nunca.
Task 7: implementer DONE (commit 22343233; 15 passed no arquivo da onda, 7 passed em
  test_fase06_d4_plano_contas_por_tenant; RED literal citado com as duas asserções).
  As quatro correcoes conferidas por mim: 3a o join agora leva `admin_id` (PK composta confirmada
  em models.py:3247-3267); 3b `Proposta`/`NotaFiscal` validados por `filter_by(id=origem_id,
  admin_id=admin_id)` ANTES de chamar `contabilizar_*`, que carregavam por PK pelada;
  3c o dedup de NF ganhou `admin_id` (que ja estava em escopo como parametro de
  `processar_xml_nfe` — nao precisou virar parametro novo); 3d `ConfiguracaoHorario` escopada e
  `obra_id` do JSON validado com fk_do_tenant (ponto_views:1153).
  Prova de mutacao entregue para 3a e 3c.
  LACUNA que eu vou levar a revisao: 3b e 3d NAO tem teste nenhum — os dois testes da task sao
  source-guard e cobrem so 3a e 3c. E 3b e justamente o que o plano marca como "quando a Onda 4
  consertar contabilidade_utils.py:221, este vira EXPLORAVEL. Nao adie."
  QUARTA confirmacao do padrao sistemico: o implementador reportou que o `except Exception` de
  `api_salvar_configuracao` converte o BadRequest do fk_do_tenant em 500. Mesma familia dos
  achados das Tasks 3, 5 e 6.
Task 6: fix round 1/5 aplicado (commit 4b55a2d3) — dois testes de comportamento para o 3c:
  `test_bater_ponto_rejeita_funcionario_e_obra_de_outro_tenant_sem_vazar_nome` e
  `test_registrar_falta_rejeita_funcionario_de_outro_tenant`. Diff conferido por mim ANTES do
  commit dele: puramente aditivo, +65 linhas, zero remocoes — nao clobberou a Task 7.
  Re-review a despachar.
Trilha B, Task 8: implementer DONE (commit 1a880748; 3 testes, RED confirmado nos tres pelo motivo
  certo — inclusive o de 4b mostrando o Cliente DUPLICADO sendo criado de fato antes da correcao).
  Escreveu, alem dos dois testes do brief, o teste de COMPORTAMENTO para 4b que eu pedi na ruling
  (o brief nao tinha nenhum para 4b). Provas de mutacao para 4a e 4b, com restauracao verificada
  por `diff` contra backup.
  Grep do Step 3 refeito por ele antes de apagar: so as duas definicoes em auth.py:47/58 e o teste
  novo. Zero chamadores — confirma a minha medicao de 26/08.
  Decisao dele que confere: manteve o import de `TipoUsuario` em auth.py porque
  `super_admin_required`/`admin_required` ainda o usam. O brief mandava conferir antes de remover;
  ele conferiu e nao removeu. Certo.
  Conferido por mim: os dois helpers sumiram de auth.py (grep -c = 0), diff de 4 arquivos,
  disjunto do que ja estava na branch. Merge limpo (90e93b2a).
  Review dispatched (sonnet) sobre c1156cb5..1a880748, com pedido de REFAZER o grep de
  consumidores ampliado (py + html + chamada dinamica), porque um chamador nao encontrado vira
  AttributeError em producao, e de checar se o `ValueError` novo do 4b e tratado nos chamadores
  (event_manager.py:1244) ou vira 500.
TODAS AS 8 TASKS IMPLEMENTADAS. Faltam: re-review do fix da Task 6, reviews das Tasks 7 e 8,
  o gate completo (meu, em serie), e os itens do Fecho da Onda.
Task 7: review — Spec ✅ CONFORME nos quatro pontos, qualidade NEEDS FIXES. 0 Critical,
  2 Important, 1 Minor.
  Verificacoes que ele fez e sustentam a aprovacao tecnica:
  - 3a: PK composta de PlanoContas confirmada em models.py:3260-3266 (dois primary_key=True), e
    `grep "join(PlanoContas"` devolve UMA ocorrencia — a corrigida. Os outros ~9 usos de
    PlanoContas no arquivo ja sao `filter_by(admin_id=...)`. Nao sobrou join irmao.
  - 3b: leu `processar_integracao` inteiro (:1363-1399). Tem exatamente TRES ramos de `tipo`.
    Os dois que carregam documento por PK vinda do request foram validados; o terceiro
    (`folha_pagamento`) recebe o admin_id do CHAMADOR como parametro e nunca toca documento por
    PK alheia — nao precisava. Nenhum ramo ficou sem guarda.
  - 3d: `RegistroPonto.admin_id` e nullable=False (models.py:823), entao escopar por
    `registro.admin_id` nao reabre fail-open.
  - Prova de mutacao refeita por ele em worktree isolado: revertendo 3a, falha com "o join de
    PlanoContas ainda ignora admin_id"; revertendo 3c, falha com "dedup de NF ainda e global
    entre tenants". Restaurados, 15/15.
Task 7: 2 Important — 3b e 3d nao tem teste NENHUM, e ele varreu `tests/` inteiro: zero hits para
  `processar_integracao`, `contabilizar_proposta_aprovada`, `contabilizar_entrada_material`,
  `api_salvar_configuracao`, `ConfiguracaoHorario`. Nao e "faltou no diff", e nao existe em lugar
  nenhum do repo.
  E ele CORRIGIU a minha leitura do 3d: eu tratei como risco futuro igual ao 3b. Nao e. O 3b esta
  inerte hoje (o bug da Onda 4 barra a escrita antes) e vira exploravel quando a Onda 4 consertar.
  O 3d fecha um buraco ATIVO AGORA: `Obra.id` e PK global auto-increment, e antes deste diff
  `api_salvar_configuracao` aceitava `obra_id` cru do JSON — qualquer admin autenticado apontava
  escrita de configuracao para obra de outro tenant.
  Ruling: CORRIGIR, fix round 1. Mesmo criterio que apliquei na Task 3 (guard sem teste) e na
  Task 6 (3c sem teste). A regra da onda virou: correcao de tenant sem teste de comportamento nao
  fecha. Aplicar em duas tasks e abrir excecao na terceira seria arbitrario.
  Custo se errado: dois testes de rota a mais. O risco oposto: o 3b e a UNICA barreira futura
  contra escrita contabil cross-tenant, e um "clean up" dos blocos duplicados de `documento = ...`
  o apaga sem nada acusar.
Task 7: minor (deferred): `ponto_views.py:1145` — QUINTA ocorrencia do padrao sistemico; aqui o
  abort(400) vira 500 com `str(e)` na mensagem.
Task 7: nota do revisor: `ponto_views.py` nao esta no cabecalho `Files:` do brief (so
  `ponto_service.py:264`), mas e o arquivo que recebe o `obra_id` do JSON — toca-lo era necessario
  para cumprir a prosa do proprio brief. Nao e desvio.
Task 7: fix round 1/5 dispatched. FIX_BASE 22343233
Task 3: fix rounds 1-2 re-review — ADDRESSED, zero breakage novo.
  Prova de mutacao refeita pelo revisor em worktree isolado contra um Postgres EFEMERO criado so
  para o experimento (nao tocou o banco do ambiente nem a arvore do repo): com guard, 1 passed
  (403); com as duas linhas comentadas, `AssertionError: deveria receber 403, recebeu 302`, e o
  log mostra `admin_id determinado de forma robusta: None` seguido de status=302.
  ATAQUE AO RISCO DO ROUND 2 (que eu pedi explicitamente): ele levantou por busca textual E POR
  AST todos os `abort()` do corpo de `rdo_salvar_unificado` (:2801-3513). Achou **um unico** — o
  proprio guard da Task 3 (:2848). Nao ha outro abort(), nem get_or_404, nem nada que produza
  HTTPException nesse try. O `funcionario_required` roda no DECORADOR, fora do try, e usa
  flash+redirect, nao abort. Logo o `except HTTPException: raise` nao muda o comportamento de
  nenhum outro fluxo — nao existe outro para mudar. O meu receio estava correto em principio e
  vazio em fato, e agora esta medido em vez de suposto.
  Conferiu tambem o unico chamador interno (`funcionario_criar_rdo` :3516-3520, que so faz
  `return rdo_salvar_unificado()`, sem try proprio) e CINCO arquivos de teste que tocam a rota
  (test_arreio_custo_rdo_rotas, test_rdo_legacy_endpoints_horas, test_fase5_matriz_rdo,
  test_rota_rdo_salvar_unica, test_b5_rdo_crud_url_map): nenhum dependia do redirect antigo — os
  que aceitam 302 usam tenant valido, onde o guard nem dispara.
Task 3: minor (deferred, de processo): os fix reports dos rounds 1 e 2 nao foram anexados ao
  task-3-report.md; ficaram so nas mensagens de commit. Nao bloqueou a verificacao (o revisor
  reproduziu tudo por experimento), mas o relatorio formal ficou incompleto.
Task 3: observacao herdada que o revisor topou por acaso e vale registrar: rodar
  `db.create_all()`/`executar_migracoes()` via app.py contra banco vazio reproduz o DEADLOCK ja
  descrito em tests/conftest.py (uma migracao fica "idle in transaction" segurando lock, a
  seguinte trava no ALTER TABLE). Pre-existente e ja documentado pela equipe; so confirmacao.
Task 3: complete (commits c1156cb5..2d94cae3, review clean apos 2 fix rounds, 2 minors deferidos)
Task 6: fix round 1/5 re-review — ADDRESSED. As tres assercoes do contrato conferidas uma a uma:
  rejeicao (:292-293), nada gravado (:299-301, count de RegistroPonto do funcionario B = 0), e a
  que fecha o vazamento — `nome_b = f'Funcionario {b.marca}'` DINAMICO, do tenant real, com
  `assert nome_b not in corpo` (:295-297). O revisor confirmou que ela pega vazamento tanto na
  `message` quanto no `funcionario_nome` da resposta, e que a construcao do f-string a torna
  segura contra nome vazio — que era a minha preocupacao explicita.
  Prova de mutacao refeita por ele em worktree isolado: com fk_do_tenant comentado,
  `AssertionError: status inesperado: 200` (o POST forjado ACEITO); restaurado, passa.
  `git diff --stat` confirma SO o arquivo de teste, +65, nenhum arquivo de producao. Diff aditivo,
  nenhum teste de outra task removido ou alterado.
Task 6: complete (commits f13ca8eb..4b55a2d3, review clean apos 1 fix round, 2 minors deferidos)
Trilha B, Task 8: review — Spec ✅ CONFORME nos tres pontos, qualidade APPROVED.
  ZERO achados: nenhum Critical, nenhum Important, nenhum Minor. Unica task da onda assim.
  Verificacoes independentes que ele fez:
  - 4c: refez o censo de consumidores AMPLIADO como pedi — alem de .py/.html, procurou .js,
    `getattr(auth, ...)` dinamico, literal de string 'get_tenant_filter'/'can_access_data', e
    `from auth import *`. Zero consumidores reais. A remocao e segura.
  - 4b: auditou os TRES call sites reais que passam `cliente_id` (event_manager.py:1244 via
    propagar_proposta_para_obra, views/obras.py:257 e :960) e confirmou que os tres estao dentro
    de try/except que faz rollback + flash/jsonify — o `ValueError` novo NAO vira 500 em lugar
    nenhum. Era a minha pergunta 3.
  - 4a: confirmou que o modulo tem exatamente DUAS rotas e as duas resolvem tenant so por
    `_admin_id()`. E que `marcar_subatividade_revisada` (o pior caso do brief) nao alcanca mais a
    mutacao com tenant nao resolvido. Confirmou tambem que ali o 404-vs-403 esta certo: recurso de
    outro tenant cai em `.first_or_404()`, e o 403 e so para "nao resolvo o SEU tenant".
  - Prova de mutacao refeita em worktree isolado: revertendo 4b, o teste falha com DID NOT RAISE
    E os logs mostram um `Cliente` DUPLICADO criado no admin_id errado (198660, o tenant alheio) —
    reproduzindo o bug descrito, nao so a ausencia de excecao.
Task 8: complete (commits c1156cb5..1a880748, review clean sem fix round, 0 minors)

## FECHO — item "um resolvedor so": NAO CUMPRIDO. Achado grande, medido.

O plano fecha a onda mandando conferir que sobrou UM resolvedor. Rodei o grep e a resposta e NAO.
Ha ~30 definicoes de `get_admin_id`/`_admin_id`/`get_admin_id_robusta` fora de `utils/tenant.py`.

Amostrei 15 e classifiquei: 4 DELEGAM (api_funcionarios, compras_views, cronograma_views,
medicao_views) e 11 tem LOGICA PROPRIA (analytics_preditivos, alimentacao_views, clientes_views,
crm_views, contabilidade_views, equipe_views, dashboards_especificos, views/metricas_views,
views/orcamentos_views, views/catalogo_views, subempreiteiros_views).

Li tres delas e o padrao das copias e sempre o mesmo:
    if current_user.admin_id: return current_user.admin_id
    return current_user.id
Comparado ao canonico (`utils/tenant.py:15-31`: ADMIN/SUPER_ADMIN -> id; TODO o resto ->
admin_id), a divergencia por papel e:
  - ADMIN / SUPER_ADMIN: so divergiria se tivessem `admin_id` preenchido. MEDIDO no banco de dev:
    **0 casos**. Nao e a exposicao.
  - Qualquer outro papel com `admin_id` NULL: o canonico devolve **None** (falha fechada, vira
    403). A copia devolve **`current_user.id`** — um TENANT FANTASMA.
E o mesmo defeito que a Task 2 consertou no `multitenant_helper`, vivo em ~11 outros modulos.
MEDIDO no banco de dev: **263 usuarios nao-admin com admin_id NULL**. Ressalva honesta: o banco
de dev e ~99% residuo de suite, entao 263 mede a FORMA (o caminho e alcancavel, o codigo e
identico), nao o volume de producao.

Ruling: NAO entra nesta onda, e nao invento uma nona task.
  (a) Esta fora do escopo declarado: a Onda 2 tem 14 achados nomeados, e nenhum deles e este.
  (b) E ~11 modulos, e a Onda 2 ja gastou 8 tasks e 5 fix rounds.
  (c) Alargar escopo desta ordem e decisao do usuario, nao minha.
Vai para o usuario como achado nomeado e medido, junto com o irmao dele (os 225 usos sem guarda
de None nos 8 importadores, do review da Task 2). Sao a MESMA familia: falha aberta quando o
tenant nao resolve.
Custo se errado: o buraco continua aberto. Mitigado por: nao e novo, nao foi introduzido por esta
onda, e a exposicao e linha orfa (admin_id NULL), nao linha de outro tenant.
Task 7: fix round 1/5 aplicado (commit 8708982e; 19 passed no arquivo da onda — 17 + 2 novos).
  Codigo de producao INTOCADO nesta rodada (so o arquivo de teste, +100 linhas, 0 remocoes).
  Provas de mutacao nas duas direcoes, com restauracao verificada por `git diff` vazio:
  - 3b: revertida a guarda `filter_by(id=origem_id, admin_id=admin_id)` -> `assert 200 == 400`.
  - 3d: revertido o `fk_do_tenant` de api_salvar_configuracao -> `status inesperado: 200`.
  Re-review escopado despachado (haiku) sobre 90e93b2a..8708982e, com dois contextos explicitos
  para o revisor nao reportar como defeito o que eu mandei fazer (o 500 esperado no 3d, e o spy
  exigido no 3b), e com a instrucao de NAO rodar suite larga porque o gate vem logo depois.
Task 7: fix round 1/5 re-review — os DOIS achados ADDRESSED.
  3b: o teste cobre os DOIS ramos (proposta_aprovada e entrada_material) e usa `mock.patch` como
  spy afirmando `not espia.called` — e a verificacao que eu exigi, e nao uma assercao sobre a
  escrita (que ficaria verde pelo motivo errado, ja que o defeito da Onda 4 barra a gravacao por
  outro caminho). Mutacao: revertida a guarda -> status 200 onde se espera 400, teste falha.
  3d: alem do status, afirma `ConfiguracaoHorario.query.filter_by(obra_id=obra_b_id).count() == 0`
  — prova que nada e gravado para a obra alheia. Mutacao: revertido o fk_do_tenant para
  `data.get('obra_id')` cru -> status 200, teste falha.
  Diff puramente aditivo, producao intocada, secao da Task 6 preservada, commit em portugues.
Task 7: complete (commits 4b65200d..8708982e, review clean apos 1 fix round, 1 minor deferido)

## AS 8 TASKS ESTAO COMPLETAS. Gate completo iniciado pelo controller, em serie, HEAD 8708982e.

## GATE COMPLETO (controller, em serie, HEAD 8708982e)
**1 failed, 2752 passed, 6 skipped, 201 deselected, 2 xfailed** em 2580s (43min). Exit 1.
Regua da onda era 2726 (medida no fecho da Onda 1). +26 verdes = os testes desta onda.

FALHA UNICA: `tests/test_triagem_rotas_fechadas.py::test_portal_serve_comprovante_com_token_valido`
Investigado por mim, e NAO e ruido de concorrencia (o gate rodou sozinho):
- A fixture `cenario_comprovante` (:121-127) cria o `PedidoCompra` SEM `tipo_compra`.
- `PedidoCompra.tipo_compra` tem `default='normal'` (models.py:5777).
- Logo a compra da fixture e INTERNA, e o teste (:133-138) afirma
  `assert r.status_code == 200` e `r.data == conteudo` — isto e: afirma que o portal SERVE o
  comprovante de uma compra interna a um anonimo portador de token.
- A Task 4 fez `ver_comprovante` passar por `_get_compra_do_portal`, que exige
  `tipo_compra='aprovacao_cliente'`. Agora devolve 404.
VEREDITO: o teste CODIFICAVA O VAZAMENTO. A Task 4 esta certa; o teste e que afirma o defeito
como comportamento esperado. E o mesmo formato do D2 da Onda 1
(`tests/test_b5_fluxo_gemeos_e_orfaos.py:100`).
BLOQUEIO: a constraint global do plano diz "Nenhum teste verde e alterado sem decisao humana
registrada. Vale para o D2 e para qualquer outro que apareca no caminho." Este e "qualquer outro".
Levado ao usuario com recomendacao, em vez de eu decidir sozinho.
DECISAO HUMANA REGISTRADA (26/08, usuario): corrigir a FIXTURE, opcao (a).
  `tests/test_triagem_rotas_fechadas.py` passa a criar o PedidoCompra com
  `tipo_compra='aprovacao_cliente'`. A correcao da Task 4 FICA; o teste deixa de afirmar o
  vazamento e passa a provar o que o nome dele promete — portal serve comprovante com token
  valido, para uma compra que o portal de fato oferece.
  O usuario NAO pediu o teste do inverso (compra interna -> 404), que era a opcao (b). Registro
  que essa metade ja esta coberta em `tests/test_onda2_portal_nao_vaza.py`, escrito pela Task 4:
  `test_comprovante_de_compra_interna_nao_e_servido_a_anonimo`. Entao as duas metades ficam
  fixadas de qualquer jeito, so que em arquivos diferentes.
  Fix despachado a um implementador (nao corrijo no controller: pularia a revisao).

## GATE FINAL (controller, em serie, apos o fix da fixture) — VERDE
**2753 passed, 6 skipped, 201 deselected, 2 xfailed, 0 failed**, 2363s (39min23), EXIT 0.
Regua da onda: 2726 (medida no fecho da Onda 1). +27 verdes, todos escritos por esta onda.
Nenhum teste antes verde caiu — a unica queda foi investigada, levada ao usuario, e era um teste
que afirmava o vazamento como esperado.
Fix da fixture: commit 97a63ea9 (15 passed no arquivo; os outros 2 testes que usam a mesma
fixture conferidos um a um pelo implementador e intocados).
Doc de auditoria: commit 0139dcb7 — 15 achados marcados inline com o commit que fechou cada um,
mais a nota de fecho com os TRES achados fora de escopo, medidos.

## REVISAO FINAL DA BRANCH (21 commits, 23 arquivos) — READY TO MERGE **WITH FIXES**
0 Critical. 1 Important. 6 Minor. Triagem dos 8 minors deferidos entregue um a um.
O revisor mediu em vez de ler: levantou os 23 call sites de fk_do_tenant por AST e confirmou
ordem posicional identica, `campo=` sempre keyword, ZERO retornos ignorados, ZERO argumentos
trocados. Confirmou que nenhuma rota ficou menos protegida (as quatro que mudaram de forma
ESTREITARAM o conjunto de linhas). Refez o censo de consumidores do auth.py. Cruzou a lista
branca de veiculo contra modelo E template de novo.
E corrigiu uma imprecisao MINHA sobre o achado (b): eu disse que o helper velho devolvia
`current_user.id` para orfao. Errado — ele fazia `getattr(current_user, 'admin_id',
current_user.id)`, e `getattr` com default so dispara quando o atributo NAO EXISTE, nao quando e
None. Entao FUNCIONARIO orfao JA devolvia None antes da onda. A Task 2 nao criou classe nova de
exposicao; so acrescentou dois papeis ao mesmo caminho. A ruling continua certa, o argumento
estava impreciso.

### I1 (Important, NOVO) — a Task 8 matou um fallback vivo em `views/obras.py`
`services/cliente_resolver.py:64` passou a LEVANTAR ValueError onde antes devolvia None. Os dois
callers de `views/obras.py` (:263-272 e :967-973) foram escritos contando com o None e DIZEM isso
no comentario ("o resolver retorna None nesse path — entao caimos no fallback").
Consequencias: (1) o bloco de fallback virou codigo morto; (2) regressao funcional real — obra
cujo Cliente foi apagado, usuario digita nome novo (fluxo suportado, obra_form.html:942), submete:
antes salvava, agora o ValueError sobe ao `except Exception` de :399 e a EDICAO INTEIRA e
descartada, com a mensagem `Erro ao editar obra: cliente_id=123 nao pertence ao tenant 45` na
tela do usuario.
Nenhuma revisao de task viu porque exige ler o CALLER num arquivo que task nenhuma tocou. A
revisao da Task 8 auditou os call sites so para responder "o ValueError vira 500?" (nao vira).
Ruling: corrigir com a opcao (a) do revisor — `try/except ValueError` nos dois sitios de
`views/obras.py`, caindo para o fallback, e o comentario reescrito.
Porque nao a opcao (b) (apagar o fallback): as duas intencoes sao legitimas e diferentes. O
racional da Task 8 e sobre `event_manager.py:1244`, onde `proposta.cliente_id` e FK de sistema e
cair no difuso criava Cliente duplicado sem log — la o ValueError DEVE subir. Em `views/obras.py`
o fallback e afordancia de UX deliberada, documentada no template. Tratar no caller preserva as
duas; apagar o fallback sacrifica a segunda por causa da primeira.
Custo se errado: um `except ValueError` a mais em dois sitios de CRUD. O risco oposto ja esta
medido: edicao de obra descartada em silencio para o usuario.
Fix wave da revisao final aplicada (commit 4dbc2a49): os tres itens num commit so.
  Conferido por mim na arvore antes do commit: `except ValueError` em views/obras.py:265 e :976
  (os outros quatro do arquivo sao pre-existentes), `obra.portal_ativo` no teste do portal,
  `obrigatorio=True` em transporte_views:164 e :387. Zero toque em cliente_resolver.py e
  event_manager.py, que eram proibidos.
  Contagens obtidas: portal 2 passed, falha_fechada 3 passed.
  O implementador NAO rodou `-k obra` (matou aos 2min por instrucao minha) e **explicitamente se
  recusou a inventar contagem** — disse "nao tenho contagem, nao estou inventando numero". E
  declarou que a prova do item 1 e de LEITURA, nao de execucao: rastreou que o ValueError e
  capturado e reabre o fallback, mas nao montou teste fim-a-fim.
  Registro a lacuna: o caminho do item 1 (obra com cliente_id alheio + nome digitado -> fallback
  resolve e salva) NAO tem cobertura automatizada. O gate completo cobre "a correcao nao quebrou
  nada"; nao cobre "a correcao faz o que promete". Vai para o fecho como item nomeado.
Fix wave — re-review escopado: os TRES achados ADDRESSED, zero breakage novo.
  E a lacuna que o implementador declarou honestamente (prova do I1 so por leitura) foi FECHADA
  pelo revisor, que a executou:
  - Montou worktree isolado em 4dbc2a49, escreveu um teste descartavel com o arreio do proprio
    repo (dois_tenants + login), e fez POST em /obras/editar/<id> com `cliente_id` do tenant B e
    nome novo em `cliente_busca`, logado como tenant A.
    Resultado: STATUS 302, LOCATION /obras/detalhes/152764, e `obra.cliente_id` apontando para um
    Cliente NOVO do tenant A (admin_id 204876), sem vazar o id do tenant B.
  - E rodou o MESMO teste contra o commit PRE-FIX (0139dcb7) como discriminador: reproduziu o bug
    verbatim — `ERRO GERAL NA EDICAO: cliente_id=149167 nao pertence ao tenant 204876`, HTTP 200,
    edicao descartada, usuario preso no formulario.
    Isso e o padrao-ouro: nao so "passa agora", mas "falhava antes, pelo motivo exato descrito".
  - Confirmou que o `try/except ValueError` envolve APENAS a chamada que passa `cliente_id=`, e
    que `cliente_resolver.py` tem exatamente UM `raise ValueError` no modulo inteiro — entao nao
    ha outro ValueError legitimo sendo engolido. Era a minha preocupacao explicita.
  - Confirmou zero diff em services/cliente_resolver.py e event_manager.py (proibidos).
