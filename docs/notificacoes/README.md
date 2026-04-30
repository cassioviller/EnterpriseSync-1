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
