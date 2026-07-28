# Checklist de deploy — EasyPanel / Dockerfile

> Auditoria de **2026-07-27**, feita lendo o `Dockerfile`, o
> `docker-entrypoint-easypanel-auto.sh`, o `pre_start.py` e o pipeline de
> migrações — e **executando** o que dava para executar em dev. Complementa
> o `docs/plano-deploy-seguro.md` (que explica as três camadas de risco);
> este aqui é o que conferir antes de apertar o botão.

## O pipeline, como ele realmente é

```
EasyPanel builda a imagem (Dockerfile, base com digest fixado, lockfile --frozen)
  └─ ENTRYPOINT docker-entrypoint-easypanel-auto.sh
       1. exige DATABASE_URL (aborta sem ela)
       2. espera/testa o banco (retry)
       3. BACKUP pré-migração (scripts/backup_banco.py) — falhou? ABORTA o deploy
       4. pre_start.py: db.create_all() + executar_migracoes()  [timeout 300s]
          — exit ≠ 0 e ENABLE_ROLLBACK=true (default)? ABORTA
       5. health check pós-migração [timeout 60s]
       6. smoke de JVM (aviso, nunca bloqueio)
       7. exec gunicorn: 2 workers sync, --timeout 120, access log no stdout
```

Cada worker do gunicorn, ao importar `app`, roda `executar_migracoes()` de
novo — idempotente e barato (cache de aplicadas), mas vale saber que roda.

## ✅ O que está pronto e conferido

| Item | Estado |
|---|---|
| Base da imagem com digest fixado; deps pelo `uv.lock --frozen` | ✅ builds reproduzíveis |
| Container roda como usuário **não-root** (`sige`) | ✅ |
| `postgresql-client-17` — o servidor do EasyPanel é **17.9**, e `pg_dump` recusa servidor mais novo que ele | ✅ corrigido 28/07 (o cliente 16 travou o deploy) |
| `DATABASE_URL` sem default embutido — deploy para sem ela | ✅ |
| `SESSION_SECRET` obrigatório em produção (`app.py` levanta) | ✅ conferido no código |
| Backup pré-migração REAL, e deploy aborta se falhar | ✅ |
| `SIGE_ENABLE_DEMO_SEED` default **false** no entrypoint (e o seed de produção ainda exige `SIGE_ALLOW_PROD_SEED=1`) | ⚠️ a trava valia só para o gunicorn — ver item 6 |
| Migrações: **264 é a máxima**; 210 distintas aplicadas em dev; numeração tem buracos históricos (16-19, 21-26…) que são normais — nunca existiram na lista | ✅ |
| Sem JVM na imagem: importação `.mpp` degrada para 422 com instrução de exportar `.xml` (MSPDI) — decisão deliberada, aviso no boot | ✅ degradação limpa |
| Upload de JSON pela tela (payload leve) | ✅ testado em 27/07: obra criada, cronograma, RDO, versão nº1; reimport arquiva v1 e cria v2 |

## ⚠️ O que você precisa SABER antes do deploy

### 1. As migrações 48 e 132 falham em banco recriado — e isso NÃO derruba o deploy

🔬 dev 27/07 (banco recriado em 22/07): as duas falham em todo boot, desde
sempre — `48: invalid input value for enum tipousuario: "admin"` e
`132: column "cliente_nome" does not exist`. São **legadas**: referenciam o
schema antigo; o schema atual vem do `create_all()` + migrações posteriores,
então o que elas fariam já está coberto. Em produção (banco antigo) elas
constam como aplicadas e são puladas.

**O ponto honesto:** o comentário do `app.py` promete "falha de migração
aborta o boot em produção", mas `executar_migracoes` **engole falhas
individuais** (`run_migration_safe` → `failed_count` → warning) — o abort só
dispara se o sistema de migrações INTEIRO levantar. Para 48/132 isso é bom
(deploy não trava por migração morta); para uma migração NOVA que falhe, o
boot **sobe assim mesmo** e o erro fica só no log. **Depois de todo deploy,
grep no log por `❌` e `Migração .* falhou`.**

### 2. Upload de JSON com MUITAS fotos NÃO cabe no request — use o CLI

🔬 27/07, medido de verdade: o import completo da Baia (26 RDOs, 99 fotos,
otimização WebP + thumbnail por foto) levou **119 segundos** via CLI — isto
é, **no fio do timeout de 120s** do gunicorn de produção. Pela tela, o mesmo
payload não completou em dev (worker morto) e em produção seria loteria: um
servidor um pouco mais lento ou três fotos a mais e o request morre no meio,
com o usuário vendo tela travada e o retry duplicando trabalho.

| Payload | Caminho |
|---|---|
| JSON sem fotos / poucas fotos | ✅ tela (`/importacao/fisico-financeiro`) |
| JSON com dezenas de fotos (o da Baia) | ✅ **CLI no servidor**: `python scripts/seed_fisico_financeiro_baias.py <admin>` — roda fora do gunicorn, sem timeout |

Alternativas de médio prazo (decisão sua, não desta rodada): subir o
`--timeout` do gunicorn, ou tirar a otimização de imagem do request.

### 3. O import era vulnerável a worker morto — corrigido em 27/07

O teste acima revelou (acontecendo de verdade) que a **primeira** importação
de um tenant sem calendário deixava **obra parcial** no banco quando o worker
morria: `get_calendario`, chamado lá no fundo, criava o calendário e
**comitava no meio da transação**. Corrigido (aquecimento antes da
transação) e travado por teste. Deploy com o commit desta rodada ou
posterior já leva o fix.

### 4. Env vars — o que definir no painel

| Var | Obrigatória? | Nota |
|---|---|---|
| `DATABASE_URL` | **sim** — deploy aborta sem ela | |
| `SESSION_SECRET` | **sim** — app não sobe em produção sem ela | |
| `UPLOADS_PATH` | para a Fase 5 das fotos | ⚠️ só defina DEPOIS que a Task 13 estiver em produção e o volume montado — ver `docs/fase-5-rollout.md` parte B |
| `SIGE_ENABLE_DEMO_SEED` | não (default false) | deixe quieta |
| `SIGE_BACKUP_DIR` | recomendada | precisa apontar para o volume persistente (`/var/backups/sige`) |
| `MIGRATION_TIMEOUT` / `HEALTH_CHECK_TIMEOUT` / `DB_WAIT_TIME` | não (300/60/30) | |
| `PORTAL_BASE_URL` | para links do portal em e-mail/PDF | |

### 5. O banco avisa "collation version mismatch" — pendência REAL, não ruído

🔬 28/07, no log do backup em produção:

```
WARNING: database "sige" has a collation version mismatch
DETAIL:  created using collation version 2.36, but the OS provides version 2.41
```

Isso é o Postgres dizendo que o cluster foi inicializado com a glibc do
Debian 12 (2.36) e hoje roda sobre a do Debian 13 (2.41) — a imagem do
serviço trocou de distro por baixo. **A ordenação de texto mudou**, então
índices `text`/`varchar` e constraints `UNIQUE` sobre texto podem estar
logicamente inconsistentes: uma busca por range pode pular linha e um
`UNIQUE` pode ter deixado passar duplicata.

É **aviso**, não erro: não bloqueia o backup nem o deploy. Mas continua
valendo até alguém rodar, numa janela de baixo movimento e **depois de um
backup bem-sucedido**:

```sql
REINDEX DATABASE sige;
ALTER DATABASE sige REFRESH COLLATION VERSION;
```

O `REINDEX` bloqueia escrita nas tabelas que reindexa — não rode em horário
de RDO. `REINDEX` sozinho não some com o aviso; quem apaga é o `ALTER`, e
rodar o `ALTER` sem o `REINDEX` só silencia o alarme sem consertar o índice.

### 6. A "trava dupla" do seed demo NÃO cobria o pre_start — corrigido em 28/07

O entrypoint exporta `SIGE_ENABLE_DEMO_SEED=false` / `SIGE_ALLOW_PROD_SEED=0`
na **linha 368**. O `pre_start.py` roda na **linha 136**. Quando ele importa
`app`, o ambiente ainda está limpo e valiam os defaults de `app.py`, que eram
`"true"` / `"1"` — ou seja, **auto-seed ligado no banco de produção**, pelo
caminho que a auditoria de 27/07 deu como travado.

🔬 Visto no deploy de 28/07:

```
[seed-demo-alfa] auto-seed iniciado em background
...
🔄 Executando Migração 222: ... tabela tarefa_vinculo + is_critica/folga_dias
   (não concluiu)
```

O seed escreve em `tarefa_cronograma` (`DELETE FROM`, `scripts/seed_demo_alfa.py:231`);
a migração 222 precisa de `ACCESS EXCLUSIVE` na mesma tabela para o
`ALTER TABLE ... ADD COLUMN`. A migração ficou esperando o lock e o deploy
bateu no `MIGRATION_TIMEOUT`.

Fix: os defaults de `app.py` passaram a depender de `IS_PRODUCTION` — em
produção o seed exige opt-in explícito; fora dela nada muda.

**Independente do fix, defina as duas no painel** — é a trava que não depende
de ordem de execução de script nenhum:

```
SIGE_ENABLE_DEMO_SEED=false
SIGE_ALLOW_PROD_SEED=0
```

Se um deploy travar numa migração de novo, o diagnóstico é olhar lock:

```sql
SELECT pid, state, wait_event_type, left(query,80)
  FROM pg_stat_activity WHERE datname='sige' AND state <> 'idle';
```

### 7. Pendências humanas que o deploy NÃO resolve (continuam)

- Volume persistente + snapshot Hostinger + dump fora do servidor (parte B
  da Fase 5 — os 16 GB de fotos).
- As flags continuam desligadas por decisão de 27/07 (`escopo_obra_ativo`
  et al.) — deploy não muda comportamento visível.
- `origin/main` ↔ produção: o EasyPanel builda do GitHub; confira **qual
  commit** ele buildou (a tela de build mostra o hash) — produção já rodou
  35 commits atrás do repositório sem ninguém notar.

## A ordem sugerida do próximo deploy

1. Conferir que o EasyPanel aponta para `main` e o hash é o atual.
2. Deploy. O entrypoint faz backup → migrações → health → sobe.
3. Grep no log do build/boot: `❌`, `Migração .* falhou`, `FATAL`.
4. Smoke manual: login, dashboard, abrir uma obra, abrir um RDO.
5. Se a Baia for importada/atualizada em produção: **CLI, não a tela** (item 2).
