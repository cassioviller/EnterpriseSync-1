# Reconferência do backlog de automações — 2026-09-02

> Reconfere, item a item e contra a árvore de HOJE (`main` em `331f3cfc`), os
> **11 itens de automação que o registro de 01/09 dá como abertos ou parciais**:
> **A01, A08, A17, A20, A21, A23** (abertos) e **A11, A13, A15, A16, A22**
> (parciais). Substitui, para esses 11, o veredito de
> `docs/reconferencia-backlog-2026-08-23.md`.
>
> **Método.** Toda afirmação tem `arquivo:linha` ou commit. `📖` = li no
> arquivo; `🔬` = medi (grep/git com o comando registrado); `🔴` = grave;
> `⚠️` = armadilha. O que não deu para verificar entra como **não verificado**,
> com o motivo — nunca como suposição.
>
> ⚠️ **Nota de método herdada e reconfirmada:** `git log --since=<data>` omite
> commits silenciosamente neste repositório (histórico não estritamente
> cronológico pós-rebase). Todas as varreduras de histórico aqui usaram
> `git log --date=short --pretty='%h %ad %s' -- <arquivo> | awk '$2 >= "2026-08-23"'`.
>
> ⚠️ **Restrição desta sessão:** proibido rodar `pytest`/`run_tests.sh` (um
> Postgres e uma porta compartilhados com outros agentes). Portanto **nenhum
> veredito aqui se apoia em execução de teste**. Onde digo "existe teste", digo
> que o arquivo existe e nomeia o símbolo — não que ele passou hoje.

---

## A regra que este documento aplica

🔬 **"Código existe" não é ENTREGUE.** O **A09** foi dado como ENTREGUE em
23/08 por leitura de código, sem teste que nomeasse a regra, e a varredura de
25/08 achou um furo de tenant no mesmo dedup — fechado só em 01/09 pela
migration 317 (`0840cd93`, "chave de acesso da NF é única por tenant, não
global"). Onze dias de "entregue" sobre um furo aberto.

Por isso, aqui: **item sem teste que o nomeie não é ENTREGUE.** Ou é
`PARCIAL`, ou é **"código existe, sem prova"**.

---

## A manchete

Dos 11 reconferidos: **zero mudaram de veredito**, mas **três mudaram de
recorte** e **quatro** carregam achado novo que o registro de 23/08 não tinha.
O trabalho de 24/08 a 02/09 foi todo em outras frentes (ondas 2-6, Fase 6,
portal, tenant) — **nenhuma das 11 automações recebeu braço dedicado nos 10
dias**, e isso está medido, não presumido.

| Veredito hoje | Itens |
|---|---|
| 🔴 **ABERTO** (6) | A01, A08, A17, A20, A21, A23 |
| 🟡 **PARCIAL** (5) | A11, A13, A15, A16, A22 |
| ✅ **ENTREGUE** (0) | — |

**As divergências entre registro e árvore** (o achado que esta varredura
existe para produzir) estão em **A16**, **A21**, **A13** e **A22** — cada uma
detalhada na sua seção e resumida no fim.

---

## O placar

| Item | 23/08 → hoje | Uma linha |
|---|---|---|
| A01 | ABERTO → **ABERTO** (inalterado) | 🔬 Zero commits em `importacao_views.py` e `services/importacao_excel.py` desde 23/08; o `confirm` ainda manda 3 chaves |
| A08 | ABERTO → **ABERTO** (inalterado) | 🔬 Zero commits; `ImportacaoAlimentacao.importar` segue sem uma linha de custo |
| A11 | PARCIAL → **PARCIAL** (inalterado) | Ramo horista segue sem guarda cruzada contra `categoria='RDO'` |
| A13 | PARCIAL → **PARCIAL** (recorte **maior** que o registrado) | 🔴 A origem tem **três** escritores, não dois — o terceiro é um listener |
| A15 | PARCIAL → **PARCIAL** (inalterado) | Duas semânticas na mesma tabela, sem teste que nomeie a dualidade |
| A16 | PARCIAL → **PARCIAL** (recorte **menor** — divergência) | 🔬 `ed17ab7f` (27/08) fechou um dos sítios; restam três |
| A17 | ABERTO → **ABERTO** (inalterado) — **destravado** | 🔬 A trava era "depois de B1"; B1 fechou. Só falta braço |
| A20 | ABERTO → **ABERTO** (inalterado) — **custo caiu** | O elo requisição→mapa já existe; falta mapa→`Fornecedor` |
| A21 | ABERTO → **ABERTO** (divergência de mensagem de commit) | 🔴 `ce331094` promete consertar kwargs; conserta outros, não os três |
| A22 | PARCIAL → **PARCIAL** (inalterado, achado novo) | 🔬 O evento `proposta_aprovada` já reserva o campo e manda `None` sempre |
| A23 | ABERTO → **ABERTO** (inalterado) | 🔬 `notific`/`EventManager`/`.emit(` = **0 ocorrências** no arquivo inteiro |

---

# Detalhamento por item

## A01 — Confirm da importação lê as transferências do extrato

**Veredito 23/08:** ABERTO → **hoje: ABERTO, inalterado.**

**🔬 O que mudou (git):**
```
git log --date=short --pretty='%h %ad %s' -- importacao_views.py | awk '$2 >= "2026-08-23"'
git log --date=short --pretty='%h %ad %s' -- services/importacao_excel.py | awk '$2 >= "2026-08-23"'
```
Ambos **vazios**. Zero commits nos dois arquivos em 10 dias.

**📖 Evidência atual:**
- `importacao_views.py:773` — `def fluxo_caixa_confirmar()`; a função vai até
  `:979` (a próxima rota abre em `:980`).
- `importacao_views.py:942-947` — a única chamada ao service dentro dela:
  ```python
  resultado = svc.importar({
      'entradas': entradas,
      'saidas': todas_saidas,
      'batch_id': batch_id,
  }, admin_id)
  ```
  🔬 As **mesmas três chaves** de 23/08. `transferencias` não entra.
- 🔬 `grep -n "transf" importacao_views.py` devolve **5 acertos, todos no lado
  do preview**: `:453` (`resultado.get('transferencias', [])`), `:473`, `:515`,
  `:550`, `:701`. Nenhum dentro de `773-979`. O dado é detectado, exibido e
  **descartado no confirm**.
- `services/importacao_excel.py:1840` monta a lista, `:1964` a preenche e
  `:2122` a devolve no payload de preview — mas o `importar()` da
  `ImportacaoFluxoCaixa` (`:1789`) não a aceita.

**🔬 Existe teste guardando?** **Não.** `grep -rl "transferencias" tests/
--include=*.py` devolve só `tests/test_endpoint_classificar_termo.py`, que é
sobre classificação de termo do extrato — não sobre o confirm. **Nenhum teste
afirma que a transferência sobrevive ao confirm, nem que ela se perde.**

**Tamanho real:** **conserto, cabe numa task.** Três sítios exatos: ler o
payload + os campos `transf_origem_<i>`/`transf_destino_<i>` do form em
`importacao_views.py:773-979`, validar as duas contas contra o tenant, e fazer
`ImportacaoFluxoCaixa.importar` aceitar a quarta chave.

**⚠️ Armadilha:** a validação de banco **contra o tenant** é o ponto onde este
item vira risco. Uma transferência aceita com conta de outro admin move
dinheiro entre empresas. O teste tem de afirmar a recusa, não só o caminho
feliz.

---

## A08 — Importação de alimentação gerar custo

**Veredito 23/08:** ABERTO → **hoje: ABERTO, inalterado.**

**🔬 O que mudou (git):** zero commits em `services/importacao_excel.py` desde
23/08 (mesma varredura do A01).

**📖 Evidência atual:**
- `services/importacao_excel.py:807` — `class ImportacaoAlimentacao`.
- `services/importacao_excel.py:883-919` — `importar()`. Li o corpo inteiro:
  cria `AlimentacaoLancamento` (`:892-899`), faz `flush()`, e um `INSERT` cru
  em `alimentacao_funcionarios_assoc` (`:904-907`). **Nenhuma chamada a
  `registrar_custo_automatico`, nenhum `CustoObra`.**
- 🔬 `grep -n "registrar_custo_automatico\|CustoObra" services/importacao_excel.py`
  devolve `:656, :747, :768, :781` (dentro de `ImportacaoDiarias`, que abre em
  `:409`) e `:1019, :1025` (dentro de `ImportacaoTransporte`, que abre em
  `:925`). **Nenhum entre `:807` e `:924`** — a janela da alimentação.
- `services/importacao_excel.py:2549` — `MODULO_MAP` segue mapeando
  `'alimentacao': ImportacaoAlimentacao`, consumido por `get_importador`
  (`:2554`). O módulo está vivo e importa; só não gera custo.

**🔬 Existe teste guardando?** **Não.** `grep -rl "ImportacaoAlimentacao"
tests/ --include=*.py` = **vazio**. O único acerto em `tests/` para
`alimentacao_funcionarios_assoc` é `tests/test_e2e_metricas_funcionario.py`,
que semeia a M2M para outra finalidade.

**Tamanho real:** **não é conserto — é decisão + funcionalidade.** O plano
consolidado registra a trava em `docs/superpowers/plans/2026-08-04-plano-consolidado.md:4767`:
"A08 espera a regra de rateio (`PLANO-NUCLEO.md:489`)". O item tem duas metades:
a mecânica (chamar `registrar_custo_automatico(tipo_categoria='ALIMENTACAO')`
dentro do savepoint) e a que não é código — **`restaurante` é texto livre sem
`entidade_id`, sem `centro_custo_id`, sem `obra_servico_custo_id`**, e a regra
de rateio (por centro de custo × agregado por obra) segue sem resposta.

**Escrever o código antes da regra produziria custo lançado no lugar errado**,
que é pior que custo não lançado — o não lançado é visível como buraco, o
errado se esconde dentro de um número plausível.

---

## A11 — Guarda cruzada RDO × ponto no ramo horista

**Veredito 23/08:** PARCIAL, "falta só a guarda cruzada RDO×ponto no ramo
horista" → **hoje: PARCIAL, inalterado.**

**🔬 O que mudou (git):** `event_manager.py` recebeu **2 commits** desde 23/08
— `da8a0c88` (24/08, "valor de contrato só muda por aditivo") e `0d92c3b3`
(24/08, "medição de contrato presa à versão do baseline"). 📖 Os dois são da
Fase 6 (contrato); nenhum toca os ramos de ponto.

**📖 Evidência atual — a parte entregue segue de pé:**
- `event_manager.py:1005` — `_ORIGENS_RDO_FOLHA = ('rdo_custo_diario', 'rdo_mao_obra')`,
  usada em `:1029` e `:1043` (bloqueio cruzado + reconciliação entre irmãs).
- `event_manager.py:356-372` — o ramo **diarista** tem a guarda inversa larga:
  `GestaoCustoFilho.origem_tabela.in_(['rdo_mao_obra', 'rdo_custo_diario'])`.

**📖 Evidência atual — a parte que falta:**
- `event_manager.py:494-578` — o ramo **horista**. Li o bloco inteiro. A única
  consulta de idempotência é `:523-533`:
  ```python
  custo = (CustoObra.query
      .filter_by(funcionario_id=..., data=..., admin_id=...,
                 categoria='PONTO_ELETRONICO')
      .order_by(CustoObra.id).first())
  ```
  🔬 Ela olha **só dentro da própria categoria**. Não há nenhuma leitura de
  `CustoObra` com `categoria='RDO'`.
- 🔬 `grep -n "categoria='RDO'" event_manager.py` devolve **um único acerto**,
  `:960` — e é uma **escrita**, no lado RDO. **Zero leituras cruzadas a partir
  do lado ponto/horista**, exatamente como em 23/08.

**🔬 Existe teste guardando?** **Não para o que falta.** `grep -rn
"rdo_custo_diario" tests/*.py` devolve `tests/test_auto_link_servico_rdo.py:246`
e `tests/test_custo_diario.py:394,431,441` — todos afirmam a chave do lado RDO,
nenhum afirma a guarda do lado horista. 🔬 O `xfail(strict=True)` mais próximo
(`tests/test_p1_dedup_cross_origem.py:98`) está **rotulado A16 2ª metade
(D6)**, não A11 — e a reconferência de 23/08 já o registrava assim.

**Tamanho real:** **conserto, cabe numa task.** É a mesma forma da guarda que
já existe no ramo diarista (`:356-372`), aplicada ao ramo horista sobre
`CustoObra` em vez de `GestaoCustoFilho`.

**⚠️ Armadilha, e é a mesma que derrubou seis andaimes nesta linhagem de
planos:** um teste que exercite o horista **tem de provar RED** — o ramo
horista só é alcançado com perfil de remuneração horista semeado, e o helper
`um_tenant()` do arreio parametriza isso (`tests/helpers_tenant.py`). Um teste
escrito com o perfil errado passa verde sem tocar o ramo.

---

## A13 — Orçado deixa de herdar venda (a **origem**)

**Veredito 23/08:** PARCIAL, "os 5 consumidores residuais corrigidos; falta a
origem (decisão adiada) + edge de 3,2%" → **hoje: PARCIAL, e o recorte da
origem é MAIOR que o registrado.**

**🔴 DIVERGÊNCIA — a origem tem três escritores, não dois.**

O documento de 23/08 nomeia dois: `medicao_views.py:314` e
`views/catalogo_views.py:902`. 🔬 A varredura de hoje
(`grep -rn "valor_orcado *= *.*valor_comercial" --include=*.py .`, excluindo
`archive/`) devolve **quatro** acertos, e o terceiro é o mais importante:

| Sítio | O que é | Estado |
|---|---|---|
| `medicao_views.py:316` | `par.valor_orcado = item.valor_comercial` (drift de `:314`) | 📖 vivo |
| `views/catalogo_views.py:905` | `par.valor_orcado = it.valor_comercial` (drift de `:902`) | 📖 vivo |
| **`models.py:8424`** | `valor_orcado = target.valor_comercial or 0` — 🔴 **dentro de um listener `after_insert` de `ItemMedicaoComercial`**, que faz o `INSERT` do `ObraServicoCusto` pareado (`:8426-8432`) | 📖 vivo, **não nomeado em 23/08** |
| `handlers/propostas_handlers.py:58` | docstring que **documenta a regra como desenho**: "(valor_orcado = valor_comercial; servico_catalogo_id = servico_id)" | 📖 é a prova de intenção |

**Por que isto muda o tamanho do item.** Os dois sítios de 23/08 são rotas —
alguém tem de clicar. O terceiro é um **listener**: dispara sozinho, a cada
aprovação de proposta, pelo caminho `_propagar_proposta_para_obra`
(`handlers/propostas_handlers.py:55`). 📖 Corrigir só as duas rotas deixaria a
origem principal intacta e produziria a pior forma de conserto — o número
melhora nas telas e continua nascendo errado no banco.

**📖 O edge case de 3,2% segue vivo, e está numa linha só:**
`services/custo_orcado.py:137` —
```python
resultado[s.id] = linhas if linhas > 0 else _f(s.valor_orcado)
```
📖 O docstring de `:125-131` declara a regra como **decisão consciente**
("linha vence agregado... o irmão sem linhas usa o agregado dele"). Não é
descuido: é fallback deliberado que herda venda quando não há linha de custo.

**🔬 Não verificado:** o número de hoje dos 2.459/76.004 `ObraServicoCusto`
(3,2%) medido em 23/08. Verificar exigiria consulta ao banco compartilhado, que
esta sessão está proibida de tocar. **O 3,2% é o número de 23/08, não o de hoje.**

**🔬 Existe teste guardando?** **Só o consumo, nunca a origem.**
- `tests/test_a13_orcado_de_custo_no_consumo.py` — 📖 li o cabeçalho: afirma o
  estado do **banco depois de um GET** em `/obras/<id>/planejamento-custos/`
  (`NotificacaoOrcamento` gravada ou não). É um teste de comportamento forte, e
  o docstring explica a asserção que protege contra a correção ingênua.
- `tests/test_p3_p9_orcado_e_contrato.py` — chama `custo_orcado_da_obra` e
  `custo_orcado_por_servico` direto.
- 🔬 **Nenhum dos dois afirma nada sobre `models.py:8424`, `medicao_views.py:316`
  ou `views/catalogo_views.py:905`.** A origem não tem guarda.

**Tamanho real:** **plano próprio, não task.** Três escritores + um listener +
backfill das obras já gravadas + a Decisão 3 de 03/08 ("consertar no consumo"),
que foi **adiada, não revertida**. Mudar a origem sem backfill cria duas
populações no banco — as gravadas antes e depois — e nenhum consumidor sabe
distinguir.

---

## A15 — Medição do portal paralela ao trilho ponderado

**Veredito 23/08:** PARCIAL, inalterado → **hoje: PARCIAL, inalterado.**

**🔬 O que mudou (git):** `portal_obras_views.py` recebeu 4 commits desde 23/08
(`63857dfb`, `31889d24`, `42c17ddb`, `b581da0d`) — 📖 vazamento na vitrine,
administração do portal, e as duas tasks da onda "o que não persiste" (trilha
de erro). `services/medicao_service.py` recebeu 1 (`6befc615`, 24/08,
"SUPRIMIDO sobrevive à medição"). 📖 **Nenhum toca a dualidade.**

**📖 Evidência atual — os dois escritores da mesma tabela:**
- 🔬 `grep -rn "MedicaoObra(" --include=*.py .` (fora de `archive/` e `tests/`)
  devolve exatamente **dois**: `portal_obras_views.py:942` e
  `services/medicao_service.py:140`.
- `portal_obras_views.py:887` — `def gerar_medicao(obra_id)`. O corpo:
  - `:935` — `perc = progresso_ponderado_armazenado(obra_id, admin_id, responsavel='empresa')`
  - `:939-940` — `valor_medido = round(float(obra.valor_contrato) * perc / 100, 2)`
    → 🔴 **acumulado**
  - `:942-956` — `MedicaoObra(...)` + `db.session.add` + `commit`.
    📖 **Sem `MedicaoObraItem`. Sem `recalcular_medicao_obra`. Sem escrever
    `ItemMedicaoComercial.percentual_executado_acumulado`.**
- `services/medicao_service.py:198` — `medicao.valor_medido = total_medido_periodo.quantize(...)`
  → 🔴 **valor do período**.
- As duas fórmulas de origem seguem divergentes por construção:
  `services/medicao_service.py:48` (`calcular_percentual_item`) e
  `utils/cronograma_engine.py:1222` (`progresso_ponderado_armazenado`).

**🔬 Existe teste guardando?** **Existem dois testes que tocam a rota, e
nenhum guarda a dualidade.**
- `tests/test_escopo_cronograma_interno.py` — 📖 o cabeçalho é explícito: guarda
  o **escopo** do percentual (cópia-cliente e tarefa arquivada não contam).
  Ele prova que o `perc` de `:935` é calculado sobre a população certa — e
  **nada** sobre o que acontece com ele depois.
- `tests/test_porta_irma.py:262` — guarda o `@admin_required` da rota.
- 🔬 **Nenhum teste no repositório afirma que `MedicaoObra.valor_medido`
  significa a mesma coisa nos dois escritores.** É uma dualidade sem guarda.

**Tamanho real:** **plano próprio + decisão.** O plano consolidado registra a
trava em `2026-08-04-plano-consolidado.md` §8.2: "Decisão 4 do `PLANO-NUCLEO.md`
(medições históricas) + a dualidade de fonte do p8/A18". 📖 Mexer no percentual
do portal mexe em `valor_medido`, e `valor_medido` já está gravado em produção
com a semântica acumulada — unificar sem decidir o que fazer com o histórico
reescreve dinheiro passado.

---

## A16 — Evento no sync alocação → ponto

**Veredito 23/08:** PARCIAL, "(a) corrigido; (b) e (c) seguem intactos" →
**hoje: PARCIAL, mas o recorte ENCOLHEU de novo. 🔴 DIVERGÊNCIA com o registro.**

**🔴 O registro de 01/09 lista A16 como PARCIAL sem qualificar, e a árvore
mostra que um dos sítios do defeito (c) foi fechado em 27/08 — por um commit
que não menciona A16.**

**🔬 A medição:**
```
git log --date=short --pretty='%h %ad %s' -S"identificar-e-registrar): {ev_err}" -- ponto_views.py
→ ed17ab7f 2026-08-27 fix(ponto): o ponto facial vira hora, e o totem passa a emitir o evento
```
📖 `ponto_views.py:2540-2553` hoje:
```python
# Emitir evento após commit — esta era a única rota de ponto que
# nunca emitia: ponto batido no totem da obra não virava custo de
# diarista nenhum (`event_manager`, handler de `ponto_registrado`).
if tipo_ponto_canonico:
    EventManager.emit('ponto_registrado', {...}, admin_id=admin_id)
```
🔬 `grep -c "EventManager.emit('ponto_registrado'" ponto_views.py` = **3** hoje;
o mesmo comando contra `2e40f8b0` (a base do documento de 23/08) = **2**.
**Um sítio a mais, medido, não lembrado.**

**📖 O que continua aberto — três sítios, verificados um a um:**

| Defeito | Sítio | 🔬 Medição de hoje |
|---|---|---|
| (b) | `models.py:4791` — `AlocacaoEquipe.sincronizar_com_ponto` | `grep -n "EventManager\|\.emit(" models.py` → **zero ocorrências no arquivo inteiro** |
| (c) | `equipe_views.py:1201` — `POST /equipe/api/sync-ponto` | `grep -n "emit\|EventManager" equipe_views.py` → **zero** |
| (c) | `ponto_service.py:324` — `registrar_falta` | 📖 o corpo até `:361` termina em `db.session.commit()` sem emit; o único emit do arquivo é `:144-150`, em `bater_ponto_obra` |

**🔬 Existe teste guardando?** **Sim, e este item é o melhor exemplo da casa.**
- A metade (a) entregue tem `tests/test_a16_fato_humano.py` — 📖 unidade sobre
  `registro_ponto_tem_fato_humano`, fail-closed, com docstring que explica por
  que a lista branca é fechada; e `tests/test_arreio_presenca_rotas.py`, que
  exercita a rota de verdade.
- A metade que **falta** tem **dois `xfail(strict=True)` que a nomeiam**:
  - `tests/test_p1_dedup_cross_origem.py:98` — `reason='A16 2ª metade (D6) — ponto sem custo ...'`
  - `tests/test_arreio_presenca_rotas.py:391` — `reason='A16 — o ponto nascido do plano não ...'`
  🔬 `strict=True` significa que **o dia em que alguém corrigir e esquecer de
  tirar a marca, o gate falha por XPASS**. Este é o único dos 11 itens cuja
  lacuna tem guarda ativa.

**Tamanho real:** **conserto — uma task por sítio, três no total.** Mas 📖 o
plano consolidado (§8.2) registra a trava: "**D6** (§10). E, mesmo respondida,
tem de vir depois de B1.9-B1.11: emitir do ramo de preenchimento antes da
guarda existir seria emitir custo por cima de um atestado." 🔬 B1.9-B1.11 estão
entregues (é a metade (a), com teste). **A dependência técnica caiu; sobra a D6.**

---

## A17 — Pré-carregar a mão de obra do RDO da presença do dia

**Veredito 23/08:** ABERTO, inalterado → **hoje: ABERTO, inalterado — mas
DESTRAVADO.**

**🔬 O que mudou (git):** `views/rdo.py` recebeu **11 commits** desde 23/08
(`95eb585f`, `77e4ab00`, `2d94cae3`, `297ac8fe`, `d585a399`, `02882e5d`,
`ce331094`, `ed85d117`, `938cc92d`, `d8ebbd61`, `9f169c0d`). 📖 São todos de
tenant, estorno de custo, guarda de duplicata e `subatividade_mestre_id`.
**Nenhum sobre pré-carga de presença.**

**📖 Evidência atual:**
- `views/rdo.py:609` — `def novo_rdo()`.
- `views/rdo.py:617` — `funcionarios = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).order_by(Funcionario.nome).all()`
  📖 **Sem recorte de dia. Sem recorte de obra.** O tenant inteiro, igual a 04/08
  e a 23/08.
- 🔬 `grep -n "RegistroPonto" views/rdo.py crud_rdo_completo.py rdo_editar_sistema.py`
  → **zero ocorrências nos três arquivos**, idêntico às duas reconferências
  anteriores.

**🔬 Existe teste guardando?** **Não.** `grep -rl "novo_rdo" tests/ --include=*.py`
devolve `test_cronograma_duplicado_rdo.py`, `test_b5_rdo_crud_url_map.py` e
`test_browser_all_modules.py` — url_map, duplicata e navegação. Nenhum afirma
nada sobre quem entra na lista de funcionários.

**Tamanho real:** **funcionalidade nova pequena — cabe numa task, e a trava
caiu.** 📖 `2026-08-04-plano-consolidado.md:4761` registrava a trava: "Toca
exatamente a superfície que A05, A10 e A16 estão consertando... Pré-carregar
sobre um custo instável multiplicaria o defeito. **Depois de B1 estabilizado e
com o arreio de B0 verde nas rotas de RDO e ponto**." 🔬 B1 está entregue (A05,
A10 ✅ em 23/08; A11 e A16 com o núcleo fechado), e o arreio de B0 existe
(`tests/test_arreio_custo_rdo_rotas.py`, `tests/test_arreio_presenca_rotas.py`).
**A condição escrita para destravar o A17 está cumprida.**

**⚠️ Achado incidental, fora do recorte do A17 mas na mesma função:**
`views/rdo.py:627` —
```python
ultimo_rdo = RDO.query.filter_by(obra_id=obra_id).order_by(RDO.data_relatorio.desc()).first()
```
📖 **sem `admin_id`**. Um `obra_id` de outro tenant devolveria o RDO daquele
tenant como fonte das "atividades anteriores". Não é o A17 e não foi medido em
produção — registrado aqui para não se perder, não para entrar nesta onda.

---

## A20 — Pré-preencher o pedido com o vencedor da cotação

**Veredito 23/08:** ABERTO (M), sem mudança → **hoje: ABERTO, inalterado — mas
o custo do item CAIU.**

**🔬 O que mudou (git):** `compras_views.py` recebeu 6 commits desde 23/08
(`1deea57a`, `9c83db7b`, `f2567fcb`, `995efb5c`, `37397333`, `30e32e3a`). 📖
Todos de régua de status, alçadas e do parser de dinheiro. `f2567fcb` ("o pedido
para de ser emitido a 1/1000 do preço") **mexeu no mesmo bloco de preço do A20**
— mas para consertar o parser, não para ler a cotação.

**📖 Evidência atual — o obstáculo estrutural, intacto:**
- `models.py:7780-7797` — `class MapaFornecedor`. Li a classe inteira. O
  fornecedor continua sendo `nome = db.Column(db.String(200), nullable=False)`
  (`:7787`). 📖 **Sem FK para `Fornecedor`.**

**📖 Evidência atual — a rota, intacta:**
- `compras_views.py:2725` — `def requisicao_emitir_pedido(requisicao_id)`.
- `compras_views.py:2774` — `fornecedor_escolhido = _fornecedor_do_form(admin_id)`.
  📖 `_fornecedor_do_form` (`:129-147`) lê `request.form.get('fornecedor_id')` cru
  e resolve contra `Fornecedor` — **nunca olha `requisicao.mapa_v2` nem
  `fornecedor_escolhido_id`**.
- `compras_views.py:2890-2891` — o preço do item:
  ```python
  preco = float(preco_lido if preco_lido is not None else (item.preco_estimado or 0))
  ```
  📖 O fallback é `preco_estimado` da requisição. **`MapaCotacao.valor_unitario`
  não aparece na rota** (🔬 `grep -n "MapaCotacao" compras_views.py` → nenhum
  acerto no bloco `2725-2900`).
- `templates/compras/requisicao_detalhe.html:411-416` — o `<select
  name="fornecedor_id">` segue sem `selected`:
  ```html
  <option value="">Selecione…</option>
  {% for f in fornecedores %}<option value="{{ f.id }}">{{ f.nome }}</option>{% endfor %}
  ```

**🔬 Achado novo — metade do caminho já existe.** `RequisicaoCompra.mapa_v2_id`
é coluna real (`models.py:6223`) com relacionamento (`models.py:6277`), e existe
rota viva que a preenche (`compras_views.py:2351` — `requisicao.mapa_v2_id = mapa.id`).
🔬 `git log -S"mapa_v2_id" -- models.py` → `cb1c3bad` (23/07), anterior a tudo.
📖 **O elo requisição → mapa existe e é usado.** O que falta é o elo
**mapa → `Fornecedor`** e a leitura no momento de emitir.

Isto **muda o julgamento de 04/08**, que cortou o item dizendo "custa coluna +
migração + tela de amarração para poupar um preenchimento"
(`2026-08-04-plano-consolidado.md` §8.1). 📖 A tela de amarração não precisa mais
ser inventada — a requisição já sabe qual mapa é o seu. Resta a coluna
`MapaFornecedor.fornecedor_id` + migração.

**🔬 Existe teste guardando?** **Não para o A20.** `requisicao_emitir_pedido`
aparece em `tests/test_alcadas_avancadas.py` e `tests/test_fase3_matriz_governanca.py`
— os dois exercitam **alçada e governança**, não preenchimento. `MapaFornecedor`
aparece em `tests/test_alcadas_avancadas.py` e `tests/test_fase3_alcada.py`, pelo
mesmo motivo.

**Tamanho real:** **decisão a reabrir + plano pequeno.** Foi **CORTADO** em
04/08 por custo>benefício. O custo mudou; o benefício não. **Quem decide é o
dono do produto, não esta varredura.**

---

## A21 — FK de frota no equipamento do RDO + TypeError de kwargs

**Veredito 23/08:** ABERTO (M), sem mudança → **hoje: ABERTO. 🔴 DIVERGÊNCIA
entre mensagem de commit e árvore.**

**🔴 O achado.** O commit `ce331094` (27/08, "fix(rdo): as rotas mortas voltam,
o dado deixa de se perder, e a duplicata morre") diz na própria mensagem:

> "- salvar_rdo legado (sem rota, reservado ao Modulo 07): usava func nunca
> importado e **kwargs de colunas inexistentes**; passa pelo helper unico de
> numero."

🔬 Conferi o diff (`git show ce331094 -- crud_rdo_completo.py`). O que ele
consertou foram os kwargs do construtor de **`RDO`** (`sequencial_ano=`, `ano=`)
e o `NameError` de `func`. 📖 **Os três kwargs que o A21 nomeia continuam
intactos**, e são de outras duas classes:

| Linha | Kwarg | Classe destino | 📖 A classe tem? |
|---|---|---|---|
| `crud_rdo_completo.py:427` | `horas_utilizacao=` | `RDOEquipamento` | **Não** — `models.py:1451` é `horas_uso` |
| `crud_rdo_completo.py:428` | `observacoes=` | `RDOEquipamento` | **Não** — a classe (`models.py:1443-1452`) tem 7 colunas e nenhuma delas |
| `crud_rdo_completo.py:448` | `descricao_completa=` | `RDOOcorrencia` | **Não** — `models.py:1466` é `descricao_ocorrencia` |

**A mensagem de commit promete mais do que o diff entrega.** Quem lesse só o
log concluiria que o A21(b) fechou. Não fechou.

**📖 Evidência do resto do item:**
- `models.py:1443-1452` — `RDOEquipamento` segue sem FK para `Veiculo`;
  `nome_equipamento = db.Column(db.String(100))` é texto livre.
- 🔬 `grep -rn "veiculo_id" utils/rdo_equip_ocorr.py templates/rdo/novo.html
  templates/rdo/editar_rdo.html` → **zero**.
- 🔬 `utils/rdo_equip_ocorr.py` — zero commits desde 23/08.
- `crud_rdo_completo.py:236-242` — o comentário que documenta a rota removida
  segue lá, e 🔬 a varredura de `@rdo_crud_bp.route` no arquivo confirma:
  `:31`, `:190`, `:224`, `:230`, `:518`, `:565`, `:718`, `:871`, `:919`, `:955`,
  `:983` — **nenhum decorador acima de `def salvar_rdo()` em `:242`**. Segue sem
  rota.
- 📖 Os caminhos **vivos** usam o helper correto: `views/rdo.py:854`, `:2177`,
  `:3504` e `rdo_editar_sistema.py:513` chamam
  `replace_equipamentos_ocorrencias` (`utils/rdo_equip_ocorr.py:127`).

**🔬 Existe teste guardando?** **Só o url_map.**
`tests/test_rota_rdo_salvar_unica.py:19-23` congela que `/rdo/salvar` resolve
para `main.salvar_rdo_flexivel`. 🔬 **Nenhum teste instancia `RDOEquipamento`
ou `RDOOcorrencia` pelo caminho de `crud_rdo_completo.salvar_rdo`** — os três
`TypeError` são latentes e sem guarda.

**Tamanho real: o item tem duas metades de tamanhos opostos.**
- **(b) — os três kwargs:** 🔴 **conserto de três linhas**, em código morto.
  Barato, e o argumento para fazer é que o Módulo 07 vai religar essa rota; o
  argumento para não fazer é que corrigir código morto sem teste é corrigir no
  escuro. **Recomendo apagar a função ou consertá-la com teste — não deixá-la
  meio consertada, que é o estado de hoje.**
- **(a) — FK de frota:** funcionalidade nova (coluna + migration + dois
  templates + parse). 📖 Cortada em 04/08 como "integração **sem dor
  relatada**". 🔬 Nada mudou nisso: continua sem dor relatada.

---

## A22 — Persistir CPF/CNPJ na proposta

**Veredito 23/08:** PARCIAL (metade (a) entregue em 05/08, `1394d907`) →
**hoje: PARCIAL, inalterado, com achado novo.**

**🔬 O que mudou (git):** `propostas_consolidated.py` recebeu 3 commits desde
23/08 (`13750ec3`, `01b070b9`, `a6afcb8e`) — 📖 revisão de proposta, comparador
de versões e o censo de tenant da Onda 6. **Nenhum toca o CPF/CNPJ.**

**📖 Evidência atual — a metade que falta:**
- `models.py:3716` — `class Proposta`. 📖 Li as colunas de cliente:
  `cliente_id` (FK, "Migração 43"), `cliente_nome`, `cliente_telefone`,
  `cliente_email`, `cliente_endereco`. **Não existe `cliente_cpf_cnpj`.**
- 🔬 `grep -n "cliente_cpf_cnpj" models.py` devolve `:2543` e `:2579` — e os dois
  são de **`ContaReceber`** (`:2579` é `db.Index('idx_conta_receber_cliente', 'cliente_cpf_cnpj')`).
  ⚠️ **Armadilha para quem for consertar:** a coluna existe no repositório, com
  esse nome exato, em outra tabela. Um `grep` apressado conclui que a coluna já
  existe.
- `propostas_consolidated.py:599` — `cliente_documento = request.form.get('cliente_cpf_cnpj', ...)`.
  🔬 `grep -n "cliente_documento" propostas_consolidated.py` devolve **essa e
  só essa linha**: a variável é lida e **nunca usada**. Variável morta, igual a
  23/08.
- `templates/propostas/editar.html:97` e
  `templates/propostas/detalhes_proposta.html:159-160` — 📖 seguem lendo
  `proposta.cliente_cpf_cnpj`, atributo que não existe. Jinja resolve como
  Undefined e o campo nunca aparece, em silêncio.
- 🔬 `grep -n "cnpj\|documento" services/cliente_resolver.py` → **zero**. O dedup
  de cliente segue só por e-mail/nome.

**🔬 Achado novo — o evento já reserva o campo e manda `None` sempre.**
`propostas_consolidated.py:1145-1152` (e os gêmeos em `:2511` e `:2693`):
```python
EventManager.emit('proposta_aprovada', {
    'proposta_id': proposta.id,
    'cliente_nome': proposta.cliente_nome,
    'cliente_cpf_cnpj': None,          # ← sempre None, nos três sítios
    ...
})
```
📖 O contrato do evento **já tem a chave**. Quem consome recebe `None` por
construção, em todos os caminhos de aprovação. Isso é bom para o conserto (o
consumidor não muda de forma) e é ruim como está (o campo parece existir).

**🔬 Existe teste guardando?** **Não.** `cliente_cpf_cnpj` aparece em
`tests/test_propagacao_proposta_obra.py:191` e
`tests/test_ciclo_proposta_obra_medido_cr.py:91` — 📖 nos dois casos como
**valor de payload enviado** (`'cliente_cpf_cnpj': ''` e `: None`), nunca como
asserção. Nenhum teste afirma que o documento persiste, nem que se perde.

**Tamanho real:** **conserto, cabe numa task.** A rota mais barata já está
aberta: `proposta.cliente_id` está gravado desde 05/08, e `Cliente.cnpj` existe
— 🔬 em **`models.py:3507`**, dentro de `class Cliente` (`:3501`). ⚠️ **A
reconferência de 23/08 cita `models.py:3354` para essa coluna, e `:3354` é uma
coluna `id`.** Citação errada herdada; conferida e corrigida aqui. Basta ler
pela FK nos dois templates e
preencher os três payloads de evento — **sem coluna nova e sem migration**.

---

## A23 — Aviso interno de comprovante e decisão de compra do portal

**Veredito 23/08:** ABERTO (P), sem mudança → **hoje: ABERTO, inalterado.**

**🔬 O que mudou (git):** `portal_obras_views.py` recebeu 4 commits desde 23/08
(os mesmos do A15). 📖 Nenhum acrescenta canal de aviso.

**📖 Evidência atual — as três rotas:**
- `portal_obras_views.py:577` — `def aprovar_compra(token, compra_id)`
- `portal_obras_views.py:685` — `def recusar_compra(token, compra_id)`
- `portal_obras_views.py:723` — `def upload_comprovante(token, compra_id)`
  📖 Li o corpo do último: termina em `logger.info(...)` (`:767`) + `flash(...)`
  (`:768`) + `redirect`. Nada mais.

**🔬 A medição mais limpa deste documento:**
```
grep -c "notific" portal_obras_views.py       → 0
grep -c "EventManager" portal_obras_views.py  → 0
grep -c "\.emit(" portal_obras_views.py       → 0
```
**Zero ocorrências de qualquer uma das três, no arquivo inteiro.** Em 23/08
havia dois comentários não relacionados; hoje nem isso. O arquivo não tem
sequer o vocabulário de notificação.

**🔬 Existe teste guardando?** **Não para o A23.** As rotas são exercitadas por
`tests/test_o_que_nao_persiste.py` (trilha de auditoria — foi o que a onda "o
que não persiste" acrescentou em 31/08), `tests/test_onda2_portal_nao_vaza.py`
(tenant) e `tests/test_onda5_recusado_nao_grava.py`. 📖 Nenhum afirma nada
sobre aviso interno.

**Tamanho real: NÃO é braço, é decisão.** 📖 O plano consolidado cortou o item
em 04/08 com a razão escrita (`2026-08-04-plano-consolidado.md` §8.1):

> "**Não existe canal interno para plugar.** `NotificacaoOrcamento`
> (`models.py:7438`) é específica de estouro por `ObraServicoCusto`, e
> `NotificacaoCliente` (`models.py:3061`) está na própria lista de mortas (E02).
> Construir um canal é **feature**, não automação — e a decisão de qual canal
> (Decisão 7 do `PLANO-NUCLEO.md`) **nem foi tomada**."

🔬 Reconferi a premissa: continua verdadeira. **A23 está bloqueado pela mesma
decisão que bloqueia o A25 (`N8N_WEBHOOK_URL`) — é a mesma Decisão 7.** Os dois
são o mesmo problema visto de dois lados: não há para onde mandar o aviso.

---

# Tabela-resumo

| Item | 23/08 | **Hoje** | Evidência âncora | 🔬 Teste que guarda a lacuna? | Tamanho real |
|---|---|---|---|---|---|
| **A01** | ABERTO | 🔴 **ABERTO** | `importacao_views.py:942-947` — 3 chaves | **Não** | Conserto — 1 task |
| **A08** | ABERTO | 🔴 **ABERTO** | `services/importacao_excel.py:883-919` sem custo | **Não** | Decisão (rateio) + funcionalidade |
| **A11** | PARCIAL | 🟡 **PARCIAL** | `event_manager.py:523-533` só `PONTO_ELETRONICO`; `:960` é a única `categoria='RDO'`, e é escrita | **Não** | Conserto — 1 task |
| **A13** | PARCIAL | 🟡 **PARCIAL** (recorte **maior**) | `models.py:8424` (listener), `medicao_views.py:316`, `views/catalogo_views.py:905`; fallback em `services/custo_orcado.py:137` | Só o consumo (`test_a13_...`), **não a origem** | Plano próprio + Decisão 3 + backfill |
| **A15** | PARCIAL | 🟡 **PARCIAL** | `portal_obras_views.py:940` (acumulado) × `services/medicao_service.py:198` (período) | **Não** para a dualidade | Plano próprio + Decisão 4 |
| **A16** | PARCIAL | 🟡 **PARCIAL** (recorte **menor**) | Restam `models.py:4791`, `equipe_views.py:1201`, `ponto_service.py:324` | **SIM** — 2 `xfail(strict=True)` | Conserto — 3 tasks; trava = D6 |
| **A17** | ABERTO | 🔴 **ABERTO** (**destravado**) | `views/rdo.py:617` sem recorte; zero `RegistroPonto` nos 3 arquivos | **Não** | Funcionalidade pequena — 1 task |
| **A20** | ABERTO | 🔴 **ABERTO** (**custo caiu**) | `models.py:7787` sem FK; `compras_views.py:2891` usa `preco_estimado`; **mas** `models.py:6223` já liga requisição→mapa | **Não** | Decisão a reabrir + plano pequeno |
| **A21** | ABERTO | 🔴 **ABERTO** (**divergência**) | `crud_rdo_completo.py:427,428,448` vs `models.py:1443-1452` e `:1466` | **Não** (só url_map) | (b) 3 linhas; (a) funcionalidade |
| **A22** | PARCIAL | 🟡 **PARCIAL** | `models.py:3716` sem coluna; `propostas_consolidated.py:599` variável morta; `:1150/:2511/:2693` mandam `None` | **Não** | Conserto — 1 task, sem migration |
| **A23** | ABERTO | 🔴 **ABERTO** | `grep -c` de `notific`/`EventManager`/`.emit(` = **0/0/0** | **Não** | **Decisão 7** — não é braço |

---

## As divergências entre registro e árvore

Este é o produto principal da varredura. Cinco:

1. 🔴 **A16 encolheu e ninguém registrou.** `ed17ab7f` (27/08) fechou o sítio
   do totem (`ponto_views.py:2540-2553`) sem mencionar A16 na mensagem.
   Medido: 2 emits em `2e40f8b0`, 3 hoje. O registro de 01/09 diz "PARCIAL" —
   correto no rótulo, desatualizado no recorte.

2. 🔴 **A21: a mensagem de commit promete o que o diff não entrega.**
   `ce331094` diz ter consertado "kwargs de colunas inexistentes" em
   `salvar_rdo`; consertou os do construtor de `RDO`, não os três de
   `RDOEquipamento`/`RDOOcorrencia` que o A21 nomeia. **Quem confiar no log
   conclui que fechou.**

3. 🔴 **A13: a origem tem três escritores, não dois.** `models.py:8424` é um
   listener `after_insert` que grava venda em `valor_orcado` a cada aprovação
   de proposta — não estava nomeado em 23/08. Corrigir só as duas rotas
   deixaria a origem principal viva.

4. 🟡 **A22: citação errada herdada.** A reconferência de 23/08 aponta
   `models.py:3354` como `Cliente.cnpj`; 🔬 `:3354` é uma coluna `id`. A coluna
   está em **`models.py:3507`**. Pequeno, mas é exatamente a classe de erro que
   o ledger da casa já teve de corrigir num fix round (citação errada repetida
   em três lugares, `onp/Task 3`) — e o custo é quem for consertar o A22 abrir
   o arquivo na linha errada.

5. 🟡 **A20: o julgamento de corte de 04/08 usou uma premissa que envelheceu.**
   `RequisicaoCompra.mapa_v2_id` existe desde 23/07 e tem rota que a preenche
   (`compras_views.py:2351`) — o elo requisição→mapa não precisa mais ser
   construído. O corte merece ser reavaliado pelo dono, não revertido por
   esta varredura.

---

## Divergência de escopo entre o plano mestre e este documento

⚠️ A Task 14 de `docs/superpowers/plans/2026-08-31-fecho-do-que-esta-aberto.md`
enumera **~13 itens**, incluindo **A18, A24 e A25**. O recorte desta
reconferência é de **11** — A18, A24 e A25 ficaram de fora porque **mudaram de
estado em 01/09** (`9f169c0d`, `9aead796`, e o runbook
`docs/operacao-agendamentos.md`) e o registro de 01/09 já os move para outra
faixa (RATIFICAR / credencial). **Não foram medidos aqui.** Quem escrever o
plano das famílias precisa decidir se eles voltam — e a decisão é sobre
ratificação humana, não sobre código.

---

## Resíduos desta varredura

- 📌 **O banner de substituição no topo de
  `docs/reconferencia-backlog-2026-08-23.md` NÃO foi escrito.** O Step 2 da
  Task 14 pede; o escopo desta sessão eram dois documentos novos. Fica para
  quem executar o commit da Task 14.
- 📌 **`views/rdo.py:627`** — `RDO.query.filter_by(obra_id=obra_id)` sem
  `admin_id`, dentro de `novo_rdo`. Achado incidental, não medido em produção,
  fora do recorte do A17.
- 📌 **O 3,2% do A13** (2.459/76.004 `ObraServicoCusto` sem linha de custo) é o
  número de **23/08**. Remedir exige consulta ao banco compartilhado, proibida
  nesta sessão.
