# Notificações externas via n8n (webhook)

Esta pasta documenta a **fundação reutilizável** que permite ao SIGE
notificar sistemas externos (e-mail, WhatsApp, Slack, Telegram, …) sem
precisar mexer no código de cada módulo: o **n8n** vira o roteador de
notificações.

> Esta infraestrutura **não envia nenhuma notificação por si só**. Ela
> só constrói o "cano". Para começar a sair eventos é preciso (a)
> configurar as variáveis de ambiente abaixo **e** (b) adicionar nomes
> de evento na **allowlist** do despachante.

---

## 1. Como ligar

Adicione no ambiente da aplicação:

| Variável             | Obrigatória? | O que é                                                                  |
| -------------------- | ------------ | ------------------------------------------------------------------------ |
| `N8N_WEBHOOK_URL`    | sim          | URL do webhook do n8n (ex.: `https://n8n.suaempresa.com.br/webhook/sige-proposta-enviada`). |
| `N8N_WEBHOOK_SECRET` | recomendada  | Segredo HMAC. Se vazio, o SIGE envia sem assinatura.                     |

Sem `N8N_WEBHOOK_URL`, o despachante é **no-op silencioso**: o sistema
funciona normalmente, só não notifica ninguém de fora.

A inicialização acontece em `app.py` via
`utils.webhook_dispatcher.init_app(app)`, que:

1. Registra um listener no `EventManager` para **cada** evento da
   allowlist.
2. Sobe **uma** thread daemon de retry (a cada 30 s reprocessa pendentes
   elegíveis).

---

## 2. Convenção de nomenclatura dos eventos

`dominio.acao` — minúsculo, snake-case por palavra, separado por ponto.

Exemplos:

* `proposta.enviada`
* `proposta.aprovada`
* `obra.medicao_publicada`
* `rdo.finalizado`
* `material.entrada`

> Os nomes legados do `EventManager` interno (sem ponto, ex.:
> `proposta_aprovada`) continuam servindo internamente. Ao colocar um
> evento na **allowlist** para sair pelo webhook, prefira o formato
> `dominio.acao`. Se quiser que ambos disparem, basta `EventManager.emit`
> dos dois nomes na mesma rota — o evento "interno" continua tocando os
> handlers de negócio, e o "externo" cai no listener universal.

---

## 3. Formato do payload

O SIGE sempre envia um JSON com este shape:

```json
{
  "event":       "proposta.enviada",
  "occurred_at": "2026-04-30T13:42:11Z",
  "admin_id":    7,
  "data":        { "...": "dict original passado ao EventManager.emit(...)" },
  "source":      "obra"
}
```

* `event` — nome do evento (igual ao da allowlist).
* `occurred_at` — UTC ISO-8601 com sufixo `Z`.
* `admin_id` — tenant que originou o evento (ou `null`).
* `data` — passa direto o dict original do emit.
* `source` — sempre `"obra"`.

---

## 4. Adicionar um novo evento à allowlist

Edite a constante em `utils/webhook_dispatcher.py`:

```python
WEBHOOK_EVENT_ALLOWLIST: set[str] = {
    "proposta.enviada",
    # adicione novos eventos aqui
}
```

E garanta que algum lugar do código está chamando:

```python
from event_manager import EventManager
EventManager.emit("proposta.enviada", {
    "proposta_id":     p.id,
    "proposta_numero": p.numero,
    "proposta_versao": p.versao,
    "cliente_nome":    p.cliente_nome,
    "cliente_email":   p.cliente_email,
    "cliente_telefone": p.cliente_telefone,
    "valor_total":     str(p.valor_total),
    "validade_dias":   p.validade_dias,
    "portal_url":      url_for("portal.proposta", token=p.token, _external=True),
}, admin_id=admin_id)
```

> O **listener universal** já está plugado no `EventManager` para todos
> os nomes da allowlist — só sair eventos que estão lá. Nada vaza por
> engano.

---

## 5. Validação da assinatura no n8n

O SIGE assina o **corpo bruto** (UTF-8) com HMAC-SHA256 usando o
`N8N_WEBHOOK_SECRET` e envia no header `X-Signature` (hex puro, sem
prefixo `sha256=`).

Receita no n8n (Function node):

```javascript
const crypto  = require('crypto');
const secret  = $env.N8N_WEBHOOK_SECRET;
const given   = $input.first().json.headers['x-signature'] || '';
const rawBody = ...; // pegue o body bruto (Webhook node com rawBody=true)

const expected = crypto
  .createHmac('sha256', secret)
  .update(rawBody, 'utf8')
  .digest('hex');

const ok = expected.length === given.length
  && crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(given));

if (!ok) throw new Error('Assinatura HMAC inválida');
```

O JSON em `n8n_workflows/proposta_enviada.json` já traz esse Function
node pronto.

---

## 6. Importar o workflow exemplo no n8n

1. Abra o n8n → **Workflows → Import from File** → selecione
   `n8n_workflows/proposta_enviada.json` (na raiz do repositório).
2. No menu **Settings → Variables (env)** do n8n, configure:
   * `N8N_WEBHOOK_SECRET` — mesmo valor que está no SIGE.
   * `SIGE_FROM_EMAIL` — remetente padrão (ex.: `propostas@suaempresa.com.br`).
   * `EVOLUTION_API_URL` — URL da Evolution API (ex.: `https://evolution.suaempresa.com.br`).
   * `EVOLUTION_INSTANCE` — nome da instância no Evolution (ex.: `comercial`).
   * `EVOLUTION_API_KEY` — apikey da instância.
3. No node **Enviar E-mail (SMTP/SendGrid)**, abra as credenciais e
   substitua o placeholder `REPLACE_WITH_YOUR_SMTP_CREDENTIAL_ID` por
   uma credencial SMTP real do n8n (Gmail, SendGrid, Amazon SES, …).
4. Ative o workflow. A URL pública do webhook é
   `https://<seu-n8n>/webhook/sige-proposta-enviada`. Coloque-a em
   `N8N_WEBHOOK_URL` no SIGE.

> ⚠️ Em ambiente de teste, use o **Test URL** do n8n (`/webhook-test/...`)
> antes de ligar a versão de produção.

---

## 7. Setup da Evolution API (resumo)

A Evolution API é o servidor que conecta no WhatsApp via WebSocket
(libwhatsapp). Para enviar mensagem por ela:

```http
POST {{EVOLUTION_API_URL}}/message/sendText/{{EVOLUTION_INSTANCE}}
apikey: {{EVOLUTION_API_KEY}}
Content-Type: application/json

{
  "number": "5511988887777",
  "text":   "Sua proposta..."
}
```

Pré-requisitos:

* Evolution API hospedada e acessível pelo n8n.
* Instância criada (`POST /instance/create`) e WhatsApp pareado
  (escaneamento do QR Code).
* `apikey` da instância (visível em `GET /instance/fetchInstances`).

O telefone do cliente vai cru no payload do SIGE — formate-o com DDI
+ DDD + número (sem `+`, espaços ou hífens) na hora de pareá-lo no
n8n. Você também pode validar/normalizar via Function node antes do
`sendText`.

---

## 8. Painel admin

Em `/admin/webhooks` (acessível a **admin** e **super_admin**) você
acompanha:

* Status do canal (ligado/desligado, URL configurada, allowlist).
* Últimas 200 entregas com filtros por **status** e **evento**.
* Botão **Reenviar** para tentar de novo entregas com falha (reseta o
  contador de tentativas e tenta agora).

> **Escopo por tenant** — o admin tenant vê e reenvia somente entregas
> do próprio `admin_id`. O super_admin vê tudo (todos os tenants).

---

## 9. Garantias e limites

* **Idempotência da fila** — toda tentativa, sucesso ou falha, vira uma
  linha em `webhook_entrega` (auditoria + retry).
* **Backoff fixo** — após cada falha transitória (timeout / 5xx) a
  próxima tentativa fica agendada para 1 min → 5 min → 15 min. Ou seja,
  são **3 retries reais** depois do disparo original (4 tentativas no
  total). Após a 4ª falha, status passa a `falha` (permanente).
* **HTTP 4xx é falha permanente** — payload ruim não vale retry.
* **Best-effort** — exceções no despachante **nunca** propagam para o
  pipeline de negócio (uma proposta enviada **não** falha porque o
  webhook caiu).
* **Sem confirmação de entrega** — o SIGE não escuta callbacks do n8n
  de "lido"/"recebido" nesta versão. Se for necessário, vira uma
  evolução futura.

---

## 10. Catálogo inicial de eventos (Task #45)

A allowlist em `utils/webhook_dispatcher.py` já está populada com **7
eventos prontos para n8n**, todos no formato `dominio.acao`. Os
emissores reais ficam em `utils/catalogo_eventos.py` (helpers
`emit_*`) — o resto do código apenas chama esses helpers nos pontos
de negócio. Cada chamada é **best-effort** (try/except no helper) e
roda **paralela** ao evento legado equivalente, para não quebrar
nenhum handler interno.

| Evento                        | Quando dispara                                                                 | Ponto de emissão                                            | Workflow exemplo                                  |
| ----------------------------- | ------------------------------------------------------------------------------ | ----------------------------------------------------------- | ------------------------------------------------- |
| `proposta.aprovada`           | Aprovação pelo admin **ou** pelo cliente no portal (após commit + criar obra)  | `propostas_consolidated.py` (rota admin + rota portal)      | `n8n_workflows/proposta_aprovada.json`            |
| `proposta.rejeitada`          | Rejeição pelo admin **ou** pelo cliente no portal (após commit, com motivo)    | `propostas_consolidated.py` (rota admin + rota portal)      | `n8n_workflows/proposta_rejeitada.json`           |
| `proposta.expirando`          | Job diário (`flask emitir-propostas-expirando`) — 3 dias antes do vencimento   | `notificacoes_cli.py`                                       | `n8n_workflows/proposta_expirando.json`           |
| `obra.rdo_publicado`          | RDO criado/finalizado (4 rotas: criar normal, criar via wizard, editar, duplicar) | `views/rdo.py` (`rdo_finalizado` + paralelo)                | `n8n_workflows/obra_rdo_publicado.json`           |
| `obra.medicao_publicada`      | Fechamento da medição quinzenal (após commit)                                  | `services/medicao_service.py::fechar_medicao`               | `n8n_workflows/obra_medicao_publicada.json`       |
| `obra.cronograma_atualizado`  | Cronograma inicial revisado/aceito (gate de revisão)                           | `views/obras.py::cronograma_revisar_inicial_post`           | `n8n_workflows/obra_cronograma_atualizado.json`   |
| `obra.concluida`              | Obra muda para status "Concluída" pela primeira vez (transição, não re-edit)   | `views/obras.py::editar_obra` (compara `status_anterior`)   | `n8n_workflows/obra_concluida.json`               |

### 10.1. Campos de payload por evento

Todos os payloads vêm dentro do campo `data` do envelope padrão
(seção 3). Aqui o **conteúdo de `data`** para cada evento:

> Os campos abaixo descrevem o conteúdo de `data` para cada evento.
> Bloco `proposta.*` compartilha o sub-bloco `_payload_proposta`
> (`proposta_id`, `proposta_numero`, `proposta_versao`,
> `cliente_nome`, `cliente_email`, `cliente_telefone`,
> `valor_total` (number), `portal_url`). Bloco `obra.*` compartilha
> `_payload_obra_basico` (`obra_id`, `obra_nome`, `obra_codigo`,
> `cliente_nome`, `cliente_email`, `cliente_telefone`,
> `portal_obra_url`). Os campos abaixo são os **adicionais** de cada
> evento, definidos em `utils/catalogo_eventos.py`.

#### `proposta.aprovada`
```jsonc
{
  // ...campos comuns de proposta...
  "data_aprovacao": "2026-04-30",     // YYYY-MM-DD (date.today())
  "aprovada_por":   "admin",          // "admin" | "cliente"
  "obra_id":        45                // null se aprovada sem criar obra
}
```

#### `proposta.rejeitada`
```jsonc
{
  // ...campos comuns de proposta...
  "data_rejeicao":  "2026-04-30",     // YYYY-MM-DD
  "rejeitada_por":  "cliente",        // "admin" | "cliente"
  "motivo":         "Prazo muito longo"  // string truncada a 500 chars
}
```

#### `proposta.expirando`
```jsonc
{
  // ...campos comuns de proposta...
  "data_validade":  "2026-05-03",     // YYYY-MM-DD (data_envio.date() + validade_dias)
  "dias_restantes": 3,
  "validade_dias":  30
}
```

#### `obra.rdo_publicado`
```jsonc
{
  // ...campos comuns de obra...
  "rdo_id":         9876,
  "numero_rdo":     "RDO-2026-04-30-001",
  "data_relatorio": "2026-04-30",
  "status":         "Finalizado"
}
```

#### `obra.medicao_publicada`
```jsonc
{
  // ...campos comuns de obra...
  "medicao_id":              12,
  "numero_medicao":          "MED-2026-08",
  "valor_medido_periodo":    85000.00,   // number (float)
  "valor_a_faturar_periodo": 85000.00,
  "percentual_executado":    42.5,
  "data_aprovacao":          "2026-04-30"
}
```

#### `obra.cronograma_atualizado`
```jsonc
{
  // ...campos comuns de obra...
  "tarefas_geradas":   18,
  "data_atualizacao":  "2026-04-30T13:42:11Z",
  "motivo":            "revisao_inicial"     // ou "replanejamento"
}
```

#### `obra.concluida`
```jsonc
{
  // ...campos comuns de obra...
  "data_conclusao":     "2026-04-30",   // YYYY-MM-DD
  "data_inicio":        "2025-11-15",
  "data_previsao_fim":  "2026-05-30",
  "valor_contrato":     1850000.00      // number (float)
}
```

### 10.2. Job diário `proposta.expirando`

O evento `proposta.expirando` **não tem trigger** dentro do fluxo de
propostas (é varredura, não reação). Para emiti-lo todo dia rode o
comando CLI:

```bash
flask emitir-propostas-expirando            # janela padrão = 3 dias
flask emitir-propostas-expirando --janela=5 # propostas que expiram nos próximos 5 dias
flask emitir-propostas-expirando --dry-run  # só lista, não emite (útil em staging)
```

Ele varre todas as propostas com:

* `status` ∈ {`enviada`, `visualizada`, `em_negociacao`}
* data de expiração ≤ hoje + `janela` (calculada como
  `data_envio.date() + validade_dias` — não há coluna dedicada).

**Idempotência por dia** — antes de emitir, o job consulta
`webhook_entrega` (filtros: `event = 'proposta.expirando'` +
`func.date(created_at) = hoje` + `payload['data']['proposta_id']
= proposta.id`). Se já existir entrega de hoje para a mesma
proposta, ele pula. Há fallback Python (filtro em memória) caso o
backend não suporte o operador JSON `->>`.

#### Cron / scheduler

Crie um cron job (host) ou um `cronWorkflow` no Replit Deploy/host
que rode 1x por dia:

```cron
# Crontab — todo dia às 09:00 horário do servidor
0 9 * * * cd /app && /app/venv/bin/flask emitir-propostas-expirando
```

No **Replit Deploy** com Scheduled Deployments, basta apontar o
schedule para o mesmo comando. O job é seguro mesmo se rodar 2x no
mesmo dia (idempotência cobre).

---

## 11. Como adicionar um 8º evento ao catálogo

1. **Allowlist** — adicione `"dominio.acao"` em
   `utils/webhook_dispatcher.py::WEBHOOK_EVENT_ALLOWLIST`.
2. **Helper de emissão** — crie `emit_dominio_acao(...)` em
   `utils/catalogo_eventos.py` seguindo o padrão dos existentes
   (try/except, monta payload completo, chama
   `EventManager.emit("dominio.acao", payload, admin_id=...)`).
3. **Pontos de emissão** — chame o helper **após o commit** da
   transação principal e **paralelo** ao evento legado equivalente,
   se existir.
4. **JSON exemplo** — copie um arquivo de `n8n_workflows/`
   (ex.: `obra_concluida.json`) e adapte o path do webhook + Function
   "Extrair Dados" + textos de e-mail/WhatsApp.
5. **Documentação** — adicione uma linha na tabela da seção 10 e um
   bloco de payload em 10.1.
6. **Teste** — atualize `tests/test_task_45_catalogo_eventos.py`
   cobrindo o novo helper.
