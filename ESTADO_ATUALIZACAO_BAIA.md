# Estado da atualização da obra Baia — físico-financeiro

> Documento de handoff. Última atualização: **2026-07-30**.
> Resume o que foi feito nesta rodada e o que ainda falta.

---

## Rodada 2026-07-30 — RDOs de 23/07 a 29/07 vindos do WhatsApp

Segunda passagem pelo caminho aberto em 27/07, e a prova de que ele repete: o
export novo do grupo (`Conversa do WhatsApp com 📝 Diário de Obras - Veks
Engenharia (1).zip`) trouxe **17 dias da Obra Itu, de 07/07 a 29/07**. Os 12
primeiros já estavam no JSON e foram preservados intactos — entraram os **5
dias novos: 23, 24, 27, 28 e 29/07**. Não há RDO de 25 e 26/07 (sábado e
domingo) nem de 30/07 até o momento do export.

Nenhuma peça nova de código. O comando é o mesmo que o documento previa:

```bash
python scripts/whatsapp_para_rdos.py \
    --zip "Conversa do WhatsApp com 📝 Diário de Obras - Veks Engenharia (1).zip" \
    --obra-marcador "Obra Itu" --regras docs/rdo/regras_apontamento_baia.json \
    --desde 2026-07-23 --saida /tmp/payload.json
```

`--desde` é o que separa o novo do que já entrou: sem ele o parser reprocessa
os 17 dias e o merge teria de descartar 12 na mão.

### O de-para aplicado — REVISAR

| Dia | Tarefa | Valor | Base no texto |
|---|---|---|---|
| 23/07 | 20 Nivelamento Calçadas (B) | 90% | nivelamento e compactação do solo das calçadas de A e B |
| 23/07 | 65 Nivelamento Calçadas (A) | 80% | idem — A vinha de 60%, B de 80% |
| 24/07 | 20 / 65 | 100% | "concluída a compactação do solo das áreas destinadas às calçadas dos Galpões A e B" |
| 24/07 | 21 Ferragem Calçada (B) | 40% | "iniciada a armação das ferragens das calçadas do Galpão B" |
| 27/07 | 21 | 60% | "concluída a armação das ferragens das calçadas do Galpão B" |
| 28/07 | — | — | só lona e posicionamento de armadura: nenhum dos dois tem tarefa (ver abaixo) |
| 29/07 | 21 | 75% | "iniciada a montagem das armaduras da calçada do Galpão B, com a colocação das malhas inferior e superior" |

**Duas leituras que o texto não resolve sozinho, decididas pelo usuário em
30/07:**

1. **A tarefa 21 é UMA série contínua, não duas.** O texto diz "concluída a
   armação" em 27/07 e "iniciada a montagem das armaduras" em 29/07 — o que,
   lido ao pé da letra, fecharia a tarefa e depois a reabriria. A leitura
   adotada: 24–27/07 é corte, dobra e pré-montagem; 29/07 é a colocação das
   malhas na calçada. Fases da mesma tarefa, daí 40 → 60 → 75.
2. **"Posicionamento da armação das vigas longitudinais do Galpão B" (23 e
   28/07) NÃO aponta na tarefa 14.** Posicionar armação já executada não é
   nova execução, e a 14 é a única tarefa com quantitativo (48 un) — saturada
   desde 10/07. Lançar produziria clamp em 100% com warning e inflaria o
   acumulado. Fica no texto do RDO.

### O que o cronograma ainda não comporta

O que era um aviso virou **fato**: em 27/07 o Grupo Mônica decidiu pelos cochos
em **alvenaria**. Segundo o Eng. Gustavo, a carga passa de ~40 kg/m linear
(estimativa da projetista de LSF) para **~700 kg/m linear**, o que obriga a
verificar as vigas longitudinais e os blocos de coroamento **antes da
concretagem**. A revisão do projeto estrutural estava prevista para 31/07.

Consequências que este documento registra e o cronograma ainda não reflete:

- A **concretagem das vigas baldrame segue sem execução** — o RDO de 24/07 diz
  que a indefinição foi a causa, e as chuvas ainda obrigaram a prever caixaria
  para conter as valas (mais material, mais mão de obra, mais prazo).
- A proposta com os cenários técnicos foi enviada em **10/07 com validade de 10
  dias**; a decisão veio em **27/07**. O RDO de 27/07 diz explicitamente que
  será preciso reavaliar o planejamento e recalcular os impactos do período de
  indefinição. **Isso não está no cronograma nem no financeiro.**
- Enquanto o projeto revisado não chega, a obra segue pelo projeto aprovado em
  contrato — decisão de engenharia registrada em 24/07 para não paralisar, com
  o risco de retrabalho assumido e a ser apresentado ao cliente.

### Dados no repositório

`cronograma_fisico_financeiro_baias.json` (e o symlink em `tests/fixtures/`)
passou de 26 para **31 RDOs**; o diff é de 184 linhas, **todas inserções** —
nenhum dia anterior foi tocado. Fotos novas em `fotos_rdos/2026-07-23`, `-24`,
`-27`, `-28` e `-29` (**26 arquivos, +6,3 MB**; a pasta vai a 37 MB).

> **Correção de 30/07 — as fotos de 27/07 tinham caído em 24/07.** No grupo, o
> engenheiro postou as fotos do dia 27 **antes** do texto do RDO, e o parser as
> atribuiu ao bloco anterior. As 7 últimas fotos que estavam em
> `fotos_rdos/2026-07-24` (`6.jpg`…`12.jpg`, a começar pela legendada "Chegada
> material calçada Galpão A") são de 27/07 e foram movidas para
> `fotos_rdos/2026-07-27/1.jpg`…`7.jpg`, com as legendas na mesma ordem. Confere
> com o texto de cada dia: 24/07 fala de compactação e início da armação (fotos
> em dia nublado), 27/07 fala de conclusão da armação e aplicação de lona (fotos
> de fim de tarde). O dia 24 fica com 5 fotos e o 27 com 7. **Atenção no
> reimport:** a pasta do dia manda no conjunto inteiro, então subir o JSON com as
> duas pastas assim já corrige o dia 24 no banco.

Duas regras novas em `docs/rdo/regras_apontamento_baia.json`: `ferragem-calcada-b`
e `malhas-calcada-b`, ambas para a tarefa 21. Nesta rodada os três bullets de
ferragem de calçada caíram como "bullet sem regra" e a tarefa foi achada à mão;
com as regras, o parser já as resolve — continuam sem `pct`, porque o
percentual segue sendo decisão de engenharia.

### Só a Obra Itu — e o que isso deixa de fora

O grupo é compartilhado. Dos 19 blocos de RDO do export, **17 são da Obra Itu**
e **2 são da "Obra a Angela"** (RDOs de 14 e 15/07, postados pelo Abel), que o
`--obra-marcador` descarta. Há ainda um pedido de RDOs de Vila Velha e Santo
Antônio em 29/07, mas esses RDOs nunca foram postados no grupo. Decisão de
30/07: esta série é só da Obra Itu; a Angela, se um dia entrar, pede JSON
canônico próprio e outra rodada do parser.

A regra de herança do parser não contaminou nada: bloco sem marcador herda a
obra do bloco anterior **do mesmo autor**, e os blocos da Angela são de outro
autor. O único bloco herdado foi o de 22/07, do próprio Eng. Alan, e a herança
saiu como aviso no relatório.

### Fotos de 27 a 29/06 seguem sem legenda — de propósito

Os dias 27, 28 e 29/06 têm 7 fotos no repositório e **nenhuma chave `fotos`** no
JSON. Isso NÃO as deixa de fora do RDO: `materializar_fotos_rdo` tem um caminho
para "pasta com imagem e JSON sem legenda" que anexa todas em ordem numérica com
legenda vazia. Medido no import real — 27/06: 1 foto, 28/06: 1, 29/06: 5, todas
criadas, nenhuma com legenda (contra 30/06, que tem 9 no JSON e 9 com legenda).

As legendas originais não são recuperáveis: o export do grupo pula de **25/05
para 08/07** e não cobre junho. Decisão do usuário em 30/07: **deixar sem**.
Legenda escrita a partir da imagem seria descrição de quem olhou a foto, não o
que o engenheiro registrou — e num documento que serve de respaldo essa
diferença importa.

---

## Rodada 2026-07-27 — RDOs de 07/07 a 22/07 vindos do WhatsApp

O diário da obra vive no grupo **"📝 Diário de Obras - Veks Engenharia"**: o
Eng. Alan posta o RDO de cada dia em texto (Efetivo / Atividades Executadas /
Observações / Próximas Atividades) e as fotos logo abaixo, cada uma com a
legenda na linha seguinte. O export do grupo (`conversa (2).zip`) trouxe **12
RDOs da Obra Itu, de 07/07 a 22/07**. No sistema, a série parava em 13/07 e os
dias 07, 09, 10 e 13/07 tinham texto mas `apontamentos: []`.

**Caminho novo, não-destrutivo.** Até aqui, entrar com RDO em lote só existia
pela seção `"rdos"` do reimport físico-financeiro — que apaga tarefas,
propostas, orçamentos, medições e todos os RDOs da obra antes de recriar, e
que é **recusado** em obra já versionada por .mpp (guard do M09). Ou seja:
acrescentar sete dias ao diário de uma obra em andamento não tinha caminho.
Agora tem:

| Peça | O que faz |
|---|---|
| `scripts/whatsapp_para_rdos.py` | export do WhatsApp → payload `{"rdos": […]}` + fotos em `fotos_rdos/<data>/N.jpg` na ordem das legendas |
| `docs/rdo/regras_apontamento_baia.json` | de-para revisável atividade→tarefa/%, usado pelo parser (`--regras`) |
| `services/atualizacao_rdos.py` | upsert por `(obra_id, data_relatorio)`; **não apaga nada**; pula RDO imutável da Fase 5 com aviso; apontamento via `registrar_apontamento` |
| `scripts/atualizar_rdos_obra.py` | CLI genérico por obra, com `--dry-run` |
| `services/rdo_fotos_import.py` | `_materializar_fotos_rdo` extraído, usado pelos dois caminhos |

🔬 27/07 — ponta a ponta em dev, sobre a obra importada só até 06/07:
**12 RDOs criados, 22 apontamentos, 0 pendências**; tarefas (101), propostas
(1) e medições (6) **idênticas antes e depois**. A resolução de tarefa caiu
inteira no fallback por NOME (`mpp_uid` vem NULL do import JSON) e acertou os
dois galpões.

> ⚠️ **Os ids do cronograma são contraintuitivos: 11–52 = Galpão B, 55–96 =
> Galpão A.** Os dois galpões repetem os mesmos nomes de tarefa E o mesmo pai
> ("Fundação"); só o avô distingue.

### O de-para aplicado — REVISAR

O texto do RDO é narrativa ("armação de 37,50 m da primeira viga longitudinal
do Galpão A, de um total de 57,50 m"); o % é leitura de engenharia. Foi esta:

| Dia | Tarefa | Valor | Base no texto |
|---|---|---|---|
| 07/07 | 14 Ferragens Fundação (B) | qtd 11 | 11 vigas transversais |
| 08/07 | 15 / 60 Concretagem das Brocas | 100% | "todas as brocas dos Galpões A e B" |
| 08/07 | 16 / 61 Concreto Magro | 60% | magro nas longitudinais; transversais suspensas |
| 08/07 | 14 Ferragens Fundação (B) | qtd 3 | 3 vigas longitudinais |
| 09-10/07 | 14 Ferragens Fundação (B) | qtd 1 + 1 | 1 viga longitudinal por dia |
| 13/07 | 59 Ferragens Fundação (A) | 35% | 20,00 m de 57,50 m |
| 14/07 | 59 | 65% | 37,50 m de 57,50 m |
| 15/07 | 59 | 75% | longitudinais concluídas; faltam transversais |
| 15/07 | 13 / 57 Escavação Hidráulica | 100% | 22 escavações de esgoto, A e B |
| 16/07 | 59 | 85% | 8 vigas transversais |
| 16/07 | 39 / 84 Instalação Infra Hidráulica | 100% | "concluída a instalação … das 22 baias" |
| 17/07 | 59 | 100% | "finalizando a etapa de armação das vigas baldrame" |
| 17/07 | 66 Ferragem Calçada (A) | 15% | 2 sapatas dos troncos |
| 20/07 | 66 | 60% | 10 sapatas |
| 21/07 | 20 Nivelamento Calçadas (B) | 60% | rebaixo de 15 cm no Galpão B |
| 22/07 | 65 Nivelamento Calçadas (A) | 60% | rebaixo de 15 cm no Galpão A |
| 22/07 | 20 | 80% | compactação do solo do Galpão B |

**Três pontos que precisam do seu aval:**

1. **39 / 84 "Instalação Infra Hidráulica" a 100% é ANTECIPAÇÃO** — a tarefa
   está planejada para agosto. O RDO de 16/07 diz que a instalação do esgoto
   das 22 baias foi concluída; se essa não for a mesma tarefa, tire os dois
   apontamentos.
2. **A tarefa 14 estoura o quantitativo.** Ela é a única com
   `quantidade_total` (48 un) e já chegou a 48 no acumulado 30/06–06/07 — em
   que, aliás, o JSON antigo lançou **24 brocas do Galpão A na tarefa do
   Galpão B**. Os dias 07–10/07 somam mais 16 un e o engine **clampa em 100%**
   com warning. Não reescrevi os dias antigos (fora do escopo desta rodada).
3. **O protótipo do cocho em LSF (21 e 22/07) não tem tarefa no cronograma** —
   o sistema construtivo (alvenaria × LSF) segue indefinido e é a causa
   declarada do atraso. Fica só no texto do RDO.

### Como repetir na próxima semana

```bash
python scripts/whatsapp_para_rdos.py --zip "conversa.zip" \
    --obra-marcador "Obra Itu" --regras docs/rdo/regras_apontamento_baia.json \
    --saida /tmp/payload_rdos.json --dry-run          # revisa
SIGE_ENABLE_DEMO_SEED=false python scripts/atualizar_rdos_obra.py \
    <admin> 10 /tmp/payload_rdos.json --dry-run       # revisa a resolução
SIGE_ENABLE_DEMO_SEED=false python scripts/atualizar_rdos_obra.py \
    <admin> 10 /tmp/payload_rdos.json                 # aplica
```

Os dois passos de `--dry-run` existem porque o de-para atividade→tarefa é
julgamento: o parser **sugere** (`_sugestoes`), e nada vira apontamento sem
`--aplicar-sugestoes` ou edição à mão.

### Dados no repositório

`cronograma_fisico_financeiro_baias.json` (e o symlink
`tests/fixtures/…`) passou de 19 para **26 RDOs**. As fotos novas entraram em
`fotos_rdos/2026-07-14` … `2026-07-22` (**31 arquivos, +9 MB**; a pasta vai a
30 MB). Os dias que já existiam ficaram com o texto e as legendas que já
tinham — foram revisados à mão antes; só o físico foi acrescentado.

---

## Rodada 2026-07-21 — M09: atualização de cronograma migra para a UI da obra

O fluxo de ATUALIZAÇÃO de cronograma deixou de ser "regenerar JSON +
reimportar": agora é a **aba Cronograma da página da obra** (M08) —
Importar cronograma (.xml/.mpp) → prévia com decisão de mapeamentos →
Aplicar (IDs/RDOs/fotos preservados, tarefas removidas arquivadas) →
Restaurar versão se preciso. O reimport do JSON canônico:

- continua valendo para **criação inicial** (e agora registra
  `CronogramaVersao` nº1 + snapshots + importação `json_canonico`);
- é **recusado** em obra já versionada pela importação de cronograma
  (mensagem manda usar a aba da obra) — o caminho destrutivo não
  atropela mais o histórico.

Verificação de equivalência automatizada:
`scripts/verificar_equivalencia_obra.py` (genérico por obra) e o cenário
completo em `tests/test_migracao_baias_equivalencia.py` (canônico →
`CRONOGRAMA 06.07.mpp` real → reconciliar → aplicar → equivalência →
rollback). **Procedimento homolog/produção**: (1) backup `pg_dump`;
(2) `--salvar estado.json` antes; (3) importar o .mpp pela aba da obra,
decidir pendências na prévia, aplicar; (4) `--comparar estado.json` —
qualquer divergência ⇒ Restaurar versão anterior e investigar.
Descontinuação dos scripts antigos (rebuild/diff/REMAP): agendada para
após 2 semanas de estabilidade em produção (spec M09 §4.3).

---

## Rodada 2026-06-30 — RDOs no payload de import (físico real pelo relatório semanal)

Spec `docs/superpowers/specs/2026-06-30-rdos-no-import-baia-design.md`;
plano `docs/superpowers/plans/2026-06-30-rdos-no-import-baia.md`.

O import (`importar_fisico_financeiro`) agora cria os **RDOs da Baia a partir de uma seção
`"rdos"` no JSON** (helper `_materializar_rdos` + `sincronizar_percentuais_obra`). Reimportar
deixou de orfanar/zerar o físico — antes o reimport apagava as `TarefaCronograma` e os RDOs
(que vinham de `scripts/seed_rdos_baias.py`) ficavam órfãos.

- **`scripts/seed_rdos_baias.py` não é mais necessário para a Baia** (o import é a fonte única).
  Mantido no repo para outras obras; sem mudança nele.
- Fixture `tests/fixtures/cronograma_fisico_financeiro_baias.json` ganhou 6 RDOs fiéis ao
  relatório 22–27/06. Físico resultante (cronograma, por tarefa): ESTUDO DE SOLO SPT **100%**,
  EXECUÇÃO DE PROJETOS **65%**, FAZENDA: NIVELAMENTO DO PLATÔ **20%**, demais **0%**.
- Mão de obra no RDO é só realismo (não gera custo). Invariantes financeiros preservados.
- Suíte focada verde (96 passed). Commits locais: `d6531d52` (helper+integração),
  `b0936359` (fixture+teste). **Pendente:** `git push` (ambiente sem credencial nesta máquina).

### Card de RDO passa a exibir o progresso da OBRA (não 0%)

Spec `docs/superpowers/specs/2026-06-30-progresso-obra-no-card-rdo-design.md`;
plano `docs/superpowers/plans/2026-06-30-progresso-obra-no-card-rdo.md`.

`utils/cronograma_engine.py::calcular_progresso_rdo` ganhou um **fallback**: tarefa sem
`quantidade_total` agora deriva o `percentual_realizado` do último apontamento até a data (mesma
fonte que `sincronizar_percentuais_obra`). Antes devolvia sempre 0, fazendo os cards de RDO
mostrarem "Progresso Geral 0,0%". Agora os cards exibem o avanço **acumulado da obra até a data do
RDO**, crescente (Baia: 1,7% em 22/06 → 2,3% em 27/06, verificado no browser). Correção de leitura;
rota/template/agregador inalterados; também beneficia obras do `seed_rdos_baias.py`.

Confirmado: das **56 tarefas** da Baia, só 5 têm %>0 (3 folhas citadas + 2 pais por rollup); as
outras **51 estão em 0%**. Suíte focada verde (98 passed). Commit local `4892d1cd`.

### Unificação do "progresso da obra" em toda a UI

Antes existiam **cinco** lugares com números diferentes de progresso da obra. Foram todos alinhados
à mesma métrica — `calcular_progresso_geral_obra_v2` (média das FOLHAS ponderada por duração,
acumulada até a data; ignora os pais, que dupla-contavam) — e à mesma formatação (**1 casa decimal**):

| Onde | Antes | Agora | Commit |
|---|---|---|---|
| Card de RDO | 0,0% (bug) | 2,3% (cresce por data) | `4892d1cd` |
| Header "Progresso Geral" do cronograma | 4% (média simples de todas as tarefas) | 2,3% | `4dbf3cb3` |
| Linha raiz "OBRA" do cronograma interno | 10,41% (rollup hierárquico) | 2,3% | `2a6bb930` |
| Portal do cliente — anel "CONCLUÍDO" | 4,4% (média simples) | 2,3% | `ccaaa754` |
| Portal do cliente — raiz da seção Cronograma | 10,4% (rollup) | 2,3% | `c557cb7e` |
| Formatação 1 casa decimal (header + raiz) | inteiro | 1 casa | `5f9c82e9` |

Notas:
- **Só exibição.** O rollup hierárquico persistido na raiz (10,41%) continua gravado no banco —
  apenas não é mais exibido. O fix da raiz/header interno é override no route/template
  (`cronograma_views.py`, `templates/obras/cronograma.html`); o portal trocou a fórmula do anel
  em `portal_obras_views.py:100` e faz override da raiz da árvore do cliente (`cronograma_cliente_tree`)
  quando há uma única raiz "OBRA".
- A raiz da seção Cronograma do portal só aparecia quando a obra tinha cronograma **`is_cliente`**
  (montado pelo editor `?cliente=1`); o import não cria esse cronograma, por isso o bug só apareceu
  em produção (em dev a seção ficava "em atualização", vazia). Os **filhos** da árvore mantêm seus
  próprios percentuais — só a raiz é alinhada ao número da obra.
- `calcular_progresso_rdo` ganhou fallback p/ `percentual_realizado` quando a tarefa não tem
  `quantidade_total` — origem do conserto do card e base das demais correções.
- Suíte focada verde (**102 passed**). Verificado no browser (cronograma interno + portal, anel e
  árvore). Tudo no `origin/main` (último commit `c557cb7e`).

### RDOs sem mão de obra no import + reimport idempotente (FK do `custo_obra`)

Commit `ae28dcff`.

- **Sem mão de obra no import.** A fixture pedia `mao_de_obra: 2/2/2/1/1/3`, e o import anexava os
  N primeiros funcionários ativos do tenant (aleatórios) em cada RDO. Zerado para `0` nos 6 RDOs —
  os RDOs nascem sem mão de obra e o usuário lança a equipe real **ao editar** cada RDO.
- **Bug de reimport descoberto (quebrava em produção).** A mão de obra dos RDOs virava `custo_obra`
  (tipo `mao_obra`, "1 diária"), que referencia o RDO **sem cascade** (`custo_obra_rdo_id_fkey`,
  delete rule NO ACTION). Reimportar sobre a Baia existente disparava
  `ForeignKeyViolation` ao apagar os RDOs antigos. Em dev (obra nova) não aparecia porque não havia
  `custo_obra` ainda.
- **Correção da idempotência** em `_materializar_rdos`: antes de apagar os RDOs antigos, agora
  **apaga** os `custo_obra` derivados deles e **desvincula** (`SET NULL` manual) as outras tabelas
  NO ACTION — `notificacao_cliente`, `movimentacao_estoque`, `alocacao_equipe`. (`rdo_custo_diario`
  já é SET NULL no banco.) Os filhos com ON DELETE CASCADE somem sozinhos.
- 2 testes novos (RDOs sem mão de obra; reimport com `custo_obra` referenciando o RDO não quebra e
  remove o custo). Suíte focada **104 passed**. Reimport real na obra 591 OK (6 RDOs, 0 mão de obra,
  0 `custo_obra`). Tudo no `origin/main` (último commit `ae28dcff`).

> **Produção:** após o deploy do código atual, a reimportação da Baia volta a funcionar (antes dava
> erro de FK) e remove os custos-fantasma de mão de obra; depois é só editar cada RDO para lançar a
> equipe real.

---

## ⚠️ POR QUE o ambiente cai no meio da sessão (5ª vez) — e como não repetir

**Sintoma:** no meio da sessão, `python3`/`git` somem com erro
`Transport endpoint is not connected`; `which python3` não acha nada.

**Causa-raiz (é de infraestrutura do sandbox, NÃO do nosso código):**
Este ambiente (Replit/Nix) serve o **`/nix/store` por um mount FUSE**. *Todos* os binários
da toolchain (python, git, node) vivem dentro de `/nix`, e arquivos de sistema como
`/etc/gitconfig` são **symlinks para dentro do `/nix`**. Quando o processo FUSE que serve
esse mount morre, o kernel passa a responder *"Transport endpoint is not connected"* para
qualquer acesso sob o mount → a toolchain inteira "desaparece" no meio da sessão.

O que mata o processo FUSE, mais provável aqui: **pressão de memória / OOM** no container.
Este repo carrega **TensorFlow + DeepFace** no import do `app` (reconhecimento facial), que
é pesado; ao rodar testes/scripts que importam `app`, o pico de RAM pode derrubar o daemon
do nix-store. Também pode ser reciclagem/idle-timeout do servidor de store do Replit.

**Como mitigar (o que está sob nosso controle):**
1. **Commit & push cedo e frequente.** Como a recuperação é *reiniciar o container* (que
   reconstrói o mount) e a sessão só volta puxando do git, qualquer trabalho não-pushado
   se perde. Esta é a lição principal — já é a 5ª vez.
2. **Git continua usável mesmo após a queda** com `GIT_CONFIG_NOSYSTEM=1` (ignora o
   `/etc/gitconfig` que aponta pro mount morto). Foi assim que este commit saiu.
3. **Não importar o stack de ML** (TensorFlow/DeepFace) quando o trabalho é só
   financeiro/cronograma — reduz a pressão de memória que provavelmente dispara o OOM.
   (Os testes daqui importam `app`, que puxa o ML; rodar só os 3 arquivos já ajuda.)
4. **Recuperação:** reiniciar o container → `git pull` da branch → seguir.

---

## Rodada 2026-06-27 — Reconciliação Planilha1 + correção do imposto (FEITA, falta rodar testes)

Spec: `docs/superpowers/specs/2026-06-27-reconciliacao-custos-imposto-baia-design.md`.
Branch: `fix/reconciliacao-custos-imposto-baia` (só o spec commitado; implementação **não
commitada** — ambiente caiu antes).

**Descobertas (investigação das fórmulas da `Planilha1`):**
- Motor: `imposto = (medição − fat_direto) × 13,5%` (ISS 4% + DAS 9,5%).
- 3 erros na planilha: Indiretos contados 3,5 E 5 meses (Δ 74.000); junho sem imposto +
  `+20.000` chumbado na mão; e 1 **bug no código**: `kpis`/`divergencia` tributavam a
  venda cheia (`venda × pct`), supertributando o fat direto.
- Decisões do usuário: **Indiretos 5 meses (versão cara)**; **tudo que a Veks recebe é
  tributado, inclusive junho/mobilização**; base = medição − fat direto.

**Mudanças aplicadas (working tree, NÃO commitadas):**
1. `services/cronograma_fisico_financeiro.py`: `kpis` (l.467) e `fluxo_caixa_divergencia`
   (l.452) → `imposto = (venda − dados["totais"]["fat_direto"]) × pct`. Em
   `calcular_fluxo_caixa` → deriva `meses_negativos` + `pior_caixa` (alerta ao vivo).
2. `tests/fixtures/cronograma_fisico_financeiro_baias.json`: `eap[].custo` + **`eap[].itens`**
   (o import lê dos ITENS, não do custo!) reconciliados; `peso_pct` recalculado; snapshot
   `fluxo_caixa_mensal` regravado (junho tributado). Convergência: veks total 800.960,
   imposto 128.903, **lucro projetado = lucro em caixa = 24.976**.
3. Alerta de caixa negativo (out = −40.142): `static/js/financeiro_obra.js`
   (`renderAlertaCaixa` + barra vermelha), `templates/obras/detalhes_obra_profissional.html`
   (`#fin-alerta-caixa`), `templates/cronograma/fisico_financeiro.html` (célula vermelha +
   resumo). Derivado ao vivo → some/aparece sozinho quando os valores mudam.
4. Asserts atualizados em `tests/test_importacao_fisico_financeiro.py` (data_fim 08/10;
   lucro_caixa_final 24976; delta_veks ~0; indiretos 39 linhas / total 457.000).

**PENDENTE (bloqueado por ambiente):** rodar
`python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py
tests/test_importacao_fisico_financeiro.py -q` e **commitar**. O mount FUSE do `/nix/store`
caiu no meio da sessão (Python e git indisponíveis: "Transport endpoint is not connected") —
**só volta com reinício do container** (mesmo problema da rodada anterior).

---

## ⚠️ Fonte de custo que PRECISA ser lida: `Planilha de Custos REV01 (2).xlsx`

O arquivo **`Planilha de Custos REV01 (2).xlsx`** (na raiz do projeto) é a versão nova
do plano de custos. A aba que importa é a **`Planilha1`** — é dela que saem:

- o **custo por etapa** (Veks + faturamento direto) de cada nó da EAP;
- o **bloco de fluxo de caixa mensal** (medição / imposto / caixa / fat_direto por mês),
  hoje gravado verbatim em `fluxo_caixa_mensal` no JSON.

**Nesta rodada os custos NÃO foram recalculados** — só o cronograma físico foi atualizado
(ver abaixo). Os números financeiros no JSON continuam vindos da REV01 **anterior**. Para
fechar a atualização de verdade, é preciso **ler a aba `Planilha1` do
`Planilha de Custos REV01 (2).xlsx`** e reconciliar:

1. `eap[].custo` (veks / fat_direto / total / peso_pct) de cada etapa;
2. `fluxo_caixa_mensal` (meses, medicao, imposto, gasto_veks, fat_direto, caixa…).

Como ler (quando o ambiente Python voltar):

```python
from openpyxl import load_workbook
wb = load_workbook("Planilha de Custos REV01 (2).xlsx", data_only=True)
ws = wb["Planilha1"]
for row in ws.iter_rows(values_only=True):
    print(row)
```

> Observação de ambiente: o Python está temporariamente indisponível nesta máquina
> (queda do mount FUSE do `/nix/store`); só volta com **reinício do container**.

---

## O que foi feito nesta rodada

### 1. Lógica nova: competência configurável do faturamento direto

Antes, o faturamento direto sempre abatia a base de imposto/entrada **no período seguinte**
("abater no próximo pagamento"). Agora há uma opção **por obra**:

- `fat_competencia = "seguinte"` (padrão) → comportamento antigo (abate no mês seguinte);
- `fat_competencia = "mesma"` → abate **na própria medição** (mesma competência),
  reduzindo o imposto do período a que pertence, **inclusive o último** (que no modo
  antigo ficava sem abater → pagava imposto a mais).

Ganho: menos imposto, porque o fat_direto reduz a base no período certo.
Diferença de imposto entre os modos = `alíquota × fat_direto do último período`.

**Onde mora:**

| Camada | Arquivo | O quê |
|---|---|---|
| Cálculo | `services/cronograma_fisico_financeiro.py` | `calcular_fluxo_caixa(..., fat_competencia)` + helper `_fat_competencia(obra)` (lê de `fluxo_caixa_planilha`); `painel_financeiro` expõe `config.fat_competencia` |
| API | `views/obras.py` | rota `POST /obras/<id>/financeiro/config` grava a opção por obra |
| UI | `templates/obras/detalhes_obra_profissional.html` + `static/js/financeiro_obra.js` | seletor "Abatimento do faturamento direto" na aba Financeiro |
| Teste | `tests/test_cronograma_fisico_financeiro.py` | `test_caixa_fat_mesma_competencia_abate_no_proprio_periodo` (cobre os dois modos) |

Padrão preservado: obras existentes não mudam (default `"seguinte"`). A Baia foi marcada
como `"mesma"` no JSON.

### 2. Cronograma físico atualizado pelo `CRONOGRAMA OFICIAL.mpp`

Fonte: **`CRONOGRAMA OFICIAL.mpp`** (MS Project, **57 tarefas**, agora com split
**BAIA 01 / BAIA 02**, fim em **08/10**). Substituiu o cronograma antigo (43 tarefas,
fim 11/09).

Fixture atualizada: `tests/fixtures/cronograma_fisico_financeiro_baias.json`

- `cronograma_tarefas` → espelho fiel das **56 tarefas** do .mpp (ids 1..56;
  descartado o wrapper "Projeto1" id 0).
- As **12 etapas de custo** da EAP foram **mantidas** (custos/`peso_pct` intactos,
  `Σ peso_pct = 0,9999`) e tiveram só o `tarefas_mpp` **remapeado por nome**, mais
  recálculo de `inicio` / `fim` / `pct_fisico`.
- Tarefas **FAZENDA** novas (nivelamento, drenagem) entram **só no físico** (sem custo),
  alocadas a **Indiretos** para faseamento.
- `data_fim_cronograma` corrigido para **08/10**; medições **preservadas** (cronograma
  de faturamento contratual não mudou); `_meta` atualizado.

**Mapa etapa → tarefas do novo .mpp** (decidido por significado):

| Etapa | %fís | tarefas_mpp (folhas do .mpp) |
|---|---|---|
| PRELIM | 83.3 | 3, 4, 5, 9 |
| FUND | 0 | 11, 12, 14, 15, 17, 18, 20, 21, 22, 23 |
| ESTMET | 0 | 30, 31, 32 |
| ESTLSF | 0 | 26, 27, 28 |
| COBERT | 0 | 33, 35 |
| FECHA | 0 | 40, 41, 42, 43, 44, 45 |
| PINT | 0 | 37, 38, 46, 47 |
| MOLEDO | 0 | 24, 48 |
| PORTAO | 0 | 53, 54 |
| ELET | 0 | 50, 51 |
| HIDRO | 0 | 13, 16 |
| INDIRETOS | 31.9 | 2, 6, 19, 34, 36, 55, 56 (inclui FAZENDA, só físico) |

> O acoplamento: `eap[].cronograma.tarefas_mpp` (ids) → busca em `cronograma_tarefas`
> → datas que faseiam o custo da etapa (alimenta Curva S e fluxo de caixa).

---

## Commits (já no `origin/main`)

- `6d70b66b` — feat: competência configurável do fat_direto + fixture da Baia atualizada
- `49b8db0a` — chore: adiciona `CRONOGRAMA OFICIAL.mpp` (add com `-f`; `*.mpp` é ignorado)

Repositório: `github.com/cassioviller/EnterpriseSync-1`.

---

## Pendências

1. **Reconciliar custos pela `Planilha1`** do `Planilha de Custos REV01 (2).xlsx`
   (ver topo). Atualizar `eap[].custo` e `fluxo_caixa_mensal` se os números mudaram.
2. **Rodar os testes** contra o JSON novo (bloqueado enquanto o Python estiver caído):
   ```
   python -m pytest tests/test_importacao_fisico_financeiro.py tests/test_painel_financeiro.py -q
   ```
3. **Revisar o mapa etapa→tarefas** acima (foi por julgamento de nome; conferir se algum
   item — ex.: basecoat em FECHA vs PINT, içamento de pilares em FUND — deve mudar de balde).
4. Reconferir se as **datas das medições** (M4 entrega 05/10, M5 retenção 20/11) seguem
   válidas com o novo fim de cronograma (08/10) — mantidas como estavam por decisão.

---

## Como o JSON é consumido (referência rápida)

- Importação: `services/importacao_fisico_financeiro.py`
  - `cronograma_tarefas` → `mpp = {t['id']: t}` (linha ~324)
  - cada etapa → `_materializar_cronograma_fisico` usa `cronograma.tarefas_mpp` para criar
    as tarefas-folha e pesar a medição por duração.
  - `obra.fluxo_caixa_planilha = payload['fluxo_caixa_mensal']` (daí saem `imposto_pct` e
    `fat_competencia` por obra).
- Painel ao vivo: `painel_financeiro(obra)` recalcula tudo do cronograma + custos
  (o `fluxo_caixa_mensal` verbatim só alimenta o comparativo de divergência).
