# Fase 9 — Portal do cliente: endurecimento + assinatura de medição (9a) e Contratos/Drive/Notificações (9b)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar o portal do cliente — hoje um sistema de identidade paralelo onde a URL *é* a credencial, sem expiração, sem escopo e sem trilha — num canal com capability tokens escopados, expiráveis, revogáveis e auditados; e, só então, entregar a assinatura de medição pelo cliente com valor probatório defensável (autoria, carimbo de tempo, IP/dispositivo e hash do documento exato assinado).

**Architecture:** Duas partes num documento só, com pesos deliberadamente diferentes. **9a** substitui `Obra.token_cliente` / `Proposta.token_cliente` (strings em claro, eternas, onipotentes) por uma tabela `portal_acesso` de tokens **hasheados**, com escopo por ação, validade, revogação e uso único; toda rota de portal passa a atravessar um único decorator `portal_token_required(escopo)`; toda passagem — negada ou concedida — vira linha em `portal_evento`. Sobre essa base entra `Assinatura`, uma tabela genérica de assinatura eletrônica simples (snapshot canônico + SHA-256 + timestamp + IP + user-agent + declaração de aceite), compartilhada com o RDO da Fase 5. **9b** fica em nível de arquitetura e responsabilidades: `Contrato`/`ContratoAditivo`, integração com Google Drive por conta de serviço, e notificações — que **não serão construídas do zero**, porque a fundação de evento/webhook/n8n já existe e está documentada.

**Tech Stack:** Flask 3 + Flask-Login + Flask-WTF (CSRF) + Flask-Limiter, SQLAlchemy 2 (`models.py`), sistema de migrações próprio numerado (`migrations.py`, `run_migration_safe`), pytest (`run_tests.sh --gate`), PostgreSQL, reportlab (PDF), n8n + Evolution API (canal externo de notificação, já existente).

**Faixa de migrações reservada:** **300–309**.

---

## Contexto verificado no código (leia antes de começar)

Tudo abaixo foi conferido em 2026-07-21 no commit `fb4147b`, arquivo por arquivo. Não são suposições nem cópias do `ESTADO-ATUAL.md`.

### O portal hoje

| Fato | Evidência |
|---|---|
| Blueprint `portal_obras`, prefixo `/portal`, declarado "Acesso público via token — sem login necessário" | `portal_obras_views.py:31-33`, docstring `portal_obras_views.py:1-6` |
| A identidade é a string da URL. Dois helpers, ambos com uma única query | `_get_obra_by_token` em `portal_obras_views.py:49-55`; `_resolve_obra_for_view` em `portal_obras_views.py:58-76` |
| `_get_obra_by_token` é literalmente `Obra.query.filter_by(token_cliente=token, portal_ativo=True).first()` + `abort(404)`. **Não há mais nada** — sem expiração, sem escopo, sem contador, sem IP, sem revogação | `portal_obras_views.py:52-55` |
| `Obra.token_cliente` é `String(255) unique`, **em claro no banco**, sem coluna de validade, de revogação ou de emissão | `models.py:261` |
| `Proposta.token_cliente` é `String(100) unique`, gerado no `__init__` do modelo, também sem validade | `models.py:2986`, `models.py:3059-3060` |
| O token nasce em **quatro** lugares independentes, todos `secrets.token_urlsafe(32)`, nenhum registrando quem emitiu | `views/obras.py:375` (criar obra), `views/obras.py:949` (editar obra), `event_manager.py:1053` (aprovação de proposta), `portal_obras_views.py:481` (toggle do portal) |
| `Obra.portal_ativo` (`models.py:272`) é o **único** liga/desliga, e é por obra — não por destinatário. Desativar o portal derruba todo mundo que tem o link | `models.py:272`, consumido em `portal_obras_views.py:52` e `:66` |
| `Obra.ultima_visualizacao_cliente` (`models.py:273`) é o único rastro de acesso que existe, e é **sobrescrito** a cada visita: guarda um `datetime` e nada mais — nem IP, nem quantas visitas, nem qual link | `models.py:273`, escrita em `portal_obras_views.py:85-89` |

### As rotas que mutam estado com nada além da URL

Sete rotas POST. Nenhuma tem `@login_required`, nenhuma tem CSRF, nenhuma tem rate-limit, nenhuma verifica escopo:

| # | Rota | Método | Linha (decorator / função) | O que muda no banco |
|---|---|---|---|---|
| 1 | `/portal/obra/<token>/compra/<id>/aprovar` | POST | `portal_obras_views.py:343` / `:344` | `PedidoCompra.status_aprovacao_cliente='APROVADO'` **e chama `processar_compra_aprovada_cliente`** (`:359-361`), que gera custos, entrada e saída de almoxarifado |
| 2 | `/portal/obra/<token>/compra/<id>/recusar` | POST | `portal_obras_views.py:377` / `:378` | `status_aprovacao_cliente='RECUSADO'` (`:381`) |
| 3 | `/portal/obra/<token>/compra/<id>/comprovante` | POST | `portal_obras_views.py:388` / `:389` | Grava arquivo em disco (`:418`) e escreve `comprovante_pagamento_url` (`:422`/`:425`) |
| 4 | `/portal/obra/<token>/mapa/<id>/aprovar` | POST | `portal_obras_views.py:432` / `:433` | Escolhe fornecedor e fecha o mapa: `opcao.selecionada=True`, `mapa.status='concluido'` (`:457-458`) |
| 5 | `/portal/obra/<token>/mapa-v2/<id>/selecionar` | POST | `portal_obras_views.py:546` / `:547` | Escreve `MapaCotacao.selecionado` e `MapaItemCotacao.fornecedor_escolhido_id` de N itens e fecha o mapa (`:592-603`) |
| 6 | `/propostas/cliente/<token>/aprovar` | POST | `propostas_consolidated.py:2503` / `:2504` | Emite `proposta_aprovada` com `raise_on_error=True` (`:2535`), que **cria a Obra**, itens de medição comercial e cronograma |
| 7 | `/propostas/cliente/<token>/rejeitar` | POST | `propostas_consolidated.py:2587` / `:2588` | `proposta.status='rejeitada'` (`:2592`) |

Rotas GET no mesmo regime: `portal_obras_views.py:79` (`portal_obra`), `:618` (`baixar_relatorio_mapa_v2_portal`), `:638` (`portal_rdo_detalhe`), `propostas_consolidated.py:2453` (`portal_cliente`), e `medicao_views.py:512` (`portal_pdf_extrato`).

### Achados que ampliam o buraco

| Fato | Evidência |
|---|---|
| **CSRF está explicitamente desligado nas 7 rotas.** `main.py` importa cada view do portal e chama `csrf.exempt` uma a uma; o blueprint `propostas` inteiro está na lista de isenção do `app.py` | `main.py:222-230` (portal de obra), `main.py:234-236` (`portal_pdf_extrato`), `app.py:1035-1049` (lista contém `'propostas'`) |
| **Rate-limit existe no app e não é usado no portal.** O `Limiter` está instanciado com `default_limits=[]` e há exatamente **um** `@limiter.limit` em todo o código: o `/login` | `app.py:234-239`; `views/auth.py:14` — única ocorrência de `@limiter` fora de `archive/` |
| **O token vai para o log a cada escrita.** `utils/auditoria_acesso.py` registra `path=` de todo POST/PUT/PATCH/DELETE, e `/portal/obra/<token>/...` carrega o token no path. A lista `_PATHS_SENSIVEIS` cobre `/login`, `/alterar-senha` e `/usuarios` — **não cobre `/portal`** | `utils/auditoria_acesso.py:29`, `:66-73`; instalado em `app.py:99` |
| Pior: como o portal é anônimo, cada aprovação de compra do cliente sai como `logger.warning('[ESCRITA-ANONIMA] ... path=/portal/obra/<token-em-claro>/compra/12/aprovar')` | `utils/auditoria_acesso.py:77-79` |
| **O access log do gunicorn também grava.** O `CMD` do Dockerfile passa `--access-logfile -`, o que manda a request line inteira (path **e querystring**) para stdout. O PDF de medição usa `?token=…` | `Dockerfile:97-99`; `medicao_views.py:514` |
| **O PDF de medição lê o token da querystring** — o pior lugar possível: entra em histórico de navegador, em `Referer` e no access log | `medicao_views.py:512-521` (`request.args.get('token', '')`, depois `Obra.query.filter_by(token_cliente=token, portal_ativo=True)`) |
| **`admin_id = 10` chumbado continua lá.** No portal da proposta, quando o tenant não resolve, o código assume o tenant 10 e renderiza a proposta com a identidade visual e a configuração de *outra empresa* | `propostas_consolidated.py:2469` (confirmado hoje; há um irmão em `propostas_consolidated.py:421`, `return 10`) |
| A página do portal carrega CSS/JS de `cdn.jsdelivr.net` e `cdnjs.cloudflare.com`, e **não existe nenhum header `Referrer-Policy` no app inteiro** (zero ocorrências de `Referrer-Policy`, `Content-Security-Policy` ou `Talisman` no código) | `templates/portal/_base.html:7,8,448`; grep sem resultado em todo o repo |
| Aprovação de compra pelo portal é atribuída ao **admin do tenant**, com comentário assumindo o problema: `# usuario_id = admin do tenant (portal é anônimo, não tem current_user)` | `portal_obras_views.py:360-361` |
| O censo de rotas classificou essas 7 POSTs como **`TOKEN (legítimo)` — "autenticação POR TOKEN, é o desenho correto"**, e é por isso que o `ESTADO-ATUAL.md` afirma "Rotas de **escrita** sem auth: **1** — e é `/login`" | `docs/anexos/A-rotas-sem-autenticacao.md:16` (a classificação), `:78-82`, `:86-87` (as 7 rotas); `ESTADO-ATUAL.md:111` (o número). **Este é o diagnóstico desatualizado**: o número certo de rotas de escrita autenticadas apenas por um bearer token eterno, sem escopo e sem trilha, é **8**, não 1 |

### O objeto que vai ser assinado

| Fato | Evidência |
|---|---|
| `MedicaoObra` — `numero`, `periodo_inicio/fim`, `percentual_executado`, `valor_medido`, `valor_total_medido_periodo`, `valor_entrada_abatido_periodo`, `valor_a_faturar_periodo`, `status`, `conta_receber_id`. **Não tem nenhum campo de assinatura** | `models.py:5482-5509` |
| `MedicaoObraItem` — a linha a linha da medição (percentuais anterior/atual/período, valores) | `models.py:5548-5566` |
| `MedicaoContrato` (migration 197) é **outra coisa**: cronograma de faturamento fixo, `valor` derivado de `pct × obra.valor_contrato`. Não é o documento assinável | `models.py:5568-5592`; `migrations.py:3998` e `migrations.py:13605` |
| O ciclo de vida é `PENDENTE → APROVADO → FATURADO`. `fechar_medicao` só troca o status e emite `obra.medicao_publicada` | `services/medicao_service.py:180-204`; `medicao_views.py:479-492` |
| O PDF do extrato é gerado por reportlab a cada request, a partir do estado **vivo** do banco — não há snapshot | `services/medicao_service.py:389-402` |
| O portal renderiza medições com link direto de PDF montado com `obra.token_cliente` no template | `templates/portal/_portal_medicoes.html:29` |
| `templates/portal/_partials/_medicoes.html` e `_rdos.html` são **cópias mortas** — `portal_obra.html:6-19` inclui apenas os `portal/_portal_*.html` | `templates/portal/portal_obra.html:13,15` vs. `templates/portal/_partials/` |

### Infra que já existe e que esta fase reaproveita

| Ativo | Onde | Estado |
|---|---|---|
| `EventManager` com `register`/`emit`/`raise_on_error` | `event_manager.py:13-71` | Vivo, usado em produção |
| Despachante de webhook para n8n com HMAC-SHA256, allowlist explícita, fila `WebhookEntrega`, retry 1m/5m/15m, thread daemon | `utils/webhook_dispatcher.py` (556 linhas), allowlist em `:61-72`, backoff em `:81-84` | **Pronto**. No-op silencioso sem `N8N_WEBHOOK_URL` |
| `WebhookEntrega` (fila/auditoria de entrega) | `models.py:6900-6923` | Pronta |
| Painel `/admin/webhooks` com filtro por tenant e botão reenviar | `views/admin.py:263`, `:317` | Pronto |
| 8 helpers `emit_*` no catálogo `dominio.acao` | `utils/catalogo_eventos.py:137,149,162,242,261,276,289` | Pronto |
| 8 workflows n8n de exemplo (e-mail SMTP + WhatsApp via Evolution API) | `n8n_workflows/*.json` | Prontos |
| Documentação completa do canal (payloads, HMAC, cron, como adicionar o 8º evento) | `docs/notificacoes/README.md` | Pronta |
| Job diário idempotente `flask emitir-propostas-expirando` | `notificacoes_cli.py` | Pronto |
| Trilha de auditoria em banco — a **forma** a copiar | `models.py:5178-5203` (`CronogramaImportacaoEvento`: evento, detalhes JSON, usuario_id, criado_em) |
| Trilha de acesso em log (não em banco, por decisão registrada) | `utils/auditoria_acesso.py:14-18` |
| Precedente de flag de rollout por tenant | `models.py:3620` (`cronograma_mpp_ativo`), `migrations.py` migration 211 |

### O que **não** existe (verificado por grep, zero ocorrências)

- `class Contrato`, `class Aditivo`, `class Locacao` em `models.py` — **nada**.
- Qualquer import de `googleapiclient`, `google.oauth2`, `google_auth` ou `drive_service` em todo o repositório — **nada**. `Lead.pasta` (`models.py:6760`) é `String(500)` digitado à mão.
- Qualquer coluna, tabela ou serviço de assinatura eletrônica — **nada**.
- Qualquer teste tocando `portal_obras_views.py` — **nenhum arquivo em `tests/` exercita o blueprint `portal_obras`**.
- `utils/notifications.py` **não é** um sistema de notificação: são 200 linhas de alerta de estouro de orçamento por serviço (`NotificacaoOrcamento`), com `servico_estourou`, `verificar_estouros_obra`, `listar_notificacoes_ativas`, `marcar_resolvida`. Nome enganoso; não confundir.

---

## Os oito achados de segurança, sem suavizar

| ID | Achado | Evidência |
|---|---|---|
| **S1** | **Sete rotas POST mutam estado autenticadas apenas pela URL.** Quem tiver o link aprova compra (que gera custo e movimenta almoxarifado), recusa compra, sobe arquivo no servidor, escolhe fornecedor, fecha mapa de concorrência, aprova proposta (criando Obra) e rejeita proposta | `portal_obras_views.py:343,377,388,432,546`; `propostas_consolidated.py:2503,2587` |
| **S2** | **O token não expira. Nunca.** Não há coluna de validade em `Obra.token_cliente` nem em `Proposta.token_cliente`. Um link mandado por WhatsApp em 2024 continua aprovando compra hoje | `models.py:261`, `models.py:2986` |
| **S3** | **Não há rotação nem revogação por destinatário.** O único controle é `Obra.portal_ativo` (booleano por obra): ou todo mundo entra, ou ninguém | `models.py:272`; `portal_obras_views.py:471-487` |
| **S4** | **Não há escopo.** Um token dá acesso a tudo: ler cronograma, ler RDO, ler medição, aprovar compra, fechar mapa. Não existe "link só de leitura" | `_get_obra_by_token` (`portal_obras_views.py:49-55`) é a autorização inteira |
| **S5** | **Não há trilha.** Nenhuma das 7 rotas grava quem, quando, de onde. `ultima_visualizacao_cliente` é sobrescrito e só existe para GET | `models.py:273`; `portal_obras_views.py:85-89` |
| **S6** | **Não há rate-limit e o CSRF foi desligado de propósito.** `main.py` isenta as 7 rotas uma a uma; o `Limiter` só protege `/login` | `main.py:222-230`, `app.py:1035-1049`, `views/auth.py:14` |
| **S7** | **O token vaza para os logs em toda mutação.** `utils/auditoria_acesso.py` grava `path` (que contém o token) e o gunicorn grava a request line com querystring. O PDF de medição põe o token na querystring | `utils/auditoria_acesso.py:29,66-79`; `Dockerfile:97-99`; `medicao_views.py:514` |
| **S8** | **`admin_id = 10` chumbado no portal da proposta.** Falha de tenant que serve a configuração e o branding da empresa 10 a um cliente de outra empresa | `propostas_consolidated.py:2469` |

**Consequência para a assinatura:** assinar uma medição num portal onde qualquer portador da URL aprova compras não produz prova de nada — o mesmo canal que "prova" a autoria já demonstrou não distinguir o cliente de quem encaminhou o WhatsApp dele. Por isso as Tasks 1–8 (endurecimento) são **pré-requisito bloqueante** das Tasks 9–14 (assinatura), e não uma melhoria paralela.

---

## Decisões que precisam do Cássio

Todas já vêm com uma recomendação adotada — o plano **não fica bloqueado** por nenhuma delas. Se a resposta divergir, o ajuste está indicado em cada linha.

### D1 — Valor jurídico da assinatura (responde a DEVOLUTIVA §7.6)

**Recomendado: assinatura eletrônica simples com registro de autoria, sem ICP-Brasil e sem provedor externo.**

Escopo mínimo defensável, implementado nas Tasks 9–13:

1. **Identificação prévia do signatário** — o token de assinatura é nominal (emitido para um nome + e-mail conferidos contra o cadastro `Cliente`, `models.py:2703-2711`), de **uso único** e com validade de 7 dias. Não é o mesmo token de leitura.
2. **Aceite explícito, não um clique** — o cliente digita o nome completo e o CPF/CNPJ, marca a declaração, e o texto exato da declaração exibida é gravado junto com a assinatura.
3. **Hash SHA-256 do documento exato** — de um snapshot canônico JSON da medição (cabeçalho + todos os itens), não do PDF. **Motivo técnico:** o PDF do reportlab não é byte-determinístico (metadados de criação mudam a cada geração, `services/medicao_service.py:389-405`); hashear o PDF produziria hashes diferentes para o mesmo conteúdo. O snapshot fica **persistido** junto com o hash, para que a prova não dependa de regenerar nada.
4. **Carimbo de tempo do servidor em UTC + IP + user-agent + id do acesso** usado.
5. **Trilha append-only** em `portal_evento` e `assinatura`, sem rota de edição nem de exclusão.
6. **Comprovante** entregue ao cliente e ao tenant, exibindo o hash, a data/hora, o IP e a declaração.

**Por que não ICP-Brasil:** exige que o cliente possua e-CPF/e-CNPJ. O cliente típico de uma obra residencial em LSF não tem. Adotar isso não endurece o processo — ele simplesmente deixa de acontecer.

**Por que não Clicksign/D4Sign agora:** custo por documento, dependência externa e dado contratual saindo para terceiro. E a camada que um provedor consome — snapshot canônico + hash + identificação do signatário — é exatamente o que as Tasks 10 e 11 constroem. Plugar um provedor depois é acrescentar um adaptador, não refazer.

**Base legal que sustenta o desenho:** Lei 14.063/2020 art. 4º, I (assinatura eletrônica simples) e MP 2.200-2/2001 art. 10 §2º (documento eletrônico não-ICP vale entre as partes **quando as partes o admitem como válido**). Daí a Task 13.5: a cláusula de aceite do portal precisa estar no contrato/proposta. **Isso é conteúdo jurídico, não código — confirmar com o advogado do Cássio.**

**Se a resposta for "quero oponibilidade contra terceiros":** aí entra provedor externo ou ICP-Brasil, e a Task 11 troca a gravação local por uma chamada ao provedor, mantendo Tasks 1–10 e 12–14 intactas.

### D2 — Validade do token de leitura

**Recomendado: 90 dias, renovável, com rotação a cada renovação.** Parametrizável por tenant em `configuracao_empresa.portal_token_dias_validade` (migration 304), default 90. Os tokens legados (Task 4) ganham **90 dias contados da data da migração** — quem tem link ativo continua entrando por três meses e recebe um link novo depois.

**Se a resposta for "não quero que expire":** setar 0 no tenant desliga a expiração (`expira_em = NULL`). Fica registrado como escolha, não como omissão.

### D3 — Um token por obra ou um por destinatário?

**Recomendado: por destinatário.** `portal_acesso` guarda `destinatario_nome` e `destinatario_email`; uma obra pode ter N acessos. Isso é o que torna possível (a) revogar o link do sócio que saiu sem derrubar o do cliente, (b) saber **quem** assinou quando há dois nomes no contrato, e (c) contar acesso por pessoa.

O backfill (Task 4) cria **um** acesso por obra, com `destinatario_email` copiado de `Cliente.email` quando existir e `destinatario_nome = '(legado)'` quando não — sem inventar dado.

### D4 — Portal continua por token ou vira login de cliente? (responde a DEVOLUTIVA §7.5)

**Recomendado: continua por token — e a Fase 9a não constrói login de cliente.** O que faltava não era senha, era **escopo, validade e trilha**, e isso as Tasks 1–8 entregam. Construir cadastro, recuperação de senha e reset para cliente final é um módulo inteiro com custo de suporte permanente, para um usuário que entra três vezes por obra.

O reforço para as ações graves não é senha, é **separação de capacidade**: assinar exige um token **distinto**, de uso único, escopo `ASSINAR_MEDICAO` e validade de 7 dias, emitido pelo tenant quando há medição a assinar. Nenhum token de leitura — nem os legados — ganha poder de assinatura em momento algum.

**Se a resposta for "quero login":** o modelo `portal_acesso` já é a tabela de credencial; acrescentar `senha_hash` e uma tela de login é aditivo, não reescrita.

### D5 — Escopos herdados pelos tokens legados

**Recomendado: `LER`, `APROVAR_COMPRA`, `ENVIAR_COMPROVANTE`, `SELECIONAR_MAPA`** — exatamente o que eles já podem fazer hoje, nada a mais. **Nunca `ASSINAR_MEDICAO`.** Manter o poder atual evita quebrar clientes no deploy; negar a assinatura garante que nenhuma assinatura nasça de um link de origem desconhecida.

### D6 — Google Drive: conta de serviço ou OAuth por usuário? (responde a DEVOLUTIVA §7.9)

**Recomendado: conta de serviço + Drive compartilhado (Shared Drive), escopo `drive.file`, chave JSON em variável de ambiente.** Ver Task 19 e a seção "Premissas a reconfirmar".

### D7 — Contrato como entidade nova?

**Recomendado: sim.** `Contrato` + `ContratoAditivo`, com `Obra.valor_contrato` (`models.py:254`) passando a ser **espelho** do contrato vigente, mantido por listener e com a edição livre bloqueada. Depende da Fase 6 (aditivo) — ver Task 18.

### D8 — Notificações: construir ou usar o que existe?

**Recomendado: não construir motor de envio.** A infra existe e está documentada (`utils/webhook_dispatcher.py`, `utils/catalogo_eventos.py`, `docs/notificacoes/README.md`, 8 workflows em `n8n_workflows/`). A Fase 9b acrescenta **eventos** à allowlist e **helpers** ao catálogo. Ver Task 20.

---

## Dependências de fases anteriores

| Fase | O que esta fase consome | Como consome | Se não estiver pronta |
|---|---|---|---|
| **Fase 1** | `utils/autorizacao.py`, `utils/identidade.py`, `UsuarioObra`, `PapelObra` | Emissão e revogação de acesso de portal exigem papel na obra: só `PapelObra.GESTOR` (ou `ADMIN`/`SUPER_ADMIN` do tenant) emite token. A Fase 1 **declarou explicitamente que não tocou nos portais por token e registrou isso como dívida candidata a esta fase** — esta é a fase que paga | Task 5 usa `@admin_required` de `auth.py` como piso e o teste de papel fica marcado `xfail` até a Fase 1 entrar |
| **Fase 2** | Estados da Obra | Emitir token de assinatura de medição exige obra em estado de execução; obra encerrada não recebe token novo | Task 11 checa `Obra.status` textual como fallback e deixa `TODO-FASE-2` no ponto exato |
| **Fase 5** | **Padrão de assinatura (RDO com ciclo de vida e assinatura)** | **Esta fase NÃO inventa assinatura própria.** A tabela `assinatura` da Task 9 é a mesma que o RDO usa, com `documento_tipo ∈ {'rdo','medicao_obra','contrato'}` | Ver o parágrafo abaixo |
| **Fase 6** | Orçamento versionado e aditivo | `ContratoAditivo` (Task 18) reusa a cadeia de versão/aditivo da Fase 6 em vez de criar outra | Task 18 fica bloqueada; é a última do plano |

**Sobre a Fase 5, explicitamente:** hoje **não existe nenhuma assinatura no código** (zero ocorrências de tabela, coluna ou serviço). O `DEVOLUTIVA.md:104` propõe `RDOAssinatura (papel, hash, timestamp, IP)`. Se a Fase 5 for executada antes desta e criar `RDOAssinatura` **específica do RDO**, a Task 9 **não cria uma segunda tabela**: ela generaliza a existente (renomeia para `assinatura`, acrescenta `documento_tipo`/`documento_id`/`snapshot`/`declaracao` e faz backfill com `documento_tipo='rdo'`), e a migration 303 muda de `CREATE TABLE` para `ALTER TABLE` + `UPDATE`. Isso está escrito como passo condicional dentro da Task 9. Se a Fase 9a rodar **antes** da Fase 5, a Task 9 cria a tabela genérica e a Fase 5 passa a consumi-la — o que é o resultado preferível.

---

## Arquivos que esta fase cria ou altera

### Parte 9a

| Arquivo | Responsabilidade |
|---|---|
| `models.py` | enums `EscopoPortal`, modelos `PortalAcesso`, `PortalEvento`, `Assinatura`; coluna `ConfiguracaoEmpresa.portal_token_dias_validade` |
| `migrations.py` | migrations **300** (`portal_acesso`), **301** (`portal_evento`), **302** (backfill dos tokens legados), **303** (`assinatura`), **304** (flags em `configuracao_empresa`), **305** (zera os tokens em claro) + registro em `migrations_to_run` — ver o mapa de ordem no fim do documento |
| `utils/portal_acesso.py` | **novo** — único resolver de token do sistema: `emitir_acesso`, `resolver_acesso`, `revogar_acesso`, `tem_escopo`, decorator `portal_token_required`, `registrar_evento`. Falha fechada |
| `services/assinatura_documento.py` | **novo** — `snapshot_medicao(medicao)`, `hash_canonico(dict)`, `assinar_documento(...)`, `assinatura_de(documento_tipo, documento_id, papel)` |
| `portal_obras_views.py` | as 8 rotas passam pelo decorator; `_get_obra_by_token`/`_resolve_obra_for_view` viram casca fina sobre o resolver; nova rota de assinatura; `token` passa a ir no contexto do template |
| `propostas_consolidated.py` | 3 rotas do portal da proposta pelo decorator; **remoção do `admin_id = 10` da linha 2469** |
| `medicao_views.py` | `portal_pdf_extrato` (`:512`) passa a receber o token no **path** e a exigir escopo `LER` |
| `main.py` | mantém o `csrf.exempt` (o token no path já é o anti-CSRF do canal), mas registra as novas rotas e acrescenta `Referrer-Policy: no-referrer` nas respostas do portal |
| `utils/auditoria_acesso.py` | redação do token no `path` antes de logar (`_PATHS_SENSIVEIS` + máscara) |
| `views/obras.py` | `:375` e `:949` param de gerar `token_cliente`; emissão passa por `utils/portal_acesso.emitir_acesso` |
| `event_manager.py` | `:1053` idem |
| `templates/portal/_portal_medicoes.html`, `_portal_mapas_v2.html`, `_portal_rdos.html` | trocam `obra.token_cliente` pela variável `token` do contexto |
| `templates/portal/portal_assinatura_medicao.html` | **novo** — tela de assinatura |
| `templates/portal/portal_comprovante_assinatura.html` | **novo** — comprovante com hash |
| `templates/obras/detalhes_obra_profissional.html` | painel de links do portal: lista acessos ativos (prefixo, escopo, validade), botões emitir/revogar |
| `templates/compras/aprovacao.html`, `templates/propostas/*.html` | param de renderizar o token em claro |
| `scripts/portal_acessos.py` | **novo** — CLI: listar, emitir, revogar, relatório de expiração |
| `tests/test_fase9_portal_acesso.py` | **novo** — escopo, expiração, revogação, uso único, hash, enumeração |
| `tests/test_fase9_portal_rotas.py` | **novo** — matriz rota × escopo × estado do token, para as 11 rotas |
| `tests/test_fase9_assinatura_medicao.py` | **novo** — snapshot canônico, hash estável, imutabilidade, comprovante |

### Parte 9b

| Arquivo | Responsabilidade |
|---|---|
| `models.py` | `Contrato`, `ContratoAditivo`, `DriveVinculo` |
| `migrations.py` | migrations **306** (contrato + aditivo), **307** (`drive_vinculo`); **308–309 reservadas** |
| `services/contrato_service.py` | **novo** — valor vigente, aplicação de aditivo, extrato de contrato |
| `services/drive_client.py` | **novo** — cliente fino da API do Drive (criar pasta, subir arquivo, dar permissão), isolado e mockável |
| `services/drive_estrutura.py` | **novo** — árvore de pastas padrão por obra, idempotente |
| `utils/catalogo_eventos.py` | novos helpers `emit_*` (medição assinada, contrato a vencer, aditivo registrado) |
| `utils/webhook_dispatcher.py` | novos nomes na `WEBHOOK_EVENT_ALLOWLIST` (`:61-72`) |
| `n8n_workflows/` | novos JSONs de exemplo |
| `docs/notificacoes/README.md` | novas linhas na tabela da §10 e blocos de payload na §10.1 |
| `contratos_views.py` | **novo** — blueprint de contratos/aditivos/alertas |

---

# PARTE 9a — Endurecimento do portal e assinatura de medição

> Tasks 1 a 8 são o endurecimento. Tasks 9 a 14 são a assinatura. **Não comece a Task 9 sem as Tasks 1–8 verdes** — a Task 14 tem um teste que falha de propósito se a ordem for invertida.

## Task 1: Modelo `PortalAcesso` (token hasheado, escopado, expirável)

**Files:**
- Modify: `models.py` (enum novo antes de `class Obra`, ~linha 240; modelo após `class Obra`)
- Modify: `migrations.py` (migration 300 + registro após a linha 4013)
- Test: `tests/test_fase9_portal_acesso.py`

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_fase9_portal_acesso.py`:

```python
"""Fase 9a — capability tokens do portal do cliente.

Até 2026-07-21 a autorização inteira do portal era uma linha:

    Obra.query.filter_by(token_cliente=token, portal_ativo=True).first()
    (portal_obras_views.py:52)

O token era String(255) em claro no banco (models.py:261), sem validade,
sem escopo, sem revogação individual e sem trilha. Sete rotas POST que
mutam estado dependiam só dele. Estes testes travam a tabela que
substitui isso.
"""
import os
import sys
import uuid
from datetime import date, datetime, timedelta

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import Cliente, EscopoPortal, Obra, PortalAcesso, TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase9-portal'
    yield


def _admin():
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'f9a_{suf}', email=f'f9a_{suf}@test.local',
        nome=f'Admin {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id, portal_ativo=True):
    suf = uuid.uuid4().hex[:8]
    cliente = Cliente(nome=f'Cliente {suf}', email=f'cli_{suf}@test.local',
                      admin_id=admin_id)
    db.session.add(cliente)
    db.session.commit()
    o = Obra(
        nome=f'Obra {suf}', codigo=f'O{suf[:6].upper()}',
        data_inicio=date(2026, 1, 1), admin_id=admin_id,
        cliente_id=cliente.id, ativo=True, portal_ativo=portal_ativo,
    )
    db.session.add(o)
    db.session.commit()
    return o


def test_escopo_portal_tem_os_seis_valores_da_fase_9():
    assert {e.name for e in EscopoPortal} == {
        'LER', 'APROVAR_COMPRA', 'ENVIAR_COMPROVANTE',
        'SELECIONAR_MAPA', 'APROVAR_PROPOSTA', 'ASSINAR_MEDICAO',
    }


def test_portal_acesso_persiste_com_hash_e_nunca_o_token():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        acesso = PortalAcesso(
            obra_id=obra.id, admin_id=admin.id,
            token_hash='a' * 64, token_prefixo='abcd1234',
            escopos='ler', destinatario_nome='Fulano',
            destinatario_email='fulano@test.local',
            expira_em=datetime.utcnow() + timedelta(days=90),
        )
        db.session.add(acesso)
        db.session.commit()
        aid = acesso.id

    with app.app_context():
        recarregado = db.session.get(PortalAcesso, aid)
        assert recarregado.token_hash == 'a' * 64
        assert recarregado.revogado_em is None
        assert recarregado.usos == 0
        assert recarregado.uso_unico is False
        # A prova de que o token em claro NÃO tem onde morar nesta tabela:
        assert not hasattr(recarregado, 'token')
        assert not hasattr(recarregado, 'token_cliente')


def test_dois_acessos_nao_compartilham_o_mesmo_hash():
    from sqlalchemy.exc import IntegrityError

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        h = uuid.uuid4().hex + uuid.uuid4().hex  # 64 chars
        for i in range(2):
            db.session.add(PortalAcesso(
                obra_id=obra.id, admin_id=admin.id,
                token_hash=h, token_prefixo=f'pre{i}',
                escopos='ler',
            ))
            if i == 0:
                db.session.commit()
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_acesso_exige_exatamente_um_alvo():
    """obra XOR proposta — nem os dois, nem nenhum."""
    from sqlalchemy.exc import IntegrityError

    with app.app_context():
        admin = _admin()
        db.session.add(PortalAcesso(
            obra_id=None, proposta_id=None, admin_id=admin.id,
            token_hash=uuid.uuid4().hex * 2, token_prefixo='orfao',
            escopos='ler',
        ))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_uma_obra_pode_ter_varios_acessos():
    """Um link por destinatário — revogar o do sócio não derruba o do cliente."""
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        for nome in ('Cliente', 'Socio', 'Engenheiro'):
            db.session.add(PortalAcesso(
                obra_id=obra.id, admin_id=admin.id,
                token_hash=uuid.uuid4().hex * 2,
                token_prefixo=nome[:8], escopos='ler',
                destinatario_nome=nome,
            ))
        db.session.commit()
        assert PortalAcesso.query.filter_by(obra_id=obra.id).count() == 3
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase9_portal_acesso.py -v
```

Esperado: FAIL na coleção — `ImportError: cannot import name 'EscopoPortal' from 'models'`.

- [ ] **Step 3: Adicione o enum e o modelo em `models.py`**

Imediatamente antes de `class Obra` (a classe cujo `__table_args__` está em `models.py:245`), insira:

```python
class EscopoPortal(Enum):
    """O que um capability token do portal pode fazer — Fase 9a.

    Até esta fase não existia escopo nenhum: `_get_obra_by_token`
    (portal_obras_views.py:49-55) era a autorização inteira, e quem
    tivesse a URL podia ler o cronograma, ler o RDO, aprovar compra (o
    que dispara `processar_compra_aprovada_cliente` e gera custo,
    entrada e saída de almoxarifado — portal_obras_views.py:359-361),
    recusar compra, subir arquivo no servidor e fechar mapa de
    concorrência. Um link só de leitura era impossível de emitir.

    ASSINAR_MEDICAO é deliberadamente separado e NUNCA é concedido a
    token de leitura nem ao backfill dos tokens legados (migration 302):
    assinatura exige token nominal, de uso único, emitido para aquele
    documento. Ver D1/D4/D5 no plano da Fase 9.
    """
    LER = "ler"                              # portal, RDO, PDF de medição, relatório de mapa
    APROVAR_COMPRA = "aprovar_compra"        # aprovar e recusar compra
    ENVIAR_COMPROVANTE = "enviar_comprovante"
    SELECIONAR_MAPA = "selecionar_mapa"      # mapa V1 e V2
    APROVAR_PROPOSTA = "aprovar_proposta"    # aprovar e rejeitar proposta
    ASSINAR_MEDICAO = "assinar_medicao"
```

Imediatamente após o fim da `class Obra` (antes da próxima classe), insira:

```python
class PortalAcesso(db.Model):
    """Capability token do portal do cliente — Fase 9a.

    Substitui `Obra.token_cliente` (models.py:261) e
    `Proposta.token_cliente` (models.py:2986), que eram strings em
    claro, sem validade, sem escopo, sem revogação individual e sem
    trilha, geradas em quatro lugares diferentes (views/obras.py:375 e
    :949, event_manager.py:1053, portal_obras_views.py:481).

    O token NÃO é guardado. O que fica é o SHA-256 hexdigest e um
    prefixo curto, suficiente para a tela do tenant dizer "link •••ab12
    ativo, expira em 62 dias" sem revelar a credencial. O token em claro
    existe uma única vez: no retorno de `utils.portal_acesso.emitir_acesso`.
    Consequência aceita: para reenviar um link, o tenant reemite — não
    há como "ver de novo". Isso é o comportamento correto e é o que
    torna a rotação real.

    ALVO: exatamente um de obra_id / proposta_id (CHECK no banco). A
    proposta e a obra têm ciclos de vida diferentes (a proposta pode
    virar obra), mas a credencial é a mesma coisa e merece uma tabela só.
    """
    __tablename__ = 'portal_acesso'
    __table_args__ = (
        db.CheckConstraint(
            '(obra_id IS NOT NULL AND proposta_id IS NULL) OR '
            '(obra_id IS NULL AND proposta_id IS NOT NULL)',
            name='ck_portal_acesso_alvo_unico'),
        db.Index('ix_portal_acesso_obra_ativo', 'obra_id', 'revogado_em'),
        db.Index('ix_portal_acesso_proposta', 'proposta_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id', ondelete='CASCADE'),
                        nullable=True, index=True)
    proposta_id = db.Column(
        db.Integer, db.ForeignKey('propostas_comerciais.id', ondelete='CASCADE'),
        nullable=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'),
                         nullable=False, index=True)

    # SHA-256 hexdigest (64 chars). UNIQUE: dois acessos não podem
    # colidir; e a busca por token é uma leitura de índice único, igual
    # à de hoje (portal_obras_views.py:52), sem custo novo.
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    token_prefixo = db.Column(db.String(12), nullable=False)

    # CSV dos valores de EscopoPortal. String e não tabela filha porque
    # a leitura é sempre "o conjunto inteiro deste token", nunca uma
    # consulta por escopo. Ver utils.portal_acesso.tem_escopo.
    escopos = db.Column(db.String(400), nullable=False, default='ler')

    destinatario_nome = db.Column(db.String(200))
    destinatario_email = db.Column(db.String(200))

    uso_unico = db.Column(db.Boolean, nullable=False, default=False)
    usos = db.Column(db.Integer, nullable=False, default=0)

    # NULL = não expira. Só o backfill legado e o tenant que setar
    # portal_token_dias_validade=0 produzem NULL.
    expira_em = db.Column(db.DateTime, nullable=True, index=True)
    revogado_em = db.Column(db.DateTime, nullable=True)
    revogado_motivo = db.Column(db.String(200))

    criado_por_usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'),
                                      nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ultimo_uso_em = db.Column(db.DateTime)
    ultimo_uso_ip = db.Column(db.String(45))
    ultimo_uso_user_agent = db.Column(db.String(300))

    obra = db.relationship('Obra', foreign_keys=[obra_id],
                           backref=db.backref('acessos_portal', lazy='dynamic'))

    def lista_escopos(self):
        return [e.strip() for e in (self.escopos or '').split(',') if e.strip()]

    def __repr__(self):
        alvo = f'obra={self.obra_id}' if self.obra_id else f'proposta={self.proposta_id}'
        return f'<PortalAcesso {self.token_prefixo}… {alvo} [{self.escopos}]>'
```

- [ ] **Step 4: Escreva a migration 300**

Em `migrations.py`, imediatamente antes de `def executar_migracoes():` (linha 3773), insira:

```python
def _migration_300_portal_acesso():
    """Fase 9a — tabela portal_acesso (capability token do portal).

    Aditiva: nasce vazia e sem consumidor. O backfill dos tokens
    legados é a 302, e a leitura só entra quando as rotas passarem pelo
    decorator (Task 5). Criar a tabela agora não muda comportamento
    nenhum.
    """
    logger.info("[Migration 300] Iniciando — tabela portal_acesso")

    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS portal_acesso (
            id SERIAL PRIMARY KEY,
            obra_id INTEGER REFERENCES obra(id) ON DELETE CASCADE,
            proposta_id INTEGER REFERENCES propostas_comerciais(id) ON DELETE CASCADE,
            admin_id INTEGER NOT NULL REFERENCES usuario(id),
            token_hash VARCHAR(64) NOT NULL,
            token_prefixo VARCHAR(12) NOT NULL,
            escopos VARCHAR(400) NOT NULL DEFAULT 'ler',
            destinatario_nome VARCHAR(200),
            destinatario_email VARCHAR(200),
            uso_unico BOOLEAN NOT NULL DEFAULT FALSE,
            usos INTEGER NOT NULL DEFAULT 0,
            expira_em TIMESTAMP,
            revogado_em TIMESTAMP,
            revogado_motivo VARCHAR(200),
            criado_por_usuario_id INTEGER REFERENCES usuario(id),
            criado_em TIMESTAMP NOT NULL DEFAULT NOW(),
            ultimo_uso_em TIMESTAMP,
            ultimo_uso_ip VARCHAR(45),
            ultimo_uso_user_agent VARCHAR(300),
            CONSTRAINT ck_portal_acesso_alvo_unico CHECK (
                (obra_id IS NOT NULL AND proposta_id IS NULL) OR
                (obra_id IS NULL AND proposta_id IS NOT NULL)
            )
        )
    """))
    db.session.commit()

    db.session.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_portal_acesso_token_hash
        ON portal_acesso (token_hash)
    """))
    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_portal_acesso_obra_ativo
        ON portal_acesso (obra_id, revogado_em)
    """))
    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_portal_acesso_proposta
        ON portal_acesso (proposta_id)
    """))
    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_portal_acesso_admin
        ON portal_acesso (admin_id)
    """))
    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_portal_acesso_expira
        ON portal_acesso (expira_em)
    """))
    db.session.commit()

    logger.info("[Migration 300] Concluída com sucesso")
```

- [ ] **Step 5: Registre a migration**

Em `migrations.py`, na lista `migrations_to_run`, logo após a entrada `(213, ...)` da linha 4013, adicione:

```python
            (300, "Fase 9a — tabela portal_acesso (capability token: hash, escopo, validade, revogação)", _migration_300_portal_acesso),
```

- [ ] **Step 6: Aplique e rode**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "300|ERRO|ERROR"
python -m pytest tests/test_fase9_portal_acesso.py -v
```

Esperado: `[Migration 300] Concluída com sucesso` e os 5 testes PASSAM.

- [ ] **Step 7: Commit**

```bash
git add models.py migrations.py tests/test_fase9_portal_acesso.py
git commit -m "feat(fase9a): tabela portal_acesso — token hasheado, escopado, expiravel

Substitui a credencial do portal (Obra.token_cliente e
Proposta.token_cliente: string em claro, eterna, onipotente). O token
deixa de ser guardado: fica o SHA-256 e um prefixo curto. Tabela nasce
vazia; nenhuma rota le dela ainda."
```

---

## Task 2: Resolver único de token (`utils/portal_acesso.py`)

**Files:**
- Create: `utils/portal_acesso.py`
- Test: `tests/test_fase9_portal_acesso.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente ao final de `tests/test_fase9_portal_acesso.py`:

```python
# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------

def test_emitir_acesso_devolve_token_uma_unica_vez_e_grava_o_hash():
    import hashlib
    from utils.portal_acesso import emitir_acesso

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        token, acesso = emitir_acesso(
            obra=obra, admin_id=admin.id,
            escopos=[EscopoPortal.LER, EscopoPortal.APROVAR_COMPRA],
            dias_validade=90, destinatario_nome='Cliente',
            destinatario_email='cliente@test.local',
        )
        db.session.commit()

        assert len(token) >= 40, 'token curto demais'
        esperado = hashlib.sha256(token.encode('utf-8')).hexdigest()
        assert acesso.token_hash == esperado
        assert acesso.token_prefixo == token[:12]
        assert acesso.escopos == 'ler,aprovar_compra'
        assert acesso.expira_em is not None


def test_resolver_acesso_aceita_token_valido():
    from utils.portal_acesso import emitir_acesso, resolver_acesso

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        token, acesso = emitir_acesso(obra=obra, admin_id=admin.id,
                                      escopos=[EscopoPortal.LER],
                                      dias_validade=90)
        db.session.commit()
        resolvido, motivo = resolver_acesso(token)
        assert motivo is None
        assert resolvido.id == acesso.id


def test_resolver_acesso_recusa_token_expirado():
    from utils.portal_acesso import emitir_acesso, resolver_acesso

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        token, acesso = emitir_acesso(obra=obra, admin_id=admin.id,
                                      escopos=[EscopoPortal.LER],
                                      dias_validade=90)
        acesso.expira_em = datetime.utcnow() - timedelta(seconds=1)
        db.session.commit()
        resolvido, motivo = resolver_acesso(token)
        assert resolvido is None
        assert motivo == 'expirado'


def test_resolver_acesso_recusa_token_revogado():
    from utils.portal_acesso import emitir_acesso, resolver_acesso, revogar_acesso

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        token, acesso = emitir_acesso(obra=obra, admin_id=admin.id,
                                      escopos=[EscopoPortal.LER],
                                      dias_validade=90)
        db.session.commit()
        revogar_acesso(acesso, motivo='teste')
        db.session.commit()
        resolvido, motivo = resolver_acesso(token)
        assert resolvido is None
        assert motivo == 'revogado'


def test_resolver_acesso_recusa_portal_desativado():
    """Obra.portal_ativo=False continua sendo um kill switch por obra."""
    from utils.portal_acesso import emitir_acesso, resolver_acesso

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id, portal_ativo=False)
        token, _ = emitir_acesso(obra=obra, admin_id=admin.id,
                                 escopos=[EscopoPortal.LER], dias_validade=90)
        db.session.commit()
        resolvido, motivo = resolver_acesso(token)
        assert resolvido is None
        assert motivo == 'portal_inativo'


def test_resolver_acesso_recusa_token_inexistente_e_vazio():
    from utils.portal_acesso import resolver_acesso

    with app.app_context():
        for entrada in ('', None, 'nao-existe-nenhum-token-assim'):
            resolvido, motivo = resolver_acesso(entrada)
            assert resolvido is None
            assert motivo == 'inexistente'


def test_uso_unico_queima_no_segundo_uso():
    from utils.portal_acesso import consumir_uso, emitir_acesso, resolver_acesso

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        token, acesso = emitir_acesso(
            obra=obra, admin_id=admin.id,
            escopos=[EscopoPortal.ASSINAR_MEDICAO],
            dias_validade=7, uso_unico=True)
        db.session.commit()

        primeiro, motivo = resolver_acesso(token)
        assert primeiro is not None and motivo is None
        consumir_uso(primeiro)
        db.session.commit()

        segundo, motivo2 = resolver_acesso(token)
        assert segundo is None
        assert motivo2 == 'consumido'


def test_tem_escopo_falha_fechada():
    from utils.portal_acesso import emitir_acesso, tem_escopo

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _, acesso = emitir_acesso(obra=obra, admin_id=admin.id,
                                  escopos=[EscopoPortal.LER], dias_validade=90)
        db.session.commit()
        assert tem_escopo(acesso, EscopoPortal.LER) is True
        assert tem_escopo(acesso, EscopoPortal.APROVAR_COMPRA) is False
        assert tem_escopo(acesso, EscopoPortal.ASSINAR_MEDICAO) is False
        assert tem_escopo(None, EscopoPortal.LER) is False


def test_ler_nunca_implica_assinar():
    """Trava de regressão da decisão D5: nenhum escopo herda ASSINAR_MEDICAO."""
    from utils.portal_acesso import emitir_acesso, tem_escopo

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _, acesso = emitir_acesso(
            obra=obra, admin_id=admin.id,
            escopos=[EscopoPortal.LER, EscopoPortal.APROVAR_COMPRA,
                     EscopoPortal.ENVIAR_COMPROVANTE, EscopoPortal.SELECIONAR_MAPA],
            dias_validade=90)
        db.session.commit()
        assert tem_escopo(acesso, EscopoPortal.ASSINAR_MEDICAO) is False
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase9_portal_acesso.py -v -k "emitir or resolver or uso_unico or escopo"
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'utils.portal_acesso'`.

- [ ] **Step 3: Implemente o resolver**

Crie `utils/portal_acesso.py`:

```python
#!/usr/bin/env python3
"""Resolver único de capability token do portal — SIGE Fase 9a.

ANTES desta fase a autorização do portal do cliente inteira era isto,
repetido em três arquivos:

    Obra.query.filter_by(token_cliente=token, portal_ativo=True).first()

    * portal_obras_views.py:52   (`_get_obra_by_token`, usado pelas 5 POSTs)
    * portal_obras_views.py:63   (`_resolve_obra_for_view`, usado pelas GETs)
    * medicao_views.py:519       (token vindo da QUERYSTRING)
    * propostas_consolidated.py:2456/2506/2590 (variante com Proposta)

Sem validade, sem escopo, sem revogação individual, sem contador, sem
IP, sem trilha. Este módulo é o único caminho a partir da Fase 9a.

Regras, todas de falha FECHADA:
  * token desconhecido, vazio ou None  -> (None, 'inexistente')
  * expirado                            -> (None, 'expirado')
  * revogado                            -> (None, 'revogado')
  * uso único já consumido              -> (None, 'consumido')
  * obra com portal_ativo=False         -> (None, 'portal_inativo')
  * escopo insuficiente                 -> tem_escopo() devolve False

Nada aqui devolve "talvez". Nada aqui adivinha tenant.
"""
from __future__ import annotations

import functools
import hashlib
import logging
import secrets
from datetime import datetime, timedelta

from flask import abort, g, render_template, request

from models import EscopoPortal, Obra, PortalAcesso, db

logger = logging.getLogger('portal_acesso')

# 32 bytes urlsafe = 256 bits de entropia, igual ao que já era gerado em
# views/obras.py:375. A entropia nunca foi o problema — a ausência de
# validade, escopo e trilha era.
TOKEN_BYTES = 32
PREFIXO_TAMANHO = 12
DIAS_VALIDADE_PADRAO = 90
DIAS_VALIDADE_ASSINATURA = 7


def _hash(token: str) -> str:
    """SHA-256 hexdigest. Sem salt e sem KDF de propósito: o token tem
    256 bits de entropia aleatória, não é uma senha escolhida por humano
    — bcrypt/argon2 aqui só custaria latência por request sem ganhar
    resistência a dicionário que não existe."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def emitir_acesso(*, admin_id, escopos, obra=None, proposta=None,
                  dias_validade=DIAS_VALIDADE_PADRAO, uso_unico=False,
                  destinatario_nome=None, destinatario_email=None,
                  criado_por_usuario_id=None):
    """Cria um acesso e devolve ``(token_em_claro, PortalAcesso)``.

    Esta é a ÚNICA vez em que o token existe em claro. Não faz commit —
    quem chama decide a transação.

    ``dias_validade=0`` produz ``expira_em=NULL`` (não expira). Só use
    quando for uma decisão consciente do tenant (ver D2 no plano).
    """
    if (obra is None) == (proposta is None):
        raise ValueError('emitir_acesso exige exatamente um de obra/proposta')

    token = secrets.token_urlsafe(TOKEN_BYTES)
    valores = []
    for e in escopos:
        valores.append(e.value if isinstance(e, EscopoPortal) else str(e))

    acesso = PortalAcesso(
        obra_id=obra.id if obra is not None else None,
        proposta_id=proposta.id if proposta is not None else None,
        admin_id=admin_id,
        token_hash=_hash(token),
        token_prefixo=token[:PREFIXO_TAMANHO],
        escopos=','.join(valores),
        destinatario_nome=destinatario_nome,
        destinatario_email=destinatario_email,
        uso_unico=bool(uso_unico),
        expira_em=(datetime.utcnow() + timedelta(days=dias_validade)
                   if dias_validade else None),
        criado_por_usuario_id=criado_por_usuario_id,
    )
    db.session.add(acesso)
    db.session.flush()
    return token, acesso


def resolver_acesso(token):
    """Devolve ``(PortalAcesso, None)`` ou ``(None, motivo)``.

    Motivos possíveis: 'inexistente', 'expirado', 'revogado',
    'consumido', 'portal_inativo'.
    """
    if not token:
        return None, 'inexistente'

    acesso = PortalAcesso.query.filter_by(token_hash=_hash(token)).first()
    if acesso is None:
        return None, 'inexistente'
    if acesso.revogado_em is not None:
        return None, 'revogado'
    if acesso.expira_em is not None and acesso.expira_em <= datetime.utcnow():
        return None, 'expirado'
    if acesso.uso_unico and (acesso.usos or 0) >= 1:
        return None, 'consumido'
    if acesso.obra_id is not None:
        obra = db.session.get(Obra, acesso.obra_id)
        if obra is None:
            return None, 'inexistente'
        if not obra.portal_ativo:
            return None, 'portal_inativo'
    return acesso, None


def tem_escopo(acesso, escopo) -> bool:
    """Falha fechada: sem acesso, sem escopo declarado, é False."""
    if acesso is None:
        return False
    alvo = escopo.value if isinstance(escopo, EscopoPortal) else str(escopo)
    return alvo in acesso.lista_escopos()


def revogar_acesso(acesso, motivo=None):
    """Revoga sem apagar — a linha continua servindo de trilha."""
    if acesso is None:
        return None
    acesso.revogado_em = datetime.utcnow()
    acesso.revogado_motivo = (motivo or '')[:200]
    return acesso


def consumir_uso(acesso):
    """Incrementa o contador. Em token de uso único, queima a credencial."""
    if acesso is None:
        return None
    acesso.usos = (acesso.usos or 0) + 1
    return acesso


def marcar_uso(acesso):
    """Carimba último uso (data, IP, user-agent) sem queimar o token."""
    if acesso is None:
        return None
    acesso.ultimo_uso_em = datetime.utcnow()
    try:
        acesso.ultimo_uso_ip = (request.remote_addr or '')[:45]
        acesso.ultimo_uso_user_agent = (request.headers.get('User-Agent') or '')[:300]
    except Exception:
        pass
    return acesso


def acesso_corrente():
    """O PortalAcesso do request atual, colocado em `g` pelo decorator."""
    return getattr(g, 'portal_acesso', None)
```

- [ ] **Step 4: Rode os testes**

```bash
python -m pytest tests/test_fase9_portal_acesso.py -v
```

Esperado: os 14 testes PASSAM.

- [ ] **Step 5: Commit**

```bash
git add utils/portal_acesso.py tests/test_fase9_portal_acesso.py
git commit -m "feat(fase9a): resolver unico de capability token do portal

utils/portal_acesso.py substitui as quatro copias de
Obra.query.filter_by(token_cliente=...). Falha fechada em cinco
motivos: inexistente, expirado, revogado, consumido, portal_inativo.
LER nunca implica ASSINAR_MEDICAO — travado por teste."
```

---

## Task 3: Trilha de auditoria em banco (`PortalEvento`)

**Files:**
- Modify: `models.py` (modelo após `PortalAcesso`)
- Modify: `migrations.py` (migration 301 + registro)
- Modify: `utils/portal_acesso.py` (função `registrar_evento`)
- Test: `tests/test_fase9_portal_acesso.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente ao final de `tests/test_fase9_portal_acesso.py`:

```python
# ---------------------------------------------------------------------------
# Trilha
# ---------------------------------------------------------------------------

def test_evento_registra_acesso_concedido():
    from models import PortalEvento
    from utils.portal_acesso import emitir_acesso, registrar_evento

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _, acesso = emitir_acesso(obra=obra, admin_id=admin.id,
                                  escopos=[EscopoPortal.LER], dias_validade=90)
        db.session.commit()
        registrar_evento(acesso=acesso, acao='ver_portal', resultado='ok')
        db.session.commit()

        ev = PortalEvento.query.filter_by(acesso_id=acesso.id).one()
        assert ev.acao == 'ver_portal'
        assert ev.resultado == 'ok'
        assert ev.obra_id == obra.id
        assert ev.admin_id == admin.id
        assert ev.criado_em is not None


def test_evento_registra_negativa_sem_acesso():
    """Token inválido não tem acesso_id — e mesmo assim deixa rastro."""
    from models import PortalEvento
    from utils.portal_acesso import registrar_evento

    with app.app_context():
        antes = PortalEvento.query.filter_by(acao='ver_portal',
                                             resultado='negado').count()
        registrar_evento(acesso=None, acao='ver_portal', resultado='negado',
                         motivo='inexistente', token='abcdefgh12345678')
        db.session.commit()
        depois = PortalEvento.query.filter_by(acao='ver_portal',
                                              resultado='negado').count()
        assert depois == antes + 1

        ev = (PortalEvento.query
              .filter_by(acao='ver_portal', resultado='negado')
              .order_by(PortalEvento.id.desc()).first())
        assert ev.acesso_id is None
        assert ev.motivo == 'inexistente'
        # O token NUNCA é gravado inteiro — só o prefixo.
        assert ev.token_prefixo == 'abcdefgh1234'
        assert 'abcdefgh12345678' not in (ev.token_prefixo or '')


def test_evento_nunca_derruba_o_request():
    """A trilha é obrigatória, mas não pode virar indisponibilidade."""
    from utils.portal_acesso import registrar_evento

    with app.app_context():
        # acao gigante: se registrar_evento propagasse o DataError, o
        # cliente veria 500 ao tentar ver o portal.
        registrar_evento(acesso=None, acao='x' * 5000, resultado='ok')
        db.session.rollback()
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase9_portal_acesso.py -v -k evento
```

Esperado: FAIL — `ImportError: cannot import name 'PortalEvento' from 'models'`.

- [ ] **Step 3: Adicione o modelo em `models.py`**

Logo após `class PortalAcesso`, insira:

```python
class PortalEvento(db.Model):
    """Trilha de auditoria do portal do cliente — Fase 9a.

    Copia a forma de `CronogramaImportacaoEvento` (models.py:5178-5203),
    que é o único padrão de trilha em banco que o sistema já tem.

    Por que EM BANCO e não só em log, diferente da decisão tomada em
    `utils/auditoria_acesso.py:14-18`: aqui a trilha é *prova*, precisa
    ser consultável pelo tenant na tela da obra e citável num
    comprovante de assinatura. Log em stdout não atende nenhum dos três.
    A trilha do access log continua existindo em paralelo.

    Append-only por contrato: não existe rota que edite nem apague
    linha desta tabela.
    """
    __tablename__ = 'portal_evento'
    __table_args__ = (
        db.Index('ix_portal_evento_obra_data', 'obra_id', 'criado_em'),
        db.Index('ix_portal_evento_acesso', 'acesso_id'),
        db.Index('ix_portal_evento_resultado', 'resultado', 'criado_em'),
    )

    id = db.Column(db.Integer, primary_key=True)
    acesso_id = db.Column(db.Integer,
                          db.ForeignKey('portal_acesso.id', ondelete='SET NULL'),
                          nullable=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id', ondelete='CASCADE'),
                        nullable=True)
    proposta_id = db.Column(
        db.Integer, db.ForeignKey('propostas_comerciais.id', ondelete='CASCADE'),
        nullable=True)

    acao = db.Column(db.String(60), nullable=False)
    resultado = db.Column(db.String(20), nullable=False)   # 'ok' | 'negado'
    motivo = db.Column(db.String(40))                      # 'expirado', 'escopo', ...
    alvo_tipo = db.Column(db.String(40))                   # 'pedido_compra', 'medicao_obra', ...
    alvo_id = db.Column(db.Integer)

    # Prefixo, NUNCA o token. Ver utils/portal_acesso.registrar_evento.
    token_prefixo = db.Column(db.String(12))
    ip = db.Column(db.String(45))
    user_agent = db.Column(db.String(300))
    detalhes = db.Column(JSON, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    acesso = db.relationship('PortalAcesso',
                             backref=db.backref('eventos', lazy='dynamic'))

    def __repr__(self):
        return f'<PortalEvento {self.acao}/{self.resultado} obra={self.obra_id}>'
```

- [ ] **Step 4: Escreva a migration 301 e registre**

Em `migrations.py`, antes de `def executar_migracoes():`:

```python
def _migration_301_portal_evento():
    """Fase 9a — tabela portal_evento (trilha do portal do cliente).

    Aditiva. Antes desta tabela, aprovar uma compra pelo portal não
    deixava rastro nenhum em banco: o único registro era um
    `logger.warning('[ESCRITA-ANONIMA] ...')` com o TOKEN EM CLARO no
    path (utils/auditoria_acesso.py:66-79).
    """
    logger.info("[Migration 301] Iniciando — tabela portal_evento")

    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS portal_evento (
            id SERIAL PRIMARY KEY,
            acesso_id INTEGER REFERENCES portal_acesso(id) ON DELETE SET NULL,
            admin_id INTEGER REFERENCES usuario(id),
            obra_id INTEGER REFERENCES obra(id) ON DELETE CASCADE,
            proposta_id INTEGER REFERENCES propostas_comerciais(id) ON DELETE CASCADE,
            acao VARCHAR(60) NOT NULL,
            resultado VARCHAR(20) NOT NULL,
            motivo VARCHAR(40),
            alvo_tipo VARCHAR(40),
            alvo_id INTEGER,
            token_prefixo VARCHAR(12),
            ip VARCHAR(45),
            user_agent VARCHAR(300),
            detalhes JSON,
            criado_em TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """))
    db.session.commit()

    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_portal_evento_obra_data
        ON portal_evento (obra_id, criado_em)
    """))
    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_portal_evento_acesso
        ON portal_evento (acesso_id)
    """))
    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_portal_evento_resultado
        ON portal_evento (resultado, criado_em)
    """))
    db.session.commit()

    logger.info("[Migration 301] Concluída com sucesso")
```

Registre em `migrations_to_run`, após a entrada `300`:

```python
            (301, "Fase 9a — tabela portal_evento (trilha append-only do portal do cliente)", _migration_301_portal_evento),
```

- [ ] **Step 5: Acrescente `registrar_evento` a `utils/portal_acesso.py`**

Ao final de `utils/portal_acesso.py`:

```python
def registrar_evento(*, acesso=None, acao, resultado, motivo=None,
                     alvo_tipo=None, alvo_id=None, token=None,
                     obra_id=None, proposta_id=None, admin_id=None,
                     detalhes=None):
    """Grava uma linha em `portal_evento`. NUNCA levanta.

    A trilha é obrigatória, mas não pode virar indisponibilidade: se a
    gravação falhar, o request continua e o problema vai para o log.

    O `token` recebido é usado APENAS para derivar o prefixo de 12
    caracteres — o token completo jamais entra na tabela nem no log.
    """
    from models import PortalEvento

    try:
        if acesso is not None:
            obra_id = obra_id if obra_id is not None else acesso.obra_id
            proposta_id = (proposta_id if proposta_id is not None
                           else acesso.proposta_id)
            admin_id = admin_id if admin_id is not None else acesso.admin_id
            prefixo = acesso.token_prefixo
        else:
            prefixo = (token or '')[:PREFIXO_TAMANHO] or None

        try:
            ip = (request.remote_addr or '')[:45]
            ua = (request.headers.get('User-Agent') or '')[:300]
        except Exception:
            ip, ua = None, None

        db.session.add(PortalEvento(
            acesso_id=acesso.id if acesso is not None else None,
            admin_id=admin_id, obra_id=obra_id, proposta_id=proposta_id,
            acao=(acao or '')[:60], resultado=(resultado or '')[:20],
            motivo=(motivo or None) and motivo[:40],
            alvo_tipo=(alvo_tipo or None) and alvo_tipo[:40],
            alvo_id=alvo_id, token_prefixo=prefixo,
            ip=ip, user_agent=ua, detalhes=detalhes,
        ))
    except Exception:
        logger.exception('[PORTAL] registrar_evento falhou (acao=%s)', acao)
```

- [ ] **Step 6: Aplique e rode**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "301|ERRO|ERROR"
python -m pytest tests/test_fase9_portal_acesso.py -v
```

Esperado: `[Migration 301] Concluída com sucesso` e os 17 testes PASSAM.

- [ ] **Step 7: Commit**

```bash
git add models.py migrations.py utils/portal_acesso.py tests/test_fase9_portal_acesso.py
git commit -m "feat(fase9a): trilha portal_evento append-only

Copia a forma de CronogramaImportacaoEvento. Grava concessao E negativa
(token invalido, expirado, escopo insuficiente) com IP, user-agent e o
PREFIXO do token — nunca o token. registrar_evento nunca levanta."
```

---

## Task 4: Backfill dos tokens legados + flags por tenant

**Files:**
- Modify: `models.py` (`class ConfiguracaoEmpresa`, junto de `cronograma_mpp_ativo` em `models.py:3620`)
- Modify: `migrations.py` (migrations 302 e 304 + registro)
- Create: `scripts/portal_acessos.py`
- Test: `tests/test_fase9_portal_acesso.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente ao final de `tests/test_fase9_portal_acesso.py`:

```python
# ---------------------------------------------------------------------------
# Backfill e CLI
# ---------------------------------------------------------------------------

def test_backfill_migra_token_legado_preservando_o_link():
    """O link que o cliente já tem no WhatsApp precisa continuar valendo."""
    import secrets as _s

    from scripts.portal_acessos import backfill_tokens_legados
    from utils.portal_acesso import resolver_acesso

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        token_legado = _s.token_urlsafe(32)
        obra.token_cliente = token_legado
        db.session.commit()

        relatorio = backfill_tokens_legados(dry_run=False, admin_id=admin.id,
                                            dias_validade=90)
        assert relatorio['migrados'] >= 1

        acesso, motivo = resolver_acesso(token_legado)
        assert motivo is None, f'link legado parou de funcionar: {motivo}'
        assert acesso.obra_id == obra.id


def test_backfill_nunca_concede_assinar_medicao():
    """Decisão D5: nenhum token de origem desconhecida assina nada."""
    import secrets as _s

    from scripts.portal_acessos import backfill_tokens_legados
    from utils.portal_acesso import resolver_acesso, tem_escopo

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        token_legado = _s.token_urlsafe(32)
        obra.token_cliente = token_legado
        db.session.commit()

        backfill_tokens_legados(dry_run=False, admin_id=admin.id,
                                dias_validade=90)
        acesso, _ = resolver_acesso(token_legado)
        assert tem_escopo(acesso, EscopoPortal.LER) is True
        assert tem_escopo(acesso, EscopoPortal.APROVAR_COMPRA) is True
        assert tem_escopo(acesso, EscopoPortal.ASSINAR_MEDICAO) is False


def test_backfill_e_idempotente():
    import secrets as _s

    from scripts.portal_acessos import backfill_tokens_legados

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        obra.token_cliente = _s.token_urlsafe(32)
        db.session.commit()

        backfill_tokens_legados(dry_run=False, admin_id=admin.id,
                                dias_validade=90)
        segunda = backfill_tokens_legados(dry_run=False, admin_id=admin.id,
                                          dias_validade=90)
        assert segunda['migrados'] == 0
        assert PortalAcesso.query.filter_by(obra_id=obra.id).count() == 1


def test_backfill_dry_run_nao_escreve():
    import secrets as _s

    from scripts.portal_acessos import backfill_tokens_legados

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        obra.token_cliente = _s.token_urlsafe(32)
        db.session.commit()

        relatorio = backfill_tokens_legados(dry_run=True, admin_id=admin.id,
                                            dias_validade=90)
        assert relatorio['migrados'] >= 1
        assert PortalAcesso.query.filter_by(obra_id=obra.id).count() == 0


def test_flag_dias_validade_nasce_em_90():
    from models import ConfiguracaoEmpresa

    with app.app_context():
        admin = _admin()
        cfg = ConfiguracaoEmpresa(admin_id=admin.id, nome_empresa='Teste')
        db.session.add(cfg)
        db.session.commit()
        assert cfg.portal_token_dias_validade == 90
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase9_portal_acesso.py -v -k "backfill or flag_dias"
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'scripts.portal_acessos'`.

- [ ] **Step 3: Adicione a coluna de flag em `models.py`**

Em `class ConfiguracaoEmpresa`, imediatamente após `cronograma_mpp_ativo` (`models.py:3620`):

```python
    # Fase 9a — validade padrão do capability token do portal, em dias.
    # 0 = não expira (decisão consciente do tenant; ver D2 do plano da
    # Fase 9). Default 90: os links legados migrados pela migration 302
    # ganham exatamente esta janela contada da data da migração.
    portal_token_dias_validade = db.Column(db.Integer, nullable=False, default=90)
    # Fase 9a — quando True, a medição fechada só vira FATURADO depois
    # da assinatura do cliente. Nasce False para não travar o
    # faturamento de ninguém no deploy (mesmo padrão de rollout do
    # cronograma_mpp_ativo, migrations.py migration 211).
    portal_exige_assinatura_medicao = db.Column(db.Boolean, nullable=False,
                                                default=False)
```

- [ ] **Step 4: Escreva as migrations 302 e 304 e registre**

Em `migrations.py`, antes de `def executar_migracoes():`:

```python
def _migration_302_backfill_portal_acesso():
    """Fase 9a — migra os tokens legados para portal_acesso.

    O token legado (obra.token_cliente, models.py:261 —
    proposta.token_cliente, models.py:2986) está EM CLARO no banco.
    Aqui ele é hasheado e passa a viver só como SHA-256. A coluna
    original NÃO é apagada nesta migração: a limpeza é a Task 8, depois
    que templates e views pararem de lê-la.

    Escopos concedidos (decisão D5 do plano): exatamente o que o token
    já podia fazer — ler, aprovar compra, enviar comprovante, selecionar
    mapa. NUNCA assinar_medicao.

    Validade: `configuracao_empresa.portal_token_dias_validade` do
    tenant (default 90), contada a partir de AGORA. Nenhum cliente perde
    acesso no dia do deploy.

    Idempotente: pula obra/proposta que já tenha acesso com o mesmo hash.
    """
    import hashlib

    logger.info("[Migration 302] Iniciando — backfill de portal_acesso")

    ESCOPOS_LEGADOS_OBRA = 'ler,aprovar_compra,enviar_comprovante,selecionar_mapa'
    ESCOPOS_LEGADOS_PROPOSTA = 'ler,aprovar_proposta'

    obras = db.session.execute(text("""
        SELECT o.id, o.admin_id, o.token_cliente,
               COALESCE(c.nome, ''), COALESCE(c.email, ''),
               COALESCE(ce.portal_token_dias_validade, 90)
        FROM obra o
        LEFT JOIN cliente c ON c.id = o.cliente_id
        LEFT JOIN configuracao_empresa ce ON ce.admin_id = o.admin_id
        WHERE o.token_cliente IS NOT NULL AND o.token_cliente <> ''
    """)).fetchall()

    migrados = 0
    for obra_id, admin_id, token, cli_nome, cli_email, dias in obras:
        token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
        existe = db.session.execute(
            text("SELECT 1 FROM portal_acesso WHERE token_hash = :h LIMIT 1"),
            {'h': token_hash}).fetchone()
        if existe:
            continue
        db.session.execute(text("""
            INSERT INTO portal_acesso
                (obra_id, admin_id, token_hash, token_prefixo, escopos,
                 destinatario_nome, destinatario_email, uso_unico, usos,
                 expira_em, criado_em)
            VALUES
                (:obra_id, :admin_id, :h, :prefixo, :escopos,
                 :nome, :email, FALSE, 0,
                 CASE WHEN :dias > 0 THEN NOW() + (:dias || ' days')::interval
                      ELSE NULL END,
                 NOW())
        """), {
            'obra_id': obra_id, 'admin_id': admin_id, 'h': token_hash,
            'prefixo': token[:12], 'escopos': ESCOPOS_LEGADOS_OBRA,
            'nome': cli_nome or '(legado)', 'email': cli_email or None,
            'dias': int(dias or 90),
        })
        migrados += 1
    db.session.commit()
    logger.info("[Migration 302] %s tokens de obra migrados", migrados)

    propostas = db.session.execute(text("""
        SELECT p.id, p.admin_id, p.token_cliente,
               COALESCE(ce.portal_token_dias_validade, 90)
        FROM propostas_comerciais p
        LEFT JOIN configuracao_empresa ce ON ce.admin_id = p.admin_id
        WHERE p.token_cliente IS NOT NULL AND p.token_cliente <> ''
          AND p.admin_id IS NOT NULL
    """)).fetchall()

    migrados_p = 0
    for prop_id, admin_id, token, dias in propostas:
        token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
        existe = db.session.execute(
            text("SELECT 1 FROM portal_acesso WHERE token_hash = :h LIMIT 1"),
            {'h': token_hash}).fetchone()
        if existe:
            continue
        db.session.execute(text("""
            INSERT INTO portal_acesso
                (proposta_id, admin_id, token_hash, token_prefixo, escopos,
                 destinatario_nome, uso_unico, usos, expira_em, criado_em)
            VALUES
                (:prop_id, :admin_id, :h, :prefixo, :escopos,
                 '(legado)', FALSE, 0,
                 CASE WHEN :dias > 0 THEN NOW() + (:dias || ' days')::interval
                      ELSE NULL END,
                 NOW())
        """), {
            'prop_id': prop_id, 'admin_id': admin_id, 'h': token_hash,
            'prefixo': token[:12], 'escopos': ESCOPOS_LEGADOS_PROPOSTA,
            'dias': int(dias or 90),
        })
        migrados_p += 1
    db.session.commit()

    logger.info("[Migration 302] %s tokens de proposta migrados", migrados_p)
    logger.info("[Migration 302] Concluída com sucesso")


def _migration_304_configuracao_empresa_portal():
    """Fase 9a — flags de portal em configuracao_empresa.

    Precisa rodar ANTES da 302 (que lê portal_token_dias_validade), por
    isso a ordem de registro em `migrations_to_run` é 300, 301, 304, 302.
    O número não é a ordem — a lista é.
    """
    logger.info("[Migration 304] Iniciando — flags de portal")

    db.session.execute(text("""
        ALTER TABLE configuracao_empresa
        ADD COLUMN IF NOT EXISTS portal_token_dias_validade INTEGER
        NOT NULL DEFAULT 90
    """))
    db.session.execute(text("""
        ALTER TABLE configuracao_empresa
        ADD COLUMN IF NOT EXISTS portal_exige_assinatura_medicao BOOLEAN
        NOT NULL DEFAULT FALSE
    """))
    db.session.commit()

    logger.info("[Migration 304] Concluída com sucesso")
```

Registre em `migrations_to_run`, após a entrada `301`, **nesta ordem**:

```python
            (304, "Fase 9a — configuracao_empresa: portal_token_dias_validade (90) e portal_exige_assinatura_medicao (False)", _migration_304_configuracao_empresa_portal),
            (302, "Fase 9a — backfill: tokens legados de obra e proposta viram portal_acesso hasheado (sem assinar_medicao)", _migration_302_backfill_portal_acesso),
```

- [ ] **Step 5: Crie o CLI `scripts/portal_acessos.py`**

```python
#!/usr/bin/env python3
"""Gestão de acessos do portal do cliente — SIGE Fase 9a.

O token em claro só existe no momento da emissão. Este CLI é o caminho
de linha de comando para emitir, listar e revogar — a tela equivalente
vive em templates/obras/detalhes_obra_profissional.html.

Uso:
    python scripts/portal_acessos.py listar --obra-id 42
    python scripts/portal_acessos.py emitir --obra-id 42 \\
        --nome "João da Silva" --email joao@cliente.com --escopos ler
    python scripts/portal_acessos.py revogar --acesso-id 17 --motivo "cliente trocou"
    python scripts/portal_acessos.py expirando --dias 15
    python scripts/portal_acessos.py backfill               # dry-run
    python scripts/portal_acessos.py backfill --aplicar
"""
import argparse
import hashlib
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (  # noqa: E402
    Cliente, ConfiguracaoEmpresa, EscopoPortal, Obra, PortalAcesso, db,
)
from utils.portal_acesso import emitir_acesso, revogar_acesso  # noqa: E402

ESCOPOS_LEGADOS = [
    EscopoPortal.LER,
    EscopoPortal.APROVAR_COMPRA,
    EscopoPortal.ENVIAR_COMPROVANTE,
    EscopoPortal.SELECIONAR_MAPA,
]


def backfill_tokens_legados(dry_run=True, admin_id=None, dias_validade=None):
    """Espelho Python da migration 302, para teste e para reexecução manual.

    Deliberadamente NÃO concede EscopoPortal.ASSINAR_MEDICAO: um token
    cuja origem ninguém consegue reconstituir não pode produzir
    assinatura (decisão D5).
    """
    query = Obra.query.filter(Obra.token_cliente.isnot(None),
                              Obra.token_cliente != '')
    if admin_id is not None:
        query = query.filter(Obra.admin_id == admin_id)

    migrados, pulados = 0, 0
    for obra in query.all():
        token_hash = hashlib.sha256(obra.token_cliente.encode('utf-8')).hexdigest()
        if PortalAcesso.query.filter_by(token_hash=token_hash).first():
            pulados += 1
            continue

        dias = dias_validade
        if dias is None:
            cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=obra.admin_id).first()
            dias = cfg.portal_token_dias_validade if cfg else 90

        migrados += 1
        if dry_run:
            continue

        cliente = db.session.get(Cliente, obra.cliente_id) if obra.cliente_id else None
        db.session.add(PortalAcesso(
            obra_id=obra.id, admin_id=obra.admin_id,
            token_hash=token_hash, token_prefixo=obra.token_cliente[:12],
            escopos=','.join(e.value for e in ESCOPOS_LEGADOS),
            destinatario_nome=(cliente.nome if cliente else None) or '(legado)',
            destinatario_email=(cliente.email if cliente else None),
            uso_unico=False, usos=0,
            expira_em=(datetime.utcnow() + timedelta(days=int(dias))
                       if dias else None),
        ))

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()
    return {'migrados': migrados, 'pulados': pulados}


def _cmd_listar(args):
    q = PortalAcesso.query
    if args.obra_id:
        q = q.filter_by(obra_id=args.obra_id)
    agora = datetime.utcnow()
    print(f'{"id":>5}  {"prefixo":<14} {"escopos":<52} {"situação":<12} destinatário')
    for a in q.order_by(PortalAcesso.id).all():
        if a.revogado_em:
            sit = 'revogado'
        elif a.expira_em and a.expira_em <= agora:
            sit = 'expirado'
        elif a.uso_unico and (a.usos or 0) >= 1:
            sit = 'consumido'
        elif a.expira_em:
            sit = f'{(a.expira_em - agora).days}d'
        else:
            sit = 'sem prazo'
        print(f'{a.id:>5}  {a.token_prefixo + "…":<14} {a.escopos:<52} '
              f'{sit:<12} {a.destinatario_nome or "—"}')
    return 0


def _cmd_emitir(args):
    obra = db.session.get(Obra, args.obra_id)
    if obra is None:
        print(f'Obra {args.obra_id} não encontrada.')
        return 1
    escopos = [EscopoPortal(e.strip()) for e in args.escopos.split(',') if e.strip()]
    token, acesso = emitir_acesso(
        obra=obra, admin_id=obra.admin_id, escopos=escopos,
        dias_validade=args.dias, destinatario_nome=args.nome,
        destinatario_email=args.email, uso_unico=args.uso_unico,
    )
    db.session.commit()
    print('=== Link emitido — ANOTE AGORA, ele não é exibido de novo ===')
    print(f'acesso_id ..: {acesso.id}')
    print(f'escopos ....: {acesso.escopos}')
    print(f'validade ...: {acesso.expira_em or "sem prazo"}')
    print(f'URL ........: /portal/obra/{token}')
    return 0


def _cmd_revogar(args):
    acesso = db.session.get(PortalAcesso, args.acesso_id)
    if acesso is None:
        print(f'Acesso {args.acesso_id} não encontrado.')
        return 1
    revogar_acesso(acesso, motivo=args.motivo)
    db.session.commit()
    print(f'Acesso {acesso.id} ({acesso.token_prefixo}…) revogado.')
    return 0


def _cmd_expirando(args):
    limite = datetime.utcnow() + timedelta(days=args.dias)
    q = (PortalAcesso.query
         .filter(PortalAcesso.revogado_em.is_(None))
         .filter(PortalAcesso.expira_em.isnot(None))
         .filter(PortalAcesso.expira_em <= limite)
         .order_by(PortalAcesso.expira_em))
    linhas = q.all()
    print(f'{len(linhas)} acesso(s) expiram nos próximos {args.dias} dias:')
    for a in linhas:
        print(f'  acesso_id={a.id} obra_id={a.obra_id} '
              f'expira={a.expira_em:%d/%m/%Y} para={a.destinatario_email or "—"}')
    return 0


def _cmd_backfill(args):
    rel = backfill_tokens_legados(dry_run=not args.aplicar)
    modo = 'APLICADO' if args.aplicar else 'DRY-RUN (nada foi escrito)'
    print(f'=== Backfill de tokens legados — {modo} ===')
    print(f'Migrados ...: {rel["migrados"]}')
    print(f'Já migrados : {rel["pulados"]}')
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='cmd', required=True)

    s = sub.add_parser('listar'); s.add_argument('--obra-id', type=int)
    s.set_defaults(func=_cmd_listar)

    s = sub.add_parser('emitir')
    s.add_argument('--obra-id', type=int, required=True)
    s.add_argument('--nome'); s.add_argument('--email')
    s.add_argument('--escopos', default='ler')
    s.add_argument('--dias', type=int, default=90)
    s.add_argument('--uso-unico', action='store_true')
    s.set_defaults(func=_cmd_emitir)

    s = sub.add_parser('revogar')
    s.add_argument('--acesso-id', type=int, required=True)
    s.add_argument('--motivo', default='revogado via CLI')
    s.set_defaults(func=_cmd_revogar)

    s = sub.add_parser('expirando'); s.add_argument('--dias', type=int, default=15)
    s.set_defaults(func=_cmd_expirando)

    s = sub.add_parser('backfill'); s.add_argument('--aplicar', action='store_true')
    s.set_defaults(func=_cmd_backfill)

    args = p.parse_args()
    from app import app
    with app.app_context():
        return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 6: Aplique, rode o dry-run e rode os testes**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "302|304|ERRO|ERROR"
python scripts/portal_acessos.py backfill
python -m pytest tests/test_fase9_portal_acesso.py -v
```

Esperado: `[Migration 304] Concluída`, `[Migration 302] Concluída`, o dry-run imprime `Migrados: 0` (a 302 já migrou tudo) e os 22 testes PASSAM.

- [ ] **Step 7: Commit**

```bash
git add models.py migrations.py scripts/portal_acessos.py tests/test_fase9_portal_acesso.py
git commit -m "feat(fase9a): backfill dos tokens legados + flags de portal por tenant

Migration 304 cria portal_token_dias_validade (90) e
portal_exige_assinatura_medicao (False). Migration 302 hasheia os
tokens de obra e proposta que hoje estao EM CLARO no banco, com os
escopos que ja tinham e validade de 90 dias a partir de agora — nenhum
cliente perde acesso no deploy, e nenhum token legado ganha
assinar_medicao. CLI scripts/portal_acessos.py emite, lista e revoga."
```

---

## Task 5: Decorator `portal_token_required` nas 11 rotas do portal

**Files:**
- Modify: `utils/portal_acesso.py` (decorator)
- Modify: `portal_obras_views.py:49-76` (helpers) e as 8 rotas
- Modify: `propostas_consolidated.py:2453,2503,2587` (3 rotas) — **e a linha 2469**
- Modify: `medicao_views.py:512-521`
- Create: `templates/portal/portal_link_invalido.html`
- Test: `tests/test_fase9_portal_rotas.py`

- [ ] **Step 1: Escreva a matriz de testes que falha**

Crie `tests/test_fase9_portal_rotas.py`:

```python
"""Fase 9a — matriz rota × escopo × estado do token.

Antes desta fase, SETE rotas POST mutavam estado com nada além da URL:

    portal_obras_views.py:343  aprovar_compra    (gera custo + almoxarifado)
    portal_obras_views.py:377  recusar_compra
    portal_obras_views.py:388  upload_comprovante (grava arquivo em disco)
    portal_obras_views.py:432  aprovar_mapa_concorrencia
    portal_obras_views.py:546  selecionar_mapa_v2
    propostas_consolidated.py:2503  aprovar_proposta_cliente (CRIA a Obra)
    propostas_consolidated.py:2587  rejeitar_proposta_cliente

Nenhuma tinha login, escopo, expiração, CSRF ou rate-limit. Estes
testes travam o novo regime: cada rota exige um escopo nominal, e token
expirado/revogado/de escopo errado é recusado.
"""
import os
import sys
import uuid
from datetime import date, datetime, timedelta

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import (
    Cliente, EscopoPortal, MapaConcorrenciaV2, Obra, PedidoCompra,
    PortalEvento, TipoUsuario, Usuario,
)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase9-rotas'
    yield


def _cenario(escopos=(EscopoPortal.LER,), dias=90, uso_unico=False):
    """Cria admin + obra + compra pendente + token, devolve (token, ids)."""
    from utils.portal_acesso import emitir_acesso

    suf = uuid.uuid4().hex[:8]
    admin = Usuario(
        username=f'f9r_{suf}', email=f'f9r_{suf}@test.local',
        nome=f'Admin {suf}', password_hash=generate_password_hash('x'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(admin)
    db.session.commit()

    cliente = Cliente(nome=f'Cliente {suf}', email=f'c_{suf}@test.local',
                      admin_id=admin.id)
    db.session.add(cliente)
    db.session.commit()

    obra = Obra(nome=f'Obra {suf}', codigo=f'O{suf[:6].upper()}',
                data_inicio=date(2026, 1, 1), admin_id=admin.id,
                cliente_id=cliente.id, ativo=True, portal_ativo=True,
                valor_contrato=100000.0)
    db.session.add(obra)
    db.session.commit()

    compra = PedidoCompra(
        obra_id=obra.id, admin_id=admin.id,
        tipo_compra='aprovacao_cliente',
        status_aprovacao_cliente='AGUARDANDO_APROVACAO_CLIENTE',
    )
    db.session.add(compra)
    db.session.commit()

    token, acesso = emitir_acesso(obra=obra, admin_id=admin.id,
                                  escopos=list(escopos), dias_validade=dias,
                                  uso_unico=uso_unico)
    db.session.commit()
    return token, {'admin_id': admin.id, 'obra_id': obra.id,
                   'compra_id': compra.id, 'acesso_id': acesso.id}


def test_get_portal_exige_escopo_ler():
    with app.app_context():
        token, _ = _cenario(escopos=[EscopoPortal.LER])
    r = app.test_client().get(f'/portal/obra/{token}')
    assert r.status_code == 200


def test_get_portal_recusa_token_desconhecido():
    r = app.test_client().get('/portal/obra/nao-existe-token-nenhum-aqui')
    assert r.status_code == 404


def test_get_portal_recusa_token_expirado_com_410():
    from models import PortalAcesso
    with app.app_context():
        token, ids = _cenario(escopos=[EscopoPortal.LER])
        acesso = db.session.get(PortalAcesso, ids['acesso_id'])
        acesso.expira_em = datetime.utcnow() - timedelta(seconds=1)
        db.session.commit()
    r = app.test_client().get(f'/portal/obra/{token}')
    assert r.status_code == 410, (
        'link expirado deve devolver 410 Gone com página explicativa, '
        'não 200 nem 500')


@pytest.mark.parametrize('caminho,escopo_necessario', [
    ('/portal/obra/{t}/compra/{c}/aprovar', EscopoPortal.APROVAR_COMPRA),
    ('/portal/obra/{t}/compra/{c}/recusar', EscopoPortal.APROVAR_COMPRA),
    ('/portal/obra/{t}/compra/{c}/comprovante', EscopoPortal.ENVIAR_COMPROVANTE),
])
def test_post_de_compra_recusa_token_so_de_leitura(caminho, escopo_necessario):
    """O achado central da Fase 9a: um link de leitura não aprova compra."""
    with app.app_context():
        token, ids = _cenario(escopos=[EscopoPortal.LER])
    r = app.test_client().post(
        caminho.format(t=token, c=ids['compra_id']))
    assert r.status_code == 403, (
        f'rota {caminho} aceitou token sem {escopo_necessario.value}')

    with app.app_context():
        compra = db.session.get(PedidoCompra, ids['compra_id'])
        assert compra.status_aprovacao_cliente == 'AGUARDANDO_APROVACAO_CLIENTE'


def test_aprovar_compra_funciona_com_o_escopo_certo():
    with app.app_context():
        token, ids = _cenario(
            escopos=[EscopoPortal.LER, EscopoPortal.APROVAR_COMPRA])
    r = app.test_client().post(
        f'/portal/obra/{token}/compra/{ids["compra_id"]}/aprovar',
        follow_redirects=False)
    assert r.status_code in (302, 303)
    with app.app_context():
        compra = db.session.get(PedidoCompra, ids['compra_id'])
        assert compra.status_aprovacao_cliente == 'APROVADO'


def test_aprovar_compra_registra_evento_com_ip():
    with app.app_context():
        token, ids = _cenario(
            escopos=[EscopoPortal.LER, EscopoPortal.APROVAR_COMPRA])
    app.test_client().post(
        f'/portal/obra/{token}/compra/{ids["compra_id"]}/aprovar',
        environ_base={'REMOTE_ADDR': '203.0.113.7'})
    with app.app_context():
        ev = (PortalEvento.query
              .filter_by(acesso_id=ids['acesso_id'], acao='aprovar_compra')
              .order_by(PortalEvento.id.desc()).first())
        assert ev is not None, 'aprovação de compra não deixou trilha'
        assert ev.resultado == 'ok'
        assert ev.ip == '203.0.113.7'
        assert ev.alvo_tipo == 'pedido_compra'
        assert ev.alvo_id == ids['compra_id']


def test_negativa_tambem_deixa_trilha():
    with app.app_context():
        token, ids = _cenario(escopos=[EscopoPortal.LER])
    app.test_client().post(
        f'/portal/obra/{token}/compra/{ids["compra_id"]}/aprovar')
    with app.app_context():
        ev = (PortalEvento.query
              .filter_by(acesso_id=ids['acesso_id'], resultado='negado')
              .order_by(PortalEvento.id.desc()).first())
        assert ev is not None
        assert ev.motivo == 'escopo'


def test_pdf_de_medicao_nao_aceita_mais_token_por_querystring():
    """medicao_views.py:514 lia request.args.get('token') — a querystring
    entra no access log do gunicorn (Dockerfile:97-99), no histórico do
    navegador e no header Referer."""
    with app.app_context():
        token, ids = _cenario(escopos=[EscopoPortal.LER])
    r = app.test_client().get(
        f'/medicao/portal/pdf/1?token={token}')
    assert r.status_code in (403, 404, 405), (
        'a rota antiga com token na querystring ainda responde')


def test_rotas_do_portal_nao_voltam_a_ler_token_direto():
    """Trava de regressão: o resolver é o único caminho."""
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for arquivo in ('portal_obras_views.py', 'medicao_views.py'):
        with open(os.path.join(raiz, arquivo), encoding='utf-8') as fh:
            conteudo = fh.read()
        assert 'filter_by(token_cliente=' not in conteudo, (
            f'{arquivo} voltou a resolver token na mão, fora de '
            'utils/portal_acesso.resolver_acesso')


def test_admin_id_10_chumbado_nao_volta():
    """propostas_consolidated.py:2469 servia o branding do tenant 10 a
    clientes de outra empresa quando o admin_id não resolvia."""
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(raiz, 'propostas_consolidated.py'),
              encoding='utf-8') as fh:
        linhas = fh.readlines()
    for i, linha in enumerate(linhas, start=1):
        codigo = linha.split('#')[0]
        assert 'admin_id = 10' not in codigo, (
            f'propostas_consolidated.py:{i} voltou a chumbar o tenant 10')
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase9_portal_rotas.py -v
```

Esperado: FAIL. `test_post_de_compra_recusa_token_so_de_leitura` devolve 302 em vez de 403 (a compra é aprovada!); `test_get_portal_recusa_token_expirado_com_410` devolve 404; `test_admin_id_10_chumbado_nao_volta` falha na linha 2469.

- [ ] **Step 3: Acrescente o decorator a `utils/portal_acesso.py`**

Ao final do arquivo:

```python
_MOTIVO_STATUS = {
    'inexistente': 404,     # não confirma nem nega que o token existiu
    'expirado': 410,        # Gone — quem já tem o link merece saber por quê
    'revogado': 410,
    'consumido': 410,
    'portal_inativo': 410,
}


def portal_token_required(escopo, param='token'):
    """Único portão do portal do cliente — Fase 9a.

    Substitui `_get_obra_by_token` (portal_obras_views.py:49) e
    `_resolve_obra_for_view` (portal_obras_views.py:58), que faziam uma
    query e nada mais.

    Coloca em `g` o `PortalAcesso` (`portal_acesso`) e o alvo já
    carregado (`portal_obra` ou `portal_proposta`), para a view não
    refazer a query.

    Status devolvidos:
      * 404 — token desconhecido (não vaza existência)
      * 410 — expirado, revogado, consumido, ou portal desativado
      * 403 — token válido, escopo insuficiente
    """
    def decorador(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            token = kwargs.get(param) or ''
            acesso, motivo = resolver_acesso(token)

            if acesso is None:
                registrar_evento(acesso=None, acao=f.__name__,
                                 resultado='negado', motivo=motivo, token=token)
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                status = _MOTIVO_STATUS.get(motivo, 404)
                if status == 404:
                    abort(404)
                return render_template('portal/portal_link_invalido.html',
                                       motivo=motivo), 410

            if not tem_escopo(acesso, escopo):
                registrar_evento(acesso=acesso, acao=f.__name__,
                                 resultado='negado', motivo='escopo')
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                abort(403)

            g.portal_acesso = acesso
            g.portal_obra = (db.session.get(Obra, acesso.obra_id)
                             if acesso.obra_id else None)
            if acesso.proposta_id:
                from models import Proposta
                g.portal_proposta = db.session.get(Proposta, acesso.proposta_id)
            else:
                g.portal_proposta = None

            marcar_uso(acesso)
            return f(*args, **kwargs)
        return wrapper
    return decorador
```

- [ ] **Step 4: Crie `templates/portal/portal_link_invalido.html`**

```html
{% extends 'portal/_base.html' %}
{% block portal_content %}
<div class="card-portal" style="max-width:560px;margin:6rem auto;text-align:center;padding:2.5rem">
  <i class="fas fa-link-slash" style="font-size:2.5rem;color:#b0b7c3"></i>
  <h1 style="font-size:1.35rem;margin:1.25rem 0 .5rem">Este link não está mais válido</h1>
  <p style="color:#5a6473;line-height:1.6">
    {% if motivo == 'expirado' %}
      O prazo de validade deste link terminou.
    {% elif motivo == 'revogado' %}
      Este link foi cancelado pela construtora.
    {% elif motivo == 'consumido' %}
      Este link era de uso único e já foi utilizado.
    {% else %}
      O acompanhamento desta obra está temporariamente indisponível.
    {% endif %}
    Peça um link novo para a construtora — leva um minuto.
  </p>
</div>
{% endblock %}
```

- [ ] **Step 5: Reescreva os helpers de `portal_obras_views.py`**

Substitua o bloco `portal_obras_views.py:49-76` (as duas funções `_get_obra_by_token` e `_resolve_obra_for_view`) por:

```python
# Fase 9a — os dois helpers antigos eram a autorização inteira do portal:
#
#   _get_obra_by_token:  Obra.query.filter_by(token_cliente=token,
#                            portal_ativo=True).first() or abort(404)
#   _resolve_obra_for_view: idem + página de portal inativo
#
# Sem validade, sem escopo, sem revogação, sem trilha. Agora quem decide
# é `utils.portal_acesso.portal_token_required`; a obra do request já
# vem carregada em `g.portal_obra`.
def _obra_do_request() -> Obra:
    """A Obra do token corrente. Só é chamada dentro de rota decorada."""
    obra = getattr(g, 'portal_obra', None)
    if obra is None:
        abort(404)
    return obra


def _render_inativo(obra):
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=obra.admin_id).first()
    return render_template(
        'portal/portal_inativo.html', obra=obra, config_empresa=config,
        nome_empresa=config.nome_empresa if config else 'Construtora',
    )
```

Acrescente aos imports do topo do arquivo (junto do `from flask import ...` em `portal_obras_views.py:15-18`):

```python
from flask import g
from app import limiter
from models import EscopoPortal
from utils.portal_acesso import (
    acesso_corrente, portal_token_required, registrar_evento,
)
```

- [ ] **Step 6: Aplique o decorator às 8 rotas de `portal_obras_views.py`**

Em cada rota, acrescente o decorator abaixo do `@portal_obras_bp.route(...)` e troque a primeira linha do corpo. As oito, com a linha atual de cada uma:

```python
# portal_obras_views.py:79 — GET do portal
@portal_obras_bp.route('/obra/<token>')
@limiter.limit("120 per hour")
@portal_token_required(EscopoPortal.LER)
def portal_obra(token: str):
    obra = _obra_do_request()
    registrar_evento(acesso=acesso_corrente(), acao='ver_portal', resultado='ok')
    # (o restante do corpo, a partir de `obra.ultima_visualizacao_cliente = ...`
    #  na linha 85, fica igual; apague apenas as 3 linhas 81-83 que chamavam
    #  `_resolve_obra_for_view`)
```

```python
# portal_obras_views.py:343 — aprovar compra
@portal_obras_bp.route('/obra/<token>/compra/<int:compra_id>/aprovar', methods=['POST'])
@limiter.limit("20 per hour")
@portal_token_required(EscopoPortal.APROVAR_COMPRA)
def aprovar_compra(token: str, compra_id: int):
    obra = _obra_do_request()
```

```python
# portal_obras_views.py:377 — recusar compra
@portal_obras_bp.route('/obra/<token>/compra/<int:compra_id>/recusar', methods=['POST'])
@limiter.limit("20 per hour")
@portal_token_required(EscopoPortal.APROVAR_COMPRA)
def recusar_compra(token: str, compra_id: int):
    obra = _obra_do_request()
```

```python
# portal_obras_views.py:388 — upload de comprovante
@portal_obras_bp.route('/obra/<token>/compra/<int:compra_id>/comprovante', methods=['POST'])
@limiter.limit("20 per hour")
@portal_token_required(EscopoPortal.ENVIAR_COMPROVANTE)
def upload_comprovante(token: str, compra_id: int):
    obra = _obra_do_request()
```

```python
# portal_obras_views.py:432 — aprovar mapa V1
@portal_obras_bp.route('/obra/<token>/mapa/<int:mapa_id>/aprovar', methods=['POST'])
@limiter.limit("20 per hour")
@portal_token_required(EscopoPortal.SELECIONAR_MAPA)
def aprovar_mapa_concorrencia(token: str, mapa_id: int):
    obra = _obra_do_request()
```

```python
# portal_obras_views.py:546 — selecionar mapa V2
@portal_obras_bp.route('/obra/<token>/mapa-v2/<int:mapa_id>/selecionar', methods=['POST'])
@limiter.limit("20 per hour")
@portal_token_required(EscopoPortal.SELECIONAR_MAPA)
def selecionar_mapa_v2(token: str, mapa_id: int):
    obra = _obra_do_request()
```

```python
# portal_obras_views.py:618 — baixar relatório do mapa
@portal_obras_bp.route('/obra/<token>/mapa-v2/<int:mapa_id>/relatorio/<int:rel_id>/baixar')
@limiter.limit("120 per hour")
@portal_token_required(EscopoPortal.LER)
def baixar_relatorio_mapa_v2_portal(token: str, mapa_id: int, rel_id: int):
    obra = _obra_do_request()
```

```python
# portal_obras_views.py:638 — detalhe de RDO
@portal_obras_bp.route('/obra/<token>/rdo/<int:rdo_id>')
@limiter.limit("120 per hour")
@portal_token_required(EscopoPortal.LER)
def portal_rdo_detalhe(token: str, rdo_id: int):
    obra = _obra_do_request()
    admin_id = obra.admin_id
```

Nas cinco rotas POST, acrescente a linha de trilha imediatamente **antes** do `db.session.commit()` de sucesso (em `aprovar_compra` é a linha 363; em `recusar_compra`, 382; em `upload_comprovante`, 426; em `aprovar_mapa_concorrencia`, 460; em `selecionar_mapa_v2`, 604):

```python
        registrar_evento(acesso=acesso_corrente(), acao='aprovar_compra',
                         resultado='ok', alvo_tipo='pedido_compra',
                         alvo_id=compra_id)
```

(trocando `acao` e `alvo_tipo`/`alvo_id` conforme a rota: `recusar_compra`/`pedido_compra`, `enviar_comprovante`/`pedido_compra`, `aprovar_mapa`/`mapa_concorrencia`, `selecionar_mapa_v2`/`mapa_concorrencia_v2`.)

Em `portal_obra` (linha 323), passe o token ao contexto do template — hoje o template monta os links com `obra.token_cliente`, que a Task 8 vai zerar:

```python
    return render_template(
        'portal/portal_obra.html',
        obra=obra,
        token=token,          # Fase 9a — o template não lê mais obra.token_cliente
        tarefas=tarefas,
```

- [ ] **Step 7: Troque `obra.token_cliente` pelos `token` nos três templates vivos**

`templates/portal/_portal_medicoes.html:29` — e note que a URL do PDF muda de querystring para path (Step 8):

```html
                        <a href="{{ url_for('medicao.portal_pdf_extrato', token=token, medicao_id=m.id) }}"
```

`templates/portal/_portal_mapas_v2.html:29` e `:259`, `templates/portal/_portal_rdos.html:13` — trocar `token=obra.token_cliente` por `token=token`.

`templates/portal/portal_rdo_detalhe.html` já recebe `token` do contexto (`portal_obras_views.py:724`) — nada a fazer.

> `templates/portal/_partials/_medicoes.html` e `_partials/_rdos.html` são cópias mortas: `portal_obra.html:6-19` não as inclui. **Apague o diretório `templates/portal/_partials/`** neste passo, em vez de mantê-lo divergindo.

- [ ] **Step 8: Reescreva `medicao_views.py:512-521` — token no path, não na querystring**

Substitua o bloco inteiro por:

```python
# Fase 9a — o token saiu da QUERYSTRING. `request.args.get('token')`
# (linha 514 até 2026-07-21) colocava a credencial no access log do
# gunicorn (Dockerfile:97-99), no histórico do navegador e no header
# Referer. No path ele continua sendo logado, mas a Task 6 passa a
# mascará-lo em `utils/auditoria_acesso.py`; na querystring não havia
# como mascarar sem reescrever o formato do access log do gunicorn.
@medicao_bp.route('/medicao/portal/<token>/pdf/<int:medicao_id>')
@limiter.limit("60 per hour")
@portal_token_required(EscopoPortal.LER)
def portal_pdf_extrato(token, medicao_id):
    from flask import g
    obra = g.portal_obra
    medicao = MedicaoObra.query.filter_by(id=medicao_id, obra_id=obra.id).first()
    if not medicao:
        abort(404)

    registrar_evento(acesso=acesso_corrente(), acao='baixar_pdf_medicao',
                     resultado='ok', alvo_tipo='medicao_obra',
                     alvo_id=medicao.id)
    db.session.commit()

    from services.medicao_service import gerar_pdf_extrato_medicao
    buf = gerar_pdf_extrato_medicao(medicao_id, medicao.admin_id)
    if not buf:
        abort(404)

    response = make_response(buf.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=medicao_{medicao_id:03d}.pdf'
    return response
```

Acrescente ao topo de `medicao_views.py`:

```python
from app import limiter
from models import EscopoPortal
from utils.portal_acesso import acesso_corrente, portal_token_required, registrar_evento
```

- [ ] **Step 9: Aplique às 3 rotas do portal da proposta e mate o `admin_id = 10`**

Em `propostas_consolidated.py`, `portal_cliente` (`:2453-2454`):

```python
@propostas_bp.route('/cliente/<token>')
@limiter.limit("120 per hour")
@portal_token_required(EscopoPortal.LER)
def portal_cliente(token):
    """Portal para o cliente visualizar e aprovar proposta"""
    from flask import g
    proposta = g.portal_proposta
    if proposta is None:
        abort(404)

    # Fase 9a — o admin_id vem do PortalAcesso, que é criado com o
    # tenant do objeto. Até 2026-07-21 este bloco tentava três fontes e,
    # falhando todas, fazia `admin_id = 10` (linha 2469): o cliente de
    # uma empresa recebia a configuração e o branding da empresa 10.
    admin_id = acesso_corrente().admin_id
```

Apague as linhas 2456-2469 (o `first_or_404`, a cascata de resolução e o `admin_id = 10`). O resto do corpo (`config_empresa = safe_db_operation(...)` em diante) fica igual.

Em `aprovar_proposta_cliente` (`:2503-2504`):

```python
@propostas_bp.route('/cliente/<token>/aprovar', methods=['POST'])
@limiter.limit("10 per hour")
@portal_token_required(EscopoPortal.APROVAR_PROPOSTA)
def aprovar_proposta_cliente(token):
    """Cliente aprova a proposta — Task #94: emite evento proposta_aprovada."""
    from flask import g
    proposta = g.portal_proposta
    if proposta is None:
        abort(404)
```

E, dentro do `try`, substitua o bloco de resolução de `admin_id` (linhas 2515-2521) por:

```python
        admin_id = acesso_corrente().admin_id
```

Imediatamente antes do `db.session.commit()` de sucesso (linha 2559):

```python
        registrar_evento(acesso=acesso_corrente(), acao='aprovar_proposta',
                         resultado='ok', alvo_tipo='proposta',
                         alvo_id=proposta.id)
```

Em `rejeitar_proposta_cliente` (`:2587-2588`), o mesmo tratamento com
`@portal_token_required(EscopoPortal.APROVAR_PROPOSTA)`, `acao='rejeitar_proposta'`, e o bloco de resolução de `admin_id` das linhas 2603-2610 trocado por `admin_id = acesso_corrente().admin_id`.

Acrescente ao topo de `propostas_consolidated.py`:

```python
from app import limiter
from models import EscopoPortal
from utils.portal_acesso import acesso_corrente, portal_token_required, registrar_evento
```

- [ ] **Step 10: Rode os testes**

```bash
python -m pytest tests/test_fase9_portal_rotas.py tests/test_fase9_portal_acesso.py -v
python -m pytest tests/ -m "not browser" -k "proposta or medicao" -q
```

Esperado: os testes da Fase 9 verdes; a segunda linha sem falha nova em relação à baseline anotada antes de começar.

- [ ] **Step 11: Commit**

```bash
git add utils/portal_acesso.py portal_obras_views.py propostas_consolidated.py \
        medicao_views.py templates/portal/ tests/test_fase9_portal_rotas.py
git rm -r templates/portal/_partials
git commit -m "fix(sec,fase9a): as 11 rotas do portal passam a exigir escopo

As sete POSTs que mutavam estado com nada alem da URL agora exigem
escopo nominal: aprovar_compra, enviar_comprovante, selecionar_mapa,
aprovar_proposta. Token de leitura nao aprova mais compra — travado por
teste. Expirado/revogado devolve 410 com pagina explicativa. Toda
passagem, concedida ou negada, vira linha em portal_evento com IP.

Remove o admin_id = 10 chumbado de propostas_consolidated.py:2469.
Tira o token da querystring do PDF de medicao. Apaga
templates/portal/_partials (copias mortas, nao incluidas por
portal_obra.html)."
```

---

## Task 6: Parar de vazar o token nos logs + `Referrer-Policy`

**Files:**
- Modify: `utils/auditoria_acesso.py:29` e `:66-73`
- Modify: `main.py` (after_request do portal)
- Test: `tests/test_fase9_portal_rotas.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente ao final de `tests/test_fase9_portal_rotas.py`:

```python
# ---------------------------------------------------------------------------
# Vazamento em log e Referer
# ---------------------------------------------------------------------------

def test_token_nao_aparece_no_log_de_auditoria(caplog):
    """utils/auditoria_acesso.py:66-79 logava `path=` de todo POST, e o
    path do portal carrega o token. Como o portal é anônimo, cada
    aprovação de compra saía em WARNING com a credencial em claro."""
    import logging

    with app.app_context():
        token, ids = _cenario(
            escopos=[EscopoPortal.LER, EscopoPortal.APROVAR_COMPRA])

    with caplog.at_level(logging.INFO, logger='sige.acesso'):
        app.test_client().post(
            f'/portal/obra/{token}/compra/{ids["compra_id"]}/aprovar')

    texto = '\n'.join(r.getMessage() for r in caplog.records)
    assert token not in texto, 'o token do portal foi para o log de auditoria'
    assert '/portal/obra/' in texto, 'a auditoria parou de registrar o portal'


def test_resposta_do_portal_traz_referrer_policy():
    """A página carrega CSS/JS de cdn.jsdelivr.net e cdnjs.cloudflare.com
    (templates/portal/_base.html:7,8,448) e o app não define
    Referrer-Policy em lugar nenhum."""
    with app.app_context():
        token, _ = _cenario(escopos=[EscopoPortal.LER])
    r = app.test_client().get(f'/portal/obra/{token}')
    assert r.headers.get('Referrer-Policy') == 'no-referrer'
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase9_portal_rotas.py -v -k "log_de_auditoria or referrer"
```

Esperado: FAIL — o token aparece no log; não há header `Referrer-Policy`.

- [ ] **Step 3: Mascare o token em `utils/auditoria_acesso.py`**

Substitua a linha 29 e acrescente a função de máscara:

```python
# Rotas cujo path pode carregar informação sensível — marcadas no log.
_PATHS_SENSIVEIS = ('/login', '/alterar-senha', '/usuarios')

# Fase 9a — prefixos cujo path carrega um capability token do portal.
# `/portal/obra/<token>/compra/12/aprovar` era logado inteiro, em
# WARNING (porque o portal é anônimo), a cada aprovação de compra.
_PATHS_COM_TOKEN = ('/portal/obra/', '/propostas/cliente/', '/medicao/portal/')
_TOKEN_VISIVEL = 8


def _mascarar_token(path: str) -> str:
    """Reduz o segmento de token a `<prefixo>…` — o suficiente para
    correlacionar com `portal_evento.token_prefixo` sem publicar a
    credencial no agregador de logs."""
    for prefixo in _PATHS_COM_TOKEN:
        if not path.startswith(prefixo):
            continue
        resto = path[len(prefixo):]
        partes = resto.split('/', 1)
        token = partes[0]
        if len(token) <= _TOKEN_VISIVEL:
            return path
        mascarado = token[:_TOKEN_VISIVEL] + '…'
        cauda = f'/{partes[1]}' if len(partes) > 1 else ''
        return f'{prefixo}{mascarado}{cauda}'
    return path
```

E, dentro de `_registrar_escrita`, substitua o bloco das linhas 68-71:

```python
            path = _mascarar_token(request.path)
            if any(path.startswith(p) for p in _PATHS_SENSIVEIS):
                path = f'{path} [sensível]'
```

- [ ] **Step 4: Acrescente o `after_request` do portal em `main.py`**

Logo após o bloco de `csrf.exempt` do portal (`main.py:222-231`):

```python
# Fase 9a — o path do portal É a credencial. `Referrer-Policy:
# no-referrer` impede que ele saia no header Referer de qualquer
# requisição disparada pela página (a página carrega Bootstrap e Font
# Awesome de CDN — templates/portal/_base.html:7,8,448). Navegador
# moderno já usa strict-origin-when-cross-origin por padrão, mas o app
# não declarava nada: zero ocorrências de Referrer-Policy no repo.
#
# `Cache-Control: no-store` impede que um proxy compartilhado ou o
# cache do navegador guarde a página de uma obra atrás de uma URL que
# vale como senha.
_PREFIXOS_PORTAL = ('/portal/obra/', '/propostas/cliente/', '/medicao/portal/')


@app.after_request
def _headers_do_portal(response):
    try:
        from flask import request
        if request.path.startswith(_PREFIXOS_PORTAL):
            response.headers['Referrer-Policy'] = 'no-referrer'
            response.headers['Cache-Control'] = 'no-store, private'
            response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    except Exception:
        pass
    return response
```

- [ ] **Step 5: Rode os testes**

```bash
python -m pytest tests/test_fase9_portal_rotas.py -v
```

Esperado: todos PASSAM.

- [ ] **Step 6: Commit**

```bash
git add utils/auditoria_acesso.py main.py tests/test_fase9_portal_rotas.py
git commit -m "fix(sec,fase9a): token do portal para de vazar em log e Referer

utils/auditoria_acesso.py mascara o segmento de token do path (mantem 8
chars, o mesmo prefixo de portal_evento, para correlacionar). Respostas
do portal ganham Referrer-Policy: no-referrer, Cache-Control: no-store
e X-Robots-Tag: noindex — o app nao definia nenhum desses headers."
```

---

## Task 7: Emissão e revogação pela tela do tenant

**Files:**
- Modify: `portal_obras_views.py:471-487` (`toggle_portal`) + 2 rotas novas
- Modify: `views/obras.py:370-375` e `:947-949` (parar de gerar token)
- Modify: `event_manager.py:1051-1053` (idem)
- Modify: `templates/obras/detalhes_obra_profissional.html:1475-1502`
- Modify: `templates/compras/aprovacao.html:97-98`, `templates/propostas/lista_propostas.html:89-90`, `templates/propostas/detalhes_proposta.html:425-429,504-519`
- Test: `tests/test_fase9_portal_rotas.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

```python
# ---------------------------------------------------------------------------
# Emissão pelo tenant
# ---------------------------------------------------------------------------

def _cliente_logado(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


def test_emitir_link_exige_login():
    with app.app_context():
        _, ids = _cenario()
    r = app.test_client().post(f'/portal/obra/{ids["obra_id"]}/acesso/emitir')
    assert r.status_code in (302, 401, 403), 'rota de emissão está anônima'


def test_emitir_link_mostra_o_token_uma_vez_e_grava_o_hash():
    from models import PortalAcesso
    with app.app_context():
        _, ids = _cenario()
        antes = PortalAcesso.query.filter_by(obra_id=ids['obra_id']).count()

    c = _cliente_logado(ids['admin_id'])
    r = c.post(f'/portal/obra/{ids["obra_id"]}/acesso/emitir',
               data={'nome': 'Novo Cliente', 'email': 'novo@test.local',
                     'escopos': 'ler', 'dias': '90'},
               follow_redirects=True)
    assert r.status_code == 200
    corpo = r.get_data(as_text=True)
    assert '/portal/obra/' in corpo, 'a tela não exibiu o link emitido'

    with app.app_context():
        depois = PortalAcesso.query.filter_by(obra_id=ids['obra_id']).count()
        assert depois == antes + 1


def test_emitir_link_recusa_obra_de_outro_tenant():
    with app.app_context():
        _, ids_a = _cenario()
        _, ids_b = _cenario()
    c = _cliente_logado(ids_a['admin_id'])
    r = c.post(f'/portal/obra/{ids_b["obra_id"]}/acesso/emitir',
               data={'nome': 'X', 'escopos': 'ler', 'dias': '90'})
    assert r.status_code == 404, 'emissão atravessou tenant'


def test_revogar_derruba_so_o_acesso_alvo():
    from models import PortalAcesso
    from utils.portal_acesso import emitir_acesso, resolver_acesso

    with app.app_context():
        token_a, ids = _cenario(escopos=[EscopoPortal.LER])
        obra = db.session.get(Obra, ids['obra_id'])
        token_b, acesso_b = emitir_acesso(
            obra=obra, admin_id=ids['admin_id'],
            escopos=[EscopoPortal.LER], dias_validade=90,
            destinatario_nome='Sócio')
        db.session.commit()
        acesso_b_id = acesso_b.id

    c = _cliente_logado(ids['admin_id'])
    c.post(f'/portal/acesso/{acesso_b_id}/revogar', data={'motivo': 'saiu'})

    with app.app_context():
        assert resolver_acesso(token_b)[1] == 'revogado'
        assert resolver_acesso(token_a)[1] is None, (
            'revogar um acesso derrubou os outros da mesma obra')


def test_criar_obra_nao_gera_mais_token_cliente():
    """views/obras.py:375, :949 e event_manager.py:1053 geravam
    secrets.token_urlsafe(32) direto na coluna. A emissão passa a ser
    explícita e auditada."""
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for arquivo in ('views/obras.py', 'event_manager.py'):
        with open(os.path.join(raiz, arquivo), encoding='utf-8') as fh:
            for i, linha in enumerate(fh, start=1):
                codigo = linha.split('#')[0]
                assert 'token_cliente = secrets.token_urlsafe' not in codigo, (
                    f'{arquivo}:{i} ainda gera token_cliente direto')
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase9_portal_rotas.py -v -k "emitir or revogar or criar_obra"
```

Esperado: 404 nas rotas novas; `test_criar_obra_nao_gera_mais_token_cliente` falha nos três arquivos.

- [ ] **Step 3: Acrescente as duas rotas em `portal_obras_views.py`**

Após `toggle_portal` (`:471-487`):

```python
@portal_obras_bp.route('/obra/<int:obra_id>/acesso/emitir', methods=['POST'])
@login_required
def emitir_acesso_portal(obra_id: int):
    """Emite um capability token para um destinatário nomeado.

    Fase 9a — antes, o token nascia sozinho em quatro lugares
    (views/obras.py:375 e :949, event_manager.py:1053,
    portal_obras_views.py:481), sem registrar quem emitiu, para quem,
    com que poder nem até quando. A partir daqui a emissão é um ato:
    tem autor, destinatário, escopo e prazo.

    O token em claro aparece UMA vez, no flash. Não há como reexibi-lo —
    a tabela guarda só o SHA-256. Para reenviar, reemita.
    """
    from utils.tenant import get_tenant_admin_id
    from utils.portal_acesso import emitir_acesso

    admin_id = get_tenant_admin_id()
    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()

    escopos_txt = request.form.get('escopos', 'ler')
    try:
        escopos = [EscopoPortal(e.strip()) for e in escopos_txt.split(',') if e.strip()]
    except ValueError:
        flash('Escopo inválido.', 'danger')
        return redirect(url_for('main.detalhes_obra', id=obra_id))

    # Assinatura NUNCA sai por esta rota: ela tem caminho próprio, com
    # token de uso único vinculado a uma medição (Task 11).
    if EscopoPortal.ASSINAR_MEDICAO in escopos:
        flash('Assinatura de medição usa link próprio, emitido na medição.',
              'warning')
        return redirect(url_for('main.detalhes_obra', id=obra_id))

    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    dias_padrao = config.portal_token_dias_validade if config else 90
    dias = request.form.get('dias', type=int)
    dias = dias_padrao if dias is None else dias

    token, acesso = emitir_acesso(
        obra=obra, admin_id=admin_id, escopos=escopos, dias_validade=dias,
        destinatario_nome=(request.form.get('nome') or '').strip() or None,
        destinatario_email=(request.form.get('email') or '').strip() or None,
        criado_por_usuario_id=current_user.id,
    )
    if not obra.portal_ativo:
        obra.portal_ativo = True
    registrar_evento(acesso=acesso, acao='emitir_acesso', resultado='ok',
                     admin_id=admin_id)
    db.session.commit()

    url = url_for('portal_obras.portal_obra', token=token, _external=True)
    logger.info("[PORTAL] acesso %s emitido para obra %s por usuario %s "
                "(escopos=%s, dias=%s)",
                acesso.token_prefixo, obra_id, current_user.id,
                acesso.escopos, dias)
    flash(f'Link gerado — copie agora, ele não será exibido novamente: {url}',
          'success')
    return redirect(url_for('main.detalhes_obra', id=obra_id))


@portal_obras_bp.route('/acesso/<int:acesso_id>/revogar', methods=['POST'])
@login_required
def revogar_acesso_portal(acesso_id: int):
    """Revoga um acesso sem derrubar os demais da mesma obra.

    Fase 9a — antes o único controle era `Obra.portal_ativo` (booleano
    por obra, models.py:272): tirar o link de uma pessoa significava
    derrubar todo mundo.
    """
    from utils.tenant import get_tenant_admin_id
    from models import PortalAcesso
    from utils.portal_acesso import revogar_acesso

    admin_id = get_tenant_admin_id()
    acesso = PortalAcesso.query.filter_by(id=acesso_id, admin_id=admin_id).first_or_404()
    revogar_acesso(acesso, motivo=(request.form.get('motivo') or 'revogado na tela'))
    registrar_evento(acesso=acesso, acao='revogar_acesso', resultado='ok',
                     admin_id=admin_id)
    db.session.commit()
    logger.info("[PORTAL] acesso %s revogado por usuario %s",
                acesso.token_prefixo, current_user.id)
    flash('Link revogado.', 'success')
    if acesso.obra_id:
        return redirect(url_for('main.detalhes_obra', id=acesso.obra_id))
    return redirect(url_for('propostas.index'))
```

Acrescente `flash`, `current_user` e `url_for` aos imports do topo (`flash` e `url_for` já estão em `portal_obras_views.py:15-18`; `current_user` entra em `from flask_login import current_user, login_required`, linha 19).

Em `toggle_portal` (`:478-481`), remova a geração automática de token:

```python
    obra.portal_ativo = not obra.portal_ativo
    # Fase 9a — ligar o portal não emite mais credencial. A emissão é
    # ato explícito (rota `emitir_acesso_portal`), com destinatário,
    # escopo, prazo e autor registrados.
```

- [ ] **Step 4: Pare de gerar token nos três outros lugares**

`views/obras.py:370-375` — apague o bloco e a variável `token_cliente` da construção da `Obra`, deixando o comentário:

```python
            # Fase 9a — a obra não nasce mais com credencial de portal.
            # O token era gerado aqui com secrets.token_urlsafe(32) e
            # ficava em claro na coluna, sem prazo e sem escopo. Agora o
            # link é emitido pela rota portal_obras.emitir_acesso_portal,
            # com destinatário, escopo, validade e autor.
```

`views/obras.py:947-949` — apague o bloco `if obra.portal_ativo and ... and not obra.token_cliente:` com o mesmo comentário.

`event_manager.py:1051-1053` — substitua o bloco `# 2) Garantir token_cliente para portal público` por:

```python
    # 2) Fase 9a — a aprovação da proposta não emite mais credencial de
    #    portal automaticamente. Emissão é ato explícito e auditado
    #    (portal_obras.emitir_acesso_portal). Uma obra recém-criada
    #    aparece na tela com "nenhum link ativo" e um botão.
```

- [ ] **Step 5: Reescreva o painel do portal em `templates/obras/detalhes_obra_profissional.html`**

Substitua o bloco `:1475-1502` (que hoje renderiza `{{ request.host_url }}portal/obra/{{ obra.token_cliente }}` num input readonly) por uma listagem de acessos + formulário de emissão:

```html
<div class="card mb-3">
  <div class="card-header d-flex justify-content-between align-items-center">
    <strong><i class="fas fa-link me-1"></i> Links do portal do cliente</strong>
    <span class="badge bg-{{ 'success' if obra.portal_ativo else 'secondary' }}">
      {{ 'Portal ativo' if obra.portal_ativo else 'Portal desativado' }}
    </span>
  </div>
  <div class="card-body">
    {% set acessos = obra.acessos_portal.filter_by(revogado_em=None).all() %}
    {% if acessos %}
    <table class="table table-sm align-middle">
      <thead><tr>
        <th>Destinatário</th><th>Link</th><th>Pode</th><th>Validade</th><th>Último acesso</th><th></th>
      </tr></thead>
      <tbody>
        {% for a in acessos %}
        <tr>
          <td>{{ a.destinatario_nome or '—' }}<br>
              <small class="text-muted">{{ a.destinatario_email or '' }}</small></td>
          <td><code>{{ a.token_prefixo }}…</code></td>
          <td><small>{{ a.escopos.replace(',', ', ') }}</small></td>
          <td>{% if a.expira_em %}{{ a.expira_em.strftime('%d/%m/%Y') }}
              {% else %}<span class="text-warning">sem prazo</span>{% endif %}</td>
          <td>{% if a.ultimo_uso_em %}{{ a.ultimo_uso_em.strftime('%d/%m/%Y %H:%M') }}
              <br><small class="text-muted">{{ a.ultimo_uso_ip or '' }}</small>
              {% else %}<span class="text-muted">nunca</span>{% endif %}</td>
          <td>
            <form method="POST" action="{{ url_for('portal_obras.revogar_acesso_portal', acesso_id=a.id) }}">
              <button class="btn btn-sm btn-outline-danger"
                      onclick="return confirm('Revogar este link? Quem o tiver perde o acesso imediatamente.')">
                Revogar</button>
            </form>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <p class="text-muted mb-3">Nenhum link ativo. O cliente ainda não tem acesso a esta obra.</p>
    {% endif %}

    <form method="POST" action="{{ url_for('portal_obras.emitir_acesso_portal', obra_id=obra.id) }}"
          class="row g-2 align-items-end border-top pt-3">
      <div class="col-md-3"><label class="form-label small">Nome do destinatário</label>
        <input name="nome" class="form-control form-control-sm" required></div>
      <div class="col-md-3"><label class="form-label small">E-mail</label>
        <input name="email" type="email" class="form-control form-control-sm"></div>
      <div class="col-md-3"><label class="form-label small">Pode</label>
        <select name="escopos" class="form-select form-select-sm">
          <option value="ler">Só acompanhar (leitura)</option>
          <option value="ler,aprovar_compra,enviar_comprovante">Acompanhar e aprovar compras</option>
          <option value="ler,aprovar_compra,enviar_comprovante,selecionar_mapa">Acompanhar, aprovar compras e escolher fornecedor</option>
        </select></div>
      <div class="col-md-2"><label class="form-label small">Validade (dias)</label>
        <input name="dias" type="number" min="0" value="90" class="form-control form-control-sm"></div>
      <div class="col-md-1"><button class="btn btn-sm btn-primary w-100">Gerar</button></div>
      <div class="col-12"><small class="text-muted">
        O link aparece uma única vez, depois de gerado. Não é possível reexibi-lo —
        se perder, gere outro e revogue o antigo.</small></div>
    </form>
  </div>
</div>
```

E em `:810-811` troque o link direto por `{% if obra.acessos_portal.filter_by(revogado_em=None).count() %}` + texto, sem expor token.

- [ ] **Step 6: Tire o token dos outros três templates**

- `templates/compras/aprovacao.html:97-98` — o link para o portal do cliente deixa de existir (o usuário interno vê a compra na tela interna). Substitua por um texto simples com o nome da obra.
- `templates/propostas/lista_propostas.html:89-90`, `templates/propostas/detalhes_proposta.html:425-429` e `:504-519` — troque o input com o token por um botão que aponta para uma rota de emissão de acesso de proposta, no mesmo molde da rota de obra.

- [ ] **Step 7: Rode os testes**

```bash
python -m pytest tests/test_fase9_portal_rotas.py tests/test_fase9_portal_acesso.py -v
python -m pytest tests/ -m "not browser" -k "obra or proposta" -q
```

- [ ] **Step 8: Commit**

```bash
git add portal_obras_views.py views/obras.py event_manager.py templates/ \
        tests/test_fase9_portal_rotas.py
git commit -m "feat(fase9a): emissao e revogacao de link do portal viram ato explicito

Nova tela lista os links ativos por destinatario (prefixo, escopo,
validade, ultimo acesso com IP) e permite revogar UM sem derrubar os
outros — antes o unico controle era Obra.portal_ativo, booleano por
obra. O token deixa de nascer sozinho em views/obras.py:375, :949 e
event_manager.py:1053. Templates param de renderizar a credencial."
```

---

## Task 8: Aposentar `Obra.token_cliente` e `Proposta.token_cliente`

**Files:**
- Modify: `migrations.py` (migration **305**)
- Test: `tests/test_fase9_portal_acesso.py` (acrescenta)

> **Nota de numeração:** a 303 está reservada para a tabela `assinatura` (Task 9). Esta task usa a **305**; 9b usa **306** e **307**. Ver o mapa de migrações no fim do documento.

- [ ] **Step 1: Escreva o teste que falha**

```python
def test_coluna_token_cliente_fica_vazia_apos_a_aposentadoria():
    """A credencial não pode continuar em claro no banco depois que o
    hash existe. Um dump de produção com token_cliente preenchido é um
    dump com N credenciais de portal utilizáveis."""
    with app.app_context():
        restantes = db.session.execute(db.text("""
            SELECT COUNT(*) FROM obra
            WHERE token_cliente IS NOT NULL AND token_cliente <> ''
        """)).scalar()
        assert restantes == 0, (
            f'{restantes} obras ainda guardam o token em claro')


def test_nenhum_codigo_vivo_le_token_cliente():
    import subprocess
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    saida = subprocess.run(
        ['grep', '-rn', 'token_cliente', '--include=*.py', '--include=*.html', raiz],
        capture_output=True, text=True).stdout
    permitidos = ('models.py', 'migrations.py', '/archive/', '/tests/',
                  '/scripts/seed_', 'portal_acessos.py')
    ofensores = [l for l in saida.splitlines()
                 if l.strip() and not any(p in l for p in permitidos)]
    assert not ofensores, 'ainda há leitura de token_cliente:\n' + '\n'.join(ofensores)
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase9_portal_acesso.py -v -k "token_cliente"
```

Esperado: FAIL — as colunas continuam preenchidas.

- [ ] **Step 3: Escreva a migration 305 e registre**

```python
def _migration_305_aposentar_token_cliente():
    """Fase 9a — zera obra.token_cliente e proposta.token_cliente.

    A coluna NÃO é dropada: numa base de 178 tabelas com um sistema de
    migração próprio, DROP COLUMN sem janela de rollback é risco
    desnecessário. Zerar já elimina o problema — um dump deixa de
    carregar credencial utilizável — e mantém a porta aberta.

    GUARDA: só zera a linha que já tem um PortalAcesso correspondente
    (criado pela 302). Obra cujo backfill falhou mantém o token e
    aparece no log — perder acesso de cliente calado seria pior.
    """
    logger.info("[Migration 305] Iniciando — aposentadoria de token_cliente")

    orfas = db.session.execute(text("""
        SELECT COUNT(*) FROM obra o
        WHERE o.token_cliente IS NOT NULL AND o.token_cliente <> ''
          AND NOT EXISTS (SELECT 1 FROM portal_acesso pa WHERE pa.obra_id = o.id)
    """)).scalar()
    if orfas:
        logger.warning(
            "[Migration 305] %s obra(s) com token e SEM portal_acesso — "
            "mantidas como estão. Rode "
            "`python scripts/portal_acessos.py backfill --aplicar` e reexecute.",
            orfas)

    r1 = db.session.execute(text("""
        UPDATE obra o SET token_cliente = NULL
        WHERE o.token_cliente IS NOT NULL
          AND EXISTS (SELECT 1 FROM portal_acesso pa WHERE pa.obra_id = o.id)
    """))
    r2 = db.session.execute(text("""
        UPDATE propostas_comerciais p SET token_cliente = NULL
        WHERE p.token_cliente IS NOT NULL
          AND EXISTS (SELECT 1 FROM portal_acesso pa WHERE pa.proposta_id = p.id)
    """))
    db.session.commit()

    logger.info("[Migration 305] %s obras e %s propostas zeradas",
                r1.rowcount, r2.rowcount)
    logger.info("[Migration 305] Concluída com sucesso")
```

Registre após a entrada `302`:

```python
            (305, "Fase 9a — zera obra.token_cliente e proposta.token_cliente (credencial em claro) após o backfill", _migration_305_aposentar_token_cliente),
```

- [ ] **Step 4: Remova a geração automática em `models.py:3059-3060`**

No `__init__` de `Proposta`, substitua:

```python
        # Fase 9a — a proposta não nasce mais com credencial de portal.
        # `secrets.token_urlsafe(32)` gravado em claro aqui era a
        # credencial do portal `/propostas/cliente/<token>`, sem prazo e
        # sem escopo. Emissão passa a ser ato explícito.
```

- [ ] **Step 5: Aplique e rode a suíte inteira**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "305|ERRO|ERROR|WARNING"
bash run_tests.sh --gate 2>&1 | tail -20
```

Esperado: `[Migration 305] Concluída`, nenhum WARNING de órfãs, e a linha final do gate verde. **Cole a linha final no commit.**

- [ ] **Step 6: Commit**

```bash
git add models.py migrations.py tests/test_fase9_portal_acesso.py
git commit -m "fix(sec,fase9a): aposenta token_cliente em claro no banco

Migration 305 zera obra.token_cliente e proposta.token_cliente onde
existe portal_acesso correspondente. A coluna fica (drop sem janela de
rollback e risco desnecessario), mas para de guardar credencial
utilizavel: um dump de producao deixa de valer como molho de chaves.
Obras sem backfill sao preservadas e reportadas em WARNING.

Gate: <cole aqui a linha final de run_tests.sh --gate>"
```

---

> **CHECKPOINT.** As Tasks 1–8 são o pré-requisito. Antes da Task 9, confirme: `bash run_tests.sh --gate` verde, `tests/test_fase9_portal_rotas.py` verde, e a migration 305 sem WARNING de órfãs. Assinar num portal onde um link de leitura aprova compra não produz prova de nada — a Task 14 tem um teste que falha de propósito se este checkpoint for pulado.

## Task 9: Modelo `Assinatura` (genérico, compartilhado com o RDO da Fase 5)

**Files:**
- Modify: `models.py` (modelo após `PortalEvento`)
- Modify: `migrations.py` (migration 303 + registro)
- Test: `tests/test_fase9_assinatura_medicao.py`

- [ ] **Step 1: Verifique se a Fase 5 já criou uma tabela de assinatura**

```bash
grep -n "class RDOAssinatura\|class Assinatura\|rdo_assinatura" models.py migrations.py | head
```

- Se **não houver saída** (situação de 2026-07-21, confirmada): siga o Step 3 como escrito — a tabela nasce genérica e a Fase 5 passa a consumi-la.
- Se houver `class RDOAssinatura`: **não crie uma segunda tabela.** Renomeie-a para `Assinatura`, acrescente as colunas `documento_tipo`, `documento_id`, `snapshot`, `declaracao`, `signatario_documento`, `portal_acesso_id`, e troque o `CREATE TABLE` da migration 303 por `ALTER TABLE rdo_assinatura RENAME TO assinatura` + `ADD COLUMN IF NOT EXISTS` + `UPDATE assinatura SET documento_tipo='rdo', documento_id=rdo_id`. O restante das Tasks 10–14 não muda.

- [ ] **Step 2: Escreva o teste que falha**

Crie `tests/test_fase9_assinatura_medicao.py`:

```python
"""Fase 9a — assinatura de medição pelo cliente no portal.

Até 2026-07-21 não existia assinatura nenhuma no sistema: zero tabelas,
zero colunas, zero serviços (`DEVOLUTIVA.md` §2 transversal:
"Assinatura eletrônica com hash/IP — CONSTRUIR. Nada existe").

O desenho adotado é assinatura eletrônica simples com registro de
autoria (decisão D1 do plano): identificação prévia + aceite explícito
+ SHA-256 do snapshot canônico + carimbo de tempo + IP + user-agent +
trilha append-only. Não é ICP-Brasil e não é provedor externo.
"""
import os
import sys
import uuid
from datetime import date, datetime

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import (
    Assinatura, Cliente, EscopoPortal, MedicaoObra, Obra, TipoUsuario, Usuario,
)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase9-assinatura'
    yield


def _obra_com_medicao(status='APROVADO'):
    suf = uuid.uuid4().hex[:8]
    admin = Usuario(
        username=f'f9s_{suf}', email=f'f9s_{suf}@test.local',
        nome=f'Admin {suf}', password_hash=generate_password_hash('x'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(admin)
    db.session.commit()
    cliente = Cliente(nome=f'Cliente {suf}', email=f'c_{suf}@test.local',
                      cnpj='12.345.678/0001-90', admin_id=admin.id)
    db.session.add(cliente)
    db.session.commit()
    obra = Obra(nome=f'Obra {suf}', codigo=f'O{suf[:6].upper()}',
                data_inicio=date(2026, 1, 1), admin_id=admin.id,
                cliente_id=cliente.id, ativo=True, portal_ativo=True,
                valor_contrato=250000.0)
    db.session.add(obra)
    db.session.commit()
    medicao = MedicaoObra(
        obra_id=obra.id, admin_id=admin.id, numero=1,
        periodo_inicio=date(2026, 6, 1), periodo_fim=date(2026, 6, 15),
        percentual_executado=42.5, valor_medido=106250.00,
        valor_total_medido_periodo=106250.00,
        valor_a_faturar_periodo=106250.00, status=status,
    )
    db.session.add(medicao)
    db.session.commit()
    return admin, obra, medicao


def test_assinatura_persiste_com_todos_os_elementos_probatorios():
    with app.app_context():
        admin, obra, medicao = _obra_com_medicao()
        a = Assinatura(
            documento_tipo='medicao_obra', documento_id=medicao.id,
            documento_hash='b' * 64, snapshot={'numero': 1},
            papel='cliente', signatario_nome='João da Silva',
            signatario_documento='123.456.789-00',
            signatario_email='joao@cliente.com',
            declaracao='Declaro que revisei e aceito a medição nº 001.',
            ip='203.0.113.7', user_agent='Mozilla/5.0',
            assinado_em=datetime.utcnow(),
            admin_id=admin.id, obra_id=obra.id,
        )
        db.session.add(a)
        db.session.commit()
        aid = a.id

    with app.app_context():
        r = db.session.get(Assinatura, aid)
        assert r.documento_hash == 'b' * 64
        assert r.snapshot == {'numero': 1}
        assert r.ip == '203.0.113.7'
        assert r.declaracao.startswith('Declaro')
        assert r.assinado_em is not None


def test_um_documento_nao_e_assinado_duas_vezes_no_mesmo_papel():
    from sqlalchemy.exc import IntegrityError

    with app.app_context():
        admin, obra, medicao = _obra_com_medicao()
        for i in range(2):
            db.session.add(Assinatura(
                documento_tipo='medicao_obra', documento_id=medicao.id,
                documento_hash='c' * 64, snapshot={}, papel='cliente',
                signatario_nome=f'Signatario {i}',
                declaracao='x', assinado_em=datetime.utcnow(),
                admin_id=admin.id, obra_id=obra.id,
            ))
            if i == 0:
                db.session.commit()
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_o_mesmo_documento_aceita_papeis_diferentes():
    """Fase 5 assina RDO como encarregado e como GP; aqui o cliente."""
    with app.app_context():
        admin, obra, medicao = _obra_com_medicao()
        for papel in ('cliente', 'gerente_projeto'):
            db.session.add(Assinatura(
                documento_tipo='medicao_obra', documento_id=medicao.id,
                documento_hash='d' * 64, snapshot={}, papel=papel,
                signatario_nome=papel, declaracao='x',
                assinado_em=datetime.utcnow(),
                admin_id=admin.id, obra_id=obra.id,
            ))
        db.session.commit()
        assert Assinatura.query.filter_by(
            documento_tipo='medicao_obra', documento_id=medicao.id).count() == 2


def test_tabela_serve_ao_rdo_da_fase_5():
    """Trava de contrato: a tabela não é específica de medição."""
    with app.app_context():
        admin, obra, _ = _obra_com_medicao()
        a = Assinatura(
            documento_tipo='rdo', documento_id=999, documento_hash='e' * 64,
            snapshot={}, papel='encarregado', signatario_nome='Encarregado',
            declaracao='x', assinado_em=datetime.utcnow(),
            admin_id=admin.id, obra_id=obra.id, usuario_id=admin.id,
        )
        db.session.add(a)
        db.session.commit()
        assert a.id is not None
```

- [ ] **Step 3: Adicione o modelo em `models.py`**

Logo após `class PortalEvento`:

```python
class Assinatura(db.Model):
    """Assinatura eletrônica simples com registro de autoria — Fase 9a.

    Tabela GENÉRICA de propósito: `documento_tipo` ∈ {'medicao_obra',
    'rdo', 'contrato'}. A Fase 5 (RDO com ciclo de vida e assinatura)
    usa esta mesma tabela — o `DEVOLUTIVA.md:104` propunha uma
    `RDOAssinatura` específica; duas tabelas com o mesmo conteúdo
    probatório seriam duas implementações do mesmo raciocínio jurídico,
    divergindo com o tempo.

    O QUE FAZ ESTA LINHA VALER COMO PROVA (decisão D1 do plano):

      1. `signatario_nome` + `signatario_documento` digitados pelo
         próprio signatário e conferidos contra o cadastro `Cliente`.
      2. `portal_acesso_id` — a credencial de uso único, nominal,
         emitida para aquele documento e aquele destinatário.
      3. `documento_hash` — SHA-256 do `snapshot` canônico.
      4. `snapshot` — o conteúdo exato assinado, PERSISTIDO. Sem ele, a
         prova dependeria de o banco nunca mudar.
      5. `assinado_em` (UTC), `ip`, `user_agent`.
      6. `declaracao` — o texto exato exibido na tela no ato.

    POR QUE O HASH É DO SNAPSHOT E NÃO DO PDF: o extrato é gerado por
    reportlab a cada request (services/medicao_service.py:389-405) e o
    PDF não é byte-determinístico — metadados de criação mudam a cada
    geração. Hashear o PDF produziria hashes diferentes para o mesmo
    conteúdo, o que é pior do que não ter hash.

    APPEND-ONLY por contrato: não existe rota que edite nem apague.
    """
    __tablename__ = 'assinatura'
    __table_args__ = (
        db.UniqueConstraint('documento_tipo', 'documento_id', 'papel',
                            name='uq_assinatura_documento_papel'),
        db.Index('ix_assinatura_documento', 'documento_tipo', 'documento_id'),
        db.Index('ix_assinatura_obra', 'obra_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    documento_tipo = db.Column(db.String(40), nullable=False)
    documento_id = db.Column(db.Integer, nullable=False)
    documento_hash = db.Column(db.String(64), nullable=False)
    snapshot = db.Column(JSON, nullable=False)

    papel = db.Column(db.String(40), nullable=False)   # cliente | encarregado | gerente_projeto
    signatario_nome = db.Column(db.String(200), nullable=False)
    signatario_documento = db.Column(db.String(20))    # CPF/CNPJ digitado
    signatario_email = db.Column(db.String(200))
    declaracao = db.Column(db.Text, nullable=False)

    # Um dos dois identifica a origem: usuário interno (Fase 5) ou
    # capability token do portal (Fase 9a).
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    portal_acesso_id = db.Column(
        db.Integer, db.ForeignKey('portal_acesso.id', ondelete='SET NULL'),
        nullable=True)

    ip = db.Column(db.String(45))
    user_agent = db.Column(db.String(300))
    assinado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id', ondelete='CASCADE'),
                        nullable=True)

    def __repr__(self):
        return (f'<Assinatura {self.documento_tipo}#{self.documento_id} '
                f'{self.papel} {self.documento_hash[:8]}…>')
```

- [ ] **Step 4: Escreva a migration 303 e registre**

```python
def _migration_303_assinatura():
    """Fase 9a — tabela assinatura (genérica, compartilhada com a Fase 5).

    Se a Fase 5 já tiver criado `rdo_assinatura`, esta migração NÃO cria
    tabela nova: renomeia, completa e faz backfill. Ver o Step 1 da Task
    9 do plano.
    """
    logger.info("[Migration 303] Iniciando — tabela assinatura")

    ja_existe_rdo = db.session.execute(text("""
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'rdo_assinatura' LIMIT 1
    """)).fetchone()

    if ja_existe_rdo:
        logger.info("[Migration 303] rdo_assinatura existe — generalizando")
        db.session.execute(text("ALTER TABLE rdo_assinatura RENAME TO assinatura"))
        db.session.commit()
        for coluna, tipo in [
            ('documento_tipo', "VARCHAR(40)"), ('documento_id', 'INTEGER'),
            ('documento_hash', 'VARCHAR(64)'), ('snapshot', 'JSON'),
            ('declaracao', 'TEXT'), ('signatario_documento', 'VARCHAR(20)'),
            ('signatario_email', 'VARCHAR(200)'),
            ('portal_acesso_id', 'INTEGER'), ('obra_id', 'INTEGER'),
        ]:
            db.session.execute(text(
                f"ALTER TABLE assinatura ADD COLUMN IF NOT EXISTS {coluna} {tipo}"))
        db.session.commit()
        db.session.execute(text("""
            UPDATE assinatura
            SET documento_tipo = 'rdo', documento_id = rdo_id
            WHERE documento_tipo IS NULL
        """))
        db.session.commit()
    else:
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS assinatura (
                id SERIAL PRIMARY KEY,
                documento_tipo VARCHAR(40) NOT NULL,
                documento_id INTEGER NOT NULL,
                documento_hash VARCHAR(64) NOT NULL,
                snapshot JSON NOT NULL,
                papel VARCHAR(40) NOT NULL,
                signatario_nome VARCHAR(200) NOT NULL,
                signatario_documento VARCHAR(20),
                signatario_email VARCHAR(200),
                declaracao TEXT NOT NULL,
                usuario_id INTEGER REFERENCES usuario(id),
                portal_acesso_id INTEGER REFERENCES portal_acesso(id) ON DELETE SET NULL,
                ip VARCHAR(45),
                user_agent VARCHAR(300),
                assinado_em TIMESTAMP NOT NULL DEFAULT NOW(),
                admin_id INTEGER NOT NULL REFERENCES usuario(id),
                obra_id INTEGER REFERENCES obra(id) ON DELETE CASCADE
            )
        """))
        db.session.commit()

    db.session.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_assinatura_documento_papel
        ON assinatura (documento_tipo, documento_id, papel)
    """))
    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_assinatura_documento
        ON assinatura (documento_tipo, documento_id)
    """))
    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_assinatura_obra ON assinatura (obra_id)
    """))
    db.session.commit()

    logger.info("[Migration 303] Concluída com sucesso")
```

Registre após a entrada `302`:

```python
            (303, "Fase 9a — tabela assinatura genérica (medição, RDO, contrato): snapshot + SHA-256 + IP + declaração", _migration_303_assinatura),
```

- [ ] **Step 5: Aplique e rode**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "303|ERRO|ERROR"
python -m pytest tests/test_fase9_assinatura_medicao.py -v
```

Esperado: `[Migration 303] Concluída com sucesso` e os 4 testes PASSAM.

- [ ] **Step 6: Commit**

```bash
git add models.py migrations.py tests/test_fase9_assinatura_medicao.py
git commit -m "feat(fase9a): tabela assinatura generica (medicao, RDO, contrato)

Assinatura eletronica simples com registro de autoria: snapshot
canonico PERSISTIDO + SHA-256 + carimbo UTC + IP + user-agent +
declaracao exibida + vinculo com o capability token de uso unico.

Hash do SNAPSHOT e nao do PDF: o extrato reportlab
(services/medicao_service.py:389) nao e byte-deterministico.

A Fase 5 usa esta mesma tabela (documento_tipo='rdo'); a migration
generaliza rdo_assinatura se ela ja existir."
```

---

## Task 10: Snapshot canônico e hash da medição

**Files:**
- Create: `services/assinatura_documento.py`
- Test: `tests/test_fase9_assinatura_medicao.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

```python
# ---------------------------------------------------------------------------
# Snapshot canônico
# ---------------------------------------------------------------------------

def test_snapshot_de_medicao_traz_cabecalho_e_itens():
    from services.assinatura_documento import snapshot_medicao

    with app.app_context():
        _, obra, medicao = _obra_com_medicao()
        snap = snapshot_medicao(medicao)
        assert snap['documento_tipo'] == 'medicao_obra'
        assert snap['medicao']['numero'] == 1
        assert snap['medicao']['periodo_inicio'] == '2026-06-01'
        assert snap['medicao']['periodo_fim'] == '2026-06-15'
        assert snap['medicao']['percentual_executado'] == '42.50'
        assert snap['medicao']['valor_a_faturar_periodo'] == '106250.00'
        assert snap['obra']['codigo'] == obra.codigo
        assert snap['obra']['valor_contrato'] == '250000.00'
        assert isinstance(snap['itens'], list)


def test_hash_canonico_e_estavel_entre_execucoes():
    from services.assinatura_documento import hash_canonico, snapshot_medicao

    with app.app_context():
        _, _, medicao = _obra_com_medicao()
        h1 = hash_canonico(snapshot_medicao(medicao))
        h2 = hash_canonico(snapshot_medicao(medicao))
        assert h1 == h2
        assert len(h1) == 64


def test_hash_canonico_ignora_ordem_das_chaves():
    from services.assinatura_documento import hash_canonico

    a = {'x': 1, 'y': {'b': 2, 'a': 3}}
    b = {'y': {'a': 3, 'b': 2}, 'x': 1}
    assert hash_canonico(a) == hash_canonico(b)


def test_hash_muda_quando_o_valor_da_medicao_muda():
    """É a propriedade inteira: alterar a medição depois de assinada
    torna a divergência detectável."""
    from services.assinatura_documento import hash_canonico, snapshot_medicao

    with app.app_context():
        _, _, medicao = _obra_com_medicao()
        antes = hash_canonico(snapshot_medicao(medicao))
        medicao.valor_a_faturar_periodo = 999999.00
        db.session.commit()
        depois = hash_canonico(snapshot_medicao(medicao))
        assert antes != depois


def test_snapshot_nao_carrega_dado_volatil():
    """`data_medicao` tem default datetime.utcnow (models.py:5490) e não
    entra no snapshot: um campo que muda sozinho quebraria a estabilidade
    do hash sem representar mudança de conteúdo."""
    from services.assinatura_documento import snapshot_medicao

    with app.app_context():
        _, _, medicao = _obra_com_medicao()
        snap = snapshot_medicao(medicao)
        assert 'data_medicao' not in snap['medicao']
        assert 'created_at' not in snap['medicao']
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase9_assinatura_medicao.py -v -k "snapshot or hash"
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'services.assinatura_documento'`.

- [ ] **Step 3: Implemente o serviço**

Crie `services/assinatura_documento.py`:

```python
#!/usr/bin/env python3
"""Snapshot canônico e assinatura de documentos — SIGE Fase 9a.

O problema que este módulo resolve: "o que exatamente foi assinado?".

O extrato de medição é montado a cada request a partir do estado VIVO
do banco (services/medicao_service.py:389-405) e o PDF do reportlab não
é byte-determinístico. Assinar "a medição 001" sem congelar o conteúdo
significa assinar um alvo móvel.

A resposta é um snapshot canônico: um dict com chaves fixas, valores
normalizados (Decimal → string com casas fixas, date → ISO) e ordem
irrelevante, serializado com `sort_keys=True` e separadores compactos.
O SHA-256 desse texto é o hash. O snapshot inteiro fica PERSISTIDO em
`Assinatura.snapshot` — a prova não depende de regenerar nada.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger('assinatura')

DECLARACAO_MEDICAO = (
    'Declaro, para os devidos fins, que revisei o extrato da medição '
    'nº {numero:03d} da obra {obra_nome} ({obra_codigo}), referente ao '
    'período de {periodo_inicio} a {periodo_fim}, no valor de '
    'R$ {valor} ({percentual}% executado), e que o aceito como correto. '
    'Reconheço este aceite eletrônico como manifestação de vontade '
    'válida entre as partes, nos termos do art. 10, §2º da MP 2.200-2/2001 '
    'e do art. 4º, I da Lei 14.063/2020.'
)


def _dec(valor, casas=2) -> str:
    """Decimal/float/None → string com casas fixas. Nunca float no JSON:
    `0.1 + 0.2` mudaria o hash entre plataformas."""
    if valor is None:
        return '0.' + '0' * casas
    return f'{Decimal(str(valor)):.{casas}f}'


def _data(valor) -> str | None:
    if valor is None:
        return None
    return valor.isoformat()[:10]


def snapshot_medicao(medicao) -> dict:
    """Conteúdo exato de uma medição, em forma canônica.

    Deliberadamente FORA do snapshot: `data_medicao` e `created_at`
    (defaults `datetime.utcnow`, models.py:5490/5502) e `conta_receber_id`
    — nenhum representa o conteúdo do que o cliente aceita, e todos
    mudariam o hash sem mudar o documento.
    """
    from models import MedicaoObraItem, Obra, db

    obra = db.session.get(Obra, medicao.obra_id)
    itens = (MedicaoObraItem.query
             .filter_by(medicao_obra_id=medicao.id)
             .order_by(MedicaoObraItem.id)
             .all())

    return {
        'versao_formato': 1,
        'documento_tipo': 'medicao_obra',
        'documento_id': medicao.id,
        'obra': {
            'id': obra.id if obra else None,
            'codigo': obra.codigo if obra else None,
            'nome': obra.nome if obra else None,
            'valor_contrato': _dec(obra.valor_contrato if obra else 0),
        },
        'medicao': {
            'numero': medicao.numero,
            'periodo_inicio': _data(medicao.periodo_inicio),
            'periodo_fim': _data(medicao.periodo_fim),
            'status': medicao.status,
            'percentual_executado': _dec(medicao.percentual_executado),
            'valor_medido': _dec(medicao.valor_medido),
            'valor_total_medido_periodo': _dec(medicao.valor_total_medido_periodo),
            'valor_entrada_abatido_periodo': _dec(medicao.valor_entrada_abatido_periodo),
            'valor_a_faturar_periodo': _dec(medicao.valor_a_faturar_periodo),
            'observacoes': medicao.observacoes or '',
        },
        'itens': [
            {
                'id': it.id,
                'item_medicao_comercial_id': it.item_medicao_comercial_id,
                'descricao': getattr(it.item_comercial, 'descricao', None)
                             if it.item_comercial else None,
                'percentual_anterior': _dec(it.percentual_anterior),
                'percentual_atual': _dec(it.percentual_atual),
                'percentual_executado_periodo': _dec(it.percentual_executado_periodo),
                'valor_medido_periodo': _dec(it.valor_medido_periodo),
                'percentual_executado_acumulado': _dec(it.percentual_executado_acumulado),
                'valor_executado_acumulado': _dec(it.valor_executado_acumulado),
            }
            for it in itens
        ],
    }


def hash_canonico(snapshot: dict) -> str:
    """SHA-256 hexdigest da serialização canônica do snapshot."""
    texto = json.dumps(snapshot, sort_keys=True, ensure_ascii=False,
                       separators=(',', ':'))
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()


def declaracao_medicao(medicao, snapshot) -> str:
    """O texto exibido ao cliente no ato — gravado junto com a assinatura."""
    m = snapshot['medicao']
    return DECLARACAO_MEDICAO.format(
        numero=medicao.numero,
        obra_nome=snapshot['obra']['nome'] or '—',
        obra_codigo=snapshot['obra']['codigo'] or '—',
        periodo_inicio=(m['periodo_inicio'] or '')[8:10] + '/'
                       + (m['periodo_inicio'] or '')[5:7] + '/'
                       + (m['periodo_inicio'] or '')[0:4],
        periodo_fim=(m['periodo_fim'] or '')[8:10] + '/'
                    + (m['periodo_fim'] or '')[5:7] + '/'
                    + (m['periodo_fim'] or '')[0:4],
        valor=m['valor_a_faturar_periodo'],
        percentual=m['percentual_executado'],
    )


def assinar_documento(*, documento_tipo, documento_id, snapshot, papel,
                      signatario_nome, declaracao, admin_id, obra_id=None,
                      signatario_documento=None, signatario_email=None,
                      usuario_id=None, portal_acesso_id=None,
                      ip=None, user_agent=None):
    """Grava a assinatura. Não faz commit — quem chama decide a transação.

    Levanta `JaAssinado` se já houver assinatura do mesmo papel para o
    mesmo documento (o UNIQUE do banco é a rede de segurança; esta
    checagem é a mensagem legível).
    """
    from models import Assinatura, db

    ja = Assinatura.query.filter_by(
        documento_tipo=documento_tipo, documento_id=documento_id, papel=papel
    ).first()
    if ja is not None:
        raise JaAssinado(
            f'{documento_tipo}#{documento_id} já foi assinado como "{papel}" '
            f'em {ja.assinado_em:%d/%m/%Y %H:%M} UTC')

    assinatura = Assinatura(
        documento_tipo=documento_tipo, documento_id=documento_id,
        documento_hash=hash_canonico(snapshot), snapshot=snapshot,
        papel=papel, signatario_nome=signatario_nome,
        signatario_documento=signatario_documento,
        signatario_email=signatario_email, declaracao=declaracao,
        usuario_id=usuario_id, portal_acesso_id=portal_acesso_id,
        ip=ip, user_agent=user_agent, assinado_em=datetime.utcnow(),
        admin_id=admin_id, obra_id=obra_id,
    )
    db.session.add(assinatura)
    db.session.flush()
    return assinatura


def assinatura_de(documento_tipo, documento_id, papel=None):
    """Assinatura(s) de um documento. Com `papel`, devolve uma ou None."""
    from models import Assinatura

    q = Assinatura.query.filter_by(documento_tipo=documento_tipo,
                                   documento_id=documento_id)
    if papel is not None:
        return q.filter_by(papel=papel).first()
    return q.order_by(Assinatura.assinado_em).all()


def conferir_integridade(assinatura, snapshot_atual) -> dict:
    """Compara o estado atual do documento com o que foi assinado.

    Devolve ``{'integro': bool, 'hash_assinado': str, 'hash_atual': str}``.
    Usado no comprovante e na tela interna: se o documento mudou depois
    da assinatura, isso precisa aparecer — não ser escondido.
    """
    atual = hash_canonico(snapshot_atual)
    return {
        'integro': atual == assinatura.documento_hash,
        'hash_assinado': assinatura.documento_hash,
        'hash_atual': atual,
    }


class JaAssinado(Exception):
    """Tentativa de assinar duas vezes o mesmo documento no mesmo papel."""
```

- [ ] **Step 4: Rode os testes**

```bash
python -m pytest tests/test_fase9_assinatura_medicao.py -v
```

Esperado: os 9 testes PASSAM.

- [ ] **Step 5: Commit**

```bash
git add services/assinatura_documento.py tests/test_fase9_assinatura_medicao.py
git commit -m "feat(fase9a): snapshot canonico e hash SHA-256 da medicao

Congela o que esta sendo assinado: dict de chaves fixas, Decimal como
string de casas fixas (nunca float), datas ISO, serializacao com
sort_keys. Fora do snapshot: data_medicao e created_at (defaults
utcnow) — mudariam o hash sem mudar o documento.

conferir_integridade() compara o estado atual com o assinado: se a
medicao mudou depois, isso aparece."
```

---

## Task 11: Emissão do link de assinatura e a rota que assina

**Files:**
- Modify: `medicao_views.py` (rota interna de emissão)
- Modify: `portal_obras_views.py` (rotas de assinatura, GET e POST)
- Create: `templates/portal/portal_assinatura_medicao.html`
- Test: `tests/test_fase9_assinatura_medicao.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

```python
# ---------------------------------------------------------------------------
# Fluxo de assinatura
# ---------------------------------------------------------------------------

def _token_de_assinatura(medicao, obra, admin_id, dias=7):
    from utils.portal_acesso import emitir_acesso
    token, acesso = emitir_acesso(
        obra=obra, admin_id=admin_id,
        escopos=[EscopoPortal.ASSINAR_MEDICAO], dias_validade=dias,
        uso_unico=True, destinatario_nome='João da Silva',
        destinatario_email='joao@cliente.com')
    db.session.commit()
    return token, acesso


def test_link_de_leitura_nao_abre_a_tela_de_assinatura():
    """O achado central, aplicado à assinatura."""
    from utils.portal_acesso import emitir_acesso

    with app.app_context():
        admin, obra, medicao = _obra_com_medicao()
        token, _ = emitir_acesso(obra=obra, admin_id=admin.id,
                                 escopos=[EscopoPortal.LER], dias_validade=90)
        db.session.commit()
        mid = medicao.id

    r = app.test_client().get(f'/portal/obra/{token}/medicao/{mid}/assinar')
    assert r.status_code == 403


def test_assinatura_grava_hash_ip_e_declaracao():
    with app.app_context():
        admin, obra, medicao = _obra_com_medicao()
        token, acesso = _token_de_assinatura(medicao, obra, admin.id)
        mid, aid = medicao.id, acesso.id

    r = app.test_client().post(
        f'/portal/obra/{token}/medicao/{mid}/assinar',
        data={'nome': 'João da Silva', 'documento': '123.456.789-00',
              'aceite': 'on'},
        environ_base={'REMOTE_ADDR': '198.51.100.22',
                      'HTTP_USER_AGENT': 'Mozilla/5.0 (Teste)'},
        follow_redirects=True)
    assert r.status_code == 200

    with app.app_context():
        from services.assinatura_documento import (
            conferir_integridade, snapshot_medicao,
        )
        a = Assinatura.query.filter_by(documento_tipo='medicao_obra',
                                       documento_id=mid, papel='cliente').first()
        assert a is not None, 'a assinatura não foi gravada'
        assert a.ip == '198.51.100.22'
        assert a.user_agent.startswith('Mozilla/5.0')
        assert a.signatario_nome == 'João da Silva'
        assert a.signatario_documento == '123.456.789-00'
        assert len(a.documento_hash) == 64
        assert 'MP 2.200-2/2001' in a.declaracao
        assert a.portal_acesso_id == aid
        assert a.snapshot['medicao']['numero'] == 1

        medicao = db.session.get(MedicaoObra, mid)
        assert conferir_integridade(a, snapshot_medicao(medicao))['integro']


def test_assinatura_exige_o_aceite_marcado():
    with app.app_context():
        admin, obra, medicao = _obra_com_medicao()
        token, _ = _token_de_assinatura(medicao, obra, admin.id)
        mid = medicao.id

    app.test_client().post(f'/portal/obra/{token}/medicao/{mid}/assinar',
                           data={'nome': 'João', 'documento': '123'})
    with app.app_context():
        assert Assinatura.query.filter_by(documento_id=mid).count() == 0


def test_assinatura_exige_nome_e_documento():
    with app.app_context():
        admin, obra, medicao = _obra_com_medicao()
        token, _ = _token_de_assinatura(medicao, obra, admin.id)
        mid = medicao.id

    app.test_client().post(f'/portal/obra/{token}/medicao/{mid}/assinar',
                           data={'aceite': 'on'})
    with app.app_context():
        assert Assinatura.query.filter_by(documento_id=mid).count() == 0


def test_token_de_assinatura_queima_apos_o_uso():
    from utils.portal_acesso import resolver_acesso

    with app.app_context():
        admin, obra, medicao = _obra_com_medicao()
        token, _ = _token_de_assinatura(medicao, obra, admin.id)
        mid = medicao.id

    app.test_client().post(f'/portal/obra/{token}/medicao/{mid}/assinar',
                           data={'nome': 'João', 'documento': '123', 'aceite': 'on'})
    with app.app_context():
        assert resolver_acesso(token)[1] == 'consumido'


def test_nao_assina_medicao_ainda_pendente():
    """Só documento fechado é assinável — assinar rascunho não prova nada."""
    with app.app_context():
        admin, obra, medicao = _obra_com_medicao(status='PENDENTE')
        token, _ = _token_de_assinatura(medicao, obra, admin.id)
        mid = medicao.id

    r = app.test_client().post(
        f'/portal/obra/{token}/medicao/{mid}/assinar',
        data={'nome': 'João', 'documento': '123', 'aceite': 'on'})
    assert r.status_code in (302, 303, 409)
    with app.app_context():
        assert Assinatura.query.filter_by(documento_id=mid).count() == 0


def test_nao_assina_medicao_de_outra_obra():
    with app.app_context():
        admin_a, obra_a, _ = _obra_com_medicao()
        _, _, medicao_b = _obra_com_medicao()
        token, _ = _token_de_assinatura(medicao_b, obra_a, admin_a.id)
        mid_b = medicao_b.id

    r = app.test_client().post(
        f'/portal/obra/{token}/medicao/{mid_b}/assinar',
        data={'nome': 'X', 'documento': '1', 'aceite': 'on'})
    assert r.status_code == 404
    with app.app_context():
        assert Assinatura.query.filter_by(documento_id=mid_b).count() == 0


def test_assinatura_registra_evento_na_trilha():
    from models import PortalEvento

    with app.app_context():
        admin, obra, medicao = _obra_com_medicao()
        token, acesso = _token_de_assinatura(medicao, obra, admin.id)
        mid, aid = medicao.id, acesso.id

    app.test_client().post(f'/portal/obra/{token}/medicao/{mid}/assinar',
                           data={'nome': 'João', 'documento': '123', 'aceite': 'on'})
    with app.app_context():
        ev = PortalEvento.query.filter_by(acesso_id=aid,
                                          acao='assinar_medicao').first()
        assert ev is not None
        assert ev.resultado == 'ok'
        assert ev.alvo_tipo == 'medicao_obra'
        assert ev.alvo_id == mid
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase9_assinatura_medicao.py -v -k "assina or token_de_assinatura or link_de_leitura"
```

Esperado: FAIL com 404 — as rotas não existem.

- [ ] **Step 3: Acrescente as rotas de assinatura em `portal_obras_views.py`**

Ao final do arquivo:

```python
@portal_obras_bp.route('/obra/<token>/medicao/<int:medicao_id>/assinar')
@limiter.limit("30 per hour")
@portal_token_required(EscopoPortal.ASSINAR_MEDICAO)
def assinar_medicao_form(token: str, medicao_id: int):
    """Tela de assinatura. O token que chega aqui é de USO ÚNICO e não
    é queimado na exibição — só no POST."""
    from services.assinatura_documento import (
        assinatura_de, declaracao_medicao, hash_canonico, snapshot_medicao,
    )

    obra = _obra_do_request()
    medicao = MedicaoObra.query.filter_by(id=medicao_id, obra_id=obra.id).first()
    if not medicao:
        abort(404)

    ja = assinatura_de('medicao_obra', medicao.id, papel='cliente')
    if ja is not None:
        return redirect(url_for('portal_obras.comprovante_assinatura',
                                token=token, medicao_id=medicao.id))

    snapshot = snapshot_medicao(medicao)
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=obra.admin_id).first()
    return render_template(
        'portal/portal_assinatura_medicao.html',
        obra=obra, medicao=medicao, token=token, snapshot=snapshot,
        documento_hash=hash_canonico(snapshot),
        declaracao=declaracao_medicao(medicao, snapshot),
        destinatario=acesso_corrente().destinatario_nome,
        config_empresa=config,
        nome_empresa=config.nome_empresa if config else 'Construtora',
    )


@portal_obras_bp.route('/obra/<token>/medicao/<int:medicao_id>/assinar',
                       methods=['POST'])
@limiter.limit("10 per hour")
@portal_token_required(EscopoPortal.ASSINAR_MEDICAO)
def assinar_medicao(token: str, medicao_id: int):
    """Registra a assinatura eletrônica simples do cliente.

    Fase 9a. Ordem deliberada: valida o formulário, valida o estado do
    documento, congela o snapshot, grava, QUEIMA o token, registra a
    trilha — tudo numa transação só. Se qualquer passo falhar, nada
    fica: nem assinatura sem trilha, nem token queimado sem assinatura.
    """
    from services.assinatura_documento import (
        JaAssinado, assinar_documento, declaracao_medicao, snapshot_medicao,
    )
    from utils.portal_acesso import consumir_uso

    obra = _obra_do_request()
    acesso = acesso_corrente()
    medicao = MedicaoObra.query.filter_by(id=medicao_id, obra_id=obra.id).first()
    if not medicao:
        abort(404)

    nome = (request.form.get('nome') or '').strip()
    documento = (request.form.get('documento') or '').strip()
    aceite = request.form.get('aceite') in ('on', 'true', '1')

    if not nome or not documento or not aceite:
        registrar_evento(acesso=acesso, acao='assinar_medicao',
                         resultado='negado', motivo='formulario_incompleto',
                         alvo_tipo='medicao_obra', alvo_id=medicao.id)
        db.session.commit()
        flash('Preencha o nome completo, o CPF/CNPJ e marque a declaração.',
              'warning')
        return redirect(url_for('portal_obras.assinar_medicao_form',
                                token=token, medicao_id=medicao.id))

    # Só documento fechado é assinável. Assinar uma medição PENDENTE
    # seria assinar rascunho — o valor pode mudar depois sem que o
    # cliente tenha visto.
    if medicao.status not in ('APROVADO', 'FATURADO'):
        registrar_evento(acesso=acesso, acao='assinar_medicao',
                         resultado='negado', motivo='medicao_nao_fechada',
                         alvo_tipo='medicao_obra', alvo_id=medicao.id)
        db.session.commit()
        flash('Esta medição ainda não foi fechada pela construtora.', 'warning')
        return redirect(url_for('portal_obras.portal_obra', token=token))

    snapshot = snapshot_medicao(medicao)
    try:
        assinatura = assinar_documento(
            documento_tipo='medicao_obra', documento_id=medicao.id,
            snapshot=snapshot, papel='cliente',
            signatario_nome=nome[:200], signatario_documento=documento[:20],
            signatario_email=acesso.destinatario_email,
            declaracao=declaracao_medicao(medicao, snapshot),
            admin_id=obra.admin_id, obra_id=obra.id,
            portal_acesso_id=acesso.id,
            ip=(request.remote_addr or '')[:45],
            user_agent=(request.headers.get('User-Agent') or '')[:300],
        )
    except JaAssinado:
        db.session.rollback()
        flash('Esta medição já foi assinada.', 'info')
        return redirect(url_for('portal_obras.comprovante_assinatura',
                                token=token, medicao_id=medicao.id))

    consumir_uso(acesso)
    registrar_evento(acesso=acesso, acao='assinar_medicao', resultado='ok',
                     alvo_tipo='medicao_obra', alvo_id=medicao.id,
                     detalhes={'documento_hash': assinatura.documento_hash,
                               'signatario': nome[:200]})
    db.session.commit()

    logger.info("[PORTAL] medição %s assinada por '%s' (acesso %s, hash %s…)",
                medicao.id, nome, acesso.token_prefixo,
                assinatura.documento_hash[:12])

    try:
        from utils.catalogo_eventos import emit_obra_medicao_assinada
        emit_obra_medicao_assinada(medicao, obra.admin_id, assinatura)
    except Exception as e:
        logger.warning("emit obra.medicao_assinada falhou (best-effort): %s", e)

    return redirect(url_for('portal_obras.comprovante_assinatura',
                            token=token, medicao_id=medicao.id))
```

> `comprovante_assinatura` é criada na Task 13. Até lá, o teste
> `test_assinatura_grava_hash_ip_e_declaracao` usa `follow_redirects=True`
> e vai receber 404 no destino — **execute a Task 13 antes de fechar a
> Task 11**, ou troque temporariamente o redirect por
> `url_for('portal_obras.portal_obra', token=token)`.
> `emit_obra_medicao_assinada` é criada na Task 20 (9b); até lá o
> `except` engole o `ImportError`, que é o comportamento desejado.

- [ ] **Step 4: Acrescente a rota interna de emissão do link em `medicao_views.py`**

```python
@medicao_bp.route('/obras/<int:obra_id>/medicao/<int:medicao_id>/link-assinatura',
                  methods=['POST'])
@login_required
def emitir_link_assinatura(obra_id, medicao_id):
    """Emite o capability token de ASSINATURA da medição.

    Fase 9a — deliberadamente separado do link de acompanhamento
    (portal_obras.emitir_acesso_portal, que RECUSA o escopo
    assinar_medicao). Aqui o token é:
      * de uso único,
      * válido por 7 dias,
      * nominal (nome e e-mail do signatário),
      * emitido para uma medição já FECHADA.

    É isso que dá à assinatura um vínculo prévio de identidade: o link
    não é o mesmo que circula no grupo de WhatsApp da obra.
    """
    from models import Cliente, EscopoPortal, Obra as ObraModel
    from utils.portal_acesso import DIAS_VALIDADE_ASSINATURA, emitir_acesso, registrar_evento

    admin_id = _admin_id()
    obra = ObraModel.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()
    medicao = MedicaoObra.query.filter_by(
        id=medicao_id, obra_id=obra.id, admin_id=admin_id).first_or_404()

    if medicao.status not in ('APROVADO', 'FATURADO'):
        flash('Feche a medição antes de enviar para assinatura.', 'warning')
        return redirect(url_for('medicao.gestao_itens', obra_id=obra_id))

    cliente = db.session.get(Cliente, obra.cliente_id) if obra.cliente_id else None
    nome = (request.form.get('nome') or (cliente.nome if cliente else '')).strip()
    email = (request.form.get('email') or (cliente.email if cliente else '')).strip()
    if not nome:
        flash('Informe o nome do signatário.', 'warning')
        return redirect(url_for('medicao.gestao_itens', obra_id=obra_id))

    token, acesso = emitir_acesso(
        obra=obra, admin_id=admin_id,
        escopos=[EscopoPortal.ASSINAR_MEDICAO],
        dias_validade=DIAS_VALIDADE_ASSINATURA, uso_unico=True,
        destinatario_nome=nome, destinatario_email=email or None,
        criado_por_usuario_id=current_user.id,
    )
    registrar_evento(acesso=acesso, acao='emitir_link_assinatura',
                     resultado='ok', alvo_tipo='medicao_obra',
                     alvo_id=medicao.id, admin_id=admin_id)
    db.session.commit()

    url = url_for('portal_obras.assinar_medicao_form', token=token,
                  medicao_id=medicao.id, _external=True)
    flash(f'Link de assinatura para {nome} — válido por '
          f'{DIAS_VALIDADE_ASSINATURA} dias, uso único, copie agora: {url}',
          'success')
    return redirect(url_for('medicao.gestao_itens', obra_id=obra_id))
```

- [ ] **Step 5: Crie `templates/portal/portal_assinatura_medicao.html`**

```html
{% extends 'portal/_base.html' %}
{% block portal_content %}
<div class="card-portal" style="max-width:760px;margin:2rem auto;padding:2rem">
  <h1 style="font-size:1.4rem;margin-bottom:.25rem">
    Medição nº {{ '%03d'|format(medicao.numero) }}</h1>
  <p style="color:#5a6473;margin-bottom:1.5rem">
    {{ obra.nome }} · período de
    {{ medicao.periodo_inicio.strftime('%d/%m/%Y') }} a
    {{ medicao.periodo_fim.strftime('%d/%m/%Y') }}</p>

  <table class="table table-sm">
    <tr><th style="width:45%">Percentual executado</th>
        <td>{{ snapshot.medicao.percentual_executado }}%</td></tr>
    <tr><th>Valor medido no período</th>
        <td>{{ snapshot.medicao.valor_total_medido_periodo }}</td></tr>
    <tr><th>Entrada abatida</th>
        <td>−{{ snapshot.medicao.valor_entrada_abatido_periodo }}</td></tr>
    <tr><th>Valor a faturar</th>
        <td><strong>R$ {{ snapshot.medicao.valor_a_faturar_periodo }}</strong></td></tr>
  </table>

  <p style="margin:1rem 0">
    <a href="{{ url_for('medicao.portal_pdf_extrato', token=token, medicao_id=medicao.id) }}"
       target="_blank" rel="noopener">
      <i class="fas fa-file-pdf"></i> Abrir o extrato completo em PDF</a>
  </p>

  <div style="background:#f5f7fa;border-radius:8px;padding:1rem;margin:1.5rem 0;
              font-size:.85rem;color:#5a6473">
    <strong>Identificador desta versão do documento (SHA-256):</strong><br>
    <code style="word-break:break-all">{{ documento_hash }}</code><br>
    <small>Qualquer alteração no conteúdo acima muda este identificador.</small>
  </div>

  <form method="POST"
        action="{{ url_for('portal_obras.assinar_medicao', token=token, medicao_id=medicao.id) }}">
    <div class="mb-3">
      <label class="form-label">Nome completo</label>
      <input name="nome" class="form-control" required
             value="{{ destinatario or '' }}" autocomplete="name">
    </div>
    <div class="mb-3">
      <label class="form-label">CPF ou CNPJ</label>
      <input name="documento" class="form-control" required
             inputmode="numeric" autocomplete="off">
    </div>
    <div class="form-check mb-3">
      <input class="form-check-input" type="checkbox" name="aceite" id="aceite" required>
      <label class="form-check-label" for="aceite" style="font-size:.9rem;line-height:1.55">
        {{ declaracao }}</label>
    </div>
    <p style="font-size:.8rem;color:#7a828e">
      Ao confirmar, serão registrados a data e a hora (UTC), o seu endereço IP
      e o navegador utilizado, junto com o identificador do documento acima.
      Este link é de uso único e deixa de valer após a confirmação.</p>
    <button class="btn btn-primary btn-lg w-100">Assinar esta medição</button>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 6: Rode os testes**

```bash
python -m pytest tests/test_fase9_assinatura_medicao.py -v
```

Esperado: todos PASSAM (execute a Task 13 antes, ou aplique o desvio do redirect descrito no Step 3).

- [ ] **Step 7: Commit**

```bash
git add portal_obras_views.py medicao_views.py templates/portal/ \
        tests/test_fase9_assinatura_medicao.py
git commit -m "feat(fase9a): assinatura de medicao pelo cliente no portal

Token de assinatura e SEPARADO do de acompanhamento: uso unico, 7 dias,
nominal, emitido pela tela da medicao ja FECHADA. A rota de emissao de
link do portal recusa explicitamente o escopo assinar_medicao.

O POST valida formulario e estado, congela o snapshot, grava hash + IP
+ user-agent + declaracao, QUEIMA o token e registra a trilha na mesma
transacao. Link de leitura recebe 403 na tela de assinatura."
```

---

## Task 12: Imutabilidade da medição assinada

**Files:**
- Modify: `services/medicao_service.py` (guarda em `fechar_medicao` e no recálculo)
- Modify: `medicao_views.py:217,323,341,400,420` (rotas de edição de item)
- Test: `tests/test_fase9_assinatura_medicao.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

```python
# ---------------------------------------------------------------------------
# Imutabilidade
# ---------------------------------------------------------------------------

def _assinar(medicao, obra, admin_id):
    from services.assinatura_documento import (
        assinar_documento, declaracao_medicao, snapshot_medicao,
    )
    snap = snapshot_medicao(medicao)
    a = assinar_documento(
        documento_tipo='medicao_obra', documento_id=medicao.id, snapshot=snap,
        papel='cliente', signatario_nome='João', signatario_documento='123',
        declaracao=declaracao_medicao(medicao, snap),
        admin_id=admin_id, obra_id=obra.id, ip='203.0.113.1')
    db.session.commit()
    return a


def test_medicao_assinada_nao_aceita_edicao_de_item():
    with app.app_context():
        admin, obra, medicao = _obra_com_medicao()
        _assinar(medicao, obra, admin.id)
        mid, oid, aid = medicao.id, obra.id, admin.id

    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(aid)
        sess['_fresh'] = True
    r = c.post(f'/obras/{oid}/medicao/itens', data={'descricao': 'novo'},
               follow_redirects=True)
    assert 'assinada' in r.get_data(as_text=True).lower() or r.status_code == 409


def test_medicao_assinada_nao_e_reaberta():
    from services.medicao_service import fechar_medicao

    with app.app_context():
        admin, obra, medicao = _obra_com_medicao(status='PENDENTE')
        medicao.status = 'APROVADO'
        db.session.commit()
        _assinar(medicao, obra, admin.id)
        medicao.status = 'PENDENTE'   # simula tentativa de reabertura
        db.session.commit()
        resultado, erro = fechar_medicao(medicao.id, admin.id)
        assert resultado is None
        assert 'assinada' in (erro or '').lower()


def test_conferir_integridade_denuncia_alteracao_pos_assinatura():
    from services.assinatura_documento import conferir_integridade, snapshot_medicao

    with app.app_context():
        admin, obra, medicao = _obra_com_medicao()
        a = _assinar(medicao, obra, admin.id)
        medicao.valor_a_faturar_periodo = 1.00
        db.session.commit()
        resultado = conferir_integridade(a, snapshot_medicao(medicao))
        assert resultado['integro'] is False
        assert resultado['hash_atual'] != resultado['hash_assinado']
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase9_assinatura_medicao.py -v -k "imutab or assinada or integridade"
```

Esperado: os dois primeiros FALHAM (a edição passa e a medição reabre).

- [ ] **Step 3: Acrescente a guarda em `services/medicao_service.py`**

No topo do arquivo, após os imports:

```python
def medicao_esta_assinada(medicao_id) -> bool:
    """True se o cliente já assinou esta medição — Fase 9a.

    Documento assinado é imutável: alterar valor ou percentual depois da
    assinatura invalidaria o hash gravado em `assinatura.documento_hash`
    sem ninguém perceber, e é exatamente o cenário que a assinatura
    existe para impedir.
    """
    from services.assinatura_documento import assinatura_de
    return assinatura_de('medicao_obra', medicao_id, papel='cliente') is not None
```

E, no início de `fechar_medicao` (`services/medicao_service.py:180-186`), logo após o `if not medicao:`:

```python
    if medicao_esta_assinada(medicao.id):
        return None, ('Medição já assinada pelo cliente — não pode ser '
                      'reaberta nem refechada. Emita uma medição '
                      'retificadora.')
```

- [ ] **Step 4: Acrescente a guarda nas rotas de edição de `medicao_views.py`**

Nas cinco rotas que escrevem em itens (`:217`/`:218` editar, `:323`–`:325` excluir, `:341`/`:342` vincular tarefa, `:400`/`:401` desvincular, `:420`/`:421` config) e na de criação (`:127`/`:128`), acrescente como primeira linha do corpo:

```python
    from services.medicao_service import medicao_esta_assinada
    medicao_atual = MedicaoObra.query.filter_by(
        obra_id=obra_id, admin_id=_admin_id()
    ).order_by(MedicaoObra.numero.desc()).first()
    if medicao_atual and medicao_esta_assinada(medicao_atual.id):
        flash('Esta medição já foi assinada pelo cliente e não pode ser '
              'alterada. Emita uma medição retificadora.', 'danger')
        return redirect(url_for('medicao.gestao_itens', obra_id=obra_id))
```

- [ ] **Step 5: Rode os testes**

```bash
python -m pytest tests/test_fase9_assinatura_medicao.py -v
python -m pytest tests/ -m "not browser" -k medicao -q
```

- [ ] **Step 6: Commit**

```bash
git add services/medicao_service.py medicao_views.py tests/test_fase9_assinatura_medicao.py
git commit -m "feat(fase9a): medicao assinada vira imutavel

fechar_medicao recusa reabertura e as rotas de edicao de item recusam
escrita. Sem isso, alterar o valor depois da assinatura invalidaria
silenciosamente o hash gravado — o cenario exato que a assinatura
existe para impedir. conferir_integridade() denuncia divergencia."
```

---

## Task 13: Comprovante de assinatura

**Files:**
- Modify: `portal_obras_views.py` (rota do comprovante)
- Modify: `medicao_views.py` (visão interna)
- Create: `templates/portal/portal_comprovante_assinatura.html`
- Test: `tests/test_fase9_assinatura_medicao.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

```python
def test_comprovante_mostra_hash_data_ip_e_declaracao():
    with app.app_context():
        admin, obra, medicao = _obra_com_medicao()
        a = _assinar(medicao, obra, admin.id)
        from utils.portal_acesso import emitir_acesso
        token, _ = emitir_acesso(obra=obra, admin_id=admin.id,
                                 escopos=[EscopoPortal.LER], dias_validade=90)
        db.session.commit()
        mid, hash_esperado = medicao.id, a.documento_hash

    r = app.test_client().get(f'/portal/obra/{token}/medicao/{mid}/comprovante')
    assert r.status_code == 200
    corpo = r.get_data(as_text=True)
    assert hash_esperado in corpo
    assert '203.0.113.1' in corpo
    assert 'MP 2.200-2/2001' in corpo
    assert 'João' in corpo


def test_comprovante_de_medicao_nao_assinada_devolve_404():
    from utils.portal_acesso import emitir_acesso

    with app.app_context():
        admin, obra, medicao = _obra_com_medicao()
        token, _ = emitir_acesso(obra=obra, admin_id=admin.id,
                                 escopos=[EscopoPortal.LER], dias_validade=90)
        db.session.commit()
        mid = medicao.id

    r = app.test_client().get(f'/portal/obra/{token}/medicao/{mid}/comprovante')
    assert r.status_code == 404


def test_comprovante_denuncia_documento_alterado():
    from utils.portal_acesso import emitir_acesso

    with app.app_context():
        admin, obra, medicao = _obra_com_medicao()
        _assinar(medicao, obra, admin.id)
        medicao.valor_a_faturar_periodo = 1.00   # alteração fora do fluxo
        token, _ = emitir_acesso(obra=obra, admin_id=admin.id,
                                 escopos=[EscopoPortal.LER], dias_validade=90)
        db.session.commit()
        mid = medicao.id

    r = app.test_client().get(f'/portal/obra/{token}/medicao/{mid}/comprovante')
    corpo = r.get_data(as_text=True).lower()
    assert 'diverge' in corpo or 'alterado' in corpo, (
        'o comprovante escondeu que o documento mudou depois da assinatura')
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase9_assinatura_medicao.py -v -k comprovante
```

Esperado: 404 nas três — a rota não existe.

- [ ] **Step 3: Acrescente a rota em `portal_obras_views.py`**

```python
@portal_obras_bp.route('/obra/<token>/medicao/<int:medicao_id>/comprovante')
@limiter.limit("60 per hour")
@portal_token_required(EscopoPortal.LER)
def comprovante_assinatura(token: str, medicao_id: int):
    """Comprovante da assinatura — o artefato que o cliente guarda.

    Legível com o token de LEITURA (não o de assinatura, que já foi
    queimado no ato). Mostra o hash, a data/hora UTC, o IP, o
    dispositivo, a declaração exata e uma conferência de integridade
    contra o estado ATUAL do documento — se divergir, aparece. Esconder
    divergência transformaria o comprovante em decoração.
    """
    from services.assinatura_documento import (
        assinatura_de, conferir_integridade, snapshot_medicao,
    )

    obra = _obra_do_request()
    medicao = MedicaoObra.query.filter_by(id=medicao_id, obra_id=obra.id).first()
    if not medicao:
        abort(404)

    assinatura = assinatura_de('medicao_obra', medicao.id, papel='cliente')
    if assinatura is None:
        abort(404)

    config = ConfiguracaoEmpresa.query.filter_by(admin_id=obra.admin_id).first()
    return render_template(
        'portal/portal_comprovante_assinatura.html',
        obra=obra, medicao=medicao, token=token, assinatura=assinatura,
        integridade=conferir_integridade(assinatura, snapshot_medicao(medicao)),
        config_empresa=config,
        nome_empresa=config.nome_empresa if config else 'Construtora',
    )
```

- [ ] **Step 4: Crie `templates/portal/portal_comprovante_assinatura.html`**

```html
{% extends 'portal/_base.html' %}
{% block portal_content %}
<div class="card-portal" style="max-width:760px;margin:2rem auto;padding:2rem">
  <div style="text-align:center;margin-bottom:1.5rem">
    <i class="fas fa-circle-check" style="font-size:2.5rem;color:#1e9e5a"></i>
    <h1 style="font-size:1.35rem;margin-top:.75rem">Comprovante de assinatura</h1>
    <p style="color:#5a6473">Medição nº {{ '%03d'|format(medicao.numero) }} ·
       {{ obra.nome }}</p>
  </div>

  <table class="table table-sm">
    <tr><th style="width:38%">Assinado por</th>
        <td>{{ assinatura.signatario_nome }}</td></tr>
    <tr><th>CPF/CNPJ informado</th>
        <td>{{ assinatura.signatario_documento or '—' }}</td></tr>
    <tr><th>Data e hora (UTC)</th>
        <td>{{ assinatura.assinado_em.strftime('%d/%m/%Y às %H:%M:%S') }}</td></tr>
    <tr><th>Endereço IP</th><td><code>{{ assinatura.ip or '—' }}</code></td></tr>
    <tr><th>Dispositivo</th>
        <td style="font-size:.8rem;word-break:break-all">
          {{ assinatura.user_agent or '—' }}</td></tr>
    <tr><th>Identificador do documento</th>
        <td><code style="word-break:break-all">{{ assinatura.documento_hash }}</code></td></tr>
  </table>

  {% if integridade.integro %}
  <div style="background:#eaf7ef;border-left:4px solid #1e9e5a;padding:.9rem 1rem;
              border-radius:6px;margin:1.25rem 0;font-size:.9rem">
    <strong>Documento íntegro.</strong> O conteúdo da medição continua
    idêntico ao que foi assinado.
  </div>
  {% else %}
  <div style="background:#fdecec;border-left:4px solid #d33;padding:.9rem 1rem;
              border-radius:6px;margin:1.25rem 0;font-size:.9rem">
    <strong>Atenção: o documento foi alterado após a assinatura.</strong><br>
    O identificador atual (<code>{{ integridade.hash_atual }}</code>) diverge do
    que foi assinado. Procure a construtora antes de considerar esta medição
    válida.
  </div>
  {% endif %}

  <h2 style="font-size:1rem;margin-top:1.5rem">Declaração assinada</h2>
  <blockquote style="border-left:3px solid #d7dce3;padding-left:1rem;
                     color:#4a545f;font-size:.9rem;line-height:1.6">
    {{ assinatura.declaracao }}
  </blockquote>

  <p style="margin-top:1.5rem">
    <a href="{{ url_for('medicao.portal_pdf_extrato', token=token, medicao_id=medicao.id) }}"
       target="_blank" rel="noopener">
      <i class="fas fa-file-pdf"></i> Abrir o extrato da medição</a>
  </p>
  <p style="font-size:.78rem;color:#7a828e;margin-top:1rem">
    Assinatura eletrônica simples com registro de autoria, nos termos do
    art. 4º, I da Lei 14.063/2020 e do art. 10, §2º da MP 2.200-2/2001.
    Para imprimir ou salvar, use a função de impressão do navegador.
  </p>
</div>
{% endblock %}
```

- [ ] **Step 5: Mostre a assinatura na tela interna**

Em `templates/portal/_portal_medicoes.html`, dentro do bloco de cada medição, após o `pill` de status:

```html
                        {% set assin = assinaturas_medicao.get(m.id) %}
                        {% if assin %}
                        <a href="{{ url_for('portal_obras.comprovante_assinatura', token=token, medicao_id=m.id) }}"
                           class="pill pill-success" title="Assinada em {{ assin.assinado_em.strftime('%d/%m/%Y') }}">
                          <i class="fas fa-signature"></i> Assinada</a>
                        {% endif %}
```

E em `portal_obras_views.py`, dentro de `portal_obra`, antes do `render_template` (linha 323), monte o dicionário:

```python
    from models import Assinatura
    assinaturas_medicao = {
        a.documento_id: a
        for a in Assinatura.query.filter(
            Assinatura.documento_tipo == 'medicao_obra',
            Assinatura.obra_id == obra.id,
            Assinatura.papel == 'cliente',
        ).all()
    }
```

e passe `assinaturas_medicao=assinaturas_medicao` ao template.

- [ ] **Step 6: Rode os testes e o gate**

```bash
python -m pytest tests/test_fase9_assinatura_medicao.py -v
bash run_tests.sh --gate 2>&1 | tail -20
```

- [ ] **Step 7: Commit**

```bash
git add portal_obras_views.py templates/portal/ tests/test_fase9_assinatura_medicao.py
git commit -m "feat(fase9a): comprovante de assinatura com conferencia de integridade

Mostra hash, data/hora UTC, IP, dispositivo e a declaracao exata.
Compara o estado ATUAL do documento com o assinado e denuncia
divergencia em vermelho — esconder isso transformaria o comprovante em
decoracao."
```

---

## Task 14: Fecho de 9a — regressões e gate

**Files:**
- Test: `tests/test_fase9_portal_rotas.py` (acrescenta)

- [ ] **Step 1: Escreva os testes de regressão do achado**

```python
# ---------------------------------------------------------------------------
# Regressões da Fase 9a — o que não pode voltar
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('arquivo,padrao,descricao', [
    ('portal_obras_views.py', 'filter_by(token_cliente=',
     'resolução de token fora do resolver único'),
    ('medicao_views.py', "request.args.get('token'",
     'token na querystring (vai para o access log do gunicorn)'),
    ('views/obras.py', 'token_cliente = secrets.token_urlsafe',
     'geração automática de credencial sem autor, escopo nem prazo'),
    ('event_manager.py', 'token_cliente = secrets.token_urlsafe',
     'geração automática de credencial na aprovação de proposta'),
])
def test_padrao_da_fase_9a_nao_retorna(arquivo, padrao, descricao):
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(raiz, arquivo), encoding='utf-8') as fh:
        for i, linha in enumerate(fh, start=1):
            codigo = linha.split('#')[0]
            assert padrao not in codigo, (
                f'{arquivo}:{i} voltou a conter "{padrao}" — {descricao}')


def test_toda_rota_do_portal_passa_pelo_decorator():
    """Uma rota nova de portal sem decorator é o buraco reaberto."""
    from utils.portal_acesso import portal_token_required  # noqa: F401

    sem_protecao = []
    for regra in app.url_map.iter_rules():
        if '<token>' not in str(regra):
            continue
        if regra.endpoint.startswith('static'):
            continue
        view = app.view_functions[regra.endpoint]
        if not getattr(view, '_portal_escopo', None):
            sem_protecao.append(f'{regra.endpoint} ({regra})')
    assert not sem_protecao, (
        'rotas com <token> sem portal_token_required:\n'
        + '\n'.join(sem_protecao))


def test_assinatura_nao_existe_sem_o_endurecimento():
    """Trava de ordem: a Task 9 não vale sem as Tasks 1-8.

    Se a tabela `assinatura` existe mas `portal_acesso` não, alguém
    implementou a assinatura pulando o endurecimento — e a assinatura
    não prova nada nesse cenário.
    """
    from models import Assinatura, PortalAcesso, PortalEvento  # noqa: F401

    with app.app_context():
        for tabela in ('portal_acesso', 'portal_evento', 'assinatura'):
            existe = db.session.execute(db.text("""
                SELECT 1 FROM information_schema.tables
                WHERE table_name = :t LIMIT 1
            """), {'t': tabela}).fetchone()
            assert existe, f'tabela {tabela} não existe'
```

- [ ] **Step 2: Marque o escopo no decorator para o teste de cobertura**

Em `utils/portal_acesso.py`, dentro de `portal_token_required`, antes do `return wrapper`:

```python
        wrapper._portal_escopo = (escopo.value if isinstance(escopo, EscopoPortal)
                                  else str(escopo))
```

- [ ] **Step 3: Rode e confirme**

```bash
python -m pytest tests/test_fase9_portal_rotas.py -v -k "nao_retorna or decorator or endurecimento"
```

Esperado: PASSAM. Se `test_toda_rota_do_portal_passa_pelo_decorator` listar alguma rota, volte à Task 5 e decore-a.

- [ ] **Step 4: Rode o gate completo**

```bash
bash run_tests.sh --gate 2>&1 | tail -30
```

Esperado: verde. **Cole a linha final no commit e no documento de fecho** — a dívida de processo do R5 (`DEVOLUTIVA.md:189-198`) é explícita quanto a isso.

- [ ] **Step 5: Recontagem do achado**

```bash
python - <<'PY'
import main  # noqa
from app import app
rotas = []
for r in app.url_map.iter_rules():
    metodos = r.methods - {'HEAD', 'OPTIONS'}
    if not (metodos & {'POST', 'PUT', 'PATCH', 'DELETE'}):
        continue
    if '<token>' not in str(r):
        continue
    v = app.view_functions[r.endpoint]
    rotas.append((r.endpoint, str(r), getattr(v, '_portal_escopo', 'SEM ESCOPO')))
print(f'{len(rotas)} rotas de escrita por token:')
for e, u, esc in sorted(rotas):
    print(f'  {esc:<20} {e:<45} {u}')
PY
```

Esperado: 8 rotas, **nenhuma** com `SEM ESCOPO`. Cole a saída no documento de fecho — é a correção do número que o `ESTADO-ATUAL.md:111` publicou como "1".

- [ ] **Step 6: Commit**

```bash
git add utils/portal_acesso.py tests/test_fase9_portal_rotas.py
git commit -m "test(fase9a): travas de regressao do endurecimento do portal

Nenhuma rota com <token> pode existir sem portal_token_required —
verificado varrendo o url_map. Os quatro padroes mortos (resolucao de
token na mao, token na querystring, geracao automatica de credencial)
sao proibidos por teste de codigo-fonte.

Gate: <cole aqui a linha final de run_tests.sh --gate>
Rotas de escrita por token: 8, todas com escopo (era: 8, nenhuma)."
```

---

# PARTE 9b — Contratos, Google Drive e notificações

> **Profundidade deliberadamente menor.** As Tasks 15–21 trazem objetivo, arquivos, responsabilidades e critério de pronto — não o código linha a linha das Tasks 1–14. Motivo: 9b depende de decisões externas (credencial do Google, estrutura de pastas, layout de contrato) e de duas fases anteriores (2 e 6) que ainda não existem. Escrever código detalhado agora seria escrever ficção. **Leia a seção "Premissas a reconfirmar antes de executar" antes de abrir qualquer arquivo.**

## Objetivo

Três entregas independentes que compartilham um mesmo eixo — o dado da obra saindo da cabeça das pessoas e passando a existir como registro:

1. **Contrato como entidade.** Hoje `Obra.valor_contrato` (`models.py:254`) é um `Float` editável livremente, e `MedicaoContrato` (`models.py:5568`) é cronograma de faturamento, não documento. Não existem `Contrato`, aditivo, locação nem alerta de vencimento (confirmado por grep: zero ocorrências).
2. **Google Drive.** Zero integração hoje. `Lead.pasta` (`models.py:6760`) é `String(500)` digitado à mão. A entrega é: criar a árvore de pastas da obra automaticamente e registrar o vínculo — não sincronizar arquivo, não virar gerenciador de documentos.
3. **Notificações.** **A fundação já existe e não será reconstruída.** A entrega é acrescentar eventos ao catálogo e ligar o canal.

## Arquitetura

**Contrato.** `Contrato` é filho de `Obra` (1:1 na prática, N:1 no schema, para admitir contrato substitutivo). `ContratoAditivo` guarda delta de valor e de prazo, com motivo e data. `Contrato.valor_vigente` = valor original + soma dos aditivos aprovados — derivado, nunca digitado. `Obra.valor_contrato` continua existindo como **espelho de leitura** (o resto do sistema depende dele: `services/medicao_service.py:420`, `models.py:5578` no `MedicaoContrato.valor`, `views/dashboard.py` na margem), mantido em sincronia por listener e com a edição direta bloqueada na UI. Isso reaproveita a cadeia de aditivo da Fase 6 em vez de criar uma segunda.

**Drive.** Um cliente fino e isolado (`services/drive_client.py`) com as quatro operações que interessam (achar/criar pasta, subir arquivo, conceder permissão, montar link) e **nenhuma regra de negócio**. Acima dele, `services/drive_estrutura.py` conhece a árvore padrão por obra e é idempotente. O vínculo mora em `DriveVinculo(entidade_tipo, entidade_id, drive_file_id, url, criado_em)` — nunca em campo texto solto como `Lead.pasta`. Toda chamada é best-effort e assíncrona em relação ao request de negócio: **criar obra não pode falhar porque o Google está fora**.

**Notificações.** Nada novo de infraestrutura. `utils/webhook_dispatcher.py` já entrega com HMAC, fila (`WebhookEntrega`), retry 1m/5m/15m e painel `/admin/webhooks`. A entrega é: novos nomes na `WEBHOOK_EVENT_ALLOWLIST` (`utils/webhook_dispatcher.py:61-72`), novos helpers `emit_*` em `utils/catalogo_eventos.py`, novos JSONs em `n8n_workflows/`, novas linhas na tabela do `docs/notificacoes/README.md` §10, e um job diário de alerta de vencimento no molde de `notificacoes_cli.py`.

## Premissas a reconfirmar antes de executar

Nenhuma destas foi verificada — todas são condições externas ao código. **Confirme cada uma antes de abrir o arquivo correspondente; se alguma cair, a task muda de forma.**

| # | Premissa | Por que importa | Como confirmar |
|---|---|---|---|
| P1 | **A Fase 6 entregou versionamento e aditivo no orçamento.** | `ContratoAditivo` deve reusar aquela cadeia, não criar outra. Se a Fase 6 não entrou, a Task 18 constrói uma segunda modelagem de aditivo, que vai conflitar depois | `grep -n "class OrcamentoVersao\|origem_id\|class Aditivo" models.py` |
| P2 | **A Fase 2 entregou estados da Obra.** | O alerta de vencimento de contrato e o de locação só fazem sentido para obra em execução. Sem estado, o job dispara para obra encerrada | `grep -n "class ObraTransicaoEstado\|estado = db.Column" models.py` |
| P3 | **Existe uma conta Google Workspace do Cássio com Drive compartilhado (Shared Drive), não só um Drive pessoal.** | Conta de serviço **não tem cota de armazenamento própria**: arquivos criados por ela em "Meu Drive" ficam órfãos de proprietário e não têm onde morar. Shared Drive resolve. Sem Workspace, o desenho muda para OAuth por usuário | Perguntar. Verificar em `admin.google.com` se há Shared Drives |
| P4 | **Onde o segredo do Google vai morar.** | **O projeto já teve `SESSION_SECRET` e a senha do Postgres commitados, e eles estão no histórico do git para sempre** (`ESTADO-ATUAL.md:34`) — a rotação continua pendente do lado humano. Uma chave de conta de serviço é um JSON de ~2 KB que abre o Drive inteiro. Não pode virar arquivo no repositório | Decidir: variável de ambiente `GOOGLE_SERVICE_ACCOUNT_JSON` no painel EasyPanel (recomendado) vs. secret manager |
| P5 | **A estrutura de pastas padrão por obra.** | `DEVOLUTIVA.md:320` já perguntou e não teve resposta. Sem o template, a Task 19 inventa uma árvore que o Cássio vai refazer à mão | Pedir a lista de pastas de uma obra real já organizada |
| P6 | **Quem enxerga a pasta da obra no Drive.** | Compartilhar com o cliente é dado saindo para terceiro sob a conta da Veks. Compartilhar por link é pior. Decidir: só equipe interna, ou cliente por e-mail nominal | Perguntar |
| P7 | **O n8n está no ar e `N8N_WEBHOOK_URL` está configurado em produção.** | Sem isso o dispatcher é no-op silencioso (`utils/webhook_dispatcher.py:112-116`) e as notificações da Task 20 não saem — sem erro nenhum, o que é pior que falhar | `python -c "import os; print(bool(os.environ.get('N8N_WEBHOOK_URL')))"` no ambiente de produção; conferir `/admin/webhooks` |
| P8 | **A Evolution API está pareada com o WhatsApp da empresa.** | O `docs/notificacoes/README.md` §7 documenta o setup, mas nada prova que a instância existe e está conectada | `GET {{EVOLUTION_API_URL}}/instance/fetchInstances` |
| P9 | **O que é um "contrato" para a Veks: um PDF assinado ou um conjunto de cláusulas estruturadas?** | Decide se `Contrato` guarda campos (objeto, prazo, valor, reajuste, garantia) ou só metadados + arquivo. A `Proposta` já tem cláusulas estruturadas (`models.py:3140` `PropostaHistorico`, template de cláusulas configuráveis) — talvez o contrato seja a proposta aprovada + assinatura | Pedir um contrato real da Veks |
| P10 | **Locação de equipamento entra nesta fase?** | `DEVOLUTIVA.md:76` cita "aditivo, locação nem alerta de vencimento" juntos, mas locação é um domínio próprio (equipamento, período, diária, devolução). Pode dobrar o tamanho de 9b | Perguntar. **Recomendado: fica FORA de 9b**, vira fase própria |

---

## Task 15: `Contrato` e `ContratoAditivo` — modelo e migration 306

**Files:**
- Modify: `models.py` — `Contrato` (obra_id, numero, objeto, valor_original, data_assinatura, data_inicio, data_fim_prevista, indice_reajuste, status, arquivo_drive_id, admin_id) e `ContratoAditivo` (contrato_id, numero, tipo `valor|prazo|escopo`, delta_valor, delta_dias, motivo, data, aprovado_por_usuario_id, orcamento_versao_id → Fase 6)
- Modify: `migrations.py` — migration **306**, aditiva, tabelas nascem vazias
- Test: `tests/test_fase9b_contrato.py`

**Responsabilidades:** `Contrato.valor_vigente` é property derivada (`valor_original` + soma dos aditivos com `aprovado_em is not None`). `ContratoAditivo` **nunca** grava valor absoluto — só delta, para que a cadeia seja auditável e reversível. Unique `(contrato_id, numero)`.

**Critério de pronto:** teste provando que dois aditivos de +R$10.000 e −R$3.000 sobre um contrato de R$250.000 dão `valor_vigente == 257000`; teste provando que aditivo não aprovado não conta; teste de tenant (aditivo de outro `admin_id` não entra na soma).

**Risco:** P1 e P9. Se o contrato for "a proposta aprovada + assinatura", `Contrato` vira uma tabela fina apontando para `Proposta` e a maior parte desta task some — **confirme P9 antes de escrever o modelo**.

---

## Task 16: `Obra.valor_contrato` vira espelho do contrato vigente

**Files:**
- Create: `services/contrato_service.py` — `valor_vigente(contrato)`, `aplicar_aditivo(contrato, ...)`, `sincronizar_obra(contrato)`, `extrato_contrato(contrato)`
- Modify: `models.py` — listener `after_flush` em `ContratoAditivo` chamando `sincronizar_obra`
- Modify: `views/obras.py` — bloqueia a edição direta de `valor_contrato` quando existe `Contrato` para a obra
- Modify: `templates/obras/obra_form.html` — campo vira read-only com link para o contrato
- Test: `tests/test_fase9b_contrato.py` (acrescenta)

**Responsabilidades:** `Obra.valor_contrato` continua sendo a fonte que o resto do sistema lê — `MedicaoContrato.valor` (`models.py:5578-5581`), `portal_obras_views.py:523` no cálculo da medição, `services/medicao_service.py:420` no PDF, a margem do dashboard. Mudar todos esses pontos seria uma refatoração transversal fora do escopo. O que muda é **quem escreve**: passa a ser só o listener.

**Critério de pronto:** aprovar um aditivo move `Obra.valor_contrato` e deixa trilha; tentar editar `valor_contrato` pela tela de obra com contrato existente é recusado, provado por teste; a medição gerada depois do aditivo usa o valor novo.

**Risco:** **alto**. `valor_contrato` é lido em muitos lugares e o listener roda dentro do flush — um erro ali derruba transações de negócio. Mitigação: o listener só escreve, nunca calcula do zero (delega a `contrato_service`), e tem `try/except` com log; o valor é recalculável a qualquer momento por CLI.

---

## Task 17: Alertas de vencimento de contrato

**Files:**
- Create: `contratos_views.py` — blueprint `contratos`: listar, detalhar, registrar aditivo, extrato
- Modify: `main.py` — registro do blueprint (**abaixo da linha 386 de `app.py`; a ordem de import é contrato não declarado**, `ESTADO-ATUAL.md:132-135`)
- Modify: `notificacoes_cli.py` — comando `flask emitir-contratos-vencendo`, no molde exato de `emitir_propostas_expirando` (janela em dias, dedup por `WebhookEntrega` do dia, `--dry-run`)
- Test: `tests/test_fase9b_contrato.py` (acrescenta)

**Responsabilidades:** o job é varredura, não reação — igual ao `proposta.expirando` (`docs/notificacoes/README.md` §10.2). Idempotência por dia consultando `webhook_entrega`, com o mesmo fallback Python para dialeto sem operador JSON (`notificacoes_cli.py:52-70`).

**Critério de pronto:** rodar o job duas vezes no mesmo dia emite um evento só, provado por teste; contrato de obra encerrada não dispara (depende de P2 — sem a Fase 2, filtra por `Obra.ativo`).

---

## Task 18: Aditivo conectado ao orçamento versionado da Fase 6

**Files:**
- Modify: `models.py` — `ContratoAditivo.orcamento_versao_id` (FK para a entidade de versão da Fase 6)
- Modify: `services/contrato_service.py` — `aplicar_aditivo` passa a exigir a versão de orçamento que o justifica
- Modify: `propostas_consolidated.py` / `event_manager.py` — o fluxo de revisão de proposta (o mesmo do bug R1, `DEVOLUTIVA.md:137-150`) passa a **gerar aditivo** em vez de mexer em `valor_contrato` direto
- Test: `tests/test_fase9b_contrato.py` (acrescenta)

**Responsabilidades:** fechar o laço da regra 5.4 da especificação. É a task que amarra 9b à Fase 6.

**Critério de pronto:** aprovar a v2 de uma proposta de obra em execução cria um `ContratoAditivo` vinculado à versão de orçamento, move `Obra.valor_contrato` e deixa trilha — sem criar obra duplicada (o R1 já corrigido na Fase 0 continua verde).

**Risco:** **bloqueada por P1.** Se a Fase 6 não entrou, **pule esta task e deixe `orcamento_versao_id` nullable e vazio** — as Tasks 15–17 funcionam sem ela.

---

## Task 19: Google Drive — cliente, estrutura de pastas e vínculo

**Files:**
- Create: `services/drive_client.py` — quatro operações, nenhuma regra: `obter_ou_criar_pasta(nome, pai_id)`, `subir_arquivo(caminho, nome, pasta_id)`, `conceder_permissao(file_id, email, papel)`, `url_de(file_id)`. Autenticação por `google.oauth2.service_account.Credentials.from_service_account_info(json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']))`, escopo `https://www.googleapis.com/auth/drive.file`
- Create: `services/drive_estrutura.py` — `garantir_estrutura_obra(obra)`, idempotente, lendo a árvore de P5
- Modify: `models.py` — `DriveVinculo(entidade_tipo, entidade_id, drive_file_id, url, admin_id, criado_em)` + unique `(entidade_tipo, entidade_id, drive_file_id)`
- Modify: `migrations.py` — migration **307**
- Modify: `views/obras.py` — botão "criar pastas no Drive", **nunca no caminho crítico de criar obra**
- Modify: `requirements.txt` — `google-api-python-client`, `google-auth`
- Modify: `.gitignore` — `*service-account*.json`, `*credentials*.json`
- Test: `tests/test_fase9b_drive.py` — com o cliente **mockado**; nenhum teste do gate pode chamar a API do Google

**Responsabilidades e restrições de segurança — leia antes de escrever a primeira linha:**

1. **O segredo nunca vira arquivo no repositório.** Só `os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']`. O projeto já perdeu `SESSION_SECRET` e a senha do Postgres para o histórico do git (`ESTADO-ATUAL.md:34`), e essa rotação **ainda está pendente**. Escreva um teste que falha se algum `*.json` com `"private_key"` estiver rastreado pelo git.
2. **Escopo `drive.file`, não `drive`.** `drive.file` limita a conta de serviço aos arquivos que ela mesma criou — que é exatamente o caso de uso. `drive` daria acesso ao Drive inteiro da organização com uma chave que mora numa variável de ambiente.
3. **Shared Drive obrigatório** (P3): conta de serviço não tem cota de armazenamento própria.
4. **Ausente = desligado.** Sem `GOOGLE_SERVICE_ACCOUNT_JSON`, `drive_client` é no-op silencioso — mesmo padrão de `utils/webhook_dispatcher.py:112-116`. O sistema tem que rodar sem Drive.
5. **Nunca no caminho crítico.** Criar obra não pode falhar porque a API do Google está fora. A chamada é botão explícito ou job assíncrono; falha vira flash de aviso, não 500.
6. **Nada de sincronização bidirecional.** O SIGE cria pastas e sobe arquivo; não lê, não observa, não reconcilia. Sincronização é um projeto próprio.

**Critério de pronto:** `garantir_estrutura_obra` chamada duas vezes cria as pastas uma vez (idempotência provada com mock); sem a variável de ambiente, tudo devolve `None` sem exceção; nenhum teste do `--gate` faz chamada de rede; `git ls-files | grep -i 'service.account'` vazio.

**Risco:** P3, P4, P5, P6 todos abertos. **Não comece esta task com qualquer um deles em aberto** — a árvore de pastas errada custa retrabalho manual em todas as obras já criadas.

---

## Task 20: Notificações — estender o catálogo, não construir motor

**Files:**
- Modify: `utils/webhook_dispatcher.py:61-72` — acrescentar à `WEBHOOK_EVENT_ALLOWLIST`: `obra.medicao_assinada`, `obra.medicao_aguardando_assinatura`, `contrato.vencendo`, `contrato.aditivo_registrado`, `obra.portal_link_emitido`
- Modify: `utils/catalogo_eventos.py` — helpers `emit_obra_medicao_assinada(medicao, admin_id, assinatura)`, `emit_obra_medicao_aguardando_assinatura(medicao, admin_id, url)`, `emit_contrato_vencendo(...)`, `emit_contrato_aditivo_registrado(...)`, todos no padrão existente (`_safe_emit`, `_payload_obra_basico`, try/except, best-effort, **depois do commit**)
- Create: `n8n_workflows/obra_medicao_assinada.json`, `contrato_vencendo.json` — copiados de `obra_medicao_publicada.json` e adaptados
- Modify: `docs/notificacoes/README.md` — novas linhas na tabela §10 e blocos de payload em §10.1, seguindo o roteiro de 6 passos da §11
- Test: `tests/test_fase9b_notificacoes.py`

**Responsabilidades:** **nada de infraestrutura nova.** O canal existe, entrega com HMAC, tem fila com retry 1m/5m/15m, painel de reenvio por tenant e 8 workflows de exemplo. Esta task é catálogo.

**Cuidado obrigatório com o payload:** `_payload_obra_basico` (`utils/catalogo_eventos.py:192-214`) inclui `portal_obra_url`, montado por `_portal_obra_url(obra)` (`:86`). Depois da Fase 9a, **`Obra.token_cliente` está NULL** (migration 305) e não há como montar essa URL — e mesmo que houvesse, **mandar um capability token para dentro de um webhook externo é reabrir o buraco pela porta dos fundos**. Ajuste `_portal_obra_url` para devolver `None` e documente. Se o n8n precisa mandar o link ao cliente, o link tem que ser **emitido no ato**, com escopo e prazo, e o `emit` recebe a URL como parâmetro explícito — nunca derivada de credencial persistida.

**Critério de pronto:** teste provando que `emit_obra_medicao_assinada` não levanta com o dispatcher desligado; teste provando que `_portal_obra_url` não devolve token; a tabela do `README.md` §10 lista 12 eventos; `/admin/webhooks` mostra as entregas novas.

**Risco:** P7 e P8. Sem `N8N_WEBHOOK_URL` em produção, tudo isso é no-op silencioso — funciona nos testes e não notifica ninguém. Confirme antes de declarar pronto.

---

## Task 21: Fecho de 9b — gate e documento

**Files:**
- Modify: `docs/notificacoes/README.md`
- Create: documento de fecho no padrão dos `docs/superpowers/plans/*-fecho.md`

- [ ] Rodar `bash run_tests.sh --gate` e colar a linha final — a dívida de processo do R5 (`DEVOLUTIVA.md:189-198`) é explícita: nenhuma fase é aceita sem isso.
- [ ] Rodar `python scripts/portal_acessos.py expirando --dias 30` e anexar a saída — é o primeiro relatório operacional da nova credencial.
- [ ] Registrar quais premissas P1–P10 foram confirmadas, quais foram contornadas e como.
- [ ] Registrar o que ficou fora: locação de equipamento (P10), login de cliente (D4), sincronização bidirecional com o Drive, provedor externo de assinatura (D1).

---

# Riscos desta fase

| ID | Risco | Impacto | Mitigação |
|---|---|---|---|
| **RA** | **Cliente perde acesso no deploy.** A migration 302 backfilla; se falhar parcialmente, alguns links morrem calados | Alto | A 302 é idempotente e a 305 **só zera `token_cliente` onde existe `portal_acesso`**, logando WARNING para as órfãs. Rode `scripts/portal_acessos.py backfill` (dry-run) antes de aplicar e confira o número |
| **RB** | **O token não é mais reexibível.** Tenant acostumado a copiar o link da tela vai reclamar | Médio | É o comportamento correto (é o que torna a rotação real) e a tela nova mostra prefixo, escopo, validade e último acesso, com "Gerar" a um clique. Avisar o Cássio **antes** do deploy |
| **RC** | **Rate-limit é por worker.** O `Limiter` usa `storage_uri="memory://"` (`app.py:238`) e o Dockerfile sobe `--workers 2` — o limite efetivo é o dobro do declarado | Baixo | Aceito e documentado. Migrar para Redis é decisão de infra, fora desta fase. Os limites foram escolhidos com folga |
| **RD** | **A assinatura pode ser contestada.** Assinatura eletrônica simples vale entre as partes, não contra terceiros | Médio | Decisão D1 explícita, com a base legal citada e a cláusula de aceite no contrato (Task 13.5, conteúdo jurídico). A camada de snapshot+hash é exatamente o que um provedor externo consome, se for preciso subir o nível depois |
| **RE** | **Ordem invertida.** Alguém implementa a assinatura pulando o endurecimento | Alto | `test_assinatura_nao_existe_sem_o_endurecimento` (Task 14) falha se as tabelas `portal_acesso`/`portal_evento` não existirem, e o CHECKPOINT está escrito no corpo do plano |
| **RF** | **Segredo do Google no repositório.** O projeto já perdeu dois segredos para o histórico do git, e a rotação continua pendente | Alto | P4 + `.gitignore` + teste que falha se `*.json` com `"private_key"` estiver rastreado. Só variável de ambiente |
| **RG** | **Token vazando em webhook.** `_payload_obra_basico` monta `portal_obra_url` com a credencial | Alto | Tratado explicitamente na Task 20: `_portal_obra_url` passa a devolver `None`; link para o cliente é emitido no ato, com escopo e prazo |
| **RH** | **`propostas` inteiro é CSRF-exempt** (`app.py:1035-1049`) — 35 rotas, não só as 3 do portal | Médio | **Fora do escopo desta fase**, mas registrado como dívida: a isenção do blueprint inteiro deveria virar isenção por rota, como `main.py:222-230` já faz para o portal de obra |

# Critérios de pronto da fase

**9a:**
- [ ] As 8 rotas de escrita por token exigem escopo nominal, provado pela varredura do `url_map` (Task 14, Step 5).
- [ ] Um token de leitura recebe **403** ao tentar aprovar compra, e a compra continua pendente — provado por teste.
- [ ] Token expirado devolve **410** com página explicativa; token desconhecido devolve **404**.
- [ ] Toda passagem pelo portal, concedida ou negada, deixa linha em `portal_evento` com IP e user-agent.
- [ ] `obra.token_cliente` e `proposta.token_cliente` estão vazios no banco; nenhum código vivo os lê.
- [ ] O token não aparece em log de auditoria nem no header `Referer`.
- [ ] `admin_id = 10` não existe mais em `propostas_consolidated.py`.
- [ ] O cliente assina a medição com nome, CPF/CNPJ, aceite explícito, e a linha guarda snapshot + SHA-256 + UTC + IP + user-agent + declaração.
- [ ] Assinar exige token de **uso único**, escopo `ASSINAR_MEDICAO`, 7 dias — que o backfill nunca concede.
- [ ] Medição assinada não aceita edição nem reabertura.
- [ ] O comprovante denuncia divergência quando o documento muda depois da assinatura.
- [ ] `bash run_tests.sh --gate` verde, linha final colada no fecho.

**9b:**
- [ ] `Contrato.valor_vigente` é derivado dos aditivos; `Obra.valor_contrato` é espelho e não é editável direto.
- [ ] Job de vencimento é idempotente por dia, provado por teste.
- [ ] Estrutura de pastas do Drive é idempotente e o sistema roda sem a credencial.
- [ ] Nenhum arquivo com `"private_key"` rastreado pelo git.
- [ ] Nenhum payload de webhook carrega capability token.
- [ ] Premissas P1–P10 registradas: confirmadas, contornadas ou explicitamente adiadas.
- [ ] `bash run_tests.sh --gate` verde, linha final colada no fecho.

# Mapa das migrações desta fase

| Nº | O quê | Ordem em `migrations_to_run` |
|---|---|---|
| **300** | tabela `portal_acesso` | 1ª |
| **301** | tabela `portal_evento` | 2ª |
| **304** | `configuracao_empresa`: `portal_token_dias_validade`, `portal_exige_assinatura_medicao` | 3ª — **antes da 302**, que lê a coluna |
| **302** | backfill dos tokens legados de obra e proposta | 4ª |
| **303** | tabela `assinatura` (genérica; generaliza `rdo_assinatura` se existir) | 5ª |
| **305** | zera `obra.token_cliente` e `proposta.token_cliente` | 6ª |
| **306** | `contrato` + `contrato_aditivo` (9b) | 7ª |
| **307** | `drive_vinculo` (9b) | 8ª |
| **308–309** | reservadas | — |

> O número da migração **não** determina a ordem de execução — a lista `migrations_to_run` determina. A 304 roda antes da 302 de propósito.
