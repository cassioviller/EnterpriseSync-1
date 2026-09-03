# Fase 9a/9b — as premissas medidas contra a árvore de hoje

> **Task 15** de `docs/superpowers/plans/2026-08-31-fecho-do-que-esta-aberto.md`.
> Documento de **veredito**, não de execução: nenhuma linha de código de
> produção ou de teste foi tocada para produzi-lo. Tudo aqui é `grep`,
> `sed`, `git log` e leitura.
>
> Árvore medida: branch `sdd/a-porta-irma`, HEAD `80c3bb31` (02/09).
> Plano medido: `docs/superpowers/plans/2026-07-21-fase-9-portal-assinatura-contratos.md`
> (4956 linhas, escrito em 21/07 sobre o commit `fb4147b`).

---

## Estado

**As dez premissas numeradas** da seção *"Premissas a reconfirmar antes de
executar"* (`2026-07-21-fase-9-portal-assinatura-contratos.md:4676-4687`):

| Veredito | Quantas | Quais |
|---|---|---|
| **VALE** | 3 | P1, P2, P10 |
| **CAIU** | 0 | — |
| **MUDOU DE FORMA** | 2 | P4, P9 |
| **NÃO VERIFICÁVEL AQUI** | 5 | P3, P5, P6, P7, P8 |

⚠️ **O placar de P1–P10 não é o placar da fase.** As dez premissas são, por
construção do próprio plano, *"condições externas ao código"* (`:4674`) — cinco
delas só se respondem perguntando ao dono ou medindo produção. **O que decide o
destino da fase são as premissas NÃO numeradas**, que o plano escreveu como
fato verificado e não como pergunta: a seção *"Contexto verificado no código"*
(`:23-108`), as decisões D1–D8 (`:126-186`) e a faixa de migrações (`:19`).
Dessas, o placar é outro:

| Veredito | Quantas | Quais |
|---|---|---|
| **VALE** | 5 | os cinco furos de segurança que sustentam a 9a (§3.1) |
| **CAIU** | 3 | D2, D7, e o cabeçalho *"nunca começada"* (§3.2) |
| **MUDOU DE FORMA** | 3 | D3/D4, Task 9, faixa de migrações (§3.3) |

🔴 **O achado que domina o documento não é uma premissa: é o cabeçalho.** O
plano diz *"🟡 ABERTO — trabalho real pendente — nunca começada"* (`:3`). É
falso. Duas frentes já executaram sob o rótulo **Fase 9a**, com migrations
registradas com esse nome — ver §3.2.

---

## 1. Onde procurei, o que achei, e por que este é o terceiro veredito

📖 O plano **existe** — ao contrário da opção C da VIGA-I, que a Task 1 deste
mesmo plano-mestre encontrou citada em quatro documentos e definida em nenhum.
Procurei por:

- `ls docs/superpowers/plans/ | grep -i "fase-9"` → **1 arquivo**,
  `2026-07-21-fase-9-portal-assinatura-contratos.md`.
- `grep -rln "Fase 9a\|Fase 9b\|fase-9-portal" docs/ *.md` → **25 documentos**
  citam a fase; um só a define.
- 🔬 `grep -rn "Fase 9a\|Fase 9b" --include=*.py --include=*.html` → **49
  ocorrências em código de produção vivo** (`main.py:227`,
  `portal_obras_views.py:26,517,652,871,1167,1176`, `models.py:1597,1611,1630,1647,1687,6465`,
  `services/rdo_ciencia_cliente.py:2`, `services/portal_signatario_auth.py:2`,
  `services/rdo_pdf_service.py:839,878,1003`, `services/contrato_obra.py:6`,
  `migrations.py:5518,5581,5584,5644,7845-7847`,
  `templates/obras/_signatarios_cliente.html:1`,
  `templates/portal/_portal_rdos.html:41`,
  `templates/obras/detalhes_obra_profissional.html:1516`).

⚠️ **Este documento é o TERCEIRO veredito de premissas desta fase**, não o
primeiro. O plano já carrega duas seções de revisão apensadas, na convenção da
casa:

| Seção | Commit | O que concluiu |
|---|---|---|
| `Revisão de premissas — 2026-07-23 (pós-Fase 3)` (`:4868-4916`) | `941e6738` | R1–R15. Quatro premissas do contexto QUEBRADAS pela Fase 3 (expiração, 180 dias, trilha, testes) |
| `Revisão de premissas — 2026-08-03 (pós-PLANO-NUCLEO)` (`:4917-4956`) | `a723babe` | P1–P10 medidas. *"A 9b precisa ser reescrita, e depois da Fase 6"*; *"a 9a segue como está, parcial"* |

O que este acrescenta: **a Fase 6 fechou** (24/08, `3f28c4db`), e com ela a
premissa que em 03/08 era 🟡 *"ainda não — mas a porta está aberta"* virou fato
consumado. Isso muda o veredito da 9b de "reescrever" para "quase toda ela já
foi entregue por outra fase".

---

## 2. As dez premissas numeradas, uma a uma

### P1 — "A Fase 6 entregou versionamento e aditivo no orçamento."

📖 `2026-07-21-fase-9-portal-assinatura-contratos.md:4678`:

> **A Fase 6 entregou versionamento e aditivo no orçamento.** `ContratoAditivo`
> deve reusar aquela cadeia, não criar outra. Se a Fase 6 não entrou, a Task 18
> constrói uma segunda modelagem de aditivo, que vai conflitar depois.
> Como confirmar: `grep -n "class OrcamentoVersao\|origem_id\|class Aditivo" models.py`

🔬 Medido hoje. A Fase 6 **fechou em 24/08** (`3f28c4db`;
`2026-07-21-fase-6-orcamento-versionado-aditivo.md:3`, ✅ FECHADO, 33/33
arquivos). O que ela entregou:

| Objeto | Onde | O que faz |
|---|---|---|
| `ObraContratoVersao` | `models.py:7589` | baseline versionado do valor de contrato, janela `[vigente_de, vigente_ate)`, `versao=1` é o original |
| `AditivoContrato` | `models.py:7688` | `tipo ∈ (acrescimo, supressao, prazo, misto)`, `motivo` NOT NULL, `valor_anterior`→`valor_novo`, `prazo_delta_dias`, ciclo `rascunho → aprovado \| cancelado`, `UNIQUE (obra_id, numero)` |
| `services/contrato_obra.py` | `abrir_versao:114`, `contrato_vigente:240`, `valor_vigente_em:248`, `definir_valor_contrato:262`, `abrir_aditivo:485`, `aprovar_aditivo:570`, `cancelar_aditivo:811` | a cadeia inteira, escritor único |
| `views/aditivos_views.py` | `:42` blueprint, `:56` listar, `:86` novo, `:154` aprovar, `:202` cancelar | a tela |
| migrations | 271, 272, 315 (`migrations.py:7381`), 316 (`:7415`) | o schema, já em produção |

**Veredito: VALE — e mais que isso, está CUMPRIDA.** A condição que a premissa
existia para garantir não só se realizou como se realizou por inteiro.

**O que isso faz com as tasks que dependiam dela:**

🔴 **A Task 15 da 9b some.** Ela mandava criar `Contrato` + `ContratoAditivo`
(`:4691-4702`). Executá-la hoje construiria **exatamente a segunda modelagem de
aditivo que a P1 foi escrita para impedir** — o texto da própria premissa nomeia
esse desfecho.

🔴 **A Task 16 some.** Ela mandava fazer `Obra.valor_contrato` virar espelho do
contrato vigente, via listener novo em `models.py` e bloqueio da edição em
`views/obras.py` (`:4706-4719`). 🔬 O espelho já existe e o escritor já é único:
`services/contrato_obra.py:236` (`obra.valor_contrato = float(nova.valor)`),
`:296`, `:321`. E a decisão que a matou está escrita **dentro do código**,
`services/contrato_obra.py:6-8`:

> Cássio, 03/08: o dono é a **Fase 6** — `ObraContratoVersao` +
> `services/contrato_obra.py` como cadeia única. A Fase 9b vira camada
> documental (PDF, assinatura, vencimento), **sem listener concorrente**.

⚠️ **A Task 18 encolhe a quase nada.** *"Aditivo conectado ao orçamento
versionado da Fase 6"* (`:4737`) — a conexão já é nativa:
`AditivoContrato.proposta_id` (`models.py:7735`) e `aprovar_aditivo` abrindo
versão nova com `origem_tipo='aditivo'`.

⚠️ **A Task 17 (alertas de vencimento) sobrevive inteira.** 🔬
`notificacoes_cli.py` tem **um** comando (`emitir_propostas_expirando`, `:130`);
nada varre contrato. E ela agora é *mais fácil*: o objeto a varrer existe.

---

### P2 — "A Fase 2 entregou estados da Obra."

📖 `:4679`: *"O alerta de vencimento de contrato e o de locação só fazem sentido
para obra em execução. Sem estado, o job dispara para obra encerrada."*

🔬 Medido: `class EstadoObra` em `models.py:29`; `class ObraTransicaoEstado` em
`models.py:511`; a coluna `Obra.estado` em `models.py:385-392`
(`String(20), nullable=False, default='planejamento', index=True`, com CHECK em
vez de ENUM nativo). A Fase 2 está ✅ **FECHADA desde 22/07**
(`2026-07-21-fase-2-maquina-estados-obra.md:3`).

**Veredito: VALE.** Confirmada em 03/08 e reconfirmada hoje — a única premissa
das dez que nunca oscilou. A Task 17 pode filtrar por `Obra.estado`.

---

### P3 — "Existe uma conta Google Workspace com Drive compartilhado."

📖 `:4680`: *"Conta de serviço não tem cota de armazenamento própria... Sem
Workspace, o desenho muda para OAuth por usuário."* Como confirmar: *"Perguntar.
Verificar em `admin.google.com`."*

🔬 O que dá para medir daqui: **nada mudou no repo em 43 dias.**
`grep -rln "GOOGLE_SERVICE_ACCOUNT\|googleapiclient\|google.oauth2\|drive_file_id\|DriveVinculo"`
sobre `*.py`, `*.txt` e `*.toml` → **zero arquivos**. `grep -i google` em
`requirements.txt` e `pyproject.toml` → **zero linhas**. `Lead.pasta`
(`models.py:8935`) continua `String(500), nullable=True`, digitado à mão —
exatamente como o plano descreveu em `:4661`.

**Veredito: NÃO VERIFICÁVEL AQUI.** É condição de um console externo
(`admin.google.com`), ao qual esta sessão não tem acesso. O que **é** verificável
e vale registrar: o repositório não deu um único passo nessa direção desde 21/07,
então nenhuma decisão foi tomada por fato consumado — a pergunta está intacta.

---

### P4 — "Onde o segredo do Google vai morar."

📖 `:4681`: *"O projeto já teve `SESSION_SECRET` e a senha do Postgres
commitados, e eles estão no histórico do git para sempre (`ESTADO-ATUAL.md:34`)
— **a rotação continua pendente do lado humano**."*

🔬 **A frase citada envelheceu.** `ESTADO-ATUAL.md:461`:

> ~~Rotacionar `SESSION_SECRET` e a senha do Postgres~~ — 🔴 **Decisão do
> Cássio, 03/08: NÃO rotacionar.** Sai da lista de pendências — não voltar a
> recomendar.

O **fato** que sustenta a premissa continua verdadeiro (`ESTADO-ATUAL.md:2007`
registra as senhas no histórico); o que mudou é o status: deixou de ser
"pendência" e virou "risco aceito por decisão".

**Veredito: MUDOU DE FORMA.** A revisão de 03/08 (`:4930`) já tinha visto isso e
concluiu que **o argumento fica mais forte, não mais fraco** — se a casa optou
por conviver com um segredo exposto no histórico, mais razão para o JSON do
Drive nunca encostar no repositório. Reconfirmo. A decisão em si (env var no
EasyPanel vs. secret manager) **segue aberta**, e é humana.

---

### P5 — "A estrutura de pastas padrão por obra."

📖 `:4682`: *"`DEVOLUTIVA.md:320` já perguntou e não teve resposta. Sem o
template, a Task 19 inventa uma árvore que o Cássio vai refazer à mão."*

🔬 `DEVOLUTIVA.md:322-323` — a pergunta nº 9 continua no arquivo, sem resposta
apensada: *"Google Drive: conta de serviço ou OAuth por usuário? E a estrutura
de pastas padrão por obra — você tem o template definido?"*. Conferido também
contra os dois documentos de decisão de 31/08 e 01/09
(`2026-08-31-decisoes-pendentes.md`, `2026-09-01-decisoes-respondidas.md`):
🔬 **nenhum dos dois contém uma decisão sobre Drive, pastas ou portal** — as
únicas ocorrências de "portal" ali são sobre miniatura de foto e sobre
`portal_obras_views.py:768`.

**Veredito: NÃO VERIFICÁVEL AQUI.** Pergunta ao dono, aberta há 43 dias.

---

### P6 — "Quem enxerga a pasta da obra no Drive."

📖 `:4683`: *"Compartilhar com o cliente é dado saindo para terceiro sob a conta
da Veks. Compartilhar por link é pior."*

🔬 Mesma medição de P5: sem vestígio no repo, sem resposta nos documentos de
decisão.

**Veredito: NÃO VERIFICÁVEL AQUI.**

⚠️ Nota que vale para quem for responder: **a casa já tem precedente sobre
identidade de terceiro no portal**, criado depois que a P6 foi escrita —
`ObraSignatarioCliente` (`models.py:1685`) é *"o responsável do cliente
autorizado a dar ciência nos RDOs de UMA obra"*, deliberadamente **não** um
`Usuario`. Se a resposta de P6 for "cliente por e-mail nominal", esse modelo já
é o lugar onde o e-mail mora.

---

### P7 — "O n8n está no ar e `N8N_WEBHOOK_URL` está configurado em produção."

📖 `:4684`: *"Sem isso o dispatcher é no-op silencioso
(`utils/webhook_dispatcher.py:112-116`) e as notificações da Task 20 não saem —
sem erro nenhum, o que é pior que falhar."*

🔬 **O mecanismo está confirmado, o ambiente não.** O código descrito continua
lá, só andou de linha: `get_webhook_url()` lê `os.environ["N8N_WEBHOOK_URL"]` e
devolve `None` quando vazio; `is_enabled()` é `get_webhook_url() is not None`.
A `WEBHOOK_EVENT_ALLOWLIST` tem hoje **10 eventos** — e um deles,
`obra.estado_alterado`, é da Fase 2, prova de que a allowlist é mesmo o ponto de
extensão que a Task 20 pretende usar (`:4780`, *"estender o catálogo, não
construir motor"*).

**Veredito: NÃO VERIFICÁVEL AQUI.** A pergunta é sobre a env de **produção**, e
esta sessão não tem `DATABASE_URL` nem env de produção — a mesma limitação que o
ledger da casa registrou para a medição do tenant fantasma
(`.superpowers/sdd/2026-08-31-fecho-do-que-esta-aberto/progress.md:227-232`).
O que posso afirmar: **o modo de falha descrito é real e continua real** — sem a
variável, o despachante desliga inteiro e em silêncio.

---

### P8 — "A Evolution API está pareada com o WhatsApp da empresa."

📖 `:4685`: *"O `docs/notificacoes/README.md` §7 documenta o setup, mas nada
prova que a instância existe e está conectada."* Como confirmar:
`GET {{EVOLUTION_API_URL}}/instance/fetchInstances`.

**Veredito: NÃO VERIFICÁVEL AQUI.** Exige chamada HTTP a um serviço externo com
credencial de produção. A premissa é literalmente uma medição de ambiente.

---

### P9 — "O que é um 'contrato' para a Veks: um PDF assinado ou um conjunto de cláusulas estruturadas?"

📖 `:4686`: *"Decide se `Contrato` guarda campos (objeto, prazo, valor,
reajuste, garantia) ou só metadados + arquivo."*

⚠️ A revisão de 03/08 (`:4935`) marcou esta como **a mais urgente das dez** e
deu o aviso exato: *"Levante P9 antes da Fase 6, não antes da 9b. Perguntar
tarde custa duas fases."*

🔬 **A Fase 6 rodou e a pergunta não foi levantada.** O que a Fase 6 modelou
responde P9 **por construção**, sem decisão registrada: o contrato da casa hoje
é *cláusulas estruturadas* — `ObraContratoVersao` (valor, vigência, origem) +
`AditivoContrato` (tipo, motivo NOT NULL, valor anterior/novo, delta de prazo,
`proposta_id` em `models.py:7735`). **Não há campo de arquivo, não há PDF do
contrato, não há `arquivo_drive_id`** — a coluna que a Task 15 previa
(`:4694`) nunca nasceu.

**Veredito: MUDOU DE FORMA.** Deixou de ser uma pergunta **estrutural** (que
decidia um schema) e virou uma pergunta de **camada documental** (o PDF assinado
é um anexo do que já existe, não uma modelagem concorrente).

🟢 **E o custo previsto não se materializou.** O aviso de 03/08 dizia que
perguntar tarde custaria refazer duas fases. Não custa: se a resposta for "o
contrato é o PDF assinado", isso **acrescenta** metadados e arquivo ao
`ObraContratoVersao` existente — é aditivo, não reescrita. Registro isto porque
um risco que a casa declarou e que **não** se realizou merece o mesmo rigor de
registro que um que se realiza.

---

### P10 — "Locação de equipamento entra nesta fase?"

📖 `:4687`: *"Locação é um domínio próprio... Pode dobrar o tamanho de 9b.
**Recomendado: fica FORA de 9b**, vira fase própria."*

🔬 `grep -rn "class Locacao\|locacao_equipamento" --include=*.py` (fora de
`archive/`) → **zero ocorrências**. Ninguém começou locação por nenhum caminho, e
nenhuma fase a reivindicou.

**Veredito: VALE.** A recomendação está intacta e não foi contrariada por
nenhum fato: locação continua fora, e continua sendo uma fase que não existe.

---

## 3. As premissas não numeradas — onde o veredito realmente se decide

O plano declara em `:4674` que as dez premissas são *"condições externas ao
código"*. Por isso mesmo, elas **não** decidem se a fase sobrevive: cinco só
respondem a uma conversa com o dono. Quem decide é o que o plano tratou como
**fato verificado** — e é lá que houve movimento.

### 3.1 Os cinco furos da 9a: todos VIVOS

Estas são as premissas que sustentam a **razão de existir** da Parte 9a. Medi
uma a uma:

| # | Premissa do plano | Veredito | 🔬 Medição de hoje |
|---|---|---|---|
| A | `Obra.token_cliente` é `String` **em claro no banco**, sem hash | **VALE** | `models.py:397` — `token_cliente = db.Column(db.String(255), unique=True)`. `Proposta.token_cliente` idem, `models.py:3784`, gerado no `__init__` (`:3857-3858`). 🔬 `grep "token_hash"` no repo → **zero** |
| B | Não há **escopo por ação**: quem tem o link pode tudo | **VALE** | Não existe coluna, enum nem parâmetro de escopo de portal. `_get_obra_by_token` (`portal_obras_views.py:89`) resolve a obra e pronto |
| C | CSRF **explicitamente desligado** nas rotas do portal | **VALE** | `main.py:220-226` (`csrf.exempt` uma a uma nas 7) + `:239` (`portal_pdf_extrato`) + `app.py` isentando o blueprint `propostas` inteiro |
| D | O token **vaza nos logs**; `_PATHS_SENSIVEIS` não cobre `/portal` | **VALE** | `utils/auditoria_acesso.py:29` — `_PATHS_SENSIVEIS = ('/login', '/alterar-senha', '/usuarios')`, **inalterado desde 21/07**. `:69-79` loga o `path` inteiro e sobe a WARNING quando anônimo. `Dockerfile:123` — `--access-logfile -` |
| E | **Zero** `Referrer-Policy` / CSP no app inteiro | **VALE** | 🔬 `grep -rn "Referrer-Policy\|Content-Security-Policy\|Talisman"` sobre `*.py`, `*.html` e `*.txt`, fora de `archive/` → **nenhuma ocorrência** |

⚠️ Dois furos citados no plano que **também continuam vivos**, e que a revisão
de 23/07 já tinha marcado (R10, R11):

- `medicao_views.py:524` — `token = request.args.get('token', '')`. O PDF do
  extrato **continua lendo a credencial da querystring**, o pior lugar
  possível (histórico do navegador, `Referer`, access log do gunicorn).
  🟢 Diferença desde 23/07: a rota **ganhou** a checagem de expiração
  (`:535-540`) que o R10 apontou como bypass. O furo de canal permanece; o de
  expiração fechou.
- `propostas_consolidated.py:2619` — `admin_id = 10`. 🔴 **Continua chumbado**,
  e sobreviveu à Onda 2 (o tenant), que matou os irmãos em
  `multitenant_helper`/`views`/`rdo`. O próprio arquivo denuncia o padrão no
  comentário de `:420-422` e mantém a ocorrência 2199 linhas abaixo.

**Consequência: a Parte 9a não perdeu razão de existir.** Nenhum dos cinco
furos estruturais foi fechado por outro caminho. O que mudou é *quanto* dela
falta — §4.

### 3.2 As três premissas que CAÍRAM

**🔴 C1 — O cabeçalho do plano: *"nunca começada"*. FALSO.**

📖 `2026-07-21-fase-9-portal-assinatura-contratos.md:3`:

> **Estado em 2026-08-25 (varredura de fecho):** 🟡 **ABERTO — trabalho real
> pendente — nunca começada.**

🔬 Medido por `git log -S`, não por checkbox:

| Commit | Data | O que entregou sob o rótulo |
|---|---|---|
| `851fd70b` *"fix(sec,fase3): fecha os furos do portal por token"* | 23/07 | `Obra.token_cliente_expira_em` (`models.py:404`) e `PortalAcessoEvento` (`models.py:6455`) — a **trilha em banco com IP e user-agent** que é o objeto da **Task 3** da 9a |
| `1fbc97c0` *"feat(rdo): ciencia do cliente com N responsaveis por obra (**Fase 9a**)"* | 29/07 | `ObraSignatarioCliente` (`models.py:1685`), `services/portal_signatario_auth.py`, `services/rdo_ciencia_cliente.py`, `templates/portal/ciencia_senha.html`, `templates/obras/_signatarios_cliente.html` |

E o registro de migrations nomeia a fase **explicitamente**
(`migrations.py:7845-7847`):

```
(267, "Fase 9a — obra_signatario_cliente + rdo_assinatura.signatario_cliente_id", ...)
(268, "Fase 9a — unicidade de assinatura por signatário (dois índices parciais)", ...)
(269, "Fase 9a — remove uq_rdo_assinatura_papel também quando é ÍNDICE", ...)
```

⚠️ **Precisão importa:** nenhuma das 21 Tasks do plano foi executada *como
escrita*. O que houve é diferente e mais insidioso — **o rótulo "Fase 9a" foi
consumido por trabalho de outras frentes**, e três migrations levam o nome dela
no registro permanente. Quem abrir o plano lê "nunca começada" e conclui que o
campo está limpo; 🔬 não está.

🔴 **É a terceira ocorrência deste apodrecimento nesta linhagem.** O ledger da
casa já registrou duas
(`.superpowers/sdd/2026-08-31-fecho-do-que-esta-aberto/progress.md:193-213`):
a Onda 1 (commit `d5a0e9bd`, *"estava fechada e o doc dizia aberta"*) e a
Onda 2 (*"O cabeçalho diz 'pronto para executar'. Está MENTINDO"*). Esta é a
mesma doença numa terceira forma: não "fechada e dita aberta", mas **parcialmente
consumida e dita virgem**.

**🔴 C2 — D7: *"Contrato como entidade nova? Recomendado: sim."* CAIU.**

📖 `:181`: *"`Contrato` + `ContratoAditivo`, com `Obra.valor_contrato` passando a
ser espelho do contrato vigente, mantido por listener."*

🔬 Derrubada pela **decisão nº 2 do PLANO-NUCLEO, de 03/08**, gravada
permanentemente no código em `services/contrato_obra.py:6-8`, e **executada**
pela Fase 6 em 24/08 (`3f28c4db`). O dono do `valor_contrato` é a Fase 6; a 9b
fica com *"PDF, assinatura, vencimento e Drive, sem listener concorrente"*.

Esta é a decisão que o plano-mestre nomeia na Task 15 (*"uma de suas decisões já
caiu"*). Confirmada, com a evidência atualizada: em 03/08 ela era decisão; hoje
é **schema aplicado em produção** (migrations 271/272/315/316).

**🟡 C3 — D2: *"validade default de 90 dias"*. CAIU (desde 23/07).**

🔬 A Fase 3 escolheu **180 dias**, e a revisão de 23/07 já registrou (R2,
`:4874`). Reconfirmo o mecanismo: `Obra.token_cliente_expira_em`
(`models.py:404`) existe e é honrado em três lugares
(`portal_obras_views.py:104-105`, `:120-121`, `medicao_views.py:535-536`).
🔬 `configuracao_empresa.portal_token_dias_validade` — a coluna que a Task 4
criaria — **não existe** (`grep` em `models.py` → zero).

### 3.3 As três que MUDARAM DE FORMA

**M1 — D3 e D4 (um token por destinatário / portal continua por token).**

📖 `:159` recomendava *"por destinatário... revogar o link do sócio que saiu sem
derrubar o do cliente... saber **quem** assinou quando há dois nomes"*. `:165`
recomendava *"continua por token — e a Fase 9a **não** constrói login de
cliente"*.

🔬 **Metade disso foi entregue, por outro caminho, e para outro documento.**
`ObraSignatarioCliente` (`models.py:1685`) é identidade **por destinatário**, com
`ativo`, e — apesar de D4 — **com senha**:
`services/portal_signatario_auth.py` faz `autenticar(obra, signatario_id, senha)`
e `definir_senha`, com trava de 10 falhas no modelo e rate-limit de
`5 per 15 minutes` por IP **+ signatário**
(`portal_obras_views.py:1205-1220`, aplicado em `:1317` e `:1506`).

⚠️ Ou seja: **a casa construiu login de cliente**, contra a recomendação de D4 —
mas apenas para o RDO, e apenas no fluxo de ciência. O token de obra continua
sendo a credencial de tudo o mais.

🟢 Isto é um ganho de projeto, não um problema: o desenho *"o reforço para as
ações graves não é senha, é separação de capacidade"* (`:169`) tem hoje um
precedente **implementado e em produção** para copiar, em vez de uma
recomendação em prosa.

**M2 — Task 9 (`Assinatura` genérica): o ramo condicional virou o ramo real.**

📖 `:198` escreveu o condicional com precisão: *"Se a Fase 5 for executada antes
desta e criar `RDOAssinatura` **específica do RDO**, a Task 9 **não cria uma
segunda tabela**: ela generaliza a existente."*

🔬 Foi exatamente o que aconteceu, e um passo além. A Fase 5 fechou
(`2026-07-21-fase-5-rdo-ciclo-vida-assinatura.md:3`, ✅, 19/19) e criou
`RDOAssinatura` (`models.py:1588`) com `hash_conteudo` SHA-256, `algoritmo`,
`provedor` (default `'interno'`, com `referencia_externa` reservada para
Clicksign/D4Sign), `assinado_em` do servidor, `ip`, `user_agent`,
`nome_signatario`/`cargo_signatario` como **snapshot**. A base jurídica
(MP 2.200-2/2001, art. 10 §2º) está escrita no docstring `:1590-1597` — e o
docstring **aponta para esta fase**: *"o que é oponível a terceiro (medição
assinada pelo cliente) fica para a Fase 9a"*.

E as migrations 267/268/269, rotuladas "Fase 9a", **já generalizaram parte
dela** (`signatario_cliente_id`, dois índices parciais para N signatários).

**Veredito: MUDOU DE FORMA — para melhor.** A Task 9 deixa de ser "criar tabela
genérica" e vira "acrescentar `documento_tipo`/`documento_id`/`snapshot` a uma
tabela madura, testada e em produção". 🔬 O que **falta** é real:
`grep -rn "documento_tipo"` → **zero**; não há assinatura de medição no repo.

**M3 — A faixa de migrações reservada 300–309 encolheu para 300–307.**

📖 `:19`: *"**Faixa de migrações reservada:** **300–309**."*

🔬 Duas foram gastas. `migrations.py:7874` registra a 308 e explica a invasão
com todas as letras:

> *"308 e nao 300: 300-307 e faixa da Fase 9 e 290-295 da Fase 8, nenhuma
> aplicada"*

E `:7875` gastou a 309. A árvore está hoje na **318**
(`_migration_318_flag_folha_rateio_encargos`, `migrations.py:7540`), e o
plano-mestre já comprometeu **319/320/321** (T8) e **322/323** (T12) — ver o
Ruling C1 do ledger (`progress.md:571-585`).

**Veredito: MUDOU DE FORMA.** 🟢 A 9a cabe (precisa de 300–305) e a 9b cabe
(306–307). O que sumiu foram as duas *reservas*, 308–309. ⚠️ Mas o
precedente do Ruling C1 vale aqui inteiro: **a faixa é conferida no momento de
escrever, contra a lista viva do registry — nunca contra o número do plano.**

---

## 4. O que sobra, task a task

Medido por existência de objeto na árvore, nunca por checkbox.

### Parte 9a — 14 tasks

| Task | Objeto | Estado hoje | Evidência |
|---|---|---|---|
| 1 | `PortalAcesso` (token hasheado, escopado) | **PENDENTE** | `grep "class PortalAcesso\b"` → zero. Só `PortalAcessoEvento` |
| 2 | `utils/portal_acesso.py` (resolver único) | **PENDENTE** | arquivo ausente |
| 3 | Trilha `PortalEvento` | 🟢 **ENTREGUE por outro caminho** | `PortalAcessoEvento` `models.py:6455` (obra, admin, ação, alvo, **IP, UA**, JSON), migration 247, commit `851fd70b`. Vira *estender*, não *criar* — como o R3 de 23/07 já mandava |
| 4 | Backfill + flags por tenant | **PENDENTE**, com ajuste | `portal_token_dias_validade` não existe. E o backfill **não pode carimbar 90 dias chapados**: tem de herdar `token_cliente_expira_em` (R1/R2), senão encurta a validade de 180 que a Fase 3 prometeu |
| 5 | Decorator nas 11 rotas | **PENDENTE**, e a matriz cresceu | R5 já contava 12–13 endpoints; hoje o portal ganhou ainda as rotas de ciência (`portal_obras_views.py:1317`, `:1506`) |
| 6 | Parar de vazar token + `Referrer-Policy` | **PENDENTE, intacta** | `_PATHS_SENSIVEIS` inalterado (`utils/auditoria_acesso.py:29`); zero `Referrer-Policy` no repo |
| 7 | Emissão/revogação pela tela | **PARCIAL, por analogia** | `templates/obras/detalhes_obra_profissional.html:1516` já tem o painel *"ACESSO DO CLIENTE"* — mas para **signatários**, não para tokens |
| 8 | Aposentar `token_cliente` | **PENDENTE** | `models.py:397` e `:3784` vivos; quatro pontos de emissão idem (R13) |
| 9 | `Assinatura` genérica | 🟡 **MUDOU DE FORMA** | ver M2 |
| 10–13 | Snapshot, hash, emissão, imutabilidade e comprovante **da medição** | **PENDENTES, sem substituto** | zero `documento_tipo`; `MedicaoObra` (`models.py:7447`) sem campo de assinatura; PDF ainda gerado do estado vivo |
| 14 | Fecho e gate | **PENDENTE** | — |

**Placar da 9a: 1 entregue por outro caminho, 1 parcial, 1 mudou de forma, 11
pendentes.** ⚠️ E há um risco novo que nenhuma revisão anterior nomeou: **N1 do
03/08 ficou mais forte** — a fórmula da medição do portal mudou (`a2321503`), e
uma assinatura de medição hoje assina um número diferente do que assinaria em
julho. O documento assinado precisa dizer **qual** fórmula gerou o número.

### Parte 9b — 7 tasks

| Task | Objeto | Estado hoje |
|---|---|---|
| 15 | `Contrato` + `ContratoAditivo` | 🔴 **SOME** — é a Fase 6 (`models.py:7589`, `:7688`) |
| 16 | `valor_contrato` vira espelho | 🔴 **SOME** — `services/contrato_obra.py:236`, decisão nº 2 |
| 17 | Alertas de vencimento | 🟢 **SOBREVIVE inteira**, e ficou mais fácil |
| 18 | Aditivo ligado ao orçamento versionado | 🟡 **QUASE SOME** — a ligação é nativa (`models.py:7735`) |
| 19 | Google Drive | 🟡 **SOBREVIVE, bloqueada** por P3, P5 e P6 — três perguntas humanas |
| 20 | Notificações (estender catálogo) | 🟢 **SOBREVIVE**, bloqueada por P7 (env de produção) |
| 21 | Fecho e gate | — |

**Placar da 9b: 2 tasks somem, 1 quase some, 3 sobrevivem — e das 3 que
sobrevivem, 2 estão bloqueadas por perguntas que só o dono responde.**

---

## Veredito

### A recomendação: **REESCREVER, partida em duas — e a 9b encolheu ~60%**

Não *"reabrir como está"*, e não *"enterrar"*. As três opções foram pesadas:

**Por que não reabrir como está.** 🔴 O plano manda executar coisas que
construiriam duplicatas do que já existe (Tasks 15 e 16 → segunda modelagem de
aditivo, o desfecho que a própria P1 foi escrita para impedir), e afirma no
cabeçalho um estado que a árvore contradiz (§3.2/C1). Um plano cujo cabeçalho
mente é o defeito que esta linhagem já pagou três vezes.

**Por que não enterrar.** 🟢 O plano-mestre autoriza riscar como resultado
válido (`2026-08-31-fecho-do-que-esta-aberto.md`, Step 3-b: *"isto é resultado
válido e final, não fracasso"*), mas **a evidência não sustenta o enterro**. Os
cinco furos de segurança que dão razão à 9a estão **todos vivos e medidos hoje**
(§3.1) — token em claro, zero escopo, CSRF desligado, token no log, zero
`Referrer-Policy`. Riscar a fase não fecha nenhum deles; só apaga o único
documento da casa que os descreve com evidência linha a linha. E a assinatura de
medição — o entregável de maior valor da fase — não tem substituto: `MedicaoObra`
segue sem campo de assinatura, e o docstring de `RDOAssinatura:1595-1597` aponta
nominalmente para cá.

**Por que reescrever, e em duas peças separadas:**

> **9a → plano novo, quase do mesmo tamanho.** 11 das 14 tasks seguem
> pendentes e sem substituto. O que muda não é o escopo, é o **ponto de
> partida**: a Task 3 estende `PortalAcessoEvento` em vez de criar tabela; a
> Task 9 estende `RDOAssinatura` em vez de criar tabela; a Task 4 herda os 180
> dias da Fase 3 em vez de impor 90; a Task 5 cobre uma matriz de rotas maior. O
> plano de 21/07 vira **histórico e fonte de evidência**, não roteiro.
>
> 🟢 **E a 9a hoje é mais barata do que era em julho**, porque
> `ObraSignatarioCliente` + `portal_signatario_auth` já são o precedente
> implementado de identidade por destinatário no portal — o que em julho era
> recomendação em prosa (D3/D4) hoje é código em produção para copiar.
>
> **9b → plano novo bem menor: de 7 tasks para 3.** As Tasks 15, 16 e 18
> saem (a Fase 6 as entregou); sobram 17 (alerta de vencimento — pronta para
> executar, sem bloqueio), 19 (Drive — bloqueada por P3/P5/P6) e 20
> (notificações — bloqueada por P7). 🔬 Em massa de trabalho isso é **~60%
> de encolhimento**, e o que resta **não é mais estrutural**: é a "camada
> documental" que a decisão nº 2 nomeou.
>
> ⚠️ **A 9b não deve virar um plano único**, e sim ficar suspensa por
> pergunta: a Task 17 executa hoje; as Tasks 19 e 20 não devem virar plano
> antes das respostas de P3/P5/P6/P7 — escrever tasks detalhadas sobre uma
> árvore de pastas desconhecida é escrever ficção, como o próprio plano
> advertiu em `:4654`.

### O que o dono precisa decidir — e é dele a escolha, não minha

Este documento mede; não decide. Quatro coisas ficam para o dono:

1. **Reescrever, reabrir ou enterrar.** Minha recomendação é reescrever partida
   em duas, pelo argumento acima. Se a prioridade da casa for outra, "enterrar a
   9b e manter só a 9a" é uma leitura defensável da mesma evidência — a 9b
   encolhida não fecha nenhum furo de segurança.
2. **As quatro perguntas externas que ninguém pode responder daqui:** P3
   (Shared Drive), P5 (árvore de pastas), P6 (quem enxerga a pasta), P7 (n8n em
   produção) — mais P8 (Evolution). Elas estão abertas há 43 dias e **bloqueiam
   2 das 3 tasks que sobram da 9b**.
3. **P9, agora que a Fase 6 já respondeu por construção:** o contrato da Veks
   ganha um PDF assinado por cima do que existe, ou o modelo estruturado basta?
   A resposta é aditiva — não custa mais refazer fase nenhuma.
4. 🔴 **O cabeçalho do plano de 21/07 precisa do carimbo de correção**, no mesmo
   movimento que o commit `d5a0e9bd` fez para a Onda 1 e o commit `b13e23c9`
   para a Onda 2. **Não o apliquei**: este documento tinha ordem de não editar
   nada além de si mesmo. Fica registrado como pendência nomeada, com a
   evidência de §3.2 pronta para ser copiada.

### O que este veredito NÃO afirma

- Não afirma que a 9a foi *executada*. Afirma que o **rótulo** dela foi
  consumido por duas frentes e por três migrations, e que dizer "nunca começada"
  induz ao erro (§3.2/C1).
- Não afirma nada sobre produção. P3, P5, P6, P7 e P8 continuam **não medidas**,
  e nenhuma frase acima as trata como respondidas.
- Não afirma que os cinco furos de §3.1 sejam exploráveis hoje na prática —
  afirma que o **código que os produz está intacto**, medido linha a linha.
