# Planos em aberto — varredura de 2026-08-23

> **O que é:** a resposta, conferida no código e no git, à pergunta "quais planos
> ainda estão abertos". Cobre os **99 arquivos** de `docs/superpowers/plans/`, os
> **31** de `docs/superpowers/specs/`, as branches do `origin` e as listas que o
> `ESTADO-ATUAL.md` deixou em aberto.
>
> **Contra o quê:** `main` em **`6407775f`** (21/08), árvore limpa exceto
> `scripts/limpar_tenants_teste_dev.py`, que é ferramenta de dev e por decisão do
> Cássio (23/08) **não vai ser versionada**.
>
> **O que este documento NÃO é:** não é plano, não é spec, não muda código.
> Continua valendo a regra da casa: nada aqui vira mudança sem spec própria.

Marcas de procedência iguais às do `ESTADO-ATUAL.md`: 🔬 medido · 📖 lido no
código (`arquivo:linha`) · 🧮 deduzido de outro documento.

## Por que a contagem óbvia mente

Contar `- [ ]` nos planos não responde a pergunta. 🔬 `2026-07-21-fase-1-identidade-papeis.md`
tem **72 de 72 caixas abertas** e a fase está ✅ fechada desde 21/07 com 11/11 tasks —
ninguém voltou para marcar. O mesmo vale para as Fases 2, 3, 4 e 5 e para os dez
módulos do cronograma MPP. Quem carrega a verdade é o `ESTADO-ATUAL.md`, o código
e o git; a caixa de seleção é rascunho de execução, não registro de estado.

Por isso cada item abaixo foi julgado por **existência de código na árvore**, não
por mensagem de commit nem por checkbox.

---

## 1. 🔴 O achado que muda o mapa — a linhagem partida, e o PR #6

🔬 **A história do `main` começa em 2026-07-22.** São **476 commits**, o primeiro
`b30923b5` ("ci: restaura workflows browser-noturno e gate", 22/07 03:01). As
branches de junho em `origin/*` vivem numa linhagem **disjunta** de **4.369
commits**:

```
git rev-list --count main                                  # 476
git rev-list --count origin/fix/fase-0-estancar            # 4369
git rev-list --count origin/fix/fase-0-estancar..main      # 476  ← nada em comum
```

O repositório foi recomeçado. A árvore trouxe o código acumulado, então o
trabalho que já estava mesclado sobreviveu — mas **o que estava só em branch
naquele dia ficou do outro lado da fratura**, e nenhum `git log` do `main`
consegue vê-lo.

### 🔴 A Espinha Financeira (Fatias 1–5) não está no `main`

`ESTADO_design_espinha_financeira.md` está na árvore, se apresenta como *"ponto de
entrada único para retomar"* e afirma: *"as 5 fatias estão implementadas, testadas
e no PR"* (PR #6, branch `design/espinha-financeira-obra`, 15/06, ~40 testes).

🔬 conferido arquivo por arquivo — **nenhum existe na árvore**:

| O que o documento promete | Estado |
|---|---|
| `services/resultado_atividade_service.py` (read-model: valor agregado, custo MO, EVM, portfólio) | ❌ ausente |
| `services/importar_obra_completa.py` (Proposta→Obra→IMC→Cronograma) | ❌ ausente |
| `services/caixa_obra_service.py` | ❌ ausente |
| `services/aprendizado_produtividade.py` | ❌ ausente |
| `resultado_views.py` + `templates/resultado/*` (4 telas) | ❌ ausente |
| `scripts/{criar_orcamento_baia_rev10,seed_templates_baia_rev10,importar_baia_easypanel}.py` | ❌ ausentes |
| os ~40 testes (`test_resultado_atividade_service.py`, `test_caixa_obra.py`, …) | ❌ ausentes |

🔬 `grep -rn "resultado_atividade\|resultado/portfolio\|por_atividade"` na árvore
inteira: **zero ocorrências**. As migrations 193/194/195 que o documento cita
também são da linhagem velha.

**Parte foi refeita por outro caminho** — `services/evm.py`, `medicao_service.py` e
`progresso_subatividade.py` vieram dos pacotes p4/p10, e o EVM está entregue
(`e86ab635` + `3612db6b`). Mas *resultado por atividade* como serviço e tela, o
importador de obra por planilha e a lente de caixa **não têm equivalente**.

**Decisão humana, e é a mais cara desta varredura:** resgatar do PR #6 ou riscar o
`ESTADO_design_espinha_financeira.md`, que hoje mente para quem retomar por ele.

> 🔬 **23/08, corrigido no mesmo dia: o resgate NUNCA dependeu do `gh`.** A leitura
> do repositório é **anônima** — `git fetch origin design/espinha-financeira-obra`
> devolve `EXIT=0` sem credencial e o ref local `a18f86e7` bate com o remoto. A
> varredura tratou "abrir o PR pela API" e "ler o código da branch" como a mesma
> coisa; não são. O `gh` deslogado bloqueia só metadado (abrir issue, ler
> comentário de PR). **O código das cinco fatias está a um `git checkout` daqui** —
> o que o resgate custa é portar contra o schema de hoje, que mudou nas Fases 0.6
> a 5, não obter o código.

### 🔬 23/08 — o custo do resgate, medido

Com o código a um `git checkout`, o porte deixou de ser chute. Os cinco módulos e
os sete arquivos de teste (**2.542 linhas**) foram extraídos e conferidos contra o
`main` de hoje.

**O que porta de graça:**

- 🔬 **os cinco módulos importam limpo** sob o app de hoje (`resultado_atividade_service`,
  `caixa_obra_service`, `aprendizado_produtividade`, `importar_obra_completa`,
  `resultado_views`) — nenhum `ImportError`, nenhuma classe de modelo sumida;
- 🔬 **16 classes de `models` referenciadas, todas existem**;
- 🔬 a cadeia que sustenta o read-model está inteira: `ItemMedicaoCronogramaTarefa.peso`,
  `PropostaItem.composicao_snapshot`, `RDOCustoDiario.custo_total_dia` e
  `RDOMaoObra.tarefa_cronograma_id` — as quatro presentes;
- 🔬 `caixa_obra_service.py` (27 linhas) porta **sem tocar em nada**: chama
  `FinanceiroService.calcular_fluxo_caixa(admin_id, data_inicio, data_fim, obra_id=None)`
  e `agregar_fluxo_mensal(detalhes, saldo_inicial=0.0)`, e as duas assinaturas
  batem exatamente com as de hoje.

**O que não existe e teria de ser recriado** — as migrations 193/194/195 são da
linhagem velha e nunca chegaram aqui (🔬 a maior migration de hoje é a **314**,
então elas entrariam como **315+**):

| Coluna que falta | Era a migration | Quem depende |
|---|---|---|
| `cronograma_template_item.peso_medicao` | 193 | 📖 `importar_obra_completa.py:214` — é o **coração** do importador (peso explícito, DC8/ADR 0004) |
| `propostas_comerciais.origem` | 194 | 📖 `importar_obra_completa.py:68` (`origem='importacao_obra'`, ADR 0005). Hoje existe `proposta_origem_id`, que é **outra coisa** |
| `rdo_subempreitada_apontamento.verba` / `lucro` / `pai` | 195 | A Fatia 2 (DC9). 🔬 a tabela já tem `tarefa_cronograma_id`; faltam os três de verba/lucro/pai |

**Leitura honesta do resultado.** A auditoria de atributos (`Classe.atributo`) não
pega acesso por instância (`ti.peso_medicao`), então "nenhum atributo ausente" era
mais fraco do que parecia — foi a conferência coluna a coluna acima que achou os
três buracos. O porte é, então:

1. **`caixa_obra_service` + `aprendizado_produtividade`** (90 linhas): entram como estão;
2. **`resultado_atividade_service`** (537 linhas): entra inteiro **menos** o ramo de
   subempreitada da Fatia 2, que espera as colunas de verba/lucro;
3. **`importar_obra_completa`** (291 linhas) + **`resultado_views`** (174) + 4 templates:
   exigem **duas migrations novas** (peso_medicao, origem) e o registro do blueprint;
4. os **sete arquivos de teste** (1.450 linhas) só rodam depois de 1-3, e não foram
   executados nesta medição — o banco de dev estava em limpeza.

**Não há incompatibilidade estrutural** com as Fases 0.6-5: 🔬 nenhum uso do padrão
antigo de PK do plano de contas (`PlanoContas.query.get(codigo)`), e o read-model lê
`RDOCustoDiario`, que o ciclo de vida do RDO só passa a alimentar fora do rascunho —
mudança de semântica, não de contrato.

### As outras 15 branches do `origin` não escondem entrega

🔬 varridas uma a uma: o que falta delas na árvore são templates mortos que a
limpeza apagou (`templates/obras.html`, `rdo/novo_backup.html`,
`debug_funcionario.html`) e o `handlers/financeiro_handlers.py`, comum a todas.
As de agosto (`feat/cronograma-pdf`, `feat/recebimento-atesto`, `test/b0-arreio`)
estão **mescladas** (`ahead=0`). Só a espinha tem entrega distinta pendurada.

> ✅ **23/08, no mesmo dia: o Cássio subiu `main` manualmente.** 🔬
> `git ls-remote origin main` → **`975cb2a1`**, igual ao local. Os 63 commits que
> estavam só nesta máquina e no `gitsafe-backup` estão no GitHub. Do item humano
> nº 2 sobra apenas a API (`gh auth status` segue deslogado): abrir as 8 issues de
> `docs/superpowers/issues/` e ler comentário de PR.

---

## 2. Parados por decisão humana — os únicos com dono nomeado

| Plano | O que falta | Quem destrava |
|---|---|---|
| `2026-08-20-rollup-percentual-cronograma.md` | Task 3 de 3 (📖 `:351` "BLOQUEADA") | **Paulo**: média ponderada por duração (o que o código faz hoje) ou média simples por item (os ~80% que ele descreveu). Muda curva S, EVM, medição e físico-financeiro em cascata. Tasks 1 e 2 valem nas duas hipóteses e já estão em `main` |
| `2026-08-20-manual-padrao-preenchimento-rdo.md` | Steps 1–4 (4 caixas abertas de 11) | **Alan e Abel** lerem o capítulo 23a antes de ele virar cobrança. Sem essa rodada o capítulo é opinião do escritório, não acordo |

---

## 3. Fases do núcleo nunca iniciadas

| Fase | Estado | O que saber antes de começar |
|---|---|---|
| **6** — orçamento versionado e aditivo | ⬜ nunca começada | O p9 abriu a porta: `definir_valor_contrato()` é escritor único e os 5 chamadores passam por ele. ⚠️ faixa de migration **271-276** — o **270 está queimado** por registro fantasma no `migration_history`; numerar 270 faz a migração nunca rodar, em silêncio |
| **7** — CPM/baseline/EVM | ❌ **obsoleta como escrita** | Reescrita pelo p10. Implementá-la ao pé da letra criaria uma **segunda** rede de predecessoras e uma **segunda** baseline |
| **8** — financeiro avançado + Domínio | ⬜ **spec nova, plano nenhum** | A spec foi reescrita em 17/08 (`specs/2026-08-17-fase-8-financeiro-design.md`) com escopo maior; 🔬 **não existe plano de execução para ela**. O `plans/2026-07-21-fase-8-...md` é da versão velha e serve como referência, não como roteiro |
| **9a/9b** — portal, assinatura de medição, contratos, Drive | ⬜ nunca começada | A decisão nº 2 já foi tomada: o dono do `valor_contrato` é a **Fase 6**; a 9b vira camada documental |

> Os planos das Fases 6-9 foram escritos sobre o schema de antes das Fases 1-5.
> Cada um tem seção *"Premissas a reconfirmar antes de executar"* — abra por ela.

---

## 4. Ciclo de compras — a Fase 4 está escrita e sem plano

`specs/2026-08-19-status-unificado-design.md` existe desde 19/08. Plano de
execução, não.

🔴 **E ela carrega o pior tipo de pendência:** as "9 etapas" da régua **nunca foram
enumeradas**. 📖 o número é citado como coisa sabida em `2026-08-15-alcadas-design.md:469`,
`:554`, `:895`, `2026-08-17-nota-e-liberacao-design.md:8`, `:398` e na própria spec da
Fase 4 — e 🔬 **nenhum dos cinco lista os nove**. Não há enum, tabela nem spec. A
fase não é "implementar a régua escrita": é **decidir quais são as etapas**.

🔬 O inventário que a spec mediu: **seis portadores de estado em quatro tabelas**,
mais dois sem coluna (a nota é presença, o adiantamento é `baixado_em`), e
**nenhuma função que agregue isso** — as telas põem os badges lado a lado e deixam
a soma para a cabeça de quem olha. **A régua é código novo, não refatoração.**

Três decisões abertas, todas com recomendação na spec: régua **derivada** e não
gravada; **uma** régua com as casas inaplicáveis apagadas; e o mapa das 9 casas
conferido contra as saídas laterais.

As Fases 1, 2 e 3 do ciclo estão ✅ entregues, com runbook rodado **por script**
(43+41+21 no piloto, 14/14 nas alçadas, 36/36 na Fase 1).

---

## 5. As 25 automações — 25 vivas em 04/08, sem reconferência desde

`docs/reconferencia-backlog-2026-08-04.md`: **zero entregues, 25 vivas** — 13
podiam começar naquele dia, 12 travadas por decisão ou credencial. Passaram-se 19
dias de trabalho em cima dessas áreas e ninguém reabriu a lista.

📖 **Uma já mudou e a lista não sabe:** **A05** ("emitir `rdo_finalizado` nos 4
caminhos") estava PARCIAL porque o 4º caminho seguia intacto. Hoje
📖 `views/rdo.py:3415-3417`, dentro de `rdo_salvar_unificado` (📖 `:2769`), tem
`publica_custos(rdo)` + `emit` — entrou pelo trabalho de 21/08 (rascunho não lança
custo). **Isto é leitura de código, não medição**: candidato a riscar, depois de
rodar as famílias de RDO.

Três delas são decisões suas, não trabalho pendente:

- **A24** — rateio dos encargos patronais. 📖 `services/folha_service.py:1378-1444`
  está **completo e sem chamador**; hoje a mão de obra sai **~28% subestimada**.
- **A25** — `N8N_WEBHOOK_URL` + cron. Segura **toda notificação do plano**.
- **A04** — conta de débito da despesa geral (pergunta do contador).

---

## 6. Resíduos nomeados dentro de planos já fechados

| Resíduo | Prova | Por que ficou |
|---|---|---|
| 🟡 **RDO em rascunho ainda alimenta o cronograma** | 🔬 23/08: `utils/cronograma_engine.py:1412` (`atualizar_percentual_tarefa`) não menciona `estado` nem `rdo_ciclo_vida` — não filtra apontamento por estado do RDO | O custo foi travado em 21/08; o percentual não. Travar muda a semântica do avanço em dezenas de testes de 20/08. O capítulo 23a foi reescrito para não prometer |
| 📖 **`obra.progresso_conclusao` não existe em Python nenhum** | O card de obra tenta mostrá-lo, o `{% if %}` engole, a barra nunca aparece | Fazer funcionar é funcionalidade nova, não conserto |
| **Jornada E2E nunca rodada** | `bash run_tests.sh --jornada` | Os 7 blocos (59 passed) e a varredura (48/48) rodaram depois que o Chromium voltou; a jornada, não |
| **Miniatura do portal × migração de fotos** | Gate da passada 2 da Task 15 da Fase 5 | Único ponto do plano sem recomendação: ou a rota de foto por token (9a) vem antes, ou o portal fica sem miniatura no intervalo |

---

## 7. Fase 0.5 — o que continua ❌

| Item | Situação |
|---|---|
| Backup **agendado** | ❌ só existe o pré-migração; usar job do EasyPanel, não APScheduler |
| ~~Triagem de `fix/bloco2-segredos` e `fix/bloco1-blindagem-acesso`~~ | ✅ **fechado por inexistência — 23/08.** 🔬 `git ls-remote --heads origin` lista **20 branches** e nenhuma das duas está entre elas. O item nunca esperou credencial: as branches não existem mais no remoto. Não há o que triar |
| Conflito `opencv-python` × `headless` | ❌ entra por `deepface`/`retina-face`; exige decidir sobre reconhecimento facial |
| `psycopg2-binary` → compilado | ⏸️ recomendado; só se valida no build de produção |
| `scripts/medir_producao.py` | ❌ aguarda acesso ao banco de produção — pré-requisito de quase toda medição pendente |
| `/health/veiculos` | 🔴 1 decisão: fechar se nenhum monitor externo a consome |

---

## 8. O que **não** está aberto — para ninguém reabrir por engano

Fases **0, 0.6, 1, 1.5, 2, 3, 4 e 5** fechadas com gate verde. Ciclo de compras
**Fases 1, 2 e 3** entregues. Os **dez pacotes p1–p10** no GitHub. **M01–M10** do
cronograma MPP entregues (a Fase 7 é que virou obsoleta por causa deles). Dos
cinco planos da reunião de 20/08, **três ✅** (RDO efetivo e terceiros 31/31,
cadastro rápido de funcionário 22/22, linha de base e revisões 22/22) e dois 🟡 —
os do item 2. O manual visual do RDO (18 telas) e o do ciclo de compras estão
entregues e regeneráveis por comando.

🔬 Dos 99 planos, **70 são anteriores a 22/07**. Isso **não** os torna órfãos: a
árvore trouxe o código mesclado. O corte que importa não é a data do plano, é se
o arquivo que ele promete existe — foi o teste aplicado no item 1.

---

## 9. Ordem sugerida

1. **Decidir sobre o PR #6** (espinha financeira). É a única entrega inteira fora
   do `main`, e o documento que a descreve engana quem retomar por ele. Depende do
   item humano nº 2.
2. **Fase 4 do ciclo** — enumerar as 9 etapas. A spec está pronta; a decisão é sua.
3. **Rollup Task 3** — uma frase do Paulo destrava.
4. **Reconferir as 25 automações** — a lista tem 19 dias e pelo menos a A05 já está
   errada.
5. **Fase 6** — o p9 já deixou a porta aberta, e é a fase com menos incógnita.
