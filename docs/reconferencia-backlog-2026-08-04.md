# Reconferência do backlog — 2026-08-04

> ⚠️ **Superado em 23/08** — reconferência item a item em
> `docs/reconferencia-backlog-2026-08-23.md` (9 entregues, 7 parciais, 9
> abertas). Este documento fica como retrato de 04/08.

> **O que é:** a reconferência, **no código vivo**, das duas listas do
> `PLANO-NUCLEO.md` — o backlog de 25 automações (§5) e as 12 estruturas mortas
> (§6). Ambas foram escritas em **2026-07-31**. Entre 31/07 e 03/08 entraram os
> **dez pacotes** (p1..p10), que mexeram exatamente nessas áreas, e nenhuma das
> duas listas foi atualizada depois.
>
> **Contra o quê:** `main` no commit **`a723babe`** (03/08), árvore limpa.
>
> **Como foi feita:** cada um dos 37 itens foi aberto no arquivo. Mensagem de
> commit não valeu como evidência em nenhum ponto — só `arquivo:linha` no código
> atual. Onde o revisor e o cético divergiram, vale o cético, e a divergência
> está registrada na §5 deste documento.
>
> **O que este documento NÃO é:** não é spec, não é plano, não muda código.
> A regra da casa continua: nada aqui vira mudança sem spec própria em
> `docs/superpowers/specs/`.

---

## 1. A manchete

**Nenhum dos 25 itens do backlog pode ser riscado — zero entregues, 25 vivos
(13 podem começar hoje, 12 travados por decisão ou credencial) —, duas das 12
"estruturas mortas" têm leitor vivo em produção, e o achado mais caro é uma
regressão do próprio p1: os três caminhos que passaram a emitir `rdo_finalizado`
deixaram de gerar custo para mensalista e horista e emitem sem `obra_id`, então
por eles não sai nem custo nem medição.**

Três desdobramentos da manchete, porque a frase sozinha esconde o tamanho:

**A suspeita de partida estava errada em cinco de cinco.** Entrou-se nesta
reconferência achando que A05, A10, A13, A14 e A19 tinham sido entregues nos dez
pacotes. Nenhum foi. A10 chegou a receber veredito ENTREGUE do primeiro revisor
e foi **derrubado** pelo cético. Os outros quatro são PARCIAL — cada um com o
recorte do que sobrou nomeado em `arquivo:linha` na tabela da §3.

**A regressão do p1 é dinheiro perdido, não trabalho pendente.** O p1 trocou, em
três caminhos, a chamada direta a `gerar_custos_mao_obra_rdo` pela emissão do
evento `rdo_finalizado`, na premissa de que "o handler faz o que a chamada fazia,
mais o recálculo". Não faz. `gerar_custos_mao_obra_rdo` lê `RDOCustoDiario` e,
no fallback (`services/rdo_custos.py:396-413`), calcula `horas × valor_hora` para
quem não é diarista. Já `lancar_custos_rdo` usa só `funcionario.valor_diaria` e
faz `continue` quando ele é zero (`event_manager.py:730-733` — conferido linha a
linha). Como `models.py:302-303` tem `tipo_remuneracao` default `'salario'` e
`valor_diaria` default `0.0`, **todo mensalista e horista que antes gerava
`GestaoCustoFilho` por `POST /rdo/finalizar/<id>` e `POST /rdo/editar/<id>` hoje
não gera nada** — e o benefício (VA/VT) some junto, porque o bloco de benefícios
(`event_manager.py:872-889`) está depois do `continue`. Some-se a isso que os
três payloads emitem literalmente `{'rdo_id': rdo.id}`
(`crud_rdo_completo.py:475`, `:592`, `rdo_editar_sistema.py:557` — verificados
agora), e `recalcular_medicao_apos_rdo` sai em `event_manager.py:1529-1531` por
falta de `obra_id`. Ou seja: o objetivo declarado do p1 Step E ("custo implica
medição") **não é atingido em nenhum dos três caminhos tocados**, e o custo que
funcionava foi junto.

**Os testes-guarda dos pacotes são de forma, não de comportamento.**
`tests/test_p1_dedup_cross_origem.py:151-165` varre só as strings de dois
arquivos e nunca `views/rdo.py`; `tests/test_p5_aprovacao_semeia_obra.py:210-220`
faz `texto.count(...) == 2` e diz no docstring que cobre o caminho de importação,
que não cobre; `tests/test_p4_formula_unica_progresso.py:133-177` abre arquivos e
procura nomes de função. Nenhum exerce rota. **O gate verde de 03/08 não
contradiz nada deste documento** — ele nunca chegou a olhar.

---

## 2. Antes da tabela: duas estruturas dadas como mortas NÃO estão mortas

Este é o achado mais importante da §6 do `PLANO-NUCLEO.md`, e vale mais que
qualquer linha da tabela porque é um erro de **método**, não de drift.

### `ObraSignatarioCliente.email` (E03) — a alegação já nascia errada

O enunciado de 31/07 diz "gravado e jamais consumido para envio, exibição ou
payload". **Exibição existe e é visível ao usuário:**
`templates/obras/_signatarios_cliente.html:74` renderiza
`{% if s.email %} · {{ s.email }}{% endif %}`; o parcial entra por
`templates/obra_form.html:550`, alimentado por `views/obras.py:1137-1141`.

O agravante: `git log -L 74,74:templates/obras/_signatarios_cliente.html` aponta
para **`1fbc97c0`, de 2026-07-29** — Fase 9a, **dois dias antes** do documento
que declarou a coluna morta. Não foram os dez pacotes que ressuscitaram nada: a
linha estava errada quando foi escrita. É exatamente o padrão da armadilha nº 7
do `ESTADO-ATUAL.md` (`Obra.regime_medicao`, dada como não-lida enquanto
`cronograma_views.py:732` já a lia). **Nada a aposentar.** Do enunciado só
sobrevive a parte estreita: o e-mail não é usado para **envio** (não há SMTP —
ver E12) nem entra em payload de webhook.

### `subatividade_mestre_id` como ponte (E11) — o p8 a ressuscitou

Deixou de ser morta em 03/08, pelo `ecf7f3a9`: `services/progresso_subatividade.py:41`
cruza `TarefaCronograma.subatividade_mestre_id` com a obra, e `:66`
(`percentual_derivado`) devolve `(percentual, origem)`. O consumidor de produção
é real: `services/medicao_service.py:279-284`, que substituiu o antigo
`MAX(RDOServicoSubatividade.percentual_conclusao)`.

Mas a leitura é **mais estreita do que "o p8 passou a lê-la"** sugere: o único
consumidor está atrás do gate `if perc_atual <= 0 and item.servico_id`
(`services/medicao_service.py:277`) — item comercial com vínculo de cronograma
nunca passa por ali. E `percentual_do_servico_na_obra` faz um SELECT por linha de
RDO (loop em `services/progresso_subatividade.py:114-118`): N+1 dentro do
recálculo da medição. A **escrita** segue dual, como o próprio módulo declara em
`services/progresso_subatividade.py:24-31`. Não é aposentadoria, é o oposto — e o
resto do p8 continua aberto como A18.

**Consequência de método para a próxima lista de estruturas mortas:** "grep por
instanciação" não prova morte. Nos dois casos o consumo estava em template
(E03) ou em serviço novo (E11), e nos dois a busca por `Classe(` ou por escrita
devolveria vazio.

---

## 3. O backlog de 25 automações

Legenda de veredito: **ABERTO** (nada entregue) · **PARCIAL** (entregue em parte,
com o recorte do que sobra explícito) · **MUDOU_DE_FORMA** (o problema descrito
não existe mais; outro nasceu no lugar). Nenhum item recebeu **ENTREGUE**.

Coluna "Esforço": `P/M/G` revisado; onde mudou em relação a §5 do
`PLANO-NUCLEO.md`, aparece `antes → agora`.

| # | Veredito | Evidência (`arquivo:linha`) | O que sobra | Esforço | Bloqueio |
|---|---|---|---|---|---|
| **A01** Transferências do extrato no confirm | **ABERTO** | Detecção e payload existem (`services/importacao_excel.py:1961-1969`, `importacao_views.py:473`/`:550`, `templates/importacao/preview_fluxo.html:786-845`); o confirm nunca lê — `importacao_views.py:783-946` não toca `payload['transferencias']` nem `transf_origem_*`, e `svc.importar({...})` em `:942-946` passa só entradas/saídas/batch_id | Tudo. Ler o payload + `request.form['transf_origem_<i>']`/`transf_destino_<i>` em `importacao_views.py:783-946`, validar bancos contra o tenant (padrão de `_obra_segura`, `:795-803`) e gerar o par SAÍDA/ENTRADA com `import_batch_id` via `services/importacao_excel.py:2129`, que hoje nem aceita a chave | P | — |
| **A02** `FluxoCaixa` na baixa de ContaReceber | **ABERTO** | Lado pagar faz (`financeiro_views.py:391`, `:402-420`); `receber_conta` (`financeiro_views.py:631-663`) chama `baixar_recebimento` e vai direto ao flash. `financeiro_service.py:297-393` nunca toca FluxoCaixa. Leitura já existe e não é alimentada: `financeiro_service.py:686-696` consulta `referencia_tabela='conta_receber'`, escrito só pelo import (`services/importacao_excel.py:2489-2503`) | Espelhar `financeiro_views.py:402-420` dentro de `receber_conta` (após `:656`) com `tipo_movimento='ENTRADA'`, `referencia_tabela='conta_receber'`; acrescentar `criar_fluxo_caixa` + `categoria_fluxo_caixa_id` em `templates/financeiro/receber_conta.html` | P | — |
| **A03** Conta contábil na CR OBR-MED | **ABERTO** | `services/medicao_service.py:369-383` cria a CR sem `conta_contabil_codigo` (o ramo de update em `:390-409` também não). O gate `if conta.conta_contabil_codigo:` em `financeiro_service.py:332` pula a partida dobrada (`:333-385`) **sem log de aviso** | Preencher o campo em `services/medicao_service.py:369-383` (candidato: `4.1.01.001 Receita de Serviços`, já em `_V2_CONTAS_SEED`) ou trocar o gate mudo de `financeiro_service.py:332` por fallback + log. Hoje todo recebimento de medição fica fora da partida dobrada | P | — |
| **A04** `DESPESA_GERAL` no `MAPEAMENTO_CONTABIL` | **ABERTO** | `contabilidade_utils.py:1536-1543` tem seis chaves, nenhuma `DESPESA_GERAL`; os dois pagamentos chamam com esse tipo (`gestao_custos_views.py:839-845` e `:987-993`). `contabilidade_utils.py:1685-1688` só faz `logger.warning` + `return False` — os `except` dos chamadores nem rodam. Falha silenciosa | A entrada no dicionário (`:1536-1543`) e, provavelmente, a conta de débito no `_V2_CONTAS_SEED` (`:1547-1592` — hoje só combustível/transporte/material). O código é uma linha; o que falta é a conta | P | ⚖️ Decisão 5 (`PLANO-NUCLEO.md:541`), ainda sem marca de resolvida na §7 |
| **A05** Emitir `rdo_finalizado` nos 4 caminhos | **PARCIAL** | Dos 4 caminhos que só chamavam o serviço, o p1 tocou 3; o 4º segue intacto: `views/rdo.py:3425` (`rdo_salvar_unificado`, rota `POST /rdo/salvar`, usada também por `views/rdo.py:3461`) chama e não emite — os únicos `emit` do arquivo são `:1767`, `:2164`, `:4500`. Os 3 tocados emitem `{'rdo_id': rdo.id}` sem `obra_id` (`crud_rdo_completo.py:475`, `:592`, `rdo_editar_sistema.py:557`) e `event_manager.py:1529-1531` retorna | (a) `'obra_id': rdo.obra_id` nos três payloads; (b) `views/rdo.py:3425` emitir em vez de chamar, e incluir `views/rdo.py` na varredura de `tests/test_p1_dedup_cross_origem.py:156`; (c) **não fechar sem desfazer a regressão de custo** (ver §1) — ou `lancar_custos_rdo` passa a ler `RDOCustoDiario`/`horas×valor_hora`, ou os 3 voltam a chamar o serviço **e** emitir, como já fazem `views/rdo.py:2157+2164` e `:4490+4500`; (d) teste que exercite as rotas com funcionário `tipo_remuneracao='salario'`, `valor_diaria=0`. Fora do recorte literal: `views/rdo.py:718` (`criar_rdo`) finaliza em `:787` sem custo nem evento | P | — |
| **A06** Replanejar curvas após recálculo do editor v2 | **ABERTO** | `utils/cronograma_engine.py:1120` define `replanejar_curvas_obra`; único caller de produção é `services/cronograma_versao_service.py:443`. As 6 rotas de escrita do editor v2 só chamam `recalcular_obra`: `cronograma_views.py:866-868`, `:1150-1152`, `:1261`, `:1308`, `:1416-1418`, `:1666-1668`, `:1710-1712`. Os commits do p2 (`41f23403`, `ff94240d`) não têm uma linha de A06 | Chamar `replanejar_curvas_obra` nos 6 pontos. Detalhe que não pode ser ignorado: a função **commita por dentro** (`utils/cronograma_engine.py:1177`) e chama `sincronizar_percentuais_obra` (`:1178`) — tem que ser pós-commit, no padrão de `services/cronograma_versao_service.py:432-457`, com try/except que loga e não desfaz a edição | P | — |
| **A07** Pré-preencher proposta e obra com os IDs do CRM | **ABERTO** | Emissor OK (`crm_views.py:936-941` e `:972-978` montam `?cliente_id=&lead_id=`). Receptor descarta: `propostas_consolidated.py:1183-1188` é `redirect(url_for('propostas.nova'))` **sem query string**; `propostas_consolidated.py:507-540` não lê `request.args`; `views/obras.py:292-294` idem no ramo GET (render em `:518-523`). Templates também não resgatam | Três consertos, e nenhum funciona sozinho: (1) repassar `**request.args` em `propostas_consolidated.py:1188` (ou o CRM apontar para `propostas.nova`); (2) ler os args em `propostas_consolidated.py:510-540`, carregar o Cliente com escopo de `admin_id` e mandar hidden `lead_id`; (3) mesma leitura em `views/obras.py:294` → render de `:518` | P | — |
| **A08** Import de alimentação gerar custo | **ABERTO** | `services/importacao_excel.py:883-920` cria só `AlimentacaoLancamento` + M2M por SQL cru; zero `CustoObra`, zero `registrar_custo_automatico`, zero contábil, zero evento. O formulário v2 faz tudo (`alimentacao_views.py:488-548`) e o irmão do próprio importador também (`services/importacao_excel.py:1017-1036`, transporte). Importador ligado: `MODULO_MAP` em `:2549`, consumido por `importacao_views.py:226`/`:279` | `registrar_custo_automatico(tipo_categoria='ALIMENTACAO', origem_tabela='alimentacao_lancamento', ...)` dentro do savepoint de `:889`. Falta insumo no `processar`: `:869-879` devolve `restaurante` como **texto livre** (sem `entidade_id`) e não coleta `centro_custo_id`/`obra_servico_custo_id` — sem isso só dá para a versão agregada por obra | P | ⚖️ Rateio por centro de custo × agregado por obra, e o que fazer com o restaurante que vem só como texto (`PLANO-NUCLEO.md:489`) |
| **A09** Dedup de NF na entrada manual de almoxarifado | **ABERTO** | `views/almoxarifado/movimentos.py:37-203` grava `nota_fiscal` sem verificação (`:107`, `:159`, `:178`); idem `:208-390` (`:322`, `:363`, `:382`). A única guarda é por número de série (`:88-96`, `:263-271`). O caminho XML tem dedup (`almoxarifado_utils.py:254-257`, `sha256`). O p1 admite por escrito que não trata (`docs/superpowers/specs/2026-08-03-p1-...-design.md:181`); `git log --since=2026-07-30` no arquivo: vazio | Guarda por `(nota_fiscal, fornecedor_id, admin_id)` antes dos inserts de `:101`, `:154`, `:316`, `:355` — NF vazia tratada como "sem chave", senão toda entrada sem NF colide. **De brinde:** `almoxarifado_utils.py:257` consulta `NotaFiscal` por `xml_hash` **sem filtrar `admin_id`** — a mesma NF importada por outro tenant faz o dedup recusar a nota do tenant atual | P | — |
| **A10** Idempotência no custo de horista do ponto | **MUDOU_DE_FORMA** *(era ENTREGUE — derrubado, ver §5)* | A guarda existe e o defeito antigo morreu: `event_manager.py:524-530` busca por (funcionário, data, obra, admin, `categoria='PONTO_ELETRONICO'`) e atualiza (`:532-545`) em vez de inserir (`:547-563`). Mas a chave **não amarra em `registro_ponto.id`** e não há unique em `RegistroPonto(funcionario_id, data)` (`models.py:800-804`: três índices não-únicos). `views/admin.py:98-176` (`POST /novo_ponto`) cria `RegistroPonto` **incondicionalmente** (`:150`, ao contrário de `ponto_service.py:105-109`) e emite (`:185`) | O problema novo: dois lançamentos manuais no mesmo dia/obra (manhã 4h + tarde 4h) — o segundo cai em `:532` e **sobrescreve** o custo do primeiro. Antes eram duas linhas somando 8h; agora é uma de 4h. Dupla contagem virou **perda de custo**, na mesma superfície. `tests/test_p1_fallback_e_idempotencia.py:119-135` sempre reusa o mesmo `RegistroPonto` e não cobre o caso. **Adjacentes (não são A10, mas não registrá-los seria omissão):** `ponto_views.py:1506-1519` e `views/api.py:398-419` só emitem para `tipo_remuneracao=='diaria'` → horista importado ou lançado em lote nunca gera custo; `ponto_views.py:2178-2494` (quiosque facial) não emite nada; `ponto_views.py:1563-1755` emite sem calcular horas → sai em `event_manager.py:491`; dois deletes sem cascata de `CustoObra` (`ponto_views.py:901-943` e `:792-811`); dias históricos com N linhas seguem com N, e o `.first()` de `:524-530` não tem `order_by` | P (recorte novo) | — |
| **A11** Unificar os dois mecanismos de custo do RDO | **PARCIAL** | Entregue **ponto × RDO**: `event_manager.py:722-726` (`existe_ponto_no_dia`), `:826-840` (chave larga sem `origem_tabela`), `:910-921` (VA/VT). **Não** entregue o recorte do item (`rdo_custo_diario` × `rdo_mao_obra`): `services/rdo_custos.py:422-427` e `:463-468` seguem com `filter_by(origem_tabela=..., origem_id=...)` estrito, `'rdo_custo_diario'` (`:384`) contra `'rdo_mao_obra'`/`rdo.id` (`event_manager.py:860-861`) | (1) Dupla contagem viva por ordem de execução: `views/rdo.py:1767` só emite → filho com `('rdo_mao_obra', rdo.id)`; edição posterior por `atualizar_rdo` procura `('rdo_custo_diario', custo_dia.id)`, não acha e cria o **segundo** filho — `remover_custos_rdo` (`services/rdo_custos.py:90-140`) nunca alcança o filho do handler. (2) Chave cruzada em `services/rdo_custos.py:422` e `:463` espelhando `event_manager.py:826`. **Quatro buracos que o recorte original não listava:** a guarda inversa do handler de ponto só existe no ramo diarista e só contra `'rdo_mao_obra'` (`event_manager.py:381-390`); o ramo horista (`:487-563`) não tem guarda cruzada contra o `CustoObra` categoria `'RDO'` (`:787-808`); a chave larga de `:826-840` **não tem `obra_id`** (funcionário em duas obras no mesmo dia é contado uma vez por um trilho e duas pelo outro); e `tests/test_p1_dedup_cross_origem.py:149-163` não olha `views/rdo.py` | M | ⚖️ Qual mecanismo é canônico (valor por diária × `componente_folha` rateado) — os dois produzem números diferentes para o mesmo dia |
| **A12** Reprocesso de folha estornar antes de recriar | **ABERTO** | `folha_pagamento_views.py:148-153` faz `delete()` + commit e nada mais. Os efeitos colaterais não são estornados: `:226-266` cria `GestaoCustoPai`/`Filho` sem checar existência; `:198-200` emite `folha_processada` → `event_manager.py:1235-1236` cria Lançamento/Partida; `:281-288` chama `gerar_lancamento_contabil_automatico`. `git log --since=2026-07-30` no arquivo: vazio; não há teste de reprocesso | Tudo. Cada reprocesso duplica (a) o par Pai/Filho por funcionário, com os filhos antigos virando órfãos apontando `folha_id` já deletado; (b) o lançamento do handler; (c) o agregado de `:281-288`. Precisa de estorno explícito antes do `delete()` de `:149-152` | M | ⚖️ Estornar lançamento emitido × lançar contrapartida; e pai da Gestão de Custos já **pago** não pode simplesmente sumir |
| **A13** Orçado deixa de herdar venda | **PARCIAL** | **Consumo consertado:** `services/custo_orcado.py:51` e `:93` aplicam "linha de custo vence agregado" (fallback em `:87`/`:125`); consumidores ligados em `services/resumo_custos_obra.py:262-263`, `services/cronograma_fisico_financeiro.py:287-288`, `services/evm.py:167-168`, `cronograma_views.py:2138-2139`. **Origem intacta:** `models.py:7544`/`:7553` (`valor_orcado = target.valor_comercial`), `medicao_views.py:314`, `views/catalogo_views.py:886` | Origem: os 3 escritores + backfill das obras já gravadas (adiado por decisão em 03/08). E consumidores que o p3 não migrou e leem venda como custo: `utils/notifications.py:40-49` (`servico_estourou`, vivo por `views/planejamento_custos_views.py:98` e `views/obras.py:2166` — o alerta de estouro só dispara depois que o custo passa do **preço de venda**); `views/catalogo_views.py:675-676`; `models.py:7198-7200` (`saldo`). **Dois não listados antes:** `services/resumo_custos_obra.py:192-198` rateia o realizado com peso `valor_orcado/total_orcado`, isto é, distribui **custo real com peso de preço de venda**, no mesmo arquivo cuja linha 263 já lê o número certo; e `templates/obras/planejamento_custos/lista.html:95`/`:98` exibem `s.valor_orcado` cru e `s.saldo` na **mesma tela** cujo cabeçalho já usa o resumo do p3 — a soma das colunas não fecha com o total, e a divergência é visível ao usuário | M | ⚖️ Decisão 3 de 03/08 ("consertar no consumo") adiou a origem; sem revertê-la, só os consumidores residuais andam |
| **A14** Aprovação semeia serviços e fecha o lead | **PARCIAL** | Semeadura correta e idempotente: `handlers/propostas_handlers.py:179-243` (campos batem com `models.py:603-628`). Fecho do lead existe: `:246-282`. Chamadas só em `:427-428` e `:493-494`. Mas `:378-384` (`if valor_total <= 0 or skip_contabil:`) dá `return` **antes** das duas — e `services/importacao_fisico_financeiro.py:572-578` emite com `'skip_contabil': True` | (1) O caminho de **importação** (e toda proposta de valor zero) continua nascendo sem serviço: falta chamar as duas funções no branch de `:378-384`. O teste `tests/test_p5_aprovacao_semeia_obra.py:210-220` diz no docstring que cobre esse caminho e só faz `texto.count(...) == 2` — as duas ocorrências são o fluxo normal e o `delta == 0`. (2) `_fechar_lead_da_proposta` é **inalcançável em produção**: filtra por `Lead.proposta_id` (`:263`) e nada grava o campo (`grep proposta_id crm_views.py` não retorna nada; `grep lead_id propostas_consolidated.py` idem) | M | Depende de **A07**: enquanto `?lead_id=` morrer no redirect de `propostas_consolidated.py:1188`, o fecho entregue continua inerte. É dependência de código, não decisão |
| **A15** Unificar a medição do portal com o trilho ponderado | **PARCIAL** | O p6 não encostou no portal (mexeu no gate de peso, `services/medicao_service.py:114-128`); quem tocou foi o p4 (`portal_obras_views.py:766-771`, racional em `:745-765`). A rota segue sendo **gerador paralelo**: `portal_obras_views.py:775-790` cria `MedicaoObra` sem nenhum `MedicaoObraItem`, sem escrever `ItemMedicaoComercial.percentual_executado_acumulado` e sem chamar `recalcular_medicao_obra`. Ambos numeram pela mesma sequência (`:727-734` × `services/medicao_service.py:133-136`); os dois botões estão vivos (`templates/obras/detalhes_obra_profissional.html:1638` e `templates/medicao/gestao_itens.html:510`) | Os dois geradores escrevem a **mesma tabela com semânticas diferentes**: `portal_obras_views.py:782-783` grava `valor_medido = valor_contrato × perc/100` (**acumulado**) e `services/medicao_service.py:195` grava o valor do **período**. A medição do portal não move dinheiro: `_recalcular_imc_avanco` (`:242-308`) ignora `MedicaoObra`. **E nem a fórmula ficou unificada:** `progresso_ponderado_armazenado` (`utils/cronograma_engine.py:1074-1095`) pondera todas as folhas por `duracao_dias` filtrando `is_cliente=False`/`responsavel='empresa'`, enquanto `calcular_percentual_item` (`services/medicao_service.py:48-65`) pondera por `ItemMedicaoCronogramaTarefa.peso` só das tarefas vinculadas, sem filtro de responsável — para a mesma obra e data os números divergem por construção, e o "Pronto quando" do p4 (`PLANO-NUCLEO.md:332`) não é satisfeito. Falta a rota delegar a `gerar_medicao_quinzenal` ou ser aposentada | M | ⚖️ Decisão 4 (`PLANO-NUCLEO.md:540`) + dualidade de fonte do p8/A18 (`portal_obras_views.py:759-765` registra que migrar agora zeraria obra que avança por import sem RDO) |
| **A16** Consertar o sync alocação → ponto | **PARCIAL** *(recorte derrubado, ver §5)* | Defeito NOT NULL corrigido nos dois ramos (`models.py:4626`, `:4797`). Guarda contra sobrescrita existe: `models.py:4580-4598` (`tem_batida_real`). Defeito 3 **continua**: `grep EventManager models.py` não devolve nada; `:4642-4654` e `:4798-4806` fazem `add`+`commit` e retornam; nenhum listener compensa; o caller externo `equipe_views.py:1236` também não emite | (a) A guarda é `bool(hora_entrada or hora_saida)` — **ausência classificada não tem nenhuma das duas**: `ponto_service.py:330-360` cria `RegistroPonto(tipo_registro='falta'/'atestado')` sem hora, e o plano sobrescreve tudo (`models.py:4602`, `:4604-4605`, `:4614`, `:4616` → 8h por `:4660-4664`). **O atestado vira dia trabalhado de 8h, em silêncio.** (b) Emitir `ponto_registrado` nos dois ramos de criação (`:4623-4642`, `:4785-4798`) **e** no preenchimento do registro vazio (`:4602-4616`) — sem isso, `services/rdo_custos.py:368-373` continua pulando o lançamento do RDO com a justificativa "já tem ponto", e o dia **perde** o custo pelos dois lados. (c) `ponto_views.py:2369` e `ponto_service.py:344` também não emitem — a frase "todos os outros pontos de criação emitem" é falsa | M → **P** | ⚖️ Ponto **semeado** pelo plano (turno previsto, sem batida) deve gerar custo? O código é pequeno; a resposta não |
| **A17** Pré-carregar a mão de obra do RDO da presença do dia | **ABERTO** | `views/rdo.py:622-714` (`novo_rdo`): `:632` carrega a lista inteira de funcionários do tenant, sem recorte de dia nem obra; o único pré-carregamento é de **atividades** (`:642-679`); o render (`:703-713`) não passa nada de presença. `grep RegistroPonto` em `views/rdo.py`, `crud_rdo_completo.py` e `rdo_editar_sistema.py`: vazio. `templates/rdo/novo.html` não menciona ponto nem alocação. Bate com o que o p7 declarou não entregue (`ecf7f3a9`) | Tudo: (a) buscar `RegistroPonto` do dia+obra e/ou `AllocationEmployee` em `views/rdo.py:622-714` e mandar a equipe ao template; (b) renderizar as linhas em `templates/rdo/novo.html`; (c) alerta de divergência entre quem bateu ponto e quem foi apontado. A dependência do p1 já está satisfeita (`services/rdo_custos.py:25-53`), então pré-carregar não duplica custo | M | — |
| **A18** Derivar progresso entre trilhos via `subatividade_mestre_id` | **PARCIAL** | Leitura entregue (ver §2/E11), com **um único** consumidor de produção e ainda atrás de um gate de fallback (`services/medicao_service.py:277-286`). O elo do lado RDO é gravado em `views/rdo.py:4015`, `rdo_editar_sistema.py:296`/`:322` e `crud_rdo_completo.py:366`, mas **não** em `views/rdo.py:3190-3200`/`:3251` — rota `POST /rdo/salvar`, viva e auto-declarada legada (`views/rdo.py:2772-2782`, log `[LEGACY-RDO]`) | (1) **Escrita segue dual**: `RDOServicoSubatividade.percentual_conclusao` é gravado em 7 pontos sem write-through, e `TarefaCronograma.percentual_concluido` por caminhos independentes (`cronograma_views.py:1016`, `:1161`, `:1176`; `services/importacao_fisico_financeiro.py:214`; `services/cronograma_versao_service.py:622`, `:796`; `utils/cronograma_engine.py:459`, `:556`, `:1286-1313`). (2) **Leitores ainda crus**: `services/rdo_pdf_service.py:196-205`, `views/rdo.py:2524-2536`, `:2656-2666`, `views/obras.py:744-756` (SQL cru, **sem filtro de `admin_id`**), `utils/cronograma_engine.py:1024-1040`. (3) `views/rdo.py:3190-3200` precisa gravar `subatividade_mestre_id`, senão RDO dessa rota nasce sem elo e a derivação cai em `'linha'` em silêncio | M → **G** | ⚖️ Decisão 4 (`PLANO-NUCLEO.md:335`): recalcular ou congelar `MedicaoObra` históricas — unificar a escrita muda o número que multiplica `valor_contrato` em `portal_obras_views.py:768` |
| **A19** Fórmula única de progresso | **PARCIAL** | As **cinco** fórmulas nomeadas pelo p4 sumiram, conferidas uma a uma: `portal_obras_views.py:766-774`; `views/dashboard.py:455-461`; `:994-996`; `cronograma_views.py:369-391` (SUM(pct×peso)/SUM(peso) só sobre folhas vivas); `templates/obras/cronograma.html:162` só formata `progresso_geral_header`. Mas o "Pronto quando" não se cumpre: a mesma forma está reimplementada em 4 lugares, sobre 2 fontes | (a) Mesma forma, 4 implementações: `utils/cronograma_engine.py:839` (fonte apontamento, peso quantidade), `:1043` (fonte coluna, peso duração), `cronograma_views.py:369-391` (SQL própria) e `:503-513` (média em Python, modo cliente) — o próprio comentário de `:365-368` admite que o índice não é bit-idêntico. (b) Família V1 intocada, com fórmulas diferentes entre si: `views/rdo.py:1332-1335`, `:2524-2536`, `services/rdo_pdf_service.py:196-205`, `crud_rdo_completo.py:132-135`, `views/obras.py:742-756`, `utils/cronograma_engine.py:1024-1040`. **Três omissões do recorte original:** existe um **sexto** gerador de número, `services/medicao_service.py:196-198` (`Σ valor_executado_acumulado / valor_contrato`), gravando a mesma coluna `MedicaoObra.percentual_executado` que o portal, e virando `valor_medido` — é a fórmula mais cara; o portal se contradiz (`portal_obras_views.py:176-178` mostra ao **cliente** a fonte apontamento e `:766-768` **fatura** pela fonte coluna: obra que avança por `.mpp` sem RDO mostra 0% e recebe medição de 80%); e o dashboard só unificou dentro de `if rdo_mais_recente and ...` (`views/dashboard.py:446`), zerando em `:466` obra com cronograma a 60% e sem RDO. *Confiança do item: média-alta — alta nas omissões, média em afirmar que não há um sétimo caminho, porque o app não foi executado.* | M | ⚖️ A convergência das **fontes** foi reescopada para p8/A18 (decisão `PLANO-NUCLEO.md:335`). A consolidação da família V1 em `_progresso_fallback_subatividades` **não depende de decisão nenhuma** |
| **A20** Pré-preencher o pedido com o vencedor da cotação | **ABERTO** | O vencedor é gravado (`models.py:6917-6922`, `:6944-6946`; espelhado em `portal_obras_views.py:843-852`) e a requisição sabe o mapa (`models.py:5599-5612`, preenchido em `compras_views.py:1302-1344`). Nada chega ao pedido: `compras_views.py:1406-1423` monta a lista inteira de fornecedores e nunca lê `requisicao.mapa_v2`; `templates/compras/requisicao_detalhe.html:173-178` não tem `selected`; `compras_views.py:1644-1653` pega `fornecedor_id` cru do form; os preços em `:1673-1687` vêm de `preco_estimado`, não de `MapaCotacao.valor_unitario`. A rota avulsa (`:532-566`) também não | Tudo — e há um obstáculo estrutural que a estimativa "P" não previa: `MapaFornecedor` (`models.py:6887-6904`) guarda o fornecedor só como `nome` (String(200)), **sem FK para `Fornecedor`**; o mapa v1 idem (`models.py:6793`). Pré-preencher exige casar nome→Fornecedor (frágil) ou acrescentar `MapaFornecedor.fornecedor_id` + migração + tela de amarração | P → **M** | — |
| **A21** FK de frota no equipamento do RDO + TypeError de kwargs | **ABERTO** | `models.py:1341-1350`: `RDOEquipamento` sem nenhuma FK para `Veiculo` (`models.py:4873`); templates com texto livre (`templates/rdo/novo.html:378`, `templates/rdo/editar_rdo.html:366`/`:442`); parse/persistência por string (`utils/rdo_equip_ocorr.py:41-56`, `:79-97`). TypeError intacto: `crud_rdo_completo.py:428` (`horas_utilizacao=`), `:429` (`observacoes=`), `:449` (`descricao_completa=`) — kwargs que não existem nos modelos | (a) Coluna `veiculo_id` + migração + select nos dois templates + parse/persistência. (b) Os três kwargs. **Recorte que muda a urgência:** o bloco está dentro de `salvar_rdo()`, função **sem rota** desde `b30923b5` (`crud_rdo_completo.py:237-254` documenta), sem chamadores fora de testes — o TypeError é **latente em código morto**. Os dois caminhos vivos (`views/rdo.py:865-866`, `rdo_editar_sistema.py:509-510`) usam `replace_equipamentos_ocorrencias`, com os kwargs corretos (`utils/rdo_equip_ocorr.py:82-88`, `:106-112`) | M | — |
| **A22** Select de cliente na proposta manual + persistir CPF/CNPJ | **ABERTO** | `git show --stat af29acc1` (p5): só `handlers/propostas_handlers.py` e o teste. `git log --since=2026-07-30` em `propostas_consolidated.py` e no template: vazio. Hoje: `templates/propostas/nova_proposta.html:78` é `<input name="cliente_nome">` (sem `<select name="cliente_id">` em lugar nenhum) e `:94` é `cliente_cpf_cnpj`; `propostas_consolidated.py:559` lê `cliente_documento` e a variável **morre ali** — o construtor de `:647-659` nunca grava documento nem `cliente_id` | (a) Popular `nova()` (`:507-539`) com os Clientes do tenant, trocar o input por select que poste `cliente_id`, e atribuir `proposta.cliente_id` em `:647-659` (a FK existe: `models.py:3571`). (b) Não há onde persistir o documento: `Proposta` (`models.py:3571-3580`) não tem coluna — ou grava via `cliente_id` → `Cliente.cnpj` (`models.py:3354`), ou coluna nova + migração. Efeito colateral aberto: `services/cliente_resolver.py:100-133` desduplica só por e-mail e nome, nunca por CNPJ | P | — |
| **A23** Aviso interno de comprovante e decisão de compra do portal | **ABERTO** | `portal_obras_views.py:567-609` (`upload_comprovante`) termina em `logger.info` + flash ao cliente; `:453-531` (`aprovar_compra`) e `:536-563` (`recusar_compra`) idem. `grep notific\|emit\|EventManager` no arquivo inteiro (1394 linhas): três ocorrências, **todas em comentários** (`:70`, `:492`, `:493`). `git log --since=2026-07-30` traz só `a2321503` (p4), que não toca esses handlers | Emitir aviso interno em `:607`, `:519`/`:524` e `:561`. **Não existe canal interno pronto para plugar:** `NotificacaoOrcamento` (`models.py:7438`) é específica de estouro por `ObraServicoCusto`, e `NotificacaoCliente` (`models.py:3061`) está na própria lista de estruturas mortas (E02) | P | ⚖️ Qual canal: evento novo pela allowlist do n8n (dark até A25) ou notificação in-app nova, que exige modelo/tabela — não há genérico hoje |
| **A24** Ligar o pipeline de encargos patronais | **ABERTO** | `services/folha_service.py:1378-1444` está **completo** e sem chamador: grep do nome no repo (fora de `archive/`) devolve 4 hits — a definição `:1378`, dois logs internos `:1423`/`:1436` e `PLANO-NUCLEO.md:524`. `git log --since=2026-07-30` no arquivo: vazio. A aritmética dos ~28% confere: FGTS 8% (`:46`) + INSS patronal `Decimal('0.20')` (`:981`). `grep encargo` em `services/rdo_custos.py`, `ponto_service.py`, `utils.py`: zero | Um chamador (rota, CLI ou job) e a ponte do resultado para o custo da obra — hoje `FolhaProcessada` nasceria e nada leria encargos. **Recorte adicional que entra junto:** `services/folha_service.py:1142` e `:1171` gravam `encargos_inss_patronal = total × Decimal('0.7')`, ou seja 28% × 0.7 = **19,6%** em vez dos 20% de `:981`; somado ao FGTS gravado à parte, a `FolhaProcessada` persiste **27,6%**, não 28% — perda silenciosa no exato campo que a decisão pretende ratear | M | ⚖️ Decisão 6 (`PLANO-NUCLEO.md:542`): critério de rateio por obra. Funcionário em várias obras no mês precisa de regra antes de qualquer código |
| **A25** Ativar o canal externo: `N8N_WEBHOOK_URL` + cron D-3 | **ABERTO** | No-op sem persistir confirmado: `utils/webhook_dispatcher.py:228-231` faz `return False` **antes** de `_persist_pending` (`:239`), a única linha que cria `WebhookEntrega` — sem a variável, nem linha de auditoria. `get_webhook_url` em `:97-100`; `reentregar_pendentes`/`reentregar_uma` abortam por `is_enabled()` (`:110-112`). O comando D-3 existe e está registrado (`notificacoes_cli.py:130-138`, janela em `:32-34`, `app.py:990-992`), mas o APScheduler registra **um único** job (`app.py:1039-1044`, `cobertura_ociosa_mensalistas`) | (1) `N8N_WEBHOOK_URL` (e opcionalmente `N8N_WEBHOOK_SECRET`, `:103-107`) no ambiente de produção — sem isso o canal inteiro segue morto, inclusive o que A23 precisaria. (2) Um `add_job` ao lado de `app.py:1039-1044` (ou cron externo). **Nota que reduz o esforço original:** o APScheduler já roda no processo (`app.py:1006-1046`), não há agendador a construir | P | 🔑 Decisão 7 (`PLANO-NUCLEO.md:543`): infra. O n8n precisa estar no ar e a URL provisionada. Código não resolve — é provisionamento + segredo |

---

## 4. As 12 estruturas mortas

Duas deixaram de estar mortas (E03 e E11) e estão tratadas em prosa na §2 —
não repita a leitura pela tabela.

| Estrutura | Veredito | Evidência (`arquivo:linha`) | O que sobra | Esforço |
|---|---|---|---|---|
| **E01** Handler `nota_fiscal_paga` órfão | **ABERTO** (morta) | `handlers/financeiro_handlers.py:15-16` registrado; `app.py:428` importa no boot com auto-registro. Grep no repo: só o próprio arquivo (`:15,16,36,40,48,111,115`) — zero `emit`. O único ponto de emissão dinâmica (`utils/catalogo_eventos.py:114`) só serve os 7 eventos `dominio.acao` | Remover `handle_nota_fiscal_paga` (`:15-115`) ou criar o emissor no pagamento de NF. Nenhum dos dez pacotes tocou o arquivo | P |
| **E02** `NotificacaoCliente` | **ABERTO** (morta) | `models.py:3061` declarada e carregada (`app.py:405`). Zero instanciação viva (só `archive/legacy_cleanup/passo_9/cliente_portal_utils.py:362`); nenhum template a referencia | Correção ao enunciado: os usos vivos são **três**, e um é UPDATE, não DELETE — `crud_rdo_completo.py:530`, `views/rdo.py:565` e `services/importacao_fisico_financeiro.py:368-369` (anula `rdo_id` porque o RDO é recriado em seguida). Aposentar = migração destrutiva + limpar os três pontos | M |
| **E03** `ObraSignatarioCliente.email` | **MUDOU_DE_FORMA** — **não está morta** | Leitor visível: `templates/obras/_signatarios_cliente.html:74`, incluído por `templates/obra_form.html:550`, alimentado por `views/obras.py:1137-1141`. Escrita em `views/obras.py:4025`; campo em `:133`/`:181` do parcial; coluna em `models.py:1631` | **Nada a aposentar.** E o leitor é de `1fbc97c0` (**29/07**), dois dias antes do documento — ver §2. Do enunciado só sobrevive: o e-mail não é usado para **envio** (não há SMTP, E12) nem entra em payload de webhook | n/a |
| **E04** `AlocacaoEquipe` + FK `rdo_gerado_id` | **ABERTO** (morta) | `models.py:2090` declarada; `:2129` mantém a FK. O p7 (`d5294ce4`) só marcou "EM APOSENTADORIA" no docstring (`:2091-2113`) e repontou o antigo leitor (`almoxarifado_utils.py:417-433` resolve por `Usuario.funcionario_id`). Zero instanciações em produção | Os leitores/escritores vivos que travam a remoção são **três, não dois** — e o inventário do próprio docstring (`:2105-2109`) omite o principal: `views/rdo.py:561-563` (UPDATE na rota viva de exclusão de RDO), `crud_rdo_completo.py:539` (segunda rota de exclusão, blueprint em `main.py:24-25`) e `services/importacao_fisico_financeiro.py:372-373`. Mais a migração destrutiva | M — **bloqueio:** conferência em base de **produção** antes do DROP (dev mediu 33 linhas com `rdo_gerado_id` vazio; ninguém provou o mesmo em produção) |
| **E05** `Lead.proposta_id` / `Lead.obra_id` | **ABERTO** *(era PARCIAL — derrubado, ver §5)* | `handlers/propostas_handlers.py:275` grava `lead.obra_id`, mas dentro do loop de `:263`, que filtra `Lead.query.filter_by(proposta_id=...)`. **Nada grava `proposta_id`**: `grep -rn "\.proposta_id\s*=" --include=*.py` só acha `propostas_consolidated.py:2821` (outro modelo); os dois construtores `Lead(` vivos não passam o kwarg (`crm_views.py:566-570`, `:1462-1476`); o salvar-lead não o toca (`:576-604`); sem `setattr` genérico nem UPDATE cru | O escritor de `obra_id` é **código morto** — o filtro nunca casa, então **nenhuma** das duas FKs recebe escrita em runtime. Falta: (a) escritor real de `Lead.proposta_id` (consumir o `?lead_id=` que `crm_views.py:934-936` já manda, ou select em `crm_views.py:576-604` + `templates/crm/lead_form.html`); (b) mover as chamadas para antes do `return` de `handlers/propostas_handlers.py:385`, senão obra por importação nunca fecha lead; (c) trocar o assert textual de `tests/test_p5_aprovacao_semeia_obra.py:219` por teste que emita o evento. O teste passa verde porque semeia `proposta_id` à mão (`:168-169`) | P |
| **E06** `FolhaPagamento.adiantamentos` | **ABERTO** (morta) | Coluna viva em `models.py:2818`; único escritor em `archive/legacy_cleanup/passo_9/folha_pagamento_utils.py:510`. Grep em `services/`, `views/`, `templates/`: nenhum uso da **coluna** — os hits são do modelo `Adiantamento` (entidade diferente) e do backref homônimo `models.py:2903`. O escritor vivo de folha (`folha_pagamento_views.py:176-189`) não a passa | DROP COLUMN em `folha_pagamento`. **Atenção ao renomear:** o backref `Funcionario.adiantamentos` (`models.py:2903`) tem o mesmo nome e é usado de verdade | P |
| **E07** Pipeline de encargos patronais (= A24) | **ABERTO** (morta) | `services/folha_service.py:1378` sem chamador algum (grep: definição + dois logs). `folha_pagamento_views.py:16` importa só `processar_folha_funcionario`; `views/obras.py:1908` só `obter_dados_folha_obra` | Recorte exato do que está morto: `salvar_folha_processada` (`:1105`) tem **um** chamador — `:1415`, dentro da própria função órfã. É ela quem grava `encargos_inss_patronal` (`:1142`, `:1171`) e o vínculo `obra_id`. `calcular_encargos_patronais` (`:966`) até roda (chamada em `:1044`) e devolve o valor em `:1092` — mas a única rota viva que consome o dict, `folha_pagamento_views.py:172-189`, **descarta** `encargos_patronais` e `obra_id`. O número é calculado a cada folha e jogado fora | M — **bloqueio:** decisão 6 (rateio por obra) |
| **E08** Evento `material_saida` | **ABERTO** (morta) | Handler write-nothing intacto: `event_manager.py:87-125` só consulta e faz `logger.info` (`:122`), sem `add`/`commit`. Emissor com zero fixo intacto: `views/almoxarifado/movimentos.py:891-899` (`'movimento_id': 0`) — como `0` é falsy, o handler cai em `event_manager.py:105-107` e retorna | O p7/`d5294ce4` **não** mudou nada aqui: tocou `almoxarifado_utils.py` e `models.py`, e a função que arrumou (`almoxarifado_utils.py:405`) opera em outro par de tabelas (`MovimentacaoEstoque`/`Produto`) e não emite `material_saida` — são dois estoques paralelos. **Defeito adicional:** o segundo emissor, `views/almoxarifado/movimentos.py:600`, usa `movimento.id if movimento else 0`, e `movimento` é a variável do loop de lotes (`:580`) — carrega o id do **último lote**, não o da saída. Inofensivo hoje só porque o handler não escreve | P |
| **E09** CPF/CNPJ da proposta (= A22) | **ABERTO** (morta) | `propostas_consolidated.py:559` é a **única** ocorrência de `cliente_documento` no arquivo; o objeto é montado em `:647-660` sem documento. `models.py:3562-3576` não tem a coluna (a `cliente_cpf_cnpj` de `models.py:2388` é de `ContaReceber`) | O formulário coleta o dado (`templates/propostas/nova_proposta.html:94`, `templates/propostas/proposta_form.html:42-44` com máscara em `:400`) e **dois templates tentam exibi-lo de volta** (`detalhes_proposta.html:159-160`, `editar.html:97`) lendo `proposta.cliente_cpf_cnpj`, atributo inexistente — o Jinja resolve como Undefined e o bloco nunca aparece: o usuário digita e o dado some **sem erro visível**. Falta coluna + persistência em `:647`. É o A22 | P |
| **E10** Tabela `CronogramaCliente` | **ABERTO** (morta) | `models.py:6988` declarada e carregada; importada em `views/obras.py:4`. O portal não a lê. A rota de edição segue de pé e **grava**: `views/obras.py:3200-3251` (`:3215`, `:3222`, `:3231`, `:3239`, commit em `:3243`) | Dois refinamentos do enunciado: (1) **nada cria linhas** — grep por `CronogramaCliente(` devolve só a declaração; a geração migrou para `TarefaCronograma(is_cliente=True)` (`views/obras.py:3141-3150`); (2) a mesma geração **apaga** a tabela legada a cada execução (`:3133-3139`). Somando: a rota só encontraria linhas anteriores à migração que nunca passaram por regeneração — e é **POST órfão** (grep de `editar_cronograma_cliente` em `templates/`: vazio). Aposentar = remover `:3200-3251`, o delete de `:3134-3139`, o import de `views/obras.py:4` e DROP TABLE | P |
| **E11** `subatividade_mestre_id` como ponte | **MUDOU_DE_FORMA** — **não está morta** | O p8 (`ecf7f3a9`) entregou o leitor: `services/progresso_subatividade.py:39` e `:66`; consumidor real em `services/medicao_service.py:279-284`, que substituiu o `MAX(...)` antigo. Os dois trilhos seguem escritos: `cronograma_views.py:747`, `:974`, `:3443`, `:3520`, `:3675` × `views/rdo.py:2033`, `:4015`, `rdo_editar_sistema.py:296`/`:322`, `crud_rdo_completo.py:366` | Não é aposentadoria, é o oposto — mas a leitura é mais estreita que o commit sugere: o único consumidor está no **ramo de fallback** (`services/medicao_service.py:277`), e a dualidade de **escrita** que o próprio módulo declara (`:24-31`) é o resto do p8 = **A18** | n/a |
| **E12** SMTP + agendador de relatórios | **ABERTO** (morta, e mente) | Blueprint registrado no boot (`main.py:157-158`, `exportacao_relatorios.py:46`). SMTP: `:530-591`, com `MAIL_SERVER` default `'localhost'` (`:534`) e `smtplib.SMTP` em `:578` — `grep MAIL_SERVER\|MAIL_USERNAME` em `app.py`/`main.py`: **nada**. Painel 500: `:599-604` renderiza `relatorios/exportacao/painel.html` e o diretório **não existe**. Agenda em memória: `:759-763`, preenchida em `:778-783` | Pior que "dict de memória": `:823` instancia `SistemaAgendamentoRelatorios()` **novo a cada request**, então `jobs_agendados` nasce vazio, recebe um job e é coletado no fim da requisição — e **nenhuma linha do repo jamais lê** `jobs_agendados`. Ou seja, `:812-840` responde `{'success': True, 'job_id': ...}` para um agendamento que não existe: **mente para o usuário**. Decidir entre remover as três peças ou implementá-las | M — **bloqueio:** infra, mesma família da decisão 7 (o caminho escolhido para notificação é o n8n) |

---

## 5. O que o cético derrubou

Três vereditos foram revistos. Nenhum foi revisto "para melhor" — nos três casos
a revisão **aumentou** o trabalho pendente, e em dois deles o primeiro revisor
havia se apoiado em código que existe mas não executa.

### A10 — de **ENTREGUE** para **MUDOU_DE_FORMA**

O primeiro revisor mostrou que a guarda de idempotência existe
(`event_manager.py:524-530`) e sustentou, com argumento estrutural correto
(handler único de `ponto_registrado`, nenhum criador paralelo de `CustoObra` de
ponto), que o defeito antigo morreu. Tudo isso se sustenta.

**A razão da derrubada:** a chave da guarda é (funcionário, data, obra, admin,
categoria) e **não amarra em `registro_ponto.id`**, e não há unique em
`RegistroPonto(funcionario_id, data)` (`models.py:800-804` tem três índices
não-únicos). Enquanto isso, `views/admin.py:98-176` (`POST /novo_ponto`, usado
por `templates/funcionario_perfil.html:2204`) cria `RegistroPonto`
**incondicionalmente** em `:150` — ao contrário de `ponto_service.py:105-109`,
que reusa o registro do dia. Dois lançamentos manuais no mesmo dia/obra: o
segundo cai no ramo de UPDATE (`:532`) e **sobrescreve** o custo do primeiro.
Antes eram duas linhas somando 8h; agora é uma linha de 4h.

O problema descrito (dupla contagem) morreu e nasceu **perda de custo** na mesma
superfície — que é a definição de MUDOU_DE_FORMA. `tests/test_p1_fallback_e_idempotencia.py:119-135`
não pega, porque sempre reusa o mesmo `RegistroPonto` e emite o evento à mão.

*Ressalva de confiança, na letra do cético:* alta nos fatos de código, **média**
sobre a frequência do cenário em produção — ninguém contou quantos pares
(funcionário, data) têm mais de um `RegistroPonto` na mesma obra. Se for ~0, o
defeito novo é latente, não ativo. Isso não muda o veredito; muda a prioridade.

### A16 — rótulo **PARCIAL** mantido, **recorte derrubado**

O rótulo sobreviveu, mas o recorte estava materialmente errado, e é o recorte que
faz alguém riscar meio item.

O primeiro revisor deu o defeito 2 (batida destruída) como corrigido em todos os
caminhos. **Não está.** A guarda do p7 é
`tem_batida_real = bool(hora_entrada or hora_saida)` (`models.py:4580-4582`), e
registro de **ausência classificada não tem nenhuma das duas**:
`ponto_service.py:330-360` cria `RegistroPonto(tipo_registro='falta'/'atestado')`
sem hora. Esse registro cai no ramo "vazio" e o plano o sobrescreve inteiro —
`:4602` (obra), `:4604-4605` (horários do turno), `:4614` (`tipo_registro` volta a
`'trabalho_normal'`) e `:4616` (`horas_trabalhadas` = 8.0 por `:4660-4664`).
**O atestado lançado à mão vira dia trabalhado de 8h, em silêncio**, alcançável
pelo cron (`models.py:4772-4774`) e pela rota `POST /equipe/api/sync-ponto`
(`equipe_views.py:1212-1236`).

E a consequência do defeito 3 é pior que "o dia entra sem custo": o ponto nascido
do plano **suprime ativamente** o custo que o RDO geraria —
`services/rdo_custos.py:368-373` pula o lançamento justificando "já tem ponto,
o custo virá pelo handler", handler que nunca roda porque nada emite. Não é
"entra sem custo", é "**perde** o custo que teria".

Também caiu a frase "todos os outros pontos de criação emitem":
`ponto_views.py:2369` e `ponto_service.py:344` não emitem, e dois dos que emitem
(`ponto_views.py:1514`, `views/api.py:419`) só o fazem para `tipo_remuneracao == 'diaria'`.

### E05 — de **PARCIAL** para **ABERTO**

O primeiro revisor deu "metade entregue" porque `Lead.obra_id` ganhou escritor
real em `handlers/propostas_handlers.py:275`. O escritor existe **como texto** e
não é alcançável: está no corpo do loop de `:263`, que filtra
`Lead.query.filter_by(proposta_id=...)`, e **nada no código de produção grava
`proposta_id`** — `grep -rn "\.proposta_id\s*=" --include=*.py` só devolve
`propostas_consolidated.py:2821`, que é de outro modelo; os dois construtores
`Lead(` vivos não passam o kwarg; o salvar-lead não o toca; não há `setattr`
genérico nem UPDATE cru. A lista devolvida em `:263` é sempre vazia, e `:275`
nunca executa.

Se o único escritor de `obra_id` só roda atrás de um filtro que nunca casa, não
houve metade entregue: houve **zero escrita das duas FKs**. O item "FKs sem
escrita" continua vivo por inteiro.

O cético ainda achou um furo que o primeiro veredito não viu: a chamada falta num
**terceiro** caminho do handler — `:378-384` dá `return` sem semear nem fechar,
e é exatamente por ali que passa a importação físico-financeira
(`services/importacao_fisico_financeiro.py:572-578`, `skip_contabil=True`) e toda
proposta de valor zero.

### Onde o cético **não** derrubou — e isso é sinal, não omissão

Nos outros sete itens em que houve segunda passada (A05, A11, A13, A14, A15,
A18, A19) o cético **confirmou o rótulo** e ainda assim acrescentou achado novo
em todos os sete: a regressão de custo do p1 (A05), quatro buracos de dedup não
listados (A11), o rateio por peso de venda em `services/resumo_custos_obra.py:192-198`
e a tela que não fecha (A13), o falso verde de `tests/test_p5_...:167-172` (A14),
a terceira fórmula do p4 (A15), o N+1 e o gate estreito da derivação (A18), e o
sexto gerador de medição (A19).

**A leitura disso:** nenhum rótulo de PARCIAL/ABERTO foi otimista demais, mas
**todo recorte de "o que sobra" estava incompleto**. O padrão é consistente —
quem confere sozinho acerta o veredito e subestima a sobra. Vale como método para
a próxima rodada: a segunda passada não é sobre o rótulo, é sobre o recorte.

---

## 6. A lista de trabalho real

**Esta lista substitui a §5 do `PLANO-NUCLEO.md`.** São os 13 itens vivos que
alguém pode começar **hoje**, sem esperar decisão nem credencial. Ordem: esforço
crescente; dentro do mesmo esforço, o que destrava outro item primeiro.

| Ordem | # | Esforço | Por que está aqui / o que faz primeiro |
|---|---|---|---|
| 1 | **A05** | P | **É a regressão de custo, não uma automação pendente.** Mensalista e horista pararam de gerar `GestaoCustoFilho` por `POST /rdo/finalizar/<id>` e `POST /rdo/editar/<id>` (`event_manager.py:730-733`), e os três payloads sem `obra_id` matam o recálculo de medição. Começa por `'obra_id': rdo.obra_id` nos três `emit` e pela decisão sobre `lancar_custos_rdo` × chamada direta |
| 2 | **A10** | P | Perda de custo simétrica à de A05, pelo lado do ponto: `views/admin.py:150` cria registro incondicional e o segundo lançamento do dia sobrescreve o primeiro. Mesma família, mesma sessão de trabalho |
| 3 | **A16** | P *(era M)* | Atestado virando 8h trabalhadas (`models.py:4602-4616`) é perda de dado do usuário. A parte de **emitir evento** está travada por decisão (ver §7); a parte de **estender a guarda para ausência classificada** não está e vale sozinha |
| 4 | **A07** | P | **Destrava A14 e metade de A22.** Três linhas em três arquivos (`propostas_consolidated.py:1188`, `:510-540`, `views/obras.py:294`), e nenhuma funciona sem as outras duas |
| 5 | **A09** | P | Dedup de NF; leva de carona o vazamento cross-tenant de `almoxarifado_utils.py:257` (`xml_hash` sem `admin_id`), que é bug de tenant, a mesma classe que o p1 existiu para fechar |
| 6 | **A06** | P | Seis chamadas, um padrão já pronto (`services/cronograma_versao_service.py:432-457`). Cuidado único: pós-commit, porque `utils/cronograma_engine.py:1177` commita por dentro |
| 7 | **A03** | P | Uma atribuição em `services/medicao_service.py:369-383`. Enquanto não sair, todo recebimento de medição fica fora da partida dobrada — e o gate de `financeiro_service.py:332` nem loga |
| 8 | **A02** | P | Copiar `financeiro_views.py:402-420` para dentro de `receber_conta`. A leitura já existe (`financeiro_service.py:686-696`) e está sem alimentação |
| 9 | **A22** | P | Select de cliente + `proposta.cliente_id`. A parte do CPF/CNPJ precisa da escolha entre `Cliente.cnpj` e coluna nova — mas não bloqueia o select |
| 10 | **A01** | P | Confirm consumir as transferências. Escopo bem cercado: o payload e o template já existem |
| 11 | **A14** | M | Mover as chamadas para antes do `return` de `handlers/propostas_handlers.py:385` é pequeno e independente. A ponta do lead **só surte efeito depois de A07** — por isso vem depois dele |
| 12 | **A17** | M | Pré-carregar a equipe do dia no RDO. Dependência do p1 satisfeita (`services/rdo_custos.py:25-53`), mas ganha muito se A05/A10 já tiverem estabilizado o custo |
| 13 | **A20** | M *(era P)* | Subiu de P porque `MapaFornecedor` não tem FK para `Fornecedor` (`models.py:6887-6904`): exige coluna + migração + tela de amarração, ou casamento por nome (frágil) |
| 14 | **A21** | M | FK de frota. Os kwargs quebrados (`crud_rdo_completo.py:428-449`) são **código morto sem rota** — não trate como incidente de produção |

Fora da lista numerada, do lado das estruturas mortas, três aposentadorias são
baratas e independentes: **E01** (P, remover handler órfão), **E06** (P, DROP
COLUMN — cuidado com o backref homônimo `models.py:2903`) e **E10** (P, remover
rota órfã + DROP TABLE). **E05** (P) entra junto de A07/A14, porque é o mesmo
buraco visto do outro lado.

---

## 7. Itens travados por decisão ou credencial

Ninguém consegue começar estes hoje. Estão separados justamente para não
poluírem a lista acima — mas quase todos têm **uma fatia livre**, anotada, que
pode andar sem a decisão.

| # | Trava | Quem decide | Fatia que anda sem a decisão |
|---|---|---|---|
| **A04** | Decisão 5 (`PLANO-NUCLEO.md:541`): conta de débito da despesa geral | Contador | Nenhuma. O código é uma entrada de dicionário; o que falta é a conta |
| **A08** | ⚖️ Rateio por centro de custo × agregado por obra; e o restaurante que vem só como texto (`PLANO-NUCLEO.md:489`) | Negócio | A versão **agregada por obra** já é implementável: `registrar_custo_automatico` no savepoint de `services/importacao_excel.py:889` |
| **A11** | Qual mecanismo de custo é canônico (diária × `componente_folha` rateado) | Negócio | A chave cruzada em `services/rdo_custos.py:422`/`:463` e a falta de `obra_id` na chave larga (`event_manager.py:826-840`) são bugs independentes da escolha |
| **A12** | Estornar lançamento emitido × lançar contrapartida; pai já **pago** não pode sumir | Contador + negócio | Nenhuma segura. Estorno parcial duplica de outro jeito |
| **A13** | Decisão 3 de 03/08 adiou a origem ("consertar no consumo") | Cássio (reverter ou manter) | Os consumidores residuais: `utils/notifications.py:40-49`, `views/catalogo_views.py:675-676`, `models.py:7198-7200`, `services/resumo_custos_obra.py:192-198` e `templates/obras/planejamento_custos/lista.html:95`/`:98` |
| **A15** | Decisão 4 (`:540`) + dualidade de fonte do p8 | Negócio | Nenhuma segura — mexer no percentual do portal mexe em `valor_medido` |
| **A16** | Ponto **semeado** pelo plano deve gerar custo? | Negócio | Sim, e grande: a guarda contra sobrescrita de ausência classificada. Por isso A16 aparece **nas duas** seções |
| **A18** | Decisão 4 (`:335`): recalcular ou congelar `MedicaoObra` históricas | Negócio | `views/rdo.py:3190-3200` gravar `subatividade_mestre_id` (o elo, não a convergência) e o `admin_id` faltante em `views/obras.py:744-756` |
| **A19** | Convergência das **fontes** reescopada para p8/A18 | Negócio | A família V1 inteira: consolidar `views/rdo.py:1332`, `:2524-2536`, `services/rdo_pdf_service.py:196-205`, `crud_rdo_completo.py:132-135` e `views/obras.py:742-756` em `_progresso_fallback_subatividades`. **Não depende de decisão nenhuma** |
| **A23** | Qual canal: n8n (dark até A25) × notificação in-app nova | Produto | Nenhuma. Não existe canal interno genérico para plugar hoje |
| **A24** / **E07** | Decisão 6 (`:542`): rateio dos encargos patronais por obra | Contador + negócio | A correção do `× 0.7` em `services/folha_service.py:1142`/`:1171` (27,6% gravados contra 28% calculados) — é bug aritmético, não rateio |
| **A25** | 🔑 Decisão 7 (`:543`): **credencial e infra**. `N8N_WEBHOOK_URL` provisionada e n8n no ar | Infra | O `add_job` do lembrete D-3 ao lado de `app.py:1039-1044` — o APScheduler já roda; só o webhook depende do segredo |
| **E04** | Conferência em base de **produção** antes do DROP | Ops | Limpar os três pontos vivos (`views/rdo.py:561-563`, `crud_rdo_completo.py:539`, `services/importacao_fisico_financeiro.py:372-373`) e corrigir o inventário do docstring `models.py:2105-2109` |
| **E12** | Infra, mesma família da decisão 7: SMTP × aposentar o módulo | Produto + infra | Nenhuma. Mas note que `exportacao_relatorios.py:812-840` responde `success: True` para agendamento inexistente — se a decisão demorar, **desligue a rota** |

---

## 8. Notas de confiança

Todos os 37 vereditos foram fechados com **confiança alta**, exceto:

* **A19** — confiança **média-alta**. Alta nas quatro omissões verificadas linha a
  linha (o sexto gerador de medição, a contradição do portal, o gate do dashboard
  e os testes textuais); **média** em afirmar que não existe um sétimo caminho de
  cálculo de progresso, porque o app não foi executado — só lido.
* **A10** — confiança alta nos fatos de código; **média** sobre a frequência do
  cenário novo em produção, pelo motivo já registrado na §5.
* **A15** — o revisor fechou em média; a segunda passada **subiu para alta** ao
  encontrar a divergência de fórmula entre `progresso_ponderado_armazenado` e
  `calcular_percentual_item`. Fica registrado que a confiança mudou, e por quê.

Nenhum item ficou em confiança **baixa**. Duas checagens não foram feitas por
restrição de escopo (esta reconferência é read-only) e são as únicas lacunas
conhecidas: nenhuma suíte de teste foi **executada**, e nenhuma consulta foi
feita à **base de produção** — o que afeta especificamente a prioridade de A10
(quantos dias têm mais de um `RegistroPonto`) e a viabilidade de E04 (quantas
linhas de `alocacao_equipe` existem lá).

---

## 9. Como este documento se relaciona com os outros

| Documento | Relação |
|---|---|
| `PLANO-NUCLEO.md` §5 (backlog de 25) | **Substituída pela §6 deste documento.** Nenhum item foi entregue; os esforços de A16, A18 e A20 mudaram |
| `PLANO-NUCLEO.md` §6 (estruturas mortas) | **Corrigida pela §2 e §4.** Duas das 12 não estão mortas, e uma delas nunca esteve |
| `PLANO-NUCLEO.md` §7 (decisões) | Inalterada. As decisões 4, 5, 6 e 7 seguem travando os itens da §7 deste documento |
| `docs/superpowers/plans/2026-07-21-fase-6-*` | Sem impacto: a §"Revisão de premissas — 03/08" já incorporou o p9 e o p3 |
| `docs/superpowers/specs/2026-08-03-p1-*` | O p1 declarou não tratar A09 (`:181`) — confirmado. Mas a **regressão de custo** da §1 não está registrada em nenhuma spec |
