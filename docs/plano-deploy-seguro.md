# Plano de deploy seguro — não perder dados no EasyPanel

> Escrito em 2026-07-22, ancorado no código conferido (`caminho:linha`).
> Substitui a resposta verbal fraca dada antes. A pergunta é *"se eu fizer o
> deploy, perco algo do meu banco?"* — e a resposta honesta tem três camadas,
> não um "sim/não".

## O modelo de risco, em uma tela

O que "deploy" toca **não é uma coisa só**. São três camadas com durabilidades
diferentes, e confundi-las é o que produz respostas erradas:

| Camada | Onde vive | Sobrevive a um redeploy? |
|---|---|---|
| **Dados do Postgres** (obras, RDOs, financeiro…) | container do banco no EasyPanel, com **volume próprio** | ✅ **Sim** — deploy do app não recria o banco |
| **Uploads** (`static/uploads`, ~13 GB de fotos) | filesystem do **container do app** | ❌ **Não** — container recriado = arquivos apagados |
| **Código que sobe** | buildado do GitHub pelo EasyPanel | ⚠️ é o `origin/main` **antigo** — 35 commits atrás do trabalho local |

Então a resposta curta: **os dados do banco em si, você não perde.** Mas há
uma perda real (as fotos), uma rede de segurança que hoje é ilusória, e o
detalhe de que o deploy de hoje nem subiria o código novo. As três seções
abaixo são cada um desses.

---

## Camada 1 — O banco: por que está seguro, e a única coisa que o ameaça

O Postgres roda em container separado, com volume persistente próprio no
EasyPanel. Um deploy do **app** builda uma imagem nova e a reinicia; ele não
cria, apaga nem recria o banco. O `DATABASE_URL` aponta para o banco de fora.

**O único momento em que um deploy escreve no banco de produção** é o startup,
que roda as migrations automaticamente
(`docker-entrypoint-easypanel-auto.sh:136` → `pre_start.py` → `executar_migracoes`).
Duas das novas mexem em **dados**, não só em schema:

- **Migration 217** — `UPDATE obra.status` (canoniza a grafia). Reversível,
  baixo risco.
- **Migration 218** — troca a PK de `plano_contas` para `(admin_id, codigo)`,
  **derruba e recria 6 FKs** e **copia contas entre tenants**. É a mais
  invasiva de toda a fila.

A 218 foi desenhada para produção: idempotente, **tudo numa transação só**
(`with db.engine.begin()`), e se qualquer passo falhar, a transação inteira
reverte. Não existe estado "meio-migrado". E o boot **aborta** se ela falhar
(`app.py`, política Fase 0.5/1.1 — `raise RuntimeError` em produção), em vez de
servir tráfego contra schema inconsistente.

> ⚠️ **Mas a 218 só foi testada contra o banco de DEV** — que foi recriado
> vazio em 22/07. O teste que prova que ela roda íntegra em cima de dados
> reais **ainda não existe**. É a Fase 0 do plano abaixo.

---

## Camada 2 — As fotos: aqui há perda real, hoje

Duas armadilhas do `ESTADO-ATUAL.md`, agora com consequência de deploy:

1. **Os uploads estão no disco efêmero do container** porque o volume
   persistente nunca foi criado no painel (`ESTADO-ATUAL`, Travado nº 3).
   Redeploy recria o container → os 13 GB de `static/uploads` **somem**.

2. **`servir_foto` não tem fallback para a base64.** 🔬 Conferido:
   `crud_rdo_completo.py:810` monta `os.getcwd()/static/<caminho>` e, se o
   arquivo não existe, devolve **404** (`:812`) — não cai para a cópia base64
   do banco. `grep -c base64 crud_rdo_completo.py` = **0**. Ou seja, quando os
   arquivos somem, **as fotos quebram na tela**, mesmo a base64 existindo.

Atenuante: 28.860 das 28.870 fotos têm a base64 no banco (`rdo_foto`). O dado
não se perde para sempre — dá para re-extrair para o disco. Mas até alguém
fazer isso, o portal e os RDOs mostram imagem quebrada.

**A armadilha dentro da armadilha:** definir `UPLOADS_PATH` para o volume
**sem** corrigir o descasamento faz **todas** as fotos sumirem da tela
imediatamente — `salvar_foto_rdo` passa a gravar em `$UPLOADS_PATH/rdo/…` mas
`servir_foto` continua procurando em `os.getcwd()/static/…`
(`crud_rdo_completo.py:810`). O caminho de leitura tem de ser corrigido
**antes** de montar o volume, não depois.

---

## Camada 3 — O que deployaria hoje não é o que trabalhamos

🔬 O branch `fix/fase-0-estancar` está **35 commits à frente de `origin/main`**,
e nada foi pushado (`ESTADO-ATUAL`, Travado nº 2 — falta o `gh auth setup-git`).
O EasyPanel builda do GitHub. Um deploy hoje subiria o `origin/main` antigo:

- **sem** as correções D1–D5 (o faturamento de revisão ainda erra, o portal
  ainda aprova compra fora de escopo, etc.);
- **sem** a Fase 1 inteira;
- e — o mais perigoso — provavelmente **sem** a própria política de
  "backup-aborta-deploy" e "migração-aborta-boot", que são justamente o que
  torna o deploy seguro.

Ou seja: deployar hoje é o pior dos dois mundos — o risco do código velho, sem
a proteção do código novo.

---

## O pipeline JÁ é auto-protegido — falta ligar duas coisas

A parte boa: a Fase 0.5 já construiu a rede de segurança. Só está desconectada.

```
entrypoint  →  backup_banco.py --criar  →  falhou? ABORTA o deploy (exit 1)
            →  sucesso?  →  migrations  →  falhou? ABORTA o boot (RuntimeError)
            →  sucesso?  →  app sobe
```

Conferido em `docker-entrypoint-easypanel-auto.sh:124-131`. A corrente é sólida.
O elo que falta é físico:

- **`backup_banco.py` grava em `SIGE_BACKUP_DIR` (default `/var/backups/sige`),
  que é efêmero** sem o volume. Então hoje o backup ou (a) "tem sucesso" e
  evapora com o container, ou (b) falha e — corretamente — aborta o deploy.
  Nas duas hipóteses, **não há de onde restaurar**.
- Backup **agendado** não existe (pendência aberta da Fase 0.5). Só o
  pré-migração.

---

## O plano — cinco fases, cada uma com um portão verificável

Ordem escolhida para que **nada dependa de algo ainda não provado**. Cada fase
tem um comando que a fecha; não passe adiante sem o verde.

### Fase 0 — Provar a migration 218 contra dados reais (antes de qualquer deploy)

O único risco de dados do deploy é a 218 em cima de produção. Prove-a **fora**
de produção primeiro:

1. `pg_dump` do banco de produção para um banco descartável (Postgres local ou
   um segundo banco no painel).
2. Rodar `executar_migracoes()` contra ele e conferir os invariantes que os
   testes da Fase 0.6 checam: **0 partidas órfãs**, PK composta nas 6 tabelas,
   contagem de contas por tenant coerente.
3. Rodar o **gate completo** apontando `DATABASE_URL` para esse banco.

**Portão:** gate verde sobre uma cópia dos dados reais. Sem isso, a 218 é uma
aposta.

### Fase 1 — Dar um destino durável ao backup

1. Criar o **volume persistente** no EasyPanel (um único volume serve os dois
   usos).
2. Apontar `SIGE_BACKUP_DIR` para dentro dele.
3. Rodar `python scripts/backup_banco.py --criar` **manualmente** e confirmar
   que o arquivo `.dump` fica lá depois de reiniciar o container.
4. Fazer **um restore de ensaio** desse dump num banco descartável
   (`--sem-fotos` existe para isso — `scripts/backup_banco.py:317`). Backup que
   nunca foi restaurado não é backup.

**Portão:** um dump em volume persistente, restaurado com sucesso.

### Fase 2 — Resolver as fotos antes de montar o volume de uploads

1. Corrigir o descasamento de caminho: `servir_foto` (`crud_rdo_completo.py:810`)
   e `salvar_foto_rdo` têm de ler/gravar no **mesmo** lugar. Decisão sua
   (abaixo) sobre qual dos dois manda.
2. Só então apontar `UPLOADS_PATH` para o volume.
3. Migrar os 13 GB atuais para o volume **ou** re-extrair da base64
   (`rdo_foto`) — as duas funcionam; ver decisão.

**Portão:** uma foto antiga e uma foto nova, ambas servidas por HTTP 200
depois de um restart do container.

### Fase 3 — Pushar o código e passar no CI

1. `gh auth setup-git` (o `gh` já está autenticado — `ESTADO-ATUAL`, Travado
   nº 2).
2. Push do branch, abrir PR, **CI verde** (o CI nunca rodou verde porque nunca
   houve push).
3. Merge para `main`.

**Portão:** `origin/main` contém os 35 commits e o CI está verde.

### Fase 4 — Deploy, com a rede de segurança ativa

1. **Rotacionar `SESSION_SECRET` e a senha do Postgres** no painel — estão no
   histórico do git para sempre (`ESTADO-ATUAL`, Travado nº 1). Com a chave de
   sessão, forja-se cookie de qualquer usuário de qualquer tenant. Isto é
   pré-requisito de segurança do deploy, não opcional.
2. Confirmar `SIGE_ENABLE_DEMO_SEED=false` (senão o seed demo roda em
   produção).
3. Deploy. O entrypoint agora: faz backup **que persiste** → migrations
   (incluindo a 218 já provada) → app sobe. Se qualquer elo falhar, aborta
   antes de tocar em dado.
4. Pós-deploy: `GET /health` verde, e reconferir os invariantes da 218 em
   produção.

**Portão:** `/health` verde e 0 partidas órfãs em produção.

---

## As decisões que são suas (nenhuma me cabe)

| # | Decisão | Recomendação |
|---|---|---|
| **A** | Fotos: migrar os 13 GB do disco para o volume, ou re-extrair da base64? | **Re-extrair da base64** — é a fonte da verdade que sobreviveu, e força a validar que a base64 está íntegra. Migrar o disco carrega para o volume um estado que já pode ter buracos. |
| **B** | Descasamento de caminho: `servir_foto` passa a ler de `UPLOADS_PATH`, ou `salvar_foto_rdo` volta a gravar em `static/`? | **`servir_foto` lê de `UPLOADS_PATH`** — é o caminho para tirar as fotos do container de vez. Voltar a gravar em `static/` é reintroduzir o problema. |
| **C** | Backup agendado: job do EasyPanel ou APScheduler? | **Job do EasyPanel** (`ESTADO-ATUAL` já recomenda) — não morre com o worker, não depende do app estar de pé. |
| **D** | Provar a 218: banco local descartável ou segundo banco no painel? | Tanto faz — o que importa é que **não seja produção**. |

---

## Se você precisar deployar HOJE, sem fazer o plano

Contra minha recomendação, mas honesto: o mínimo irredutível é **um só passo**.

    # no shell do container do banco (ou com DATABASE_URL de produção):
    pg_dump --format=custom --no-owner --no-privileges \
      --file /caminho/FORA/do/container/sige_prod_$(date +%Y%m%d).dump \
      "$DATABASE_URL"

Guarde esse arquivo **fora do EasyPanel** (sua máquina, Drive). É a diferença
entre "provavelmente não perco" e "não perco". Mas note que isso protege só a
Camada 1 — as fotos (Camada 2) continuam indo embora no redeploy, e o código
velho (Camada 3) continua sendo o que sobe.
