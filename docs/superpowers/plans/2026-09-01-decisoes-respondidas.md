# Decisões respondidas — 2026-09-01

> **O que é:** a resposta às 13 perguntas abertas levantadas na varredura de
> 01/09. Substitui, para efeito de execução, o *estado de espera* de
> `2026-08-31-decisoes-pendentes.md` — que continua válido como enunciado das
> três primeiras.
>
> **Método:** cada resposta é medida contra a árvore e o banco de
> desenvolvimento de hoje, ou pesquisada fora quando o fato é externo. Marcas:
> 🔬 medido · 📖 lido no código (`arquivo:linha`) · 🌐 fonte externa · ⚖️ juízo,
> com o critério declarado.
>
> ⚠️ **Onde a decisão é de negócio, dinheiro ou pessoa, a recomendação está
> marcada `RATIFICAR` — ela é executável, mas o dono do repositório é quem
> assina.**

---

## D6 — o de-para do plano de contas

**Resposta: (a), mas corrigida — chavear pela ASSINATURA ESTRUTURAL, não por
`(código, nome)`. E a premissa da pergunta está incompleta.**

🔴 **A pergunta assume dois seeders. São pelo menos quatro** — e o próprio
código já dizia isso: 📖 `contabilidade_utils.py:514` — *"O sistema tem QUATRO
planos de contas concorrentes"*. O enunciado da D6 herdou um recorte de dois.

🔬 Medido no banco de dev (7.287 tenants com plano de contas):

| Forma | nº de contas | tenants | Origem |
|---|---:|---:|---|
| grupo 6 só, sem grupo 5 | 35 | 6.941 | 📖 `scripts/seed_demo_alfa.py:3484` |
| com `5.1.01.%` (filhos nível 4) | 39 | 95 | 📖 `financeiro_seeds.py:10` |
| com `5.2.01.001` | 45 | 86 | variante não identificada |
| fragmentos | 5 / 2 / 1 | 165 | parciais |

🔬 **Os 95 têm as duas assinaturas ao mesmo tempo** — grupo 6 *e* `5.1.01.%`.
Dois seeders rodaram no mesmo tenant. 🔬 **71 não casam com nenhuma.**

**Por que (a) funciona sem violar a spec:** a proibição da spec é sobre usar
`nome`. Os seeders divergem no **conjunto de códigos**, que a spec não proíbe —
e que é evidência mais forte que o nome, porque nome é editável pela tela e
código é chave primária. Discriminadores que nunca leem `nome`:

| Sinal | Prova |
|---|---|
| existe `6` | seeder `contabilidade_utils` (F não tem grupo 6) |
| existe `5.1.01.%` | seeder `financeiro_seeds` (C não tem filhos nível 4 sob `5.1.01`) |
| `2.1.03.001–003` × `2.1.03.007–009` | mutuamente exclusivos entre F e C |
| `4.1.01.%` × `4.1.02.%` | mutuamente exclusivos entre F e C |
| `aceita_lancamento` de `5.1.01` | **True** em C (é conta folha) · **False** em F (é sintética) |

🔬 **O de-risking que muda o tamanho do problema:** em F, `5.1.01` e `5.1.02`
são **sintéticas** (`aceita_lancamento=False`) — lançamento nenhum pode pousar
nelas. Se isso se confirmar em produção, **a colisão é vazia para partidas
contábeis**: todo lançamento em `5.1.01` veio de C, e os de F estão nos filhos
`5.1.01.00x`. Medir isso é a primeira coisa a fazer, e pode encolher a Task 4
de "de-para de centenas de linhas" para "de-para de duas contas sintéticas".

**(b) está descartada** — é a única saída que corrompe dado, e o volume medido
mostra por quê: aplicaria o significado errado a uma população que nem sequer é
a majoritária.

**(c) está descartada** — adiar mantém quatro significados vivos, não dois.

**O que executar:** de-para chaveado por assinatura estrutural, com **falha
fechada e nomeada** para qualquer tenant cuja assinatura não seja uma das
conhecidas — os 71 indeterminados de dev são a prova de que esse ramo vai ser
exercitado.

---

## FASE8-T1 — medir o plano de contas em produção

**Resposta: continua sem poder ser respondida daqui — não há acesso ao banco de
produção. Mas o que trava mudou de forma.**

⚖️ A medição que a Fase 8 pede (`5.x` residual ou dominante?) é a pergunta
errada agora. 🔬 Em dev, a forma dominante **não tem grupo 5 nenhum** (6.941 de
7.287 tenants) — é o seeder de demo. A pergunta que a produção precisa
responder é mais ampla:

1. Quantas **assinaturas estruturais distintas** existem (não quantos `5.x`)?
2. Existe partida contábil pousada em `5.1.01` ou `5.1.02` **diretamente**? Se
   não existir, a colisão é vazia e a Task 4 encolhe.
3. Quantos tenants não casam com nenhuma assinatura conhecida?

**O que executar:** rodar `scripts/medir_producao.py` — que a Task 1 da Fase 8
ainda precisa escrever — contra uma **réplica ou dump de produção**, somente
leitura, com as três perguntas acima acrescentadas à `q8_planos_de_contas`.
Enquanto isso não acontece, a Fase 8 fica parada **na Task 4**, não na Task 1:
as Tasks 1–3 são executáveis.

`RATIFICAR`: só o dono consegue o acesso ao banco. É o único item desta lista
que nenhuma quantidade de trabalho técnico destrava.

---

## VIGA-I — verba/lucro do telhado viga I

**Resposta: opção B (markup uniforme). E a opção C deve ser declarada morta.**

⚖️ **Critério: qual das duas preserva o instrumento de medição.** A Espinha
Financeira existe para medir **resultado por atividade**. A opção A ("reduzir
margens dos demais proporcionalmente") faz o ajuste ser absorvido item a item —
ou seja, muda a margem de itens que ninguém tocou, para acomodar um item novo.
Depois disso, "a margem do item X" deixa de significar o que significava, e a
própria medida que o plano entrega fica contaminada na origem. A opção B move
**um único parâmetro declarado** (`orcamento.margem_pct_global`) até a venda
total voltar a R$ 1.720.796,75: é reversível, auditável em uma linha, e
mantém as margens relativas entre itens comparáveis antes e depois.

**Opção C: descartar por escrito.** 🔬 Ela é citada em quatro documentos e
definida em nenhum; o arquivo que a definiria
(`ESPACO_telhado_viga_i_baia_rev10.md`) nunca existiu na árvore. Uma opção que
sobreviveu meses sem definição não é uma opção — é uma nota de rodapé que
trava um plano.

`RATIFICAR` — é uma escolha comercial. A recomendação acima é sobre
mensurabilidade, não sobre qual dá o melhor número para o cliente.

⚠️ Lembrete: isto trava **só a Task 8 de 10** do Resgate da Espinha. As outras
nove entram sem esta decisão.

---

## A04 — conta de débito da despesa geral

**Resposta: criar uma conta analítica NOVA e inequívoca, em vez de reaproveitar
um código ambíguo.**

📖 O impasse tem causa medida: `6.1.02` é "DESPESAS GERAIS" no seed V2, mas
`6.1.02.001` é "Despesa com Combustível" num plano e "Material de Escritório"
noutro; `6.1.02.003` é "Despesa com Material" num e "Energia Elétrica" noutro.
Foi exatamente por isso que 📖 `contabilidade_utils.py:545` deixou o subgrupo
**deliberadamente fora** da classificação do DRE.

Reaproveitar qualquer `6.1.02.00x` existente para `despesa_geral` escolheria um
dos dois significados sem saber qual o tenant usa — o mesmo erro da opção (b)
da D6, em escala menor.

**O que executar:** acrescentar ao `_V2_CONTAS_SEED` uma analítica própria sob
`6.1.02` num código que **nenhum** dos planos concorrentes usa, e então:

```python
MAPEAMENTO_CONTABIL['despesa_geral'] = {'debito': <novo>, 'credito': '2.1.01.001'}
```

Enquanto a Fase 8 não unificar, o valor segue aparecendo no DRE pelo residual,
rotulado "outras" — honestamente não classificado, que é a regra que o próprio
módulo já adota.

`RATIFICAR` com o contador: **o nome e a natureza da conta**, não o encanamento.
A pergunta que vale a pena levar a ele é estreita — *"despesa geral de obra
entra como despesa operacional (grupo 6) ou como custo do serviço prestado
(grupo 5)?"* — e a resposta muda uma linha.

---

## A18 — Decisão 4: recalcular ou congelar `MedicaoObra` históricas

**Resposta: congelar as históricas. Unificar só da vigência em diante.**

⚖️ **Critério: o número já saiu da casa.** 📖 `portal_obras_views.py:768`
multiplica o percentual por `valor_contrato` — medição é documento que o
cliente viu. Recalcular reescreve realidade já comunicada, e a divergência não
se anuncia: as duas fórmulas (`utils/cronograma_engine.py:1074-1095` pondera
por `duracao_dias`; `services/medicao_service.py:48-65` pondera por `peso`)
divergem **por construção**, então o recálculo produziria números novos para
períodos fechados sem que ninguém soubesse quais mudaram.

**O que executar:** congelar com marcador de versão de cálculo na `MedicaoObra`
(qual fórmula gerou aquela linha), e a rota do portal passa a delegar a
`gerar_medicao_quinzenal` para as novas.

**Independente da decisão, dois consertos entram já** — são elo, não
convergência, e nenhum move dinheiro:
- 📖 `views/rdo.py:3190-3200`/`:3251` gravar `subatividade_mestre_id` (sem isso
  o RDO da rota legada nasce sem elo e a derivação cai em `'linha'` em silêncio);
- 🔴 📖 `views/obras.py:744-756` — SQL cru **sem filtro de `admin_id`**.

`RATIFICAR`: congelar é escolha de negócio (aceitar que o histórico não é
comparável ao novo). A alternativa honesta seria recalcular **e avisar o
cliente**, o que é bem mais caro.

---

## A24 — ligar o rateio dos encargos patronais

**Resposta: ligar, por tenant, com reconciliação antes — e sem reescrever mês
fechado.**

🔬 Confirmado hoje: `processar_e_salvar_folha_obra`, `_folha_rateada_para_obra`
e `_ratear_valor_por_obra` têm **zero chamadores de produção** — só
`tests/test_onda3_folha.py`. O pipeline está escrito, testado e desligado.

⚖️ Mão de obra ~28% subestimada não é um relatório feio: é o custo de obra
errado para baixo, o que infla resultado por atividade, margem e a base de
qualquer decisão de preço. É o item de maior distorção silenciosa da lista.

**O que executar:** ligar atrás de flag por tenant → rodar para **um** tenant e
**um** mês → reconciliar contra o número atual e explicar a diferença → só
então avançar. Meses já fechados **não** são reprocessados (mesmo critério da
A18: número que já saiu não se reescreve em silêncio).

`RATIFICAR`: o custo de obra vai subir ~28% na mão de obra a partir da
vigência. Quem lê o resultado precisa saber disso **antes**, ou vai achar que
piorou a operação.

---

## A25 — `N8N_WEBHOOK_URL` e o agendamento

**Resposta: definir a variável, e agendar por cron EXTERNO — não por
APScheduler no processo web.**

🔬 A infra já existe inteira: 📖 `app.py:434` (despachante, no-op sem a
variável), `notificacoes_cli.py` (o comando), 📖 `app.py:1041` (o job diário) e
📖 `app.py:1054` (o gate `SCHEDULER_ENABLED`). **Falta só a credencial.**

⚖️ Por que cron externo: 📖 o comentário do próprio `app.py:1056` admite que a
proteção contra multi-worker é **manual** — *"Defina `SCHEDULER_ENABLED=0` em
todos os workers exceto um"*. Hoje o gunicorn roda com 1 worker e funciona; no
dia em que alguém puser `-w 2` para aguentar carga, **todo job passa a rodar
duas vezes**, e notificação duplicada não dá erro — dá spam no cliente. Um cron
do EasyPanel chamando o CLI não tem esse modo de falha, e o CLI já existe.

`RATIFICAR`: só o dono tem a URL do n8n.

---

## Fase 0.5 — backup agendado

**Resposta: job do EasyPanel. Confirma a recomendação que já estava escrita.**

⚖️ Mesmo argumento da A25, e mais grave: um backup que roda N vezes por causa
de N workers, ou **zero** vezes porque o worker que o tinha morreu, é um backup
em que ninguém pode confiar. Agendador tem de viver fora do processo que serve
requisição.

---

## `/health/veiculos`

**Resposta: manter. A ausência de referência no repositório não é evidência de
ausência de monitor.**

🔬 A única referência é 📖 `views/dashboard.py:29`, que aponta para ela mesma.
Mas o consumidor de um endpoint de health é, por definição, **externo ao
repositório** — um monitor, um healthcheck de container, um uptime robot. O
custo de manter é uma rota; o custo de remover errado é perder o alarme sem
saber.

**O que executar antes de decidir:** olhar a configuração de healthcheck do
EasyPanel. Se nada aponta para lá, aí sim remover é seguro.

---

## `opencv-python` × `headless` / reconhecimento facial

**Resposta: a decisão de produto ("manter reconhecimento facial?") não precisa
ser tomada — o conflito tem conserto técnico que a torna irrelevante.**

🔬 **O conflito não é teórico, está vivo:** as duas distribuições estão
instaladas ao mesmo tempo, escrevendo o mesmo pacote `cv2` —
`opencv_python-4.11.0.86` **e** `opencv_python_headless-4.13.0.90`. 🔬 A causa é
transitiva e exata: `deepface-0.0.97` e `retina_face-0.0.17` declaram
`Requires-Dist: opencv-python`, não a headless.

🔬 **O que o app realmente usa do DeepFace é um modelo só: o SFace**
(📖 `ponto_views.py:80` — `DeepFace.build_model('SFace')`). E **o OpenCV traz
SFace nativo**: `cv2.FaceRecognizerSF` — 🔬 confirmado presente na 4.11
instalada, junto com `cv2.FaceDetectorYN`.

**O que executar:** trocar `DeepFace.build_model('SFace')` por
`cv2.FaceRecognizerSF`, e remover `deepface` + `retina-face`. Isso:
- elimina a **causa** do conflito (some quem exige `opencv-python`);
- 🔬 remove **1,8 GB de TensorFlow** do deploy, mais ~91 MB de libs duplicadas;
- mantém o recurso de pé — nenhuma decisão de produto precisa ser tomada.

⚠️ **Ressalva honesta:** os *embeddings* já cacheados precisam ser
regenerados — o caminho existe (`gerar_cache_facial.py`), mas é migração de
dado, não troca de import, e precisa de RED próprio comparando embeddings
antigo × novo antes de invalidar o cache.

**Paliativo, se a troca não couber agora:** 🌐 `[tool.uv] override-dependencies`
substitui a dependência transitiva. Não há solução documentada pela uv para
*renomear* `opencv-python` → headless (a issue está aberta e sem resposta de
mantenedor), então o paliativo é frágil e a troca do SFace é o conserto de
verdade.

---

## Miniatura do portal × migração de fotos

**Resposta: seguir a migração e aceitar o portal sem miniatura no intervalo.**

⚖️ A alternativa é ordenar a Fase 9a antes — e a 9a é 🔬 o plano **menos
urgente e mais desatualizado** da lista (escrito sobre o schema anterior às
Fases 1–5, com seção própria de premissas a reconfirmar). Trocar a ordem para
salvar uma miniatura é deixar a decisão de arquitetura ser tomada por um
detalhe de interface. Degradação visível e reversível é preferível a bloqueio.

---

## FUNCIONARIO sem `admin_id`

**Resposta: falhar fechado. O canônico devolve `None`; a resolução por FK sai.**

⚖️ 📖 `utils/tenant.py` já declara a regra no docstring — *"FALHA SEGURA:
Retorna None se dados inconsistentes"* — e 📖 `ensure_tenant_isolation` já faz
`abort(403)` quando não há tenant. Resolver por FK em `crud_rdo_completo` é
**um caminho que contorna a política do módulo que existe para ter uma
política.** Um funcionário sem `admin_id` é defeito de dado; resolver por FK
transforma o defeito em comportamento normal e ele nunca é consertado.

**O que executar:** canônico devolve `None`, e uma **medição** (não uma
correção) que reporte quantos usuários estão nesse estado — 🔬 em dev são 263
não-admins com `admin_id` NULL, mas dev é resíduo de suíte; produção é que
decide o tamanho do reparo de dado.

`RATIFICAR`: falhar fechado pode tirar do ar um funcionário que hoje consegue
usar o sistema. É melhor que ele saiba disso do que gravar no tenant errado —
mas é uma escolha de produto, e alguém vai ligar reclamando.

---

## As 18 rotas restantes de `views/vehicles.py`

**Resposta: apagar, pelo mesmo procedimento das seis (D3).**

🔬 São 18 rotas registradas em `main_bp`, mortas pela interface: os templates
postam para `frota.*` e `/veiculos` redireciona para `frota.lista`. Rota
alcançável por URL e não exercitada por ninguém é superfície sem guarda e sem
teste — foi assim que as seis já removidas passaram meses quebrando na primeira
requisição sem ninguém notar.

**O que executar:** o mesmo roteiro da Task 3 do plano de 31/08 — provar que
nada em template ou JS as referencia, teste que prova 404 nas URLs, apagar,
verde, commit. ⚠️ E rodar a suíte **com browser**, porque
📖 `tests/test_browser_all_modules.py:647` exercita `/veiculos/relatorios`.

**Se houver dúvida:** devolver 410 por uma versão antes de apagar. Custa um
release e elimina o risco de descobrir um consumidor externo pelo suporte.

---

## Manual padrão do RDO — Alan e Abel

**Resposta: não é minha para decidir. Mas a forma como está enunciada garante
que ela nunca feche.**

⚖️ "Falta duas pessoas lerem" não é estado de trabalho — não tem dono, prazo
nem critério de pronto, e por isso atravessou de 20/08 até aqui sem se mover.

**O que executar:** marcar uma data. Se a data passar sem a leitura, o capítulo
23a entra como **recomendação do escritório**, com essa qualificação escrita no
próprio documento — em vez de ficar parado esperando virar cobrança. As duas
saídas são aceitáveis; ficar em espera indefinida não é.

---

## `psycopg2-binary` → compilado

**Resposta: não fazer agora. Registrar e deixar para quando houver build de
produção próprio.**

🌐 A recomendação oficial do psycopg é que a distribuição binária traz as
próprias `libpq`/`libssl`, então **atualizar as bibliotecas do sistema não
atualiza as que o driver usa** — é um ponto cego de correção de segurança, não
um problema de funcionamento. E a direção de 2026 não é "compilar o psycopg2":
é migrar para **psycopg 3** (`psycopg[c]`), que o SQLAlchemy 2.0 já suporta com
dialeto próprio.

⚖️ Nenhuma das duas cabe neste backlog: não desbloqueiam nada, e a migração
para psycopg3 é projeto com risco próprio. O que **não** se deve fazer é a meia
medida de compilar o psycopg2 agora e migrar depois.

---

## Fontes externas

- [uv — Settings (`override-dependencies`)](https://docs.astral.sh/uv/reference/settings/)
- [uv issue #14220 — Replace transitive dependencies? `opencv-python` → `opencv-python-headless`](https://github.com/astral-sh/uv/issues/14220) (aberta, sem solução de mantenedor)
- [Psycopg 2 — Installation (por que a binária não é para produção)](https://www.psycopg.org/docs/install.html)
- [psycopg2-binary — PyPI](https://pypi.org/project/psycopg2-binary/)
