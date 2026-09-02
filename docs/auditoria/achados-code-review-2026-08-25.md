# Achados do code review de 2026-08-25 — o app inteiro, por módulo

> **O que é:** o resultado bruto da varredura pedida em 25/08 ("code review no app
> inteiro"), fatiada por módulo. Cada achado traz `arquivo:linha` e o cenário de
> falha. Quando foi escrito, **nenhum tinha sido corrigido** — este documento é
> insumo, não conserto.
>
> **Atualização de 2026-08-25 — Onda 1 fechada.** Os cinco achados de parser de
> dinheiro estão corrigidos e marcados ✅ inline, na branch
> `sdd/onda-1-parser-de-dinheiro` (13 commits, gate verde: 2726 passed). Os cinco
> parsers artesanais viraram um só, `utils/decimal_br.parse_decimal_br`, que
> **recusa** o ambíguo (`'1.500'`) em vez de escolher sozinho entre R$ 1,50 e
> R$ 1.500,00. Dois testes de varredura guardam a porta: se um sexto parser
> nascer, ou se um espaço invisível voltar como literal, eles falham.
>
> **Como foi feito:** a árvore está limpa e `main` não tinha diff contra si mesmo,
> então cada passada leu os arquivos-alvo inteiros, não um diff. As afirmações
> foram conferidas contra `models.py`, os chamadores reais e a versão instalada do
> SQLAlchemy (2.0.41).
>
> **Marcas:** 🔴 alto · 🟡 médio · ⚪ baixo


> **26/08 — a Onda 2 fechou os 15 achados de isolamento de tenant.** Marcados inline
> com o commit que fechou cada um. A raiz era uma só: `utils.tenant.get_tenant_admin_id`
> é o resolvedor correto, e `multitenant_helper.get_admin_id` era uma cópia que divergia
> nos papéis GESTOR_EQUIPES e ALMOXARIFE — mandando-os para um tenant que não existe —
> importada por oito módulos, dois deles sob o nome do resolvedor certo.
>
> Gate ao fim da onda: **2752 passed** (régua era 2726). Uma falha apareceu e não era
> ruído: `test_portal_serve_comprovante_com_token_valido` **afirmava o vazamento como
> comportamento esperado** — a fixture criava compra interna (`tipo_compra` default
> `'normal'`) e exigia que o portal servisse o comprovante dela a um anônimo com token.
> Corrigida a fixture por decisão do dono do repositório (commit `97a63ea9`), não em
> silêncio.
>
> ⚠️ **Dois achados FORA do escopo desta onda, medidos e em aberto:**
> 1. Restam ~11 resolvedores de tenant com lógica própria (`clientes_views`, `crm_views`,
>    `equipe_views`, `views/metricas_views`, `subempreiteiros_views` e outros). O padrão
>    deles é `admin_id if set else current_user.id` — que para usuário sem `admin_id`
>    devolve **um tenant fantasma** onde o canônico devolve `None` e falha fechado. É o
>    mesmo defeito que a Task 2 fechou, vivo noutros módulos. Medido no banco de dev:
>    263 usuários não-admin com `admin_id` NULL (dev é ~99% resíduo de suíte, então isso
>    mede a forma, não o volume de produção).
> 2. Os 8 módulos que importam `multitenant_helper` somam **225 usos de `admin_id` em
>    query e ZERO guardas de `None`**. Com tenant não resolvido viram `admin_id IS NULL`.
> 3. Padrão sistêmico confirmado em **cinco** pontos independentes: o `try/except Exception`
>    dos handlers engole a `HTTPException` de `abort()`, então o 400/403 das guardas novas
>    nunca chega ao cliente (vira flash+redirect, ou **500** em `ponto_views`). Seguro — a
>    escrita é bloqueada e a mensagem continua genérica — mas o contrato documentado é
>    ficção nesses pontos. `views/rdo.py` já usa `except HTTPException: raise` em 8 lugares;
>    o idioma existe e não foi aplicado nos demais.


> **27/08 — a Onda 3 fechou os 16 achados de valor duplicado/evaporado.** Marcados
> inline com o commit que fechou cada um: `quantidade_disponivel` do almoxarifado
> passa a ser mantida por um ponto único (Tasks 1-3), a disciplina "contar filho,
> nunca somar valor" do `GestaoCustoPai`×filhos chegou a reembolso e à migração de
> contas a pagar (Tasks 4-5), o card e o detalhe do financeiro pararam de discordar
> (Task 6), os gêmeos de reembolso ficaram conscientes de estado (D2/Task 3.6), a
> ressalva de compra parou de zerar parcelas e o lote ganhou guarda de fechamento
> (Task 7), a folha parou de dobrar no reprocesso — **a automação A12 fecha junto**
> (Task 8), as quatro dobras de mão de obra da folha foram cortadas (Task 9), e o
> ponto/RDO pararam de perder e de sobre-cobrar custo (Task 10). Executada em 27/08
> via subagent-driven development em 5 lanes paralelas, 10/10 tasks + o mini-plano
> D2, 6 rounds de correção, review final da branch inteira limpa (zero Critical).
>
> Gate ao fim da onda: **2798 passed, 6 skipped, 201 deselected, 2 xfailed** (régua
> antiga: 2560 passed). Dos +238 verdes a mais, ~48 são os testes novos desta onda
> (`test_onda3_*.py`); o resto é drift da régua — ela foi escrita em 23/08, **antes**
> de a Onda 2 e o trabalho de medição do tenant fantasma entrarem na `main` em 26/08.
>
> ⚠️ **Cinco achados novos, descobertos durante a própria execução da Onda 3 — não
> estavam na varredura de 25/08.** Registrados em
> "Achados novos da execução da Onda 3 (27/08)", no fim deste documento.


> **28/08 — a Onda 5 fechou os 10 achados de estado recusado que ainda era gravado.**
> Marcados inline com o commit que fechou cada um: o traceback saiu da resposta HTML
> em `/ponto/` e `/equipe/alocacao-principal` (Task 1), a garantia de rollback em
> `4xx` passou a morar no decorador `_com_undo` em vez de em cada `return`
> (Task 2), o portal do cliente deixou de ser administrável por qualquer
> FUNCIONARIO (Task 3), as duas entregas da Fase 6 chegaram à tela (Task 4), quatro
> defeitos de progresso apagado/retrocesso foram cada um para seu próprio commit
> (Task 5), os RDOs pararam de quebrar, duplicar ou perder dado (Task 6), frota,
> transporte e reembolso pararam de regredir odômetro, perder passageiro e vazar
> `main_bp` (Task 7), e o índice `uq_contrato_versao_vigente` passou a concordar
> com as queries (Task 8). Executada solo, task a task, via
> superpowers:executing-plans, 27-28/08, TDD com o RED citado em todos os 8/8
> tasks + 1 fecho-fix, 12 commits. Teste desta onda:
> `tests/test_onda5_recusado_nao_grava.py` (38 testes).
>
> Duas decisões explícitas: **o geofencing consultivo vira impositivo** (obra
> cercada e sem coordenada agora recusa o ponto; commit `7ec18fe0`) e **o índice
> `uq_contrato_versao_vigente` ganha `admin_id`** em vez de as queries o perderem
> (migration 315, commit `ae4e4191`) — ambas em
> `docs/superpowers/plans/2026-08-25-onda-5-o-recusado-para-de-ser-gravado.md`,
> seção "Fecho da onda".
>
> ⚠️ **Três achados novos, descobertos durante a própria execução da Onda 5 — não
> estavam na varredura de 25/08.** Registrados em
> "Achados novos da execução da Onda 5 (28/08)", no fim deste documento.
>
> ⚠️ **Fecho-fix fora do escopo original das 10:** o grep de fecho achou a mesma
> classe de vazamento de traceback da Task 1 viva em `error_handlers.py` (handler
> global) e `production_routes.py`, para todo `500` do app inteiro — não só
> `/ponto/`. Corrigido e env-gated como `main.py`, commit próprio `356c2cf9`.


## Placar

| Módulo | 🔴 | 🟡 | ⚪ | Passada |
|---|---|---|---|---|
| Fase 6 (25 commits não empurrados) | 1 | 2 | 6 | ✅ |
| Financeiro + contabilidade | 10 | 5 | 12 | ✅ |
| RDO | 4 | 5 | 3 | ✅ |
| Cronograma + medição + EVM | 2 | 4 | 1 | ✅ |
| Compras + almoxarifado + alçadas | 6 | 7 | 2 | ✅ |
| Obras + propostas + orçamento | 1 | 2 | 1 | ✅ |
| Portal do cliente + auth + multitenant | 2 | 6 | 4 | ✅ |
| Pessoas + ponto + folha | 4 | 7 | 4 | ✅ |
| Frota + transporte + alimentação + reembolso | 3 | 6 | 1 | ✅ |
| Núcleo + models + event_manager | 0 | 1 | 2 | ✅ |
| **Total** | **33** | **45** | **36** | **114** |

---

## 1. Fase 6 — os 25 commits que ainda não foram empurrados

🔴 ✅ **CORRIGIDO** (Onda 1, Task 2 — commit `169ddd68`). **`views/aditivos_views.py:102` — o parser BR infla o contrato 100×.**
`valor.replace('.', '').replace(',', '.')` num campo `<input type="text"
inputmode="decimal">` (`templates/aditivos/form.html:31`). Digitar `150000.00` —
o que um teclado numérico produz — vira `"15000000"`. O aditivo nasce valendo
R$ 15.000.000,00 e, na aprovação, `abrir_versao` grava isso em
`obra.valor_contrato` **e** `lancar_delta_contrato` lança ~R$ 14,85M de receita no
razão. Não há sanidade entre o formulário e o razão. Já existe
`_parse_br_decimal` em `views/orcamentos_views.py` — use-o, ou rejeite string com
os dois separadores.

🟡 **`handlers/propostas_handlers.py:166` — o portal do cliente vira beco sem saída.**
A guarda de redução levanta `ValueError` dentro de `_propagar_proposta_para_obra`,
que sobe por `emit(raise_on_error=True)`. No portal
(`propostas_consolidated.py:2680-2691`) um `except Exception` pelado captura, faz
rollback e mostra *"Tente novamente em instantes"*. Tentar de novo **nunca** pode
dar certo. A mensagem útil ("estorne a medição antes do aditivo") só vai para o
log. Mesma forma na rota interna (`propostas_consolidated.py:1138`).

🟡 **`templates/obras/detalhes_obra_profissional.html:1316` ✅ **CORRIGIDO** (Onda 5, Task 8 — commit `ae4e4191`) — 500 onde havia degradação.**
`app.py:940-953` engole de propósito a falha de registro do `aditivos_bp` (loga e
segue de pé). Mas a página de detalhe faz `url_for('aditivos.listar', ...)` sem
guarda: se o blueprint não registrar — o cenário que o `app.py` foi escrito para
sobreviver — toda obra com `valor_contrato > 0` dá `BuildError` 500.
`templates/obra_form.html` usa href literal e está safe.

⚪ `views/aditivos_views.py:147` ✅ **CORRIGIDO** (Onda 5, Task 8 — commit `ae4e4191`) — o reformat de moeda é aplicado à frase inteira:
o ponto final vira vírgula.
⚪ `views/aditivos_views.py:74` ✅ **CORRIGIDO** (Onda 5, Task 8 — commit `ae4e4191`) — `pode_editar=True` fixo; usuário só-leitura vê
"Aprovar"/"Cancelar" e leva 404 opaco. Só UI, não é furo de authz.
⚪ `templates/aditivos/listar.html:50` ✅ **CORRIGIDO** (Onda 5, Task 8 — commit `ae4e4191`) — o mapa de rótulos usa `'proposta'`,
`'aditivo'`, `'manual'`, mas `ORIGEM_TIPO` grava `proposta_aprovada`,
`cadastro_manual`, `contrato_original`, `backfill`… Só `aditivo` casa; o resto da
linha do tempo mostra o token cru.
⚪ `services/contrato_obra.py:407` 🔬 **TESTADO, NÃO REPRODUZIDO** (Onda 5, Task 8 — commit `ae4e4191`) — `_versao_vigente_da_obra` pode devolver versão
já encerrada em memória. Latente hoje (uma entrada por request), mas a guarda não
faz o que o docstring promete. No cenário direto o defeito **não reproduziu**: a
query em `no_autoflush` e o identity map devolvem o objeto já mutado, e o
teste-pino nasceu verde. Pino de regressão
`test_versao_encerrada_em_memoria_nao_e_vigente` adicionado — se houver caminho
real, ele passa pelo fallback de `db.session.new`. Ver achado novo (b), no fim
deste documento.
⚪ `views/aditivos_views.py:143` ✅ **CORRIGIDO** (Onda 5, Task 8 — commit `ae4e4191`) — `aprovar_aditivo` pode devolver `None` e a view
faz `float(versao.valor)` **depois** do commit: diz "Erro ao aprovar" quando nada
deu errado.
⚪ `services/orcamento_versao.py:117` — `criar_revisao` copia `criado_por` da v1.
Toda revisão da cadeia é atribuída a quem criou a primeira, o que derrota a
trilha de auditoria que a Task 10 existe para construir.

✅ **Conferido e são:** a reconciliação pendente de `abrir_versao` × índice parcial
`uq_contrato_versao_vigente` (o SQLAlchemy 2.0 emite UPDATE antes de INSERT por
tabela); o `no_autoflush` em `event_manager.py:1367` e
`importacao_fisico_financeiro.py:770`; as migrations 271-275 (idempotentes, bem
numeradas, `admin_id IS NOT NULL` na backfill); `lancar_delta_contrato` mantendo
`ja_lancado` coerente entre a porta do aditivo e a da proposta; a ordenação de
Kahn em `scripts/limpar_tenants_teste_dev.py`.

---

## 2. Financeiro e contabilidade — 10 🔴

🔴 **`financeiro_service.py:619` ✅ **CORRIGIDO** (Onda 3, D2/Task 3.6 — commits `5be4a5bd`+`0d244e48`) — a obrigação não muda de lado, ela evapora.**
As exclusões de gêmeos (`_gemeos_compra` :619, `_gemeos_reembolso` :621) são
incondicionais, mas `ContaPagar` **nunca** alimenta `saidas_previstas` em
`calcular_fluxo_caixa`. Um pedido de R$ 100k ainda PENDENTE mostra
`saidas_previstas = 0` e o `saldo_final_projetado` superestima o caixa pelo valor
inteiro. O próprio comentário mede a exposição: *"580 gêmeos, R$ 490.950, 24% do
valor aberto"*.
⚠️ `tests/test_b5_fluxo_gemeos_e_orfaos.py:100` **afirma isso como intencional**.
Corrigir exige mudar o teste — é decisão humana, não edição silenciosa.

🔴 **`contabilidade_utils.py:621` — a DRE conta só um lado.**
`if partida.tipo_partida == tipo_esperado: total += valor`. Estornar uma despesa
de R$ 840 grava a partida inversa correta (`contabilidade_views.py:479-487`), mas
o crédito é filtrado fora: a DRE reporta os R$ 840 para sempre. O balancete, que
compensa os dois lados, discorda permanentemente da DRE no mesmo mês.

🔴 **`contabilidade_utils.py:871` — o balancete nunca fecha.**
`'saldo_devedor': saldo_atual if saldo_atual > 0` é aplicado **depois** da
normalização pela natureza da conta, então o saldo credor normal de uma conta
CREDORA é positivo e cai na coluna de débito. Um lançamento D Caixa 1.000 /
C Receita 1.000 dá `total_saldo_devedor = 2.000`, `total_saldo_credor = 0`. Mesmo
defeito em `contabilidade_views.py:619`.

🔴 **`contabilidade_views.py:1300` ✅ **CORRIGIDO** (Onda 2, Task 7 — commit `22343233`) — o join vaza entre tenants.**
`.join(PlanoContas, PartidaContabil.conta_codigo == PlanoContas.codigo)` omite
`admin_id`, mas a PK de `PlanoContas` é composta `(admin_id, codigo)`
(`models.py:3266`). Cada tenant que possui aquele código soma uma linha
duplicada: uma partida de R$ 840 em ~300 tenants semeados vira R$ 252.000, com
`conta.nome` puxado de um plano alheio.

🔴 **`contabilidade_utils.py:221` — a integração 500 nos três tipos.**
`contabilizar_folha_pagamento` lê `f.salario_bruto`, que `FolhaPagamento` não tem
(tem `salario_base`/`total_proventos`). Idem `proposta.data_aprovacao` (:182) e
`nota.fornecedor_nome`/`nota.valor_icms` (:201, :206). E mesmo corrigido,
`contabilizar_entrada_material` debita `valor_produtos + valor_icms` contra
crédito de `valor_total`, disparando "Lançamento desbalanceado" sempre que o ICMS
está embutido no preço — que é a norma brasileira.

🔴 **`gestao_custos_views.py:1433` ✅ **CORRIGIDO** (Onda 3, Task 5 — commit `60ca071e`) — a migração "idempotente" perde a corrida toda.**
Monta `GestaoCustoFilho` com `obra_id` possivelmente NULL e sem
`centro_custo_id`, violando `ck_gestao_custo_filho_destino` (`models.py:7261`).
`custos_escritorio_views._criar_conta_pagar` cria toda despesa de escritório sem
`obra_id`, então essas linhas existem por construção. O `IntegrityError` estoura
**fora** do `try` por registro, o handler externo faz rollback, e todo registro
migrado naquela execução se perde — num botão anunciado como *"ação segura e pode
ser repetida"*.

🔴 **`gestao_custos_views.py:1415` ✅ **CORRIGIDO** (Onda 3, Task 5 — commit `60ca071e`) — o passivo encolhe sozinho.**
O pai nasce com `valor_total=valor_original` e o único filho com `valor=saldo_cp`,
e a query inclui de propósito contas PARCIAL onde os dois diferem. Um
`ContaPagar(valor_original=1000, valor_pago=400, saldo=600)` dá um pai de 1000 com
filho de 600. A primeira edição chama `_recalcular_total_pai`, que reescreve
`valor_total` para 600 — o passivo some R$ 400 sem trilha. `sincronizar_obra_do_pai`
também nunca é chamado aqui, então `gcp.obra_id` fica NULL.

🔴 **`gestao_custos_views.py:234` ✅ **CORRIGIDO** (Onda 2, Task 5 — commit `42f48247`) — a correção de tenant não foi aplicada nos irmãos.**
`obra_id = request.form.get('obra_id', type=int)` vai direto para
`destino_de_filho_novo`, que devolve verbatim. O commit `6af4fe93` adicionou
exatamente essa checagem em `editar_filho` (:550, com comentário explicando o
ataque) — mas `novo()` e `editar()` (:1074) ficaram de fora. Um POST forjado grava
custo na obra de outro tenant, e `sincronizar_obra_do_pai` propaga para o pai,
disparando `recalcular_obra` no snapshot orçado×real da vítima.

🔴 **`services/financeiro_compra.py:433` ✅ **CORRIGIDO** (Onda 3, Task 7 — commits `1074e658`+`de18c64c`) — a ressalva D6 zera todas as parcelas.**
`if total_aberto > 0 and atestado != total_aberto:` não tem guarda `atestado > 0`.
O caminho da ressalva existe justamente para liberar uma conta com "sem atesto de
recebimento" em aberto; quando é usado (alcançável de `compras_views.py:1580`),
`atestado` é 0 e **toda parcela é reescrita para R$ 0,00**, com
`saldo = 0 - valor_pago`. É exatamente a "conta de R$ 0,00 que desaparece de toda
projeção de caixa" que o docstring de `criar_obrigacao` diz evitar. E
`divergencia_nota_atestado` devolve `dentro=True` quando `atestado <= 0`, então
nem o aviso de divergência dispara.

🔴 **`relatorios_financeiros_avancados.py:154` — o módulo inteiro é inoperante, em silêncio.**
Quatro defeitos independentes, cada um engolido por um `except` local que devolve
forma vazia, então `/relatorios/financeiros/api/dados-financeiros` responde
`{"success": true, "dados": {}}` em vez de errar:
`UsoVeiculo.km_rodado` (:154, :246, :407, :516, :683, :810) — a coluna é
`km_percorrido`; `UsoVeiculo.horas_uso` (:812) e `CustoVeiculo.km_atual` (:830) —
não existem (`km_veiculo` existe); `AlocacaoVeiculo` (:470, :472) — classe
inexistente no repo; `case([(cond, val)], else_=0)` (:220-225) — a forma de lista
saiu no SQLAlchemy 2.0 e o ambiente roda 2.0.41 (`ArgumentError`, reproduzido).
Mais um `NameError` puro em :876 (`custo_per_km` × o parâmetro `custo_por_km`) e um
produto cartesiano em :512 que junta `CustoVeiculo` e `UsoVeiculo` pelo mesmo
`Veiculo` e soma os dois num GROUP BY, inflando `custo_por_km` ~10×.

🟡 ✅ **CORRIGIDO** (Onda 1, Task 5 — commits `be90b0b1`, `4e390e00`; a guarda entrou também em `financeiro_service.py`, porque a view não pode ser a única). `financeiro_views.py:525` — `Decimal(request.form.get('valor_pago'))` sem
validação de sinal nem de ordem de grandeza, e `FinanceiroService.baixar_pagamento`
(:110, :127) também não. Digitar `-100` **credita** o banco
(`saldo_atual -= -100`), deixa `saldo = 1100`, mantém PENDENTE e mostra sucesso.
Errar `10000` por `1000.00` debita R$ 10.000 contra dívida de R$ 1.000.
`receber_conta` (:840) é idêntico.
🟡 `services/financeiro_compra.py:420` ✅ **CORRIGIDO** (Onda 3, Task 7 — commits `1074e658`+`de18c64c`) — `liberar()` seleciona por
`pedido_compra_id` sem filtrar `fechamento_id`. Fechar um lote com a parcela 1 de
3 libera as parcelas 2 e 3 — pagáveis sem nunca terem estado em lote fechado,
porque `pagar_conta` só olha `situacao_liberacao` (`financeiro_views.py:506`).
🟡 `services/financeiro_compra.py:566` ✅ **CORRIGIDO** (Onda 3, Task 7 — commits `1074e658`+`de18c64c`) — `reabrir_lote` volta o `status` para
'ABERTO' mas não reverte a `situacao_liberacao` que `fechar_lote` pôs em
'liberada'. Fecha, reabre, tira a conta do lote: ela fica pagável para sempre sem
lote nenhum a autorizando.
🟡 `contabilidade_views.py:1377` ✅ **CORRIGIDO** (Onda 2, Task 7 — commits `22343233`+`8708982e`) — `origem_id` vem do JSON do request e
`contabilizar_*` carrega por PK pelada, lançando sob o `admin_id` **do documento**.
Tenant A cria centro de custo e lançamento no razão do tenant B. Só o achado 5
impede a escrita de aterrissar hoje.
🟡 `financeiro_service.py:752` ✅ **CORRIGIDO** (Onda 3, Task 6 — commit `dd96623d`) — pai PARCIAL: `valor_pai` é o `saldo` restante mas
o laço de filhos manuais soma cada filho pelo `valor` cheio e descarta o `resto`
negativo. Dois filhos de R$ 500 com R$ 600 pagos dão `saidas_previstas = 400` no
card e R$ 1.000 de previsto no detalhe — os R$ 600 pagos contados duas vezes na
mesma tela.

⚪ **Doze menores:** `contabilidade_utils.py:457` (o Balanço nunca acumula contas de
resultado, então `balanceado` é False sempre que há atividade; `abs(saldo)` soma
prejuízo acumulado ao PL) · `contabilidade_utils.py:534` (o mapa de prefixos da
DRE está invertido em relação a `criar_plano_contas_padrao` e deslocado um grupo em
relação a `financeiro_seeds.py`; locação de equipamento reporta como CMV) ·
`gestao_custos_views.py:812` (a rota viva `autorizar()` ainda grava `FluxoCaixa`
sem obra/centro — o commit `6775b391` corrigiu só o `pagar()` LEGADO) ·
`gestao_custos_views.py:822`, `:262`, `financeiro_views.py:895` (FKs de
banco/fornecedor/subempreiteiro gravadas de valores de formulário não validados) ·
`financeiro_views.py:1509` (composição do lote reapontada por formulário velho,
depois do lote fechado e auditado) · `financeiro_service.py:1011` (KPI de vencidos
conta por `data_criacao`, ignorando `data_vencimento`) · `custos_views.py:250`
(`order_by('mes').limit(12)` plota os doze meses **mais velhos**) ·
`financeiro_views.py:36` ✅ **CORRIGIDO** (Onda 1, Task 5 — commit `be90b0b1`) (`_parse_valor` não trata entrada só com ponto: `1.500`
vira R$ 1,50) · `services/custo_orcado.py:84` (o fallback "linha vence agregado" no
nível da obra é tudo-ou-nada enquanto o por serviço é por serviço, então o BAC do
EVM subestima obra mista) · `custos_escritorio_views.py:220`
(`request.form.get('valor', default)` nunca cai no default com campo vazio;
`Decimal('')` vira "Erro ao criar ocorrência" genérico) · `contabilidade_views.py:463`
(o estorno estoura o VARCHAR(500) de `historico`, tornando lançamento longo
inestornável) · `financeiro_seeds.py:122` (linha de log inalcançável após `return 0`).

✅ **Conferido e são:** não há vazamento de pai CANCELADO nestes arquivos — o único
agregado de `GestaoCustoFilho` nas views de custo é escopado a um `pai_id`, e
`resumo` separa CANCELADO em balde próprio.

---

## 3. RDO — 4 🔴

🔴 **`views/rdo.py:2127` ✅ **CORRIGIDO** (Onda 5, Task 6 — commit `ce331094`) — `atualizar_rdo` está morta.** Lê `rdo.tempo_manha`, que
não é atributo de `RDO`; todo POST em `/rdo/<id>/atualizar` levanta
`AttributeError` e faz rollback. **Verificado em runtime.**
🔴 **`views/rdo.py:3070` ✅ **CORRIGIDO** (Onda 5, Task 6 — commit `ce331094`) — `obra_id` não vinculada** no ramo de edição de
`rdo_salvar_unificado`; o `NameError` escapa do `except (ValueError, IndexError)`
local e aborta a edição inteira.
🔴 **`rdo_editar_sistema.py:218` ✅ **CORRIGIDO** (Onda 2, Task 6 — commit `af913fce`) — RDO muda de tenant.** `rdo.obra_id` é atribuído
do formulário sem checagem de tenant nem de existência.
🔴 **`views/rdo.py:2838` ✅ **CORRIGIDO** (Onda 2, Task 3 — commits `77e4ab00`+`2d94cae3`) — `get_admin_id_robusta` resolve o tenant** por
`Funcionario.query.filter_by(email=...)` sem escopo e **cai num `return 10`
hardcoded**.

🟡 `views/rdo.py:2867` ✅ **CORRIGIDO** (Onda 3, Task 10 — commits `6be3b790`+`ed17ab7f`+`297ac8fe`+`d585a399`, fix rounds `02882e5d`+`cead7569`+`aa657b9f`) — o caminho unificado de edição apaga `RDOMaoObra` em bloco
sem `remover_custos_rdo`/`remover_custo_diario_rdo`: o trabalhador removido segue
sendo cobrado.
🟡 `views/rdo.py:1888` ✅ **CORRIGIDO** (Onda 3, Task 10 — commits `6be3b790`+`ed17ab7f`+`297ac8fe`+`d585a399`, fix rounds `02882e5d`+`cead7569`+`aa657b9f`) — `reabrir_rdo` desfaz o percentual do cronograma mas deixa
o custo de mão de obra já lançado no razão enquanto o RDO está em `rascunho`.
🟡 `views/rdo.py:4002` ✅ **CORRIGIDO** (Onda 5, Task 6 — commits `ce331094`
+ `ed85d117`) — `salvar_rdo_flexivel` ignora `rdo_id` e não tem guarda de
obra+data: é o produtor dos RDOs duplicados na mesma data que os serviços de
exportação e atualização contornam.
⚠️ **O achado tinha duas metades, e a 1ª correção pegou a errada.** A `ce331094`
pôs a guarda de obra+data e deixou `rdo_id` intocado. **O gate de fecho
reprovou**: 6 testes caíram, a guarda disparou 12 vezes. Dois RDOs na mesma
obra e mesmo dia são estado **legal** — `services/custo_funcionario_dia.py`
rateia a diária entre os RDOs do dia, e a 🔬 **Onda 3 / Task 9 desta mesma
auditoria aprofundou exatamente esse caso**. A guarda ainda recusava com
`302` + `flash` (sucesso para quem confere status), matando o toggle reverso de
terceiros em silêncio — a classe de defeito que a própria onda existia para
matar. `ed85d117` removeu a guarda e corrigiu a metade real: `rdo_id` de um RDO
da obra/tenant agora **edita** em vez de criar. Detalhe em
`docs/superpowers/plans/2026-08-25-onda-5-o-recusado-para-de-ser-gravado.md`,
seção "A guarda da Task 6 que o gate derrubou".
🟡 `views/rdo.py:3969` ✅ **CORRIGIDO** (Onda 5, Task 6 — commit `ce331094`) — a checagem de colisão de `numero_rdo` é escopada por
`admin_id` embora a coluna seja `UNIQUE` global; uma linha com `admin_id` NULL
causa `IntegrityError` em laço permanente.
🟡 `services/custo_funcionario_dia.py:97` ✅ **CORRIGIDO** (Onda 3, Task 9 — commits `a174e8b1`+`171043d7`+`9caa8ce9`+`0e78e1cb`+`e2e69035`) — para diaristas o `componente_folha` é
rateado mas `custo_hora_normal` não, então a tela mostra o dobro do que foi
efetivamente lançado.

⚪ `crud_rdo_completo.py:602` ✅ **CORRIGIDO** (Onda 5, Task 6 — commit `ce331094`) — `finalizado_em`/`finalizado_por_id` não são colunas
mapeadas: a autoria da finalização é descartada em silêncio numa rota viva.
⚪ `crud_rdo_completo.py:324` ✅ **CORRIGIDO** (Onda 5, Task 6 — commit `ce331094`) — `salvar_rdo` (sem rota, mas marcada para revival) usa
`func` não importado e passa kwargs `sequencial_ano`/`ano` que `RDO` não aceita.
Segue sem rota (reservada ao Módulo 07) — ver achado novo (c), no fim deste
documento.
⚪ `views/rdo.py:2969` ✅ **CORRIGIDO** (Onda 5, Task 6 — commit `ce331094`) — campos de clima legados (`tempo_manha`, `temperatura`,
`condicoes_climaticas`, `observacoes_meteorologicas`) são gravados em atributos não
mapeados em duas rotas e perdidos em silêncio.

✅ **Conferido e são:** a guarda `publica_custos` está corretamente aplicada nas cinco
rotas de salvamento e em `crud_rdo_completo.finalizar_rdo`. O trabalho de 21/08 e
24/08 (rascunho não lança custo, rascunho não move percentual) não tem defeito.

---

## 4. Cronograma, medição e EVM — 2 🔴

🔴 **`services/medicao_service.py:178` — medição permanentemente zerada.**
`gerar_medicao_quinzenal` zera o percentual acumulado do IMC para itens medidos
pelo fallback RDO/`servico_id`: usa `calcular_percentual_item` (0 sem vínculo de
cronograma) mas omite o fallback `percentual_do_servico_na_obra` que
`_recalcular_imc_avanco` tem. Essas obras geram medição vazia para sempre
(`perc_periodo = max(0, 0 - 60) = 0` a cada ciclo), com extrato PDF em 0%, mesmo
que `recalcular_medicao_obra` restaure o IMC depois.

🔴 **`cronograma_views.py:1017` ✅ **CORRIGIDO** (Onda 5, Task 2 — commit `6ac1566b`) — a edição rejeitada é persistida.**
Três `return 400` em `atualizar_tarefa` (:1017 `modo_apontamento`, :1058
subatividade×serviço, :1168 hierarquia circular) pulam o
`db.session.rollback()`, ao contrário dos vizinhos em :1000/:1010/:1130. O
`_com_undo` então chama `registrar_acao`, que autoflusha e commita — a edição
recusada é gravada **e empilhada no undo**, contradizendo o docstring do próprio
decorador. Mesma forma em `cronograma_views.py:1618` (`atualizar_vinculo` atribui
`vinculo.tipo` em :1613, devolve 400 por `lag_dias` inválido sem rollback, e o
`_com_undo` commita a troca: TI vira II em silêncio).

🟡 `medicao_views.py:334` — `excluir_item` apaga `ItemMedicaoComercial` sem checar
`MedicaoObraItem`, cuja FK é `nullable=False` sem `ondelete` nem cascade
(`models.py:7501`). Apagar item já medido dá `ForeignKeyViolation` → 500 com sessão
suja.
🟡 `services/cronograma_apontamento_service.py:397` ✅ **CORRIGIDO** (Onda 5, Task 5 — commit `a2ab9b81`) — `registrar_apontamento` lê
`pct_ant` só de `percentual_realizado` (travado em 100) enquanto
`recomputar_cadeia:246` e o preview do RDO preferem `percentual_acumulado`. Depois
de uma superexecução (120% guardado como acumulado=120/realizado=100), uma
regressão real para 110% **passa por baixo** da guarda `RetrocessoNaoPermitido` e
grava incremento +10, que qualquer recompute depois vira −10.
🟡 `services/evm.py:130` — `_pv_ate_hoje` soma só `etapa['meses']`, que
`montar_fisico_financeiro` preenche exclusivamente para etapas `entregavel`,
enquanto o BAC (`custo_orcado_da_obra`) soma toda linha de custo, inclusive
`periodo`. Qualquer obra com custo indireto/de período recebe SPI estruturalmente
inflado e SV positivo mesmo em dia.
🟡 `medicao_views.py:365` — `vincular_tarefa` valida a tarefa por
`id/obra_id/admin_id` só, sem `ativa` nem `is_cliente`, ao contrário da listagem
(:56). Um POST direto vincula item de medição a tarefa arquivada ou a clone de
cópia-cliente, e `calcular_percentual_item` (que usa `.get()` sem filtro) fatura
contra ela.

⚪ `services/evm.py:100` — `eac = (bac / _d(cpi)) if cpi else bac` trata `cpi == 0.0`
(EV=0, AC>0) como "ainda sem CPI", reportando `vac = 0` — exatamente no orçamento —
no pior cenário possível; o payload ainda emite `cpi: 0.0`, indistinguível de
desempenho zero real, enquanto `None` significa "sem dado".

---

## 5. Compras, almoxarifado e alçadas — 6 🔴

🔴 **`views/almoxarifado/relatorios.py:39` — o relatório "Posição de Estoque" nunca funcionou.**
`AlmoxarifadoEstoque.query.filter_by(admin_id=admin_id, ativo=True)`, mas
`AlmoxarifadoEstoque` (`models.py:5546`) não tem coluna `ativo`. **Reproduzido:**
`InvalidRequestError: Entity namespace for "almoxarifado_estoque" has no property
"ativo"`. Nada captura na rota — 500 seco.

🔴 **`views/almoxarifado/movimentos.py:1239` — devolução em lote sempre falha.**
`filter_by(id=..., funcionario_id=...)`; a coluna é `funcionario_atual_id` (a rota
de item único, em :1019, acerta). Mesmo `InvalidRequestError`, desta vez engolido
pelo `except Exception` de :1381 → toda devolução de carrinho serializado devolve
500 "Erro ao processar operação" sem mensagem útil.

🔴 **`views/almoxarifado/movimentos.py:411` (e :455) ✅ **CORRIGIDO** (Onda 3, Task 3 — commit `673e73a9`) — a "TRANSAÇÃO ATÔMICA" não é atômica.**
`EventManager.emit('material_entrada', …)` roda **dentro** do laço, antes do
`db.session.commit()` da rota (:467); o handler
`criar_conta_pagar_entrada_material` chama `db.session.commit()`
(`event_manager.py:216`). Depois do item 1 a sessão já foi commitada: falha no
item 3 chama `db.session.rollback()` e não desfaz nada — metade do carrinho fica
no estoque enquanto o chamador é informado de que a operação falhou. A rota de
item único (:185, :236) emite **depois** do commit; esta divergiu.

🔴 **`almoxarifado_utils.py:602` ✅ **CORRIGIDO** (Onda 3, Task 1 — commit `fda7d189`) — a mesma unidade pode ser emitida duas vezes.**
`apply_movimento_manual`/`rollback_movimento_manual` mantêm só
`estoque.quantidade`, nunca `quantidade_disponivel`/`quantidade_inicial`, enquanto
a saída valida em `func.sum(quantidade_disponivel)` (`movimentos.py:597`). Quebra
nos dois sentidos: ENTRADA manual de 100 cria lote com `quantidade_disponivel =
NULL`, então a guarda de saída vê 0 e recusa; SAÍDA manual contra lote de compra
zera `quantidade` mas deixa `quantidade_disponivel` em 100 — **as mesmas unidades
saem de novo.**

🔴 **`views/almoxarifado/movimentos.py:1066` ✅ **CORRIGIDO** (Onda 3, Task 2 — commit `aeb41ca9`) — material devolvido some do estoque.**
`processar_devolucao` (consumível) cria o lote de retorno só com `quantidade`.
Mesma consequência do anterior: o devolvido é invisível para
`sum(quantidade_disponivel)` e nunca mais pode ser emitido.
`processar_devolucao_multipla:1330` tem a omissão idêntica.

🔴 **`views/almoxarifado/movimentos.py:1045` ✅ **CORRIGIDO** (Onda 3, Task 3 — commit `673e73a9`) — toda devolução vai para a obra 1.**
`obra_id=estoque.obra_id or 1`, mas `estoque.obra_id = None` foi atribuído três
linhas antes (:1031). A expressão é **sempre** `1`: todo movimento de devolução
serializada é carimbado com a obra de id 1 — obra arbitrária, possivelmente de
outro tenant — e a obra real se perde. `relatorios.py:214` (consumo por obra) lê
exatamente essa coluna.

🟡 ✅ **CORRIGIDO** (Onda 1, Task 3 — commits `f2567fcb`, `995efb5c`, `37397333`; os dois últimos porque `_num()` primeiro perdeu a distinção entre campo vazio e campo com lixo, e depois voltou a aceitar lixo que a limpeza esvazia). **`compras_views.py:2853` — o pedido é gravado a 1/1000 do preço negociado.**
`float(bruto.replace('.','').replace(',','.') if ',' in bruto else bruto)` para o
preço unitário real na emissão: `"1.500"` → `1.5`. E porque o valor é **menor** que
o estimado aprovado, a guarda 3 (`valor_total > aprovado`) deixa passar — GCP,
ContaPagar e a entrada no almoxarifado herdam o número errado. É o achado nº 6 da
revisão da Fase 3, ainda vivo no caminho de emissão (`nota()` em :1518 reconhece).
🟡 ✅ **CORRIGIDO** (Onda 1, Task 4 — commits `c16f3a90`, `f8f86e0e`). `services/faixa_alcada_admin.py:206` — `_para_teto` só tira o ponto de milhar
quando há vírgula. `"30.000"` vira `Decimal('30.000')` → R$ 30,00. A escada segue
monotônica, `_violacoes` não levanta nada, e a primeira faixa do tenant passa a
cobrir só compras abaixo de R$ 30. Mesma ambiguidade de 1000× que
`compras_views._quantidade_do_form` foi escrito para recusar.
🟡 `services/entregas_terceiros.py:340` ✅ **CORRIGIDO** (Onda 5, Task 5 — commit `22bea5a8`) — o toggle reverso põe
`percentual_concluido = 0.0` em toda tarefa de `terceiros_tarefa_ids_lista[]` não
marcada em `entrega_tarefa_ids[]`. Tarefa de subempreitada em 45% é zerada no
próximo salvamento de RDO que não a marque. O docstring só promete reverter "para
pendente" — progresso parcial é dado real.
🟡 `services/entregas_terceiros.py:357` ✅ **CORRIGIDO** (Onda 5, Task 5 — commit `40024db8`) — o `except` pelado devolve `(0, 0)` depois
de os laços já terem mutado `TarefaCronograma` na sessão. O chamador commita
assim mesmo: falha no meio persiste escrita parcial reportando que nada foi
aplicado.
🟡 `views/almoxarifado/movimentos.py:857` ✅ **CORRIGIDO** (Onda 3, Task 3 — commit `673e73a9`) — em `processar_saida_multipla`, a fase 2
re-consulta cada lote alocado e faz `continue` em silêncio quando ele não está mais
`DISPONIVEL`. Duas alocações no mesmo `estoque_id` (ou saída concorrente entre a
validação e o processamento) emitem menos que o pedido, e a resposta ainda é
`success: true` com a contagem cheia.
🟡 `views/almoxarifado/movimentos.py:1302` — grava `'EM_MANUTENCAO'` e
`'INUTILIZADO'`, fora do vocabulário de `models.py:5560` (`MANUTENCAO`,
`DESCARTADO`). `funcionario_perfil.html:977` e
`almoxarifado/itens_detalhes.html:246` testam `'MANUTENCAO'`, então item devolvido
avariado não mostra selo nenhum nas duas telas — enquanto `dashboard.py:93` e
`relatorios.py:296` casam `EM_MANUTENCAO`. **O vocabulário está partido no meio.**
🟡 `almoxarifado_utils.py:257` ✅ **CORRIGIDO** (Onda 2, Task 7 — commit `22343233`) — `NotaFiscal.query.filter_by(xml_hash=xml_hash)` sem
`admin_id`. Se outro tenant já importou aquele XML, este tenant ouve "Nota fiscal já
foi importada anteriormente" e nunca consegue importar. É o mesmo defeito que
`entrada_ja_lancada` (`movimentos.py:16`) documenta e evita de propósito uma camada
abaixo.

⚪ `views/almoxarifado/relatorios.py:286` — `qtd_atual < item.estoque_minimo` sem
guarda de `None`; a coluna é nullable (`models.py:5530` — o `default=0` é do lado
Python, então linhas antigas podem ser NULL). `dashboard.py:52` e `itens.py:61`
guardam; aqui uma linha NULL derruba o relatório de alertas.
⚪ `views/almoxarifado/itens.py:110` (e `:165`) — `categoria_id` vai do formulário
para o item sem checagem de tenant, ao contrário de toda outra FK do módulo. POST
forjado prende o item à categoria de outro tenant, cujo nome passa a aparecer nas
listagens deste via `item.categoria.nome`.

---

## 6. Obras, propostas e orçamento

🔴 **`services/proposta_diff.py:88` ✅ **CORRIGIDO** (Onda 5, Task 4 — commit `a8f4ff44`) — o comparador de versões relata impacto R$ 0,00.**
`diff_versoes`/`total_do_diff` leem `PropostaItem.subtotal`, que é NULL para todo
item não construído pelo caminho de explosão da Task #89
(`subtotal_snap = None` em `propostas_consolidated.py:899`). Uma revisão que muda
**só** `preco_unitario` aparece como "mantido" e a tela nova
`/propostas/<a>/comparar/<b>` reporta impacto zero.
`PropostaItem.subtotal_calculado` existe exatamente para isso e não é usado em
lugar nenhum.

🟡 **`services/cronograma_proposta.py:602` ✅ **CORRIGIDO** (Onda 5, Task 5 — commit `a80973e8`) — item ressuscitado não volta ao cronograma.**
O fluxo novo de supressão arquiva tarefas (`ativa=False`), mas os ramos de reúso
por chave natural de `materializar_cronograma` (:602-606, :675-686) reaproveitam a
tarefa casada **sem restaurar `ativa`**. Uma "Alvenaria" suprimida e re-adicionada
como item *novo* (sem linhagem → `reativar_…` nunca roda) fica em silêncio sem
tarefa viva. `natural_key_index` não filtra `ativa`.

🟡 `views/orcamentos_views.py:566` — `_bloqueio_por_trava` no `excluir` torna
permanentemente indeletável todo orçamento que um dia gerou proposta (nada limpa
`travado_em`), e a mensagem fala em "mudar valores".
⚪ `views/orcamentos_views.py:617` ✅ **CORRIGIDO** (Onda 5, Task 4 — commit `a8f4ff44`) — nem `orcamentos.comparar` nem
`propostas.comparar` são linkados de template nenhum: **a entrega inteira da Task
12 está inalcançável pela interface.**

✅ **Conferido e são:** `_CAMPOS_DO_ITEM` × o corpo antigo de `duplicar` (completo);
a guarda de ciclo de `_raiz_do_item` (termina); idempotência das migrations 274/275
e `versao NOT NULL DEFAULT 1`; `obra_form.html` usa `disabled` (o campo realmente
não é submetido, casando com a guarda `is not None`); as seis rotas travadas são
POST de formulário puro, então a recusa por redirect funciona; o
`congelar_base_medicoes_recebidas` que saiu de `event_manager.py` é semanticamente
equivalente.

---

## 7. Portal do cliente, auth e multitenant — 2 🔴

🔴 **`multitenant_helper ✅ **CORRIGIDO** (Onda 2, Task 2 — commit `44bea17f`).py:25` — o tenant fantasma.**
`get_admin_id()` só mapeia `tipo == 'funcionario'` para `current_user.admin_id`;
**todo outro papel não-admin cai no `return current_user.id`**.
`TipoUsuario.GESTOR_EQUIPES` e `ALMOXARIFE` são papéis vivos (`crm_views.py:83`,
`views/metricas_views.py:44`). Um gestor com `id=42, admin_id=7` recebe
`admin_id=42` — **um tenant que não existe**. Tudo que for escrito por
`financeiro_views`, `configuracoes_views`, `ponto_views`, `reembolso_views` e
`crud_servico_obra_real` (todos importam este helper) é carimbado nesse tenant
fantasma, fica invisível para o admin 7, e as leituras voltam vazias.
`utils/tenant.get_tenant_admin_id` e `auth.get_tenant_filter` tratam esses papéis
corretamente no ramo `else` — **esta é a única cópia que divergiu.**

🔴 **`portal_obras_views.py:304` ✅ **CORRIGIDO** (Onda 2, Task 4 — commit `63857dfb`) — compra interna ainda vaza no portal do cliente.**
`compras_resolvidas` continua sem o filtro `tipo_compra == 'aprovacao_cliente'`.
É exatamente o vazamento que o docstring de `_get_compra_do_portal` (:511) descreve
como **corrigido**: *"Uma compra `tipo_compra='normal'` carimbada como APROVADO
passava a aparecer em `compras_resolvidas` (:177), que não filtra tipo"*. A
correção entrou nas duas rotas de ação **mas não na listagem que o próprio
docstring aponta**.

🟡 `portal_obras_views.py:645` — `upload_comprovante` resolve a compra por
`filter_by(id=compra_id, obra_id=obra.id)` em vez de `_get_compra_do_portal`: sem
`admin_id`, sem `tipo_compra`. Quem tem a URL do portal posta arquivo sobre compra
interna, sobrescrevendo `comprovante_pagamento_url`.
🟡 `portal_obras_views.py:720` — `ver_comprovante` tem a mesma busca sem escopo e
então faz `send_file`. A rota criada para **substituir** o `/persistent-uploads`
removido entrega a visitante anônimo o comprovante de compra interna que o portal
nunca ofereceu.
🟡 `portal_obras_views.py:663` ✅ **CORRIGIDO** (Onda 5, Task 3 — commit `31889d24`) — o fallback de `5 * 1024 * 1024` é morto:
`app.py:159` põe `MAX_CONTENT_LENGTH = 64 * 1024 * 1024`, então `max_bytes` é
sempre 64 MB. O teto de 5 MB do portal nunca se aplica — sobra rota anônima, sem
autenticação e sem rate limit gravando blobs de 64 MB no volume persistente a cada
requisição.
🟡 `portal_obras_views.py:768` e `:798` ✅ **CORRIGIDO** (Onda 5, Task 3 — commit `31889d24`) — `toggle_portal` e `gerar_medicao` têm só
`@login_required`. Qualquer FUNCIONARIO do tenant liga/desliga o portal do cliente
(recarimbando `token_cliente_expira_em` +180 dias **sem rotacionar o token**) ou
cria `MedicaoObra` cujo `valor_medido` é percentual de `obra.valor_contrato`. Rotas
administrativas comparáveis usam `admin_required`, e
`templates/obras/detalhes_obra_profissional.html:1477,1657` renderizam os dois
botões sem condição.
🟡 `vinculos_audit_views.py:38` ✅ **CORRIGIDO** (Onda 2, Task 8 — commit `1a880748`) — `_admin_id()` devolve `get_tenant_admin_id()`
direto, e `Usuario.admin_id` é nullable (`models.py:122`). Para funcionário sem
`admin_id` devolve `None` e todo filtro degrada para `admin_id IS NULL` — a página
**falha aberta** sobre linhas órfãs em vez de 403, e
`marcar_subatividade_revisada` (:116) muta `SubatividadeMestre` de tenant NULL. O
docstring promete "filtra TUDO por admin_id"; `utils.tenant.require_tenant()` é o
helper fail-closed que existe para isso.
🟡 `services/cliente_resolver.py:61` ✅ **CORRIGIDO** (Onda 2, Task 8 — commit `1a880748`) — com `cliente_id` explícito que não pertence
ao `admin_id`, a busca devolve vazio em silêncio e a execução **cai** para casamento
difuso por nome/e-mail e depois cria um `Cliente` novo, sem log. O chamador
(`event_manager.py:1244`) acredita que a regra 1 "vence sempre": uma FK velha produz
cliente duplicado com a obra presa a ele.

⚪ `portal_obras_views.py:534` ✅ **CORRIGIDO** (Onda 5, Task 3 — commit `31889d24`) — o evento de trilha entra na sessão **antes** das
guardas de idempotência, e os ramos de retorno antecipado não commitam. A sessão é
descartada no teardown, então o evento `compra_aprovar`/`compra_recusar` some —
contradizendo o comentário `# Persistida no commit adiante`.
⚪ `portal_obras_views.py:576` ✅ **CORRIGIDO** (Onda 5, Task 3 — commit `31889d24`) — no ramo de governança um **segundo** evento
`compra_aprovar` é gravado para o mesmo `alvo_id`, e esse caminho commita: toda
aprovação sob governança deixa duas linhas na trilha.
⚪ `portal_obras_views.py:958` ✅ **CORRIGIDO** (Onda 5, Task 3 — commit `31889d24`) — `os.path.join(static_root, rel.arquivo_path)` sem
checar que o resultado fica sob `static/`. Latente hoje
(`services/mapa_relatorio_pdf.py:333` grava caminho relativo), mas um valor
absoluto ou com `../` naquela coluna de 500 chars transforma rota anônima em
leitor de arquivo arbitrário — o mesmo defeito que fez remover
`/persistent-uploads` (`app.py:176`).
⚪ **Armadilha para o próximo:** `auth.py:47 ✅ **CORRIGIDO** (Onda 2, Task 8 — commit `1a880748`)` `get_tenant_filter()` e `auth.py:58`
`can_access_data()` têm **zero** consumidores no repo — a mesma condição que
justificou apagar `almoxarife_required` e irmãos na Fase 1, comentado no pé do
próprio arquivo. `get_tenant_filter` devolve `None` tanto para "super admin vê
tudo" quanto para "não autenticado", então o idiomático
`if f: query.filter_by(admin_id=f)` serviria as linhas de todo tenant a um
chamador anônimo. Morto hoje; armadilha para quem ligar.

✅ **Conferido e são:** `landing_views.py`; `decorators.py`
(`cronograma_import_required` falha fechado em tenant `None`); os três decoradores
de `auth.py`; a remoção do `X-Forwarded-For` em `_registrar_acesso`; a
normalização por `int()` de `_chave_limite_assinatura`; a ordem
senha-antes-de-motivo-de-bloqueio em `services/portal_signatario_auth.autenticar`;
a rechecagem de `rdo_id` em `_assinatura_do_comprovante`; o caminho de
`IntegrityError` em `ciencia_confirmar`; e o casamento por `_caminho` em
`portal_obra` (guarda de ciclo presente, fallback por nome restrito a nomes
internamente únicos).

---

## 8. Pessoas, ponto e folha — 4 🔴

🔴 **`ponto_views.py:611` ✅ **CORRIGIDO** (Onda 5, Task 1 — commit `7ec18fe0`) — traceback na resposta HTML.** `/ponto/` e
`/equipe/alocacao-principal` renderizam `traceback.format_exc()` no HTML em caso de
erro, expondo caminhos, frames e **SQL com parâmetros vinculados** a qualquer
usuário autenticado. Nota: a segunda rota vive em `equipe_views.py`, não em
`ponto_views.py` como o plano original listava — a spec de achados já nomeava as
duas. ✅ **28/08 — o mesmo padrão (traceback em `error.html`) apareceu em
`error_handlers.py` e `production_routes.py`, para todo `500` do app**; fechado à
parte, commit `356c2cf9`.
🔴 **`ponto_views.py:777` ✅ **CORRIGIDO** (Onda 2, Task 6 — commits `af913fce`+`4b55a2d3`) — ponto batido no funcionário de outro tenant.**
`api_bater_ponto` repassa `funcionario_id`/`obra_id` do corpo do request sem
checagem; o serviço cria `RegistroPonto` para o funcionário alheio **e devolve o
nome dele**. `api_registrar_falta` tem o mesmo furo.
🔴 **`ponto_views.py:1487` ✅ **CORRIGIDO** (Onda 3, Task 10 — commits `6be3b790`+`ed17ab7f`+`297ac8fe`+`d585a399`, fix rounds `02882e5d`+`cead7569`+`aa657b9f`) — o mês importado vale zero hora.** A importação Excel
nunca calcula `horas_trabalhadas`: o mês lido marca 0h, a folha cobra todo dia como
falta cheia e nenhum custo de obra é gerado. O ramo de atualização ainda descarta
`obra_id`/`tipo_registro`.
🔴 **`folha_pagamento_views.py:148` ✅ **CORRIGIDO** (Onda 3, Task 8 — commits `0668989b`+`552e7699` — esta é a automação A12) — reprocessar dobra a folha.** `reprocessar`
apaga só `FolhaPagamento`; o `GestaoCustoPai`/`Filho` e o lançamento contábil da
rodada anterior sobrevivem e são recriados — **a folha dobra no contas a pagar e no
razão.**

🟡 `services/folha_service.py:761` ✅ **CORRIGIDO** (Onda 3, Task 9 — commits `a174e8b1`+`171043d7`+`9caa8ce9`+`0e78e1cb`+`e2e69035`) — atraso é descontado duas vezes: as horas
faltantes já estão dentro de `horas_falta`, e `desconto_atrasos` cobra de novo.
🟡 `services/folha_service.py:1444` ✅ **CORRIGIDO** (Onda 3, Task 9 — commits `a174e8b1`+`171043d7`+`9caa8ce9`+`0e78e1cb`+`e2e69035`) — `processar_e_salvar_folha_obra` lança a folha
**inteira do mês** contra *cada* obra trabalhada: o custo de mão de obra por obra e
qualquer roll-up entre obras ficam inflados.
🟡 `services/folha_service.py:1336` ✅ **CORRIGIDO** (Onda 3, Task 9 — commits `a174e8b1`+`171043d7`+`9caa8ce9`+`0e78e1cb`+`e2e69035`) — a composição de custo usa `salario_bruto` (que
já inclui HE e DSR) como "Salário Base" e **soma HE 50/100 e DSR outra vez** como
fatias separadas.
🟡 `ponto_views.py:2446` ✅ **CORRIGIDO** (Onda 3, Task 10 — commits `6be3b790`+`ed17ab7f`+`297ac8fe`+`d585a399`, fix rounds `02882e5d`+`cead7569`+`aa657b9f`) — as duas rotas de ponto facial commitam sem chamar
`PontoService._calcular_horas`, então `horas_trabalhadas` fica 0.0;
`/api/identificar-e-registrar` também nunca emite `ponto_registrado`, então nenhuma
linha de custo é criada.
🟡 `ponto_views.py:1845` — `/api/cache/gerar` regenera os embeddings de um tenant
mas sobrescreve o **único** `cache_facial.pkl` compartilhado, apagando os de todos
os outros.
🟡 `ponto_views.py:2625` — `recarregar_cache_facial()` só relê o pickle, nunca o
regenera: foto facial apagada/desativada **continua autenticando** e foto nova nunca
passa a valer.
🟡 `ponto_service.py:264` ✅ **CORRIGIDO** (Onda 2, Task 7 — commits `22343233`+`8708982e`) — `ConfiguracaoHorario` é lida sem `admin_id`, e
`api_salvar_configuracao` aceita qualquer `obra_id`: um tenant planta regras de
horário que alteram a matemática de atraso/hora extra de outro.

⚪ `folha_pagamento_views.py:1059` — `FolhaPagamento.horas_extras` guarda uma
**contagem de horas** mas o holerite e o Excel formatam como moeda ("Horas Extras
R$ 12,00" para 12h que valem R$ 450).
⚪ `services/folha_service.py:414` — `registros_por_data[reg.data] = reg` guarda só
o último ponto do dia; um segundo registro na mesma data é descartado e suas horas
viram `horas_falta`. (PLAUSÍVEL — depende de linhas duplicadas, contra as quais nada
constrange.)
⚪ `ponto_views.py:919` — o delete em cascata recalcula `pai.valor_total` mas deixa
`saldo` velho, quebrando `saldo = valor_total - valor_pago`; a rota de DELETE simples
(:794) deixa `GestaoCustoFilho` órfão.
⚪ `ponto_views.py:2338` ✅ **DECISÃO REGISTRADA** (Onda 5, Task 1 — commit `7ec18fe0`) — obra cercada e sem coordenada agora **RECUSA**
o ponto (a semântica que `utils_geofencing` já implementava e a rota pulava); obra
sem geofence configurado segue aceitando. Antes, o geofencing era **pulado
inteiro** quando o cliente omitia latitude/longitude: o controle era consultivo,
não impositivo. ⚠️ Achado novo relacionado: `/api/registrar-facial` não faz
geofencing **nenhum** — ver achado novo (a), no fim deste documento.

---

## 9. Frota, transporte, alimentação e reembolso — 3 🔴

🔴 **`reembolso_views.py:330` ✅ **CORRIGIDO** (Onda 3, Task 4 — commits `6d2d5423`+`c860d712`) — excluir um reembolso apaga os dos colegas.**
Excluir apaga o `GestaoCustoPai` **compartilhado**; o cascade
`all, delete-orphan` (`models.py:7203`) leva junto os filhos de **todos os outros
reembolsos do mesmo funcionário**. É a armadilha que
`transporte_views.py:565-579` documenta e evita.
🔴 **`reembolso_views.py:293` ✅ **CORRIGIDO** (Onda 3, Task 4 — commits `6d2d5423`+`c860d712`) — editar faz os irmãos evaporarem.** Sobrescreve
`pai.valor_total` com o valor de um único reembolso (o pai é compartilhado) e nunca
atualiza o `GestaoCustoFilho`: pai e filhos divergem.
🔴 **`veiculos_services.py:16 ✅ **CORRIGIDO** (Onda 2, Task 6 — commit `af913fce`)7` — o veículo muda de tenant por POST.** `setattr`
cego sobre `request.form.to_dict()`: um POST com `admin_id=99` em
`/veiculos/<id>/editar` transfere o veículo **e o histórico em cascata** para outro
tenant.

🟡 `transporte_views.py:204` ✅ **CORRIGIDO** (Onda 2, Task 5 — commit `42f48247`) — `obra_id`, `categoria_id`, `funcionario_id`,
`veiculo_id` e `centro_custo_id` entram sem checagem de tenant (só `osc_id` é
validado): POST forjado prende o lançamento e o `CustoObra` à obra de outro tenant.
🟡 `transporte_views.py:442` ✅ **CORRIGIDO** (Onda 5, Task 7 — commit `808bd0bb`) — o lote grava o custo sem `origem_id`, e
`_limpar_gestao_custo_filho` filtra por `origem_id`: excluir lançamento em lote
deixa o valor vivo em Contas a Pagar dizendo *"Gestão de Custos atualizada"*.
🟡 `frota_views.py:1063` ✅ **CORRIGIDO** (Onda 5, Task 7 — commit `808bd0bb`) — `.join(FrotaVeiculo)` duplicado (tipo + status).
Confirmado no SA 2.0.41 que o segundo join **não** é deduplicado → o filtro por
tipo do dashboard TCO sempre erra. 🔬 O mesmo `.join(FrotaVeiculo)` duplicado
existia em **seis** builders — o achado citava um, a família saiu junto.
🟡 `frota_views.py:741` ✅ **CORRIGIDO** (Onda 5, Task 7 — commit `808bd0bb`) — a edição lê passageiros de `to_dict()` (só o primeiro
valor do multi-select) enquanto a criação usa `getlist`+CSV; e apaga
`responsavel_veiculo`/`observacoes` quando o campo não vem no form.
🟡 `frota_views.py:499` ✅ **CORRIGIDO** (Onda 5, Task 7 — commit `808bd0bb`) — `veiculo.km_atual = km_final` sem comparação: um uso
retroativo faz o odômetro **andar para trás** e cala o alerta de manutenção. As três
rotas irmãs têm a guarda.
🟡 `reembolso_views.py:34` ✅ **CORRIGIDO** (Onda 5, Task 7 — commit `808bd0bb`) — `url_for('main_bp.dashboard')`; o blueprint chama-se
`main` (`views/__init__.py:6`). Tenant sem V2 clicando em Reembolsos recebe
BuildError 500 em vez do aviso.

⚪ **Seis rotas mortas em `views/vehicles.py`** — registradas e alcançáveis por URL,
mas **nenhum template ou JS referencia a família `main.*` de veículos**
(`veiculos_editar.html` posta para `frota.editar`, `/veiculos` redireciona para
`frota.lista`): `:192` `PassageiroVeiculo` não importado no escopo do módulo
(NameError → `-1` → rollback com a mensagem falsa "já estavam registrados como
passageiros"); `:716` `form.km_custo`/`form.litros` não existem em
`CustoVeiculoForm` (a edição de custo **nunca gravou**); `:925`
`from sqlalchemy import Funcionario, Obra` (ImportError em toda requisição ao
histórico); `:1321` `aprovado`/`aprovado_por_id`/`data_aprovacao` não são colunas
(commit vazio com flash de sucesso); `:834` dashboard/relatórios/exportação leem
campos inexistentes (`horas_uso`, `litros_combustivel`, `proxima_manutencao_km`) —
**passam em teste de fumaça com base vazia** e quebram assim que houver dado;
`:665` `url_for('main.detalhes_veiculo', veiculo_id=…)` mas a rota declara `id`
(BuildError **depois** do commit → "Erro ao excluir uso" numa exclusão que
funcionou; idem :626, :722, :758).

✅ **Conferido e são:** `_limpar_gestao_custo_filho` (conta filhos em vez de olhar a
soma); a validação de tenant de `obra_servico_custo_id` nas três telas; as
validações multi-tenant de `alimentacao_views.lancamento_novo`/`_v2` (restaurante,
obra e cada funcionário); o limite `MAX_QTD_POR_ITEM` com 422; o agrupamento de
`CustoObra` por centro de custo.

---

## 10. Núcleo — app, models, event_manager

🟡 **`models.py:7608` ✅ **CORRIGIDO** (Onda 5, Task 8 — commit `ae4e4191`; migration 315, índice ganha `admin_id`) — o índice e as queries discordam sobre `admin_id`.**
`uq_contrato_versao_vigente` é `UNIQUE (obra_id) WHERE vigente_ate IS NULL`, mas
todo leitor/escritor filtra por `(obra_id, admin_id)`. Se uma linha aterrissar com
`admin_id` divergente — o comentário da migration 273 cita *"precedente real:
migration 266"* para exatamente isso — a obra fica **permanentemente travada**:
`abrir_versao` não vê a linha, nunca a fecha, e seu INSERT de uma segunda linha
`vigente_ate IS NULL` viola o índice → `IntegrityError` em toda escrita de contrato
daquela obra, enquanto `abrir_aditivo` reporta "obra não tem contrato vigente".
`uq_contrato_versao_obra_versao` tem a mesma assimetria contra `max(versao)`.

⚪ `models.py:8648` ✅ **CORRIGIDO** (Onda 5, Task 8 — commit `ae4e4191`) × `_migration_274_orcamento_cadeia_revisao` — a migration cria
`versao INTEGER NOT NULL DEFAULT 1`; o modelo declara `nullable=False, default=1`
**sem `server_default`**. Um schema criado por `db.create_all()` (tenant novo, CI via
`pre_start.py`) fica sem default no banco, enquanto produção migrada tem. INSERT em
`orcamento` fora do ORM funciona em produção e falha com `NotNullViolation` em
schema novo — **os dois schemas discordam em silêncio.** Falta
`server_default=db.text('1')`.
⚪ `models.py:7698` ✅ **CORRIGIDO** (Onda 5, Task 8 — commit `ae4e4191`) — o backref de `AditivoContrato.obra` usa `passive_deletes=True`
mas, ao contrário do irmão `ObraContratoVersao.obra` criado no mesmo hunk, omite
`cascade='all, delete-orphan'`. Se a coleção já estiver carregada quando
`db.session.delete(obra)` rodar, o SQLAlchemy toma o caminho de nulificação e emite
`UPDATE aditivo_contrato SET obra_id = NULL`, violando o NOT NULL.

✅ **O hunk do `event_manager.py` está correto** — conferido: `definir_valor_contrato`
chama `congelar_base_medicoes_recebidas(obra, anterior)` antes de escrever, com os
mesmos filtros e a mesma guarda `anterior <= 0`, e roda antes do ramo antecipado de
`admin_id is None`. Sem regressão.

---

## Achados novos da execução da Onda 3 (27/08)

> Nenhum destes estava na varredura de 25/08 — surgiram do próprio trabalho de
> corrigir os 16 achados originais: um implementer que precisou entender a fundo
> uma rotina viu a rachadura ao lado dela. Não têm task nem commit de correção
> ainda; são insumo para a próxima rodada.

1. **`transporte_views._limpar_gestao_custo_filho`, `reembolso_views` (excluir) e
   `folha_service.estornar_folha_do_mes` — o cânon pai×filho recalcula
   `valor_total` mas nunca `saldo`.** As três rotinas que a Onda 3 corrigiu ou
   escreveu seguem, **consistentemente**, o mesmo padrão parcial: quando o
   `GestaoCustoPai` sobrevive (porque ainda tem filho de outra origem), elas
   atualizam `valor_total` a partir dos filhos remanescentes e não tocam `saldo`.
   `financeiro_service.calcular_fluxo_caixa` lê `saldo` **primeiro**. Cenário
   concreto: um reprocesso de folha cujo pai é compartilhado com um filho de RDO
   deixa o pai sobrevivente com `saldo` fantasma da folha antiga somado ao pai
   novo da rodada nova — resíduo de duplicação, ainda que menor que o problema
   original. Correção futura: um helper compartilhado que, quando o pai
   sobrevive e `saldo` não é NULL, faça `pai.saldo = valor_total -
   (valor_pago or 0)`. (Achado da review final da branch, 27/08.)

2. **`_gemeos_compra`, `financeiro_service.py` — a família 1 dos gêmeos tem a
   MESMA evaporação que a D2 corrigiu na família 2.** A D2/Task 3.6 tornou
   `_gemeos_reembolso` consciente de estado, mas `_gemeos_compra` continua
   excluindo incondicionalmente: a obrigação some de `saidas_previstas` sem a
   outra perna do par ter entrado em projeção nenhuma. Exige um join novo,
   simétrico ao que a D2 já escreveu para reembolso. (Flagado pelo implementer
   da D2, 27/08.)

3. **`folha_service.py` (event_manager por funcionário) × view (agregado) — dupla
   via de criação de `LancamentoContabil` da folha.** Um tenant com plano legado
   e V2 ativos simultaneamente pode dobrar o razão na **primeira** rodada de
   folha, porque as duas vias criam lançamento independentemente. Não é um
   problema novo de reprocesso: o estorno da Task 8 já apaga as duas formas
   simetricamente, então reprocessar não compõe mais o defeito — mas a primeira
   rodada, nesses tenants, ainda pode dobrar. (Achado da Task 8, pré-existente à
   Onda 3.)

4. **`salvar_folha_processada` / `processar_e_salvar_folha_obra` — `FolhaProcessada`
   não é escrita por nada em produção.** As correções das dobras 2 e 3 da Task 9
   (o `salario_bruto` que duplica HE/DSR, e a folha inteira do mês lançada contra
   cada obra) estão corretas — mas dormentes: as duas funções não têm chamador
   fora de teste. Decisão do dono do repositório: ligar um chamador de produção,
   ou marcar o módulo como dormente explicitamente. Se for ligado, `folha_service.
   estornar_folha_do_mes` precisa crescer uma quarta tabela a estornar (apagar
   também `FolhaProcessada`), senão o reprocesso reintroduz o store velho ao lado
   do novo. (Review da Task 9 + review final da branch.)

5. **`utils.calcular_custos_salariais_completos` — código morto e quebrado.**
   `utils.py:315` usa `Funcionario` sem importar — todo chamador levanta
   `NameError`. Zero chamadores de produção além do próprio re-export. Apagar.
   (Descoberto no fix round da Task 10.)

---

## Achados novos da execução da Onda 5 (28/08)

> Nenhum destes estava na varredura de 25/08 — surgiram do próprio trabalho de
> corrigir os 10 achados desta onda. Não têm task nem commit de correção
> própria ainda (fora o (c), já consertado sem ligar rota nenhuma); são insumo
> para a próxima rodada.

(a) **`/api/registrar-facial` (`ponto_views.py`) não faz geofencing NENHUM.** A
    Task 1 tornou o geofencing impositivo em vez de consultivo — mas só na rota
    irmã. Esta rota nem chama o validador: um dispositivo fora do perímetro da
    obra bate ponto facial sem nenhuma checagem de posição, cercada ou não.
    (Observação da Task 1, 28/08.)

(b) **`services/contrato_obra.py:407` — o defeito descrito não reproduziu no
    cenário direto.** A varredura de 25/08 descrevia `_versao_vigente_da_obra`
    devolvendo, em memória, uma versão já encerrada como se ainda fosse
    vigente. No cenário direto isso **não** aconteceu: a query roda em
    `no_autoflush` e o identity map devolve o objeto já mutado, então o
    teste-pino nasceu verde. Pino de regressão
    `test_versao_encerrada_em_memoria_nao_e_vigente` adicionado; se houver um
    caminho real para o defeito, ele passa pelo fallback de `db.session.new`
    que o pino não exercita. Registrado como **não reproduzido, pino
    guardando** — não como corrigido. (Task 8, 28/08.)

(c) **`crud_rdo_completo.salvar_rdo` segue SEM rota — reservada ao Módulo 07.**
    O `func` não importado e os kwargs que `RDO` não aceita (`sequencial_ano`,
    `ano`) foram consertados no commit `ce331094`, junto com o resto da Task 6
    — a função agora está **consertada em vez de quebrada**, mas continua sem
    nenhum chamador de produção. Decisão pendente para o Módulo 07: ligar uma
    rota, ou apagar a função. (Task 6, 28/08.)


## Achados do `/code-review max` sobre a branch da Onda 5 (28/08)

> 🔴 **Passada nova, escopo novo: os 14 commits da branch
> `sdd/onda-5-o-recusado-para-de-ser-gravado`, DEPOIS de a onda ter fechado com
> gate verde de 2839.** Não são achados da varredura de 25/08 — são defeitos
> introduzidos ou deixados passar pela execução das ondas.
>
> **Por que existiram apesar do gate verde:** três dos testes centrais da Onda 5
> provam por `inspect.getsource()`. Um teste que lê o texto do código não vê o
> que o código faz.

### ✅ Corrigidos no fix round (`938cc92d`, `2d736fc0`)

| # | Arquivo:linha | Defeito |
|---|---|---|
| R1 | `services/entregas_terceiros.py:366` | O `db.session.rollback()` do `except` é da sessão INTEIRA e apagava a transação do chamador. Como a falha vira `(0, 0)`, o `except` do chamador nunca dispara: o RDO sumia, o commit persistia sessão vazia, a tela dizia sucesso. **Perda silenciosa.** → SAVEPOINT |
| R2 | `views/rdo.py:4116` | O ramo de edição de `ed85d117` nunca apagava os filhos: `custo_funcionario_dia.py:223-230` soma horas sobre todas as linhas do `rdo_id`, e o dia do trabalhador dobrava na 1ª edição. → delete igual ao de `rdo_salvar_unificado:2916-2941` |
| R3 | `views/rdo.py:4117` | `data_relatorio` parseada e nunca atribuída no ramo de edição; `x or rdo.x` não distinguia campo ausente de campo esvaziado |
| R4 | `views/rdo.py:4050` | `_rdo_alvo` filtrava `RDO.admin_id`, que é `nullable=True`: RDO legado caía na criação e produzia a duplicata que a correção existia para impedir. → `join(Obra)`, como `:2891` |

### ✅ Corrigidos pela onda "A Porta Irmã" (31/08)

> Plano: `docs/superpowers/plans/2026-08-28-a-porta-irma.md`. TDD com RED
> citado em todas as tasks. **Gate de fecho: 2854 passed, 6 skipped, 2
> xfailed, 0 failed** (43min55s) — o skipped caiu de 10 para 6, que é a Task 7
> devolvendo `tests/test_propagacao_proposta_obra.py` ao gate (os 6 testes do
> arquivo aparecem PASSED na saída).

| # | Arquivo:linha | Defeito | Commit |
|---|---|---|---|
| A1 | `views/aditivos_views.py:144` | Ação financeira irreversível pendurada em `PapelObra.GESTOR`, cujo predicado devolve GESTOR para todo usuário do tenant enquanto `escopo_obra_ativo` está desligado — o default. **Decisão D5: garantia própria na rota**, não ligar a flag; o fallback permissivo de `utils/autorizacao.py` fica como está, porque é escolha consciente e documentada | `da778eba` `5fa775e7` `959fca86` |
| A2 | `medicao_views.py:449` | O `@admin_required` do portal contornável trocando a URL: a mesma view responde em `/medicao/obra/<id>/gerar` e `/obras/<id>/medicao/fechar`. Decorator entra uma vez e cobre as duas | `d966b34a` |
| A3 | `views/rdo.py:3581` | `flash()` com 500 caracteres de `format_exc()` mais e-mail e admin_id. **A varredura achou um segundo site que o review não tinha visto:** `views/obras.py:2279`, mesma forma, com um comentário dizendo "modo desenvolvimento" que não checava nada | `d8ebbd61` |
| A4 | `production_routes.py:124,201,279,336,387` | `error_message=f"...{str(e)}"` sem gate, com `error.html:17` renderizando cru. O `:387` (safe-alimentacao) não passava `error_details` nenhum — a mensagem era o único vazamento da rota | `39fe3a85` |
| A5 | `ponto_views.py:2454` | Omitir `obra_id` (ou mandar um irresolvível) pulava o geofencing inteiro. A tela veio junto: dizia "Obra (opcional)" e mandava `obra_id: obraId \|\| null`, então o caminho padrão passaria a tomar 400 | `b3af3549` |
| A6 | `services/cronograma_apontamento_service.py:398` | Janela de `pct_ant` com `<` estrito não via o RDO irmão do mesmo dia. **A porta irmã estava dentro do próprio achado:** `acum_ant` (`:378`) tinha a janela idêntica no modo quantitativo — RDO B lia acumulado 40 onde o recompute lê 70 | `7d494cb9` |

### ✅ Corrigidos pelo plano "O Que Não Persiste" (31/08)

> Plano: `docs/superpowers/plans/2026-08-28-o-que-nao-persiste.md`. TDD com RED
> citado em todas as tasks. **Gate de fecho: 2872 passed, 6 skipped, 201
> deselected, 2 xfailed, 0 failed** (46min44s) — 18 verdes acima do piso de
> 2854 deixado pela onda "A Porta Irmã", e o skipped ficou nos mesmos 6.

| # | Arquivo:linha | Defeito | Commit |
|---|---|---|---|
| N1 | `portal_obras_views.py:647` | `db.session.commit()` sem guarda dentro do `except`, e a linha 648 relaiando a exceção crua para visitante **anônimo**. O commit da trilha de erro ganhou guarda própria, e a exceção parou de subir para o anônimo | `42c17ddb` |
| N2 | `models.py:7616` | A migration 315 alargou `uq_contrato_versao_vigente` para `(obra_id, admin_id)` e deixou a irmã `uq_contrato_versao_obra_versao` como `UNIQUE(obra_id, versao)`, enquanto `abrir_versao` numera por tenant: a obra travada continuava travada. Migration 316 dá o `admin_id` à irmã. **A porta irmã apareceu dentro do próprio fix:** `create_all()` roda ANTES das migrações em todo boot, então em banco novo o modelo criava a irmã como CONSTRAINT genuína enquanto a 316 sempre a tratou como ÍNDICE solto — `DROP INDEX` estourava `DependentObjectsStillExist`, e `IF EXISTS` não salvava | `416967b9` `f906e20f` |
| N3 | `services/cronograma_proposta.py:609,685` | `if not tarefa.ativa: tarefa.ativa = True` reimplementava, incompleto, o `reativar_tarefas_de_itens_reincluidos` do mesmo módulo: não limpava `arquivada_em` nem cascateava para as filhas arquivadas. Os dois ramos de reúso passam a delegar ao restaurador | `e404a5e8` `22fa7e4e` `915462d0` |
| N4 | `services/proposta_diff.py:92` | Comparava o snapshot `Numeric(15,2)` com o produto `quantidade × preco_unitario` não arredondado (até 5 casas): linha intocada virava "alterado", e `templates/propostas/comparar.html:78-79` imprimia um valor diferente do que o diff usava. A classificação passou a comparar em centavos e a tela mostra o mesmo número. **Fix round:** `total_do_diff` misturava centavos com valor cru e arredondava linha a linha — um reajuste distribuído por muitos itens, cada delta abaixo de meio centavo, somaria zero apesar do impacto agregado; agora soma bruto e arredonda uma vez só, no fim | `6ce5c90a` `aba6df97` |
| N5 | `portal_obras_views.py:774,696,786,939` | O redesenho "um evento commitado por tentativa" tinha sido aplicado a 2 das 6 rotas que registram trilha; `ver_comprovante` registrava e devolvia `send_file` sem commit algum, e **toda visualização de comprovante pelo cliente sumia no `session.remove()`**. As seis rotas commitam, e a tentativa recusada também deixa rastro | `b581da0d` |

⚠️ **O padrão do teste que nasce verde reapareceu aqui**, agora dentro do
próprio fix round: `test_reuso_por_chave_natural_restaura_a_tarefa_arquivada`
contava ocorrências de `.ativa = True` no fonte com `inspect.getsource()` — o
padrão que estes planos existem para eliminar — e **reprovava a melhora de
comportamento** do N3, porque delegar ao restaurador derrubava a contagem de 3
para 1. Reescrito em `915462d0` para provar pelo banco, via
`materializar_cronograma`, que o ramo de reúso em nível inferior restaura
`ativa`, limpa `arquivada_em` e cascateia para a neta arquivada.

### ✅ Um achado sobre o próprio gate — fechado pela Task 7 (`dd8ff183`)

📖 `tests/test_propagacao_proposta_obra.py:35` — a fixture faz
`Usuario.query.filter_by(tipo_usuario='ADMIN').first()`, um `.first()` **sem
`ORDER BY`** num banco com **185.784 ADMINs**, e `pytest.skip()` quando o
sorteado não tem obra. Qualquer escrita reembaralha o sorteio: no gate de
28/08 **4 testes pararam de rodar** sem que nada sinalizasse, e isso não havia
acontecido em nenhum dos oito gates anteriores. Não é regressão de código — é
uma verificação que parece cobrir mais do que cobre.

✅ **Fechado em `dd8ff183`:** a fixture semeia o próprio tenant em vez de
sortear entre os 185.784 ADMINs. No gate de fecho da onda (31/08) os **6**
testes do arquivo aparecem PASSED e o skipped total caiu de 10 para 6 — os 4
que a Task 7 devolveu. 🔬 A contagem "4" é a do ruling R7: o plano dizia 6, e 6
estava errado.


## Achados novos da execução da onda "A Porta Irmã" (31/08)

> Registrados no mesmo formato das Ondas 3 e 5: o que a execução revelou e o
> review não tinha visto.

1. **`views/obras.py:2279` — o gêmeo do vazamento do RDO.** Mesmo `flash` com
   `format_exc()` inteiro, e o comentário dizia "exibir traceback completo em
   modo desenvolvimento" quando não havia checagem nenhuma: ia para a tela em
   produção também. Só apareceu porque o guarda da Task 3 deixou de nomear
   módulos e passou a varrer o app. (Task 3, corrigido em `d8ebbd61`.)

2. **`services/cronograma_apontamento_service.py:378` — a porta irmã dentro do
   próprio achado.** O review nomeou o `pct_ant` (`:398`); o `acum_ant`
   (`:378`), que alimenta o modo quantitativo, tinha a janela estrita idêntica,
   e o `recomputar_cadeia` soma o irmão do mesmo dia nos DOIS modos. RED
   medido: RDO A executa 30 un, RDO B no mesmo dia executa 40, e o acumulado de
   B lia 40 em vez de 70. (Task 6, corrigido em `7d494cb9`.)

3. **A correção do geofencing quebrava a própria tela.** `ponto_views` passou a
   exigir `obra_id`, mas `templates/ponto/ponto_facial_automatico.html:131`
   dizia "Obra (opcional)" e o JS mandava `obra_id: obraId || null` — o caminho
   PADRÃO da interface passaria a tomar 400. Achado só porque se foi olhar quem
   chamava a rota. Backend e tela têm de mudar no mesmo commit. (Task 5,
   `b3af3549`.)

### 🔴 O padrão que se repetiu: o teste que nasce verde

**Em três das seis tasks, o teste escrito NO PLANO teria passado sem tocar no
defeito** — e teria sido commitado como prova.

| Task | O teste do plano | Por que não podia falhar |
|---|---|---|
| 3 | POST em `/rdo/salvar` com `obra_id` inexistente | Cai em `flash('Obra não encontrada')` + redirect (`:2951`), caminho validado que nunca chega ao `except`. Gatilho trocado por data em formato brasileiro, que estoura o `strptime` de `:2948` |
| 4 | GET nas cinco rotas `/prod/safe-*` | Só falharia se alguma rota errasse por conta própria no ambiente. O plano mandava forçar o erro à mão e desfazer; o erro passou a ser injetado pelo teste (monkeypatch em `get_safe_admin_id`, chamada dentro do `try` das cinco), para o teste seguir sendo guarda |
| 5 | POST facial sem `obra_id` | Morre em 404 "nenhum funcionário com foto cadastrada" antes do geofencing — e 404 estava na lista de status aceitos. Passou a semear foto e grampear os dois pontos que barram foto sintética |

**A leitura que importa:** esta onda nasceu porque três testes da Onda 5
provavam por `inspect.getsource()` — liam o texto do código e não viam o que
ele fazia. O plano proibiu `getsource()` explicitamente, e mesmo assim três dos
seus próprios testes traziam a versão seguinte do mesmo vício: **não ler o
texto, mas também nunca chegar ao código sob teste.** Proibir a técnica não
basta; o RED tem de ser medido e a mensagem do RED tem de citar o defeito, não
só um status aceitável.

Daí a regra que esta onda acrescenta, e que o teste da Task 4 já aplica: **um
teste de guarda tem de reprovar também quando o próprio gatilho para de
funcionar.** Ele exige status 500 em cada rota antes de olhar o vazamento — se
o erro injetado deixar de ocorrer, o teste acusa em vez de virar andaime verde.

---

## 02/09 — a suíte browser rodou inteira, e sobrou um achado

A primeira rodada completa da suíte (02/09, 46:08) devolveu **12 failed + 68
errors**. Eram **um defeito só**: fixture de escopo `session` segurando um
`with sync_playwright()` aberto envenenava todo teste de browser dos arquivos
seguintes (corrigido em `a80f1ddc`; guarda no gate em
`tests/test_contrato_isolamento_playwright.py`). Um segundo defeito, que o
primeiro escondia, era a jornada E2E criar o Cliente **depois** do GET da
página (corrigido em `160c7282`).

Depois dos dois, pelo runner retomável (`scripts/suite_resumavel.py`, 30
chunks, processo isolado por arquivo de browser): **3435 passed, 1 failed,
8 skipped, 72 xfailed**. Sobrou este:

### 🟡 P4 do RDO unificado espera o botão de equipe interna numa tarefa de subempreitada

- **Onde:** `tests/test_rdo_unificado_playwright.py:275-277` (asserção P4);
  `templates/rdo/novo.html:1262-1267` (ramo `isSub`) e `:1329` (ramo `else`).
- **O que acontece:** o teste exige `#btn-equipe-<t_sub_id>` presente numa
  tarefa cujo responsável é **Subempreitada**. No template, `btn-equipe-` só é
  emitido no ramo `else` (tarefa interna); o ramo `isSub` renderiza apenas
  `Total:` e o botão de terceiros. O comentário de `novo.html:1176` chama o
  `btn-equipe-` de "botão de **efetivo interno**".
- **Log:** `FAIL: P4 botão #btn-equipe-1887165 presente` — única asserção
  vermelha das ~20 do arquivo; P1, P2, P3, P5, P5b, P3b, P6 e as seguintes
  passam, inclusive o `#modalSubempreitada` abrindo com a tarefa
  pré-selecionada.
- **Por que NÃO foi corrigido aqui:** decidir isso é decisão de produto — ou o
  botão de equipe interna deve aparecer também em tarefa subempreitada (e o
  template regrediu), ou não deve (e a asserção P4 está desatualizada, mesma
  família das outras desta rodada). A rodada de 02/09 tinha constraint
  explícita de **não tocar em produção**, e não há evidência no repositório que
  decida a intenção. Quem souber a intenção fecha em uma linha, dos dois lados.
- **O que se sabe e o que não se sabe:** sabe-se que a asserção e o template
  discordam hoje. **Não** se sabe desde quando — a família browser nunca teve
  placar histórico, então isto não é presumida regressão.

---

## 02/09 — o pré-voo da Onda 4 acha o gêmeo vivo do módulo que a D4 apagou

A varredura de pré-voo da **Task 7** de `2026-08-31-fecho-do-que-esta-aberto.md`
(a regra da casa: pré-voo abre cada etapa) foi procurar se os alvos da Onda 4
ainda existiam na árvore de hoje. Dois haviam sido apagados — e um terceiro
arquivo, que **nenhum dos dois planos lista**, comete os mesmos defeitos.

### 🔴 `exportacao_relatorios.py` — inoperante, registrado, e mentindo `success: true`

- **É módulo vivo, não morto:** blueprint registrado em `main.py:157`
  (`url_prefix='/relatorios/exportacao'`) e na lista de módulos de
  `app.py:1108`. 📖 É o mesmo argumento que pôs `dashboards_especificos.py` no
  adendo de 28/08 da Onda 4.
- **Onde:** `_obter_dados_resumo_executivo` (`exportacao_relatorios.py:373-418`),
  alcançável por três rotas — `/gerar-pdf` (via `:97`), `/gerar-excel` (via
  `:245`) e `/api/preview-dados` (`:746`).
- **Os três defeitos, provados por execução e não por leitura:**
  1. `:380` — `UsoVeiculo.km_rodado`: `AttributeError: type object 'UsoVeiculo'
     has no attribute 'km_rodado'`. A coluna real é `km_percorrido`
     (`models.py:5265`). É o **terceiro** sítio do mesmo defeito: os outros são
     `dashboards_especificos.py:396, :448, :463` (o adendo de 28/08 os aponta em
     `:394, :446, :461` — as linhas andaram).
  2. `:396` `ManutencaoVeiculo` e `:404`, `:480-483` `AlertaVeiculo`: **nenhum
     dos dois importado**. O import de `models` (`:36-38`) traz só
     `db, Veiculo, CustoVeiculo, UsoVeiculo` → `NameError`.
  3. `AlertaVeiculo` **não existe no repo** — nem em `models.py`, nem em lugar
     nenhum: só o `AlertaVeiculoForm` (`forms.py:475`). É o mesmo caso do
     `AlocacaoVeiculo` que a Onda 4 cita para o módulo já apagado.
- **E o erro é engolido:** `:416-418` faz `except Exception: logger.error(...);
  return {}`, e `/api/preview-dados` responde `{'success': True, 'resumo': {}}`.
  🔴 **É exatamente a mentira que motivou a D4** — "responde `success: true` com
  forma vazia em vez de errar" — viva noutro arquivo, depois de o primeiro ter
  sido apagado.
- **Por que NÃO foi corrigido aqui:** é a mesma pergunta da D4 (apagar ou
  consertar), e a D4 foi respondida pelo **dono**, não pelo executor. Escalada
  como **D7** em `2026-08-31-decisoes-pendentes.md`.
- **O que se sabe e o que não se sabe:** sabe-se que as três rotas quebram na
  primeira requisição que chegue ao resumo executivo, e que o usuário vê PDF/
  Excel/preview vazios em vez de erro. **Não** se sabe se alguém as usa — não há
  teste que as chame (é a razão pela qual sobreviveram) e o repositório não
  registra chamador de produção.

### ✅ Um falso alarme desarmado no mesmo pré-voo

O cabeçalho da Onda 4 lista `ativo=True` "numa tabela sem `ativo`" entre os
defeitos de existência. 🔬 `Veiculo.ativo` **existe** (`models.py:5186`), e
`AlertaVeiculo.ativo` não é o caso porque a classe inteira não existe. Aquele
defeito morreu junto com o módulo apagado — quem for executar a Onda 4 não deve
procurá-lo.
