# DOSSIÊ DO REPOSITÓRIO — EnterpriseSync-1 (SIGE / Veks)

> Data: 2026-07-21. Método: quatro frentes de investigação paralelas sobre o
> repositório e o banco PostgreSQL acessível, com os achados de maior
> gravidade reverificados manualmente. Regra: toda afirmação com
> `arquivo:linha` ou comando + saída. **"Não sei" / "não medido" é resposta
> registrada como LACUNA, não substituída por estimativa.**
>
> Marco temporal: as medições de código foram feitas entre `664bc67` e
> `f090b09`. Onde a Fase 0 já corrigiu um achado, isso está marcado.

---

## ⚠️ Leia isto primeiro

Três coisas deste dossiê são mais urgentes que qualquer decisão de produto:

1. **Há credencial de produção viva no git.** `.env.easypanel` está rastreado
   em `main` com o `SESSION_SECRET` do Flask (frase adivinhável, padrão
   `sige-<palavra>-<ano>`) e a `DATABASE_URL` com senha. Com a chave de
   sessão, forja-se cookie de qualquer usuário de qualquer tenant sem
   explorar nenhuma outra falha. Apagar o arquivo não resolve — **só
   rotacionar resolve**. Detalhe em §17.
2. **Não existe backup de banco.** E o entrypoint de produção imprime
   `"💾 Criando backup de segurança"` **sem executar comando nenhum**,
   imediatamente antes de rodar migrações. §18.
3. **Você não saberia que foi invadido.** Sem access log, sem `before_request`,
   sem tabela de auditoria de acesso, com `ProxyFix` sem `x_for` (IP do
   cliente nunca é registrado) e `logger.debug` globalmente suprimido por um
   `basicConfig` duplicado. §19.

---

## Sobre o banco medido — ressalva que vale para todo o D4

O PostgreSQL acessível (`heliumdb`) **não contém dados de produção**. Dos
6.479 usuários `ADMIN`, **todos** têm e-mail em domínio sintético
(`test.local` 4.688, `t.local` 1.005, `sige.test` 712, `e2e.local` 77,
outros 18); o único plausível é `admin@construtoraalfa.com.br`, que é a
fixture `scripts/seed_demo_alfa.py`. **2.461 admins foram criados hoje.**

Não há tenant "Veks". O que existe é o rastro dos dados da Veks **sem** o
tenant: `cliente.nome = 'Grupo Mônica / Kabod Cabana'` aparece 3.040 vezes e
`obra.nome = 'Baias Kabod'` outras 3.040 — **uma obra por tenant descartável**,
porque a obra real da Veks é usada como fixture e re-semeada a cada execução
da suíte.

**Consequência:** percentuais e proporções abaixo são informação estrutural
válida (refletem os caminhos de código que criam os registros). Contagens
absolutas **não** dimensionam produção.

---

# D1 — Multitenancy e identidade

## 1. O que é `admin_id`, quantos tenants, e qual é a Veks

`admin_id` é uma **auto-FK na tabela `usuario`** (`models.py:36`):

```python
admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
```

**Não existe entidade `Empresa`/`Tenant`.** O tenant *é* uma linha de
`usuario` com `tipo_usuario=ADMIN`. A identidade da empresa mora numa tabela
satélite **opcional**, `ConfiguracaoEmpresa` (nome, CNPJ, cores, BDI padrão).

Consequências diretas dessa modelagem:

- Um tenant **não pode ter dois donos** nem transferir propriedade.
- **Apagar o usuário admin apaga a empresa inteira em cascata** — as FKs
  criadas pela migração universal usam `ON DELETE CASCADE`
  (`migrations.py:4620-4624`).
- Um tenant sem `ConfiguracaoEmpresa` **não tem nome**: 6.479 admins, 645
  configurações.

| Métrica | Valor |
|---|---|
| Usuários `ADMIN` (tenants potenciais) | 6.479 |
| `SUPER_ADMIN` / `FUNCIONARIO` | 6 / 93 |
| `admin_id` distintos em `obra` | 5.630 |
| **Tenants com dado de negócio real** | **0** |

**LACUNA:** não é possível dizer daqui qual seria o `admin_id` da Veks em
produção. Exigiria acesso ao banco de produção.

## 2. Como o tenant é resolvido — e onde falha

**Não há resolução por subdomínio nem por sessão.** `app.py:125` faz
`SERVER_NAME = None`; **não existe `before_request` global**. Toda resolução
deriva de `current_user`, reimplementada dezenas de vezes.

Foram contadas **41 definições distintas** de resolvedor de `admin_id`, em
6 famílias com semânticas diferentes:

| # | Resolvedor | Local | Sem usuário | Consumidores |
|---|---|---|---|---|
| **A** | `get_tenant_admin_id()` | `utils/tenant.py:15` | **Fail-closed** → `None` | 43 imports — **é o canônico** |
| B | `get_admin_id()` | `multitenant_helper.py:10` | fail-closed, mas o `except` devolve `current_user.id` | 30 |
| C | `get_admin_id_robusta()` | `views/helpers.py:376` + cópia byte-a-byte em `views/obras.py:454` | `None`, **exceto no `except` → `1`** | 2 |
| D | `get_admin_id_dinamico()` | `views/helpers.py:409` + cópia em `views/api.py:996` | ~~fail-open → `return 1`~~ | ✅ **corrigido na Fase 0** |
| E | `get_safe_admin_id()` | `production_routes.py:11` | ~~ignorava `current_user`, `return 2`~~ | ✅ **corrigido na Fase 0** |
| F | ad-hoc | ≈30 arquivos, um cada | varia | 1 cada |

Caminhos legítimos não-`current_user`: **token de portal**
(`portal_obras_views.py:52`, `secrets.token_urlsafe(32)` — bem construído) e
**HMAC com `admin_id` no envelope** (`importacao_views.py:41-70`), que é o
**único ponto do sistema com anti-replay cross-tenant explícito** — o padrão
a copiar.

### Estado atual das falhas (pós-Fase 0)

| Furo | Status |
|---|---|
| `views/rdo.py` — tenant vindo de `request.form['admin_id_form']` (escrita entre tenants) | ✅ corrigido |
| `production_routes.py` — 6 rotas anônimas, tenant por heurística | ✅ corrigido |
| `api_funcionarios.py` — `utils.auth_utils` não existe, fallback `return 10` | ✅ corrigido |
| `categoria_servicos.py` — `return 10` em 3 caminhos, 2 rotas de escrita | ✅ corrigido |
| `views/employees.py` — `@admin_required` comentado "temporariamente" | ✅ corrigido |
| `views/users.py` — `get_or_404` sem predicado de tenant | ✅ corrigido |
| `relatorios_funcionais.py` — 3 relatórios agregando todas as empresas | ✅ corrigido |
| **`views/rdo.py:1680`** — `admin_id = funcionario.admin_id if funcionario else 10` | 🟠 **aberto** |
| **`utils/tenant.py:101`** — backdoor `ALLOW_TENANT_AUTODETECT=true` | 🟡 **aberto** |
| **`views/rdo.py:2149`** — e-mail de tenant específico chumbado (`"funcionario@valeverde.com"`) | 🟡 **aberto** |
| **137 lookups `.query.get()` sem predicado de tenant** | 🟠 **aberto** — cada um é um IDOR em potencial |
| **21 tabelas com `admin_id` nullable** (incl. `obra`, `rdo`, `funcionario`) | 🟠 **aberto** — linha sem tenant some de todo filtro sem erro |

## 3. Dado compartilhado entre tenants

**Não existe. Tudo é replicado por tenant.**

Das 178 tabelas, **177 têm `admin_id`**. A única sem é `migration_history`
(metadado de infra). Nenhuma flag `is_global`/`padrao_sistema` em modelo algum.

Todo catálogo que num SaaS seria global aqui é semeado por tenant, via
`seed_defaults(admin_id)`:

| Tabela | Linhas | Tenants distintos |
|---|---:|---:|
| `insumo` | 100.233 | 2.762 |
| `categoria_fluxo_caixa` | 30.060 | 668 |
| `categoria_fornecedor` | 15.336 | 213 |
| `plano_contas` | 45 | 1 (semeado preguiçosamente na 1ª aprovação de proposta) |

**Implicação:** não há como corrigir um insumo, uma composição ou o plano de
contas "para todos". Uma correção de catálogo é uma migração de N tenants — e
`migrations.py:12641,13335,13501` **já fazem isso em loop** por essa razão.
O custo de manutenção cresce **linearmente com o número de clientes**.

## 4. SaaS por concepção ou sistema interno que herdou multitenancy?

**Foi declarado SaaS; o código conta a história de um sistema interno com
multitenancy enxertada por script.**

| A favor de SaaS | Contra |
|---|---|
| `replit.md:2` — "multi-tenant business management system" | **Zero self-service signup** — só `POST /super-admin/criar-admin` |
| `SUPER_ADMIN` + painel de admins | **Zero cobrança/plano/trial/gateway** — grep por `billing\|subscription\|stripe` → 0 |
| Feature-flags por tenant (`versao_sistema`, `cronograma_mpp_ativo`) | **Zero onboarding** |
| White-label (cores, logo, BDI padrão) | **Um schema, um banco, sem RLS** |

A evidência decisiva é `fix_all_admin_id_universal.py:1-3`, que se
autodescreve: *"AUTO-FIX UNIVERSAL: Adiciona admin_id em TODAS as tabelas que
precisam / Executa automaticamente no startup"*. E traz um
`BACKFILL_STRATEGIES` mapeando cada tabela ao caminho para **deduzir** o
tenant (`'rdo': 'obra_id'`, `'registro_ponto': 'funcionario_id'`). A migração
universal faz `ADD COLUMN admin_id` → backfill → **conta órfãos** → `SET NOT
NULL` → `CASCADE`. É a assinatura textual de dados que **nasceram sem tenant**.

As três marcas dessa origem estão todas presentes: **(a)** o tenant é o
usuário-dono, não uma entidade; **(b)** o `admin_id` foi inferido por
relacionamento num backfill; **(c)** sobravam fallbacks para tenants
concretos (`1`, `2`, `10`) espalhados — todos removidos pela Fase 0.

**LACUNA:** o histórico Git começa em 2026-05-27 já na "MIGRAÇÃO 154" — está
truncado. Não é possível datar *quando* a multitenancy entrou.

---

# D2 — Rotas, eventos e acoplamento

## 5. Inventário de rotas

**724 rotas · 48 sem decorator de autenticação** (eram 64 antes da Fase 0).
Lista completa em [`docs/anexos/A-rotas-sem-autenticacao.md`](docs/anexos/A-rotas-sem-autenticacao.md).

| Decorator | Rotas |
|---|---:|
| `login_required` | 588 |
| `admin_required` | 190 |
| `funcionario_required` | 16 |
| `cronograma_import_required` | 12 |
| `super_admin_required` | 4 |
| **nenhum** | **48** |

As 48 sem auth, classificadas:

| Criticidade | Rotas | Leitura |
|---|---:|---|
| `TOKEN (legítimo)` | 11 | portal do cliente/proposta — autenticação por token, é o desenho correto |
| `EXPOE DADO (página)` | 18 | template renderizado para anônimo |
| `EXPOE DADO (api)` | 11 | endpoint JSON legível por anônimo |
| **`GRAVA`** | **8** | **aceita POST/PUT/PATCH/DELETE sem autenticação** |

Concentração: `portal_obras_views.py` (8, legítimo), `api_organizer.py` (5),
`views/rdo.py` (5), `api_servicos_obra_limpa.py` (4).

> **Nota:** "sem `@login_required`" não é automaticamente vazamento. O
> contra-exemplo é `views/dashboard.py:189` — sem decorator, mas `abort(403)`
> se `admin_id is None`, com o comentário *"NUNCA auto-detectar admin_id de
> outros tenants"*. **O que decide é se o resolvedor falha aberto ou fechado.**
> As rotas fechadas na Fase 0 foram exatamente as que combinavam ausência de
> auth **com** resolvedor fail-open.

## 6. `event_manager.py`

Pub/sub **síncrono, in-process, sem fila e sem persistência**
(`event_manager.py:13-72`). Registry é atributo **de classe** — estado global
do processo. `emit()` itera na **ordem de registro, que é a ordem de import**.

**17 eventos, 19 handlers**, em dois namespaces: legado `snake_case` (escreve
no banco) e catálogo `dominio.acao` (só alimenta webhook n8n, best-effort).

### A cascata da aprovação de proposta

Um clique em "aprovar" dispara, **na mesma transação**:

1. `propagar_proposta_para_obra` (`event_manager.py:871`) — resolve/cria
   `Cliente` (com fallback sintético), procura a `Obra` por 3 caminhos, gera
   código `OBR####`, **cria a Obra**, gera `token_cliente` (**habilita o
   portal público**), faz o back-link.
2. `handle_proposta_aprovada` (`handlers/propostas_handlers.py:73`) —
   **semeia o plano de contas inteiro do tenant** se não existir, cria
   `LancamentoContabil` + 2 partidas, cria **1 `ItemMedicaoComercial` por
   `PropostaItem`**, materializa cronograma + versão inicial.
3. **Efeito de 2ª ordem invisível:** um listener `after_insert` em
   `ItemMedicaoComercial` cria o `ObraServicoCusto` pareado.

**≥9 tabelas de 5 módulos escritas por um clique.**

### Efeitos colaterais que vão morder

| # | Problema |
|---|---|
| 🔴 **6a** | **A corretude depende da ordem de import em `app.py`.** `event_manager` na linha 351, `handlers.propostas_handlers` na 364 — por isso o handler que *cria* a Obra roda antes do que a *usa*. Trocar duas linhas quebra a cascata **silenciosamente** (o handler 2 só loga "sem obra vinculada — pular"). O próprio código admite a dependência por escrito |
| 🔴 **6d** | `duplicar_rdo` emite **só** o webhook `obra.rdo_publicado`, **sem** `rdo_finalizado`. O cliente recebe "RDO publicado" e **nenhum custo é lançado** |
| 🟠 **6b** | `app.py:358` importa `handlers.folha_handlers` — **módulo que não existe**. Engolido por `try/except`; o boot loga "Handler de folha registrado" sobre algo que nunca existiu |
| 🟠 **6c** | `nota_fiscal_paga` é handler **órfão** — registrado, nunca emitido. A integração "NF paga → lançamento" está morta |
| 🟠 **6e** | Dois modos de atomicidade convivem. Só `proposta_aprovada` usa `raise_on_error=True`. Nos demais, `emit()` retorna `True` se **pelo menos um** handler passou — em `rdo_finalizado`, se o lançamento de custos explodir e o recálculo passar, **o chamador vê sucesso e comita um RDO sem custos** |
| 🟡 **6g** | O grafo de causalidade é **invisível no ponto de chamada**. Todos os handlers usam import tardio, então nem a lista de imports revela o acoplamento |

## 7. Grafo de dependência e ciclos

| Top fan-in | | Top fan-out | |
|---|---:|---|---:|
| `models` | **125** | `app` | **53** |
| `app` | 66 | `views/obras.py` | 23 |
| `utils.tenant` | 25 | `views/rdo.py` | 22 |
| `services.dropdown_service` | 13 (**0 top-level**) | `main` | 19 |

**Ciclos:** o grafo top-level tem **1 componente fortemente conexa de 44 nós
com 53 ciclos elementares**. Incluindo imports tardios, a SCC vira **115
nós — praticamente todo o sistema**. Há **809 imports tardios** internos,
cada um um ciclo contornado à mão.

O padrão dominante (17×) é `app ↔ <módulo>_views`: todo view faz
`from app import db` no topo. **Isso só não quebra por causa da ordem física
das linhas em `app.py`** — `from views import main_bp` está na linha 386,
depois de `models` (179) e `event_manager` (351). **Mover qualquer registro
de blueprint acima da linha 386 quebra metade do sistema**, e isso não está
declarado em lugar nenhum.

**55 blueprints** registrados em 2 arquivos, cada um num `try/except
ImportError` que degrada para `warning` — um blueprint pode falhar ao
carregar e o app sobe com as rotas ausentes.

### Onde vai doer

**(a) RBAC por papel** — ~300 pontos de uso a reescrever (190 `@admin_required`
+ 110 checagens ad-hoc de `current_user.tipo_usuario`). `auth.py` tem fan-in
14, **100% top-level** — é o lugar seguro para novos decorators. Mas qualquer
decorator que consulte o **banco** importa `models` → entra na SCC de 115 nós
→ vai precisar de import tardio. Não existe tabela de papéis/permissões, e
`GESTOR_EQUIPES` está no enum sem nenhum decorator que o trate.

**(b) Escopo por obra** — o bloqueio é **estrutural**: não existe modelo
`Usuario ↔ Obra`, e `Obra.responsavel_id` aponta para **`Funcionario`**, que
**não tem FK para `Usuario`**. Hoje a ligação é comparação de e-mail em
runtime. **O responsável pela obra não é um usuário logável.** São 3.047
ocorrências de `obra_id` no código, e **não há ponto único onde injetar o
escopo** (sem `before_request`, 55 blueprints em 2 arquivos).

**(c) Máquina de estados da Obra** — surpreendentemente **fácil**:
`grep -rnE "obra\.status\s*=[^=]"` em produção retorna **exatamente 1 linha**
(`views/obras.py:861`). Um método `Obra.transicionar(estado, autor)` + guard
ali cobre 100% das mutações. O que dói é o **backfill**: já há duas grafias no
banco (`'Em andamento'` 6.733 / `'Em Andamento'` 47) e **6 vocabulários
distintos** no código — `views/dashboard.py:428` tem uma query com 5 grafias.
⚠️ A FSM **não deve ir para `models.py`**: agravaria a SCC. Deve viver em
`services/obra_estado.py`.

## 8. Rotas e telas duplicadas

**Regra de desempate no Flask: vence a primeira registrada.**

### Colisões exatas — uma rota sombreia a outra

| Path | Vence | Perde | Gravidade |
|---|---|---|---|
| `GET /api/funcionarios/<int:X>` | `views/api.py:24` — trata o int como `obra_id` **e o ignora**, devolve **lista** | `api_funcionarios.py:138` — devolveria **um objeto** | 🔴 **única colisão que devolve resposta errada em vez de 404** |
| `GET /api/funcionarios/buscar` | `api_funcionarios.py:90` | `api_funcionarios_buscar.py:20` | arquivo inteiro morto |
| `GET /health` | `views/dashboard.py:25` | `health.py:14` | arquivo inteiro morto |
| `GET /rdo`, `/rdo/novo`, `POST /rdo/excluir/<id>` | `views/rdo.py` | `crud_rdo_completo.py` | — |
| `GET /rdo/editar/<id>` | `rdo_editar_sistema.py:20` | `crud_rdo_completo.py:220` | 🟠 a perdedora redireciona para a **mesma URL** — loop infinito se um dia vencer |

### Gravadores de RDO: são **quatro**

| # | Local | Estado |
|---|---|---|
| 1 | `views/rdo.py:3854` `salvar_rdo_flexivel` | ✅ **canônico (criação)** |
| 2 | `rdo_editar_sistema.py:166` | ✅ **canônico (edição)** |
| 3 | `views/rdo.py:2516` `rdo_salvar_unificado` | ⚠️ legado mas **vivo** — chamado por `funcionario_criar_rdo` |
| 4 | `crud_rdo_completo.py:230` | ❌ morto (decorador removido) |

`crud_rdo_completo.py` **não é descartável**: as rotas de foto continuam vivas
(`:663`, `:857`, `:885`). É **metade vivo / metade sombreado**.

### Duplicações **ambas vivas** — as que realmente doem

🔴 **`PedidoCompra` é criado por duas rotas com efeitos divergentes:**

| | `compras_views.py:533` | `views/obras.py:2638` |
|---|---|---|
| Efeitos | `GestaoCustoPai` + `AlmoxarifadoMovimento` + estoque + parcelas | **nenhum** |

Pedidos criados pela tela da obra **não geram custo nem estoque**. Mesma
entidade, dois contratos.

**Trio "serviço da obra"** — 3 blueprints, 10 rotas, 2 tabelas, **0 uso no
frontend**. `main.py:120` comenta que o CRUD antigo foi removido — **mas os 3
blueprints seguem registrados**, e um deles grava via **SQL cru** numa tabela
legada.

**Mapa de concorrência**: V1 tem **0 referências em templates**, V2 tem **84**.
Mas `views/obras.py:1811-1821` ainda consulta V1 **a cada carregamento da tela
de obra**, passando ao template uma variável nunca consumida.

**Todas as tabelas legadas estão vazias** (`mapa_concorrencia`, `servico_obra`,
`servico_obra_real`, `alocacao_equipe` = 0 linhas) — remover não exige
migração de dados **neste banco**. ⚠️ Confirmar em produção antes de dropar.

---

# D3 — Modelos e migrações

## 9. `models.py`

| Métrica | Valor |
|---|---|
| Linhas | **7.610** (357 KB) |
| Classes `db.Model` | **176** |
| Arquivos que importam `models` | **180** |

Domínios misturados (todas as 176 classificadas): Financeiro 21, Compras/
Almoxarifado 19, Orçamento 16, Obras 12, Contabilidade 12, RH/Ponto 11,
Cronograma 11, Comercial 11, Folha 9, RDO 9, CRM 9, Frota 7, e mais 8 menores.

**O plano de quebra existe como comentário, não como código.** O arquivo é
organizado por banners `# ====== MÓDULO N: ... ======` — **as costuras já
estão desenhadas**. E há evidência de uma tentativa abortada:
`models.py:1352` diz *"MÓDULO DE PROPOSTAS (MOVIDO PARA models_propostas.py)"*
— **esse arquivo não existe**, as classes voltaram, e o comentário mentiroso
ficou.

O cabeçalho declara o motivo do monólito (`models.py:1-2`): *"Arquivo único
para eliminar dependências circulares"*. Mas há **lógica de negócio dentro**:
listeners de recálculo (`:6061`), hook que auto-clona orçamento operacional
(`:7013`), lançamento automático de ponto (`:4008-4128`). E **gerações
duplicadas coexistem**: Frota tem 3 encarnações, Almoxarifado 2, Mapa 2.

## 10. Migrações

**Alembic NÃO está em uso** (`to_regclass('alembic_version')` → `None`), apesar
de `flask-migrate` estar no `pyproject.toml`.

O sistema real: `migrations.py` (**14.168 linhas**) com lista numerada
`(número, descrição, função)` e idempotência via `migration_history`.
**180 registros, todos `success`**, faixa 20→212, não contígua (há
aposentadorias deliberadas).

⚠️ **`executar_migracoes()` engole exceções globais** (`migrations.py:4055`) e
falhas individuais só geram `warning` — **o boot nunca falha por migração
quebrada**.

### Drift de colunas: 8 tabelas, 10 colunas fantasma

Colunas que existem no Postgres e **nenhum modelo declara** — e que **não
aparecem em `migrations.py` nem em nenhum `.sql`**:

`almoxarifado_movimento.updated_at`, `cronograma_template_item.peso_medicao`,
`custo_veiculo.tarefa_cronograma_id`, `gestao_custo_filho.tarefa_cronograma_id`,
`movimentacao_estoque.tarefa_cronograma_id`, `propostas_comerciais.origem`,
`rdo_subempreitada_apontamento.{gestao_custo_pai_id, lucro_pct, verba_unica}`,
`weekly_plan_item.admin_id`.

São resíduos de **colunas criadas à mão fora do sistema de migração**. Como
não há `DROP`, ficam para sempre. Nenhuma é `NOT NULL`, então não quebram.

### 🔴 Drift muito mais grave: índices que a migração nunca criou

**Causa mecânica identificada:** `pre_start.py:32` roda **`db.create_all()`
ANTES** de `executar_migracoes()` (`:40`). Migrações que criam tabela com
guard `IF NOT EXISTS` colocam os `CREATE INDEX` **dentro do ramo de criação**.
Como `create_all()` já criou a tabela — **sem os índices, porque o modelo não
os declara** — a migração cai no `else: SKIP` e **os índices nunca nascem**.

Caso confirmado, `_migration_76_rdo_apontamento_cronograma`
(`migrations.py:5505-5551`): declara `UNIQUE(rdo_id, tarefa_cronograma_id)` +
2 índices. No banco: **só a PK**. A tabela tem **61.923 linhas e 1 índice**.

O espelho do mesmo mecanismo: **60+ pares de índices duplicados**, quando a
migração *consegue* rodar antes e ambos criam o índice com nomes diferentes.
`obra_orcamento_operacional` tem **3 índices idênticos** em `obra_id`.

## 11. Índices — os full scans

| Tabela | linhas | índices | **seq_tup_read** | idx_scan |
|---|---:|---:|---:|---:|
| **`rdo_apontamento_cronograma`** | 61.923 | **1 (só PK)** | **6.621.134.755** | 888 |
| `tarefa_cronograma` | 253.932 | 6 | 4.878.449.044 | 505.607 |
| `cronograma_tarefa_snapshot` | 233.109 | 3 | 2.893.687.414 | 103.526 |
| **`rdo`** | 32.630 | **2** | 227.058.635 | 2.365.051 |
| **`rdo_mao_obra`** | 2.612 | 3 | 119.360.336 | **115** |
| **`gestao_custo_filho`** | 1.658 | 4 (2 duplicados) | 18.647.965 | 15.391 |
| **`cliente`** | 6.065 | **1 (só PK)** | 5.890.642 | 15.587 |

**Índices faltando, em ordem de valor:**

1. **`rdo_apontamento_cronograma(tarefa_cronograma_id, admin_id)`** — 6,6
   **bilhões** de tuplas lidas. É exatamente o índice que
   `utils/cronograma_engine.py:181,233,467,485` pede, **está escrito na
   migração 76** e nunca foi criado. **O mais barato e mais valioso do
   sistema.**
2. `rdo(obra_id)` e `rdo(admin_id)` — hoje só PK + `numero_rdo`; o motor de
   cronograma faz join por `rdo_id` dos dois lados.
3. `obra(admin_id, ativo)` — o `(codigo, admin_id)` existente **não serve**
   (`admin_id` é a 2ª coluna) e o padrão do dashboard é `filter_by(admin_id=,
   ativo=)`.
4. `gestao_custo_filho(admin_id, data_referencia)` e `(pai_id)`.
5. `cliente(admin_id)`; `pedido_compra(admin_id, obra_id)`;
   `fluxo_caixa(admin_id, data_movimento)`.
6. **Dropar os 60+ índices duplicados** — penalizam escrita sem ganho.

> Ressalva: as estatísticas vêm de um banco de dev martelado pela suíte. Os
> *ratios* são diagnósticos válidos (refletem os planos que o schema permite);
> os valores absolutos não projetam produção.

---

# D4 — Dados

## 12. Volumetria

| Tabela | Total | | Tabela | Total |
|---|---:|---|---|---:|
| `cronograma_tarefa_snapshot` | 270.619 | | `rdo` | 32.630 |
| `tarefa_cronograma` | 263.712 | | `orcamento_item` | 32.189 |
| `item_medicao_cronograma_tarefa` | 187.974 | | `medicao_contrato` | 18.234 |
| `obra_servico_custo_item` | 157.523 | | `obra` | 6.806 |
| `composicao_servico` | 100.257 | | `cliente` | 6.070 |
| `insumo` | 100.233 | | `cronograma_versao` | 5.141 |
| `rdo_apontamento_cronograma` | 61.923 | | `propostas_comerciais` | 3.560 |
| `obra_servico_custo` | 38.131 | | `pedido_compra` | 132 |
| `item_medicao_comercial` | 37.509 | | **`fluxo_caixa`** | **15** |
| `rdo_foto` | 22.461 | | **`mapa_concorrencia*` (7 tabelas)** | **0** |

Leituras que valem apesar do ruído: **`medicao_obra` tem 4 linhas** contra
`medicao_contrato` 18.234 — a medição "oficial" foi substituída pelo caminho
físico-financeiro. E o módulo **Mapa de Concorrência está 100% vazio nas 7
tabelas**, apesar de 3 migrações dedicadas.

## 13. Uso real vs. cadastro morto

**~65 das 178 tabelas (37%) estão completamente vazias.** Módulos inteiros
existem como schema e código sem um único registro:

| Tier | Módulos |
|---|---|
| **Uso contínuo** | Cronograma/RDO ≫ Orçamento/Proposta ≫ Custos de obra ≫ Compras/Almoxarifado |
| **Congelado** | **CRM** (zero escrita em 5+ semanas) · **Fluxo de Caixa** (15 linhas, **escrito uma única vez pelo seed**) · **Frota** (morta após o seed) |
| **Nunca nasceu** | **Contabilidade** (9 tabelas a zero) · **Folha** (6 a zero) · **Equipes/Alocação** (5 a zero) · **Mapa de Concorrência** (7) · Estoque v1 · Serviços v1 · **Motor de dropdowns** (migrações 173-177, seed prometido, 0 linhas) |

## 14. 🔴 Órfãos (`obra_id IS NULL`) — o dimensionamento da Fase 4

### Estrutura

| Tabela | `obra_id` nullable? |
|---|---|
| `conta_pagar`, `conta_receber`, `fluxo_caixa`, `gestao_custo_filho`, `pedido_compra`, `receita`, `reembolso_funcionario`, `registro_alimentacao`, `lancamento_transporte` | **SIM** |
| `custo_obra`, `alimentacao_lancamento` | NÃO |
| **`gestao_custo_pai`** | **coluna não existe** |

### Contagem

| Tabela | Total | Órfãos | % |
|---|---:|---:|---:|
| **`reembolso_funcionario`** | 20 | **20** | **100%** |
| `conta_pagar` | 100 | 20 | 20,0% |
| `pedido_compra` | 132 | 20 | 15,2% |
| `conta_receber` | 119 | 11 | 9,2% |
| `gestao_custo_filho` | 1.658 | 66 | 4,0% |
| **`gestao_custo_pai`** | **1.118** | **1.118 estruturalmente** | **100%** |

### O achado que muda a Fase 4

**`gestao_custo_pai` não tem coluna `obra_id`, e tem 1.118 linhas.** É a raiz
da árvore de custos (`gestao_custo_filho.pai_id → gestao_custo_pai.id`). Ou
seja, **100% da obrigação financeira do sistema é estruturalmente órfã de
obra** — o vínculo só existe nos filhos, e lá é nullable com 4% de nulos.

Como o pai não tem `obra_id`, **não há recuperação possível por esse caminho**
para os 66 filhos órfãos. A Fase 4 precisa **primeiro criar
`gestao_custo_pai.obra_id`** e decidir a regra de derivação (via filhos? via
`fechamento_id`? via `pedido_compra`?), porque hoje não há de onde tirar o
valor por SQL puro.

**O problema não é histórico — é corrente.** Todo o eixo transacional está
concentrado em 2026; cada linha órfã foi criada nas últimas 8 semanas por
código que roda hoje. Não existe "dívida legada de antes da regra": **a regra
nunca existiu**.

**LACUNA:** o volume real da Fase 4 não é mensurável neste banco.

## 15. Qualidade dos dados de CRM

**Correção de premissa:** `Lead` **não tem coluna `telefone`** — o campo é
`contato`.

Os 12 leads são 100% do seed (`crm_seeds.py`), todos com contato e e-mail
plausíveis, zero duplicatas. **A qualidade é 100% porque os dados são
fabricados** — isso não diz nada sobre o cadastro real.

**Onde a sujeira aparece de verdade é em `cliente`** (6.070 linhas):

| Métrica | Valor |
|---|---:|
| Com telefone | **32,0%** |
| Com e-mail | **37,9%** |
| Telefone `11988887777` | **1.288 ocorrências** |
| Telefones estruturalmente inválidos (`119`, `1199`, `11999`) | **69 registros** |

Os telefones repetidos são fixture, mas **`119` e `1199` são inválidos e o
sistema aceitou sem reclamar** — isso é achado real sobre ausência de
validação. E há e-mails repetidos, confirmando que **não existe constraint de
unicidade em `cliente.email`**, nem por tenant.

**LACUNA:** sem leads orgânicos, a taxa real de preenchimento e duplicidade do
CRM em uso não é mensurável. O que se afirma com evidência é do lado do
schema: sem validação de formato, sem unicidade, sem normalização de telefone.

---

# D5 — Operação e infraestrutura

## 16. Onde roda e como é o deploy

**LACUNA parcial** — o provedor não é observável de dentro do repo. O que o
repositório afirma: **EasyPanel sobre Hostinger**, container
`python:3.11-slim` (**tag flutuante, sem digest**), WSGI
`gunicorn --workers 2 --timeout 120`, **rodando como root** (nenhum `USER`
nos Dockerfiles).

⚠️ O domínio aparece em **duas grafias divergentes**:
`sige.cassiovillar.tech` (`EXECUTAR_PRODUCAO_AGORA.sh:113`) e
`sige.cassioviller.tech` (`app.py:131`, allowlist do CORS). **Uma está errada
e é a do CORS que vale em runtime.**

**Deploy é um clique manual num painel web.** Não há CI. `git push` → botão
"Deploy/Rebuild" no EasyPanel. Sem gate, sem aprovação, sem rollback
automático de imagem.

### Os entrypoints — 4 shells, 2 Dockerfiles, 5 scripts de deploy

**O usado é `docker-entrypoint-easypanel-auto.sh`.** Evidência: `Dockerfile:46`
faz `COPY docker-entrypoint-easypanel-auto.sh /app/docker-entrypoint.sh` —
**o `docker-entrypoint.sh` da raiz nunca entra na imagem**. Armadilha real:
quem editar o arquivo de nome óbvio não está mexendo em produção.

| Arquivo | md5 | Roda migrações? | Status |
|---|---|---|---|
| `docker-entrypoint-easypanel-auto.sh` | `54c46f…` | ✅ via `pre_start.py` | **EM USO** |
| `docker-entrypoint.sh` | `75cf8e…` | ❌ só `db.create_all()` | morto (sobrescrito) |
| `docker-entrypoint-v10.sh` | `75cf8e…` | ❌ só `db.create_all()` | **duplicata byte-a-byte** |
| `docker-entrypoint-production-simple.sh` | `46c601…` | ✅ inline | órfão |

**A divergência que mais importa:** os dois do meio fazem apenas
`db.create_all()`, que **nunca altera tabela existente**, e **engolem toda
exceção**. Se um fosse ativado por engano, o app subiria "com sucesso" contra
schema desatualizado.

**`Dockerfile.production` está quebrado**: faz `COPY requirements.txt` de um
arquivo que **não existe no repositório**. E dos 5 scripts `deploy_*.sh`,
**4 referenciam arquivos inexistentes** e falhariam imediatamente.

### ⚠️ Auto-seed de demo LIGADO por padrão em produção

`docker-entrypoint-easypanel-auto.sh:350-351`:
```bash
export SIGE_ENABLE_DEMO_SEED="${SIGE_ENABLE_DEMO_SEED:-true}"
export SIGE_ALLOW_PROD_SEED="${SIGE_ALLOW_PROD_SEED:-1}"
```
O próprio comentário diz que os defaults foram invertidos "propositalmente" e
pede *"DEPOIS DO PRÓXIMO DEPLOY BEM-SUCEDIDO, REVERTER"*. **Nunca foi
revertido.** Combinado com `SIGE_FORCE_RESEED`, todo deploy pode apagar e
replantar o tenant Alfa.

## 17. 🔴 Segredos — o item mais grave do dossiê

### Segredos reais commitados, presentes em `main` HOJE

| # | Arquivo:linha | Tipo |
|---|---|---|
| **C1** | `.env.easypanel:6` | **`SESSION_SECRET` de produção** — frase adivinhável `sige-<palavra>-<ano>` |
| **C2** | `.env.easypanel:2` | **`DATABASE_URL`** com credencial, `sslmode=disable` |
| C3/C4 | `deploy_easypanel_final.sh:31,35,108` | os mesmos valores, regravados pelo script |

**Por que C1 é o pior:** o `SECRET_KEY` assina os cookies de sessão. Com ele,
**forja-se cookie válido para qualquer `user_id` de qualquer tenant** — sem
senha, sem vulnerabilidade adicional. E o valor não é aleatório.

**Agravante:** `app.py:33` tem fallback literal
(`"dev-only-fallback-key-not-for-production"`) sem `raise`. Se a variável não
estiver no painel, **produção sobe com uma chave publicada neste repositório**,
e o único sinal é uma linha de log. **Há dois valores adivinháveis possíveis
em produção, e ambos estão no repo.**

**Adicional:** `attached_assets/` tem **589 arquivos `Pasted-*.txt` rastreados**
(o `.gitignore` os cobre, mas `.gitignore` não destrackeia) — contêm logs de
produção com DB URLs reais e uma chave de 43 caracteres base64url
(assinatura de `secrets.token_urlsafe(32)` — chave gerada de verdade).

**Varredura negativa (útil registrar):** zero ocorrências de `sk-`, `AKIA`,
`AIza`, `ghp_`, `xox[bp]-`, `SG.`, JWTs; nenhum `.pem`/`.key` rastreado.

### 🔴 A correção existe e nunca foi mergeada

```
$ git branch -a --contains f7afca0
  fix/bloco2-segredos
$ git rev-list --left-right --count main...fix/bloco2-segredos
402   4
```

Alguém já diagnosticou e corrigiu — a branch troca os valores por
`__defina_no_easypanel__` e força `sslmode=require`. Está **402 commits atrás
de `main` e nunca foi integrada**. Existe também `fix/bloco1-blindagem-acesso`
(5 commits de isolamento de tenant) na mesma situação. **Há um backlog de
segurança já resolvido e perdido em branches órfãs.**

### O que precisa ser feito (não é "apagar o arquivo")

1. **Rotacionar `SESSION_SECRET`** no painel — o valor está no histórico do
   git para sempre. Derruba todas as sessões.
2. **Rotacionar a senha do Postgres.**
3. Trocar o fallback de `app.py:33` por `raise RuntimeError`.
4. Decidir o destino das duas branches órfãs.
5. `git rm --cached attached_assets/Pasted-*.txt` (589 arquivos).

## 18. 🔴 Backup

**Não existe rotina de backup. Nenhuma evidência de restauração testada.**

- `backups/` **não contém backups de banco** — são 7 arquivos de um evento
  único, e **5 dos 6 CSVs têm só o cabeçalho, zero linhas**.
- `pg_dump` aparece em 2 scripts, ambos manuais e ambos quebrados; um grava em
  `/tmp` (**some no restart**).
- **O entrypoint de produção mente sobre backup.**
  `docker-entrypoint-easypanel-auto.sh:118-119` imprime
  `"💾 Criando backup de segurança: $TIMESTAMP"` e **não executa comando
  nenhum** — imediatamente antes de rodar migrações destrutivas.
- Há um `BackgroundScheduler` (`app.py:911`) com **um único job**, de cobertura
  ociosa. Nada de backup. Sem cron, sem celery beat.

**LACUNA:** se o EasyPanel/Hostinger faz snapshot do volume, não é observável
daqui. Verificar no painel e **testar um restore de verdade**.

## 19. 🔴 Logs e monitoramento

`logging.basicConfig(level=logging.INFO)` em `app.py:13`. **Só isso.**

**Bug silencioso:** `main.py:33` faz `basicConfig(level=DEBUG)` — **é no-op**,
porque o root logger já tem handler e não há `force=True`. **Todo
`logger.debug()` do sistema é descartado**, e quem escreveu esperava o
contrário.

**APM/Sentry/Prometheus/OpenTelemetry: zero ocorrências.**

### Como alguém descobriria hoje que a rota anônima foi explorada?

**Não descobriria. Não existe rastro nenhum.** Cadeia completa:

1. **Gunicorn não emite access log** — `--access-logfile` não aparece em
   nenhum Dockerfile ou entrypoint; o default é `accesslog = None`.
2. **Não há `before_request`/`after_request`** em código vivo.
3. **Não há tabela de auditoria de acesso.** Existe **uma única** coluna
   `ip_address` em todo o schema (`models.py:2035`) e ela é sempre `None`,
   porque nada lê `request.remote_addr`.
4. Os logs dentro da rota eram `logger.debug()` → **suprimidos**.
5. **`ProxyFix` sem `x_for`** (`app.py:55`) — `X-Forwarded-For` é ignorado, o
   IP do cliente **nunca** é registrado. Efeito colateral: o rate limiter usa
   `get_remote_address` como chave, então **todos os clientes do mundo
   compartilham o mesmo bucket** (e `default_limits=[]`, storage em memória).

**Agravante:** `main.py:36-80` registra um `errorhandler(Exception)` que
renderiza **o traceback Python completo na página HTML**, com botão "Copiar
Erro Completo", **sem verificação de ambiente**. Qualquer 500 em produção
expõe caminhos, nomes de tabela e trechos de código a quem provocou o erro.

## 20. HTTPS e o Java/MPXJ

**Nenhuma configuração de proxy reverso ou certificado no repositório** — TLS
é responsabilidade do EasyPanel (Traefik), não observável daqui. Evidências
indiretas de que HTTPS existe: `SESSION_COOKIE_SECURE=True` em produção e o
CORS com `https://`.

⚠️ **Detecção de ambiente frágil:** `app.py:24` →
`IS_PRODUCTION = "REPL_ID" not in os.environ`. Produção é definida pela
**ausência** de uma variável do Replit. Qualquer `docker run` local é tratado
como produção e liga `SESSION_COOKIE_SECURE`, quebrando login em HTTP de
forma silenciosa.

### O `.mpp` funcionaria em produção hoje? **NÃO.**

Três bloqueios independentes:

1. **Não há JRE/JDK na imagem** — `grep -niE "java|jre|jdk"` nos Dockerfiles →
   nenhuma ocorrência.
2. **`mpxj` e `jpype1` não são dependências declaradas** — existem só no
   sandbox Replit. `services/mpp_parser_worker.py:71` daria `ModuleNotFoundError`.
3. `_achar_java_home()` procura em `/nix/store`, caminho **Replit-only**.

**E isso é consciente.** `java_disponivel()` → `False` → 422 com mensagem
acionável (*"No MS Project: Arquivo → Salvar como → XML"*), e o smoke no
entrypoint loga o modo sem bloquear o boot. O caminho `.xml` (MSPDI) usa
`defusedxml`, stdlib pura, e **funciona**.

**Se `.mpp` virar requisito**, faltam: `default-jre-headless` no Dockerfile,
`mpxj`+`jpype1` no `pyproject.toml`, e revisão de `_achar_java_home()`.

---

# D6 — Frontend

## 21. Stack real

**Jinja2 + Bootstrap 5 via CDN + jQuery + JS inline. Zero build step, zero
`package.json`, zero `node_modules`.** `.replit:35` confirma:
`stack = "FLASK_VANILLA_JS"`.

| Biblioteca | Versões simultâneas | Origem |
|---|---|---|
| Bootstrap | **5.3.0**, 5.1.3, 5.3.2 | CDN |
| Font Awesome | 6.0.0, 6.4.0, 6.5.1 | CDN |
| jQuery | 3.6.0, 3.7.1 | CDN |
| **Chart.js** | **vendorizada + 4.4.0 + 3.9.1** (a API mudou entre 3 e 4) | mista |
| Feather, SweetAlert2, Tom Select, Mermaid | **versões flutuantes** (`@11`, `@2`, `@10`, sem versão) | CDN |

🔴 **Zero SRI** — `integrity=` não aparece em nenhum template. Todo o front
depende de 5 CDNs sem verificação de integridade. E `base.html:15` depende de
um CSS hospedado pela **Replit**.

**Bug:** `base_completo.html:52` declara `font-family: 'Inter'` mas **não
carrega webfont nenhuma**. As 245 páginas rodam em `-apple-system`.

### Duplicação medida

**295 templates, 118.361 linhas.** E:

- **42,5% do código de template é JS/CSS inline** (24,6% JS + 17,9% CSS).
  Contraste: `static/js/*.js` soma **2.483 linhas** — ou seja, **~92% do
  JavaScript do produto vive dentro de templates**, não em arquivos
  versionáveis, testáveis ou cacheáveis.
- **636 funções JS inline distintas; 20 copiadas em 3+ templates.**
  `confirmarExclusao` 9×, `limparFiltros` 6×, **`fmtBRL` 5×** — e os testes
  Playwright de "formato BR" existem justamente porque essa função **diverge
  entre cópias**.
- **52 templates órfãos (17,6%), ~19.000 linhas mortas.**
- `templates/portal/_partials/` é um **fork abandonado**: 3 arquivos
  byte-idênticos aos vivos, e `_styles.html` ficou **66 linhas para trás**.

### Templates base

| Base | Consumidores | Papel |
|---|---:|---|
| **`base_completo.html`** | **245** | **canônico** — único com shell mobile |
| `base.html` | 2 vivos | legado dark-theme; **carrega jQuery duas vezes** |
| `portal/_base.html` | 3 | design system próprio do portal — separação legítima |
| `base_iframe.html` | dinâmico | cronograma em iframe |
| `base_light.html` | **0** | **morto** |

## 22. Responsividade real

### 🔴 Mobile é 100% não-testado

**O menor viewport de qualquer um dos 200 testes de browser é 1280×800.**
`grep -rln "mobile" tests/*.py` → nenhum resultado. **Nenhuma linha do CSS
mobile é exercitada por teste.**

### 🔴 PWA quebrada

`manifest.json:6` → `"start_url": "/funcionario-mobile"` — **rota que não
existe**. Instalar o app na tela inicial abre 404. `sw.js` pede cache de dois
arquivos inexistentes (e `cache.addAll` é atômico, então o install falharia
sempre) — irrelevante, porque **o service worker nunca é registrado**.
**Não há operação offline.**

### Veredicto por fluxo

| Fluxo | Veredicto | Evidência |
|---|---|---|
| **Portal do cliente** | ✅ **USÁVEL** | `_portal_styles.html:594-617` — media query com 15 regras; botões de aprovação viram full-width no celular |
| **Aprovação de compras (portal)** | ✅ **USÁVEL** | idem `:608-611` |
| **RDO — preenchimento** | 🟠 **PRECISA AJUSTE** | tem `capture="camera"` e grid que empilha; **mas** os headers de Equipamentos/Ocorrências são `d-none d-md-flex` e as linhas geradas por JS têm **4 `<select>` sem label, sem `aria-label` e sem placeholder** — no celular viram dropdowns anônimos |
| **Compras — detalhe** | 🟠 **PRECISA AJUSTE** | tabela de 8 colunas **sem `table-responsive`** (`compras/detalhe.html:151`) |
| **Cronograma (iframe `?cliente=1`)** | 🔴 **INVIÁVEL** | `base_iframe.html` não carrega `sige-mobile.css`, onde as classes de degradação são definidas — o Gantt **nunca é escondido no celular** |
| **PWA / offline** | 🔴 **INVIÁVEL** | acima |

> **Nota de arquitetura:** **não existe aprovação de compra na interface
> interna.** A ação vive só no portal público por token. Um gestor que
> precise aprovar pelo celular hoje **não tem tela**.

🟡 `base*.html:12` usa `user-scalable=no` — **zoom bloqueado nas 245 páginas
internas**, violação de WCAG 2.1 SC 1.4.4.

---

# D7 — Qualidade e processo

## 23. Distribuição dos testes

**867 testes coletados** (667 no gate, 200 browser).

| Domínio | Testes | % |
|---|---:|---:|
| **Cronograma / MPP / versionamento** | **~266** | **30,7%** |
| Browser smoke transversal | 168 | 19,4% |
| Importação / classificação | 93 | 10,7% |
| Financeiro / custos de obra | 88 | 10,1% |
| Orçamento / proposta / BDI | ~85 | 9,8% |
| RDO | ~45 | 5,2% |
| **Compras** | **2** | **0,2%** |

**Metade da suíte é cronograma + smoke genérico.**

### Módulos críticos com cobertura fraca ou zero

| Área | Testes de lógica | Veredicto |
|---|---:|---|
| `relatorios_financeiros_avancados.py` (19 rotas) | **0** | 🔴 **ZERO** |
| Contas a pagar / a receber (escrita) | **0** | 🔴 **ZERO** |
| **CRM** (`crm_views.py`, 22 rotas) | **0** | 🔴 ZERO lógica (só 6 smoke "a página abriu") |
| **Folha** (18 rotas + service) | **0** | 🔴 ZERO — ver armadilha |
| Ponto (33 rotas), Frota (13), Almoxarifado | 0 | 🔴 ZERO |
| **Portal do cliente** | 4 (só nos 2 GETs) | 🔴 **8/10 rotas — todas as de escrita por token público — sem teste** |
| `financeiro_views.py` (23 rotas) | 0 diretos | 🔴 ~19/23 sem cobertura |

### 🪤 Armadilha: 34 testes de folha que não testam a folha

`tests/test_regras_salario_completo.py` (4º maior arquivo da suíte) importa
**apenas `pytest` e `decimal`**. Ele **reimplementa** as constantes e valida a
aritmética contra um `.md`. **Não toca `folha_pagamento_views.py` nem
`services/folha_service.py`.** É um teste de documentação que infla "Folha"
de 0 para 34 em qualquer contagem por domínio.

### 🔴 Skips que produzem verde falso

**0 `xfail`, 44 skip/skipif.** Os perigosos são os de **precondição de dados**:
`test_fluxo_obra.py:43,68,96` (os 3 testes), `test_fluxo_entradas_realizadas.py`
(o único), `test_processar_usa_cadastro.py` (os 6),
`test_regressao_classificacao.py` (o único). **Num banco vazio eles passam
como "skipped" e o gate fica verde cobrindo menos.** Mais 18 pontos de skip no
browser que zeram almoxarifado, folha e conta a receber se o seed demo faltar.

## 24. O que o `--gate` cobre e não cobre

```bash
--gate)  TARGET_FILE="tests/"; MARKER_ARGS=(-m "not browser"); shift ;;
```

Uma única invocação de pytest. **Sem fail-fast, sem timeout por teste**
(`pytest-timeout` não instalado), sem `--strict-markers` (marker com typo passa
silencioso).

**Não cobre:**

- **200 testes / 16 arquivos / ~23% da suíte**, excluídos por `-m "not
  browser"`. **O gate não executa uma única linha de JavaScript, não renderiza
  um template no browser, não clica em nada** — e é exatamente aí que vivem as
  regressões que o repo mais documenta (formato BR, `{% block scripts %}` não
  renderizado, cascata de subgrupos no RDO).
- **Falsa cobertura interna:** os 3 testes `java` estão *incluídos* no gate mas
  **pulam sempre** neste ambiente.

**Acoplamento gratuito:** `run_tests.sh:63-90` sobe gunicorn e faz polling de
20s **antes** da bifurcação de flags — mas **nenhum teste do gate acessa
`localhost:5000`**. Se o servidor não subir, sai com `exit 1` sem rodar o
pytest.

### Jornadas do Playwright

16 arquivos, 200 testes. Os principais: suíte canônica de 7 blocos (120),
varredura de 48 páginas-âncora (48), jornada comercial completa em 19 etapas
(19), e 13 arquivos de 1 teste cada (RDO unificado, dois modos, subgrupo
aninhado, importação de cronograma, BDI, formato BR…).

**Anti-padrão nos 13:** cada um tem um `main()` standalone de 200–780 linhas
que semeia dados, roda o browser e chama `sys.exit()`. O "teste pytest" é só
um wrapper. **As 14 asserções P1–P14 do RDO unificado viram um único "failed
(exit code=1)"** — sem granularidade, sem `-k P11`. São scripts disfarçados de
teste. E **não há banco de teste isolado**: os wrappers gravam no mesmo
`DATABASE_URL`, sem rollback.

## 25. CI

**Não existe. Zero.** Sem `.github/workflows`, sem `.gitlab-ci.yml`, sem
`Jenkinsfile`, sem `.pre-commit-config.yaml`, sem hooks instalados em
`.git/hooks/`. `gh api .../actions/workflows` → `{"total_count":0}`.

**O remoto É GitHub, com Actions disponível e nunca usado.**

### O gate está mais perto de automatizável do que parece

| Dependência | Real? |
|---|---|
| PostgreSQL | ✅ genuína → `services: postgres:16` no Actions, custo ~0 |
| Servidor em :5000 | ❌ **falsa** — nenhum teste do gate o acessa. Chamar `pytest` direto |
| 38 min | 🟡 parcial — os 200 browser já estão fora |

**Plano, em ordem de custo/benefício:**
1. `.github/workflows/gate.yml` (~30 linhas) com Postgres, seed e
   `pytest tests/ -m "not browser and not java"`.
2. Instalar `pytest-timeout` e adicionar `--strict-markers` — **pré-requisitos**,
   não opcionais (hoje um teste travado pendura o job indefinidamente).
3. 🔴 **O bloqueio real:** banco compartilhado sem isolamento. Não dá para
   paralelizar, e os ~30 testes que `skipif` por ausência de dados **pulariam
   todos num banco novo, produzindo verde falso**. Rodar os seeds no setup e
   converter os `skipif` de dados em falha.
4. CI noturno para o browser.
5. Granularizar os 13 wrappers `main()`+`sys.exit()`.

**Bônus barato:** `ruff` já está configurado no `pyproject.toml`. Rodar
`ruff check` custa segundos e pegaria imports quebrados como o
`handlers.folha_handlers`.

## 26. ADRs e documentos

**O núcleo arquitetural está saudável** — os 3 ADRs, `CONTEXT.md` e `RDO.md`
foram verificados contra o código e batem. O apodrecimento está na camada de
UI/estilo e nos manuais.

| Documento | Veredicto |
|---|---|
| `docs/adr/0001` (BDI por dentro), `0002` (classificação por cadastro), `0003` (variação relativa) | ✅ **ATUALIZADOS** — implementação conferida |
| `CONTEXT.md`, `RDO.md`, `DEVOLUTIVA.md`, `ESTADO_ATUALIZACAO_BAIA.md` | ✅ ATUALIZADOS |
| `PRODUCT.md`, `DESIGN.md` | 🟡 atualizados, com contradição cruzada |
| `replit.md` | 🟠 **DESATUALIZADO** — diz "v9.0", ignora M01–M10, e prescreve gradientes |
| `design_guidelines.md` | 🔴 **PERIGOSO** — prescreve **Tailwind** num projeto sem Tailwind |
| **`STYLE.md`** | 🔴 **MORTO — É DE OUTRO PRODUTO** |
| `MANUAL_USUARIO_SIGE.md`, `manual/25_financeiro.md` | 🔴 **PERIGOSOS** — contradizem o ADR 0003 |
| ~12 documentos de baia/handoff/auditoria | ⚰️ MORTOS |

### 🔴 Os documentos perigosos

1. **`STYLE.md` é o brief editorial de outro produto.** `:3` — *"Editorial
   brief for **impeccable.design**"*, em inglês. Referencia
   `scripts/build.js`, que não existe. E **proíbe travessão (`—`)**, que toda
   a documentação viva do SIGE usa. Um agente que o leia como norma vai
   reescrever documentação correta. **Deletar.**
2. **`design_guidelines.md` prescreve Tailwind** (`max-w-7xl`, `grid-cols-3`)
   num projeto Bootstrap sem `package.json`.
3. **Três normas de UI mutuamente incompatíveis:** `replit.md:54` pede
   "gradientes"; `PRODUCT.md:43` lista "cards com gradiente" como
   anti-referência; `DESIGN.md:144` diz "não use gradientes". **`replit.md` é
   o mais antigo e é tipicamente o primeiro arquivo que um agente lê.**
4. **`manual/25_financeiro.md:68` — manual SERVIDO AO USUÁRIO** (em `/manual`)
   diz que o fluxo de caixa "combina previsões com realizado", exatamente o
   que o ADR 0003 proíbe e o código não faz.

**Saneamento sugerido, por risco:** deletar `STYLE.md` → atualizar
`manual/25_financeiro.md` → remover as "User preferences" de `replit.md` →
reescrever `design_guidelines.md` em Bootstrap → arquivar ~12 documentos
mortos.

---

# D8 — Dependências e riscos

## 27. Pinagem

**As versões NÃO estão pinadas, e produção não usa o lockfile.**

`pyproject.toml` tem **47 dependências, todas `>=`, zero `==`, zero teto**.
E `Dockerfile:31-32` faz `pip install .` — **`uv.lock` nunca é copiado para a
imagem**. Cada rebuild **re-resolve do PyPI**.

Consequências: dois builds do **mesmo commit** produzem dependências
diferentes; um rebuild pode puxar Flask 4.x silenciosamente; e o rollback do
EasyPanel (rebuild do commit anterior) **não reproduz a imagem anterior**.

O `uv.lock` já está **dessincronizado**: `jsonschema` foi adicionado ao
`pyproject` e **não tem entrada no lock**.

### Riscos concretos (sem inventar CVE)

- **`psycopg2-binary` 2.9.10 em produção.** Os mantenedores documentam que a
  variante `-binary` **não é para produção**: embute libpq/libssl
  estaticamente, **não recebe atualizações de segurança do OpenSSL do
  sistema**. psycopg2 está em manutenção; psycopg 3 é o sucessor. **É o item
  de dependência com risco mais concreto, e não depende de nenhum CVE
  específico para ser verdadeiro.**
- **`opencv-python` E `opencv-python-headless` ambos declarados** — dois
  provedores de `cv2`, o vencedor depende da ordem de instalação.
- **`pytest`, `ruff` e `playwright` vão para a imagem de produção** (não há
  `[dependency-groups]`). Playwright baixa binários de browser.
- **`deepface` 0.0.97 + TensorFlow 2.20** — pré-1.0, mantenedor único, ~600 MB
  e superfície de ataque enorme num sistema de RH/folha.

> A atualidade em nível de patch de `urllib3`/`requests`/`cryptography`/
> `jinja2`/`werkzeug`/`pillow` **precisa de verificação externa contra base de
> CVE** — não afirmo advisories específicos. **O ponto que importa mais que
> qualquer CVE é que produção não usa o lock**, então nem se sabe qual versão
> está lá.

## 28. O subprocess Java do MPXJ

**O desenho acerta:** JVM em subprocess separado, nunca dentro do gunicorn;
falhas viram `MppParserError` tipada; o `.xml` usa `defusedxml`. Melhor que a
média.

**Mas não é suficiente para produção:**

1. 🔴 **O timeout do parser colide exatamente com o do gunicorn — e é aí que
   nasce a JVM órfã.** `parse_cronograma(timeout_s=120)` e
   `gunicorn --timeout 120` são **o mesmo valor**, numa chamada síncrona
   dentro do request. Na prática o gunicorn ganha: mata o worker **antes** do
   `TimeoutExpired` ser tratado, o `proc.kill()` nunca roda, e **o filho é
   reparentado para o PID 1 e vira órfão**, segurando a heap até o restart. É
   o caminho **mais provável**, não o excepcional. E não há
   `start_new_session=True`, então nada é morto por grupo.
2. 🔴 **Não há limite de memória. Nenhum.** `jpype.startJVM()` sem `-Xmx` — a
   heap default é ~1/4 da RAM do container. Sem limite de concorrência: N
   uploads = N JVMs. **Com apenas 2 workers, um único `.mpp` de 120s consome
   50% da capacidade de atendimento.**
3. 🔴 **Arquivo malicioso é parseado como root.** O container não tem `USER`.
   O `capture_output=True` lê **stdout inteiro para a RAM sem limite** (só o
   stderr tem teto) — pico de 2× na memória do worker web.
4. **Zero observabilidade do subprocess.** Se JVMs órfãs se acumularem, o
   sintoma será "o sistema ficou lento", sem trilha.

**Mitigação que já existe:** `java_disponivel()` → `False` significa que
**hoje esse código nunca executa em produção**. O risco se materializa no dia
em que alguém adicionar o JRE ao Dockerfile.

**Mínimo antes de habilitar `.mpp`:** `timeout_s` bem abaixo do gunicorn
(45s vs 120s); `start_new_session=True` + `os.killpg`;
`jpype.startJVM('-Xmx512m')`; teto de tamanho específico; `USER` não-root; e
— o mais importante — **tirar o parse do ciclo de request**.

## 29. Top 5 dívidas invisíveis na especificação do produto

### 1. Segredo de produção adivinhável no git, com a correção perdida numa branch órfã
§17. Forjar sessão de qualquer usuário de qualquer tenant não exige
vulnerabilidade adicional. E a correção existe em `fix/bloco2-segredos`, **402
commits atrás**. **A dívida não é só o bug — é que o processo perde correções
de segurança já feitas.** Nenhum analista de produto veria isso; quem roda
`git branch -a` vê.

### 2. Você não saberia que foi invadido
§19. Sem access log + sem `before_request` + sem auditoria + `ProxyFix` sem
`x_for` + `logger.debug` suprimido = **um acesso anônimo bem-sucedido não
deixa rastro em lugar nenhum**. Combine com o traceback completo devolvido ao
navegador e você tem reconhecimento fácil para o atacante e cegueira total
para o operador. **Isso é pior que a rota sem `@login_required` em si — a
rota é um bug pontual, a cegueira é sistêmica.**

### 3. Migrações que falham em silêncio e um "backup" que é um `echo`
`app.py:601-609` roda `executar_migracoes()` no import e **engole qualquer
exceção**, com `"Aplicação continuará mesmo com erro nas migrações"`. Isso
roda em **todo boot de worker**. Some ao `echo` de backup que não faz backup
(§18): uma migração destrutiva mal formulada, num arquivo de **14.168
linhas**, roda sem backup e, se falhar no meio, o app sobe dizendo que está
saudável.

### 4. Quatro entrypoints, dois byte-a-byte idênticos, e o óbvio é o que não roda
§16. `docker-entrypoint.sh` e `-v10.sh` têm **md5 idêntico** e só fazem
`db.create_all()`. O `Dockerfile` sobrescreve o de nome óbvio. Dos 5
`deploy_*.sh`, **4 referenciam arquivos inexistentes**. Um operador sob
pressão às 2h da manhã tem 9 caminhos plausíveis e 1 correto — mais o
auto-seed de demo ligado por padrão.

### 5. Produção não usa o lockfile — a imagem não é reproduzível
§27. 47 deps em `>=` sem teto, `uv.lock` fora da imagem, resolução nova a cada
rebuild. O mesmo commit produz imagens diferentes em dias diferentes, e o
rollback não reproduz a imagem anterior.

> **Menção honrosa fora do top 5:** `models.py` com 7.610 linhas e
> `migrations.py` com 14.168. Doloroso de manter e torna review de mudança de
> schema inviável — mas, diferente dos cinco acima, **não causa incidente
> sozinho**. É multiplicador de risco dos itens 3 e 5, não causa raiz.

---

# Resumo das LACUNAS

| Pergunta | Não determinado | O que seria preciso |
|---|---|---|
| 1 | `admin_id` da Veks em produção | banco de produção |
| 4 | *Quando* a multitenancy entrou | histórico git está truncado em 2026-05-27 |
| 11 | Qual chamada gera o seq scan de `tarefa_cronograma` | `EXPLAIN ANALYZE` por query |
| 12-15 | Volumetria e qualidade **reais** | o banco medido é de dev, 100% poluído por testes |
| 14 | Volume real da migração da Fase 4 | banco de produção |
| 16, 18, 19, 20 | Provedor, snapshot de volume, retenção de logs, TLS | painel do EasyPanel |
| 22 | Responsividade **renderizada** | os veredictos vêm de leitura de CSS/HTML; nenhum teste do repo roda abaixo de 1280px |
| 23 | Taxa de skip em execução real | medido quantos *podem* pular (44), não quantos pulam |
| 27 | Versões **de fato** instaladas em produção | `pip freeze` no container |
| 17 | Se os valores do painel diferem dos commitados | ler as env vars no EasyPanel |

**Cobertura da varredura de segredos:** todos os arquivos rastreados
(`git ls-files`) + buscas no histórico via `git log --all -S`. **Não** cobriu
blobs não alcançáveis nem binários. Para cobertura total:
`gitleaks detect --log-opts="--all"` ou `trufflehog git file://.`
