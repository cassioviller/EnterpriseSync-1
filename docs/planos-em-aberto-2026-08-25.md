# Estado de todos os planos e specs — fecho de 2026-08-25

> **O que é:** o índice de estado dos **103 planos** de `docs/superpowers/plans/` e
> das **43 specs** de `docs/superpowers/specs/`. Todo arquivo foi **estampado no
> próprio corpo**, logo abaixo do título, com o veredito e a prova. Este documento
> é o mapa; a verdade de cada plano mora no plano.
>
> **Substitui** `docs/planos-em-aberto-2026-08-23.md`, que continua válido como
> registro histórico e como a peça que descobriu a fratura de linhagem.
>
> **Contra o quê:** `main` em `657326c4`, árvore limpa. `main` está **25 commits à
> frente do `origin`**.
>
> **O que este documento NÃO é:** não é plano e não muda código.
>
> Marcas: 🔬 medido · 📖 lido no código (`arquivo:linha`) · 🧮 deduzido.

## O placar

🔬 Contado sobre os arquivos estampados, em 25/08:

| Veredito | Planos | Specs |
|---|---:|---:|
| ✅ Fechado | 84 | 36 |
| ✅ Fechado, com resíduo nomeado | 7 | — |
| ❌ Obsoleto — não executar | 8 | — |
| 🟡 Aberto — trabalho real pendente | 9 | 2 |
| ⏸️ Parado por pessoa, não por código | 1 | — |
| 📋 Spec de execução, não plano | 1 | — |
| 📖 Referência, não é spec de mudança | — | 5 |
| **Total** | **110** | **43** |

Os planos passaram de 103 para **110** hoje. Os sete novos são a resposta à
varredura de code review: um documento de evidência
(`2026-08-25-fecho-dos-114-achados.md`, que virou **spec**) e **seis planos de
onda**, somando 45 tasks. Dos 9 abertos, **3 são herdados** (Fase 9, Fase 8, resgate
da Espinha) e **6 nasceram hoje**.

**Sobram três planos herdados que pedem código, mais o de fecho escrito hoje, um
que pede duas pessoas, e nenhum spec órfão.** Tudo o mais está fechado ou
explicitamente riscado.

## Por que a contagem óbvia mentia

🔬 `2026-07-21-fase-1-identidade-papeis.md` tem **72 de 72 caixas abertas** e a fase
está fechada desde 21/07 com 11/11 tasks. O mesmo vale para as Fases 2, 3, 4, 5 e
para os dez módulos do cronograma MPP. Ninguém volta para marcar caixa — e a casa
nunca pediu que voltasse: a caixa é **rascunho de execução**, não registro de
estado.

Somando as caixas dos 103 planos, o repositório parecia ter **~2.900 itens em
aberto**. O número verdadeiro de planos com trabalho de código pendente é **três**.

Por isso o teste aplicado a cada arquivo foi **existência do arquivo que o plano
promete**, medido mecanicamente contra a árvore, e não checkbox nem mensagem de
commit.

---

## 🟡 O que está aberto de verdade — os três

### 1. Fase 8 — o plano de contas canônico
`plans/2026-08-24-fase-8-plano-de-contas-canonico.md` · 10 tasks · 🔬 3 de 21
arquivos existem.

**Dois bloqueios, ambos nomeados no próprio plano:**
- 🔴 **A Task 1 é humana e é pré-requisito da D2.** Ela mede produção. Sem ela o
  de-para está sendo decidido com número de banco de dev, que é 99,9% resíduo de
  suíte. Se produção mostrar `5.x` dominante, a spec está errada e o canônico volta
  à mesa. Depende de `scripts/medir_producao.py`, que aguarda acesso ao banco de
  produção.
- 🔴 **D6 — o de-para não pode ser chaveado só por código.** 🔬 Os dois seeders
  aposentados **trocam entre si** o significado de `5.1.01` e `5.1.02` (Materiais
  Diretos ↔ MÃO DE OBRA). Um de-para por código mandaria material para pessoal em
  metade do parque, **em silêncio**. A única evidência sobrevivente de qual seeder
  rodou é o **nome** da conta — que a spec proibiu usar. Recomendação do plano:
  chavear em `(código, nome)` por igualdade exata contra os dois conjuntos fechados
  que estão no repo; semelhança de string continua proibida.

### 2. Resgate da Espinha Financeira
`plans/2026-08-24-resgate-espinha-financeira.md` · 10 tasks · 🔬 7 de 20 arquivos
existem.

Porte de **2.542 linhas** já escritas e testadas na branch
`design/espinha-financeira-obra` (PR #6), do outro lado da fratura de 22/07.
Nove das dez tasks podem andar hoje. **Uma** está presa a decisão de negócio sua:
verba/lucro, a opção A-B-C do telhado viga I.

🔴 O achado que impede `git checkout` + commit: os dois leitores de RDO da branch
não filtram estado (um não filtra nada; o outro filtra por `RDO.status ==
'Finalizado'`, que não filtra nada porque todo RDO nasce `'Finalizado'`). Portados
como estão, reabrem por baixo o bug que o `main` fechou por cima em 24/08.

### 3. Fase 9a/9b — portal, assinatura de medição, contratos, Drive
`plans/2026-07-21-fase-9-portal-assinatura-contratos.md` · 🔬 19 de 35 arquivos
existem.

Nunca começada. O que existe veio por outros caminhos (portal do cliente, medição,
ciência do RDO). Faltam `services/assinatura_documento.py`,
`services/contrato_service.py`, `services/drive_client.py`,
`scripts/portal_acessos.py`.

⚠️ **O plano foi escrito sobre o schema de antes das Fases 1–5** e tem seção
*"Premissas a reconfirmar antes de executar"* — abra por ela. A decisão nº 2 já
caiu: o dono do `valor_contrato` é a **Fase 6**, então a 9b vira camada documental.

---

## ⏸️ Parado por pessoa, não por código — o único

`plans/2026-08-20-manual-padrao-preenchimento-rdo.md` — Steps 1–4 (4 de 11 caixas).
Falta **Alan e Abel** lerem o capítulo 23a antes de ele virar cobrança. Sem essa
rodada o capítulo é opinião do escritório, não acordo. **Nenhuma linha de código
destrava isto.**

---

## ❌ Os oito riscados — para ninguém executar por engano

| Plano | Por que não executar |
|---|---|
| `2026-07-21-fase-7-planejamento-avancado-cpm-evm.md` | **Reescrita pelo p10.** Ao pé da letra criaria uma **segunda** rede de predecessoras e uma **segunda** baseline, concorrendo com as dos módulos M01–M10 |
| `2026-07-21-fase-8-financeiro-avancado-dominio.md` | Substituída pelo plano de 24/08, escrito sobre a spec nova de 17/08. Referência histórica, nunca roteiro |
| `2026-06-15-espinha-financeira-plano-mestre.md` | O contrato DC1–DC11 segue valendo, mas o **roteiro** foi substituído pelo plano de porte de 24/08 |
| `2026-06-15-fatia-1-resultado-por-atividade-plan.md` | ⬇️ |
| `2026-06-15-fatia-2-custos-nao-mo-por-atividade-plan.md` | ⬇️ |
| `2026-06-15-fatia-3-evm-previsao-plan.md` | ⬇️ |
| `2026-06-15-fatia-4-lente-caixa-plan.md` | ⬇️ |
| `2026-06-15-fatia-5-inteligencia-portfolio-plan.md` | As cinco fatias: o código existe, **mas na branch do PR #6**. Executá-las de novo do zero seria reescrever 2.542 linhas já testadas. O caminho é o **porte**, com as correções que 476 commits de divergência exigem |

---

## ✅ Fechado com resíduo nomeado — os sete

Entregas reais; sobrou algo pequeno, nomeado, que ninguém deve confundir com fase
em aberto.

| Plano | Resíduo | Julgamento |
|---|---|---|
| `2026-08-04-plano-consolidado.md` | 🔬 54/59, mas **dois dos cinco eram falso alarme** (ver o bloco de estado no próprio plano). Resíduo real: `test_a09_dedup_nf_entrada_e_tenant_almoxarifado.py` | 🔴 **Vale corrigir.** 🔬 Zero testes citam `entrada_ja_lancada`: a **A09** foi dada como ENTREGUE por leitura de código, e o furo de tenant do dedup (`almoxarifado_utils.py:257`) é a prova do custo. O do **A05** foi deliberadamente não criado, com razão escrita — o arreio B0.3 cobre |
| `2026-08-06-rodada-b6-varredura.md` | 🔬 15/20. Os quatro `test_b6_404_{obras,frota,cauda,miscelanea}.py` nunca foram escritos | O recorte entregue foi `test_b6_estorno_recebimento.py` e `test_b6_familia2_reembolso_import.py` |
| `2026-08-06-rodada-b5-varredura.md` | 🔬 18/19. `test_b5_curva_baseline.py` | — |
| `2026-06-02-bloco1-blindagem-acesso-plan.md` | `test_isolamento_tenant_bloco1.py` nunca existiu com esse nome | 🔴 **e é mais que resíduo:** o code review de 25/08 achou **furos de tenant vivos** (`multitenant_helper.py:25`, `transporte_views.py:204`, `veiculos_services.py:167`). A blindagem deste bloco **não cobriu o parque** |
| `2026-06-05-bloco3-bdi-plan.md` | `scripts/preflight_migracao.py` nunca existiu | inofensivo |
| `2026-06-08-remediacao-saude-app-plan.md` | `services/tenant_config.py` nunca existiu | inofensivo |
| `2026-06-09-cadastro-palavras-chave-plan.md` | 🔬 10/11. `services/leitor_fluxo.py` | inofensivo |

---

## Os falsos alarmes desta varredura — conferidos e derrubados

🔬 Cinco arquivos apareceram como "ausentes" na medição mecânica e **não são
trabalho pendente**:

| Arquivo | Veredito |
|---|---|
| `tests/test_cronograma_importacao_playwright.py` | **Renomeado** para `tests/test_cronograma_importacao_obra_playwright.py`. O M10 está inteiro |
| `templates/obras.html` | **Apagado** na limpeza de templates mortos. A Fase 2 está fechada |
| `templates/cronograma/obra.html` | **Apagado** na mesma limpeza; o físico-financeiro vive em `templates/cronograma/fisico_financeiro.html` |
| `utils/maquina_estados.py` | Nunca existiu com esse nome — a máquina de estados mora em `services/` |
| `handlers/financeiro_handlers.py` | Da linhagem velha, comum a todas as branches de junho. Não volta |

🔬 E os **70 planos anteriores a 22/07 não são órfãos**: a árvore trouxe o código
mesclado. Medidos um a um, quase todos têm **100% dos arquivos prometidos na
árvore**. O corte que importa nunca foi a data do plano.

---

## 🔴 O que esta varredura descobriu que nenhum plano previa

O `/code-review` do app inteiro, rodado no mesmo dia em **dez passadas por módulo**
sobre 286.517 linhas, achou **114 defeitos — 33 graves**. Estão em
`docs/auditoria/achados-code-review-2026-08-25.md`.

**Isto muda a ordem de prioridade do repositório.** Os três planos abertos são
funcionalidade nova; vários dos 33 graves são dinheiro errado, vazamento entre
tenants e relatórios que nunca funcionaram — em código que já está em produção.

Dois deles cruzam com o backlog e confirmam-no por caminho independente:
- 📖 `folha_pagamento_views.py:148` (reprocessar folha dobra o valor no contas a
  pagar e no razão) **é a automação A12**, que a reconferência de 23/08 lista como
  ABERTA.
- 📖 `multitenant_helper.py:25` (papéis GESTOR_EQUIPES e ALMOXARIFE escrevem num
  tenant fantasma) é a prova de que a **A-blindagem do bloco 1 não cobriu o parque**.

A evidência agrupada por causa, com as decisões D1/D2/D3, é
`docs/superpowers/plans/2026-08-25-fecho-dos-114-achados.md` — que serve de **spec**,
não de plano: cobre seis subsistemas independentes e foi quebrado em um plano por
onda. **As seis ondas têm plano escrito** (25/08), somando **45 tasks**. A Onda 1 teve o
código do próprio plano extraído e executado (🔬 32 passed) antes da entrega. A
ordem recomendada é 1 → 2 → 3 → 5 → 4 → 6, e o porquê está no cabeçalho do
documento de fecho.

---

## As 25 automações — o estado continua sendo o de 23/08

`docs/reconferencia-backlog-2026-08-23.md`: **9 entregues, 7 parciais, 9 abertas.**
Não foram reconferidas nesta varredura porque a de 23/08 tem dois dias e foi feita
item a item. **Quatro decisões suas destravam o resto:** A04 (conta de débito da
despesa geral — pergunta do contador), A18, A24 (rateio dos encargos patronais;
📖 `services/folha_service.py:1378-1444` está **completo e sem chamador**, e a mão
de obra sai ~28% subestimada) e A25 (`N8N_WEBHOOK_URL` + cron, que segura **toda**
notificação do plano).

## Fase 0.5 — o que continua ❌

| Item | Situação |
|---|---|
| Backup **agendado** | ❌ só existe o pré-migração; usar job do EasyPanel, não APScheduler |
| Conflito `opencv-python` × `headless` | ❌ entra por `deepface`/`retina-face`; exige decidir sobre reconhecimento facial |
| `psycopg2-binary` → compilado | ⏸️ recomendado; só se valida no build de produção |
| `scripts/medir_producao.py` | ❌ aguarda acesso ao banco de produção — **pré-requisito da Task 1 da Fase 8** |
| `/health/veiculos` | 🔴 1 decisão: fechar se nenhum monitor externo consome |

## Resíduos de fora dos planos

| Resíduo | Estado |
|---|---|
| `obra.progresso_conclusao` não existe em Python nenhum | O card tenta mostrar, o `{% if %}` engole, a barra nunca aparece. Fazer funcionar é **funcionalidade nova**, não conserto |
| Jornada E2E nunca rodada | `bash run_tests.sh --jornada`. Os 7 blocos (59 passed) e a varredura (48/48) rodaram; a jornada, não |
| Miniatura do portal × migração de fotos | Único ponto sem recomendação: ou a rota de foto por token (9a) vem antes, ou o portal fica sem miniatura no intervalo |

## Ordem sugerida

1. 🔴 **Os 33 graves do code review**, começando pelos que corrompem dado em
   produção. É o único item desta lista que já está errando **hoje**, com dado real.
2. 🔴 **Empurrar os 25 commits** — a Fase 6 inteira está só nesta máquina. Mas
   corrigir antes o `views/aditivos_views.py:102`: subir o inflador de contrato 100×
   é subir um defeito de dinheiro.
3. **Fase 8** — depois de `medir_producao` rodar em produção e da D6 decidida.
4. **Resgate da Espinha** — nove das dez tasks andam sem você; a décima espera a
   decisão do telhado viga I.
5. **Fase 9a/9b** — a menos urgente, e a que mais precisa de reconferência de
   premissas antes de virar código.
