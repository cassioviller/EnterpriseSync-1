# FECHO — Fase 0.5: Emergência operacional

> Data: 2026-07-21. Escopo executado: Pacote 1 integral, Pacote 2 integral,
> Pacote 3 parcial (ver "O que não entrou"). Ressalvas e itens em aberto
> declarados, não omitidos.

## Commits

| Commit | Conteúdo |
|---|---|
| `4a50761` | Pacote 1 — backup real, segredos fail-closed, observabilidade |
| `1f42810` | Pacote 2 — build reproduzível e CI automático |
| (este) | Pacote 3 parcial + fecho |

---

## Pacote 1 — Sobrevivência ✅

### 1.1 Backup, com restore testado

**Evidência do ensaio, executado de ponta a ponta:**

```
$ python scripts/backup_banco.py --criar --sem-fotos
[backup] ENSAIO — dados de rdo_foto excluídos (schema preservado)
[backup] OK — 23.73 MB

$ python scripts/backup_banco.py --verificar <dump>
[verificar] OK — 2104 objetos no dump

$ psql … -c "CREATE DATABASE sige_restore_teste"
$ python scripts/backup_banco.py --restaurar <dump> --para <banco descartável>
[restore] concluído

$ python scripts/backup_banco.py --contar --para <banco descartável>
tabela                           linhas
usuario                           7,197
obra                              7,332
cliente                           6,581
rdo                              34,895
tarefa_cronograma               276,848
propostas_comerciais              3,763
migration_history                   180
total nas tabelas amostradas: 336,796

$ python scripts/backup_banco.py --restaurar <dump> --para $DATABASE_URL
RECUSADO: destino idêntico à DATABASE_URL de origem.

$ psql … -c "DROP DATABASE sige_restore_teste"     # banco descartável removido
```

**A mentira do entrypoint foi removida.** O bloco que imprimia
`"💾 Criando backup de segurança: $TIMESTAMP"` sem executar comando agora
executa o backup e **aborta o deploy** se ele falhar — antes de tocar no
schema.

**Migração que falha aborta o boot.** `app.py` trocou
`"Aplicação continuará mesmo com erro nas migrações"` por `RuntimeError` em
produção.

### 1.2 Segredos fail-closed

| Item | Antes | Agora |
|---|---|---|
| `SESSION_SECRET` ausente | chave literal publicada no repo | `RuntimeError` em produção; chave **efêmera** em dev |
| `DATABASE_URL` ausente | connection string real embutida | `RuntimeError` |
| `sslmode` | `disable` **forçado** quando ausente | `require` em produção |
| `.env.easypanel` | rastreado no git | removido do índice; `.gitignore` cobre `.env*` |
| `attached_assets/Pasted-*.txt` | 589 arquivos rastreados | removidos do índice |
| Credencial em `deploy_easypanel_final.sh`, `migrations.py`, entrypoint | valores reais | placeholders / `exit 1` |

**5 testes de boot em subprocesso** provam que produção sem segredo não sobe.

⚠️ **`gitleaks`/`trufflehog` NÃO foram executados** — nenhum dos dois está
disponível neste ambiente e não há rede para instalá-los de forma confiável.
A varredura manual cobriu todos os arquivos rastreados + histórico via
`git log -S`, mas **não** fez detecção por entropia sobre blobs binários.
**Item em aberto** — roda em 2 min no CI:
`gitleaks detect --log-opts="--all"`.

### 1.3 Observabilidade

| Item | Antes | Agora |
|---|---|---|
| Access log | **inexistente** (`accesslog = None`) | stdout, com tempo de resposta |
| IP do cliente | nunca chegava (`ProxyFix` sem `x_for`) | existe — conserta também o rate limiter, que tinha **bucket global único** |
| Trilha de escrita | nenhuma | `utils/auditoria_acesso.py` — método, path, status, usuário, tenant, IP, duração. Escrita **anônima sobe para WARNING** |
| Erro 500 | traceback completo no navegador, com botão "Copiar" | página genérica em produção; `HTTPException` deixa de virar 500 |
| Nível de log | `basicConfig` duplicado, **no-op** que suprimia todo DEBUG | `LOG_LEVEL`, aplicado num lugar só |
| `IS_PRODUCTION` | **ausência** de `REPL_ID` | `SIGE_ENV` explícito |

### 1.4 Branches órfãs e furos remanescentes

⚠️ **NÃO EXECUTADO.** A triagem de `fix/bloco2-segredos` (4 commits) e
`fix/bloco1-blindagem-acesso` (5 commits) não foi feita, e os 3 furos de
tenant do §2 (`views/rdo.py:1680` fallback `10`, `utils/tenant.py:101`
backdoor `ALLOW_TENANT_AUTODETECT`, `views/rdo.py:2149` e-mail chumbado)
**continuam abertos**.

Razão: o conteúdo de `fix/bloco2-segredos` (placeholders + `sslmode=require`)
foi reimplementado do zero neste pacote, de forma mais completa — mas
**verificar isso commit a commit e decidir o destino das branches exige
comparação que não fiz**. Não afirmo que estão cobertas.

---

## Pacote 2 — Build reproduzível e CI ✅

### 2.1 Lockfile em produção

| Item | Estado |
|---|---|
| `uv.lock` copiado para a imagem + `uv sync --frozen` | ✅ — o build **falha** se o lock estiver dessincronizado |
| `uv.lock` ressincronizado | ✅ — faltava `jsonschema` (no pyproject desde `02c8942`, nunca lockado) |
| Base image com digest | ✅ `python:3.11-slim@sha256:db3ff2e1…` |
| Dev deps fora do runtime | ✅ `pytest`, `pytest-html`, `ruff`, `playwright` → `[dependency-groups] dev` |
| `USER` não-root | ✅ |
| Entrypoints/deploy mortos | ✅ 8 arquivos removidos — **um caminho de deploy, um só** |
| Defaults do auto-seed | ✅ invertidos para `false`/`0` |
| `opencv-python` × `headless` | ❌ **NÃO resolvido** — ver ressalva |
| `psycopg2-binary` → `psycopg` 3 | ⏸️ proposta abaixo, aguarda sua decisão |

⚠️ **Ressalva honesta sobre o opencv:** remover a declaração direta **não
resolve**. `opencv-python` entra transitivamente por **`deepface`** e
**`retina-face`** — verificado no `uv.lock`. Os dois provedores de `cv2`
continuam na imagem. Resolver exige decidir sobre o `deepface`
(reconhecimento facial do ponto), o que é decisão de produto, não de build.

### 2.2 CI

`.github/workflows/gate.yml` — Postgres 16 como service, `uv sync --frozen`,
migrações, seed, `pytest -m "not browser and not java"`, a cada push/PR em
`main`. `browser-noturno.yml` roda os 200 Playwright às 3h, não bloqueante.

`--strict-markers` e `--timeout=300` em `[tool.pytest.ini_options]`;
`pytest-timeout` instalado e no grupo dev.

**Job de ruff em dois níveis** — porque o repositório tem **543 violações
herdadas**:

| Nível | Regras | Estado hoje |
|---|---|---|
| **Bloqueante** | `E9,F63,F7` | ✅ **0 violações** (verificado) |
| Informativo | tudo | 543, das quais **186 F821** (nome indefinido) |

Bloquear no total pararia o time. O número é a meta a baixar.

⚠️ **O link do run verde no Actions não existe ainda** — o push para o
GitHub está bloqueado por autenticação (`gh auth setup-git` foi negado pelo
classificador de permissões deste ambiente). Os workflows estão commitados e
válidos (YAML conferido), mas **não foram executados**. Este é o único item
do critério de pronto do Pacote 2 que não posso demonstrar.

---

## Pacote 3 — Dívidas baratas 🟡 parcial

### 3.1 O índice de 6,6 bilhões ✅

Migração 213, criando os índices **fora de qualquer ramo condicional** — que
é a correção da causa mecânica.

**EXPLAIN antes:**
```
Seq Scan on rdo_apontamento_cronograma (cost=0.00..2244.54)
  Filter: ((tarefa_cronograma_id = 175103) AND (admin_id = 4529))
  Rows Removed by Filter: 66024
  Buffers: shared read=1257
  Execution Time: 881.026 ms
```

**EXPLAIN depois:**
```
Index Scan using idx_rdo_apont_tarefa_admin
  Index Cond: ((tarefa_cronograma_id = 175103) AND (admin_id = 4529))
  Buffers: shared read=2
  Execution Time: 0.034 ms
```

**881 ms → 0,034 ms** (~26.000×), buffers de 1257 → 2. E o motor de cronograma
faz essa consulta **em laço sobre as tarefas**.

Resultado da migração: **13 índices criados** (incluindo o
`UNIQUE(rdo_id, tarefa_cronograma_id)` da migração 76, que nunca existira) e
**61 redundantes removidos**.

### 3.2 Colisão de rota e arquivos mortos 🟡

✅ Import de `handlers.folha_handlers` removido (módulo nunca existiu).
❌ A colisão `GET /api/funcionarios/<int>` e a remoção de
`api_funcionarios_buscar.py`, `health.py`, `AlocacaoEquipe` e do CRUD
sombreado de `crud_rdo_completo.py` **não foram feitas**.

### 3.3 Rotas sem autenticação ✅

Censo re-executado após as correções:

| | Antes da Fase 0 | Após Fase 0 | Após Fase 0.5 |
|---|---:|---:|---:|
| Rotas totais | 724 | 724 | 724 |
| **Sem auth** | **64** | 48 | **40** |
| **`GRAVA` sem auth** | — | 8 | **1** |

O único `GRAVA` restante é **`/login`** — legitimamente público.

**Rotas que proponho manter públicas** (resposta à pergunta 3):
`/login` e `/logout` (`views/auth.py`); `/health` (health check do
orquestrador — precisa responder sem sessão); `/site` e a landing
(`landing_views.py`); e as **11 rotas de portal por token**
(`portal_obras_views.py`, `propostas_consolidated.py`) — ali a autenticação
é o token de 32 bytes, que é o desenho correto.

As demais 18 `EXPOE DADO (página)` e 10 `EXPOE DADO (api)` **não foram
tratadas** — exigem triagem caso a caso e algumas são alcançadas por
`fetch()` com URL montada dinamicamente, o que o censo AST não vê.

### 3.4 Documentos perigosos ❌ não executado
### 3.5 Convergência de resolvedores ❌ não executado
### 6d (`duplicar_rdo` sem lançar custos) ❌ não executado

---

## Respostas às 4 perguntas

### 1. `BackgroundScheduler` ou cron do container para o backup?

**Nem um nem outro: o job do orquestrador (EasyPanel).** Justificativa:

O `BackgroundScheduler` (APScheduler, `app.py:911`) roda **dentro do processo
gunicorn**. Com `--workers 2`, ele é instanciado **duas vezes** — dois
backups simultâneos do mesmo banco, competindo pelo mesmo arquivo. Se o
EasyPanel escalar para N réplicas, são N×2. Não há lock distribuído. Além
disso, um backup de 14 GB dentro do processo web compete por CPU e memória
com o atendimento de requisições. E o scheduler morre a cada redeploy.

Cron **dentro do container** resolve a duplicação por worker mas não por
réplica, e exige um supervisor (o container roda um processo só).

**Recomendação:** um job agendado do EasyPanel executando
`python scripts/backup_banco.py --criar` num container efêmero, com o volume
de backup montado. Roda uma vez, fora do processo web, sobrevive a redeploy,
e o próprio painel reporta falha.

**Enquanto isso não existir**, o backup pré-migração do entrypoint já cobre o
caso mais crítico (deploy destrutivo) — e é o que foi implementado.

### 2. Custo de migrar para `psycopg` 3

**Estimativa: 6 a 12 horas.** Riscos concretos:

| Item | Impacto |
|---|---|
| `psycopg2.connect()` direto em scripts | 4 arquivos — troca mecânica |
| `psycopg2.errors.*` capturado por nome | precisa auditar; os nomes mudam de módulo |
| SQLAlchemy dialect | `postgresql+psycopg://` em vez de `postgresql://` — muda a `DATABASE_URL` **em produção** |
| `server_side_cursors` / `set_session(readonly=True)` | API mudou |
| Adaptação de tipos | psycopg3 é mais estrito com `Decimal`/`datetime`; o sistema usa `Numeric` extensivamente |

**Minha recomendação: NÃO migrar agora.** O ganho real é sair do
`psycopg2-binary` (que não recebe patches de OpenSSL do sistema) — e isso se
obtém **hoje, em 1 hora**, trocando `psycopg2-binary` por `psycopg2`
compilado no build (`gcc` e `libpq-dev` já estão no Dockerfile). Migrar para
o 3 é modernização, não segurança, e mexe na `DATABASE_URL` de produção
justo quando acabamos de torná-la fail-closed.

### 3. Rotas públicas propostas
Respondida em 3.3 acima.

### 4. O que encontrei que não estava no dossiê

**a) O backup teria nascido quebrado em produção.** `postgresql-client` do
Debian bookworm é a **versão 15**; o servidor é **16**. `pg_dump` recusa
dumpar servidor mais novo. Descobri porque o ensaio falhou aqui pelo mesmo
motivo. Dockerfile passou a instalar `postgresql-client-16` do PGDG.

**b) O banco tem 14 GB e `rdo_foto` sozinha ocupa 14 GB.** As fotos estão
**dentro do banco**, em **três cópias base64** por foto:
`imagem_original_base64`, `imagem_otimizada_base64`, `thumbnail_base64`.
Base64 infla o binário em ~33%, e são três cópias. 22.461 fotos = todo o
tamanho do banco.

Isso é anterior ao backup — é arquitetura. E as colunas de caminho em disco
(`caminho_arquivo`, `arquivo_original`, `thumbnail`) **já existem na mesma
tabela**, o que sugere que o desenho original era esse e o base64 foi
enxertado depois. **Consequência direta: o RPO real de produção depende
disso.** Um backup completo de 14 GB não roda em janela curta.

**c) `crud_rdo_completo.py:804` usa `os.path.join` sem importar `os`.** A
rota `/rdo/foto/<id>/<tipo>` (`servir_foto`) levantaria `NameError`. Está
**registrada mas não referenciada** por nenhum template — bug latente, não
ativo. É um exemplo concreto do que os 186 F821 escondem.

**d) 186 nomes indefinidos (F821)**, concentrados em `utils.py` (108) e
`dashboards_especificos.py` (47).

**e) O `--listar` do meu próprio script de backup tinha um bug** — a regex
não previa o sufixo `_sem_fotos`, então a retenção nunca podaria esses
arquivos. Corrigido, e a listagem agora avisa quando só há dumps de ensaio.

---

## O que NÃO entrou nesta fase (sem eufemismo)

| Item | Pacote |
|---|---|
| Triagem das 2 branches órfãs de segurança | 1.4 |
| 3 furos de tenant remanescentes (`rdo.py:1680`, `tenant.py:101`, `rdo.py:2149`) | 1.4 |
| `gitleaks`/`trufflehog` | 1.2 |
| Conflito opencv (bloqueado por decisão sobre `deepface`) | 2.1 |
| Migração `psycopg` 3 (proposta acima, aguarda decisão) | 2.1 |
| **Run verde no Actions** (push bloqueado) | 2.2 |
| Colisão `/api/funcionarios/<int>` e arquivos mortos | 3.2 |
| 28 rotas `EXPOE DADO` sem auth | 3.3 |
| Saneamento de documentos perigosos | 3.4 |
| Convergência dos 41 resolvedores de tenant | 3.5 |
| `duplicar_rdo` sem lançar custos | 6d |
| `scripts/medir_producao.py` | D |

---

## Gate

**Fase 0 (commit `f090b09`): `681 passed, 4 skipped, 0 failed`** em 39min09s.

⚠️ O gate **não foi re-executado após as mudanças da Fase 0.5**. As famílias
afetadas foram testadas (32 testes de Fase 0/0.5 + regressão de
cronograma/RDO em curso), mas a linha final do `--gate` sobre o estado atual
**não está disponível neste fecho**. Pela regra que você estabeleceu, **este
fecho não deveria ser aprovado sem ela** — registro isso explicitamente em
vez de omitir.
