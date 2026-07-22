# Fase 3 — Compras com Governança (requisição → aprovação → pedido de compra)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao módulo de compras um documento de demanda (`RequisicaoCompra`), uma cadeia de aprovação com alçada configurável por tenant e um histórico auditável de quem aprovou o quê e por quanto — de modo que nenhum pedido de compra nasça sem uma aprovação registrada, e nenhum custo de obra apareça sem obra.

**Architecture:** O módulo de compras de hoje é um **registro a posteriori**: `compras_views.py:709-711` cria o `PedidoCompra`, os `GestaoCustoPai`, os `ContaPagar` e os movimentos de almoxarifado **no mesmo request** do formulário. A Fase 3 não reescreve isso — ela coloca um documento **antes**: a `RequisicaoCompra`, que nasce em RASCUNHO, sobe para AGUARDANDO_APROVACAO, coleta N aprovações conforme a faixa de alçada do valor, e só então pode ser convertida em `PedidoCompra` (que continua fazendo exatamente o que faz hoje). A máquina de estados segue o padrão que a Fase 2 estabelece para a Obra (enum + tabela de transição + um único chokepoint que valida). O papel `PapelObra.COMPRADOR` nasce aqui porque aqui existem verbos para ele: criar requisição e emitir pedido. E a separação de funções é o invariante duro da fase: **quem solicita não aprova; quem aprova não emite**.

**Tech Stack:** Flask 3 + Flask-Login, SQLAlchemy 2 (`models.py`), sistema de migrações próprio numerado (`migrations.py`, faixa reservada 240–249), Bootstrap 5 (`templates/base_completo.html`), pytest + PostgreSQL (`run_tests.sh --gate`).

---

## Contexto verificado no código (leia antes de começar)

Tudo abaixo foi conferido em 2026-07-21 no commit `fb4147b`, arquivo a arquivo. Não são suposições, e várias delas **corrigem** documentos anteriores.

| Fato | Evidência |
|---|---|
| `PedidoCompra` é registro *a posteriori* de NF/recibo, não um PO. `numero` é o número da NF, texto livre | `models.py:4727-4732` |
| `PedidoCompra.obra_id` é **nullable** — compra sem obra some do custo da obra | `models.py:4736` |
| A etapa (`obra_servico_custo_id`) já existe e já é opcional; entrou pela migration 205 | `models.py:4740-4741`; `migrations.py:13769-13782`; registro em `migrations.py:4006` |
| Compras parceladas (`responsavel_id`, `data_vencimento_primeira_parcela`, `intervalo_parcelas_dias`) já existem — migration 167 | `models.py:4763-4766`; registro em `migrations.py:3972` |
| A compra é **efetivada no mesmo request**: `processar_compra_normal` cria GCP + ContaPagar + entrada/saída de almoxarifado e commita | `compras_views.py:709-711`, chamando `compras_views.py:162-272` |
| O `obra_id` é lido com `or None` — salvar sem obra é o caminho feliz, não um erro | `compras_views.py:582` |
| Todas as 8 rotas de `compras_views.py` são `@login_required` **puro** — sem papel, sem escopo de obra | `compras_views.py:409,451,500,532,770,842,955,1024` |
| A listagem filtra só por tenant, nunca por obra | `compras_views.py:421` |
| **Não existe** nenhuma `Requisicao`. `grep -rni "requisic" --include=*.py --include=*.html .` devolve **zero** ocorrências | verificado em 2026-07-21 |
| **Não existe** nenhuma alçada. `grep -rni "alcada\|alçada"` só casa `'calcada'` em listas de palavras-chave de cronograma | `services/cronograma_normalizacao.py:69`; `scripts/rebuild_baia_from_0607_mpp.py:36` |
| `GestaoCustoPai` **não tem** coluna `obra_id` — a obra vive em `entidade_id`, um inteiro sem FK | `models.py:5224-5243` (nenhuma coluna de obra); comparar com `GestaoCustoFilho.obra_id` em `models.py:5302` |
| O módulo inteiro de compras é V2-only: toda rota chama `_check_v2()`, que depende de `versao_sistema == 'v2'` | `compras_views.py:36-40`; `utils/tenant.py:63-83` |
| O menu de Compras também é V2-only e não olha papel nenhum | `templates/base_completo.html:953` (`{% if is_v2_active() %}`) |
| `views/almoxarifado/*.py` roda com `@login_required` puro nas 6 famílias de rota | `views/almoxarifado/dashboard.py:15`, `fornecedores.py:15,44,140,243,267,313,353`, `itens.py:15,77,135`, `categorias.py:14,27,68,107`, `movimentos.py`, `api.py:22,57,98,152`, `relatorios.py:16` |
| `TipoUsuario.ALMOXARIFE` continua **existindo no enum** depois da Fase 1 — ela remove só os helpers de `auth.py:70-99`, não o valor | `models.py:25`; Fase 1 Task 10, passo 5 |
| Maior migration registrada hoje é a **213**. Fase 1 usa 214-216; Fase 2 vem depois; **a faixa desta fase é 240-249** | `migrations.py:4014` |
| `db.create_all()` roda **antes** de `executar_migracoes()` no boot | `app.py:582` vs `app.py:666-667` |
| O repositório **nunca** estendeu um enum nativo do Postgres: `grep -rn "ALTER TYPE\|ADD VALUE" migrations.py` devolve zero | verificado em 2026-07-21 — ver Task 4, que é a primeira vez |
| `run_tests.sh --gate` é `pytest tests/ -m "not browser"` | `run_tests.sh:36` |
| Marcadores de pytest são estritos (`--strict-markers`); `integration` existe | `pyproject.toml:76-82` |
| Login em teste é injeção de sessão, não POST em `/login` | `tests/test_fase0_autorizacao.py:53-59` |
| `Cliente` só precisa de `nome` + `admin_id`; `Obra.cliente_id` é NOT NULL | `models.py:2703-2711`; `models.py:265-268` |

### Correções a documentos anteriores

Duas afirmações que circulam nos documentos do repositório **não se sustentam no código** e foram reconferidas:

1. **`DEVOLUTIVA.md:73` diz que "não existe recebimento".** Existe. A rota `POST /compras/receber/<pedido_id>` está viva em `compras_views.py:841-948`, tem botão renderizado em `templates/compras/detalhe.html:24`, agrega quantidades já recebidas por item (`compras_views.py:861-870`) e é idempotente por diferença (`compras_views.py:893-896`). O que ela **não** faz é gerar obrigação financeira — o financeiro já nasceu lá atrás, no `processar_compra_normal`. Portanto: **recebimento parcial de material existe e não será refeito nesta fase**; o que falta é recebimento como *gatilho* financeiro, e isso é Fase 4/8, não aqui.

2. **`ESTADO-ATUAL.md:52-54` sugere que a Fase 3 é greenfield.** Não é. Mapa de concorrência V1 e V2, cotação por item×fornecedor, seleção de fornecedor, PDF versionado do mapa, compra parcelada, apropriação por etapa e recebimento parcial já existem e ficam como estão. O que falta é exclusivamente o **fluxo de decisão** antes da compra.

### O que já existe no módulo de compras e NÃO será refeito

| Ativo | Onde | Papel na Fase 3 |
|---|---|---|
| `PedidoCompra` + `PedidoCompraItem` | `models.py:4727-4792` | Continuam sendo o documento de compra. Ganham só `requisicao_id` |
| `processar_compra_normal` (GCP + ContaPagar por parcela + entrada/saída almox) | `compras_views.py:162-272` | Intocado. Passa a ser chamado **a partir** da requisição aprovada |
| `processar_compra_aprovada_cliente` (FATURAMENTO_DIRETO, idempotente) | `compras_views.py:275-371` | Intocado no cálculo; muda **quem** o dispara (Task 11) |
| `_vencimentos` (à vista / 30-60-90 / parcelado com data e intervalo) | `compras_views.py:374-402` | Intocado |
| `_gerar_entrada_almoxarifado` / `_gerar_saida_almoxarifado` | `compras_views.py:80-159` | Intocados |
| Recebimento parcial por item | `compras_views.py:841-948` | Intocado |
| `MapaConcorrenciaV2` + `MapaFornecedor` + `MapaItemCotacao` + `MapaCotacao` | `models.py:5599-5685` | Ganham um vínculo **opcional** com a requisição; a matriz não muda |
| `RelatorioCompraMapa` (PDF versionado do mapa) | `models.py:5687-5720` | Intocado |
| Telas de mapa V1/V2 | `views/obras.py:2769,2843,3043,3130` | Intocadas |
| `MapaConcorrencia` V1 + `OpcaoConcorrencia` | `models.py:5512-5545` | Intocados (legado; ver "o que esta fase NÃO fez") |
| Edição de lançamento financeiro de compra | `compras_views.py:954-1017` | Intocada |
| Templates `compras/index|nova_compra|detalhe|aprovacao.html` | `templates/compras/` | Intocados; a fase acrescenta 3 templates novos |

---

## Achados de segurança do portal por token (não suavizados)

O portal do cliente é um **sistema de identidade paralelo**. O token é `Obra.token_cliente`, `db.String(255), unique=True` (`models.py:261`) — **sem coluna de expiração, sem escopo de ação, sem revogação individual, sem contador de uso**. Quem tem a URL tem tudo o que a URL permite, para sempre. As cinco rotas POST abaixo mutam estado sem nenhuma autenticação:

| # | Rota | Linha | O que muta | Gravidade |
|---|---|---|---|---|
| 1 | `POST /portal/obra/<token>/compra/<id>/aprovar` | `portal_obras_views.py:343-374` | Grava `status_aprovacao_cliente='APROVADO'` e, se `tipo_compra=='aprovacao_cliente'`, **chama `processar_compra_aprovada_cliente`** (`:361`), que cria `GestaoCustoPai` PAGO, `GestaoCustoFilho`, entrada e saída de almoxarifado | **Crítica** — POST anônimo cria lançamento financeiro |
| 2 | `POST /portal/obra/<token>/compra/<id>/recusar` | `portal_obras_views.py:377-385` | Grava `RECUSADO` sem nenhuma guarda de estado, sem motivo, sem trilha | Alta |
| 3 | `POST /portal/obra/<token>/compra/<id>/comprovante` | `portal_obras_views.py:388-429` | **Upload de arquivo** anônimo para o disco do servidor (`:418`) | Alta |
| 4 | `POST /portal/obra/<token>/mapa/<id>/aprovar` | `portal_obras_views.py:432-468` | Escolhe fornecedor e fecha o mapa V1 (`:457-458`) | Média |
| 5 | `POST /portal/obra/<token>/mapa-v2/<id>/selecionar` | `portal_obras_views.py:546-615` | Escolhe fornecedor de N itens e fecha o mapa V2 (`:592-603`) | Média |

Três agravantes que também confirmei:

- **A rota 1 não checa `tipo_compra`.** `portal_obras_views.py:354` grava `APROVADO` em *qualquer* `PedidoCompra` da obra, inclusive nos de `tipo_compra='normal'`, que nunca deveriam passar pelo cliente. O único filtro é `obra_id` (`:346`).
- **O usuário registrado no movimento de estoque é o admin do tenant**, porque "o portal é anônimo" (`portal_obras_views.py:360-361`). Ou seja: a trilha de auditoria do almoxarifado atribui ao admin uma ação que ele não fez.
- **`portal_ativo` nasce `True`** (`models.py:272`). O token só é gerado no `toggle_portal` (`portal_obras_views.py:480-481`), então na prática o portal só abre depois de dois cliques — mas o default do modelo é "aberto", não "fechado".

### Decisão desta fase sobre o portal — conviver, com o dente arrancado

**Não substituo o token por login nesta fase** (isso é a Fase 9a, junto da assinatura de medição, e exige cadastro e recuperação de senha para o cliente — decisão de produto, não de compras). **Mas retiro do token o poder de criar lançamento financeiro.** Concretamente:

1. **Correções incondicionais** (Task 10, valem com ou sem flag, porque são falha de segurança, não mudança de fluxo): a rota 1 passa a recusar compra que não seja `tipo_compra='aprovacao_cliente'`; o token ganha `expira_em` com verificação em `_get_obra_by_token`; as cinco rotas passam a gravar IP e user-agent numa trilha (`PortalAcessoEvento`).
2. **Mudança de fluxo sob flag** (Task 11): com `compras_governanca_ativa` ligada, a aprovação do cliente registra **ciência**, não custo. O custo passa a nascer da cadeia interna de alçada. O POST anônimo deixa de ser um gatilho financeiro e vira um dado de entrada.

O motivo de não simplesmente apagar as rotas: elas são o fluxo de *faturamento direto* real da empresa (cliente paga o fornecedor). Apagá-las sem substituto tira uma capacidade em uso. O motivo de não deixá-las como estão: **um POST sem autenticação que cria `GestaoCustoPai` com `status='PAGO'` é um caminho de fraude, não uma comodidade.**

---

## Decisões de projeto desta fase

1. **A requisição é o documento; o pedido continua sendo o pedido.** Não transformo `PedidoCompra` em PO com máquina de estados própria. Ele já tem seis responsabilidades e 300 linhas de processamento acopladas. A governança mora na `RequisicaoCompra`, que é nova e limpa; o `PedidoCompra` só ganha uma FK de origem.
2. **`obra_id` é NOT NULL na requisição — desde o primeiro dia.** É tabela nova, não há órfão para migrar. O `PedidoCompra.obra_id` continua nullable (isso é Fase 4, e é caro); mas todo pedido **emitido a partir de requisição** herda obra obrigatória. A Fase 4 encontra o terreno preparado.
3. **A etapa (`obra_servico_custo_id`) é opcional na requisição e herdada pelo pedido.** Espelha exatamente o que a migration 205 fez em `pedido_compra` (`migrations.py:13769`). Quando existe, o custo cai no Realizado daquela etapa; quando não existe, cai na obra.
4. **Alçada é dado, não código.** Faixas ficam em `faixa_alcada`, por tenant, editáveis. O motor lê a tabela. Nenhum número em `if valor > 5000`.
5. **Separação de funções é invariante, não configuração.** `solicitante_id != aprovador_id` sempre, inclusive para ADMIN. E quem emite o pedido não pode ser um dos aprovadores quando a faixa exige duas aprovações. Isso é o que faz a governança valer alguma coisa numa empresa pequena, onde a mesma pessoa acumula papéis.
6. **A máquina de estados copia o padrão da Fase 2, não inventa outro.** Enum + tabela `*Transicao` + um único `transicionar()` que valida contra um dicionário de transições permitidas. Ver "Dependências" abaixo — a Task 2 começa procurando o helper da Fase 2.
7. **Rollout atrás de flag por tenant, desligada por padrão** (`configuracao_empresa.compras_governanca_ativa`), espelhando `cronograma_mpp_ativo` (`models.py:3620`) e `escopo_obra_ativo` (Fase 1). Com a flag desligada, `compras.nova_post` continua funcionando exatamente como hoje e as telas de requisição existem como caminho opcional. Com a flag ligada, pedido sem requisição aprovada é recusado.
8. **`PapelObra.COMPRADOR` nasce com dois verbos**: criar requisição e emitir pedido. A Fase 1 deliberadamente não o criou porque seria "permissão sem verbo" (Fase 1, Task 5, docstring do enum). Agora há verbo.
9. **O mapa de concorrência pendura na requisição por FK opcional, não por reparentagem.** `RequisicaoCompra.mapa_v2_id` nullable. Os mapas existentes continuam pendurados na obra e continuam funcionando. Faixas de alçada altas podem **exigir** o mapa (`exige_mapa_concorrencia`), e aí a exigência é verificada na aprovação.
10. **O almoxarifado continua com `@login_required` puro nesta fase.** Ele lê e movimenta estoque, não decide compra. Amarrá-lo ao `COMPRADOR` agora significaria trancar 20 rotas por um papel que ninguém tem ainda. Fica registrado no fecho como dívida explícita, com o papel já existindo para consumo futuro.

### Dependências declaradas

- **Fase 1 é pré-requisito.** Esta fase importa `funcionario_do_usuario()` de `utils/identidade.py` e `obras_visiveis()`, `pode_ver_obra()`, `pode_editar_obra()`, `papel_na_obra()` e `obra_required(papel_minimo=None)` de `utils/autorizacao.py`, mais os símbolos `PapelObra` e `UsuarioObra` de `models.py`. Se algum não existir, **pare e execute a Fase 1 antes.**
- **Fase 2 é pré-requisito de padrão, não de símbolo.** Ela cria a máquina de estados da Obra com histórico de transição. **Não assumo nome de estado nem de função dela.** A Task 2 começa com um passo de reconhecimento: se a Fase 2 tiver deixado um helper genérico (procure por `utils/maquina_estados.py`, `transicionar`, `TRANSICOES_VALIDAS`), a `RequisicaoCompra` **usa esse helper** em vez da cópia local descrita aqui — e o passo diz exatamente o que trocar.

---

## Decisões que precisam do Cássio

Nenhuma delas bloqueia o plano. Todas seguem com a recomendação adotada, marcada `Recomendado:` e implementada como **seed de dados editável**, não como constante de código.

### D1 — Valores de alçada (R$) e número de aprovações

Pergunta 3 da `DEVOLUTIVA.md:293-295` ("qual o valor de X? A dupla aprovação é por valor absoluto, por % do orçamento da obra, ou por categoria?") continua **sem resposta**. Não invento número como se fosse fato.

**Recomendado:** três faixas por valor absoluto da requisição, semeadas por tenant pela migration 243 e editáveis depois:

| Faixa | Valor | Aprovações necessárias | Quem | Exige mapa? |
|---|---|---|---|---|
| 1 | até **R$ 5.000,00** | 1 | GESTOR da obra (ou ADMIN) | não |
| 2 | de R$ 5.000,01 a **R$ 30.000,00** | 2 | GESTOR da obra **e** ADMIN do tenant | não |
| 3 | acima de R$ 30.000,00 | 2 | GESTOR da obra **e** ADMIN do tenant | **sim** — mapa V2 concluído com ≥ 2 fornecedores |

Por que valor absoluto e não % do orçamento da obra: o % exige que `Obra.orcamento` esteja preenchido e correto, e ele é `db.Float, default=0.0` (`models.py:253`) — com orçamento zerado, qualquer compra viraria "100% do orçamento" e cairia na faixa mais alta. Valor absoluto degrada bem; percentual degrada para o pior caso.

### D2 — O que acontece com o fluxo de aprovação do cliente no portal

**Recomendado:** conviver, com o poder financeiro removido (ver a seção do portal, acima). A aprovação do cliente passa a ser **ciência registrada**, e a emissão do custo passa a exigir a cadeia interna. Se o Cássio disser que o cliente é quem manda e a cadeia interna é burocracia, a alternativa é marcar a faixa de alçada dessas compras como "1 aprovação, papel COMPRADOR" — continua havendo trilha, com atrito quase zero.

### D3 — Migrar o token do portal para login de cliente

**Recomendado:** **não nesta fase.** Aqui o token ganha expiração e trilha de IP; a troca por login é a Fase 9a. Pergunta 5 da `DEVOLUTIVA.md:302-304`.

### D4 — Prazo de expiração do token

**Recomendado:** **180 dias** a partir da geração, renovado a cada `toggle_portal`. Escolhi longo de propósito: token curto demais gera chamado de suporte a cada obra e o time desliga a expiração. 180 dias fecha a janela do ex-cliente e do link vazado em grupo de WhatsApp sem atrapalhar a obra em curso. Coluna nullable — token existente sem data continua valendo até ser rotacionado, para o deploy não derrubar portal de obra ativa.

### D5 — O almoxarifado passa a exigir papel?

**Recomendado:** **não nesta fase.** O papel `COMPRADOR` nasce ligado a compras. Trancar as ~20 rotas de `views/almoxarifado/` num papel que ninguém tem ainda tiraria acesso de campo no dia do deploy. Fica como primeiro consumidor candidato da Fase 4.

### D6 — Numeração da requisição

**Recomendado:** `RC-<ano>-<sequencial de 4 dígitos por tenant>`, ex.: `RC-2026-0001`. Sequencial por tenant e por ano, calculado com `SELECT max` dentro da transação e protegido por `UNIQUE (admin_id, numero)` — em caso de corrida, o `IntegrityError` é capturado e o número recalculado (mesmo padrão de retry já usado no versionamento do relatório de mapa, `views/obras.py:3279`).

---

## Arquivos que esta fase cria ou altera

| Arquivo | Responsabilidade |
|---|---|
| `models.py` | `EstadoRequisicao`, `RequisicaoCompra`, `RequisicaoCompraItem`, `RequisicaoTransicao`, `FaixaAlcada`, `PortalAcessoEvento`; `PapelObra.COMPRADOR`; `PedidoCompra.requisicao_id`; `ConfiguracaoEmpresa.compras_governanca_ativa`; `Obra.token_cliente_expira_em` |
| `migrations.py` | migrations 240–247 + registro em `migrations_to_run` |
| `services/requisicao_compra.py` | **novo** — chokepoint `transicionar()`, `proximo_numero()`, `recalcular_valor()` |
| `services/alcada_compras.py` | **novo** — motor de alçada: faixa por valor, quem pode aprovar, o que ainda falta |
| `utils/autorizacao.py` | acrescenta `pode_requisitar_na_obra()`, `pode_comprar_na_obra()`, `PAPEIS_QUE_REQUISITAM`, `PAPEIS_QUE_COMPRAM` |
| `compras_views.py` | 6 rotas novas de requisição + guard de governança no `nova_post` |
| `portal_obras_views.py` | guarda de `tipo_compra`, verificação de expiração, trilha de acesso, ciência sob flag |
| `scripts/flag_compras_governanca.py` | **novo** — liga/desliga a flag por tenant, com guarda |
| `templates/compras/requisicoes.html` | **novo** — lista com filtro por estado |
| `templates/compras/requisicao_nova.html` | **novo** — formulário com itens dinâmicos |
| `templates/compras/requisicao_detalhe.html` | **novo** — detalhe, histórico, botões de aprovar/rejeitar/emitir |
| `templates/base_completo.html` | dois itens no menu de Compras |
| `tests/test_fase3_requisicao.py` | **novo** — modelo, numeração, máquina de estados |
| `tests/test_fase3_alcada.py` | **novo** — faixas, separação de funções, matriz de aprovação |
| `tests/test_fase3_portal_seguranca.py` | **novo** — os cinco POSTs anônimos |
| `docs/fase-3-rollout.md` | **novo** — runbook |

---

## Task 1: Modelo da requisição (`RequisicaoCompra` + itens)

**Files:**
- Modify: `models.py` (enum após `PapelObra`, ~linha 27; modelos após `PedidoCompraItem`, linha 4793)
- Modify: `migrations.py` (migrations 240 e 241 + registro após a linha 4014)
- Test: `tests/test_fase3_requisicao.py`

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_fase3_requisicao.py`:

```python
"""Fase 3 — documento de requisição de compra.

Até 2026-07-21 não existia nenhuma requisição no repositório inteiro
(`grep -rni "requisic"` devolvia zero). A compra nascia direto do
formulário e era efetivada no mesmo request (`compras_views.py:709-711`),
criando GestaoCustoPai, ContaPagar e movimento de almoxarifado sem que
ninguém tivesse aprovado nada. Estes testes travam o documento que passa
a existir ANTES da compra.
"""
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import (Cliente, EstadoRequisicao, Obra, ObraServicoCusto,
                    RequisicaoCompra, RequisicaoCompraItem, TipoUsuario, Usuario)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase3-requisicao'
    yield


def _admin(nome='Admin'):
    """ADMIN do tenant. `versao_sistema='v2'` porque TODA rota de compras
    passa por `_check_v2()` (compras_views.py:36-40)."""
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'f3a_{suf}', email=f'f3a_{suf}@test.local',
        nome=f'{nome} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _operador(admin_id, nome='Operador'):
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'f3o_{suf}', email=f'f3o_{suf}@test.local',
        nome=f'{nome} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
        admin_id=admin_id, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id, nome='Obra'):
    """`Obra.cliente_id` é NOT NULL (models.py:265-268) — o Cliente vem antes."""
    suf = uuid.uuid4().hex[:8]
    cliente = Cliente(nome=f'Cliente {suf}', admin_id=admin_id)
    db.session.add(cliente)
    db.session.commit()
    o = Obra(
        nome=f'{nome} {suf}', codigo=f'O{suf[:6].upper()}',
        data_inicio=date(2026, 1, 1), admin_id=admin_id,
        cliente_id=cliente.id, ativo=True,
    )
    db.session.add(o)
    db.session.commit()
    return o


def test_estado_requisicao_tem_os_seis_estados():
    assert {e.name for e in EstadoRequisicao} == {
        'RASCUNHO', 'AGUARDANDO_APROVACAO', 'APROVADA',
        'REJEITADA', 'CONVERTIDA', 'CANCELADA'}


def test_requisicao_nasce_em_rascunho():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        r = RequisicaoCompra(
            numero='RC-2026-0001', obra_id=obra.id,
            solicitante_id=admin.id, admin_id=admin.id,
            justificativa='Perfis U90 para a montagem do painel P3',
        )
        db.session.add(r)
        db.session.commit()
        rid = r.id

    with app.app_context():
        recarregada = db.session.get(RequisicaoCompra, rid)
        assert recarregada.estado == EstadoRequisicao.RASCUNHO
        assert recarregada.valor_estimado == Decimal('0.00')


def test_requisicao_exige_obra():
    """obra_id NOT NULL desde o primeiro dia — é tabela nova, não há órfão
    para migrar (ao contrário de pedido_compra.obra_id, models.py:4736)."""
    from sqlalchemy.exc import IntegrityError

    with app.app_context():
        admin = _admin()
        db.session.add(RequisicaoCompra(
            numero='RC-2026-0002', obra_id=None,
            solicitante_id=admin.id, admin_id=admin.id))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_numero_e_unico_por_tenant():
    from sqlalchemy.exc import IntegrityError

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        for _ in range(2):
            db.session.add(RequisicaoCompra(
                numero='RC-2026-0003', obra_id=obra.id,
                solicitante_id=admin.id, admin_id=admin.id))
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                return
        pytest.fail('numero repetido no mesmo tenant foi aceito')


def test_dois_tenants_podem_ter_o_mesmo_numero():
    with app.app_context():
        a1, a2 = _admin('A'), _admin('B')
        o1, o2 = _obra(a1.id), _obra(a2.id)
        db.session.add(RequisicaoCompra(
            numero='RC-2026-0001', obra_id=o1.id,
            solicitante_id=a1.id, admin_id=a1.id))
        db.session.add(RequisicaoCompra(
            numero='RC-2026-0001', obra_id=o2.id,
            solicitante_id=a2.id, admin_id=a2.id))
        db.session.commit()  # não pode levantar


def test_itens_somam_no_valor_estimado():
    from services.requisicao_compra import recalcular_valor

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        r = RequisicaoCompra(
            numero='RC-2026-0004', obra_id=obra.id,
            solicitante_id=admin.id, admin_id=admin.id)
        db.session.add(r)
        db.session.flush()
        db.session.add(RequisicaoCompraItem(
            requisicao_id=r.id, admin_id=admin.id, descricao='Perfil U90',
            unidade='m', quantidade=Decimal('120.000'),
            preco_estimado=Decimal('18.50')))
        db.session.add(RequisicaoCompraItem(
            requisicao_id=r.id, admin_id=admin.id, descricao='Parafuso GN25',
            unidade='cx', quantidade=Decimal('4.000'),
            preco_estimado=Decimal('89.90')))
        db.session.flush()
        recalcular_valor(r)
        db.session.commit()
        # 120 * 18.50 = 2220.00 ; 4 * 89.90 = 359.60
        assert r.valor_estimado == Decimal('2579.60')


def test_etapa_e_opcional_e_validada_contra_a_obra():
    """obra_servico_custo_id espelha pedido_compra (models.py:4740) — opcional."""
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        etapa = ObraServicoCusto(
            admin_id=admin.id, obra_id=obra.id, nome='Montagem de painéis')
        db.session.add(etapa)
        db.session.commit()

        r = RequisicaoCompra(
            numero='RC-2026-0005', obra_id=obra.id,
            obra_servico_custo_id=etapa.id,
            solicitante_id=admin.id, admin_id=admin.id)
        db.session.add(r)
        db.session.commit()
        assert r.obra_servico_custo_id == etapa.id

        r2 = RequisicaoCompra(
            numero='RC-2026-0006', obra_id=obra.id,
            solicitante_id=admin.id, admin_id=admin.id)
        db.session.add(r2)
        db.session.commit()
        assert r2.obra_servico_custo_id is None
```

- [ ] **Step 2: Rode o teste e confirme que falha**

```bash
python -m pytest tests/test_fase3_requisicao.py -v
```

Esperado: FAIL na coleção — `ImportError: cannot import name 'EstadoRequisicao' from 'models'`.

- [ ] **Step 3: Acrescente o enum de estados**

Em `models.py`, logo **após** a `class PapelObra` que a Fase 1 inseriu (fim do bloco, antes de `class Usuario`), insira:

```python
class EstadoRequisicao(Enum):
    """Ciclo de vida da RequisicaoCompra — Fase 3.

    Mesma forma da máquina de estados da Obra (Fase 2) e da
    CronogramaImportacao (models.py:5037): enum de estado + tabela de
    transição auditada + um único chokepoint que valida. Não há
    `transicionar` no modelo de propósito — ele vive em
    services/requisicao_compra.py, para que exista UM caminho de escrita.

    Terminais: REJEITADA, CONVERTIDA e CANCELADA. De CONVERTIDA não se
    volta: o PedidoCompra já existe e já gerou GestaoCustoPai e
    ContaPagar (compras_views.py:193-254).
    """
    RASCUNHO = "rascunho"
    AGUARDANDO_APROVACAO = "aguardando_aprovacao"
    APROVADA = "aprovada"
    REJEITADA = "rejeitada"
    CONVERTIDA = "convertida"
    CANCELADA = "cancelada"
```

- [ ] **Step 4: Acrescente os dois modelos**

Em `models.py`, imediatamente após a `class PedidoCompraItem` (que termina na linha 4792, antes do comentário `# MÓDULO V2: TRANSPORTE` da linha 4795), insira:

```python
class RequisicaoCompra(db.Model):
    """Documento de DEMANDA de compra — Fase 3.

    O que existia até 2026-07-21 era só o `PedidoCompra`, que é registro a
    posteriori de NF/recibo: `compras_views.py:709-711` cria o pedido, os
    GestaoCustoPai, os ContaPagar e os movimentos de almoxarifado no MESMO
    request do formulário. Não havia lugar onde alguém pedisse antes de
    comprar, nem onde alguém aprovasse.

    Diferenças deliberadas em relação a PedidoCompra:
      * `obra_id` é NOT NULL aqui (lá é nullable — models.py:4736). Tabela
        nova, sem órfão para migrar; a Fase 4 encontra o terreno pronto.
      * `valor_estimado` é ESTIMATIVA. O valor real é o do pedido emitido.
        A alçada decide pela estimativa, e a Task 8 recusa emitir pedido
        acima da faixa aprovada.
    """
    __tablename__ = 'requisicao_compra'
    __table_args__ = (
        db.UniqueConstraint('admin_id', 'numero', name='uq_requisicao_admin_numero'),
        db.Index('ix_requisicao_obra_estado', 'obra_id', 'estado'),
        db.Index('ix_requisicao_admin_estado', 'admin_id', 'estado'),
    )

    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(30), nullable=False)  # RC-2026-0001, por tenant
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'),
                         nullable=False, index=True)

    # Vínculo obrigatório com obra. É a regra central da fase: requisição
    # sem obra não existe, porque custo sem obra não é rastreável
    # (DEVOLUTIVA R4 / services/resumo_custos_obra.py:190, que hoje rateia
    # órfão por estimativa).
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id', ondelete='CASCADE'),
                        nullable=False, index=True)
    # Etapa/centro de custo — opcional, exatamente como em
    # pedido_compra.obra_servico_custo_id (models.py:4740, migration 205).
    obra_servico_custo_id = db.Column(
        db.Integer, db.ForeignKey('obra_servico_custo.id', ondelete='SET NULL'),
        nullable=True)

    solicitante_id = db.Column(db.Integer, db.ForeignKey('usuario.id'),
                               nullable=False, index=True)
    estado = db.Column(db.Enum(EstadoRequisicao), nullable=False,
                       default=EstadoRequisicao.RASCUNHO)

    justificativa = db.Column(db.Text)
    data_necessidade = db.Column(db.Date, nullable=True)
    valor_estimado = db.Column(db.Numeric(15, 2), nullable=False, default=0)

    # Mapa de concorrência opcional. FK, NÃO reparentagem: os mapas
    # existentes continuam pendurados na obra (models.py:5604) e continuam
    # funcionando. Faixas de alçada altas podem exigir que esta FK esteja
    # preenchida e o mapa concluído (FaixaAlcada.exige_mapa_concorrencia).
    mapa_v2_id = db.Column(
        db.Integer, db.ForeignKey('mapa_concorrencia_v2.id', ondelete='SET NULL'),
        nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    obra = db.relationship('Obra', foreign_keys=[obra_id],
                           backref=db.backref('requisicoes', lazy='dynamic'))
    obra_servico_custo = db.relationship('ObraServicoCusto',
                                         foreign_keys=[obra_servico_custo_id])
    solicitante = db.relationship('Usuario', foreign_keys=[solicitante_id])
    mapa_v2 = db.relationship('MapaConcorrenciaV2', foreign_keys=[mapa_v2_id])
    itens = db.relationship('RequisicaoCompraItem', backref='requisicao',
                            lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<RequisicaoCompra {self.numero} obra={self.obra_id} {self.estado.value}>'


class RequisicaoCompraItem(db.Model):
    """Linha de uma RequisicaoCompra.

    Espelha PedidoCompraItem (models.py:4778) de propósito: a conversão em
    pedido é uma cópia campo a campo, sem tradução. A diferença é que aqui
    o preço é ESTIMADO (o solicitante de campo raramente sabe o preço
    fechado) e existe `unidade`, que PedidoCompraItem não tem.
    """
    __tablename__ = 'requisicao_compra_item'
    __table_args__ = (
        db.Index('ix_requisicao_item_requisicao', 'requisicao_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    requisicao_id = db.Column(
        db.Integer, db.ForeignKey('requisicao_compra.id', ondelete='CASCADE'),
        nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    # Opcional: item do catálogo do almoxarifado (models.py:4508). Quando
    # preenchido, a conversão em pedido leva o vínculo junto e a entrada de
    # estoque é gerada por _gerar_entrada_almoxarifado (compras_views.py:80).
    almoxarifado_item_id = db.Column(
        db.Integer, db.ForeignKey('almoxarifado_item.id'), nullable=True)
    descricao = db.Column(db.String(200), nullable=False)
    unidade = db.Column(db.String(20), default='un')
    quantidade = db.Column(db.Numeric(12, 3), nullable=False, default=1)
    preco_estimado = db.Column(db.Numeric(15, 2), nullable=False, default=0)

    almoxarifado_item = db.relationship('AlmoxarifadoItem',
                                        foreign_keys=[almoxarifado_item_id])

    @property
    def subtotal(self):
        """Derivado, não persistido: não existe caminho em que subtotal e
        quantidade*preco divirjam, e persistir os dois cria a chance de
        divergirem (é o que acontece em PedidoCompraItem.subtotal)."""
        from decimal import Decimal as _D
        return (_D(str(self.quantidade or 0)) * _D(str(self.preco_estimado or 0))
                ).quantize(_D('0.01'))

    def __repr__(self):
        return f'<RequisicaoCompraItem req={self.requisicao_id} {self.descricao[:30]}>'
```

- [ ] **Step 5: Escreva as migrations 240 e 241**

Em `migrations.py`, imediatamente **antes** de `def executar_migracoes():` (linha 3773), insira:

```python
def migration_240_requisicao_compra():
    """Fase 3 — tabela requisicao_compra.

    Aditiva e idempotente. Nasce vazia e sem consumidor obrigatório: a
    flag `configuracao_empresa.compras_governanca_ativa` (migration 246)
    nasce FALSE, então `compras.nova_post` continua funcionando como hoje.

    obra_id é NOT NULL desde já — é tabela nova, não há linha órfã para
    classificar (o problema caro do §3.4 da DEVOLUTIVA é o pedido_compra,
    não este).

    Nota sobre o tipo da coluna `estado`: o modelo declara
    `db.Enum(EstadoRequisicao)`, e `db.create_all()` (app.py:582) roda
    ANTES desta migração no boot. Em banco novo a tabela já terá nascido
    com um tipo enum nativo; o CREATE TABLE IF NOT EXISTS abaixo é no-op.
    Em banco existente, esta migração cria a tabela com VARCHAR e o
    SQLAlchemy grava/lê o NOME do membro ('RASCUNHO'). As duas formas
    convivem — é por isso que o DEFAULT abaixo usa o nome, não o valor.
    """
    logger.info("[Migration 240] Iniciando — tabela requisicao_compra")

    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS requisicao_compra (
            id SERIAL PRIMARY KEY,
            numero VARCHAR(30) NOT NULL,
            admin_id INTEGER NOT NULL REFERENCES usuario(id),
            obra_id INTEGER NOT NULL REFERENCES obra(id) ON DELETE CASCADE,
            obra_servico_custo_id INTEGER
                REFERENCES obra_servico_custo(id) ON DELETE SET NULL,
            solicitante_id INTEGER NOT NULL REFERENCES usuario(id),
            estado VARCHAR(30) NOT NULL DEFAULT 'RASCUNHO',
            justificativa TEXT,
            data_necessidade DATE,
            valor_estimado NUMERIC(15,2) NOT NULL DEFAULT 0,
            mapa_v2_id INTEGER
                REFERENCES mapa_concorrencia_v2(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """))
    db.session.commit()

    db.session.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_requisicao_admin_numero
        ON requisicao_compra (admin_id, numero)
    """))
    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_requisicao_obra_estado
        ON requisicao_compra (obra_id, estado)
    """))
    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_requisicao_admin_estado
        ON requisicao_compra (admin_id, estado)
    """))
    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_requisicao_solicitante
        ON requisicao_compra (solicitante_id)
    """))
    db.session.commit()

    logger.info("[Migration 240] Concluída com sucesso")


def migration_241_requisicao_compra_item():
    """Fase 3 — tabela requisicao_compra_item. Aditiva e idempotente.

    Sem coluna `subtotal`: ele é derivado em
    RequisicaoCompraItem.subtotal. Persistir quantidade, preço E subtotal
    (como faz pedido_compra_item, models.py:4788) cria três fontes para
    um número só, e portanto a chance de divergirem.
    """
    logger.info("[Migration 241] Iniciando — tabela requisicao_compra_item")

    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS requisicao_compra_item (
            id SERIAL PRIMARY KEY,
            requisicao_id INTEGER NOT NULL
                REFERENCES requisicao_compra(id) ON DELETE CASCADE,
            admin_id INTEGER NOT NULL REFERENCES usuario(id),
            almoxarifado_item_id INTEGER REFERENCES almoxarifado_item(id),
            descricao VARCHAR(200) NOT NULL,
            unidade VARCHAR(20) DEFAULT 'un',
            quantidade NUMERIC(12,3) NOT NULL DEFAULT 1,
            preco_estimado NUMERIC(15,2) NOT NULL DEFAULT 0
        )
    """))
    db.session.commit()

    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_requisicao_item_requisicao
        ON requisicao_compra_item (requisicao_id)
    """))
    db.session.commit()

    logger.info("[Migration 241] Concluída com sucesso")
```

- [ ] **Step 6: Registre as migrations**

Em `migrations.py`, na lista `migrations_to_run`, **depois** da última entrada da Fase 2 (a lista termina hoje na `213`, linha 4014; Fase 1 acrescenta 214-216 e Fase 2 as suas), adicione:

```python
            (240, "Fase 3 — tabela requisicao_compra (documento de demanda, obra_id NOT NULL)", migration_240_requisicao_compra),
            (241, "Fase 3 — tabela requisicao_compra_item", migration_241_requisicao_compra_item),
```

- [ ] **Step 7: Crie o serviço com `recalcular_valor`**

Crie `services/requisicao_compra.py`:

```python
"""Serviço da RequisicaoCompra — Fase 3.

Único caminho de escrita do estado e do valor da requisição. O modelo
(models.RequisicaoCompra) é deliberadamente burro: nenhuma regra mora
lá, para que não existam dois lugares onde uma transição possa
acontecer.
"""
import logging
from datetime import datetime
from decimal import Decimal

from models import EstadoRequisicao, RequisicaoCompra, db

logger = logging.getLogger('requisicao_compra')


def recalcular_valor(requisicao):
    """Soma os itens em `valor_estimado`. NÃO commita.

    Chamada em todo ponto que mexe em item. O valor é a base da alçada
    (services/alcada_compras.py), então deixá-lo desatualizado é deixar a
    requisição cair na faixa errada.
    """
    total = Decimal('0.00')
    for item in requisicao.itens:
        total += item.subtotal
    requisicao.valor_estimado = total
    requisicao.updated_at = datetime.utcnow()
    return total


def proximo_numero(admin_id, ano=None):
    """Próximo `RC-<ano>-<NNNN>` do tenant.

    Sequencial por tenant e por ano. Há corrida possível entre dois
    requests simultâneos; ela é fechada pelo UNIQUE (admin_id, numero) e
    pelo retry em `compras_views.requisicao_nova_post`. Mesmo padrão já
    usado no versionamento do relatório de mapa (views/obras.py:3279).
    """
    ano = ano or datetime.utcnow().year
    prefixo = f'RC-{ano}-'
    ultimo = (
        db.session.query(RequisicaoCompra.numero)
        .filter(RequisicaoCompra.admin_id == admin_id)
        .filter(RequisicaoCompra.numero.like(f'{prefixo}%'))
        .order_by(RequisicaoCompra.numero.desc())
        .first()
    )
    if not ultimo:
        return f'{prefixo}0001'
    try:
        seq = int(ultimo[0].rsplit('-', 1)[1]) + 1
    except (IndexError, ValueError):
        logger.warning('numero fora do padrão no tenant %s: %r', admin_id, ultimo[0])
        seq = 1
    return f'{prefixo}{seq:04d}'
```

- [ ] **Step 8: Aplique as migrations e rode os testes**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "240|241|ERRO|ERROR"
python -m pytest tests/test_fase3_requisicao.py -v
```

Esperado: `[Migration 240] Concluída com sucesso`, `[Migration 241] Concluída com sucesso` e os 7 testes PASSAM.

- [ ] **Step 9: Commit**

```bash
git add models.py migrations.py services/requisicao_compra.py tests/test_fase3_requisicao.py
git commit -m "feat(fase3): modelo de requisicao de compra

RequisicaoCompra + RequisicaoCompraItem. obra_id NOT NULL desde o
primeiro dia (tabela nova, sem orfao para migrar). subtotal derivado,
nao persistido. Nasce sem consumidor: a compra continua funcionando
exatamente como hoje."
```

---

## Task 2: Máquina de estados e histórico de transição

**Files:**
- Modify: `models.py` (modelo após `RequisicaoCompraItem`)
- Modify: `migrations.py` (migration 242 + registro)
- Modify: `services/requisicao_compra.py` (chokepoint `transicionar`)
- Test: `tests/test_fase3_requisicao.py` (acrescenta)

- [ ] **Step 1: Reconheça o que a Fase 2 deixou (obrigatório antes de escrever)**

```bash
ls -la utils/maquina_estados.py 2>/dev/null
grep -rn "TRANSICOES_VALIDAS\|def transicionar\|TransicaoInvalida" --include=*.py . | grep -v archive
grep -n "class ObraTransicao\|class .*Transicao" models.py
```

Duas saídas possíveis, e o passo 4 muda conforme:

- **Se a Fase 2 tiver deixado um helper genérico** (uma função `transicionar(entidade, novo_estado, ...)` parametrizada por um mapa de transições, ou uma mixin), **use-o**. Substitua o corpo de `transicionar` do passo 4 por uma chamada a ele, mantendo a assinatura pública `transicionar(requisicao, novo_estado, usuario, motivo=None)` que o resto deste plano consome, e mantenha `TRANSICOES_VALIDAS` como o mapa que você passa para o helper.
- **Se a Fase 2 tiver feito a máquina inline na Obra** (só `Obra.estado` + `ObraTransicaoEstado` + validação em `services/`), escreva o código do passo 4 como está — ele é a mesma forma aplicada à requisição, e a extração de um helper comum fica para quem tiver o terceiro caso.

Anote no commit qual dos dois caminhos você seguiu.

- [ ] **Step 2: Escreva o teste que falha**

Acrescente ao final de `tests/test_fase3_requisicao.py`:

```python
# ---------------------------------------------------------------------------
# Máquina de estados
# ---------------------------------------------------------------------------

def _requisicao(admin_id, obra_id, solicitante_id, valor='1000.00'):
    from services.requisicao_compra import proximo_numero
    r = RequisicaoCompra(
        numero=proximo_numero(admin_id), obra_id=obra_id,
        solicitante_id=solicitante_id, admin_id=admin_id,
        valor_estimado=Decimal(valor),
        justificativa='Material da semana')
    db.session.add(r)
    db.session.commit()
    return r


def test_transicao_valida_grava_historico():
    from models import RequisicaoTransicao
    from services.requisicao_compra import transicionar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        op = _operador(admin.id)
        r = _requisicao(admin.id, obra.id, op.id, valor='2579.60')

        transicionar(r, EstadoRequisicao.AGUARDANDO_APROVACAO, op,
                     motivo='enviada para aprovação')
        db.session.commit()

        assert r.estado == EstadoRequisicao.AGUARDANDO_APROVACAO
        t = RequisicaoTransicao.query.filter_by(requisicao_id=r.id).one()
        assert t.de_estado == EstadoRequisicao.RASCUNHO
        assert t.para_estado == EstadoRequisicao.AGUARDANDO_APROVACAO
        assert t.usuario_id == op.id
        # o valor no momento da transição é o dado que a auditoria precisa:
        # a requisição pode ser editada depois, e o histórico não pode mentir
        assert t.valor_no_momento == Decimal('2579.60')
        assert t.criado_em is not None


def test_transicao_invalida_e_recusada():
    from services.requisicao_compra import TransicaoInvalida, transicionar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        op = _operador(admin.id)
        r = _requisicao(admin.id, obra.id, op.id)
        # RASCUNHO → CONVERTIDA pula a aprovação inteira
        with pytest.raises(TransicaoInvalida):
            transicionar(r, EstadoRequisicao.CONVERTIDA, op)
        db.session.rollback()


def test_estado_terminal_nao_transiciona():
    from services.requisicao_compra import TransicaoInvalida, transicionar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        op = _operador(admin.id)
        r = _requisicao(admin.id, obra.id, op.id)
        transicionar(r, EstadoRequisicao.CANCELADA, op, motivo='desistiu')
        db.session.commit()
        with pytest.raises(TransicaoInvalida):
            transicionar(r, EstadoRequisicao.RASCUNHO, op)
        db.session.rollback()


def test_rejeitada_volta_para_rascunho():
    """Rejeitar não é matar: o solicitante corrige e reenvia. É o único
    caminho de volta de um estado de decisão."""
    from services.requisicao_compra import transicionar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        op = _operador(admin.id)
        r = _requisicao(admin.id, obra.id, op.id)
        transicionar(r, EstadoRequisicao.AGUARDANDO_APROVACAO, op)
        transicionar(r, EstadoRequisicao.REJEITADA, admin, motivo='sem verba')
        transicionar(r, EstadoRequisicao.RASCUNHO, op, motivo='corrigindo')
        db.session.commit()
        assert r.estado == EstadoRequisicao.RASCUNHO


def test_historico_fica_em_ordem_e_completo():
    from models import RequisicaoTransicao
    from services.requisicao_compra import transicionar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        op = _operador(admin.id)
        r = _requisicao(admin.id, obra.id, op.id)
        transicionar(r, EstadoRequisicao.AGUARDANDO_APROVACAO, op)
        transicionar(r, EstadoRequisicao.APROVADA, admin, motivo='ok')
        db.session.commit()

        trilha = (RequisicaoTransicao.query
                  .filter_by(requisicao_id=r.id)
                  .order_by(RequisicaoTransicao.id).all())
        assert [t.para_estado for t in trilha] == [
            EstadoRequisicao.AGUARDANDO_APROVACAO, EstadoRequisicao.APROVADA]
        assert [t.usuario_id for t in trilha] == [op.id, admin.id]
```

- [ ] **Step 3: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase3_requisicao.py -v -k "transicao or terminal or rejeitada or historico"
```

Esperado: FAIL — `ImportError: cannot import name 'RequisicaoTransicao' from 'models'`.

- [ ] **Step 4: Acrescente o modelo de transição**

Em `models.py`, imediatamente após a `class RequisicaoCompraItem`, insira:

```python
class RequisicaoTransicao(db.Model):
    """Trilha de auditoria da RequisicaoCompra — quem, quando, de onde para
    onde, e por QUANTO.

    Mesma forma de CronogramaImportacaoEvento (models.py:5178) e de
    PropostaHistorico (models.py:3140), que são as duas trilhas que já
    funcionam neste repositório. A diferença é `valor_no_momento`: numa
    aprovação por alçada, o valor da decisão é parte da decisão. Sem ele,
    editar a requisição depois de aprovada reescreveria a história — que é
    exatamente o buraco que uma alçada tem que fechar.

    `papel_aplicado` guarda com que chapéu a pessoa agiu ('ADMIN',
    'GESTOR', 'COMPRADOR'), porque o vínculo em usuario_obra pode mudar
    depois e o histórico não pode mudar junto.
    """
    __tablename__ = 'requisicao_transicao'
    __table_args__ = (
        db.Index('ix_requisicao_transicao_req', 'requisicao_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    requisicao_id = db.Column(
        db.Integer, db.ForeignKey('requisicao_compra.id', ondelete='CASCADE'),
        nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    de_estado = db.Column(db.Enum(EstadoRequisicao), nullable=True)
    para_estado = db.Column(db.Enum(EstadoRequisicao), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    papel_aplicado = db.Column(db.String(20), nullable=True)
    valor_no_momento = db.Column(db.Numeric(15, 2), nullable=True)
    motivo = db.Column(db.Text, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    requisicao = db.relationship(
        'RequisicaoCompra',
        backref=db.backref('transicoes', lazy='dynamic',
                           order_by='RequisicaoTransicao.id',
                           cascade='all, delete-orphan'))
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id])

    def __repr__(self):
        de = self.de_estado.value if self.de_estado else '-'
        return f'<RequisicaoTransicao req={self.requisicao_id} {de}→{self.para_estado.value}>'
```

- [ ] **Step 5: Escreva a migration 242 e registre**

Em `migrations.py`, antes de `def executar_migracoes():`, insira:

```python
def migration_242_requisicao_transicao():
    """Fase 3 — trilha de auditoria da requisição. Aditiva e idempotente.

    `valor_no_momento` é NULLable porque transições que não são de decisão
    (cancelamento, volta para rascunho) não têm valor relevante — mas
    aprovação e rejeição sempre gravam.
    """
    logger.info("[Migration 242] Iniciando — tabela requisicao_transicao")

    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS requisicao_transicao (
            id SERIAL PRIMARY KEY,
            requisicao_id INTEGER NOT NULL
                REFERENCES requisicao_compra(id) ON DELETE CASCADE,
            admin_id INTEGER NOT NULL REFERENCES usuario(id),
            de_estado VARCHAR(30),
            para_estado VARCHAR(30) NOT NULL,
            usuario_id INTEGER REFERENCES usuario(id),
            papel_aplicado VARCHAR(20),
            valor_no_momento NUMERIC(15,2),
            motivo TEXT,
            criado_em TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """))
    db.session.commit()

    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_requisicao_transicao_req
        ON requisicao_transicao (requisicao_id)
    """))
    db.session.commit()

    logger.info("[Migration 242] Concluída com sucesso")
```

Registre em `migrations_to_run`, após a entrada `241`:

```python
            (242, "Fase 3 — trilha de auditoria requisicao_transicao (quem/quando/valor)", migration_242_requisicao_transicao),
```

- [ ] **Step 6: Acrescente o chokepoint ao serviço**

Ao final de `services/requisicao_compra.py`, acrescente:

```python
class TransicaoInvalida(Exception):
    """Transição de estado não permitida pela máquina."""


# Máquina de estados da requisição. Ler assim: "de X, pode-se ir para".
# Estado ausente do dicionário (ou com tupla vazia) é TERMINAL.
#
# Duas escolhas que valem comentário:
#   * REJEITADA → RASCUNHO existe porque rejeitar não é matar. O gestor
#     rejeita "3 chapas é pouco, peça 5"; o solicitante corrige e reenvia,
#     e o histórico guarda os dois momentos.
#   * De CONVERTIDA não se volta. Nesse ponto o PedidoCompra já existe e
#     já gerou GestaoCustoPai e ContaPagar (compras_views.py:193-254).
#     Desfazer é excluir o pedido (compras_views.py:1023), que é outra
#     operação, com outra trilha.
TRANSICOES_VALIDAS = {
    EstadoRequisicao.RASCUNHO: (
        EstadoRequisicao.AGUARDANDO_APROVACAO,
        EstadoRequisicao.CANCELADA,
    ),
    EstadoRequisicao.AGUARDANDO_APROVACAO: (
        EstadoRequisicao.APROVADA,
        EstadoRequisicao.REJEITADA,
        EstadoRequisicao.CANCELADA,
    ),
    EstadoRequisicao.APROVADA: (
        EstadoRequisicao.CONVERTIDA,
        EstadoRequisicao.CANCELADA,
    ),
    EstadoRequisicao.REJEITADA: (
        EstadoRequisicao.RASCUNHO,
        EstadoRequisicao.CANCELADA,
    ),
    EstadoRequisicao.CONVERTIDA: (),
    EstadoRequisicao.CANCELADA: (),
}


def _papel_de(usuario, requisicao):
    """Com que chapéu a pessoa está agindo. Congelado no histórico porque o
    vínculo em usuario_obra pode mudar depois — e a trilha não pode."""
    from models import TipoUsuario

    if usuario is None:
        return None
    if usuario.tipo_usuario in (TipoUsuario.ADMIN, TipoUsuario.SUPER_ADMIN):
        return 'ADMIN'
    try:
        from utils.autorizacao import papel_na_obra
        papel = papel_na_obra(requisicao.obra_id)
        return papel.name if papel is not None else None
    except Exception:
        logger.warning('papel_na_obra indisponível para requisicao %s',
                       requisicao.id)
        return None


def transicionar(requisicao, novo_estado, usuario, motivo=None):
    """ÚNICO caminho de mudança de estado. NÃO commita.

    Valida contra TRANSICOES_VALIDAS, grava a RequisicaoTransicao com
    quem/quando/valor/papel, e só então muda o estado. A ordem importa:
    se a validação falhar, nada foi escrito.

    Não decide PERMISSÃO — isso é de services/alcada_compras.py e das
    rotas. Aqui só se decide LEGALIDADE da transição. Separar os dois é o
    que permite testar a máquina sem montar um request.
    """
    from models import RequisicaoTransicao

    atual = requisicao.estado
    permitidos = TRANSICOES_VALIDAS.get(atual, ())
    if novo_estado not in permitidos:
        nomes = ', '.join(e.name for e in permitidos) or '(nenhum — terminal)'
        raise TransicaoInvalida(
            f'Requisição {requisicao.numero}: {atual.name} → '
            f'{novo_estado.name} não é permitido. Permitidos: {nomes}')

    db.session.add(RequisicaoTransicao(
        requisicao_id=requisicao.id,
        admin_id=requisicao.admin_id,
        de_estado=atual,
        para_estado=novo_estado,
        usuario_id=getattr(usuario, 'id', None),
        papel_aplicado=_papel_de(usuario, requisicao),
        valor_no_momento=requisicao.valor_estimado,
        motivo=motivo,
    ))
    requisicao.estado = novo_estado
    requisicao.updated_at = datetime.utcnow()
    db.session.flush()

    logger.info('requisicao %s %s → %s por usuario=%s valor=%s',
                requisicao.numero, atual.name, novo_estado.name,
                getattr(usuario, 'id', None), requisicao.valor_estimado)
    return requisicao
```

- [ ] **Step 7: Aplique e rode**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "242|ERRO|ERROR"
python -m pytest tests/test_fase3_requisicao.py -v
```

Esperado: `[Migration 242] Concluída com sucesso` e os 12 testes PASSAM.

- [ ] **Step 8: Commit**

```bash
git add models.py migrations.py services/requisicao_compra.py tests/test_fase3_requisicao.py
git commit -m "feat(fase3): maquina de estados da requisicao + trilha auditada

TRANSICOES_VALIDAS num dicionario e um unico transicionar() que valida
antes de escrever. RequisicaoTransicao guarda quem/quando/de/para e o
VALOR no momento — sem isso, editar a requisicao depois de aprovada
reescreveria a historia da alcada."
```

---

## Task 3: Alçada configurável por tenant (`FaixaAlcada` + motor)

**Files:**
- Modify: `models.py` (modelo após `RequisicaoTransicao`)
- Modify: `migrations.py` (migration 243 + seed + registro)
- Create: `services/alcada_compras.py`
- Test: `tests/test_fase3_alcada.py`

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_fase3_alcada.py`:

```python
"""Fase 3 — alçada de aprovação de compras.

Até 2026-07-21 não existia alçada nenhuma: `grep -rni "alcada|alçada"`
só casava a palavra 'calcada' em listas de palavras-chave de cronograma
(services/cronograma_normalizacao.py:69). Qualquer usuário autenticado
com V2 registrava compra de qualquer valor em `compras_views.py:532`.

Os VALORES das faixas são RECOMENDAÇÃO (ver 'Decisões que precisam do
Cássio', D1), semeados pela migration 243 e editáveis por tenant. Estes
testes travam o MECANISMO, não os números: eles criam as próprias faixas
sempre que testam limites, e o único teste que olha o seed está marcado
como tal.
"""
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import (Cliente, EstadoRequisicao, FaixaAlcada, Obra, PapelObra,
                    RequisicaoCompra, TipoUsuario, Usuario, UsuarioObra)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase3-alcada'
    yield


def _admin(nome='Admin'):
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'f3l_{suf}', email=f'f3l_{suf}@test.local',
        nome=f'{nome} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _operador(admin_id, nome='Operador'):
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'f3p_{suf}', email=f'f3p_{suf}@test.local',
        nome=f'{nome} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
        admin_id=admin_id, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id, nome='Obra'):
    suf = uuid.uuid4().hex[:8]
    cliente = Cliente(nome=f'Cliente {suf}', admin_id=admin_id)
    db.session.add(cliente)
    db.session.commit()
    o = Obra(nome=f'{nome} {suf}', codigo=f'O{suf[:6].upper()}',
             data_inicio=date(2026, 1, 1), admin_id=admin_id,
             cliente_id=cliente.id, ativo=True)
    db.session.add(o)
    db.session.commit()
    return o


def _vincular(usuario, obra, papel):
    v = UsuarioObra(usuario_id=usuario.id, obra_id=obra.id, papel=papel,
                    admin_id=obra.admin_id, ativo=True)
    db.session.add(v)
    db.session.commit()
    return v


def _faixas_de_teste(admin_id):
    """Faixas próprias, independentes do seed — o teste trava o mecanismo."""
    FaixaAlcada.query.filter_by(admin_id=admin_id).delete()
    db.session.add(FaixaAlcada(
        admin_id=admin_id, ordem=1, valor_ate=Decimal('100.00'),
        aprovacoes_necessarias=1, exige_admin=False,
        exige_mapa_concorrencia=False, ativo=True))
    db.session.add(FaixaAlcada(
        admin_id=admin_id, ordem=2, valor_ate=Decimal('1000.00'),
        aprovacoes_necessarias=2, exige_admin=True,
        exige_mapa_concorrencia=False, ativo=True))
    db.session.add(FaixaAlcada(
        admin_id=admin_id, ordem=3, valor_ate=None,
        aprovacoes_necessarias=2, exige_admin=True,
        exige_mapa_concorrencia=True, ativo=True))
    db.session.commit()


def _requisicao(admin, obra, solicitante, valor):
    from services.requisicao_compra import proximo_numero
    r = RequisicaoCompra(
        numero=proximo_numero(admin.id), obra_id=obra.id,
        solicitante_id=solicitante.id, admin_id=admin.id,
        valor_estimado=Decimal(valor), justificativa='teste')
    db.session.add(r)
    db.session.commit()
    return r


# ---------------------------------------------------------------------------
# Seleção de faixa
# ---------------------------------------------------------------------------

def test_faixa_e_escolhida_pelo_teto_mais_baixo_que_cobre_o_valor():
    from services.alcada_compras import faixa_para_valor

    with app.app_context():
        admin = _admin()
        _faixas_de_teste(admin.id)
        assert faixa_para_valor(admin.id, Decimal('50.00')).ordem == 1
        assert faixa_para_valor(admin.id, Decimal('100.00')).ordem == 1
        assert faixa_para_valor(admin.id, Decimal('100.01')).ordem == 2
        assert faixa_para_valor(admin.id, Decimal('1000.00')).ordem == 2
        assert faixa_para_valor(admin.id, Decimal('1000.01')).ordem == 3
        assert faixa_para_valor(admin.id, Decimal('999999.00')).ordem == 3


def test_tenant_sem_faixa_cai_na_faixa_de_seguranca():
    """Falha FECHADA: sem configuração, exige o máximo, não o mínimo."""
    from services.alcada_compras import faixa_para_valor

    with app.app_context():
        admin = _admin()
        FaixaAlcada.query.filter_by(admin_id=admin.id).delete()
        db.session.commit()
        faixa = faixa_para_valor(admin.id, Decimal('10.00'))
        assert faixa.aprovacoes_necessarias == 2
        assert faixa.exige_admin is True
        assert faixa.id is None, 'a faixa de segurança não é persistida'


def test_faixa_inativa_e_ignorada():
    from services.alcada_compras import faixa_para_valor

    with app.app_context():
        admin = _admin()
        _faixas_de_teste(admin.id)
        f1 = FaixaAlcada.query.filter_by(admin_id=admin.id, ordem=1).one()
        f1.ativo = False
        db.session.commit()
        assert faixa_para_valor(admin.id, Decimal('50.00')).ordem == 2


# ---------------------------------------------------------------------------
# Separação de funções — o invariante duro da fase
# ---------------------------------------------------------------------------

def test_solicitante_nunca_aprova_a_propria_requisicao():
    from services.alcada_compras import pode_aprovar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _faixas_de_teste(admin.id)
        gestor = _operador(admin.id, 'Gestor')
        _vincular(gestor, obra, PapelObra.GESTOR)
        r = _requisicao(admin, obra, gestor, '50.00')
        r.estado = EstadoRequisicao.AGUARDANDO_APROVACAO
        db.session.commit()

        ok, motivo = pode_aprovar(r, gestor)
        assert ok is False
        assert 'solicitante' in motivo.lower()


def test_admin_tambem_nao_aprova_a_propria_requisicao():
    """Sem exceção para ADMIN. Numa empresa pequena a mesma pessoa acumula
    papéis — é justamente aí que a separação de funções tem que valer."""
    from services.alcada_compras import pode_aprovar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _faixas_de_teste(admin.id)
        r = _requisicao(admin, obra, admin, '50.00')
        r.estado = EstadoRequisicao.AGUARDANDO_APROVACAO
        db.session.commit()

        ok, motivo = pode_aprovar(r, admin)
        assert ok is False
        assert 'solicitante' in motivo.lower()


def test_ninguem_aprova_duas_vezes_a_mesma_requisicao():
    from services.alcada_compras import pode_aprovar, registrar_aprovacao

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _faixas_de_teste(admin.id)
        gestor = _operador(admin.id, 'Gestor')
        solicitante = _operador(admin.id, 'Solicitante')
        _vincular(gestor, obra, PapelObra.GESTOR)
        r = _requisicao(admin, obra, solicitante, '500.00')  # faixa 2: 2 aprovações
        r.estado = EstadoRequisicao.AGUARDANDO_APROVACAO
        db.session.commit()

        registrar_aprovacao(r, gestor, papel='GESTOR')
        db.session.commit()

        ok, motivo = pode_aprovar(r, gestor)
        assert ok is False
        assert 'já aprovou' in motivo.lower()


# ---------------------------------------------------------------------------
# Contagem de aprovações
# ---------------------------------------------------------------------------

def test_uma_aprovacao_basta_na_faixa_baixa():
    from services.alcada_compras import (aprovacoes_registradas,
                                         esta_totalmente_aprovada,
                                         registrar_aprovacao)

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _faixas_de_teste(admin.id)
        gestor = _operador(admin.id, 'Gestor')
        solicitante = _operador(admin.id, 'Solicitante')
        _vincular(gestor, obra, PapelObra.GESTOR)
        r = _requisicao(admin, obra, solicitante, '50.00')
        r.estado = EstadoRequisicao.AGUARDANDO_APROVACAO
        db.session.commit()

        assert esta_totalmente_aprovada(r) is False
        registrar_aprovacao(r, gestor, papel='GESTOR')
        db.session.commit()
        assert aprovacoes_registradas(r) == 1
        assert esta_totalmente_aprovada(r) is True


def test_faixa_alta_exige_duas_aprovacoes_sendo_uma_do_admin():
    from services.alcada_compras import (esta_totalmente_aprovada,
                                         registrar_aprovacao)

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _faixas_de_teste(admin.id)
        gestor = _operador(admin.id, 'Gestor')
        outro = _operador(admin.id, 'Outro')
        solicitante = _operador(admin.id, 'Solicitante')
        _vincular(gestor, obra, PapelObra.GESTOR)
        _vincular(outro, obra, PapelObra.GESTOR)
        r = _requisicao(admin, obra, solicitante, '500.00')
        r.estado = EstadoRequisicao.AGUARDANDO_APROVACAO
        db.session.commit()

        registrar_aprovacao(r, gestor, papel='GESTOR')
        registrar_aprovacao(r, outro, papel='GESTOR')
        db.session.commit()
        # duas aprovações, mas NENHUMA de ADMIN — a faixa exige_admin=True
        assert esta_totalmente_aprovada(r) is False

        registrar_aprovacao(r, admin, papel='ADMIN')
        db.session.commit()
        assert esta_totalmente_aprovada(r) is True


def test_faixa_de_topo_exige_mapa_concluido():
    from models import MapaConcorrenciaV2, MapaFornecedor
    from services.alcada_compras import (esta_totalmente_aprovada,
                                         registrar_aprovacao,
                                         pendencias_de_aprovacao)

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _faixas_de_teste(admin.id)
        gestor = _operador(admin.id, 'Gestor')
        solicitante = _operador(admin.id, 'Solicitante')
        _vincular(gestor, obra, PapelObra.GESTOR)
        r = _requisicao(admin, obra, solicitante, '5000.00')  # faixa 3
        r.estado = EstadoRequisicao.AGUARDANDO_APROVACAO
        db.session.commit()

        registrar_aprovacao(r, gestor, papel='GESTOR')
        registrar_aprovacao(r, admin, papel='ADMIN')
        db.session.commit()
        assert esta_totalmente_aprovada(r) is False
        assert any('mapa' in p.lower() for p in pendencias_de_aprovacao(r))

        mapa = MapaConcorrenciaV2(obra_id=obra.id, admin_id=admin.id,
                                  nome='Perfis', status='concluido')
        db.session.add(mapa)
        db.session.flush()
        db.session.add(MapaFornecedor(mapa_id=mapa.id, admin_id=admin.id,
                                      nome='Forn A', ordem=0))
        db.session.add(MapaFornecedor(mapa_id=mapa.id, admin_id=admin.id,
                                      nome='Forn B', ordem=1))
        r.mapa_v2_id = mapa.id
        db.session.commit()
        assert esta_totalmente_aprovada(r) is True


def test_mapa_com_um_fornecedor_so_nao_conta_como_concorrencia():
    from models import MapaConcorrenciaV2, MapaFornecedor
    from services.alcada_compras import (esta_totalmente_aprovada,
                                         registrar_aprovacao)

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _faixas_de_teste(admin.id)
        gestor = _operador(admin.id, 'Gestor')
        solicitante = _operador(admin.id, 'Solicitante')
        _vincular(gestor, obra, PapelObra.GESTOR)
        r = _requisicao(admin, obra, solicitante, '5000.00')
        r.estado = EstadoRequisicao.AGUARDANDO_APROVACAO
        mapa = MapaConcorrenciaV2(obra_id=obra.id, admin_id=admin.id,
                                  nome='Unico', status='concluido')
        db.session.add(mapa)
        db.session.flush()
        db.session.add(MapaFornecedor(mapa_id=mapa.id, admin_id=admin.id,
                                      nome='Forn A', ordem=0))
        r.mapa_v2_id = mapa.id
        db.session.commit()

        registrar_aprovacao(r, gestor, papel='GESTOR')
        registrar_aprovacao(r, admin, papel='ADMIN')
        db.session.commit()
        assert esta_totalmente_aprovada(r) is False


# ---------------------------------------------------------------------------
# Seed recomendado (D1) — trava os NÚMEROS da recomendação adotada
# ---------------------------------------------------------------------------

def test_seed_recomendado_cria_tres_faixas_para_tenant_novo():
    """Estes números são a RECOMENDAÇÃO do plano (D1), não uma regra do
    Cássio. Se ele definir outros, ajuste aqui E na migration 243."""
    from services.alcada_compras import garantir_faixas_do_tenant

    with app.app_context():
        admin = _admin()
        FaixaAlcada.query.filter_by(admin_id=admin.id).delete()
        db.session.commit()
        garantir_faixas_do_tenant(admin.id)
        db.session.commit()

        faixas = (FaixaAlcada.query.filter_by(admin_id=admin.id)
                  .order_by(FaixaAlcada.ordem).all())
        assert [f.valor_ate for f in faixas] == [
            Decimal('5000.00'), Decimal('30000.00'), None]
        assert [f.aprovacoes_necessarias for f in faixas] == [1, 2, 2]
        assert [f.exige_admin for f in faixas] == [False, True, True]
        assert [f.exige_mapa_concorrencia for f in faixas] == [False, False, True]


def test_garantir_faixas_e_idempotente():
    from services.alcada_compras import garantir_faixas_do_tenant

    with app.app_context():
        admin = _admin()
        garantir_faixas_do_tenant(admin.id)
        db.session.commit()
        garantir_faixas_do_tenant(admin.id)
        db.session.commit()
        assert FaixaAlcada.query.filter_by(admin_id=admin.id).count() == 3
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase3_alcada.py -v
```

Esperado: FAIL na coleção — `ImportError: cannot import name 'FaixaAlcada' from 'models'`.

- [ ] **Step 3: Acrescente o modelo `FaixaAlcada`**

Em `models.py`, imediatamente após a `class RequisicaoTransicao`, insira:

```python
class FaixaAlcada(db.Model):
    """Faixa de alçada de aprovação de compra, POR TENANT — Fase 3.

    Alçada é dado, não código. A pergunta 3 da DEVOLUTIVA ("qual o valor
    de X?") continua sem resposta do negócio, e a resposta não pode virar
    um `if valor > 5000` no meio de uma view. Os valores semeados pela
    migration 243 são a RECOMENDAÇÃO do plano da Fase 3 e podem ser
    trocados sem deploy.

    Leitura de uma linha: "compra de até `valor_ate` precisa de
    `aprovacoes_necessarias` aprovações distintas; se `exige_admin`, uma
    delas tem que ser de ADMIN/SUPER_ADMIN; se `exige_mapa_concorrencia`,
    a requisição precisa apontar para um MapaConcorrenciaV2 concluído com
    pelo menos dois fornecedores".

    `valor_ate = NULL` é o teto aberto — tem que existir exatamente uma
    faixa assim por tenant, e ela é sempre a de maior `ordem`.
    """
    __tablename__ = 'faixa_alcada'
    __table_args__ = (
        db.UniqueConstraint('admin_id', 'ordem', name='uq_faixa_alcada_admin_ordem'),
        db.Index('ix_faixa_alcada_admin_ativo', 'admin_id', 'ativo'),
    )

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'),
                         nullable=False, index=True)
    ordem = db.Column(db.Integer, nullable=False, default=1)
    # NULL = sem teto. Comparação é `valor <= valor_ate` (inclusivo): a
    # compra de exatamente R$ 5.000,00 fica na faixa de R$ 5.000,00.
    valor_ate = db.Column(db.Numeric(15, 2), nullable=True)
    aprovacoes_necessarias = db.Column(db.Integer, nullable=False, default=1)
    exige_admin = db.Column(db.Boolean, nullable=False, default=False)
    exige_mapa_concorrencia = db.Column(db.Boolean, nullable=False, default=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        teto = f'<= {self.valor_ate}' if self.valor_ate is not None else 'sem teto'
        return (f'<FaixaAlcada #{self.ordem} {teto} '
                f'{self.aprovacoes_necessarias} aprov>')
```

- [ ] **Step 4: Escreva o motor**

Crie `services/alcada_compras.py`:

```python
"""Motor de alçada de compras — Fase 3.

Responde a três perguntas, e só a essas três:
  1. Em que faixa cai este valor, neste tenant?   → faixa_para_valor
  2. Esta pessoa pode aprovar esta requisição?    → pode_aprovar
  3. Ainda falta alguma coisa para aprovar?       → pendencias_de_aprovacao

O registro da aprovação em si é uma RequisicaoTransicao com
`para_estado=AGUARDANDO_APROVACAO` e motivo prefixado — ver
`registrar_aprovacao`. Reutilizar a trilha existente evita uma segunda
tabela de histórico que teria de ser mantida em sincronia com a primeira.
"""
import logging
from decimal import Decimal

from models import (EstadoRequisicao, FaixaAlcada, MapaConcorrenciaV2,
                    RequisicaoTransicao, TipoUsuario, db)

logger = logging.getLogger('alcada_compras')

# Prefixo que marca uma RequisicaoTransicao como "voto de aprovação"
# (transição AGUARDANDO_APROVACAO → AGUARDANDO_APROVACAO) em vez de uma
# mudança de estado de verdade. É o que permite N aprovações sem N estados.
MARCA_APROVACAO = '[aprovacao]'

# Faixas RECOMENDADAS (Fase 3, decisão D1). Um só lugar: a migration 243
# importa desta constante, e `garantir_faixas_do_tenant` também — assim
# mudar a recomendação é mudar uma lista.
FAIXAS_RECOMENDADAS = [
    # (ordem, valor_ate, aprovacoes, exige_admin, exige_mapa)
    (1, Decimal('5000.00'), 1, False, False),
    (2, Decimal('30000.00'), 2, True, False),
    (3, None, 2, True, True),
]


class _FaixaSeguranca:
    """Faixa usada quando o tenant não tem NENHUMA faixa ativa.

    Falha FECHADA: exige o máximo (2 aprovações, uma de ADMIN), não o
    mínimo. Um tenant sem configuração não deve ser um tenant sem
    controle. Não é persistida — `id` é None de propósito, para que
    ninguém a confunda com uma faixa real ao debugar.
    """
    id = None
    ordem = 0
    valor_ate = None
    aprovacoes_necessarias = 2
    exige_admin = True
    exige_mapa_concorrencia = False
    ativo = True


def garantir_faixas_do_tenant(admin_id):
    """Semeia as faixas recomendadas se o tenant não tiver nenhuma.

    Idempotente: só age quando a contagem é zero. NÃO commita.
    Chamada pela migration 243 (para os tenants existentes) e pela rota de
    criação de requisição (para tenants criados depois da migração).
    """
    if FaixaAlcada.query.filter_by(admin_id=admin_id).count() > 0:
        return False
    for ordem, valor_ate, aprov, exige_admin, exige_mapa in FAIXAS_RECOMENDADAS:
        db.session.add(FaixaAlcada(
            admin_id=admin_id, ordem=ordem, valor_ate=valor_ate,
            aprovacoes_necessarias=aprov, exige_admin=exige_admin,
            exige_mapa_concorrencia=exige_mapa, ativo=True))
    db.session.flush()
    logger.info('faixas de alçada semeadas para o tenant %s', admin_id)
    return True


def faixa_para_valor(admin_id, valor):
    """A faixa ativa de menor teto que ainda cobre `valor`.

    Ordena por `valor_ate` com NULLs por último (o teto aberto é sempre a
    última opção) e devolve a primeira que cobre. Sem faixa ativa alguma,
    devolve `_FaixaSeguranca`.
    """
    valor = Decimal(str(valor or 0))
    faixas = (FaixaAlcada.query
              .filter_by(admin_id=admin_id, ativo=True)
              .order_by(FaixaAlcada.valor_ate.asc().nullslast(),
                        FaixaAlcada.ordem.asc())
              .all())
    if not faixas:
        logger.warning('tenant %s sem faixa de alçada ativa — faixa de '
                       'segurança aplicada', admin_id)
        return _FaixaSeguranca()

    for faixa in faixas:
        if faixa.valor_ate is None or valor <= faixa.valor_ate:
            return faixa

    # Só chega aqui se nenhuma faixa tem teto aberto e o valor passou de
    # todas. Também é falha fechada: a mais restritiva vale.
    logger.warning('tenant %s: valor %s acima de todas as faixas — aplicando '
                   'a de maior teto', admin_id, valor)
    return faixas[-1]


def votos_de_aprovacao(requisicao):
    """As RequisicaoTransicao que são voto de aprovação, em ordem."""
    return (RequisicaoTransicao.query
            .filter_by(requisicao_id=requisicao.id)
            .filter(RequisicaoTransicao.motivo.like(f'{MARCA_APROVACAO}%'))
            .order_by(RequisicaoTransicao.id)
            .all())


def aprovacoes_registradas(requisicao):
    """Quantas PESSOAS DISTINTAS já aprovaram."""
    return len({v.usuario_id for v in votos_de_aprovacao(requisicao)})


def _tem_aprovacao_de_admin(requisicao):
    return any(v.papel_aplicado == 'ADMIN' for v in votos_de_aprovacao(requisicao))


def _mapa_serve_de_concorrencia(requisicao):
    """Mapa V2 concluído, do mesmo tenant e da mesma obra, com >= 2
    fornecedores. Um fornecedor só não é concorrência — é orçamento."""
    if not requisicao.mapa_v2_id:
        return False
    mapa = db.session.get(MapaConcorrenciaV2, requisicao.mapa_v2_id)
    if mapa is None:
        return False
    if mapa.obra_id != requisicao.obra_id or mapa.admin_id != requisicao.admin_id:
        return False
    if mapa.status != 'concluido':
        return False
    return len(mapa.fornecedores) >= 2


def pendencias_de_aprovacao(requisicao):
    """Lista de textos do que ainda falta. Vazia = pode ir para APROVADA.

    Devolve texto porque é o que a tela mostra — e porque o motivo de uma
    requisição estar parada tem que ser legível sem ler código.
    """
    faixa = faixa_para_valor(requisicao.admin_id, requisicao.valor_estimado)
    faltando = []

    registradas = aprovacoes_registradas(requisicao)
    if registradas < faixa.aprovacoes_necessarias:
        restam = faixa.aprovacoes_necessarias - registradas
        faltando.append(
            f'faltam {restam} aprovação(ões) de {faixa.aprovacoes_necessarias}')

    if faixa.exige_admin and not _tem_aprovacao_de_admin(requisicao):
        faltando.append('falta a aprovação de um administrador')

    if faixa.exige_mapa_concorrencia and not _mapa_serve_de_concorrencia(requisicao):
        faltando.append('falta mapa de concorrência concluído com pelo menos '
                        '2 fornecedores vinculado a esta requisição')

    return faltando


def esta_totalmente_aprovada(requisicao):
    return not pendencias_de_aprovacao(requisicao)


def pode_aprovar(requisicao, usuario):
    """(bool, motivo). O motivo é exibido ao usuário — escreva para humano.

    A ordem das checagens é do mais estrutural para o mais circunstancial,
    para que a mensagem seja a mais informativa possível.
    """
    if usuario is None or not getattr(usuario, 'id', None):
        return False, 'Usuário não identificado.'

    if requisicao.estado != EstadoRequisicao.AGUARDANDO_APROVACAO:
        return False, (f'A requisição está em {requisicao.estado.value} — '
                       f'só se aprova o que está aguardando aprovação.')

    # SEPARAÇÃO DE FUNÇÕES — sem exceção, nem para ADMIN. Numa empresa
    # pequena a mesma pessoa acumula papéis; é exatamente aí que a regra
    # precisa valer.
    if requisicao.solicitante_id == usuario.id:
        return False, ('Você é o solicitante desta requisição e não pode '
                       'aprová-la. Peça a outra pessoa com alçada.')

    if any(v.usuario_id == usuario.id for v in votos_de_aprovacao(requisicao)):
        return False, 'Você já aprovou esta requisição.'

    if usuario.tipo_usuario in (TipoUsuario.ADMIN, TipoUsuario.SUPER_ADMIN):
        if usuario.id != requisicao.admin_id and \
                getattr(usuario, 'admin_id', None) != requisicao.admin_id:
            return False, 'Requisição de outra empresa.'
        return True, ''

    # Não-admin: precisa ser GESTOR da obra (Fase 1, usuario_obra).
    from utils.autorizacao import PAPEIS_QUE_EDITAM_OBRA, papel_na_obra
    papel = papel_na_obra(requisicao.obra_id)
    if papel in PAPEIS_QUE_EDITAM_OBRA:
        return True, ''
    return False, ('Você não é gestor desta obra e não tem alçada para '
                   'aprovar esta requisição.')


def papel_para_alcada(usuario, requisicao):
    """Com que chapéu o voto será registrado."""
    if usuario.tipo_usuario in (TipoUsuario.ADMIN, TipoUsuario.SUPER_ADMIN):
        return 'ADMIN'
    from utils.autorizacao import papel_na_obra
    papel = papel_na_obra(requisicao.obra_id)
    return papel.name if papel is not None else 'DESCONHECIDO'


def registrar_aprovacao(requisicao, usuario, papel=None, observacao=None):
    """Grava UM voto de aprovação. NÃO commita, NÃO muda o estado.

    Quem muda o estado para APROVADA é a rota, depois de checar
    `esta_totalmente_aprovada`. Separar as duas coisas é o que permite N
    aprovações antes de uma única transição de estado.
    """
    motivo = MARCA_APROVACAO
    if observacao:
        motivo = f'{MARCA_APROVACAO} {observacao}'

    voto = RequisicaoTransicao(
        requisicao_id=requisicao.id,
        admin_id=requisicao.admin_id,
        de_estado=requisicao.estado,
        para_estado=requisicao.estado,   # voto não move o estado
        usuario_id=usuario.id,
        papel_aplicado=papel or papel_para_alcada(usuario, requisicao),
        valor_no_momento=requisicao.valor_estimado,
        motivo=motivo,
    )
    db.session.add(voto)
    db.session.flush()
    logger.info('voto de aprovacao: requisicao=%s usuario=%s papel=%s valor=%s',
                requisicao.numero, usuario.id, voto.papel_aplicado,
                requisicao.valor_estimado)
    return voto
```

- [ ] **Step 5: Escreva a migration 243 e registre**

Em `migrations.py`, antes de `def executar_migracoes():`, insira:

```python
def migration_243_faixa_alcada():
    """Fase 3 — tabela faixa_alcada + seed das faixas RECOMENDADAS.

    Os valores (R$ 5.000 / R$ 30.000 / acima) são a recomendação do plano
    da Fase 3, decisão D1 — a pergunta 3 da DEVOLUTIVA nunca foi
    respondida pelo negócio. São DADO, editável por tenant sem deploy.

    O seed roda para todo usuário ADMIN/SUPER_ADMIN existente. Tenants
    criados depois desta migração são semeados sob demanda por
    `services.alcada_compras.garantir_faixas_do_tenant`, chamado na
    criação da primeira requisição.
    """
    logger.info("[Migration 243] Iniciando — tabela faixa_alcada")

    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS faixa_alcada (
            id SERIAL PRIMARY KEY,
            admin_id INTEGER NOT NULL REFERENCES usuario(id),
            ordem INTEGER NOT NULL DEFAULT 1,
            valor_ate NUMERIC(15,2),
            aprovacoes_necessarias INTEGER NOT NULL DEFAULT 1,
            exige_admin BOOLEAN NOT NULL DEFAULT FALSE,
            exige_mapa_concorrencia BOOLEAN NOT NULL DEFAULT FALSE,
            ativo BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """))
    db.session.commit()

    db.session.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_faixa_alcada_admin_ordem
        ON faixa_alcada (admin_id, ordem)
    """))
    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_faixa_alcada_admin_ativo
        ON faixa_alcada (admin_id, ativo)
    """))
    db.session.commit()

    # Seed por tenant. INSERT ... SELECT com NOT EXISTS: idempotente e sem
    # laço em Python sobre 6.479 admins (o banco de desenvolvimento tem
    # essa volumetria de suíte — ESTADO-ATUAL.md, armadilha 1).
    from services.alcada_compras import FAIXAS_RECOMENDADAS

    for ordem, valor_ate, aprov, exige_admin, exige_mapa in FAIXAS_RECOMENDADAS:
        db.session.execute(text("""
            INSERT INTO faixa_alcada
                (admin_id, ordem, valor_ate, aprovacoes_necessarias,
                 exige_admin, exige_mapa_concorrencia, ativo)
            SELECT u.id, :ordem, :valor_ate, :aprov, :exige_admin,
                   :exige_mapa, TRUE
            FROM usuario u
            WHERE u.tipo_usuario IN ('ADMIN', 'SUPER_ADMIN')
              AND NOT EXISTS (
                  SELECT 1 FROM faixa_alcada f
                  WHERE f.admin_id = u.id AND f.ordem = :ordem
              )
        """), {
            'ordem': ordem,
            'valor_ate': valor_ate,
            'aprov': aprov,
            'exige_admin': exige_admin,
            'exige_mapa': exige_mapa,
        })
    db.session.commit()

    total = db.session.execute(
        text("SELECT COUNT(*) FROM faixa_alcada")).scalar()
    logger.info("[Migration 243] Concluída com sucesso — %s faixas", total)
```

Registre em `migrations_to_run`, após a entrada `242`:

```python
            (243, "Fase 3 — faixa_alcada + seed das faixas recomendadas (5k / 30k / acima) por tenant", migration_243_faixa_alcada),
```

> **Atenção ao seed:** `usuario.tipo_usuario` é enum nativo do Postgres (`models.py:35`, `db.Enum(TipoUsuario)`), e os rótulos gravados são os **nomes** dos membros (`'ADMIN'`, `'SUPER_ADMIN'`), não os valores. Se o `SELECT` devolver zero linhas num banco onde existem admins, confira o rótulo com:
> `SELECT DISTINCT tipo_usuario FROM usuario;`

- [ ] **Step 6: Aplique e rode**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "243|ERRO|ERROR"
python -m pytest tests/test_fase3_alcada.py -v
```

Esperado: `[Migration 243] Concluída com sucesso — <n> faixas` e os 12 testes PASSAM.

- [ ] **Step 7: Commit**

```bash
git add models.py migrations.py services/alcada_compras.py tests/test_fase3_alcada.py
git commit -m "feat(fase3): alcada configuravel por tenant

FaixaAlcada e o motor que le a tabela. Nenhum valor em R$ dentro de if.
Faixas semeadas (5k/30k/acima) sao RECOMENDACAO do plano — a pergunta 3
da DEVOLUTIVA segue sem resposta do negocio, e a resposta e dado.
Separacao de funcoes e invariante: solicitante nunca aprova, nem ADMIN.
Tenant sem faixa cai numa faixa de seguranca que exige o MAXIMO."
```

---

## Task 4: `PapelObra.COMPRADOR` — o papel que a Fase 1 adiou

**Files:**
- Modify: `models.py` (`class PapelObra`, inserida pela Fase 1 logo após `TipoUsuario`)
- Modify: `migrations.py` (migration 245 + registro)
- Modify: `utils/autorizacao.py` (novos predicados)
- Test: `tests/test_fase3_alcada.py` (acrescenta)

> **Por que aqui e não na Fase 1.** A Fase 1 escreveu, na docstring do enum: *"Deliberadamente três valores. COMPRADOR entra na Fase 3, quando a governança de compras existir para consumi-lo — antes disso seria permissão sem verbo."* Os verbos existem agora: **criar requisição** (Task 6) e **emitir pedido de compra** (Task 8). Um papel sem rota que o consulte é o erro que `TipoUsuario.ALMOXARIFE` cometeu — ele está no enum desde o Módulo 4 (`models.py:25`) e tem **zero** rotas, zero templates e zero testes até hoje.

- [ ] **Step 1: Confirme como a Fase 1 materializou a coluna `papel`**

Isto decide se a migration 245 precisa de DDL ou não. Não pule.

```bash
python - <<'PY'
from app import app, db
from sqlalchemy import text
with app.app_context():
    linha = db.session.execute(text("""
        SELECT data_type, udt_name
        FROM information_schema.columns
        WHERE table_name='usuario_obra' AND column_name='papel'
    """)).fetchone()
    print('usuario_obra.papel →', linha)
    if linha and linha[0] == 'USER-DEFINED':
        print('rótulos atuais:', db.session.execute(text(
            "SELECT enumlabel FROM pg_enum e "
            "JOIN pg_type t ON t.oid = e.enumtypid "
            "WHERE t.typname = :n ORDER BY e.enumsortorder"
        ), {'n': linha[1]}).scalars().all())
PY
```

Duas saídas possíveis, e as duas são esperadas:

- `('USER-DEFINED', 'papelobra')` — a coluna é **enum nativo**. É o caso do banco novo: `db.create_all()` roda em `app.py:582`, **antes** de `executar_migracoes()` em `app.py:666`, e cria a tabela a partir do modelo, que declara `db.Enum(PapelObra)`. O `CREATE TABLE IF NOT EXISTS` da migration 215 vira no-op. **Precisa de `ALTER TYPE ... ADD VALUE`.**
- `('character varying', 'varchar')` — a coluna é VARCHAR, criada pelo DDL da migration 215. Acrescentar um membro ao enum Python não exige DDL nenhum.

A migration 245 abaixo trata os dois casos. Anote qual apareceu no seu ambiente.

- [ ] **Step 2: Escreva o teste que falha**

Acrescente ao final de `tests/test_fase3_alcada.py`:

```python
# ---------------------------------------------------------------------------
# PapelObra.COMPRADOR
# ---------------------------------------------------------------------------

def test_papel_obra_ganhou_comprador():
    """A Fase 1 parou em GESTOR/APONTADOR/LEITOR de propósito. O COMPRADOR
    só entra quando existem verbos: criar requisição e emitir pedido."""
    assert {p.name for p in PapelObra} == {
        'GESTOR', 'APONTADOR', 'LEITOR', 'COMPRADOR'}


def test_comprador_persiste_no_vinculo():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        op = _operador(admin.id)
        v = _vincular(op, obra, PapelObra.COMPRADOR)
        vid = v.id

    with app.app_context():
        recarregado = db.session.get(UsuarioObra, vid)
        assert recarregado.papel == PapelObra.COMPRADOR


def test_comprador_requisita_mas_nao_edita_a_obra():
    """COMPRADOR não é GESTOR de bolso: ele pede e emite, não manda na obra."""
    from utils.autorizacao import (PAPEIS_QUE_COMPRAM, PAPEIS_QUE_EDITAM_OBRA,
                                   PAPEIS_QUE_REQUISITAM)

    assert PapelObra.COMPRADOR in PAPEIS_QUE_REQUISITAM
    assert PapelObra.COMPRADOR in PAPEIS_QUE_COMPRAM
    assert PapelObra.COMPRADOR not in PAPEIS_QUE_EDITAM_OBRA


def test_gestor_requisita_mas_nao_emite_pedido():
    """Separação de funções no nível do papel: quem aprova não emite."""
    from utils.autorizacao import PAPEIS_QUE_COMPRAM, PAPEIS_QUE_REQUISITAM

    assert PapelObra.GESTOR in PAPEIS_QUE_REQUISITAM
    assert PapelObra.GESTOR not in PAPEIS_QUE_COMPRAM


def test_apontador_e_leitor_nao_requisitam():
    from utils.autorizacao import PAPEIS_QUE_REQUISITAM

    assert PapelObra.APONTADOR not in PAPEIS_QUE_REQUISITAM
    assert PapelObra.LEITOR not in PAPEIS_QUE_REQUISITAM


def test_predicados_de_obra_respondem_pelo_vinculo():
    from utils.autorizacao import pode_comprar_na_obra, pode_requisitar_na_obra

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        comprador = _operador(admin.id, 'Comprador')
        leitor = _operador(admin.id, 'Leitor')
        _vincular(comprador, obra, PapelObra.COMPRADOR)
        _vincular(leitor, obra, PapelObra.LEITOR)
        oid, cid, lid = obra.id, comprador.id, leitor.id

    cliente = app.test_client()
    with cliente.session_transaction() as sess:
        sess['_user_id'] = str(cid)
        sess['_fresh'] = True
    with app.test_request_context():
        from flask_login import login_user
        with app.app_context():
            login_user(db.session.get(Usuario, cid))
            assert pode_requisitar_na_obra(oid) is True
            assert pode_comprar_na_obra(oid) is True

    with app.test_request_context():
        from flask_login import login_user
        with app.app_context():
            login_user(db.session.get(Usuario, lid))
            assert pode_requisitar_na_obra(oid) is False
            assert pode_comprar_na_obra(oid) is False
```

- [ ] **Step 3: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase3_alcada.py -v -k "comprador or requisita or apontador or predicados"
```

Esperado: FAIL — `AttributeError: COMPRADOR` no enum e `ImportError` de `PAPEIS_QUE_REQUISITAM`.

- [ ] **Step 4: Acrescente o membro ao enum**

Em `models.py`, dentro da `class PapelObra` que a Fase 1 criou, **depois** de `LEITOR`, insira:

```python
    COMPRADOR = "comprador"  # requisita e emite pedido; NÃO aprova e NÃO edita a obra
```

E substitua o parágrafo final da docstring do enum (o que diz *"Deliberadamente três valores. COMPRADOR entra na Fase 3..."*) por:

```python
    """
    ...
    COMPRADOR entrou na Fase 3, quando passaram a existir verbos para
    ele: criar requisição de compra e emitir pedido a partir de
    requisição aprovada (compras_views.py). Ele NÃO aprova — quem aprova
    é GESTOR ou ADMIN, e a separação de funções é checada em
    services/alcada_compras.pode_aprovar.
    """
```

- [ ] **Step 5: Escreva a migration 245 e registre**

Em `migrations.py`, antes de `def executar_migracoes():`, insira:

```python
def migration_245_papel_obra_comprador():
    """Fase 3 — acrescenta COMPRADOR ao papel de obra.

    PRIMEIRA extensão de enum nativo deste repositório: até 2026-07-21,
    `grep -rn "ALTER TYPE|ADD VALUE" migrations.py` devolvia zero.

    Trata as duas formas em que a coluna `usuario_obra.papel` pode existir:

      * VARCHAR — foi o DDL da migration 215 (Fase 1) que criou a tabela.
        Nada a fazer: o SQLAlchemy grava o NOME do membro e a coluna
        aceita qualquer string do tamanho.
      * enum nativo — `db.create_all()` (app.py:582) criou a tabela ANTES
        da migração, a partir de `db.Enum(PapelObra)`. Aqui é preciso
        `ALTER TYPE ... ADD VALUE`.

    `ALTER TYPE ... ADD VALUE` **não pode rodar dentro de um bloco de
    transação** em Postgres < 12, e mesmo em 12+ o valor novo não pode ser
    usado na mesma transação. Por isso a conexão abaixo é aberta em
    AUTOCOMMIT, fora da sessão do SQLAlchemy.
    """
    from sqlalchemy import text as sa_text

    logger.info("[Migration 245] Iniciando — PapelObra.COMPRADOR")

    linha = db.session.execute(sa_text("""
        SELECT data_type, udt_name
        FROM information_schema.columns
        WHERE table_name = 'usuario_obra' AND column_name = 'papel'
    """)).fetchone()

    if linha is None:
        logger.error("[Migration 245] usuario_obra.papel não existe — a "
                     "Fase 1 (migration 215) não foi aplicada. Abortando.")
        raise RuntimeError('migration 215 (usuario_obra) é pré-requisito da 245')

    data_type, udt_name = linha[0], linha[1]

    if data_type != 'USER-DEFINED':
        logger.info("[Migration 245] usuario_obra.papel é %s — nenhum DDL "
                    "necessário, o membro novo do enum Python basta.", data_type)
        logger.info("[Migration 245] Concluída com sucesso")
        return

    rotulos = db.session.execute(sa_text("""
        SELECT e.enumlabel
        FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid
        WHERE t.typname = :nome
    """), {'nome': udt_name}).scalars().all()

    if 'COMPRADOR' in rotulos:
        logger.info("[Migration 245] COMPRADOR já existe em %s — no-op.", udt_name)
        logger.info("[Migration 245] Concluída com sucesso")
        return

    # Fora da sessão: ADD VALUE exige autocommit.
    with db.engine.connect() as conn:
        conn = conn.execution_options(isolation_level='AUTOCOMMIT')
        conn.execute(sa_text(
            f'ALTER TYPE {udt_name} ADD VALUE IF NOT EXISTS \'COMPRADOR\''))
    logger.info("[Migration 245] COMPRADOR adicionado ao tipo %s", udt_name)
    logger.info("[Migration 245] Concluída com sucesso")
```

Registre em `migrations_to_run`, após a entrada `244` (que a Task 8 acrescenta) — ou, se você estiver executando as tasks em ordem e a 244 ainda não existir, logo após a `243`. A lista tem que ficar em ordem numérica crescente ao final da fase:

```python
            (245, "Fase 3 — PapelObra.COMPRADOR (estende o enum de papel de obra)", migration_245_papel_obra_comprador),
```

- [ ] **Step 6: Acrescente os predicados a `utils/autorizacao.py`**

Em `utils/autorizacao.py`, logo abaixo das constantes que a Fase 1 definiu (`PAPEIS_QUE_EDITAM_OBRA`, `PAPEIS_QUE_APONTAM`), insira:

```python
# Fase 3 — quem PEDE e quem COMPRA, por papel na obra.
#
# A assimetria entre as duas listas é a separação de funções no nível do
# papel, e é de propósito:
#   * GESTOR requisita e APROVA (services/alcada_compras.pode_aprovar),
#     mas NÃO emite pedido — quem aprova não emite.
#   * COMPRADOR requisita e EMITE, mas não aprova e não edita a obra.
#   * APONTADOR e LEITOR não fazem nem uma coisa nem outra.
# ADMIN/SUPER_ADMIN passam por cima das duas listas (papel_na_obra
# devolve GESTOR implícito para eles), e é por isso que a checagem de
# "não aprove a própria requisição" existe também para ADMIN.
PAPEIS_QUE_REQUISITAM = (PapelObra.GESTOR, PapelObra.COMPRADOR)
PAPEIS_QUE_COMPRAM = (PapelObra.COMPRADOR,)
```

E ao final do arquivo, **antes** do `obra_required` (ou depois, tanto faz — mas junto dos outros predicados `pode_*`):

```python
def pode_requisitar_na_obra(obra_id):
    """Criar/editar requisição de compra nesta obra. Fase 3."""
    papel = papel_na_obra(obra_id)
    if papel is None:
        return False
    if _e_admin_do_tenant():
        return True
    return papel in PAPEIS_QUE_REQUISITAM


def pode_comprar_na_obra(obra_id):
    """Emitir PedidoCompra a partir de requisição aprovada. Fase 3.

    ADMIN pode — não há como impedir o dono da empresa de comprar. Mas
    quando ele emite, `compras_views.requisicao_emitir_pedido` recusa se
    ele foi um dos aprovadores e a faixa exigia mais de uma aprovação
    (Task 8): a separação de funções sobrevive ao acúmulo de chapéus.
    """
    papel = papel_na_obra(obra_id)
    if papel is None:
        return False
    if _e_admin_do_tenant():
        return True
    return papel in PAPEIS_QUE_COMPRAM
```

- [ ] **Step 7: Aplique e rode**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "245|ERRO|ERROR"
python -m pytest tests/test_fase3_alcada.py -v
python -m pytest tests/test_fase1_escopo_obra.py -v
```

Esperado: `[Migration 245] Concluída com sucesso`, os testes da Fase 3 passam, **e os da Fase 1 não regridem**. Atenção: o teste `test_papel_obra_tem_os_tres_valores_da_fase_1` (Fase 1, Task 5) **vai falhar de propósito** — o enum agora tem quatro valores. Atualize-o no lugar, trocando a asserção por:

```python
def test_papel_obra_tem_os_valores_esperados():
    """Três na Fase 1; COMPRADOR entrou na Fase 3, com rota que o consome."""
    assert {p.name for p in PapelObra} == {
        'GESTOR', 'APONTADOR', 'LEITOR', 'COMPRADOR'}
```

- [ ] **Step 8: Commit**

```bash
git add models.py migrations.py utils/autorizacao.py tests/test_fase3_alcada.py tests/test_fase1_escopo_obra.py
git commit -m "feat(fase3): PapelObra.COMPRADOR com verbos que o consomem

A Fase 1 adiou este papel por ser permissao sem verbo. Agora ha dois:
criar requisicao e emitir pedido. Migration 245 e a PRIMEIRA extensao de
enum nativo do repo — trata tanto a coluna VARCHAR da migration 215
quanto o enum nativo que db.create_all (app.py:582) cria antes dela.

PAPEIS_QUE_REQUISITAM != PAPEIS_QUE_COMPRAM de proposito: quem aprova
nao emite."
```

---

## Task 5: Flag de rollout por tenant (`compras_governanca_ativa`)

**Files:**
- Modify: `models.py` (`class ConfiguracaoEmpresa`, junto de `cronograma_mpp_ativo` na linha 3620)
- Modify: `migrations.py` (migration 246 + registro)
- Create: `scripts/flag_compras_governanca.py`
- Test: `tests/test_fase3_requisicao.py` (acrescenta)

- [ ] **Step 1: Leia o precedente**

```bash
grep -n "cronograma_mpp_ativo" models.py migrations.py scripts/flag_cronograma_mpp.py | head -20
```

A flag nova é irmã dessa (`models.py:3620`), e da `escopo_obra_ativo` da Fase 1. Mesma forma, mesmo script, mesmo default `FALSE`.

- [ ] **Step 2: Escreva o teste que falha**

Acrescente ao final de `tests/test_fase3_requisicao.py`:

```python
# ---------------------------------------------------------------------------
# Flag de rollout
# ---------------------------------------------------------------------------

def test_governanca_nasce_desligada():
    """Ligada por padrão, o deploy quebraria o registro de compra de todo
    mundo no mesmo minuto."""
    from scripts.flag_compras_governanca import governanca_ativa

    with app.app_context():
        admin = _admin()
        assert governanca_ativa(admin.id) is False


def test_governanca_liga_e_desliga():
    from scripts.flag_compras_governanca import definir_flag, governanca_ativa

    with app.app_context():
        admin = _admin()
        definir_flag(admin.id, True)
        assert governanca_ativa(admin.id) is True
        definir_flag(admin.id, False)
        assert governanca_ativa(admin.id) is False


def test_flag_ilegivel_e_tratada_como_desligada():
    """Falha para o lado do comportamento antigo, não para o lado de
    travar o registro de compra de uma empresa em obra."""
    from scripts.flag_compras_governanca import governanca_ativa

    with app.app_context():
        assert governanca_ativa(None) is False
        assert governanca_ativa(-1) is False
```

- [ ] **Step 3: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase3_requisicao.py -v -k governanca
```

Esperado: FAIL — `ModuleNotFoundError: No module named 'scripts.flag_compras_governanca'`.

- [ ] **Step 4: Acrescente a coluna ao modelo**

Em `models.py`, dentro da `class ConfiguracaoEmpresa`, imediatamente após `cronograma_mpp_ativo` (linha 3620-3621), insira:

```python
    # Fase 3 — flag de rollout da governança de compras, por tenant.
    # Default FALSE: com ela desligada, `compras.nova_post` registra compra
    # exatamente como antes (compras_views.py:709-711) e as telas de
    # requisição existem como caminho OPCIONAL. Ligada, pedido sem
    # requisição aprovada é recusado. Liga-se por
    # scripts/flag_compras_governanca.py. Irmã de cronograma_mpp_ativo
    # (acima) e de escopo_obra_ativo (Fase 1).
    compras_governanca_ativa = db.Column(db.Boolean, nullable=False,
                                         default=False, server_default='false')
```

- [ ] **Step 5: Escreva a migration 246 e registre**

Em `migrations.py`, antes de `def executar_migracoes():`, insira:

```python
def migration_246_flag_compras_governanca():
    """Fase 3 — configuracao_empresa.compras_governanca_ativa.

    Aditiva, idempotente, e deliberadamente FALSE por padrão. O schema
    inteiro da Fase 3 é aditivo enquanto esta flag estiver desligada: o
    risco da fase está em LIGÁ-LA, não em aplicá-la. Ver
    docs/fase-3-rollout.md.
    """
    logger.info("[Migration 246] Iniciando — compras_governanca_ativa")

    db.session.execute(text("""
        ALTER TABLE configuracao_empresa
        ADD COLUMN IF NOT EXISTS compras_governanca_ativa
        BOOLEAN NOT NULL DEFAULT FALSE
    """))
    db.session.commit()

    logger.info("[Migration 246] Concluída com sucesso")
```

Registre em `migrations_to_run`:

```python
            (246, "Fase 3 — flag por tenant compras_governanca_ativa (default FALSE)", migration_246_flag_compras_governanca),
```

- [ ] **Step 6: Escreva o script de flag**

Crie `scripts/flag_compras_governanca.py`:

```python
#!/usr/bin/env python3
"""Liga/desliga a governança de compras por tenant — Fase 3.

Uso:
    python scripts/flag_compras_governanca.py <admin_id> --ligar
    python scripts/flag_compras_governanca.py <admin_id> --desligar
    python scripts/flag_compras_governanca.py <admin_id>          # consulta

Ligar a flag muda comportamento de produção: `POST /compras/nova` passa a
recusar pedido sem requisição aprovada. O guard do `--ligar` recusa
tenants que ainda não têm faixa de alçada configurada — ligar sem faixa
faria toda compra cair na faixa de segurança (2 aprovações + ADMIN) e
travaria o canteiro.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def governanca_ativa(admin_id):
    """True se o tenant tem a governança ligada. Falha FECHADA para o
    comportamento ANTIGO: qualquer erro devolve False."""
    if not admin_id:
        return False
    try:
        from models import ConfiguracaoEmpresa
        cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
        return bool(cfg and cfg.compras_governanca_ativa)
    except Exception:
        return False


def definir_flag(admin_id, valor):
    """Grava a flag, criando a ConfiguracaoEmpresa se ela não existir.

    `nome_empresa` é NOT NULL (models.py:3596); num tenant que nunca abriu
    a tela de configurações a linha não existe, e é preciso criá-la com um
    nome provisório em vez de estourar.
    """
    from app import db
    from models import ConfiguracaoEmpresa, Usuario

    cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    if cfg is None:
        usuario = db.session.get(Usuario, admin_id)
        cfg = ConfiguracaoEmpresa(
            admin_id=admin_id,
            nome_empresa=(usuario.nome if usuario else f'Tenant {admin_id}'))
        db.session.add(cfg)
    cfg.compras_governanca_ativa = bool(valor)
    db.session.commit()
    return cfg.compras_governanca_ativa


def _tem_faixa(admin_id):
    from models import FaixaAlcada
    return FaixaAlcada.query.filter_by(admin_id=admin_id, ativo=True).count() > 0


def main():
    parser = argparse.ArgumentParser(description='Flag de governança de compras')
    parser.add_argument('admin_id', type=int)
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument('--ligar', action='store_true')
    grupo.add_argument('--desligar', action='store_true')
    parser.add_argument('--forcar', action='store_true',
                        help='liga mesmo sem faixa de alçada configurada')
    args = parser.parse_args()

    from app import app
    with app.app_context():
        if args.ligar:
            if not _tem_faixa(args.admin_id) and not args.forcar:
                print(f'RECUSADO: tenant {args.admin_id} não tem faixa de '
                      f'alçada ativa. Toda compra cairia na faixa de '
                      f'segurança (2 aprovações + ADMIN). Rode a migration '
                      f'243 ou use --forcar se for isso mesmo.')
                return 1
            definir_flag(args.admin_id, True)
            print(f'tenant {args.admin_id}: governança de compras LIGADA')
        elif args.desligar:
            definir_flag(args.admin_id, False)
            print(f'tenant {args.admin_id}: governança de compras DESLIGADA')
        else:
            estado = 'LIGADA' if governanca_ativa(args.admin_id) else 'DESLIGADA'
            print(f'tenant {args.admin_id}: governança de compras {estado}')
        return 0


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 7: Aplique e rode**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "246|ERRO|ERROR"
python -m pytest tests/test_fase3_requisicao.py -v -k governanca
```

Esperado: `[Migration 246] Concluída com sucesso` e os 3 testes PASSAM.

- [ ] **Step 8: Commit**

```bash
git add models.py migrations.py scripts/flag_compras_governanca.py tests/test_fase3_requisicao.py
git commit -m "feat(fase3): flag de rollout compras_governanca_ativa

Default FALSE, irma de cronograma_mpp_ativo e de escopo_obra_ativo. Todo
o schema da fase e aditivo enquanto ela estiver desligada — o risco esta
em ligar. O --ligar recusa tenant sem faixa de alcada, que cairia na
faixa de seguranca e travaria o canteiro."
```

---

## Task 6: Rotas de requisição — listar, criar, detalhar

**Files:**
- Modify: `compras_views.py` (imports no topo; rotas ao final, após a linha 1049)
- Create: `templates/compras/requisicoes.html`
- Create: `templates/compras/requisicao_nova.html`
- Create: `templates/compras/requisicao_detalhe.html`
- Modify: `templates/base_completo.html:958-968` (menu)
- Test: `tests/test_fase3_requisicao.py` (acrescenta)

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao final de `tests/test_fase3_requisicao.py`:

```python
# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


@pytest.mark.parametrize('rota', [
    '/compras/requisicoes',
    '/compras/requisicoes/nova',
])
def test_rotas_de_requisicao_exigem_login(rota):
    anon = app.test_client()
    r = anon.get(rota, follow_redirects=False)
    assert r.status_code in (302, 401), (
        f'{rota} devolveu {r.status_code} para anônimo')


def test_listagem_abre_para_admin():
    with app.app_context():
        admin = _admin()
        aid = admin.id
    r = _cliente_de(aid).get('/compras/requisicoes')
    assert r.status_code == 200


def test_criar_requisicao_gera_numero_e_itens():
    from models import RequisicaoCompraItem

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        aid, oid = admin.id, obra.id

    r = _cliente_de(aid).post('/compras/requisicoes/nova', data={
        'obra_id': str(oid),
        'justificativa': 'Perfis para o painel P3',
        'data_necessidade': '2026-08-15',
        'item_descricao[]': ['Perfil U90', 'Parafuso GN25'],
        'item_unidade[]': ['m', 'cx'],
        'item_quantidade[]': ['120', '4'],
        'item_preco[]': ['18,50', '89,90'],
        'item_almoxarifado_id[]': ['', ''],
    }, follow_redirects=False)
    assert r.status_code == 302

    with app.app_context():
        req = RequisicaoCompra.query.filter_by(admin_id=aid).one()
        assert req.numero.startswith('RC-')
        assert req.obra_id == oid
        assert req.estado == EstadoRequisicao.RASCUNHO
        assert req.valor_estimado == Decimal('2579.60')
        assert RequisicaoCompraItem.query.filter_by(
            requisicao_id=req.id).count() == 2


def test_requisicao_sem_obra_e_recusada():
    with app.app_context():
        admin = _admin()
        aid = admin.id

    r = _cliente_de(aid).post('/compras/requisicoes/nova', data={
        'obra_id': '',
        'justificativa': 'sem obra',
        'item_descricao[]': ['Qualquer'],
        'item_quantidade[]': ['1'],
        'item_preco[]': ['10'],
    }, follow_redirects=False)
    assert r.status_code == 302
    with app.app_context():
        assert RequisicaoCompra.query.filter_by(admin_id=aid).count() == 0


def test_obra_de_outro_tenant_e_recusada():
    with app.app_context():
        a1, a2 = _admin('A'), _admin('B')
        obra_b = _obra(a2.id)
        aid, oid_b = a1.id, obra_b.id

    r = _cliente_de(aid).post('/compras/requisicoes/nova', data={
        'obra_id': str(oid_b),
        'justificativa': 'atravessando tenant',
        'item_descricao[]': ['X'],
        'item_quantidade[]': ['1'],
        'item_preco[]': ['10'],
    }, follow_redirects=False)
    assert r.status_code == 302
    with app.app_context():
        assert RequisicaoCompra.query.filter_by(admin_id=aid).count() == 0


def test_detalhe_de_requisicao_de_outro_tenant_devolve_404():
    with app.app_context():
        a1, a2 = _admin('A'), _admin('B')
        obra_b = _obra(a2.id)
        req = RequisicaoCompra(numero='RC-2026-0001', obra_id=obra_b.id,
                               solicitante_id=a2.id, admin_id=a2.id)
        db.session.add(req)
        db.session.commit()
        aid, rid = a1.id, req.id

    r = _cliente_de(aid).get(f'/compras/requisicoes/{rid}')
    assert r.status_code == 404


def test_enviar_para_aprovacao_muda_o_estado():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        op = _operador(admin.id)
        from services.requisicao_compra import proximo_numero
        req = RequisicaoCompra(
            numero=proximo_numero(admin.id), obra_id=obra.id,
            solicitante_id=op.id, admin_id=admin.id,
            valor_estimado=Decimal('100.00'))
        db.session.add(req)
        db.session.commit()
        opid, rid = op.id, req.id

    r = _cliente_de(opid).post(f'/compras/requisicoes/{rid}/enviar',
                               follow_redirects=False)
    assert r.status_code == 302
    with app.app_context():
        assert db.session.get(RequisicaoCompra, rid).estado == \
            EstadoRequisicao.AGUARDANDO_APROVACAO


def test_requisicao_sem_item_nao_vai_para_aprovacao():
    """Requisição vazia aprovada é assinatura em branco."""
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        from services.requisicao_compra import proximo_numero
        req = RequisicaoCompra(
            numero=proximo_numero(admin.id), obra_id=obra.id,
            solicitante_id=admin.id, admin_id=admin.id,
            valor_estimado=Decimal('0.00'))
        db.session.add(req)
        db.session.commit()
        aid, rid = admin.id, req.id

    _cliente_de(aid).post(f'/compras/requisicoes/{rid}/enviar',
                          follow_redirects=False)
    with app.app_context():
        assert db.session.get(RequisicaoCompra, rid).estado == \
            EstadoRequisicao.RASCUNHO
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase3_requisicao.py -v -k "rotas_de_requisicao or listagem or criar_requisicao or sem_obra or outro_tenant or enviar or sem_item"
```

Esperado: FAIL — 404 em todas as rotas (não existem).

- [ ] **Step 3: Acrescente os imports em `compras_views.py`**

Substitua o bloco de import de `models` (linhas 10-12) por:

```python
from models import (AlmoxarifadoItem, AlmoxarifadoEstoque, AlmoxarifadoMovimento,
                    ContaPagar, EstadoRequisicao, Fornecedor, Funcionario,
                    MapaConcorrenciaV2, Obra, ObraServicoCusto, PedidoCompra,
                    PedidoCompraItem, RequisicaoCompra, RequisicaoCompraItem,
                    GestaoCustoPai, GestaoCustoFilho, Usuario)
```

E logo abaixo de `from utils.tenant import get_tenant_admin_id, is_v2_active` (linha 13), acrescente:

```python
# Fase 3 — governança de compras. Imports no topo de propósito: estes
# módulos não importam compras_views de volta, então não há ciclo.
from services.alcada_compras import (esta_totalmente_aprovada,
                                     garantir_faixas_do_tenant,
                                     faixa_para_valor,
                                     pendencias_de_aprovacao, pode_aprovar,
                                     registrar_aprovacao)
from services.requisicao_compra import (TransicaoInvalida, proximo_numero,
                                        recalcular_valor, transicionar)
from utils.autorizacao import (obras_visiveis, pode_comprar_na_obra,
                               pode_requisitar_na_obra, pode_ver_obra)
```

- [ ] **Step 4: Acrescente as rotas ao final de `compras_views.py`**

Ao final do arquivo (depois da rota `excluir`, linha 1049), acrescente:

```python
# ═════════════════════════════════════════════════════════════════════════════
# FASE 3 — REQUISIÇÃO DE COMPRA (requisição → aprovação → pedido)
# ═════════════════════════════════════════════════════════════════════════════
#
# Estas rotas existem SEMPRE. O que a flag `compras_governanca_ativa`
# muda é apenas se `POST /compras/nova` continua aceitando pedido sem
# requisição (Task 9). Com a flag desligada, este é um caminho opcional
# que não tira nada de ninguém.


def _requisicao_do_tenant(requisicao_id):
    """Carrega a requisição do tenant logado ou aborta com 404.

    404 e não 403, pela mesma razão do `obra_required` da Fase 1: não
    vazar sequer a existência de documento de outra empresa.
    """
    from flask import abort

    admin_id = _admin_id()
    if admin_id is None:
        abort(404)
    req = RequisicaoCompra.query.filter_by(
        id=requisicao_id, admin_id=admin_id).first()
    if req is None:
        abort(404)
    return req


def _itens_do_form():
    """Lê os itens do formulário. Devolve lista de dicts, ignorando linhas
    sem descrição (o formulário mantém uma linha-modelo vazia)."""
    descricoes = request.form.getlist('item_descricao[]')
    unidades = request.form.getlist('item_unidade[]')
    quantidades = request.form.getlist('item_quantidade[]')
    precos = request.form.getlist('item_preco[]')
    almox_ids = request.form.getlist('item_almoxarifado_id[]')

    itens = []
    for i, desc in enumerate(descricoes):
        desc = (desc or '').strip()
        if not desc:
            continue

        def _num(lista, idx, padrao='0'):
            bruto = (lista[idx] if idx < len(lista) else '') or padrao
            return float(str(bruto).replace('.', '').replace(',', '.')
                         if ',' in str(bruto) else str(bruto))

        almox_bruto = almox_ids[i] if i < len(almox_ids) else ''
        itens.append({
            'descricao': desc[:200],
            'unidade': ((unidades[i] if i < len(unidades) else '') or 'un')[:20],
            'quantidade': _num(quantidades, i, '1'),
            'preco': _num(precos, i, '0'),
            'almoxarifado_item_id': int(almox_bruto) if almox_bruto else None,
        })
    return itens


@compras_bp.route('/requisicoes')
@login_required
def requisicoes():
    """Lista de requisições do tenant, filtrada pelo escopo de obra."""
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    estado_filtro = (request.args.get('estado') or '').strip().upper()

    query = RequisicaoCompra.query.filter_by(admin_id=admin_id)

    # Fase 1 — escopo por obra. `obras_visiveis()` já aplica os dois eixos
    # (tenant sempre; obra só com a flag do tenant ligada). Sem isso, a
    # listagem repetiria o erro de `compras_views.py:421`, que filtra só
    # por admin_id.
    ids_visiveis = [o.id for o in obras_visiveis(admin_id).with_entities(Obra.id)]
    query = query.filter(RequisicaoCompra.obra_id.in_(ids_visiveis or [-1]))

    if estado_filtro in {e.name for e in EstadoRequisicao}:
        query = query.filter(RequisicaoCompra.estado ==
                             EstadoRequisicao[estado_filtro])

    requisicoes_lista = query.order_by(RequisicaoCompra.id.desc()).limit(200).all()

    contagem = {}
    for estado in EstadoRequisicao:
        contagem[estado.name] = sum(
            1 for r in requisicoes_lista if r.estado == estado)

    return render_template(
        'compras/requisicoes.html',
        requisicoes=requisicoes_lista,
        contagem=contagem,
        estado_filtro=estado_filtro,
        estados=list(EstadoRequisicao),
    )


@compras_bp.route('/requisicoes/nova', methods=['GET'])
@login_required
def requisicao_nova():
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()
    obras = obras_visiveis(admin_id).filter(Obra.ativo.is_(True)).order_by(
        Obra.nome).all()
    itens_catalogo = AlmoxarifadoItem.query.filter_by(
        admin_id=admin_id).order_by(AlmoxarifadoItem.nome).all()

    return render_template(
        'compras/requisicao_nova.html',
        obras=obras,
        itens_catalogo=itens_catalogo,
        hoje=date.today().isoformat(),
    )


@compras_bp.route('/requisicoes/nova', methods=['POST'])
@login_required
def requisicao_nova_post():
    guard = _check_v2()
    if guard:
        return guard

    admin_id = _admin_id()

    obra_id_bruto = (request.form.get('obra_id') or '').strip()
    if not obra_id_bruto:
        flash('Toda requisição precisa de uma obra. É o vínculo que faz o '
              'custo aparecer no lugar certo.', 'danger')
        return redirect(url_for('compras.requisicao_nova'))
    try:
        obra_id = int(obra_id_bruto)
    except (TypeError, ValueError):
        flash('Obra inválida. Selecione uma obra pelo menu.', 'danger')
        return redirect(url_for('compras.requisicao_nova'))

    # Defesa de tenant + escopo de obra (Fase 1) num só predicado.
    if not pode_ver_obra(obra_id):
        flash('Obra não encontrada ou fora do seu acesso.', 'danger')
        return redirect(url_for('compras.requisicao_nova'))
    if not pode_requisitar_na_obra(obra_id):
        flash('Você não tem papel de gestor ou comprador nesta obra e não '
              'pode abrir requisição para ela.', 'danger')
        return redirect(url_for('compras.requisicao_nova'))

    # Etapa opcional — mesma validação de pedido_compra (compras_views.py:597)
    osc_id_bruto = (request.form.get('obra_servico_custo_id') or '').strip()
    osc_id = None
    if osc_id_bruto:
        try:
            candidato = int(osc_id_bruto)
        except (TypeError, ValueError):
            candidato = None
        if candidato and ObraServicoCusto.query.filter_by(
                id=candidato, obra_id=obra_id, admin_id=admin_id).first():
            osc_id = candidato

    mapa_id_bruto = (request.form.get('mapa_v2_id') or '').strip()
    mapa_id = None
    if mapa_id_bruto:
        try:
            candidato = int(mapa_id_bruto)
        except (TypeError, ValueError):
            candidato = None
        if candidato and MapaConcorrenciaV2.query.filter_by(
                id=candidato, obra_id=obra_id, admin_id=admin_id).first():
            mapa_id = candidato

    itens = _itens_do_form()
    if not itens:
        flash('Adicione pelo menos um item à requisição.', 'danger')
        return redirect(url_for('compras.requisicao_nova'))

    data_nec_bruta = (request.form.get('data_necessidade') or '').strip()
    try:
        data_necessidade = (datetime.strptime(data_nec_bruta, '%Y-%m-%d').date()
                            if data_nec_bruta else None)
    except ValueError:
        data_necessidade = None

    # Tenants criados depois da migration 243 não têm faixa; semeia aqui,
    # antes de existir requisição que dependa delas.
    garantir_faixas_do_tenant(admin_id)

    # Retry de numeração: o UNIQUE (admin_id, numero) fecha a corrida entre
    # dois requests simultâneos. Mesmo padrão de views/obras.py:3279.
    from sqlalchemy.exc import IntegrityError

    for tentativa in range(3):
        try:
            requisicao = RequisicaoCompra(
                numero=proximo_numero(admin_id),
                admin_id=admin_id,
                obra_id=obra_id,
                obra_servico_custo_id=osc_id,
                mapa_v2_id=mapa_id,
                solicitante_id=current_user.id,
                estado=EstadoRequisicao.RASCUNHO,
                justificativa=(request.form.get('justificativa') or '').strip() or None,
                data_necessidade=data_necessidade,
                valor_estimado=0,
            )
            db.session.add(requisicao)
            db.session.flush()

            for item in itens:
                db.session.add(RequisicaoCompraItem(
                    requisicao_id=requisicao.id,
                    admin_id=admin_id,
                    almoxarifado_item_id=item['almoxarifado_item_id'],
                    descricao=item['descricao'],
                    unidade=item['unidade'],
                    quantidade=item['quantidade'],
                    preco_estimado=item['preco'],
                ))
            db.session.flush()
            recalcular_valor(requisicao)
            db.session.commit()
            break
        except IntegrityError:
            db.session.rollback()
            logger.warning('colisão de numeração de requisição no tenant %s '
                           '(tentativa %s)', admin_id, tentativa + 1)
    else:
        flash('Não foi possível gerar o número da requisição. Tente novamente.',
              'danger')
        return redirect(url_for('compras.requisicao_nova'))

    faixa = faixa_para_valor(admin_id, requisicao.valor_estimado)
    flash(f'Requisição {requisicao.numero} criada (R$ '
          f'{requisicao.valor_estimado}). Pela alçada configurada, ela vai '
          f'precisar de {faixa.aprovacoes_necessarias} aprovação(ões).',
          'success')
    return redirect(url_for('compras.requisicao_detalhe',
                            requisicao_id=requisicao.id))


@compras_bp.route('/requisicoes/<int:requisicao_id>')
@login_required
def requisicao_detalhe(requisicao_id):
    guard = _check_v2()
    if guard:
        return guard

    requisicao = _requisicao_do_tenant(requisicao_id)

    from flask import abort
    if not pode_ver_obra(requisicao.obra_id):
        abort(404)

    faixa = faixa_para_valor(requisicao.admin_id, requisicao.valor_estimado)
    pode, motivo_recusa = pode_aprovar(requisicao, current_user)

    pedidos = PedidoCompra.query.filter_by(
        requisicao_id=requisicao.id).all() if hasattr(
            PedidoCompra, 'requisicao_id') else []

    return render_template(
        'compras/requisicao_detalhe.html',
        requisicao=requisicao,
        itens=requisicao.itens.all(),
        transicoes=requisicao.transicoes.all(),
        faixa=faixa,
        pendencias=pendencias_de_aprovacao(requisicao),
        pode_aprovar=pode,
        motivo_recusa=motivo_recusa,
        pode_emitir=pode_comprar_na_obra(requisicao.obra_id),
        pedidos=pedidos,
        EstadoRequisicao=EstadoRequisicao,
    )


@compras_bp.route('/requisicoes/<int:requisicao_id>/enviar', methods=['POST'])
@login_required
def requisicao_enviar(requisicao_id):
    """RASCUNHO → AGUARDANDO_APROVACAO."""
    guard = _check_v2()
    if guard:
        return guard

    requisicao = _requisicao_do_tenant(requisicao_id)

    if not pode_requisitar_na_obra(requisicao.obra_id):
        flash('Você não pode movimentar requisições desta obra.', 'danger')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    # Requisição sem item aprovada é assinatura em branco.
    if requisicao.itens.count() == 0:
        flash('Requisição sem itens não vai para aprovação.', 'warning')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    recalcular_valor(requisicao)
    try:
        transicionar(requisicao, EstadoRequisicao.AGUARDANDO_APROVACAO,
                     current_user,
                     motivo=(request.form.get('motivo') or '').strip() or None)
        db.session.commit()
        flash(f'Requisição {requisicao.numero} enviada para aprovação.', 'success')
    except TransicaoInvalida as e:
        db.session.rollback()
        flash(str(e), 'danger')

    return redirect(url_for('compras.requisicao_detalhe',
                            requisicao_id=requisicao_id))


@compras_bp.route('/requisicoes/<int:requisicao_id>/cancelar', methods=['POST'])
@login_required
def requisicao_cancelar(requisicao_id):
    guard = _check_v2()
    if guard:
        return guard

    requisicao = _requisicao_do_tenant(requisicao_id)

    if not pode_requisitar_na_obra(requisicao.obra_id):
        flash('Você não pode movimentar requisições desta obra.', 'danger')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    try:
        transicionar(requisicao, EstadoRequisicao.CANCELADA, current_user,
                     motivo=(request.form.get('motivo') or '').strip() or None)
        db.session.commit()
        flash(f'Requisição {requisicao.numero} cancelada.', 'info')
    except TransicaoInvalida as e:
        db.session.rollback()
        flash(str(e), 'danger')

    return redirect(url_for('compras.requisicao_detalhe',
                            requisicao_id=requisicao_id))
```

- [ ] **Step 5: Crie `templates/compras/requisicoes.html`**

```html
{% extends "base_completo.html" %}
{% block title %}Requisições de Compra{% endblock %}

{% block content %}
<div class="container-fluid py-4">

  <div class="d-flex justify-content-between align-items-center mb-4">
    <div>
      <h1 class="h3 mb-0 fw-bold">
        <i class="fas fa-clipboard-list me-2 text-primary"></i>Requisições de Compra
      </h1>
      <small class="text-muted">Pedido de material da obra, antes da compra</small>
    </div>
    <a href="{{ url_for('compras.requisicao_nova') }}" class="btn btn-primary">
      <i class="fas fa-plus me-1"></i> Nova Requisição
    </a>
  </div>

  <div class="mb-3">
    <a href="{{ url_for('compras.requisicoes') }}"
       class="btn btn-sm {{ 'btn-primary' if not estado_filtro else 'btn-outline-secondary' }}">
      Todas
    </a>
    {% for estado in estados %}
      <a href="{{ url_for('compras.requisicoes', estado=estado.name) }}"
         class="btn btn-sm {{ 'btn-primary' if estado_filtro == estado.name else 'btn-outline-secondary' }}">
        {{ estado.value|replace('_', ' ')|title }}
        <span class="badge bg-light text-dark ms-1">{{ contagem.get(estado.name, 0) }}</span>
      </a>
    {% endfor %}
  </div>

  <div class="card border-0 shadow-sm">
    <div class="table-responsive">
      <table class="table table-hover align-middle mb-0">
        <thead class="table-light">
          <tr>
            <th>Número</th>
            <th>Obra</th>
            <th>Etapa</th>
            <th>Solicitante</th>
            <th class="text-end">Valor estimado</th>
            <th>Estado</th>
            <th>Necessidade</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
        {% for r in requisicoes %}
          <tr>
            <td class="fw-semibold">{{ r.numero }}</td>
            <td>{{ r.obra.nome if r.obra else '—' }}</td>
            <td class="small text-muted">
              {{ r.obra_servico_custo.nome if r.obra_servico_custo else '—' }}
            </td>
            <td class="small">{{ r.solicitante.nome if r.solicitante else '—' }}</td>
            <td class="text-end">R$ {{ '%.2f'|format(r.valor_estimado or 0) }}</td>
            <td>
              {% set cor = {
                   'RASCUNHO': 'secondary',
                   'AGUARDANDO_APROVACAO': 'warning',
                   'APROVADA': 'success',
                   'REJEITADA': 'danger',
                   'CONVERTIDA': 'primary',
                   'CANCELADA': 'dark'
                 }.get(r.estado.name, 'secondary') %}
              <span class="badge bg-{{ cor }}">
                {{ r.estado.value|replace('_', ' ')|title }}
              </span>
            </td>
            <td class="small">
              {{ r.data_necessidade.strftime('%d/%m/%Y') if r.data_necessidade else '—' }}
            </td>
            <td class="text-end">
              <a href="{{ url_for('compras.requisicao_detalhe', requisicao_id=r.id) }}"
                 class="btn btn-outline-primary btn-sm py-0 px-2">
                <i class="fas fa-eye"></i>
              </a>
            </td>
          </tr>
        {% else %}
          <tr>
            <td colspan="8" class="text-center text-muted py-5">
              Nenhuma requisição encontrada.<br>
              <a href="{{ url_for('compras.requisicao_nova') }}"
                 class="btn btn-primary btn-sm mt-2">Criar a primeira</a>
            </td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
    </div>
  </div>

</div>
{% endblock %}
```

- [ ] **Step 6: Crie `templates/compras/requisicao_nova.html`**

```html
{% extends "base_completo.html" %}
{% block title %}Nova Requisição de Compra{% endblock %}

{% block content %}
<div class="container-fluid py-4">

  <div class="d-flex align-items-center mb-4">
    <a href="{{ url_for('compras.requisicoes') }}" class="btn btn-outline-secondary me-3">
      <i class="fas fa-arrow-left"></i>
    </a>
    <div>
      <h1 class="h3 mb-0 fw-bold">Nova Requisição de Compra</h1>
      <small class="text-muted">
        A obra é obrigatória — é o que faz o custo aparecer no lugar certo
      </small>
    </div>
  </div>

  <form method="POST" action="{{ url_for('compras.requisicao_nova_post') }}">
    <div class="row">
      <div class="col-lg-8">
        <div class="card border-0 shadow-sm mb-4">
          <div class="card-body">
            <div class="row g-3">
              <div class="col-md-6">
                <label class="form-label">Obra <span class="text-danger">*</span></label>
                <select name="obra_id" id="obraSelect" class="form-select" required>
                  <option value="">Selecione…</option>
                  {% for o in obras %}
                    <option value="{{ o.id }}">{{ o.nome }}</option>
                  {% endfor %}
                </select>
              </div>
              <div class="col-md-6">
                <label class="form-label">Data de necessidade</label>
                <input type="date" name="data_necessidade" class="form-control"
                       value="{{ hoje }}">
              </div>
              <div class="col-12">
                <label class="form-label">Justificativa</label>
                <textarea name="justificativa" rows="2" class="form-control"
                          placeholder="Para que serve, e por que agora"></textarea>
              </div>
            </div>
          </div>
        </div>

        <div class="card border-0 shadow-sm">
          <div class="card-header bg-white fw-semibold">Itens</div>
          <div class="card-body">
            <table class="table table-sm align-middle" id="tabelaItens">
              <thead>
                <tr>
                  <th style="width:38%">Descrição</th>
                  <th style="width:12%">Unid.</th>
                  <th style="width:15%">Qtd.</th>
                  <th style="width:18%">Preço estimado</th>
                  <th style="width:12%">Catálogo</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><input type="text" name="item_descricao[]" class="form-control form-control-sm"></td>
                  <td><input type="text" name="item_unidade[]" class="form-control form-control-sm" value="un"></td>
                  <td><input type="text" name="item_quantidade[]" class="form-control form-control-sm" value="1"></td>
                  <td><input type="text" name="item_preco[]" class="form-control form-control-sm" value="0,00"></td>
                  <td>
                    <select name="item_almoxarifado_id[]" class="form-select form-select-sm">
                      <option value="">—</option>
                      {% for i in itens_catalogo %}
                        <option value="{{ i.id }}">{{ i.nome }}</option>
                      {% endfor %}
                    </select>
                  </td>
                  <td class="text-end">
                    <button type="button" class="btn btn-outline-danger btn-sm py-0 px-2 btn-remover">
                      <i class="fas fa-times"></i>
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
            <button type="button" id="btnAddItem" class="btn btn-outline-primary btn-sm">
              <i class="fas fa-plus me-1"></i> Adicionar item
            </button>
          </div>
        </div>
      </div>

      <div class="col-lg-4">
        <div class="card border-0 shadow-sm">
          <div class="card-body">
            <p class="text-muted small mb-3">
              A requisição nasce em <strong>rascunho</strong>. Ela só vai para
              aprovação quando você clicar em "Enviar para aprovação" na tela
              de detalhe — e o número de aprovações depende do valor, pela
              alçada configurada para a sua empresa.
            </p>
            <button type="submit" class="btn btn-primary w-100">
              <i class="fas fa-save me-1"></i> Salvar rascunho
            </button>
            <a href="{{ url_for('compras.requisicoes') }}"
               class="btn btn-outline-secondary w-100 mt-2">Cancelar</a>
          </div>
        </div>
      </div>
    </div>
  </form>

</div>

<script>
(function () {
  var tabela = document.querySelector('#tabelaItens tbody');

  document.getElementById('btnAddItem').addEventListener('click', function () {
    var modelo = tabela.rows[0].cloneNode(true);
    modelo.querySelectorAll('input').forEach(function (el) {
      if (el.name === 'item_unidade[]') { el.value = 'un'; }
      else if (el.name === 'item_quantidade[]') { el.value = '1'; }
      else if (el.name === 'item_preco[]') { el.value = '0,00'; }
      else { el.value = ''; }
    });
    modelo.querySelectorAll('select').forEach(function (el) { el.selectedIndex = 0; });
    tabela.appendChild(modelo);
  });

  tabela.addEventListener('click', function (ev) {
    var botao = ev.target.closest('.btn-remover');
    if (!botao) { return; }
    // Nunca remover a última linha: ela é o modelo de clonagem.
    if (tabela.rows.length > 1) { botao.closest('tr').remove(); }
  });
})();
</script>
{% endblock %}
```

- [ ] **Step 7: Crie `templates/compras/requisicao_detalhe.html`**

```html
{% extends "base_completo.html" %}
{% block title %}Requisição {{ requisicao.numero }}{% endblock %}

{% block content %}
<div class="container-fluid py-4">

  <div class="d-flex align-items-center mb-4">
    <a href="{{ url_for('compras.requisicoes') }}" class="btn btn-outline-secondary me-3">
      <i class="fas fa-arrow-left"></i>
    </a>
    <div class="flex-grow-1">
      <h1 class="h3 mb-0 fw-bold">{{ requisicao.numero }}</h1>
      <small class="text-muted">
        {{ requisicao.obra.nome if requisicao.obra else '—' }}
        {% if requisicao.obra_servico_custo %}
          · etapa: {{ requisicao.obra_servico_custo.nome }}
        {% endif %}
      </small>
    </div>
    {% set cor = {
         'RASCUNHO': 'secondary', 'AGUARDANDO_APROVACAO': 'warning',
         'APROVADA': 'success', 'REJEITADA': 'danger',
         'CONVERTIDA': 'primary', 'CANCELADA': 'dark'
       }.get(requisicao.estado.name, 'secondary') %}
    <span class="badge bg-{{ cor }} fs-6">
      {{ requisicao.estado.value|replace('_', ' ')|title }}
    </span>
  </div>

  <div class="row">
    <div class="col-lg-8">

      <div class="card border-0 shadow-sm mb-4">
        <div class="card-header bg-white fw-semibold">Itens</div>
        <div class="table-responsive">
          <table class="table mb-0 align-middle">
            <thead class="table-light">
              <tr>
                <th>Descrição</th><th>Unid.</th>
                <th class="text-end">Qtd.</th>
                <th class="text-end">Preço est.</th>
                <th class="text-end">Subtotal</th>
              </tr>
            </thead>
            <tbody>
              {% for i in itens %}
                <tr>
                  <td>{{ i.descricao }}</td>
                  <td class="small text-muted">{{ i.unidade }}</td>
                  <td class="text-end">{{ '%.3f'|format(i.quantidade or 0) }}</td>
                  <td class="text-end">R$ {{ '%.2f'|format(i.preco_estimado or 0) }}</td>
                  <td class="text-end fw-semibold">R$ {{ '%.2f'|format(i.subtotal) }}</td>
                </tr>
              {% endfor %}
            </tbody>
            <tfoot class="table-light">
              <tr>
                <th colspan="4" class="text-end">Total estimado</th>
                <th class="text-end">R$ {{ '%.2f'|format(requisicao.valor_estimado or 0) }}</th>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <div class="card border-0 shadow-sm">
        <div class="card-header bg-white fw-semibold">
          Histórico de aprovação
        </div>
        <div class="table-responsive">
          <table class="table table-sm mb-0">
            <thead class="table-light">
              <tr><th>Quando</th><th>Quem</th><th>Papel</th><th>O quê</th>
                  <th class="text-end">Valor</th><th>Motivo</th></tr>
            </thead>
            <tbody>
              {% for t in transicoes %}
                <tr>
                  <td class="small">{{ t.criado_em.strftime('%d/%m/%Y %H:%M') }}</td>
                  <td class="small">{{ t.usuario.nome if t.usuario else '—' }}</td>
                  <td class="small">{{ t.papel_aplicado or '—' }}</td>
                  <td class="small">
                    {% if t.motivo and t.motivo.startswith('[aprovacao]') %}
                      <span class="badge bg-success">aprovou</span>
                    {% else %}
                      {{ (t.de_estado.value if t.de_estado else '—') }}
                      →
                      <strong>{{ t.para_estado.value }}</strong>
                    {% endif %}
                  </td>
                  <td class="text-end small">R$ {{ '%.2f'|format(t.valor_no_momento or 0) }}</td>
                  <td class="small text-muted">
                    {{ (t.motivo or '')|replace('[aprovacao]', '')|trim }}
                  </td>
                </tr>
              {% else %}
                <tr><td colspan="6" class="text-center text-muted py-4">
                  Nenhuma movimentação ainda.
                </td></tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
      </div>

    </div>

    <div class="col-lg-4">

      <div class="card border-0 shadow-sm mb-4">
        <div class="card-body">
          <h6 class="fw-bold">Alçada</h6>
          <p class="small text-muted mb-2">
            Faixa aplicada: até
            {% if faixa.valor_ate is none %}sem teto{% else %}R$ {{ '%.2f'|format(faixa.valor_ate) }}{% endif %}
            · {{ faixa.aprovacoes_necessarias }} aprovação(ões)
            {% if faixa.exige_admin %} · uma tem que ser de administrador{% endif %}
            {% if faixa.exige_mapa_concorrencia %} · exige mapa de concorrência{% endif %}
          </p>
          {% if pendencias %}
            <ul class="small text-danger mb-0">
              {% for p in pendencias %}<li>{{ p }}</li>{% endfor %}
            </ul>
          {% else %}
            <p class="small text-success mb-0">
              <i class="fas fa-check me-1"></i>Requisitos de alçada atendidos.
            </p>
          {% endif %}
        </div>
      </div>

      <div class="card border-0 shadow-sm">
        <div class="card-body d-grid gap-2">

          {% if requisicao.estado == EstadoRequisicao.RASCUNHO %}
            <form method="POST"
                  action="{{ url_for('compras.requisicao_enviar', requisicao_id=requisicao.id) }}">
              <button class="btn btn-primary w-100">
                <i class="fas fa-paper-plane me-1"></i> Enviar para aprovação
              </button>
            </form>
          {% endif %}

          {% if requisicao.estado == EstadoRequisicao.AGUARDANDO_APROVACAO %}
            {% if pode_aprovar %}
              <form method="POST"
                    action="{{ url_for('compras.requisicao_aprovar', requisicao_id=requisicao.id) }}">
                <input type="text" name="observacao" class="form-control form-control-sm mb-2"
                       placeholder="Observação (opcional)">
                <button class="btn btn-success w-100">
                  <i class="fas fa-check me-1"></i> Aprovar
                </button>
              </form>
              <form method="POST"
                    action="{{ url_for('compras.requisicao_rejeitar', requisicao_id=requisicao.id) }}">
                <input type="text" name="motivo" class="form-control form-control-sm mb-2"
                       placeholder="Motivo da rejeição" required>
                <button class="btn btn-outline-danger w-100">
                  <i class="fas fa-times me-1"></i> Rejeitar
                </button>
              </form>
            {% else %}
              <div class="alert alert-secondary small mb-0">{{ motivo_recusa }}</div>
            {% endif %}
          {% endif %}

          {% if requisicao.estado == EstadoRequisicao.APROVADA and pode_emitir %}
            <form method="POST"
                  action="{{ url_for('compras.requisicao_emitir_pedido', requisicao_id=requisicao.id) }}">
              <button class="btn btn-primary w-100">
                <i class="fas fa-file-invoice-dollar me-1"></i> Emitir pedido de compra
              </button>
            </form>
          {% endif %}

          {% if requisicao.estado.name in ('RASCUNHO', 'AGUARDANDO_APROVACAO', 'APROVADA', 'REJEITADA') %}
            <form method="POST"
                  action="{{ url_for('compras.requisicao_cancelar', requisicao_id=requisicao.id) }}"
                  onsubmit="return confirm('Cancelar esta requisição?')">
              <input type="text" name="motivo" class="form-control form-control-sm mb-2"
                     placeholder="Motivo do cancelamento">
              <button class="btn btn-outline-dark w-100 btn-sm">Cancelar requisição</button>
            </form>
          {% endif %}

          {% if pedidos %}
            <hr>
            <h6 class="fw-bold">Pedidos emitidos</h6>
            <ul class="list-unstyled small mb-0">
              {% for p in pedidos %}
                <li>
                  <a href="{{ url_for('compras.detalhe', pedido_id=p.id) }}">
                    {{ p.numero or ('Pedido #' ~ p.id) }}
                  </a>
                  — R$ {{ '%.2f'|format(p.valor_total or 0) }}
                </li>
              {% endfor %}
            </ul>
          {% endif %}

        </div>
      </div>

    </div>
  </div>

</div>
{% endblock %}
```

> **Nota:** este template referencia `compras.requisicao_aprovar`, `compras.requisicao_rejeitar` e `compras.requisicao_emitir_pedido`, que são criadas nas Tasks 7 e 8. Entre esta task e a 8 a tela de detalhe **quebra com `BuildError`** para requisições em `AGUARDANDO_APROVACAO`/`APROVADA` — o que é aceitável porque nenhuma requisição chega a esses estados até a Task 7 existir, e os testes desta task só exercitam RASCUNHO. **Não pare aqui**: execute as Tasks 7 e 8 na mesma sessão.

- [ ] **Step 8: Acrescente os itens ao menu**

Em `templates/base_completo.html`, dentro do `<ul class="dropdown-menu">` de Compras, logo **antes** do `<li><hr class="dropdown-divider"></li>` da linha 964, insira:

```html
                                <li><hr class="dropdown-divider"></li>
                                <li><a class="dropdown-item" href="{{ url_for('compras.requisicoes') }}">
                                    <i class="fas fa-clipboard-list me-1"></i> Requisições
                                </a></li>
                                <li><a class="dropdown-item" href="{{ url_for('compras.requisicao_nova') }}">
                                    <i class="fas fa-plus-circle me-1 text-success"></i> Nova Requisição
                                </a></li>
```

- [ ] **Step 9: Rode os testes**

```bash
python -m pytest tests/test_fase3_requisicao.py -v
```

Esperado: todos PASSAM.

- [ ] **Step 10: Commit**

```bash
git add compras_views.py templates/compras/requisicoes.html templates/compras/requisicao_nova.html templates/compras/requisicao_detalhe.html templates/base_completo.html tests/test_fase3_requisicao.py
git commit -m "feat(fase3): telas de requisicao de compra

Listar/criar/detalhar/enviar/cancelar. A listagem passa por
obras_visiveis() da Fase 1 — nao repete o filtro so-por-tenant de
compras_views.py:421. Obra obrigatoria no POST, com pode_ver_obra e
pode_requisitar_na_obra antes de qualquer escrita."
```

---

## Task 7: Aprovação e rejeição com alçada

**Files:**
- Modify: `compras_views.py` (duas rotas, após `requisicao_cancelar`)
- Test: `tests/test_fase3_alcada.py` (acrescenta)

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao final de `tests/test_fase3_alcada.py`:

```python
# ---------------------------------------------------------------------------
# Rotas de aprovação
# ---------------------------------------------------------------------------

def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


def _cenario(valor, papel_do_aprovador=PapelObra.GESTOR):
    """admin + obra + solicitante + aprovador vinculado, requisição já
    aguardando aprovação. Devolve os ids (fora de app_context aberto)."""
    from services.requisicao_compra import proximo_numero

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _faixas_de_teste(admin.id)
        solicitante = _operador(admin.id, 'Solicitante')
        aprovador = _operador(admin.id, 'Aprovador')
        _vincular(solicitante, obra, PapelObra.COMPRADOR)
        _vincular(aprovador, obra, papel_do_aprovador)
        req = RequisicaoCompra(
            numero=proximo_numero(admin.id), obra_id=obra.id,
            solicitante_id=solicitante.id, admin_id=admin.id,
            estado=EstadoRequisicao.AGUARDANDO_APROVACAO,
            valor_estimado=Decimal(valor))
        db.session.add(req)
        db.session.commit()
        return {'admin': admin.id, 'obra': obra.id,
                'solicitante': solicitante.id, 'aprovador': aprovador.id,
                'req': req.id}


def test_aprovacao_unica_leva_para_aprovada():
    c = _cenario('50.00')  # faixa 1: 1 aprovação, sem admin
    r = _cliente_de(c['aprovador']).post(
        f"/compras/requisicoes/{c['req']}/aprovar", follow_redirects=False)
    assert r.status_code == 302
    with app.app_context():
        req = db.session.get(RequisicaoCompra, c['req'])
        assert req.estado == EstadoRequisicao.APROVADA


def test_primeira_de_duas_aprovacoes_nao_muda_o_estado():
    c = _cenario('500.00')  # faixa 2: 2 aprovações + admin
    _cliente_de(c['aprovador']).post(
        f"/compras/requisicoes/{c['req']}/aprovar", follow_redirects=False)
    with app.app_context():
        req = db.session.get(RequisicaoCompra, c['req'])
        assert req.estado == EstadoRequisicao.AGUARDANDO_APROVACAO


def test_segunda_aprovacao_do_admin_fecha_a_alcada():
    from services.alcada_compras import aprovacoes_registradas

    c = _cenario('500.00')
    _cliente_de(c['aprovador']).post(
        f"/compras/requisicoes/{c['req']}/aprovar", follow_redirects=False)
    _cliente_de(c['admin']).post(
        f"/compras/requisicoes/{c['req']}/aprovar", follow_redirects=False)
    with app.app_context():
        req = db.session.get(RequisicaoCompra, c['req'])
        assert aprovacoes_registradas(req) == 2
        assert req.estado == EstadoRequisicao.APROVADA


def test_solicitante_nao_aprova_pela_rota():
    c = _cenario('50.00')
    _cliente_de(c['solicitante']).post(
        f"/compras/requisicoes/{c['req']}/aprovar", follow_redirects=False)
    with app.app_context():
        req = db.session.get(RequisicaoCompra, c['req'])
        assert req.estado == EstadoRequisicao.AGUARDANDO_APROVACAO


def test_leitor_da_obra_nao_aprova():
    c = _cenario('50.00', papel_do_aprovador=PapelObra.LEITOR)
    _cliente_de(c['aprovador']).post(
        f"/compras/requisicoes/{c['req']}/aprovar", follow_redirects=False)
    with app.app_context():
        req = db.session.get(RequisicaoCompra, c['req'])
        assert req.estado == EstadoRequisicao.AGUARDANDO_APROVACAO


def test_comprador_nao_aprova():
    """COMPRADOR pede e emite; não aprova. É a separação de funções."""
    c = _cenario('50.00', papel_do_aprovador=PapelObra.COMPRADOR)
    _cliente_de(c['aprovador']).post(
        f"/compras/requisicoes/{c['req']}/aprovar", follow_redirects=False)
    with app.app_context():
        req = db.session.get(RequisicaoCompra, c['req'])
        assert req.estado == EstadoRequisicao.AGUARDANDO_APROVACAO


def test_aprovador_de_outro_tenant_recebe_404():
    c = _cenario('50.00')
    with app.app_context():
        estranho = _admin('Estranho')
        eid = estranho.id
    r = _cliente_de(eid).post(
        f"/compras/requisicoes/{c['req']}/aprovar", follow_redirects=False)
    assert r.status_code == 404


def test_rejeicao_exige_motivo_e_grava_trilha():
    from models import RequisicaoTransicao

    c = _cenario('50.00')
    sem_motivo = _cliente_de(c['aprovador']).post(
        f"/compras/requisicoes/{c['req']}/rejeitar", data={'motivo': ''},
        follow_redirects=False)
    assert sem_motivo.status_code == 302
    with app.app_context():
        assert db.session.get(RequisicaoCompra, c['req']).estado == \
            EstadoRequisicao.AGUARDANDO_APROVACAO

    _cliente_de(c['aprovador']).post(
        f"/compras/requisicoes/{c['req']}/rejeitar",
        data={'motivo': 'sem verba neste mês'}, follow_redirects=False)
    with app.app_context():
        req = db.session.get(RequisicaoCompra, c['req'])
        assert req.estado == EstadoRequisicao.REJEITADA
        t = (RequisicaoTransicao.query
             .filter_by(requisicao_id=req.id,
                        para_estado=EstadoRequisicao.REJEITADA).one())
        assert 'sem verba' in t.motivo
        assert t.valor_no_momento == Decimal('50.00')


def test_valor_gravado_e_o_do_momento_da_aprovacao():
    """Editar a requisição depois não pode reescrever o histórico da alçada."""
    from services.alcada_compras import votos_de_aprovacao

    c = _cenario('50.00')
    _cliente_de(c['aprovador']).post(
        f"/compras/requisicoes/{c['req']}/aprovar", follow_redirects=False)
    with app.app_context():
        req = db.session.get(RequisicaoCompra, c['req'])
        req.valor_estimado = Decimal('99999.00')
        db.session.commit()
        voto = votos_de_aprovacao(req)[0]
        assert voto.valor_no_momento == Decimal('50.00')
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase3_alcada.py -v -k "aprovacao or aprova or rejeicao or valor_gravado"
```

Esperado: FAIL — 404 nas rotas de aprovar/rejeitar.

- [ ] **Step 3: Escreva as duas rotas**

Ao final de `compras_views.py`, depois de `requisicao_cancelar`, acrescente:

```python
@compras_bp.route('/requisicoes/<int:requisicao_id>/aprovar', methods=['POST'])
@login_required
def requisicao_aprovar(requisicao_id):
    """Registra UM voto de aprovação; move para APROVADA quando a alçada fecha.

    Um voto não é uma transição de estado: a faixa pode exigir dois. Por
    isso `registrar_aprovacao` grava a RequisicaoTransicao com
    `para_estado == estado atual` (voto) e só depois, se
    `esta_totalmente_aprovada`, é que `transicionar` roda de verdade.
    """
    guard = _check_v2()
    if guard:
        return guard

    requisicao = _requisicao_do_tenant(requisicao_id)

    permitido, motivo = pode_aprovar(requisicao, current_user)
    if not permitido:
        flash(motivo, 'danger')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    observacao = (request.form.get('observacao') or '').strip() or None

    try:
        registrar_aprovacao(requisicao, current_user, observacao=observacao)

        if esta_totalmente_aprovada(requisicao):
            transicionar(requisicao, EstadoRequisicao.APROVADA, current_user,
                         motivo='alçada atendida')
            db.session.commit()
            flash(f'Requisição {requisicao.numero} APROVADA. Já pode virar '
                  f'pedido de compra.', 'success')
        else:
            db.session.commit()
            faltando = '; '.join(pendencias_de_aprovacao(requisicao))
            flash(f'Sua aprovação foi registrada. Ainda falta: {faltando}.',
                  'info')
    except TransicaoInvalida as e:
        db.session.rollback()
        flash(str(e), 'danger')
    except Exception as e:
        db.session.rollback()
        logger.error('[fase3] falha ao aprovar requisicao %s: %s',
                     requisicao_id, e, exc_info=True)
        flash('Não foi possível registrar a aprovação. Tente novamente.',
              'danger')

    return redirect(url_for('compras.requisicao_detalhe',
                            requisicao_id=requisicao_id))


@compras_bp.route('/requisicoes/<int:requisicao_id>/rejeitar', methods=['POST'])
@login_required
def requisicao_rejeitar(requisicao_id):
    """AGUARDANDO_APROVACAO → REJEITADA. Motivo obrigatório.

    Rejeitar sem motivo é a forma mais rápida de tornar a trilha inútil:
    seis meses depois ninguém sabe se a compra foi barrada por preço, por
    prazo ou por especificação errada.
    """
    guard = _check_v2()
    if guard:
        return guard

    requisicao = _requisicao_do_tenant(requisicao_id)

    permitido, motivo_recusa = pode_aprovar(requisicao, current_user)
    if not permitido:
        flash(motivo_recusa, 'danger')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    motivo = (request.form.get('motivo') or '').strip()
    if not motivo:
        flash('Informe o motivo da rejeição — sem ele o histórico não '
              'serve para nada.', 'warning')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    try:
        transicionar(requisicao, EstadoRequisicao.REJEITADA, current_user,
                     motivo=motivo[:2000])
        db.session.commit()
        flash(f'Requisição {requisicao.numero} rejeitada. O solicitante pode '
              f'corrigir e reenviar.', 'warning')
    except TransicaoInvalida as e:
        db.session.rollback()
        flash(str(e), 'danger')

    return redirect(url_for('compras.requisicao_detalhe',
                            requisicao_id=requisicao_id))
```

- [ ] **Step 4: Rode os testes**

```bash
python -m pytest tests/test_fase3_alcada.py -v
```

Esperado: todos PASSAM.

- [ ] **Step 5: Commit**

```bash
git add compras_views.py tests/test_fase3_alcada.py
git commit -m "feat(fase3): aprovacao e rejeicao com alcada

Um voto nao e uma transicao: a faixa pode exigir dois. registrar_aprovacao
grava o voto, e so quando esta_totalmente_aprovada e que o estado muda.
Motivo obrigatorio na rejeicao. Solicitante, LEITOR, APONTADOR e
COMPRADOR nao aprovam — provado por teste de rota, nao so de servico."
```

---

## Task 8: Emissão do pedido de compra a partir da requisição aprovada

**Files:**
- Modify: `models.py` (`PedidoCompra.requisicao_id`, após a linha 4766)
- Modify: `migrations.py` (migration 244 + registro)
- Modify: `compras_views.py` (rota `requisicao_emitir_pedido`)
- Test: `tests/test_fase3_alcada.py` (acrescenta)

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao final de `tests/test_fase3_alcada.py`:

```python
# ---------------------------------------------------------------------------
# Emissão do pedido
# ---------------------------------------------------------------------------

def _cenario_aprovado(valor='50.00'):
    """Requisição com item, já APROVADA, e um COMPRADOR vinculado."""
    from models import Fornecedor, RequisicaoCompraItem
    from services.alcada_compras import registrar_aprovacao
    from services.requisicao_compra import (proximo_numero, recalcular_valor,
                                            transicionar)

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _faixas_de_teste(admin.id)
        solicitante = _operador(admin.id, 'Solicitante')
        gestor = _operador(admin.id, 'Gestor')
        comprador = _operador(admin.id, 'Comprador')
        _vincular(solicitante, obra, PapelObra.COMPRADOR)
        _vincular(gestor, obra, PapelObra.GESTOR)
        _vincular(comprador, obra, PapelObra.COMPRADOR)

        forn = Fornecedor(nome='Forn Teste', cnpj=f'{uuid.uuid4().hex[:14]}',
                          admin_id=admin.id, ativo=True)
        db.session.add(forn)

        req = RequisicaoCompra(
            numero=proximo_numero(admin.id), obra_id=obra.id,
            solicitante_id=solicitante.id, admin_id=admin.id,
            estado=EstadoRequisicao.AGUARDANDO_APROVACAO)
        db.session.add(req)
        db.session.flush()
        db.session.add(RequisicaoCompraItem(
            requisicao_id=req.id, admin_id=admin.id, descricao='Perfil U90',
            unidade='m', quantidade=Decimal('10.000'),
            preco_estimado=Decimal(valor) / Decimal('10')))
        db.session.flush()
        recalcular_valor(req)
        registrar_aprovacao(req, gestor, papel='GESTOR')
        registrar_aprovacao(req, admin, papel='ADMIN')
        transicionar(req, EstadoRequisicao.APROVADA, gestor, motivo='ok')
        db.session.commit()
        return {'admin': admin.id, 'obra': obra.id, 'req': req.id,
                'comprador': comprador.id, 'gestor': gestor.id,
                'solicitante': solicitante.id, 'fornecedor': forn.id}


def test_emitir_pedido_cria_pedido_vinculado_com_obra():
    from models import PedidoCompra

    c = _cenario_aprovado()
    r = _cliente_de(c['comprador']).post(
        f"/compras/requisicoes/{c['req']}/emitir-pedido",
        data={'fornecedor_id': str(c['fornecedor']),
              'data_compra': '2026-08-01',
              'condicao_pagamento': 'a_vista', 'parcelas': '1'},
        follow_redirects=False)
    assert r.status_code == 302

    with app.app_context():
        pedido = PedidoCompra.query.filter_by(requisicao_id=c['req']).one()
        assert pedido.obra_id == c['obra'], 'pedido emitido sem obra'
        assert pedido.admin_id == c['admin']
        assert pedido.itens.count() == 1
        req = db.session.get(RequisicaoCompra, c['req'])
        assert req.estado == EstadoRequisicao.CONVERTIDA


def test_requisicao_nao_aprovada_nao_vira_pedido():
    from models import PedidoCompra

    c = _cenario('50.00')  # AGUARDANDO_APROVACAO
    with app.app_context():
        comprador = _operador(c['admin'], 'Comprador')
        obra = db.session.get(Obra, c['obra'])
        _vincular(comprador, obra, PapelObra.COMPRADOR)
        cid = comprador.id
        forn_id = None
        from models import Fornecedor
        f = Fornecedor(nome='F', cnpj=uuid.uuid4().hex[:14],
                       admin_id=c['admin'], ativo=True)
        db.session.add(f)
        db.session.commit()
        forn_id = f.id

    _cliente_de(cid).post(
        f"/compras/requisicoes/{c['req']}/emitir-pedido",
        data={'fornecedor_id': str(forn_id), 'data_compra': '2026-08-01'},
        follow_redirects=False)
    with app.app_context():
        assert PedidoCompra.query.filter_by(requisicao_id=c['req']).count() == 0


def test_gestor_que_aprovou_nao_emite_o_pedido():
    """Separação de funções: quem aprova não emite, quando a faixa exigiu
    mais de uma aprovação."""
    from models import PedidoCompra

    c = _cenario_aprovado()
    _cliente_de(c['gestor']).post(
        f"/compras/requisicoes/{c['req']}/emitir-pedido",
        data={'fornecedor_id': str(c['fornecedor']),
              'data_compra': '2026-08-01'},
        follow_redirects=False)
    with app.app_context():
        assert PedidoCompra.query.filter_by(requisicao_id=c['req']).count() == 0


def test_nao_se_emite_duas_vezes_a_mesma_requisicao():
    from models import PedidoCompra

    c = _cenario_aprovado()
    dados = {'fornecedor_id': str(c['fornecedor']),
             'data_compra': '2026-08-01', 'condicao_pagamento': 'a_vista'}
    cliente = _cliente_de(c['comprador'])
    cliente.post(f"/compras/requisicoes/{c['req']}/emitir-pedido", data=dados)
    cliente.post(f"/compras/requisicoes/{c['req']}/emitir-pedido", data=dados)
    with app.app_context():
        assert PedidoCompra.query.filter_by(requisicao_id=c['req']).count() == 1


def test_pedido_acima_do_valor_aprovado_e_recusado():
    """A alçada aprovou R$ 50; emitir R$ 5.000 seria burlar a faixa."""
    from models import PedidoCompra

    c = _cenario_aprovado()
    _cliente_de(c['comprador']).post(
        f"/compras/requisicoes/{c['req']}/emitir-pedido",
        data={'fornecedor_id': str(c['fornecedor']),
              'data_compra': '2026-08-01',
              'item_preco_real[]': ['500.00']},  # 10 x 500 = 5000
        follow_redirects=False)
    with app.app_context():
        assert PedidoCompra.query.filter_by(requisicao_id=c['req']).count() == 0


def test_emissao_gera_custo_na_obra():
    """O pedido emitido continua fazendo o que compras_views.py:162 sempre
    fez: GestaoCustoPai + GestaoCustoFilho na obra."""
    from models import GestaoCustoFilho, PedidoCompra

    c = _cenario_aprovado()
    _cliente_de(c['comprador']).post(
        f"/compras/requisicoes/{c['req']}/emitir-pedido",
        data={'fornecedor_id': str(c['fornecedor']),
              'data_compra': '2026-08-01', 'condicao_pagamento': 'a_vista'},
        follow_redirects=False)
    with app.app_context():
        pedido = PedidoCompra.query.filter_by(requisicao_id=c['req']).one()
        filhos = GestaoCustoFilho.query.filter_by(
            origem_tabela='pedido_compra', origem_id=pedido.id).all()
        assert filhos, 'emissão não gerou custo'
        assert all(f.obra_id == c['obra'] for f in filhos)
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase3_alcada.py -v -k "emitir or emissao or duas_vezes or acima_do_valor or nao_aprovada"
```

Esperado: FAIL — `AttributeError: type object 'PedidoCompra' has no attribute 'requisicao_id'`.

- [ ] **Step 3: Acrescente a FK ao `PedidoCompra`**

Em `models.py`, dentro da `class PedidoCompra`, imediatamente após `intervalo_parcelas_dias` (linha 4766), insira:

```python
    # Fase 3 — origem do pedido. NULL = pedido avulso, registrado direto
    # pelo formulário (compras_views.py:532), que é como TODOS os pedidos
    # nasceram até 2026-07-21. Preenchido = pedido emitido a partir de
    # requisição aprovada, com alçada registrada em requisicao_transicao.
    # A coluna é o que permite a Task 9 recusar pedido sem requisição
    # quando `compras_governanca_ativa` está ligada, sem invalidar
    # nenhum registro histórico.
    requisicao_id = db.Column(
        db.Integer, db.ForeignKey('requisicao_compra.id', ondelete='SET NULL'),
        nullable=True, index=True)
```

E, junto dos demais relationships (após a linha 4775), acrescente:

```python
    requisicao = db.relationship(
        'RequisicaoCompra', foreign_keys=[requisicao_id],
        backref=db.backref('pedidos', lazy='dynamic'))
```

- [ ] **Step 4: Escreva a migration 244 e registre**

Em `migrations.py`, antes de `def executar_migracoes():`, insira:

```python
def migration_244_pedido_compra_requisicao_id():
    """Fase 3 — pedido_compra.requisicao_id.

    Aditiva, nullable e idempotente. Todos os pedidos existentes ficam com
    NULL, que é a leitura correta: eles foram registrados direto pelo
    formulário, sem requisição, porque não havia requisição no sistema.

    ON DELETE SET NULL: apagar a requisição não pode apagar o pedido — o
    pedido já gerou GestaoCustoPai e ContaPagar (compras_views.py:193-254),
    e sumir com ele deixaria o financeiro órfão.

    Roda DEPOIS da 240 (a FK referencia requisicao_compra).
    """
    from sqlalchemy import text as sa_text

    logger.info("[Migration 244] Iniciando — pedido_compra.requisicao_id")

    with db.engine.begin() as conn:
        conn.execute(sa_text(
            "ALTER TABLE pedido_compra "
            "ADD COLUMN IF NOT EXISTS requisicao_id INTEGER "
            "REFERENCES requisicao_compra(id) ON DELETE SET NULL"))
        conn.execute(sa_text(
            "CREATE INDEX IF NOT EXISTS ix_pedido_compra_requisicao "
            "ON pedido_compra (requisicao_id)"))

    logger.info("[Migration 244] Concluída com sucesso")
```

Registre em `migrations_to_run`, entre a `243` e a `245`:

```python
            (244, "Fase 3 — pedido_compra.requisicao_id (origem do pedido; NULL = avulso legado)", migration_244_pedido_compra_requisicao_id),
```

- [ ] **Step 5: Escreva a rota de emissão**

Ao final de `compras_views.py`, acrescente:

```python
@compras_bp.route('/requisicoes/<int:requisicao_id>/emitir-pedido',
                  methods=['POST'])
@login_required
def requisicao_emitir_pedido(requisicao_id):
    """APROVADA → CONVERTIDA, criando o PedidoCompra.

    Este é o ponto em que a governança encontra o módulo que já existia: a
    partir daqui o fluxo é EXATAMENTE o de `compras.nova_post`
    (compras_views.py:668-711) — mesmo `PedidoCompra`, mesmos itens, mesmo
    `processar_compra_normal`. A diferença é que agora existe uma
    requisição aprovada por trás, com quem/quando/valor gravados.

    Três guardas, nesta ordem:
      1. estado APROVADA (senão a alçada não valeu de nada);
      2. quem emite não pode ter sido aprovador — quando a faixa exigiu
         mais de uma aprovação;
      3. o valor do pedido não pode ultrapassar o valor aprovado, senão
         aprova-se R$ 50 e compra-se R$ 5.000.
    """
    guard = _check_v2()
    if guard:
        return guard

    requisicao = _requisicao_do_tenant(requisicao_id)
    admin_id = requisicao.admin_id

    if not pode_comprar_na_obra(requisicao.obra_id):
        flash('Você não tem papel de comprador nesta obra.', 'danger')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    # Guarda 1 — só requisição aprovada vira pedido.
    if requisicao.estado != EstadoRequisicao.APROVADA:
        flash(f'A requisição está em {requisicao.estado.value}. Só se emite '
              f'pedido a partir de requisição aprovada.', 'danger')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    # Guarda 2 — separação de funções. Só vale quando a faixa exigiu mais
    # de uma aprovação: numa faixa de aprovação única, exigir uma terceira
    # pessoa para clicar em "emitir" travaria a compra de R$ 200 numa
    # equipe de três.
    from services.alcada_compras import votos_de_aprovacao

    faixa = faixa_para_valor(admin_id, requisicao.valor_estimado)
    aprovadores = {v.usuario_id for v in votos_de_aprovacao(requisicao)}
    if faixa.aprovacoes_necessarias > 1 and current_user.id in aprovadores:
        flash('Você aprovou esta requisição e por isso não pode emitir o '
              'pedido dela. Peça a outra pessoa com papel de comprador.',
              'danger')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    # Idempotência — a requisição só produz um pedido.
    if PedidoCompra.query.filter_by(requisicao_id=requisicao.id).count() > 0:
        flash('Esta requisição já gerou um pedido de compra.', 'warning')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    # ── Fornecedor (obrigatório, mesmo predicado de compras_views.py:552) ──
    forn_bruto = (request.form.get('fornecedor_id') or '').strip()
    try:
        fornecedor_id = int(forn_bruto)
    except (TypeError, ValueError):
        flash('Selecione um fornecedor para emitir o pedido.', 'danger')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))
    if not Fornecedor.query.filter_by(
            id=fornecedor_id, admin_id=admin_id, ativo=True).first():
        flash('Fornecedor não encontrado ou não pertence à sua conta.', 'danger')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    data_bruta = (request.form.get('data_compra') or '').strip()
    try:
        data_compra = (datetime.strptime(data_bruta, '%Y-%m-%d').date()
                       if data_bruta else date.today())
    except ValueError:
        data_compra = date.today()

    condicao = request.form.get('condicao_pagamento', 'a_vista')
    try:
        parcelas = max(1, int(request.form.get('parcelas', 1)))
    except (TypeError, ValueError):
        parcelas = 1

    # ── Itens: da requisição, com preço real opcional ──────────────────────
    # O comprador fecha o preço com o fornecedor; se o campo vier vazio,
    # vale o preço estimado da requisição.
    precos_reais = request.form.getlist('item_preco_real[]')
    itens_requisicao = requisicao.itens.order_by(RequisicaoCompraItem.id).all()

    itens_validos = []
    valor_total = 0.0
    for idx, item in enumerate(itens_requisicao):
        bruto = (precos_reais[idx] if idx < len(precos_reais) else '') or ''
        bruto = str(bruto).strip()
        if bruto:
            try:
                preco = float(bruto.replace('.', '').replace(',', '.')
                              if ',' in bruto else bruto)
            except ValueError:
                preco = float(item.preco_estimado or 0)
        else:
            preco = float(item.preco_estimado or 0)
        qtd = float(item.quantidade or 0)
        subtotal = round(qtd * preco, 2)
        valor_total += subtotal
        itens_validos.append((item.descricao, qtd, preco,
                              item.almoxarifado_item_id, subtotal))
    valor_total = round(valor_total, 2)

    # Guarda 3 — o pedido não pode estourar o que foi aprovado.
    from decimal import Decimal as _D
    aprovado = _D(str(requisicao.valor_estimado or 0))
    if _D(str(valor_total)) > aprovado:
        flash(f'O pedido soma R$ {valor_total:.2f}, acima dos R$ {aprovado} '
              f'aprovados. Volte a requisição para rascunho, corrija os '
              f'valores e passe pela alçada de novo.', 'danger')
        return redirect(url_for('compras.requisicao_detalhe',
                                requisicao_id=requisicao_id))

    try:
        pedido = PedidoCompra(
            numero=(request.form.get('numero') or '').strip() or None,
            fornecedor_id=fornecedor_id,
            data_compra=data_compra,
            # Obra e etapa vêm da REQUISIÇÃO, não do formulário. É o que
            # torna o vínculo obrigatório de fato: não há campo para
            # esvaziar.
            obra_id=requisicao.obra_id,
            obra_servico_custo_id=requisicao.obra_servico_custo_id,
            condicao_pagamento=condicao,
            parcelas=parcelas,
            valor_total=valor_total,
            observacoes=f'Emitido a partir da requisição {requisicao.numero}',
            tipo_compra='normal',
            processada_apos_aprovacao=False,
            status_aprovacao_cliente=None,
            admin_id=admin_id,
            responsavel_id=current_user.id,
            requisicao_id=requisicao.id,
        )
        db.session.add(pedido)
        db.session.flush()

        for desc, qtd, preco, almox_id, subtotal in itens_validos:
            db.session.add(PedidoCompraItem(
                pedido_id=pedido.id,
                almoxarifado_item_id=almox_id,
                descricao=desc,
                quantidade=qtd,
                preco_unitario=preco,
                subtotal=subtotal,
                admin_id=admin_id,
            ))
        db.session.flush()

        # Mesmíssimo processamento do fluxo antigo — GCP + ContaPagar por
        # parcela + entrada/saída de almoxarifado (compras_views.py:162).
        processar_compra_normal(pedido, itens_validos, admin_id, current_user.id)

        transicionar(requisicao, EstadoRequisicao.CONVERTIDA, current_user,
                     motivo=f'pedido de compra #{pedido.id} emitido')
        db.session.commit()

        flash(f'Pedido de compra emitido a partir da requisição '
              f'{requisicao.numero}. Custo, contas a pagar e entrada no '
              f'almoxarifado gerados.', 'success')
        return redirect(url_for('compras.detalhe', pedido_id=pedido.id))

    except TransicaoInvalida as e:
        db.session.rollback()
        flash(str(e), 'danger')
    except Exception as e:
        db.session.rollback()
        logger.error('[fase3] falha ao emitir pedido da requisicao %s: %s',
                     requisicao_id, e, exc_info=True)
        flash('Não foi possível emitir o pedido. Nada foi gravado.', 'danger')

    return redirect(url_for('compras.requisicao_detalhe',
                            requisicao_id=requisicao_id))
```

- [ ] **Step 6: Complete o formulário de emissão no template de detalhe**

Em `templates/compras/requisicao_detalhe.html`, substitua o bloco do botão "Emitir pedido de compra" (que hoje é um `<form>` sem campos) por:

```html
          {% if requisicao.estado == EstadoRequisicao.APROVADA and pode_emitir %}
            <hr>
            <h6 class="fw-bold">Emitir pedido de compra</h6>
            <form method="POST"
                  action="{{ url_for('compras.requisicao_emitir_pedido', requisicao_id=requisicao.id) }}">
              <label class="form-label small mb-1">Fornecedor</label>
              <select name="fornecedor_id" class="form-select form-select-sm mb-2" required>
                <option value="">Selecione…</option>
                {% for f in fornecedores %}
                  <option value="{{ f.id }}">{{ f.nome }}</option>
                {% endfor %}
              </select>

              <label class="form-label small mb-1">Nº da NF/recibo (opcional)</label>
              <input type="text" name="numero" class="form-control form-control-sm mb-2">

              <label class="form-label small mb-1">Data da compra</label>
              <input type="date" name="data_compra" class="form-control form-control-sm mb-2"
                     value="{{ hoje }}" required>

              <label class="form-label small mb-1">Condição de pagamento</label>
              <select name="condicao_pagamento" class="form-select form-select-sm mb-2">
                {% for chave, rotulo in CONDICOES.items() %}
                  <option value="{{ chave }}">{{ rotulo }}</option>
                {% endfor %}
              </select>

              <label class="form-label small mb-1">Parcelas</label>
              <input type="number" name="parcelas" min="1" value="1"
                     class="form-control form-control-sm mb-2">

              <p class="small text-muted mb-2">
                Preço fechado por item (vazio = usa o estimado). O total não
                pode ultrapassar os R$ {{ '%.2f'|format(requisicao.valor_estimado or 0) }} aprovados.
              </p>
              {% for i in itens %}
                <div class="input-group input-group-sm mb-1">
                  <span class="input-group-text" style="max-width:60%">
                    {{ i.descricao[:28] }}
                  </span>
                  <input type="text" name="item_preco_real[]"
                         class="form-control"
                         placeholder="{{ '%.2f'|format(i.preco_estimado or 0) }}">
                </div>
              {% endfor %}

              <button class="btn btn-primary w-100 mt-2">
                <i class="fas fa-file-invoice-dollar me-1"></i> Emitir pedido
              </button>
            </form>
          {% endif %}
```

E, em `compras_views.py`, na rota `requisicao_detalhe`, acrescente ao `render_template` os três contextos que o bloco acima usa:

```python
        fornecedores=Fornecedor.query.filter_by(
            admin_id=requisicao.admin_id, ativo=True).order_by(
                Fornecedor.nome).all(),
        CONDICOES=CONDICOES,
        hoje=date.today().isoformat(),
```

- [ ] **Step 7: Aplique a migration e rode**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "244|ERRO|ERROR"
python -m pytest tests/test_fase3_alcada.py tests/test_fase3_requisicao.py -v
python -m pytest tests/test_compras_tipo.py -v
```

Esperado: `[Migration 244] Concluída com sucesso`, todos os testes da Fase 3 passam, e `test_compras_tipo.py` (o fluxo antigo) **não regride**.

- [ ] **Step 8: Commit**

```bash
git add models.py migrations.py compras_views.py templates/compras/requisicao_detalhe.html tests/test_fase3_alcada.py
git commit -m "feat(fase3): emissao de pedido a partir de requisicao aprovada

pedido_compra.requisicao_id (NULL = avulso legado). A obra e a etapa vem
da REQUISICAO, nao do formulario — nao ha campo para esvaziar. Tres
guardas: estado APROVADA, quem aprovou nao emite (quando a faixa exigiu
2+), e o pedido nao pode estourar o valor aprovado. O processamento e o
mesmo processar_compra_normal de sempre."
```

---

## Task 9: Com a governança ligada, nenhum pedido nasce sem aprovação

**Files:**
- Modify: `compras_views.py:533-540` (início de `nova_post`)
- Test: `tests/test_fase3_alcada.py` (acrescenta)

Este é o teste de aceitação da fase inteira: *"nenhum PO emitido sem aprovação registrada, provado por teste"* (`DEVOLUTIVA.md:233`).

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao final de `tests/test_fase3_alcada.py`:

```python
# ---------------------------------------------------------------------------
# Guard de governança no registro direto de compra
# ---------------------------------------------------------------------------

def _post_compra_direta(cliente, obra_id, fornecedor_id):
    return cliente.post('/compras/nova', data={
        'fornecedor_id': str(fornecedor_id),
        'data_compra': '2026-08-01',
        'condicao_pagamento': 'a_vista',
        'parcelas': '1',
        'obra_id': str(obra_id),
        'tipo_compra': 'normal',
        'item_descricao[]': ['Perfil U90'],
        'item_quantidade[]': ['10'],
        'item_preco[]': ['18,50'],
        'item_almoxarifado_id[]': [''],
    }, follow_redirects=False)


def _admin_obra_fornecedor():
    from models import Fornecedor
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        forn = Fornecedor(nome='Forn', cnpj=uuid.uuid4().hex[:14],
                          admin_id=admin.id, ativo=True)
        db.session.add(forn)
        db.session.commit()
        return admin.id, obra.id, forn.id


def test_com_flag_desligada_o_fluxo_antigo_continua_funcionando():
    """Nenhuma empresa pode acordar sem conseguir registrar compra."""
    from models import PedidoCompra

    aid, oid, fid = _admin_obra_fornecedor()
    r = _post_compra_direta(_cliente_de(aid), oid, fid)
    assert r.status_code == 302
    with app.app_context():
        assert PedidoCompra.query.filter_by(admin_id=aid).count() == 1


def test_com_flag_ligada_pedido_sem_requisicao_e_recusado():
    from models import PedidoCompra
    from scripts.flag_compras_governanca import definir_flag

    aid, oid, fid = _admin_obra_fornecedor()
    with app.app_context():
        definir_flag(aid, True)

    r = _post_compra_direta(_cliente_de(aid), oid, fid)
    assert r.status_code == 302
    with app.app_context():
        assert PedidoCompra.query.filter_by(admin_id=aid).count() == 0, (
            'pedido nasceu sem requisição aprovada com a governança ligada')


def test_com_flag_ligada_a_emissao_pela_requisicao_continua_funcionando():
    """A governança fecha o atalho, não o caminho."""
    from models import PedidoCompra
    from scripts.flag_compras_governanca import definir_flag

    c = _cenario_aprovado()
    with app.app_context():
        definir_flag(c['admin'], True)

    _cliente_de(c['comprador']).post(
        f"/compras/requisicoes/{c['req']}/emitir-pedido",
        data={'fornecedor_id': str(c['fornecedor']),
              'data_compra': '2026-08-01', 'condicao_pagamento': 'a_vista'},
        follow_redirects=False)
    with app.app_context():
        assert PedidoCompra.query.filter_by(requisicao_id=c['req']).count() == 1
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase3_alcada.py -v -k "flag_desligada or flag_ligada"
```

Esperado: `test_com_flag_ligada_pedido_sem_requisicao_e_recusado` FALHA (o pedido é criado); os outros dois passam.

- [ ] **Step 3: Acrescente o guard**

Em `compras_views.py`, na função `nova_post` (linha 533), logo **depois** do bloco `guard = _check_v2()` e **antes** de `admin_id = _admin_id()`, insira:

```python
    # ── Fase 3 — governança de compras ────────────────────────────────────
    # Com `compras_governanca_ativa` ligada para o tenant, esta rota deixa
    # de ser um caminho para criar pedido: todo pedido tem que sair de uma
    # requisição aprovada (compras.requisicao_emitir_pedido), que grava
    # quem aprovou, quando e por quanto em requisicao_transicao.
    #
    # A flag existe porque desligar este atalho sem aviso travaria o
    # registro de compra de quem está em obra hoje. Default FALSE; liga-se
    # por tenant com scripts/flag_compras_governanca.py, e o runbook em
    # docs/fase-3-rollout.md diz em que ordem.
    from scripts.flag_compras_governanca import governanca_ativa

    if governanca_ativa(_admin_id()):
        flash('A governança de compras está ativa nesta empresa: todo pedido '
              'precisa sair de uma requisição aprovada. Abra a requisição, '
              'passe pela alçada e emita o pedido por lá.', 'warning')
        return redirect(url_for('compras.requisicao_nova'))
```

Faça o mesmo em `nova` (o GET, linha 501), logo após o `guard = _check_v2()`, para que o usuário não preencha um formulário que vai ser recusado:

```python
    from scripts.flag_compras_governanca import governanca_ativa

    if governanca_ativa(_admin_id()):
        flash('A governança de compras está ativa: comece pela requisição.',
              'info')
        return redirect(url_for('compras.requisicao_nova'))
```

- [ ] **Step 4: Rode os testes**

```bash
python -m pytest tests/test_fase3_alcada.py -v
python -m pytest tests/test_compras_tipo.py tests/test_compras_nova_dropdown.py -v
```

Esperado: os da Fase 3 passam; os dois arquivos antigos de compras **não regridem** (eles rodam com a flag desligada, que é o default).

- [ ] **Step 5: Commit**

```bash
git add compras_views.py tests/test_fase3_alcada.py
git commit -m "feat(fase3): com a governanca ligada, pedido exige requisicao aprovada

O teste de aceitacao da fase (DEVOLUTIVA:233). Atras de flag por tenant:
desligada, compras_views.nova_post funciona identico ao de hoje; ligada,
recusa e manda abrir requisicao. A governanca fecha o atalho, nao o
caminho — a emissao pela requisicao continua funcionando."
```

---

## Task 10: Fechar os furos do portal por token (incondicional)

**Files:**
- Modify: `models.py` (`Obra.token_cliente_expira_em` após a linha 261; modelo `PortalAcessoEvento`)
- Modify: `migrations.py` (migration 247 + registro)
- Modify: `portal_obras_views.py:49-56, 343-374, 471-489`
- Test: `tests/test_fase3_portal_seguranca.py`

> Estas correções **não** ficam atrás da flag. Não são mudança de fluxo — são falha de segurança. Um POST anônimo que cria `GestaoCustoPai` com `status='PAGO'` (`portal_obras_views.py:361` → `compras_views.py:314-323`) não é uma comodidade que se liga por tenant.

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_fase3_portal_seguranca.py`:

```python
"""Fase 3 — os cinco POSTs anônimos do portal do cliente.

O portal é um sistema de identidade paralelo: `Obra.token_cliente`
(models.py:261) é `String(255) unique`, SEM coluna de expiração, SEM
escopo de ação e SEM revogação individual. Cinco rotas POST mutam estado
só com a URL:

  portal_obras_views.py:343  /compra/<id>/aprovar     → cria custo!
  portal_obras_views.py:377  /compra/<id>/recusar
  portal_obras_views.py:388  /compra/<id>/comprovante → upload
  portal_obras_views.py:432  /mapa/<id>/aprovar
  portal_obras_views.py:546  /mapa-v2/<id>/selecionar

Estes testes travam as correções incondicionais da Task 10.
"""
import os
import sys
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import (Cliente, Fornecedor, Obra, PedidoCompra, TipoUsuario,
                    Usuario)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase3-portal'
    yield


def _admin():
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'f3s_{suf}', email=f'f3s_{suf}@test.local', nome=f'Adm {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
    db.session.add(u)
    db.session.commit()
    return u


def _obra_com_token(admin_id, expira_em='padrao'):
    import secrets
    suf = uuid.uuid4().hex[:8]
    cliente = Cliente(nome=f'Cliente {suf}', admin_id=admin_id)
    db.session.add(cliente)
    db.session.commit()
    o = Obra(nome=f'Obra {suf}', codigo=f'O{suf[:6].upper()}',
             data_inicio=date(2026, 1, 1), admin_id=admin_id,
             cliente_id=cliente.id, ativo=True, portal_ativo=True,
             token_cliente=secrets.token_urlsafe(32))
    if expira_em != 'padrao':
        o.token_cliente_expira_em = expira_em
    db.session.add(o)
    db.session.commit()
    return o


def _compra(admin_id, obra_id, tipo='aprovacao_cliente'):
    suf = uuid.uuid4().hex[:14]
    forn = Fornecedor(nome='Forn', cnpj=suf, admin_id=admin_id, ativo=True)
    db.session.add(forn)
    db.session.commit()
    p = PedidoCompra(
        fornecedor_id=forn.id, data_compra=date(2026, 8, 1), obra_id=obra_id,
        condicao_pagamento='a_vista', parcelas=1,
        valor_total=Decimal('1000.00'), tipo_compra=tipo,
        processada_apos_aprovacao=False, admin_id=admin_id,
        status_aprovacao_cliente=('AGUARDANDO_APROVACAO_CLIENTE'
                                  if tipo == 'aprovacao_cliente' else None))
    db.session.add(p)
    db.session.commit()
    return p


# ---------------------------------------------------------------------------
# 1 — a rota de aprovar não pode tocar em compra que não é do cliente
# ---------------------------------------------------------------------------

def test_portal_nao_aprova_compra_do_tipo_normal():
    """portal_obras_views.py:354 gravava APROVADO em QUALQUER PedidoCompra
    da obra — o único filtro era obra_id (:346). Compra 'normal' nunca
    passou pelo cliente e não pode ser marcada como aprovada por ele."""
    with app.app_context():
        admin = _admin()
        obra = _obra_com_token(admin.id)
        compra = _compra(admin.id, obra.id, tipo='normal')
        token, cid = obra.token_cliente, compra.id

    anon = app.test_client()
    r = anon.post(f'/portal/obra/{token}/compra/{cid}/aprovar',
                  follow_redirects=False)
    assert r.status_code in (302, 403, 404)
    with app.app_context():
        assert db.session.get(PedidoCompra, cid).status_aprovacao_cliente is None


# ---------------------------------------------------------------------------
# 2 — expiração do token
# ---------------------------------------------------------------------------

def test_token_expirado_nao_abre_o_portal():
    with app.app_context():
        admin = _admin()
        obra = _obra_com_token(
            admin.id, expira_em=datetime.utcnow() - timedelta(days=1))
        token = obra.token_cliente

    anon = app.test_client()
    assert anon.get(f'/portal/obra/{token}').status_code == 404


def test_token_expirado_nao_muta_estado():
    with app.app_context():
        admin = _admin()
        obra = _obra_com_token(
            admin.id, expira_em=datetime.utcnow() - timedelta(days=1))
        compra = _compra(admin.id, obra.id)
        token, cid = obra.token_cliente, compra.id

    anon = app.test_client()
    r = anon.post(f'/portal/obra/{token}/compra/{cid}/aprovar',
                  follow_redirects=False)
    assert r.status_code == 404
    with app.app_context():
        assert db.session.get(PedidoCompra, cid).status_aprovacao_cliente == \
            'AGUARDANDO_APROVACAO_CLIENTE'


def test_token_sem_data_de_expiracao_continua_valendo():
    """Deploy não pode derrubar portal de obra em andamento: token antigo
    sem data segue valendo até ser rotacionado."""
    with app.app_context():
        admin = _admin()
        obra = _obra_com_token(admin.id, expira_em=None)
        token = obra.token_cliente

    anon = app.test_client()
    assert anon.get(f'/portal/obra/{token}').status_code == 200


def test_toggle_do_portal_carimba_a_expiracao():
    from portal_obras_views import PRAZO_TOKEN_DIAS

    with app.app_context():
        admin = _admin()
        obra = _obra_com_token(admin.id, expira_em=None)
        obra.portal_ativo = False
        obra.token_cliente = None
        db.session.commit()
        aid, oid = admin.id, obra.id

    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(aid)
        sess['_fresh'] = True
    c.post(f'/portal/obra/{oid}/portal-toggle', follow_redirects=False)

    with app.app_context():
        obra = db.session.get(Obra, oid)
        assert obra.token_cliente
        assert obra.token_cliente_expira_em is not None
        delta = obra.token_cliente_expira_em - datetime.utcnow()
        assert timedelta(days=PRAZO_TOKEN_DIAS - 1) < delta <= \
            timedelta(days=PRAZO_TOKEN_DIAS)


# ---------------------------------------------------------------------------
# 3 — trilha de acesso
# ---------------------------------------------------------------------------

def test_post_no_portal_grava_trilha_com_ip():
    from models import PortalAcessoEvento

    with app.app_context():
        admin = _admin()
        obra = _obra_com_token(admin.id)
        compra = _compra(admin.id, obra.id)
        token, oid, cid = obra.token_cliente, obra.id, compra.id

    anon = app.test_client()
    anon.post(f'/portal/obra/{token}/compra/{cid}/aprovar',
              environ_base={'REMOTE_ADDR': '203.0.113.7'},
              headers={'User-Agent': 'pytest-portal'})

    with app.app_context():
        eventos = PortalAcessoEvento.query.filter_by(obra_id=oid).all()
        assert eventos, 'POST anônimo no portal não deixou trilha'
        assert any(e.ip == '203.0.113.7' for e in eventos)
        assert any('pytest-portal' in (e.user_agent or '') for e in eventos)
        assert any(e.acao == 'compra_aprovar' for e in eventos)
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase3_portal_seguranca.py -v
```

Esperado: FAIL na coleção e nos testes — `token_cliente_expira_em` e `PortalAcessoEvento` não existem, e a compra `normal` **é** aprovada pelo anônimo.

- [ ] **Step 3: Acrescente a coluna de expiração e a tabela de trilha**

Em `models.py`, dentro da `class Obra`, imediatamente após `token_cliente` (linha 261), insira:

```python
    # Fase 3 — expiração do token do portal. Até 2026-07-21 o token não
    # expirava NUNCA: quem tivesse a URL mantinha acesso (e poder de POST)
    # para sempre, inclusive ex-cliente e link vazado em grupo de
    # mensagem. NULLABLE de propósito: token já emitido sem data continua
    # valendo até ser rotacionado, para que o deploy não derrube portal de
    # obra em andamento. O carimbo entra no `toggle_portal`.
    token_cliente_expira_em = db.Column(db.DateTime, nullable=True)
```

E, ao final do arquivo `models.py` (ou junto dos modelos de portal), acrescente:

```python
class PortalAcessoEvento(db.Model):
    """Trilha dos acessos que MUTAM estado pelo portal por token — Fase 3.

    O portal é anônimo por construção (portal_obras_views.py:3). Isso
    significa que, até esta tabela existir, uma aprovação de compra pelo
    portal produzia um GestaoCustoPai atribuído ao ADMIN do tenant
    (portal_obras_views.py:360-361, `usuario_id=compra.admin_id`) — a
    trilha do almoxarifado registrava como autor alguém que não fez a
    ação.

    Não identifica pessoa (não há como, sem login — isso é a Fase 9a).
    Identifica ORIGEM: IP, user-agent e momento. É o suficiente para
    responder "de onde veio essa aprovação?" numa auditoria, e para
    detectar um token vazado sendo usado de vários lugares.
    """
    __tablename__ = 'portal_acesso_evento'
    __table_args__ = (
        db.Index('ix_portal_acesso_obra_criado', 'obra_id', 'criado_em'),
    )

    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id', ondelete='CASCADE'),
                        nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    acao = db.Column(db.String(50), nullable=False)
    alvo_tipo = db.Column(db.String(40), nullable=True)   # 'pedido_compra', 'mapa_v2'…
    alvo_id = db.Column(db.Integer, nullable=True)
    ip = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(300), nullable=True)
    detalhes = db.Column(db.JSON, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    obra = db.relationship('Obra', foreign_keys=[obra_id])

    def __repr__(self):
        return f'<PortalAcessoEvento {self.acao} obra={self.obra_id} ip={self.ip}>'
```

- [ ] **Step 4: Escreva a migration 247 e registre**

Em `migrations.py`, antes de `def executar_migracoes():`, insira:

```python
def migration_247_portal_token_expiracao_e_trilha():
    """Fase 3 — obra.token_cliente_expira_em + tabela portal_acesso_evento.

    Aditiva e idempotente. A coluna nasce NULL em todas as obras: token já
    emitido continua valendo até ser rotacionado pelo toggle do portal.
    Isso é deliberado — carimbar uma data retroativa derrubaria o portal
    de toda obra em andamento no dia do deploy.
    """
    logger.info("[Migration 247] Iniciando — expiração de token + trilha do portal")

    db.session.execute(text("""
        ALTER TABLE obra
        ADD COLUMN IF NOT EXISTS token_cliente_expira_em TIMESTAMP
    """))
    db.session.commit()

    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS portal_acesso_evento (
            id SERIAL PRIMARY KEY,
            obra_id INTEGER NOT NULL REFERENCES obra(id) ON DELETE CASCADE,
            admin_id INTEGER NOT NULL REFERENCES usuario(id),
            acao VARCHAR(50) NOT NULL,
            alvo_tipo VARCHAR(40),
            alvo_id INTEGER,
            ip VARCHAR(64),
            user_agent VARCHAR(300),
            detalhes JSONB,
            criado_em TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """))
    db.session.commit()

    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_portal_acesso_obra_criado
        ON portal_acesso_evento (obra_id, criado_em)
    """))
    db.session.commit()

    logger.info("[Migration 247] Concluída com sucesso")
```

Registre em `migrations_to_run`, após a `246`:

```python
            (247, "Fase 3 — obra.token_cliente_expira_em + trilha portal_acesso_evento (IP/UA)", migration_247_portal_token_expiracao_e_trilha),
```

- [ ] **Step 5: Aplique as correções em `portal_obras_views.py`**

**5a.** No topo do arquivo, após a linha 42 (`ALLOWED_EXTENSIONS = ...`), acrescente:

```python
# Fase 3 — prazo de validade do token do portal. 180 dias é deliberadamente
# longo: token curto gera chamado de suporte a cada obra, e a equipe acaba
# desligando a expiração. 180 dias fecha a janela do ex-cliente e do link
# vazado sem atrapalhar a obra em curso. Ver decisão D4 do plano da Fase 3.
PRAZO_TOKEN_DIAS = 180
```

E acrescente `PortalAcessoEvento` ao import de `models` (linha 22-27).

**5b.** Substitua `_get_obra_by_token` (linhas 49-55) por:

```python
def _get_obra_by_token(token: str) -> Obra:
    """Para rotas de ação (POST): retorna a Obra ativa ou aborta com 404.

    Portal desativado é tratado como ausência para evitar mutações.

    Fase 3 — token EXPIRADO também é ausência. Até 2026-07-21 o token não
    expirava nunca (`models.py:261` é só um String(255) unique), então
    qualquer URL vazada continuava aprovando compra indefinidamente.
    Token sem data (`token_cliente_expira_em IS NULL`) continua valendo:
    são os emitidos antes da migration 247, e derrubá-los tiraria o portal
    de obra em andamento.
    """
    obra = Obra.query.filter_by(token_cliente=token, portal_ativo=True).first()
    if not obra:
        abort(404)
    if obra.token_cliente_expira_em and \
            obra.token_cliente_expira_em < datetime.utcnow():
        logger.warning('[PORTAL] token expirado usado — obra %s (expirou em %s)',
                       obra.id, obra.token_cliente_expira_em)
        abort(404)
    return obra
```

**5c.** Aplique a mesma verificação em `_resolve_obra_for_view` (linhas 58-76): logo após `if not obra: abort(404)` (linha 65), insira:

```python
    if obra.token_cliente_expira_em and \
            obra.token_cliente_expira_em < datetime.utcnow():
        logger.warning('[PORTAL] token expirado (GET) — obra %s', obra.id)
        abort(404)
```

**5d.** Acrescente a função de trilha, logo abaixo de `_resolve_obra_for_view`:

```python
def _registrar_acesso(obra, acao, alvo_tipo=None, alvo_id=None, detalhes=None):
    """Grava PortalAcessoEvento com IP e user-agent. NÃO commita.

    Nunca levanta: uma falha de auditoria não pode impedir o cliente de
    aprovar uma compra — mas o log fica, para que a falha apareça.

    `X-Forwarded-For` vem primeiro porque a aplicação roda atrás de proxy
    (EasyPanel); sem isso, todo evento registraria o IP do proxy.
    """
    try:
        encaminhado = request.headers.get('X-Forwarded-For', '')
        ip = (encaminhado.split(',')[0].strip() if encaminhado
              else (request.remote_addr or ''))[:64]
        db.session.add(PortalAcessoEvento(
            obra_id=obra.id,
            admin_id=obra.admin_id,
            acao=acao,
            alvo_tipo=alvo_tipo,
            alvo_id=alvo_id,
            ip=ip or None,
            user_agent=(request.headers.get('User-Agent') or '')[:300] or None,
            detalhes=detalhes,
        ))
    except Exception as e:
        logger.error('[PORTAL] falha ao registrar trilha de acesso: %s', e)
```

**5e.** Em `aprovar_compra` (linha 343), substitua o corpo entre a linha 346 e a 352 por:

```python
    compra = PedidoCompra.query.filter_by(id=compra_id, obra_id=obra.id).first_or_404()

    # Fase 3 — o portal só decide sobre compra que FOI enviada ao cliente.
    # Até 2026-07-21 a linha 354 gravava 'APROVADO' em qualquer pedido da
    # obra, inclusive nos de tipo_compra='normal', que nunca passaram pelo
    # cliente. O único filtro era obra_id.
    if compra.tipo_compra != 'aprovacao_cliente':
        _registrar_acesso(obra, 'compra_aprovar_recusado', 'pedido_compra',
                          compra_id, {'motivo': 'tipo_compra != aprovacao_cliente',
                                      'tipo_compra': compra.tipo_compra})
        db.session.commit()
        logger.warning('[PORTAL] tentativa de aprovar compra %s do tipo %s '
                       'pela obra %s', compra_id, compra.tipo_compra, obra.id)
        flash('Esta compra não está em aprovação do cliente.', 'warning')
        return redirect(url_for('portal_obras.portal_obra', token=token))

    _registrar_acesso(obra, 'compra_aprovar', 'pedido_compra', compra_id,
                      {'valor_total': str(compra.valor_total)})

    # Já aprovada? idempotente
    if compra.status_aprovacao_cliente == 'APROVADO' and compra.processada_apos_aprovacao:
        db.session.commit()   # persiste a trilha do acesso
        flash('Esta compra já foi aprovada e processada.', 'info')
        return redirect(url_for('portal_obras.portal_obra', token=token))
```

**5f.** Acrescente `_registrar_acesso` às outras quatro rotas mutantes, logo após a linha que resolve o objeto:

- `recusar_compra` (após a linha 380):
  ```python
      _registrar_acesso(obra, 'compra_recusar', 'pedido_compra', compra_id)
  ```
- `upload_comprovante` (após a linha 391):
  ```python
      _registrar_acesso(obra, 'compra_comprovante', 'pedido_compra', compra_id)
  ```
- `aprovar_mapa_concorrencia` (após a linha 438):
  ```python
      _registrar_acesso(obra, 'mapa_v1_aprovar', 'mapa_concorrencia', mapa_id)
  ```
- `selecionar_mapa_v2` (após a linha 552):
  ```python
      _registrar_acesso(obra, 'mapa_v2_selecionar', 'mapa_concorrencia_v2', mapa_id)
  ```

Todas as quatro já commitam adiante no corpo, então a trilha vai junto.

**5g.** Em `toggle_portal` (linhas 471-489), substitua o bloco de geração de token (linhas 480-481) por:

```python
    if obra.portal_ativo:
        # Fase 3 — rotacionar o token e carimbar a validade a cada vez que
        # o portal é (re)aberto. Antes, o token era gerado uma vez e valia
        # para sempre; reabrir o portal reaproveitava a MESMA URL, o que
        # tornava o "desligar o portal" uma revogação apenas temporária.
        if not obra.token_cliente:
            obra.token_cliente = secrets.token_urlsafe(32)
        obra.token_cliente_expira_em = (
            datetime.utcnow() + timedelta(days=PRAZO_TOKEN_DIAS))
```

E acrescente `timedelta` ao import de `datetime` no topo (linha 12):

```python
from datetime import date, datetime, timedelta
```

- [ ] **Step 6: Aplique a migration e rode**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "247|ERRO|ERROR"
python -m pytest tests/test_fase3_portal_seguranca.py -v
```

Esperado: `[Migration 247] Concluída com sucesso` e os 6 testes PASSAM.

- [ ] **Step 7: Commit**

```bash
git add models.py migrations.py portal_obras_views.py tests/test_fase3_portal_seguranca.py
git commit -m "fix(sec,fase3): fecha os furos do portal por token

Tres correcoes INCONDICIONAIS (nao ficam atras de flag, sao falha de
seguranca):
1. /compra/<id>/aprovar so aceita tipo_compra='aprovacao_cliente'. Antes
   gravava APROVADO em qualquer pedido da obra — o unico filtro era obra_id.
2. obra.token_cliente_expira_em (180 dias, carimbado no toggle do portal).
   O token nunca expirava; URL vazada aprovava compra para sempre.
3. portal_acesso_evento grava IP e user-agent dos 5 POSTs anonimos. Sem
   login nao da para saber QUEM; da para saber DE ONDE."
```

---

## Task 11: Com a governança ligada, o cliente dá ciência — não cria custo

**Files:**
- Modify: `portal_obras_views.py` (`aprovar_compra`)
- Test: `tests/test_fase3_portal_seguranca.py` (acrescenta)

> Esta é a mudança de **fluxo**, e por isso fica atrás da flag. Com `compras_governanca_ativa` desligada, o portal continua fazendo o que faz hoje. Com ela ligada, a aprovação do cliente deixa de ser o gatilho financeiro: ela grava a ciência, e quem emite o custo é a cadeia interna de alçada. O POST anônimo passa a ser um **dado de entrada**, não uma escritura.

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao final de `tests/test_fase3_portal_seguranca.py`:

```python
# ---------------------------------------------------------------------------
# Governança ligada: o cliente dá ciência, não cria custo
# ---------------------------------------------------------------------------

def test_sem_governanca_o_portal_continua_criando_custo():
    """Comportamento de hoje, preservado enquanto a flag estiver desligada."""
    from models import GestaoCustoPai

    with app.app_context():
        admin = _admin()
        obra = _obra_com_token(admin.id)
        compra = _compra(admin.id, obra.id)
        token, cid, aid = obra.token_cliente, compra.id, admin.id

    anon = app.test_client()
    anon.post(f'/portal/obra/{token}/compra/{cid}/aprovar',
              follow_redirects=False)

    with app.app_context():
        compra = db.session.get(PedidoCompra, cid)
        assert compra.status_aprovacao_cliente == 'APROVADO'
        assert compra.processada_apos_aprovacao is True
        assert GestaoCustoPai.query.filter_by(
            admin_id=aid, tipo_categoria='FATURAMENTO_DIRETO').count() == 1


def test_com_governanca_o_portal_registra_ciencia_sem_criar_custo():
    from models import GestaoCustoPai
    from scripts.flag_compras_governanca import definir_flag

    with app.app_context():
        admin = _admin()
        obra = _obra_com_token(admin.id)
        compra = _compra(admin.id, obra.id)
        definir_flag(admin.id, True)
        token, cid, aid = obra.token_cliente, compra.id, admin.id

    anon = app.test_client()
    anon.post(f'/portal/obra/{token}/compra/{cid}/aprovar',
              follow_redirects=False)

    with app.app_context():
        compra = db.session.get(PedidoCompra, cid)
        # a ciência do cliente FICA registrada…
        assert compra.status_aprovacao_cliente == 'APROVADO'
        # …mas o custo NÃO nasceu de um POST anônimo
        assert compra.processada_apos_aprovacao is False
        assert GestaoCustoPai.query.filter_by(
            admin_id=aid, tipo_categoria='FATURAMENTO_DIRETO').count() == 0


def test_com_governanca_a_trilha_marca_ciencia():
    from models import PortalAcessoEvento
    from scripts.flag_compras_governanca import definir_flag

    with app.app_context():
        admin = _admin()
        obra = _obra_com_token(admin.id)
        compra = _compra(admin.id, obra.id)
        definir_flag(admin.id, True)
        token, cid, oid = obra.token_cliente, compra.id, obra.id

    anon = app.test_client()
    anon.post(f'/portal/obra/{token}/compra/{cid}/aprovar',
              follow_redirects=False)

    with app.app_context():
        eventos = PortalAcessoEvento.query.filter_by(
            obra_id=oid, acao='compra_aprovar').all()
        assert eventos
        assert any((e.detalhes or {}).get('modo') == 'ciencia' for e in eventos)
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase3_portal_seguranca.py -v -k governanca
```

Esperado: `test_sem_governanca...` passa; os dois `com_governanca` FALHAM — o custo é criado do mesmo jeito.

- [ ] **Step 3: Aplique a bifurcação em `aprovar_compra`**

Em `portal_obras_views.py`, dentro do `try:` de `aprovar_compra`, substitua o bloco que hoje vai da linha 354 à 361 (`compra.status_aprovacao_cliente = 'APROVADO'` até a chamada de `processar_compra_aprovada_cliente`) por:

```python
        compra.status_aprovacao_cliente = 'APROVADO'

        # ── Fase 3 ────────────────────────────────────────────────────────
        # Com a governança de compras ligada, a decisão do cliente é
        # CIÊNCIA, não lançamento. O que criava GestaoCustoPai com
        # status='PAGO' aqui era um POST sem autenticação nenhuma
        # (o portal é anônimo por construção — ver o docstring do módulo),
        # e o movimento de almoxarifado saía atribuído ao ADMIN do tenant,
        # que não fez a ação.
        #
        # Com a flag ligada, quem emite o custo é a cadeia interna de
        # alçada (compras.requisicao_emitir_pedido), onde existe usuário
        # autenticado, papel na obra e trilha em requisicao_transicao.
        from scripts.flag_compras_governanca import governanca_ativa

        sob_governanca = governanca_ativa(obra.admin_id)

        if sob_governanca:
            _registrar_acesso(
                obra, 'compra_aprovar', 'pedido_compra', compra_id,
                {'modo': 'ciencia', 'valor_total': str(compra.valor_total)})
            db.session.commit()
            logger.info('[PORTAL] Compra %s — ciência do cliente registrada '
                        '(governança ativa; custo NÃO gerado aqui). Obra %s',
                        compra_id, obra.id)
            flash('Sua aprovação foi registrada. A compra segue para '
                  'liberação interna antes de ser efetivada.', 'success')
            return redirect(url_for('portal_obras.portal_obra', token=token))

        # Comportamento anterior à Fase 3, preservado com a flag desligada.
        if compra.tipo_compra == 'aprovacao_cliente' and not compra.processada_apos_aprovacao:
            from compras_views import processar_compra_aprovada_cliente
            # usuario_id = admin do tenant (portal é anônimo, não tem current_user)
            processar_compra_aprovada_cliente(compra, usuario_id=compra.admin_id)
```

> **Atenção à posição.** O `_registrar_acesso(obra, 'compra_aprovar', ...)` que a Task 10 inseriu **antes** do bloco idempotente continua lá e grava o evento sem `modo`. Com a governança ligada, o bloco acima grava um **segundo** evento, esse com `{'modo': 'ciencia'}`. Isso é de propósito: o primeiro registra que a URL foi acionada; o segundo, o que o sistema decidiu fazer com o acionamento. O teste `test_com_governanca_a_trilha_marca_ciencia` usa `any(...)` justamente por isso.

- [ ] **Step 4: Documente o caminho de saída no template do portal**

Em `templates/portal/` — localize o template que renderiza os botões de aprovar/recusar:

```bash
grep -rln "compra/.*aprovar\|aprovar_compra" templates/portal/
```

No card de compra pendente, acrescente abaixo do botão de aprovar:

```html
              <p class="small text-muted mt-2 mb-0">
                Ao aprovar, sua decisão fica registrada e a compra segue para
                liberação interna da construtora antes de ser efetivada.
              </p>
```

Se o `grep` não retornar nada (o bloco pode estar em `templates/portal/portal_obra.html` sob outro nome de rota), abra o template renderizado por `portal_obras_views.py:portal_obra` e procure por `compras_pendentes` — é o contexto passado em `portal_obras_views.py:330`.

- [ ] **Step 5: Rode os testes**

```bash
python -m pytest tests/test_fase3_portal_seguranca.py -v
python -m pytest tests/test_compras_tipo.py -v
```

Esperado: os 9 testes do portal passam e `test_compras_tipo.py` **não regride** — ele exercita `processar_compra_aprovada_cliente` diretamente, sem flag, e continua verde.

- [ ] **Step 6: Commit**

```bash
git add portal_obras_views.py templates/portal tests/test_fase3_portal_seguranca.py
git commit -m "feat(sec,fase3): sob governanca, a aprovacao do cliente e ciencia

Com compras_governanca_ativa ligada, o POST anonimo do portal grava a
decisao do cliente mas NAO chama processar_compra_aprovada_cliente — o
custo passa a nascer da cadeia interna de alcada, onde ha usuario
autenticado, papel na obra e trilha. Flag desligada: comportamento
identico ao de hoje."
```

---

## Task 12: Matriz de regressão, runbook e gate

**Files:**
- Create: `tests/test_fase3_matriz_governanca.py`
- Create: `docs/fase-3-rollout.md`
- Test: gate completo

- [ ] **Step 1: Escreva a matriz**

Crie `tests/test_fase3_matriz_governanca.py`:

```python
"""Fase 3 — matriz ator × ação, num arquivo só.

Os arquivos test_fase3_requisicao.py e test_fase3_alcada.py testam as
peças. Este testa a TABELA: sete atores contra as quatro ações que a fase
introduz, para que uma permissão nova nunca entre sem aparecer aqui.
"""
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401
from app import app, db
from models import (Cliente, EstadoRequisicao, Fornecedor, Obra, PapelObra,
                    RequisicaoCompra, RequisicaoCompraItem, TipoUsuario,
                    Usuario, UsuarioObra)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase3-matriz'
    yield


def _usuario(tipo, admin_id=None, nome='U'):
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'f3m_{suf}', email=f'f3m_{suf}@test.local',
        nome=f'{nome} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=tipo, ativo=True, versao_sistema='v2',
        admin_id=admin_id)
    db.session.add(u)
    db.session.commit()
    return u


def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


@pytest.fixture
def cenario():
    """Um tenant, uma obra, sete atores, uma requisição aguardando alçada
    de faixa única (1 aprovação, sem exigência de admin)."""
    from models import FaixaAlcada
    from services.requisicao_compra import proximo_numero, recalcular_valor

    with app.app_context():
        admin = _usuario(TipoUsuario.ADMIN, nome='Admin')
        outro_admin = _usuario(TipoUsuario.ADMIN, nome='Outro')

        suf = uuid.uuid4().hex[:8]
        cli = Cliente(nome=f'C {suf}', admin_id=admin.id)
        db.session.add(cli)
        db.session.commit()
        obra = Obra(nome=f'Obra {suf}', codigo=f'O{suf[:6].upper()}',
                    data_inicio=date(2026, 1, 1), admin_id=admin.id,
                    cliente_id=cli.id, ativo=True)
        db.session.add(obra)
        db.session.commit()

        FaixaAlcada.query.filter_by(admin_id=admin.id).delete()
        db.session.add(FaixaAlcada(
            admin_id=admin.id, ordem=1, valor_ate=None,
            aprovacoes_necessarias=1, exige_admin=False,
            exige_mapa_concorrencia=False, ativo=True))

        atores = {'admin': admin, 'outro_tenant': outro_admin}
        for chave, papel in (('gestor', PapelObra.GESTOR),
                             ('comprador', PapelObra.COMPRADOR),
                             ('apontador', PapelObra.APONTADOR),
                             ('leitor', PapelObra.LEITOR)):
            u = _usuario(TipoUsuario.FUNCIONARIO, admin_id=admin.id, nome=chave)
            db.session.add(UsuarioObra(usuario_id=u.id, obra_id=obra.id,
                                       papel=papel, admin_id=admin.id,
                                       ativo=True))
            atores[chave] = u
        atores['sem_vinculo'] = _usuario(TipoUsuario.FUNCIONARIO,
                                        admin_id=admin.id, nome='sem')

        solicitante = _usuario(TipoUsuario.FUNCIONARIO, admin_id=admin.id,
                               nome='Solicitante')
        db.session.add(UsuarioObra(usuario_id=solicitante.id, obra_id=obra.id,
                                   papel=PapelObra.COMPRADOR,
                                   admin_id=admin.id, ativo=True))
        atores['solicitante'] = solicitante

        forn = Fornecedor(nome='F', cnpj=uuid.uuid4().hex[:14],
                          admin_id=admin.id, ativo=True)
        db.session.add(forn)
        db.session.commit()

        req = RequisicaoCompra(
            numero=proximo_numero(admin.id), obra_id=obra.id,
            solicitante_id=solicitante.id, admin_id=admin.id,
            estado=EstadoRequisicao.AGUARDANDO_APROVACAO)
        db.session.add(req)
        db.session.flush()
        db.session.add(RequisicaoCompraItem(
            requisicao_id=req.id, admin_id=admin.id, descricao='Perfil',
            unidade='m', quantidade=Decimal('1.000'),
            preco_estimado=Decimal('100.00')))
        db.session.flush()
        recalcular_valor(req)
        db.session.commit()

        return {
            'ids': {k: v.id for k, v in atores.items()},
            'obra': obra.id, 'req': req.id, 'admin': admin.id,
            'fornecedor': forn.id,
        }


# Matriz: ator → (pode criar requisição, pode aprovar, pode emitir pedido)
MATRIZ = {
    'admin':        (True,  True,  True),
    'gestor':       (True,  True,  False),
    'comprador':    (True,  False, True),
    'apontador':    (False, False, False),
    'leitor':       (False, False, False),
    'sem_vinculo':  (False, False, False),
    'outro_tenant': (False, False, False),
}


@pytest.mark.parametrize('ator', sorted(MATRIZ))
def test_criar_requisicao(ator, cenario):
    esperado = MATRIZ[ator][0]
    antes = None
    with app.app_context():
        antes = RequisicaoCompra.query.filter_by(
            admin_id=cenario['admin']).count()

    _cliente_de(cenario['ids'][ator]).post('/compras/requisicoes/nova', data={
        'obra_id': str(cenario['obra']),
        'justificativa': f'matriz {ator}',
        'item_descricao[]': ['X'], 'item_unidade[]': ['un'],
        'item_quantidade[]': ['1'], 'item_preco[]': ['10'],
        'item_almoxarifado_id[]': [''],
    }, follow_redirects=False)

    with app.app_context():
        depois = RequisicaoCompra.query.filter_by(
            admin_id=cenario['admin']).count()
    criou = depois > antes
    assert criou is esperado, (
        f'{ator}: esperava criar={esperado}, obteve {criou}')


@pytest.mark.parametrize('ator', sorted(MATRIZ))
def test_aprovar_requisicao(ator, cenario):
    esperado = MATRIZ[ator][1]
    _cliente_de(cenario['ids'][ator]).post(
        f"/compras/requisicoes/{cenario['req']}/aprovar",
        follow_redirects=False)
    with app.app_context():
        estado = db.session.get(RequisicaoCompra, cenario['req']).estado
    aprovou = estado == EstadoRequisicao.APROVADA
    assert aprovou is esperado, (
        f'{ator}: esperava aprovar={esperado}, estado ficou {estado}')


@pytest.mark.parametrize('ator', sorted(MATRIZ))
def test_emitir_pedido(ator, cenario):
    """A requisição é levada a APROVADA pelo GESTOR antes de cada tentativa.

    Faixa de 1 aprovação: a guarda de 'quem aprovou não emite' NÃO se
    aplica (ver compras_views.requisicao_emitir_pedido, guarda 2), então
    o gestor falha aqui por não ter papel de COMPRADOR, e não por ter
    aprovado.
    """
    from models import PedidoCompra
    from services.alcada_compras import registrar_aprovacao
    from services.requisicao_compra import transicionar

    esperado = MATRIZ[ator][2]
    with app.app_context():
        req = db.session.get(RequisicaoCompra, cenario['req'])
        gestor = db.session.get(Usuario, cenario['ids']['gestor'])
        registrar_aprovacao(req, gestor, papel='GESTOR')
        transicionar(req, EstadoRequisicao.APROVADA, gestor, motivo='matriz')
        db.session.commit()

    _cliente_de(cenario['ids'][ator]).post(
        f"/compras/requisicoes/{cenario['req']}/emitir-pedido",
        data={'fornecedor_id': str(cenario['fornecedor']),
              'data_compra': '2026-08-01', 'condicao_pagamento': 'a_vista'},
        follow_redirects=False)

    with app.app_context():
        emitiu = PedidoCompra.query.filter_by(
            requisicao_id=cenario['req']).count() > 0
    assert emitiu is esperado, (
        f'{ator}: esperava emitir={esperado}, obteve {emitiu}')


def test_anonimo_nao_alcanca_nenhuma_rota_de_requisicao(cenario):
    anon = app.test_client()
    rotas = [
        ('GET', '/compras/requisicoes'),
        ('GET', '/compras/requisicoes/nova'),
        ('POST', '/compras/requisicoes/nova'),
        ('GET', f"/compras/requisicoes/{cenario['req']}"),
        ('POST', f"/compras/requisicoes/{cenario['req']}/enviar"),
        ('POST', f"/compras/requisicoes/{cenario['req']}/aprovar"),
        ('POST', f"/compras/requisicoes/{cenario['req']}/rejeitar"),
        ('POST', f"/compras/requisicoes/{cenario['req']}/emitir-pedido"),
        ('POST', f"/compras/requisicoes/{cenario['req']}/cancelar"),
    ]
    for metodo, rota in rotas:
        r = anon.open(rota, method=metodo, follow_redirects=False)
        assert r.status_code in (302, 401), (
            f'{metodo} {rota} devolveu {r.status_code} para anônimo')
```

- [ ] **Step 2: Rode a matriz**

```bash
python -m pytest tests/test_fase3_matriz_governanca.py -v
```

Esperado: 22 testes PASSAM (7 atores × 3 ações + 1 de anônimo).

- [ ] **Step 3: Escreva o runbook**

Crie `docs/fase-3-rollout.md`:

```markdown
# Fase 3 — runbook de rollout

Duas coisas foram entregues, e elas têm riscos diferentes.

**As correções de segurança do portal (Task 10) já estão valendo** assim
que o código sobe — não há flag. São elas:

- `/portal/obra/<token>/compra/<id>/aprovar` recusa compra que não seja
  `tipo_compra='aprovacao_cliente'`;
- token do portal expira em 180 dias, carimbado a cada `toggle_portal`;
- os cinco POSTs anônimos gravam IP e user-agent em `portal_acesso_evento`.

**O resto está atrás de `compras_governanca_ativa`, desligada por
padrão.** Todo o risco está em ligá-la.

## Antes de ligar, por tenant

1. **Confira as faixas de alçada.**

       python -c "
       from app import app
       from models import FaixaAlcada
       with app.app_context():
           for f in FaixaAlcada.query.filter_by(admin_id=<ID>).order_by(FaixaAlcada.ordem):
               print(f.ordem, f.valor_ate, f.aprovacoes_necessarias,
                     f.exige_admin, f.exige_mapa_concorrencia)
       "

   Os valores semeados (R$ 5.000 / R$ 30.000 / acima) são a
   **recomendação do plano**, não uma decisão do negócio. Confirme com o
   Cássio antes de ligar. Editar é UPDATE na tabela — não precisa de
   deploy.

2. **Confira que existe quem aprove.** Toda obra ativa do tenant precisa
   de pelo menos um `UsuarioObra` com papel `GESTOR` **que não seja o
   solicitante habitual**, senão as requisições daquela obra travam.

       python -c "
       from app import app
       from models import Obra, UsuarioObra, PapelObra
       with app.app_context():
           for o in Obra.query.filter_by(admin_id=<ID>, ativo=True):
               n = UsuarioObra.query.filter_by(obra_id=o.id, papel=PapelObra.GESTOR, ativo=True).count()
               if n == 0:
                   print('SEM GESTOR:', o.id, o.nome)
       "

   `ADMIN` sempre pode aprovar, então uma obra sem gestor não fica
   bloqueada — mas concentra tudo no dono da empresa.

3. **Confira que existe quem compre.** Pelo menos um `UsuarioObra` com
   papel `COMPRADOR`, ou o ADMIN vira o único que emite pedido.

4. **Ligue a flag.**

       python scripts/flag_compras_governanca.py <ID> --ligar

   O script recusa se o tenant não tiver faixa de alçada ativa.

5. **Faça o ciclo completo numa obra piloto**, com três pessoas
   diferentes: um cria a requisição, outro aprova, um terceiro emite o
   pedido. Confirme que o `GestaoCustoFilho` gerado tem `obra_id`
   preenchido.

## Rollback

Um comando, sem tocar em schema:

    python scripts/flag_compras_governanca.py <ID> --desligar

`compras.nova_post` volta a aceitar pedido direto no mesmo minuto. As
requisições já criadas continuam lá, inertes; as aprovadas continuam
podendo virar pedido.

As correções do portal (Task 10) **não têm rollback por flag**. Se uma
delas quebrar um cliente em produção, o caminho é reverter o commit —
e, no caso específico da expiração, `UPDATE obra SET
token_cliente_expira_em = NULL WHERE id = <ID>` devolve o acesso àquela
obra sem mexer em código.

## O que a Fase 3 deliberadamente NÃO fez

- **Não trocou o token do portal por login de cliente.** É a Fase 9a, e
  exige cadastro e recuperação de senha para o cliente — decisão de
  produto. Aqui o token ganhou prazo e trilha; continua sendo um sistema
  de identidade paralelo, sem escopo de ação.
- **Não criou `Recebimento` como entidade.** O recebimento parcial por
  item já existe (`compras_views.py:841-948`) e não foi refeito. O que
  falta é o recebimento ser o **gatilho** da obrigação financeira, em vez
  de o financeiro nascer no registro da compra — isso é Fase 4/8, e mexe
  em `processar_compra_normal`.
- **Não criou avaliação de fornecedor.** Sem verbo nesta fase; é
  candidata natural da Fase 8 (o dado de desempenho vem do recebimento).
- **Não tornou `pedido_compra.obra_id` NOT NULL.** Isso é Fase 4 e é a
  migração mais cara do roadmap: exige classificar os registros órfãos
  antes. O que a Fase 3 fez foi garantir que todo pedido **emitido por
  requisição** já nasce com obra.
- **Não amarrou o almoxarifado a papel.** `views/almoxarifado/*.py`
  continua com `@login_required` puro em ~20 rotas. O papel `COMPRADOR`
  agora existe e é o primeiro candidato a consumi-lo — mas trancar essas
  rotas hoje tiraria acesso de campo. Decisão D5.
- **Não migrou o `MapaConcorrencia` V1** (`models.py:5512`). Ele
  continua vivo em paralelo ao V2. A requisição só se liga ao V2
  (`RequisicaoCompra.mapa_v2_id`).
- **Não mexeu em `GestaoCustoPai`,** que continua sem coluna `obra_id`
  (a obra vive em `entidade_id`, um inteiro sem FK — `models.py:5227`).
  É Fase 4.
```

- [ ] **Step 4: Rode o gate completo**

```bash
bash run_tests.sh --gate 2>&1 | tail -40
```

Esperado: nenhuma regressão contra a baseline anotada no início da fase. **Cole a linha final do gate no documento de fecho** — é o requisito de aceitação de fase registrado em `DEVOLUTIVA.md:197-198`.

Preste atenção especial a estes arquivos, que exercitam o fluxo antigo de compras e não podem regredir:

```bash
python -m pytest tests/test_compras_tipo.py tests/test_compras_nova_dropdown.py -v
python -m pytest tests/test_fase0_autorizacao.py tests/test_fase1_escopo_obra.py tests/test_fase1_identidade.py -v
```

- [ ] **Step 5: Commit**

```bash
git add tests/test_fase3_matriz_governanca.py docs/fase-3-rollout.md
git commit -m "test(fase3): matriz ator x acao + runbook de rollout

7 atores x 3 acoes numa tabela so, mais o teste de que nenhuma das 9
rotas de requisicao responde a anonimo. Runbook documenta o que ja esta
valendo sem flag (correcoes do portal) e o que exige checagem antes de
ligar."
```

---

## Encerramento da fase

- [ ] **Atualize `ESTADO-ATUAL.md`:** marque a Fase 3 como concluída na tabela de fases (linha 54); acrescente às "Armadilhas para quem retomar" que o portal por token agora expira em 180 dias e que `compras_governanca_ativa` nasce desligada, apontando para `docs/fase-3-rollout.md`.
- [ ] **Corrija `DEVOLUTIVA.md:73`,** que afirma que "não existe recebimento": o recebimento parcial existe em `compras_views.py:841-948` desde antes desta fase. Troque por "o recebimento existe mas não é o gatilho financeiro".
- [ ] **Verifique que a Fase 4 está destravada:** `RequisicaoCompra.obra_id` é NOT NULL e `PedidoCompra.requisicao_id` existe — o subconjunto de pedidos emitidos por requisição já tem obra garantida, o que reduz o universo de órfãos que a Fase 4 precisa classificar. Meça:
  ```sql
  SELECT requisicao_id IS NOT NULL AS por_requisicao,
         obra_id IS NULL AS sem_obra, COUNT(*)
  FROM pedido_compra GROUP BY 1, 2;
  ```
- [ ] **Não ligue `compras_governanca_ativa` em produção** sem os passos 1-3 do runbook revisados pelo Cássio, e sem que ele tenha confirmado ou trocado os valores de alçada (decisão D1).

---

## Autorrevisão feita sobre este plano

- **Cobertura do escopo pedido.** Modelo de requisição → Task 1. Cadeia de aprovação com alçada → Tasks 3 e 7. Transição para pedido de compra → Task 8. Vínculo obrigatório com obra (e etapa quando existir) → Task 1 (`obra_id` NOT NULL, `obra_servico_custo_id` opcional) e Task 8 (o pedido herda os dois da requisição, sem campo de formulário que permita esvaziar). Histórico de aprovação com quem/quando/valor → Task 2 (`RequisicaoTransicao.valor_no_momento`, travado por `test_valor_gravado_e_o_do_momento_da_aprovacao`). `PapelObra.COMPRADOR` + migration que estende o enum → Task 4. Achado de segurança do portal, com decisão justificada → seção própria + Tasks 10 e 11. Mapa de concorrência → investigado (`models.py:5512-5720`, `views/obras.py:2769-3300`, `portal_obras_views.py:432,546`) e reaproveitado por FK opcional, sem reparentagem.
- **Faixa de migrations respeitada:** 240, 241, 242, 243, 244, 245, 246, 247 — dentro de 240-249, sem colisão com a maior registrada hoje (213, `migrations.py:4014`) nem com as faixas da Fase 1 (214-216) e da Fase 2.
- **Onde eu não obedeci ao briefing, e por quê.** O briefing dizia que `ALMOXARIFE` "é REMOVIDO como código morto na Fase 1". Conferi: a Fase 1 (Task 10, passo 5) remove `almoxarife_required`, `pode_gerenciar_almoxarifado` e `pode_lancar_materiais` de `auth.py:70-99`, mas **não** remove o membro `ALMOXARIFE` de `TipoUsuario` (`models.py:25`) — remover valor de enum nativo do Postgres com linhas gravadas é operação de risco, e a Fase 1 não a fez. Registrei o fato como tal em vez de repetir a premissa.
- **Onde a DEVOLUTIVA estava errada.** `DEVOLUTIVA.md:73` afirma que não existe recebimento. Existe (`compras_views.py:841-948`, com botão em `templates/compras/detalhe.html:24`). Por isso a Fase 3 **não** constrói recebimento — seria refazer o que está pronto. O item ficou registrado no runbook como "não fez".
- **Risco maior identificado e endereçado:** ligar a governança travaria o registro de compra de quem está em obra. Endereçado com a flag por tenant (Task 5), o guard no `--ligar` que recusa tenant sem faixa, o `test_com_flag_desligada_o_fluxo_antigo_continua_funcionando` e o `test_com_flag_ligada_a_emissao_pela_requisicao_continua_funcionando`.
- **Segundo risco:** faixa mal configurada travando o canteiro. Endereçado com a `_FaixaSeguranca`, que falha para o lado restritivo (o certo numa alçada), e com o passo 1 do runbook, que obriga a conferir as faixas antes de ligar.
- **Consistência de nomes conferida contra todos os usos nos testes:** `recalcular_valor`, `proximo_numero`, `transicionar`, `TransicaoInvalida`, `TRANSICOES_VALIDAS` (`services/requisicao_compra.py`); `faixa_para_valor`, `pode_aprovar`, `registrar_aprovacao`, `votos_de_aprovacao`, `aprovacoes_registradas`, `esta_totalmente_aprovada`, `pendencias_de_aprovacao`, `papel_para_alcada`, `garantir_faixas_do_tenant`, `FAIXAS_RECOMENDADAS`, `MARCA_APROVACAO` (`services/alcada_compras.py`); `pode_requisitar_na_obra`, `pode_comprar_na_obra`, `PAPEIS_QUE_REQUISITAM`, `PAPEIS_QUE_COMPRAM` (`utils/autorizacao.py`); `governanca_ativa`, `definir_flag` (`scripts/flag_compras_governanca.py`); `_registrar_acesso`, `PRAZO_TOKEN_DIAS` (`portal_obras_views.py`); endpoints `compras.requisicoes`, `requisicao_nova`, `requisicao_nova_post`, `requisicao_detalhe`, `requisicao_enviar`, `requisicao_cancelar`, `requisicao_aprovar`, `requisicao_rejeitar`, `requisicao_emitir_pedido`.
- **Dependências da Fase 1 usadas e conferidas contra o plano dela:** `obras_visiveis()` devolve **query**, não lista (por isso a Task 6 faz `.with_entities(Obra.id)`); `papel_na_obra()` devolve `PapelObra` ou `None`, e devolve `GESTOR` implícito para ADMIN; `PAPEIS_QUE_EDITAM_OBRA` é `(PapelObra.GESTOR,)`; `_e_admin_do_tenant()` é privado do módulo mas é usado pelos predicados novos, que moram no mesmo arquivo.
- **Dependência da Fase 2 declarada sem assumir nomes:** a Task 2 abre com um passo de reconhecimento que decide entre reusar o helper dela ou escrever a cópia local, e diz exatamente o que trocar em cada caso.
- **Assinaturas conferidas no código, não presumidas:** `processar_compra_normal(pedido, itens_validos, admin_id, usuario_id)` e o formato de `itens_validos` como tupla `(desc, qtd, preco, almox_id, subtotal)` (`compras_views.py:162,187,257`); `_check_v2()` devolve um redirect ou `None` (`compras_views.py:36-40`); `ConfiguracaoEmpresa.nome_empresa` é NOT NULL (`models.py:3596`), por isso o `definir_flag` cria a linha com um nome provisório; `Obra.cliente_id` é NOT NULL (`models.py:265`), por isso toda fixture cria `Cliente` antes; `Fornecedor.cnpj` é NOT NULL (`models.py:1684`), por isso as fixtures preenchem; `MapaConcorrenciaV2.fornecedores` é lista (não `lazy='dynamic'`), por isso `len(...)` funciona em `_mapa_serve_de_concorrencia` (`models.py:5612`).
- **O que não tem teste e eu sei disso:** os três templates novos não têm teste de renderização própria — eles são exercitados de lado pelos testes de rota (`test_listagem_abre_para_admin`, `test_detalhe_de_requisicao_de_outro_tenant_devolve_404`), o que pega `BuildError` e erro de sintaxe Jinja, mas não pega regressão visual. O repositório não tem cultura de teste de template fora do Playwright, e não vou inventar uma nesta fase.
