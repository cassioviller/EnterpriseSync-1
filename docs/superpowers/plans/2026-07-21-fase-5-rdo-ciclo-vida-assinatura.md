# Fase 5 — RDO com ciclo de vida e assinatura

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao RDO um ciclo de vida com guardas de transição, uma assinatura vinculada à identidade real da pessoa (`Usuario.funcionario_id`, Fase 1) e imutabilidade após a assinatura — hoje o RDO nasce `'Finalizado'` por decreto (`models.py:860`), é reescrito por oito caminhos de escrita diferentes sem nenhuma guarda, e não existe registro nenhum de quem respondeu por ele.

**Architecture:** Coluna **nova** `RDO.estado` (5 estados) ao lado do `RDO.status` legado, que fica intocado — nove consumidores em produção filtram por `status == 'Finalizado'` e nenhum deles pode quebrar. A máquina de estados mora num serviço único (`services/rdo_ciclo_vida.py`) e a imutabilidade é imposta por um listener `before_flush` do SQLAlchemy, não por edição das oito rotas de escrita: o chokepoint pega inclusive os caminhos que ninguém lembrou de migrar. A assinatura é um registro de autoria (`RDOAssinatura`) com hash SHA-256 de um payload canônico, carimbo de tempo do servidor, IP e user-agent; a correção de um RDO assinado não é edição, é um **RDO retificador** encadeado por `rdo_retificado_id`.

**Tech Stack:** Flask 3 + Flask-Login, SQLAlchemy 2 (`models.py`), sistema de migrações próprio numerado (`migrations.py`, faixa **260–269** reservada para esta fase), ReportLab (`services/rdo_pdf_service.py`), pytest + PostgreSQL real (`bash run_tests.sh --gate`).

---

## Fronteira de escopo (leia antes de qualquer coisa)

Existe um plano **irmão** sendo escrito em paralelo:
`docs/superpowers/plans/2026-07-21-cronograma-editavel-rdo-percentual.md`.

| | Plano irmão (cronograma editável / RDO percentual) | **Este plano (Fase 5)** |
|---|---|---|
| Assunto | **MODO** de apontamento: percentual × quantidade | **CICLO DE VIDA** e **ASSINATURA** do RDO |
| Código-alvo | `services/cronograma_apontamento_service.py::modo_da_tarefa` (linha 73), `registrar_apontamento` (194), `TarefaCronograma`, `services/cronograma_proposta.py::materializar_cronograma` | `models.py::RDO` (834), `services/rdo_ciclo_vida.py` (novo), `RDOAssinatura` (novo), `views/rdo.py` rotas de estado |
| Migrations | fora da faixa 260–269 | **260–264** |

**Regras de não-colisão, explícitas:**

1. Esta fase **não altera** `modo_da_tarefa`, `registrar_apontamento`, `recomputar_cadeia` nem qualquer coluna de `rdo_apontamento_cronograma`. O único ponto de contato é a guarda de imutabilidade: gravar apontamento num RDO `assinado` passa a ser recusado.
2. **Contrato oferecido ao plano irmão:** `services/rdo_ciclo_vida.garantir_editavel(rdo)` levanta `RDOImutavel` quando o RDO não aceita mais escrita. O plano irmão deve chamá-lo antes de gravar apontamento — mas mesmo que não chame, o listener `before_flush` da Task 4 barra a escrita. Nenhuma coordenação de merge é necessária.
3. Esta fase **não** cria coluna `TarefaCronograma.modo_apontamento` nem toca em `tipo_apontamento`. Se o plano irmão criar, os dois convivem: o hash canônico da Task 6 lê `tipo_apontamento` por `getattr` com default `None`.

---

## Contexto verificado no código (conferido por mim em 2026-07-21, commit `fb4147b`)

Nada aqui é suposição. Cada linha foi aberta.

| Fato | Evidência |
|---|---|
| `RDO.status` é `String(20)` com default `'Finalizado'` e o comentário *"Task #12: RDO sempre Finalizado"* | `models.py:860` |
| Não existe ciclo de vida: **cinco** caminhos de escrita gravam `status='Finalizado'` na mão | `views/rdo.py:698` (`criar_rdo`), `:1539` (`finalizar_rdo`), `:1629` (`duplicar_rdo`), `:1754` (`atualizar_rdo`), `:2742` (`rdo_salvar_unificado`), `:4574` (`salvar_rdo_flexivel`), `rdo_editar_sistema.py:221`, `crud_rdo_completo.py:331` e `:565` |
| `'Finalizado'` é lido como magic string por **9 consumidores** — mudar o significado da coluna quebraria todos | `cronograma_views.py:2315,2345`; `portal_obras_views.py:187`; `services/medicao_service.py:243`; `services/rdo_custos.py:330`; `services/metricas_produtividade.py:186,972,1302,1320` |
| Já houve um `'Rascunho'` legado, **executado à força** para `'Finalizado'` pela migration 154 | `migrations.py:11469-11670`; script gêmeo `scripts/migrar_rdos_rascunho_legados.py` |
| **`finalizar_rdo` também está morta.** O guard da linha 1533 é `if rdo.status == 'Finalizado': return` — e `models.py:860` faz TODO RDO nascer com esse valor. A rota sempre retorna "RDO já está finalizado" sem fazer nada. Segunda rota morta do módulo, ao lado do `duplicar_rdo` | `views/rdo.py:1533-1536` vs. `models.py:860` |
| `finalizar_rdo` ainda é `@admin_required`, e `admin_required` recusa `TipoUsuario.FUNCIONARIO` — o apontador não consegue submeter o próprio RDO | `views/rdo.py:1521`; `auth.py:29` |
| Não existe assinatura nenhuma. O PDF tem **linha em branco para caneta** | `services/rdo_pdf_service.py:798-865` (`_signature_block`) |
| Não existe trilha de auditoria de RDO — o próprio serviço de apontamento admite: *"não há tabela de eventos de RDO"* | `services/cronograma_apontamento_service.py:330-331` |
| Existe molde de trilha pronto para copiar | `models.py:5178` (`CronogramaImportacaoEvento`: `evento`, `detalhes` JSON, `usuario_id`, `criado_em`) + `services/cronograma_observabilidade.py:34` (`log_transicao`) |
| Existe molde de listener em `RDO` | `models.py:7018` (`_rdo_after_insert_autoclone_operacional`) e `models.py:1422` (`RDOServicoSubatividade`) |
| `visualizar_rdo` **não tem decorator de autenticação**, e o docstring diz isso na cara | `views/rdo.py:926-928` — `"""Visualizar RDO específico - SEM VERIFICAÇÃO DE PERMISSÃO"""` |
| Não há `before_request` global — a rota é mesmo anônima | comentário conferido em `views/rdo.py:2157` |
| Não existe handler de RDO em `handlers/` — só `financeiro_handlers.py` e `propostas_handlers.py`. Os efeitos colaterais do RDO moram em `event_manager.py` | `ls handlers/`; `event_manager.py:578` (`lancar_custos_rdo`), `:1357` (`recalcular_medicao_apos_rdo`) |
| `ProxyFix(x_for=1)` está ligado — `request.remote_addr` é o IP real do cliente, não o do proxy | `app.py:94` |
| Maior migration registrada é a **213** | `migrations.py:4014` |

### O bug 6d — o diagnóstico do `ESTADO-ATUAL.md` está DESATUALIZADO

`ESTADO-ATUAL.md:102` diz: *"`duplicar_rdo` emite webhook sem lançar custos (bug 6d)"*. Reconferi linha a linha. **O que está escrito é o bug que existiria se a rota funcionasse — e ela não funciona.**

1. `views/rdo.py:1624-1627` lê `rdo_original.tempo_manha`, `.tempo_tarde`, `.tempo_noite` e `.observacoes_meteorologicas`. **Nenhum desses atributos existe no modelo `RDO`.** Verificado executando:

   ```
   RDO cols: ['admin_id','clima_geral','comentario_geral','condicoes_trabalho','created_at',
              'criado_por_id','data_relatorio','id','local','numero_rdo','obra_id',
              'observacoes_climaticas','precipitacao','status','temperatura_media',
              'umidade_relativa','updated_at','vento_velocidade']
   tempo_manha in RDO mapper: False
   READ RAISES: AttributeError 'RDO' object has no attribute 'tempo_manha'
   ```

2. Portanto a rota **sempre** cai no `except Exception` de `views/rdo.py:1715`, faz `rollback` e mostra `'Erro ao duplicar RDO.'`. O `emit_obra_rdo_publicado` da linha 1708 **nunca é alcançado** — está 84 linhas depois do ponto onde a função morre.
3. `mao_original.observacoes` (`views/rdo.py:1682`) é um segundo atributo fantasma: `RDOMaoObra` não tem `observacoes` (`models.py:917-966`).
4. A rota **não tem link em nenhum template nem em nenhum JS** (`grep -rn "/duplicar" templates/ *.js` só devolve `orcamentos.duplicar`). Só é alcançável por POST direto em `/rdo/<id>/duplicar`.

**Conclusão honesta:** hoje o bug 6d é *latente*. Ele vira o bug descrito no `ESTADO-ATUAL.md` no instante em que alguém consertar os atributos fantasma sem consertar os eventos — porque `duplicar_rdo` é a **única** rota de escrita de RDO que chama `emit_obra_rdo_publicado` (linha 1708) **sem** o `EventManager.emit('rdo_finalizado', …)` que suas irmãs chamam (`:1570`, `:1819`, `:4769`). O `rdo_finalizado` é quem dispara `lancar_custos_rdo` (`event_manager.py:578`) e `recalcular_medicao_apos_rdo` (`event_manager.py:1357`). A Task 10 conserta os dois de uma vez, e o consenso do plano é que um RDO duplicado **não nasce publicado**: nasce `rascunho` e não emite nada.

### O achado de `rdo_foto` — medido por mim no banco de desenvolvimento

O `ESTADO-ATUAL.md:116` diz "14 GB de 14 GB em produção". Não tenho acesso a produção, mas medi o **banco de desenvolvimento** e o quadro é o mesmo, com um detalhe que muda a estratégia:

```
pg_database_size(current_database())     = 16 GB
pg_total_relation_size('rdo_foto')       = 16 GB
pg_relation_size('rdo_foto')  (heap)     = 11 MB
pg_total_relation_size(reltoastrelid)    = 16 GB     ← as três cópias base64
pg_indexes_size('rdo_foto')              = 1448 kB

SELECT count(*) …                        = 28.870 fotos em 5.532 RDOs
  com arquivo_otimizado preenchido       = 28.860
  SEM caminho em disco (base64-only)     = 10
  com imagem_otimizada_base64            = 28.870

Linha típica (id 29498):
  imagem_original_base64  = 313.615 caracteres
  imagem_otimizada_base64 = 122.983 caracteres
  thumbnail_base64        =  16.203 caracteres   → ~442 KB de TEXT por foto
```

E no sistema de arquivos: `du -sh static/uploads` = **13 GB**, com `UPLOADS_PATH` **não definido**.

Três conclusões que definem as Tasks 13-15:

1. **A base64 já é cópia redundante.** 28.860 das 28.870 fotos têm o arquivo em disco. O banco carrega 16 GB de duplicata.
2. **Mas o disco é efêmero.** Com `UPLOADS_PATH` vazio, `services/rdo_foto_service.py:21-53` escreve em `static/uploads/rdo` dentro do container. Foi *exatamente por isso* que a base64 nasceu (`models.py:1095-1096`: *"fotos NUNCA são perdidas em deploy/restart"*). Apagar a base64 sem o volume montado **destrói o dado** no primeiro deploy. Daí o pré-requisito de infra ser bloqueante e humano.
3. **Existe um bug que já quebra o volume hoje.** `services/rdo_foto_service.py:377-383` devolve caminho relativo `uploads/rdo/…` e `crud_rdo_completo.py:804` monta `os.path.join(os.getcwd(), 'static', caminho)`. Se alguém montar o volume e definir `UPLOADS_PATH`, o arquivo passa a ser gravado em `$UPLOADS_PATH/rdo/…` e continuará sendo **procurado** em `static/uploads/rdo/…` → 404. Consertar isso (Task 13) é pré-requisito técnico da migração.

Bônus medido: `RDO.fotos` é `lazy='selectin'` (`models.py:1104`). Toda consulta de RDO puxa as três colunas base64 de todas as fotos, inclusive na listagem paginada de `crud_rdo_completo.py:80`. A Task 14 troca por `lazy='select'` + `deferred`.

### Decisões de projeto desta fase

1. **Coluna nova `estado`; `status` legado intocado.** É o mesmo desenho que a `DEVOLUTIVA.md:98` propõe para `Obra.status`. Nove consumidores filtram `status == 'Finalizado'`; qualquer reinterpretação da coluna existente seria uma quebra silenciosa em produção. `status` continua `'Finalizado'` sempre, e um dia morre.
2. **`estado` é `String(20)` com constantes Python, não `db.Enum`.** O sistema de migrações escreve DDL cru; criar um `TYPE` nativo do Postgres exigiria bloco `DO $$`, e a coluna precisa conviver com backfill e rollback triviais. `RDO.status` já é `String`. Consistência vale mais que tipagem no banco aqui.
3. **Backfill honesto: tudo que existe vira `preenchido`, nunca `assinado`.** 5.532 RDOs históricos nunca foram assinados por ninguém. Marcá-los como assinados seria forjar autoria — o oposto do que esta fase entrega.
4. **Sem feature-flag por tenant.** A Fase 1 precisou de flag porque ligar o escopo *tira* acesso. Aqui a fase é aditiva por construção: depois do backfill todo RDO está em `preenchido`, que é mutável, e a imutabilidade só passa a existir quando alguém clicar em "Assinar". O rollback é `UPDATE rdo SET estado='preenchido'`.
5. **Imutabilidade por listener `before_flush`, não por edição das oito rotas.** Existem oito lugares que gravam `status='Finalizado'`; migrar todos à mão é como garantir que nenhum foi esquecido — impossível de provar. O listener é um ponto só, e o teste `test_qualquer_caminho_de_escrita_e_barrado` o prova contra o caminho mais obscuro (`salvar_rdo_flexivel`).
6. **O hash cobre o conteúdo declarado, não os bytes das fotos.** Hash de foto amarraria a assinatura ao formato de armazenamento, e a Task 15 muda esse formato. O payload canônico inclui `(foto.id, nome_original, descricao)` — identidade e legenda, que é o que a pessoa declarou.
7. **RDO retificador, não versão.** A `DEVOLUTIVA.md:104` pede `rdo_retificado_id`. O RDO é um documento de data — "versionar" um RDO de 22/06 é criar outro RDO de 22/06 que diz o que o primeiro deveria ter dito, com o primeiro preservado e marcado `retificado`. É a prática de campo, e cai bem no `UNIQUE` de `numero_rdo`.

### A decisão jurídica (não bloqueia o plano)

**`Recomendado:` registro de autoria + integridade, sem ICP-Brasil nesta fase.**

O que a Fase 5 entrega: identidade real do signatário (`Usuario.funcionario_id`, Fase 1), papel na obra no momento da assinatura (`UsuarioObra.papel`), hash SHA-256 de um payload canônico do RDO, carimbo de tempo do servidor, IP do cliente (real, via `ProxyFix` — `app.py:94`), user-agent, e um verificador que recomputa o hash e detecta adulteração.

Por que basta **para este documento**: a MP 2.200-2/2001, art. 10, §2º admite outros meios de comprovação de autoria e integridade de documentos eletrônicos desde que aceitos pelas partes. O RDO é documento **interno** — construtora ↔ sua própria equipe, com o cliente na posição de quem toma ciência, não de quem contrata por ele. Combinado com a imutabilidade e a trilha de transições, o conjunto é defensável.

Onde ICP-Brasil ou provedor (Clicksign / D4Sign) faz falta de verdade: no que é **oponível a terceiro** — a medição assinada pelo cliente, que é a Fase 9a da `DEVOLUTIVA.md:262`. Ali o custo se justifica; aqui não.

O plano segue **com essa recomendação adotada**. `RDOAssinatura.provedor` nasce com o valor `'interno'` justamente para que um provedor externo entre depois sem migração de schema.

### Arquivos que esta fase cria ou altera

| Arquivo | Responsabilidade |
|---|---|
| `services/rdo_ciclo_vida.py` | **novo** — estados, transições válidas, `transicionar()`, `garantir_editavel()`, listener de imutabilidade |
| `services/rdo_hash.py` | **novo** — payload canônico determinístico + SHA-256 + `verificar_integridade()` |
| `services/rdo_assinatura.py` | **novo** — `assinar()`, `aprovar()`, `criar_retificador()` |
| `scripts/migrar_fotos_rdo_para_disco.py` | **novo** — backfill reversível de `rdo_foto` (tarefa de risco) |
| `models.py` | `RDO.estado`, `RDO.rdo_retificado_id`, `RDOTransicaoEstado`, `RDOAssinatura`, `RDOFoto.armazenamento`, `lazy` das fotos |
| `migrations.py` | migrations **260–264** + registro em `migrations_to_run` |
| `views/rdo.py` | rotas `/assinar`, `/aprovar`, `/retificar`, `/reabrir`; conserto do `duplicar_rdo`; fecho de `visualizar_rdo` |
| `crud_rdo_completo.py` | conserto do caminho de `servir_foto` e do `INSERT` sem `nome_arquivo` |
| `services/rdo_foto_service.py` | para de gerar base64 nos uploads novos |
| `services/rdo_pdf_service.py` | `_signature_block` passa a imprimir a assinatura eletrônica quando existe |
| `templates/rdo/visualizar_rdo_moderno.html` | selo de estado + botões de transição + bloco de assinaturas |
| `tests/test_fase5_rdo_ciclo_vida.py` | **novo** — estados, guardas, imutabilidade |
| `tests/test_fase5_rdo_assinatura.py` | **novo** — assinatura, hash, retificador, autorização |
| `tests/test_fase5_rdo_fotos.py` | **novo** — armazenamento em disco, backfill reversível |
| `docs/fase-5-rollout.md` | **novo** — runbook, com o bloqueio de infra explícito |

---

## Task 1: Coluna `RDO.estado` e migration 260

**Files:**
- Modify: `models.py:860` (dentro de `class RDO`)
- Modify: `migrations.py` (função nova antes de `def executar_migracoes():` na linha 3773; registro após a linha 4014)
- Test: `tests/test_fase5_rdo_ciclo_vida.py`

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_fase5_rdo_ciclo_vida.py`:

```python
"""Fase 5 — ciclo de vida do RDO.

Até esta fase o RDO nascia 'Finalizado' por decreto (`models.py:860`,
comentário "Task #12: RDO sempre Finalizado") e era reescrito por oito
caminhos diferentes sem nenhuma guarda:

  views/rdo.py:698, 1539, 1629, 1754, 2742, 4574
  rdo_editar_sistema.py:221
  crud_rdo_completo.py:331, 565

A coluna `status` NÃO muda de significado — nove consumidores filtram
`status == 'Finalizado'` (cronograma_views.py:2315,2345;
portal_obras_views.py:187; services/medicao_service.py:243;
services/rdo_custos.py:330; services/metricas_produtividade.py:186,972,
1302,1320). O ciclo de vida entra numa coluna NOVA, `estado`.
"""
import os
import sys
import uuid
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os 54 blueprints antes de qualquer request
from app import app, db
from models import Cliente, Funcionario, Obra, RDO, TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase5-rdo'
    yield


def _sfx():
    return uuid.uuid4().hex[:8]


def _admin(nome='Admin F5'):
    suf = _sfx()
    u = Usuario(
        username=f'f5a_{suf}', email=f'f5a_{suf}@test.local',
        nome=f'{nome} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id, nome='Obra F5'):
    """Obra.cliente_id é NOT NULL — o Cliente vem junto, sempre."""
    suf = _sfx()
    cli = Cliente(nome=f'CLI-F5-{suf}', admin_id=admin_id)
    db.session.add(cli)
    db.session.flush()
    o = Obra(
        nome=f'{nome} {suf}', codigo=f'OF5{suf[:6].upper()}',
        data_inicio=date(2026, 1, 1), admin_id=admin_id,
        cliente_id=cli.id, valor_contrato=100000,
    )
    db.session.add(o)
    db.session.commit()
    return o


def _rdo(obra, admin_id, criado_por_id=None, data=None):
    suf = _sfx()
    r = RDO(
        numero_rdo=f'RDO-F5-{suf}',
        data_relatorio=data or date(2026, 6, 22),
        obra_id=obra.id, admin_id=admin_id,
        criado_por_id=criado_por_id,
        comentario_geral='Concretagem do radier.',
        clima_geral='Nublado',
    )
    db.session.add(r)
    db.session.commit()
    return r


def test_rdo_tem_coluna_estado():
    with app.app_context():
        assert hasattr(RDO, 'estado'), (
            'RDO.estado não existe — o RDO continua sem ciclo de vida')


def test_estado_default_e_rascunho():
    from services.rdo_ciclo_vida import RASCUNHO

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        assert rdo.estado == RASCUNHO, (
            f'RDO novo nasceu em {rdo.estado!r}, deveria nascer em rascunho')


def test_status_legado_continua_finalizado():
    """Nove consumidores filtram status=='Finalizado'. Não pode mudar."""
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        assert rdo.status == 'Finalizado', (
            'o default de RDO.status mudou — isso some com o RDO do portal '
            '(portal_obras_views.py:187) e das métricas')


def test_backfill_marcou_os_rdos_historicos_como_preenchido():
    """Migration 260: histórico vira 'preenchido', NUNCA 'assinado'."""
    from sqlalchemy import text
    from services.rdo_ciclo_vida import ASSINADO

    with app.app_context():
        forjados = db.session.execute(text(
            "SELECT count(*) FROM rdo WHERE estado = :e"), {'e': ASSINADO}
        ).scalar()
        assert forjados == 0, (
            f'{forjados} RDO(s) históricos foram marcados como assinados pelo '
            f'backfill — isso é forjar autoria')
        orfaos = db.session.execute(text(
            "SELECT count(*) FROM rdo WHERE estado IS NULL")).scalar()
        assert orfaos == 0, f'{orfaos} RDO(s) ficaram sem estado após o backfill'
```

- [ ] **Step 2: Rode o teste e confirme que falha**

```bash
python -m pytest tests/test_fase5_rdo_ciclo_vida.py -v
```

Esperado: FAIL. `test_rdo_tem_coluna_estado` falha com `AssertionError: RDO.estado não existe`; os demais falham com `ModuleNotFoundError: No module named 'services.rdo_ciclo_vida'` ou `ProgrammingError: column "estado" does not exist`.

- [ ] **Step 3: Adicione a coluna ao modelo**

Em `models.py`, dentro de `class RDO`, imediatamente após a linha 860 (`status = db.Column(...)`), insira:

```python
    # ── Fase 5 — ciclo de vida ────────────────────────────────────────
    # `status` acima NÃO muda: nove consumidores filtram por
    # `status == 'Finalizado'` (cronograma_views.py:2315,2345;
    # portal_obras_views.py:187; services/medicao_service.py:243;
    # services/rdo_custos.py:330; services/metricas_produtividade.py:186,
    # 972,1302,1320). Reinterpretar aquela coluna seria uma quebra
    # silenciosa em produção. O ciclo de vida mora AQUI.
    #
    # String(20) e não db.Enum: o sistema de migrações escreve DDL cru e
    # criar um TYPE nativo do Postgres exigiria bloco DO $$; além disso
    # `status` já é String — consistência dentro da mesma tabela.
    # Os valores válidos vivem em services/rdo_ciclo_vida.ESTADOS.
    estado = db.Column(db.String(20), nullable=False, default='rascunho',
                       server_default='rascunho', index=True)
```

- [ ] **Step 4: Escreva a migration 260**

Em `migrations.py`, imediatamente antes de `def executar_migracoes():` (linha 3773), insira:

```python
def migration_260_rdo_estado():
    """Fase 5 — coluna rdo.estado (ciclo de vida) + backfill honesto.

    Aditiva e idempotente. A coluna `status` NÃO é tocada: ela continua
    valendo 'Finalizado' para os nove consumidores que filtram por ela.

    Backfill deliberadamente conservador:
      status = 'Rascunho'  (legado da migration 154) → estado 'rascunho'
      qualquer outro valor                           → estado 'preenchido'

    NENHUM RDO histórico vira 'assinado'. Os 5.532 RDOs existentes nunca
    foram assinados por pessoa nenhuma — marcá-los como assinados seria
    forjar autoria, exatamente o oposto do que esta fase entrega.
    """
    logger.info("[Migration 260] Iniciando — rdo.estado")

    db.session.execute(text("""
        ALTER TABLE rdo
        ADD COLUMN IF NOT EXISTS estado VARCHAR(20)
    """))
    db.session.commit()

    atualizados_rascunho = db.session.execute(text("""
        UPDATE rdo SET estado = 'rascunho'
        WHERE estado IS NULL AND lower(coalesce(status, '')) = 'rascunho'
    """)).rowcount
    atualizados_preenchido = db.session.execute(text("""
        UPDATE rdo SET estado = 'preenchido'
        WHERE estado IS NULL
    """)).rowcount
    db.session.commit()
    logger.info("[Migration 260] backfill: %s rascunho, %s preenchido",
                atualizados_rascunho, atualizados_preenchido)

    db.session.execute(text("""
        ALTER TABLE rdo ALTER COLUMN estado SET DEFAULT 'rascunho'
    """))
    db.session.execute(text("""
        ALTER TABLE rdo ALTER COLUMN estado SET NOT NULL
    """))
    db.session.commit()

    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_rdo_estado ON rdo (estado)
    """))
    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_rdo_obra_estado ON rdo (obra_id, estado)
    """))
    db.session.commit()

    logger.info("[Migration 260] Concluída com sucesso")
```

- [ ] **Step 5: Registre a migration**

Em `migrations.py`, na lista `migrations_to_run`, logo após a linha 4014 (a entrada `213`), adicione:

```python
            (260, "Fase 5 — rdo.estado (ciclo de vida) + backfill histórico como 'preenchido'", migration_260_rdo_estado),
```

- [ ] **Step 6: Aplique a migration e rode os testes**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "Migration 260|ERRO|ERROR"
python -m pytest tests/test_fase5_rdo_ciclo_vida.py -v -k "coluna_estado or status_legado or backfill"
```

Esperado: log `[Migration 260] Concluída com sucesso` com a contagem do backfill, e os 3 testes selecionados PASSAM. `test_estado_default_e_rascunho` ainda falha (falta `services/rdo_ciclo_vida.py`, Task 3).

- [ ] **Step 7: Commit**

```bash
git add models.py migrations.py tests/test_fase5_rdo_ciclo_vida.py
git commit -m "feat(fase5): coluna rdo.estado com backfill honesto

Ciclo de vida entra em coluna NOVA. rdo.status continua 'Finalizado'
porque nove consumidores filtram por ele. Backfill marca os 5.532 RDOs
historicos como 'preenchido' — nenhum vira 'assinado', porque nenhum foi
assinado por pessoa nenhuma."
```

---

## Task 2: Trilha de transições (`RDOTransicaoEstado`) e migration 261

**Files:**
- Modify: `models.py` (nova classe após `class RDOFoto`, linha 1105)
- Modify: `migrations.py` (função nova + registro)
- Test: `tests/test_fase5_rdo_ciclo_vida.py` (acrescenta)

- [ ] **Step 1: Escreva o teste que falha**

Acrescente ao final de `tests/test_fase5_rdo_ciclo_vida.py`:

```python
# ---------------------------------------------------------------------------
# Trilha de transições
# ---------------------------------------------------------------------------

def test_modelo_de_transicao_existe_e_persiste():
    from models import RDOTransicaoEstado

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        t = RDOTransicaoEstado(
            rdo_id=rdo.id, admin_id=admin.id,
            estado_anterior='rascunho', estado_novo='preenchido',
            usuario_id=admin.id, motivo='submissão do dia',
            ip='203.0.113.7', detalhes={'origem': 'teste'},
        )
        db.session.add(t)
        db.session.commit()
        tid = t.id

    with app.app_context():
        recarregado = db.session.get(RDOTransicaoEstado, tid)
        assert recarregado.estado_anterior == 'rascunho'
        assert recarregado.estado_novo == 'preenchido'
        assert recarregado.detalhes == {'origem': 'teste'}
        assert recarregado.criado_em is not None


def test_transicao_e_apagada_junto_com_o_rdo():
    """ON DELETE CASCADE: excluir RDO não pode deixar trilha órfã."""
    from models import RDOTransicaoEstado

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        db.session.add(RDOTransicaoEstado(
            rdo_id=rdo.id, admin_id=admin.id,
            estado_anterior='rascunho', estado_novo='preenchido',
            usuario_id=admin.id,
        ))
        db.session.commit()
        rid = rdo.id
        db.session.delete(rdo)
        db.session.commit()
        assert RDOTransicaoEstado.query.filter_by(rdo_id=rid).count() == 0
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase5_rdo_ciclo_vida.py -v -k transicao
```

Esperado: FAIL na coleção — `ImportError: cannot import name 'RDOTransicaoEstado' from 'models'`.

- [ ] **Step 3: Adicione o modelo**

Em `models.py`, imediatamente após o fim de `class RDOFoto` (linha 1105, antes do comentário `# ===== MÓDULO ALIMENTAÇÃO`), insira:

```python
class RDOTransicaoEstado(db.Model):
    """Trilha de auditoria do ciclo de vida do RDO — Fase 5.

    Copia deliberadamente a forma de `CronogramaImportacaoEvento`
    (models.py:5178), que é o único state machine auditado do sistema:
    evento + detalhes JSON + usuario_id + criado_em. Antes desta tabela o
    RDO não tinha trilha nenhuma — o próprio serviço de apontamento
    registra a lacuna em services/cronograma_apontamento_service.py:330:
    "não há tabela de eventos de RDO".

    `estado_anterior` é nullable porque a primeira linha de um RDO criado
    já dentro da Fase 5 registra a entrada em 'rascunho' vindo do nada.
    """
    __tablename__ = 'rdo_transicao_estado'
    __table_args__ = (
        db.Index('ix_rdo_transicao_rdo_criado', 'rdo_id', 'criado_em'),
    )

    id = db.Column(db.Integer, primary_key=True)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id', ondelete='CASCADE'),
                       nullable=False, index=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'),
                         nullable=False, index=True)
    estado_anterior = db.Column(db.String(20), nullable=True)
    estado_novo = db.Column(db.String(20), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'),
                           nullable=True)
    # A pessoa de RH por trás do login (Fase 1). Redundante com
    # usuario_id por desenho: se o vínculo mudar depois, a trilha
    # continua dizendo quem era na época.
    funcionario_id = db.Column(
        db.Integer, db.ForeignKey('funcionario.id', ondelete='SET NULL'),
        nullable=True)
    motivo = db.Column(db.Text, nullable=True)
    ip = db.Column(db.String(45), nullable=True)  # 45 = IPv6 completo
    detalhes = db.Column(db.JSON, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    rdo = db.relationship(
        'RDO',
        backref=db.backref('transicoes', lazy='dynamic',
                           cascade='all, delete-orphan',
                           passive_deletes=True,
                           order_by='RDOTransicaoEstado.criado_em'))

    def __repr__(self):
        return (f'<RDOTransicaoEstado rdo={self.rdo_id} '
                f'{self.estado_anterior}→{self.estado_novo}>')
```

- [ ] **Step 4: Escreva a migration 261**

Em `migrations.py`, imediatamente antes de `def executar_migracoes():`, insira:

```python
def migration_261_rdo_transicao_estado():
    """Fase 5 — tabela rdo_transicao_estado (trilha do ciclo de vida).

    Aditiva: criar vazia é seguro. Nenhuma linha histórica é inventada —
    não existe informação de quem transicionou os 5.532 RDOs antigos, e
    fabricar autoria é justamente o que esta fase veio impedir.
    """
    logger.info("[Migration 261] Iniciando — tabela rdo_transicao_estado")

    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS rdo_transicao_estado (
            id SERIAL PRIMARY KEY,
            rdo_id INTEGER NOT NULL REFERENCES rdo(id) ON DELETE CASCADE,
            admin_id INTEGER NOT NULL REFERENCES usuario(id),
            estado_anterior VARCHAR(20),
            estado_novo VARCHAR(20) NOT NULL,
            usuario_id INTEGER REFERENCES usuario(id),
            funcionario_id INTEGER REFERENCES funcionario(id) ON DELETE SET NULL,
            motivo TEXT,
            ip VARCHAR(45),
            detalhes JSON,
            criado_em TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """))
    db.session.commit()

    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_rdo_transicao_estado_rdo_id
        ON rdo_transicao_estado (rdo_id)
    """))
    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_rdo_transicao_estado_admin_id
        ON rdo_transicao_estado (admin_id)
    """))
    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_rdo_transicao_rdo_criado
        ON rdo_transicao_estado (rdo_id, criado_em)
    """))
    db.session.commit()

    logger.info("[Migration 261] Concluída com sucesso")
```

- [ ] **Step 5: Registre a migration**

Em `migrations.py`, na lista `migrations_to_run`, logo após a entrada `260`, adicione:

```python
            (261, "Fase 5 — tabela rdo_transicao_estado (trilha do ciclo de vida do RDO)", migration_261_rdo_transicao_estado),
```

- [ ] **Step 6: Aplique e rode**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "Migration 261|ERRO|ERROR"
python -m pytest tests/test_fase5_rdo_ciclo_vida.py -v -k transicao
```

Esperado: `[Migration 261] Concluída com sucesso` e os 2 testes PASSAM.

- [ ] **Step 7: Commit**

```bash
git add models.py migrations.py tests/test_fase5_rdo_ciclo_vida.py
git commit -m "feat(fase5): trilha de transicoes do RDO

RDOTransicaoEstado copia a forma de CronogramaImportacaoEvento
(models.py:5178), o unico state machine auditado do sistema. Nenhuma
linha historica e inventada."
```

---

## Task 3: A máquina de estados (`services/rdo_ciclo_vida.py`)

**Files:**
- Create: `services/rdo_ciclo_vida.py`
- Test: `tests/test_fase5_rdo_ciclo_vida.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente ao final de `tests/test_fase5_rdo_ciclo_vida.py`:

```python
# ---------------------------------------------------------------------------
# Máquina de estados
# ---------------------------------------------------------------------------

def test_conjunto_de_estados_e_fechado():
    from services.rdo_ciclo_vida import ESTADOS

    assert ESTADOS == {'rascunho', 'preenchido', 'assinado',
                       'aprovado', 'retificado'}


def test_transicoes_validas_sao_as_esperadas():
    from services.rdo_ciclo_vida import TRANSICOES_VALIDAS

    assert TRANSICOES_VALIDAS['rascunho'] == {'preenchido'}
    assert TRANSICOES_VALIDAS['preenchido'] == {'rascunho', 'assinado'}
    assert TRANSICOES_VALIDAS['assinado'] == {'aprovado', 'retificado'}
    assert TRANSICOES_VALIDAS['aprovado'] == {'retificado'}
    assert TRANSICOES_VALIDAS['retificado'] == set()


def test_transicionar_grava_estado_e_trilha():
    from models import RDOTransicaoEstado
    from services.rdo_ciclo_vida import PREENCHIDO, transicionar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)

        transicionar(rdo, PREENCHIDO, usuario=admin, motivo='fim do dia',
                     ip='203.0.113.7')
        db.session.commit()
        rid = rdo.id

    with app.app_context():
        recarregado = db.session.get(RDO, rid)
        assert recarregado.estado == PREENCHIDO
        trilha = RDOTransicaoEstado.query.filter_by(rdo_id=rid).all()
        assert len(trilha) == 1
        assert trilha[0].estado_anterior == 'rascunho'
        assert trilha[0].estado_novo == PREENCHIDO
        assert trilha[0].motivo == 'fim do dia'
        assert trilha[0].ip == '203.0.113.7'


def test_transicao_invalida_e_recusada():
    from services.rdo_ciclo_vida import APROVADO, TransicaoInvalida, transicionar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)  # rascunho

        with pytest.raises(TransicaoInvalida):
            transicionar(rdo, APROVADO, usuario=admin)
        db.session.rollback()
        assert db.session.get(RDO, rdo.id).estado == 'rascunho'


def test_estado_desconhecido_e_recusado():
    from services.rdo_ciclo_vida import TransicaoInvalida, transicionar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        with pytest.raises(TransicaoInvalida):
            transicionar(rdo, 'homologado', usuario=admin)
        db.session.rollback()


def test_transicao_para_o_mesmo_estado_e_no_op_sem_trilha():
    """Reenviar o mesmo estado não pode poluir a trilha."""
    from models import RDOTransicaoEstado
    from services.rdo_ciclo_vida import RASCUNHO, transicionar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        transicionar(rdo, RASCUNHO, usuario=admin)
        db.session.commit()
        assert RDOTransicaoEstado.query.filter_by(rdo_id=rdo.id).count() == 0


def test_estados_imutaveis_sao_os_tres_finais():
    from services.rdo_ciclo_vida import ESTADOS_IMUTAVEIS

    assert ESTADOS_IMUTAVEIS == {'assinado', 'aprovado', 'retificado'}


def test_garantir_editavel_passa_em_rascunho_e_preenchido():
    from services.rdo_ciclo_vida import (PREENCHIDO, garantir_editavel,
                                         transicionar)

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        garantir_editavel(rdo)          # rascunho: passa
        transicionar(rdo, PREENCHIDO, usuario=admin)
        db.session.commit()
        garantir_editavel(rdo)          # preenchido: passa


def test_garantir_editavel_recusa_assinado():
    from services.rdo_ciclo_vida import (ASSINADO, PREENCHIDO, RDOImutavel,
                                         garantir_editavel, transicionar)

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        transicionar(rdo, PREENCHIDO, usuario=admin)
        transicionar(rdo, ASSINADO, usuario=admin)
        db.session.commit()
        with pytest.raises(RDOImutavel):
            garantir_editavel(rdo)
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase5_rdo_ciclo_vida.py -v -k "estados or transic or editavel"
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'services.rdo_ciclo_vida'`.

- [ ] **Step 3: Implemente a máquina de estados**

Crie `services/rdo_ciclo_vida.py`:

```python
#!/usr/bin/env python3
"""Ciclo de vida do RDO — SIGE Fase 5.

ANTES desta fase o RDO não tinha ciclo de vida nenhum. A coluna
`RDO.status` nascia `'Finalizado'` (models.py:860, comentário literal
"Task #12: RDO sempre Finalizado") e oito caminhos de escrita gravavam
esse valor na mão:

    views/rdo.py:698, 1539, 1629, 1754, 2742, 4574
    rdo_editar_sistema.py:221
    crud_rdo_completo.py:331, 565

Consequência prática: um RDO de três meses atrás podia ser reescrito por
qualquer usuário do tenant, sem registro de quem, quando ou por quê — e o
custo de mão de obra já lançado a partir dele ficava pendurado num
documento que mudou embaixo.

Este módulo é o dono único do estado. A coluna `RDO.status` NÃO é tocada:
nove consumidores filtram por `status == 'Finalizado'`
(cronograma_views.py:2315,2345; portal_obras_views.py:187;
services/medicao_service.py:243; services/rdo_custos.py:330;
services/metricas_produtividade.py:186,972,1302,1320) e mudar aquele
valor sumiria com o RDO do portal do cliente e das métricas.

O padrão de máquina de estados aqui é o mesmo de `CronogramaImportacao`
(models.py:5018) — dicionário de transições válidas + tabela de trilha
auditada. A Fase 2 (máquina de estados da Obra) usa o mesmo molde; se ela
extrair um helper genérico, este módulo passa a consumi-lo sem mudar a
API pública.
"""
from __future__ import annotations

import contextlib
import contextvars
import logging

from models import RDO, RDOTransicaoEstado, db

logger = logging.getLogger('rdo.ciclo_vida')

# ── Estados ──────────────────────────────────────────────────────────
RASCUNHO = 'rascunho'      # em preenchimento; edição livre
PREENCHIDO = 'preenchido'  # submetido; custos lançados; ainda corrigível
ASSINADO = 'assinado'      # autoria registrada; IMUTÁVEL
APROVADO = 'aprovado'      # aceite do gestor da obra; IMUTÁVEL, terminal
RETIFICADO = 'retificado'  # substituído por um RDO retificador; terminal

ESTADOS = {RASCUNHO, PREENCHIDO, ASSINADO, APROVADO, RETIFICADO}

# Estado em que os 5.532 RDOs históricos caíram no backfill da migration
# 260. É o equivalente semântico do 'Finalizado' de hoje.
ESTADO_LEGADO = PREENCHIDO

TRANSICOES_VALIDAS = {
    # Submeter o dia. Depois disso os custos de mão de obra existem.
    RASCUNHO: {PREENCHIDO},
    # Reabrir (só GESTOR — a autorização mora na rota) ou assinar.
    PREENCHIDO: {RASCUNHO, ASSINADO},
    # Assinado não volta. Ou é aprovado, ou é retificado por outro RDO.
    ASSINADO: {APROVADO, RETIFICADO},
    APROVADO: {RETIFICADO},
    RETIFICADO: set(),
}

# A partir daqui o documento não aceita mais escrita — nem nele, nem nos
# filhos (mão de obra, subatividades, fotos, equipamentos, ocorrências,
# apontamentos de cronograma). Corrigir é criar um RDO retificador.
ESTADOS_IMUTAVEIS = {ASSINADO, APROVADO, RETIFICADO}

# Rótulos para a UI (pt-BR).
ROTULOS = {
    RASCUNHO: 'Rascunho',
    PREENCHIDO: 'Preenchido',
    ASSINADO: 'Assinado',
    APROVADO: 'Aprovado',
    RETIFICADO: 'Retificado',
}

# Classe de cor Bootstrap por estado (usado no selo do template).
CORES = {
    RASCUNHO: 'secondary',
    PREENCHIDO: 'primary',
    ASSINADO: 'success',
    APROVADO: 'success',
    RETIFICADO: 'warning',
}


class CicloVidaInvalido(ValueError):
    """Base das violações de ciclo de vida (mensagem apta à UI)."""


class TransicaoInvalida(CicloVidaInvalido):
    """Transição fora de TRANSICOES_VALIDAS, ou estado desconhecido."""


class RDOImutavel(CicloVidaInvalido):
    """Tentativa de escrever num RDO assinado/aprovado/retificado."""


# ── Bypass controlado da guarda de imutabilidade ─────────────────────
# A guarda (services/rdo_ciclo_vida._guarda_imutabilidade, Task 4) barra
# QUALQUER escrita em RDO imutável. Mas as próprias transições de estado
# — assinado → aprovado, assinado → retificado — precisam escrever no
# RDO. Este ContextVar é a única porta: quem entra aqui declara que sabe
# o que está fazendo, e o teste
# test_bypass_nao_vaza_entre_transacoes prova que ele volta ao normal.
_BYPASS = contextvars.ContextVar('rdo_ciclo_vida_bypass', default=False)


@contextlib.contextmanager
def escrita_de_ciclo_de_vida():
    """Libera a guarda de imutabilidade dentro do bloco.

    Uso EXCLUSIVO deste módulo e de services/rdo_assinatura.py. Não use
    em rota, view ou script: se você precisa disso, o que você quer é um
    RDO retificador.
    """
    token = _BYPASS.set(True)
    try:
        yield
    finally:
        _BYPASS.reset(token)


def bypass_ativo() -> bool:
    return _BYPASS.get()


# ── API pública ──────────────────────────────────────────────────────
def estado_de(rdo) -> str:
    """Estado do RDO, com fallback para o legado.

    RDOs criados por caminhos que ainda não conhecem a coluna (ou linhas
    em memória antes do flush) devolvem RASCUNHO, nunca None.
    """
    return getattr(rdo, 'estado', None) or RASCUNHO


def e_imutavel(rdo) -> bool:
    return estado_de(rdo) in ESTADOS_IMUTAVEIS


def garantir_editavel(rdo) -> None:
    """Levanta RDOImutavel se o RDO não aceita mais escrita.

    É o contrato oferecido ao plano irmão (apontamento percentual): chame
    antes de gravar apontamento. Mesmo sem a chamada, a guarda
    `before_flush` barra — isto aqui só dá uma mensagem melhor e mais
    cedo.
    """
    if e_imutavel(rdo):
        raise RDOImutavel(
            f'RDO {getattr(rdo, "numero_rdo", rdo.id)} está '
            f'{ROTULOS[estado_de(rdo)].lower()} e não aceita mais edição. '
            f'Para corrigir, emita um RDO retificador.')


def pode_transicionar(rdo, novo_estado: str) -> bool:
    if novo_estado not in ESTADOS:
        return False
    atual = estado_de(rdo)
    return novo_estado in TRANSICOES_VALIDAS.get(atual, set())


def transicionar(rdo, novo_estado: str, *, usuario=None, funcionario=None,
                 motivo=None, ip=None, detalhes=None) -> RDOTransicaoEstado | None:
    """Muda o estado do RDO e grava a trilha. NÃO faz commit.

    Devolve a `RDOTransicaoEstado` criada, ou `None` quando o RDO já
    estava no estado pedido (no-op deliberado: reenvio de formulário não
    pode poluir a trilha).

    Levanta `TransicaoInvalida` para estado desconhecido ou transição
    fora de `TRANSICOES_VALIDAS`. A AUTORIZAÇÃO (quem pode fazer o quê)
    NÃO mora aqui — mora na rota, com `utils.autorizacao`. Este módulo
    responde "essa transição existe?", não "você pode?".
    """
    if novo_estado not in ESTADOS:
        raise TransicaoInvalida(
            f'Estado desconhecido: {novo_estado!r}. '
            f'Válidos: {sorted(ESTADOS)}')

    atual = estado_de(rdo)
    if atual == novo_estado:
        logger.debug('[ciclo-vida] rdo=%s já está em %s — no-op',
                     rdo.id, novo_estado)
        return None

    if novo_estado not in TRANSICOES_VALIDAS.get(atual, set()):
        raise TransicaoInvalida(
            f'RDO {getattr(rdo, "numero_rdo", rdo.id)}: transição '
            f'{atual} → {novo_estado} não é permitida. '
            f'A partir de {atual} só cabe: '
            f'{sorted(TRANSICOES_VALIDAS.get(atual, set())) or "nada"}.')

    funcionario_id = getattr(funcionario, 'id', None)
    if funcionario_id is None and usuario is not None:
        funcionario_id = getattr(usuario, 'funcionario_id', None)

    admin_id = rdo.admin_id or getattr(rdo.obra, 'admin_id', None)

    with escrita_de_ciclo_de_vida():
        rdo.estado = novo_estado
        trilha = RDOTransicaoEstado(
            rdo_id=rdo.id,
            admin_id=admin_id,
            estado_anterior=atual,
            estado_novo=novo_estado,
            usuario_id=getattr(usuario, 'id', None),
            funcionario_id=funcionario_id,
            motivo=motivo,
            ip=ip,
            detalhes=detalhes,
        )
        db.session.add(trilha)
        db.session.flush()

    logger.info('[ciclo-vida] rdo=%s %s→%s usuario=%s funcionario=%s ip=%s '
                'motivo=%r', rdo.id, atual, novo_estado,
                getattr(usuario, 'id', None), funcionario_id, ip, motivo)
    return trilha
```

- [ ] **Step 4: Rode os testes**

```bash
python -m pytest tests/test_fase5_rdo_ciclo_vida.py -v
```

Esperado: os 14 testes do arquivo PASSAM.

- [ ] **Step 5: Commit**

```bash
git add services/rdo_ciclo_vida.py tests/test_fase5_rdo_ciclo_vida.py
git commit -m "feat(fase5): maquina de estados do RDO

rascunho -> preenchido -> assinado -> aprovado, com retificado como saida
dos dois terminais. transicionar() valida a transicao e grava a trilha;
a autorizacao fica na rota. Molde copiado de CronogramaImportacao."
```

---

## Task 4: Guarda de imutabilidade (`before_flush`)

**Files:**
- Modify: `services/rdo_ciclo_vida.py` (acrescenta o listener no fim)
- Modify: `app.py` (import do módulo para registrar o listener)
- Test: `tests/test_fase5_rdo_ciclo_vida.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente ao final de `tests/test_fase5_rdo_ciclo_vida.py`:

```python
# ---------------------------------------------------------------------------
# Guarda de imutabilidade
# ---------------------------------------------------------------------------

def _assinar_direto(rdo, admin):
    """Leva o RDO até 'assinado' sem passar pela rota (Task 7 ainda não existe)."""
    from services.rdo_ciclo_vida import ASSINADO, PREENCHIDO, transicionar
    transicionar(rdo, PREENCHIDO, usuario=admin)
    transicionar(rdo, ASSINADO, usuario=admin)
    db.session.commit()


def test_editar_rdo_assinado_e_barrado_no_flush():
    from services.rdo_ciclo_vida import RDOImutavel

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        _assinar_direto(rdo, admin)

        rdo.comentario_geral = 'reescrevendo a história'
        with pytest.raises(RDOImutavel):
            db.session.commit()
        db.session.rollback()
        assert db.session.get(RDO, rdo.id).comentario_geral == \
            'Concretagem do radier.'


def test_inserir_mao_de_obra_em_rdo_assinado_e_barrado():
    from models import RDOMaoObra
    from services.rdo_ciclo_vida import RDOImutavel

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        func = Funcionario(
            nome=f'Pedreiro {_sfx()}', cpf=_sfx().ljust(14, '0')[:14],
            codigo=f'FF5{_sfx()[:6].upper()}', data_admissao=date(2025, 1, 1),
            admin_id=admin.id, ativo=True,
        )
        db.session.add(func)
        db.session.commit()
        _assinar_direto(rdo, admin)

        db.session.add(RDOMaoObra(
            rdo_id=rdo.id, admin_id=admin.id, funcionario_id=func.id,
            funcao_exercida='Pedreiro', horas_trabalhadas=8.0))
        with pytest.raises(RDOImutavel):
            db.session.commit()
        db.session.rollback()
        assert RDOMaoObra.query.filter_by(rdo_id=rdo.id).count() == 0


def test_apontamento_de_cronograma_em_rdo_assinado_e_barrado():
    """Ponto de contato com o plano irmão (modo de apontamento)."""
    from models import RDOApontamentoCronograma, TarefaCronograma
    from services.rdo_ciclo_vida import RDOImutavel

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        tarefa = TarefaCronograma(
            obra_id=obra.id, nome_tarefa='Radier', ordem=1, duracao_dias=5,
            quantidade_total=100.0, unidade_medida='m2',
            percentual_concluido=0.0, data_inicio=date(2026, 6, 20),
            data_fim=date(2026, 6, 25), admin_id=admin.id)
        db.session.add(tarefa)
        rdo = _rdo(obra, admin.id)
        db.session.commit()
        _assinar_direto(rdo, admin)

        db.session.add(RDOApontamentoCronograma(
            rdo_id=rdo.id, tarefa_cronograma_id=tarefa.id, admin_id=admin.id,
            quantidade_executada_dia=10.0, quantidade_acumulada=10.0,
            percentual_realizado=10.0))
        with pytest.raises(RDOImutavel):
            db.session.commit()
        db.session.rollback()


def test_excluir_rdo_assinado_e_barrado():
    from services.rdo_ciclo_vida import RDOImutavel

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        _assinar_direto(rdo, admin)

        db.session.delete(rdo)
        with pytest.raises(RDOImutavel):
            db.session.commit()
        db.session.rollback()
        assert db.session.get(RDO, rdo.id) is not None


def test_transicao_de_estado_atravessa_a_guarda():
    """assinado → aprovado escreve no RDO imutável e PRECISA passar."""
    from services.rdo_ciclo_vida import APROVADO, transicionar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        _assinar_direto(rdo, admin)

        transicionar(rdo, APROVADO, usuario=admin)
        db.session.commit()
        assert db.session.get(RDO, rdo.id).estado == APROVADO


def test_bypass_nao_vaza_entre_transacoes():
    """Depois da transição, a guarda tem que estar de pé de novo."""
    from services.rdo_ciclo_vida import (APROVADO, RDOImutavel, bypass_ativo,
                                         transicionar)

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        _assinar_direto(rdo, admin)
        transicionar(rdo, APROVADO, usuario=admin)
        db.session.commit()

        assert bypass_ativo() is False
        rdo.comentario_geral = 'depois da aprovação'
        with pytest.raises(RDOImutavel):
            db.session.commit()
        db.session.rollback()


def test_qualquer_caminho_de_escrita_e_barrado():
    """A prova de que a guarda vale para as rotas que ninguém migrou.

    `salvar_rdo_flexivel` (views/rdo.py:3884) é o caminho mais obscuro do
    módulo — 933 linhas, sem nenhuma noção de estado. Se a guarda pega
    ele, pega os outros sete.
    """
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        _assinar_direto(rdo, admin)
        rid, oid, aid = rdo.id, obra.id, admin.id

    cliente = app.test_client()
    with cliente.session_transaction() as sess:
        sess['_user_id'] = str(aid)
        sess['_fresh'] = True

    resposta = cliente.post('/salvar-rdo-flexivel', data={
        'rdo_id': str(rid),
        'obra_id': str(oid),
        'data_relatorio': '2026-06-22',
        'comentario_geral': 'tentativa de reescrita',
    }, follow_redirects=True)
    assert resposta.status_code in (200, 302)

    with app.app_context():
        assert db.session.get(RDO, rid).comentario_geral == \
            'Concretagem do radier.', (
            'salvar_rdo_flexivel reescreveu um RDO assinado — a guarda '
            'before_flush não pegou este caminho')
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase5_rdo_ciclo_vida.py -v -k "barrad or bypass or atravessa or caminho_de_escrita"
```

Esperado: FAIL — as escritas passam sem erro; `pytest.raises(RDOImutavel)` falha com `DID NOT RAISE`.

- [ ] **Step 3: Acrescente a guarda**

Ao final de `services/rdo_ciclo_vida.py`, adicione:

```python
# ── Guarda de imutabilidade ──────────────────────────────────────────
# Por que um listener de sessão em vez de editar as oito rotas de
# escrita: porque não dá para PROVAR que nenhuma foi esquecida. São oito
# lugares hoje (views/rdo.py:698,1539,1629,1754,2742,4574;
# rdo_editar_sistema.py:221; crud_rdo_completo.py:331,565), mais o
# import físico-financeiro, mais os scripts de seed. Um ponto só é
# auditável; oito não são.
#
# O molde de listener em modelo de RDO já existe no repo:
# models.py:1422 (RDOServicoSubatividade before_insert/update) e
# models.py:7018 (RDO after_insert). Aqui é `before_flush` de SESSÃO
# porque precisamos ver inserts, updates E deletes de uma vez.

# Filhos do RDO cuja escrita também é bloqueada. RDOTransicaoEstado e
# RDOAssinatura ficam DE FORA de propósito: são o registro da própria
# transição, e bloqueá-los tornaria impossível assinar.
_MODELOS_FILHOS = (
    'RDOMaoObra', 'RDOServicoSubatividade', 'RDOEquipamento',
    'RDOOcorrencia', 'RDOFoto', 'RDOApontamentoCronograma',
    'RDOSubempreitadaApontamento',
)


def _rdo_id_do_objeto(obj):
    """Devolve o rdo_id que o objeto afeta, ou None se não for do RDO."""
    nome = type(obj).__name__
    if nome == 'RDO':
        return obj.id
    if nome in _MODELOS_FILHOS:
        return getattr(obj, 'rdo_id', None)
    return None


def _registrar_guarda():
    from sqlalchemy import event as sa_event

    @sa_event.listens_for(db.session, 'before_flush')
    def _guarda_imutabilidade(session, flush_context, instances):
        if _BYPASS.get():
            return

        candidatos = {}
        for coleccao in (session.new, session.dirty, session.deleted):
            for obj in coleccao:
                rdo_id = _rdo_id_do_objeto(obj)
                if rdo_id is not None:
                    candidatos.setdefault(rdo_id, []).append(obj)

        if not candidatos:
            return

        with session.no_autoflush:
            for rdo_id, objetos in candidatos.items():
                alvo = session.get(RDO, rdo_id)
                if alvo is None:
                    continue
                # `estado` recém-atribuído nesta sessão não vale: o que
                # importa é o estado PERSISTIDO. Sem bypass, mudar estado
                # é justamente o que não pode acontecer por fora.
                from sqlalchemy import inspect as sa_inspect
                historico = sa_inspect(alvo).attrs.estado.history
                persistido = (historico.deleted[0] if historico.deleted
                              else alvo.estado)
                if persistido not in ESTADOS_IMUTAVEIS:
                    continue
                nomes = sorted({type(o).__name__ for o in objetos})
                logger.warning(
                    '[ciclo-vida] escrita BARRADA em rdo=%s (estado=%s): %s',
                    rdo_id, persistido, nomes)
                raise RDOImutavel(
                    f'RDO {alvo.numero_rdo or alvo.id} está '
                    f'{ROTULOS.get(persistido, persistido).lower()} e não '
                    f'aceita mais alteração ({", ".join(nomes)}). Para '
                    f'corrigir, emita um RDO retificador.')

    logger.info('[ciclo-vida] guarda de imutabilidade registrada')


_registrar_guarda()
```

- [ ] **Step 4: Garanta que o módulo é importado no boot**

Em `app.py`, ao final do arquivo (depois do último `register_blueprint` — **nunca acima da linha 386**, que é o contrato de ordem de import documentado em `ESTADO-ATUAL.md:132`), acrescente:

```python
# Fase 5 — importar registra o listener `before_flush` que impede escrita
# em RDO assinado/aprovado/retificado. Sem este import a guarda não
# existe e as oito rotas de escrita de RDO voltam a poder reescrever
# documento assinado. Import tardio de propósito: o módulo depende de
# `models` já configurado.
try:
    import services.rdo_ciclo_vida  # noqa: F401
    logging.info("[OK] Fase 5: guarda de imutabilidade de RDO ativa")
except Exception as _e_ciclo:
    logging.error("[ERRO] Fase 5: guarda de imutabilidade NÃO registrada: %s",
                  _e_ciclo)
```

- [ ] **Step 5: Rode os testes**

```bash
python -m pytest tests/test_fase5_rdo_ciclo_vida.py -v
```

Esperado: os 21 testes PASSAM, incluindo `test_qualquer_caminho_de_escrita_e_barrado`.

- [ ] **Step 6: Rode a família de RDO inteira para checar regressão**

```bash
python -m pytest tests/ -m "not browser" -k rdo -q 2>&1 | tail -20
```

Esperado: mesma contagem de falhas da baseline anotada no início da fase. A guarda só bloqueia RDO em estado imutável, e após a migration 260 nenhum RDO histórico está nesse estado — se algo ficar vermelho aqui, é bug da guarda, não do teste.

- [ ] **Step 7: Commit**

```bash
git add services/rdo_ciclo_vida.py app.py tests/test_fase5_rdo_ciclo_vida.py
git commit -m "feat(fase5): imutabilidade do RDO por guarda before_flush

Um chokepoint em vez de oito edicoes de rota. Barra insert/update/delete
no RDO e nos sete modelos filhos quando o estado persistido e assinado,
aprovado ou retificado. As transicoes de estado atravessam por um
ContextVar explicito, provado por test_bypass_nao_vaza_entre_transacoes."
```

---

## Task 5: Modelo `RDOAssinatura` e migration 262

**Files:**
- Modify: `models.py` (nova classe após `class RDOTransicaoEstado`)
- Modify: `migrations.py` (função nova + registro)
- Test: `tests/test_fase5_rdo_assinatura.py`

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_fase5_rdo_assinatura.py`:

```python
"""Fase 5 — assinatura do RDO.

Antes desta fase não existia assinatura nenhuma: o PDF imprimia uma
LINHA EM BRANCO para caneta (services/rdo_pdf_service.py:798-865) e o
único vínculo com uma pessoa era `RDO.criado_por_id` → `usuario.id`,
sem papel, sem carimbo de tempo, sem integridade.

Decisão jurídica adotada (ver seção "A decisão jurídica" do plano):
registro de autoria + integridade (hash SHA-256 + timestamp + IP),
NÃO ICP-Brasil. Base: MP 2.200-2/2001, art. 10, §2º. `provedor` nasce
'interno' para que Clicksign/D4Sign entre depois sem migração.
"""
import os
import sys
import uuid
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os 54 blueprints antes de qualquer request
from app import app, db
from models import (Cliente, Funcionario, Obra, PapelObra, RDO, TipoUsuario,
                    Usuario, UsuarioObra)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase5-assinatura'
    yield


def _sfx():
    return uuid.uuid4().hex[:8]


def _admin(nome='Admin F5A'):
    suf = _sfx()
    u = Usuario(
        username=f'f5s_{suf}', email=f'f5s_{suf}@test.local',
        nome=f'{nome} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _funcionario(admin_id, nome='Encarregado'):
    suf = _sfx()
    f = Funcionario(
        codigo=f'F5{suf[:6].upper()}', nome=f'{nome} {suf}',
        cpf=suf.ljust(14, '0')[:14], email=f'f5f_{suf}@test.local',
        data_admissao=date(2025, 1, 1), admin_id=admin_id, ativo=True,
    )
    db.session.add(f)
    db.session.commit()
    return f


def _operador(admin_id, funcionario, nome='Apontador'):
    """Usuário FUNCIONARIO já vinculado à pessoa de RH (Fase 1)."""
    suf = _sfx()
    u = Usuario(
        username=f'f5o_{suf}', email=f'f5o_{suf}@test.local', nome=f'{nome} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
        admin_id=admin_id, funcionario_id=funcionario.id,
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id, nome='Obra F5A'):
    suf = _sfx()
    cli = Cliente(nome=f'CLI-F5A-{suf}', admin_id=admin_id)
    db.session.add(cli)
    db.session.flush()
    o = Obra(
        nome=f'{nome} {suf}', codigo=f'OA5{suf[:6].upper()}',
        data_inicio=date(2026, 1, 1), admin_id=admin_id,
        cliente_id=cli.id, valor_contrato=250000,
    )
    db.session.add(o)
    db.session.commit()
    return o


def _vincular(usuario, obra, papel):
    v = UsuarioObra(usuario_id=usuario.id, obra_id=obra.id, papel=papel,
                    admin_id=obra.admin_id, ativo=True)
    db.session.add(v)
    db.session.commit()
    return v


def _rdo(obra, admin_id, criado_por_id=None):
    suf = _sfx()
    r = RDO(
        numero_rdo=f'RDO-F5A-{suf}', data_relatorio=date(2026, 6, 22),
        obra_id=obra.id, admin_id=admin_id, criado_por_id=criado_por_id,
        comentario_geral='Montagem dos perfis de aço do painel P3.',
        clima_geral='Ensolarado', temperatura_media='28°C',
    )
    db.session.add(r)
    db.session.commit()
    return r


def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------

def test_modelo_de_assinatura_existe_e_persiste():
    from models import RDOAssinatura

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        rdo = _rdo(obra, admin.id, criado_por_id=op.id)

        a = RDOAssinatura(
            rdo_id=rdo.id, admin_id=admin.id, usuario_id=op.id,
            funcionario_id=func.id, papel='executor',
            nome_signatario=op.nome, cargo_signatario='Encarregado',
            hash_conteudo='a' * 64, algoritmo='sha256', provedor='interno',
            ip='203.0.113.9', user_agent='pytest/1.0',
        )
        db.session.add(a)
        db.session.commit()
        aid = a.id

    with app.app_context():
        r = db.session.get(RDOAssinatura, aid)
        assert r.papel == 'executor'
        assert r.algoritmo == 'sha256'
        assert r.provedor == 'interno'
        assert r.assinado_em is not None
        assert r.hash_conteudo == 'a' * 64


def test_uma_assinatura_por_papel_por_rdo():
    """O mesmo papel não assina duas vezes o mesmo RDO."""
    from sqlalchemy.exc import IntegrityError

    from models import RDOAssinatura

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        rdo = _rdo(obra, admin.id)

        for i in range(2):
            db.session.add(RDOAssinatura(
                rdo_id=rdo.id, admin_id=admin.id, usuario_id=op.id,
                funcionario_id=func.id, papel='executor',
                nome_signatario=op.nome, hash_conteudo='b' * 64,
                algoritmo='sha256', provedor='interno'))
            if i == 0:
                db.session.commit()
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_assinatura_e_apagada_junto_com_o_rdo():
    from models import RDOAssinatura
    from services.rdo_ciclo_vida import escrita_de_ciclo_de_vida

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        rdo = _rdo(obra, admin.id)
        db.session.add(RDOAssinatura(
            rdo_id=rdo.id, admin_id=admin.id, usuario_id=op.id,
            funcionario_id=func.id, papel='executor',
            nome_signatario=op.nome, hash_conteudo='c' * 64,
            algoritmo='sha256', provedor='interno'))
        db.session.commit()
        rid = rdo.id
        # O RDO ainda está em rascunho, então a guarda não bloqueia o delete.
        db.session.delete(rdo)
        db.session.commit()
        assert RDOAssinatura.query.filter_by(rdo_id=rid).count() == 0
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase5_rdo_assinatura.py -v
```

Esperado: FAIL na coleção — `ImportError: cannot import name 'RDOAssinatura' from 'models'`.

- [ ] **Step 3: Adicione o modelo**

Em `models.py`, imediatamente após o fim de `class RDOTransicaoEstado` (criada na Task 2), insira:

```python
class RDOAssinatura(db.Model):
    """Assinatura eletrônica de um RDO — Fase 5.

    ESCOPO JURÍDICO ADOTADO (ver docs/superpowers/plans/
    2026-07-21-fase-5-rdo-ciclo-vida-assinatura.md, seção "A decisão
    jurídica"): registro de AUTORIA + INTEGRIDADE, não ICP-Brasil.
    Base legal: MP 2.200-2/2001, art. 10, §2º — outros meios de
    comprovação de autoria e integridade, admitidos pelas partes. O RDO é
    documento interno construtora ↔ equipe; o que é oponível a terceiro
    (medição assinada pelo cliente) fica para a Fase 9a, e é lá que
    ICP-Brasil/Clicksign/D4Sign se justificam.

    `provedor` nasce 'interno' exatamente para que um provedor externo
    entre depois sem migração de schema: bastaria gravar 'clicksign' e
    preencher `referencia_externa`.

    A identidade vem da Fase 1: `usuario_id` é quem logou,
    `funcionario_id` é a pessoa de RH (`Usuario.funcionario_id`), e
    `nome_signatario`/`cargo_signatario` são SNAPSHOT do momento — se a
    pessoa mudar de cargo ou sair, a assinatura continua dizendo quem
    assinou e em que função.
    """
    __tablename__ = 'rdo_assinatura'
    __table_args__ = (
        db.UniqueConstraint('rdo_id', 'papel', name='uq_rdo_assinatura_papel'),
        db.Index('ix_rdo_assinatura_rdo_papel', 'rdo_id', 'papel'),
    )

    # Papéis de assinatura. Deliberadamente três: quem executou, quem
    # responde pela obra, e a ciência do cliente (Fase 9a a preenche pelo
    # portal; aqui a coluna já existe para não migrar de novo).
    PAPEL_EXECUTOR = 'executor'
    PAPEL_GESTOR = 'gestor'
    PAPEL_CLIENTE = 'cliente'
    PAPEIS = (PAPEL_EXECUTOR, PAPEL_GESTOR, PAPEL_CLIENTE)

    id = db.Column(db.Integer, primary_key=True)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id', ondelete='CASCADE'),
                       nullable=False, index=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'),
                         nullable=False, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'),
                           nullable=True)
    funcionario_id = db.Column(
        db.Integer, db.ForeignKey('funcionario.id', ondelete='SET NULL'),
        nullable=True)

    papel = db.Column(db.String(20), nullable=False)
    nome_signatario = db.Column(db.String(200), nullable=False)
    cargo_signatario = db.Column(db.String(120), nullable=True)

    # Integridade: SHA-256 do payload canônico (services/rdo_hash.py).
    hash_conteudo = db.Column(db.String(128), nullable=False)
    algoritmo = db.Column(db.String(20), nullable=False, default='sha256')
    provedor = db.Column(db.String(30), nullable=False, default='interno')
    referencia_externa = db.Column(db.String(200), nullable=True)

    # Carimbo de tempo do SERVIDOR — não do cliente.
    assinado_em = db.Column(db.DateTime, default=datetime.utcnow,
                            nullable=False)
    # IP real do cliente: ProxyFix(x_for=1) está ativo em app.py:94.
    ip = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(400), nullable=True)
    observacao = db.Column(db.Text, nullable=True)

    rdo = db.relationship(
        'RDO',
        backref=db.backref('assinaturas', lazy='selectin',
                           cascade='all, delete-orphan',
                           passive_deletes=True,
                           order_by='RDOAssinatura.assinado_em'))

    def __repr__(self):
        return (f'<RDOAssinatura rdo={self.rdo_id} papel={self.papel} '
                f'por={self.nome_signatario}>')
```

- [ ] **Step 4: Escreva a migration 262**

Em `migrations.py`, imediatamente antes de `def executar_migracoes():`, insira:

```python
def migration_262_rdo_assinatura():
    """Fase 5 — tabela rdo_assinatura (autoria + integridade).

    Aditiva e vazia. NENHUMA assinatura histórica é fabricada: os 5.532
    RDOs existentes nunca foram assinados, e inventar autoria é o oposto
    do que a tabela existe para provar.

    UNIQUE (rdo_id, papel): um papel assina uma vez. Reassinatura depois
    de correção é RDO retificador (migration 263), não sobrescrita.
    """
    logger.info("[Migration 262] Iniciando — tabela rdo_assinatura")

    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS rdo_assinatura (
            id SERIAL PRIMARY KEY,
            rdo_id INTEGER NOT NULL REFERENCES rdo(id) ON DELETE CASCADE,
            admin_id INTEGER NOT NULL REFERENCES usuario(id),
            usuario_id INTEGER REFERENCES usuario(id),
            funcionario_id INTEGER REFERENCES funcionario(id) ON DELETE SET NULL,
            papel VARCHAR(20) NOT NULL,
            nome_signatario VARCHAR(200) NOT NULL,
            cargo_signatario VARCHAR(120),
            hash_conteudo VARCHAR(128) NOT NULL,
            algoritmo VARCHAR(20) NOT NULL DEFAULT 'sha256',
            provedor VARCHAR(30) NOT NULL DEFAULT 'interno',
            referencia_externa VARCHAR(200),
            assinado_em TIMESTAMP NOT NULL DEFAULT NOW(),
            ip VARCHAR(45),
            user_agent VARCHAR(400),
            observacao TEXT
        )
    """))
    db.session.commit()

    db.session.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_rdo_assinatura_papel
        ON rdo_assinatura (rdo_id, papel)
    """))
    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_rdo_assinatura_rdo_id
        ON rdo_assinatura (rdo_id)
    """))
    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_rdo_assinatura_admin_id
        ON rdo_assinatura (admin_id)
    """))
    db.session.commit()

    logger.info("[Migration 262] Concluída com sucesso")
```

- [ ] **Step 5: Registre a migration**

Em `migrations.py`, na lista `migrations_to_run`, logo após a entrada `261`, adicione:

```python
            (262, "Fase 5 — tabela rdo_assinatura (autoria + hash + carimbo de tempo + IP)", migration_262_rdo_assinatura),
```

- [ ] **Step 6: Aplique e rode**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "Migration 262|ERRO|ERROR"
python -m pytest tests/test_fase5_rdo_assinatura.py -v
```

Esperado: `[Migration 262] Concluída com sucesso` e os 3 testes PASSAM.

- [ ] **Step 7: Commit**

```bash
git add models.py migrations.py tests/test_fase5_rdo_assinatura.py
git commit -m "feat(fase5): modelo RDOAssinatura

Autoria (usuario_id + funcionario_id da Fase 1, com snapshot de nome e
cargo), integridade (hash SHA-256), carimbo de tempo do servidor, IP real
(ProxyFix x_for=1) e user-agent. provedor='interno' deixa a porta aberta
para Clicksign/D4Sign sem migracao. Nenhuma assinatura historica e
fabricada."
```

---

## Task 6: Hash canônico do RDO (`services/rdo_hash.py`)

**Files:**
- Create: `services/rdo_hash.py`
- Test: `tests/test_fase5_rdo_assinatura.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente ao final de `tests/test_fase5_rdo_assinatura.py`:

```python
# ---------------------------------------------------------------------------
# Hash canônico
# ---------------------------------------------------------------------------

def test_hash_e_determinista():
    from services.rdo_hash import calcular_hash

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        assert calcular_hash(rdo) == calcular_hash(rdo)


def test_hash_tem_64_hex():
    from services.rdo_hash import calcular_hash

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        h = calcular_hash(rdo)
        assert len(h) == 64
        assert all(c in '0123456789abcdef' for c in h)


def test_hash_muda_quando_o_comentario_muda():
    from services.rdo_hash import calcular_hash

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        antes = calcular_hash(rdo)
        rdo.comentario_geral = 'Choveu; frente parada após as 14h.'
        db.session.commit()
        assert calcular_hash(rdo) != antes


def test_hash_muda_quando_a_mao_de_obra_muda():
    from models import RDOMaoObra
    from services.rdo_hash import calcular_hash

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        rdo = _rdo(obra, admin.id)
        antes = calcular_hash(rdo)
        db.session.add(RDOMaoObra(
            rdo_id=rdo.id, admin_id=admin.id, funcionario_id=func.id,
            funcao_exercida='Montador', horas_trabalhadas=8.0))
        db.session.commit()
        db.session.refresh(rdo)
        assert calcular_hash(rdo) != antes


def test_hash_nao_depende_da_ordem_de_insercao_da_mao_de_obra():
    """Duas linhas iguais em ordem trocada têm que dar o mesmo hash."""
    from models import RDOMaoObra
    from services.rdo_hash import calcular_hash

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        f1, f2 = _funcionario(admin.id, 'A'), _funcionario(admin.id, 'B')
        r1, r2 = _rdo(obra, admin.id), _rdo(obra, admin.id)
        for func, horas in ((f1, 8.0), (f2, 6.0)):
            db.session.add(RDOMaoObra(rdo_id=r1.id, admin_id=admin.id,
                                      funcionario_id=func.id,
                                      funcao_exercida='Montador',
                                      horas_trabalhadas=horas))
        for func, horas in ((f2, 6.0), (f1, 8.0)):
            db.session.add(RDOMaoObra(rdo_id=r2.id, admin_id=admin.id,
                                      funcionario_id=func.id,
                                      funcao_exercida='Montador',
                                      horas_trabalhadas=horas))
        db.session.commit()
        db.session.refresh(r1)
        db.session.refresh(r2)
        from services.rdo_hash import payload_canonico
        assert payload_canonico(r1)['mao_obra'] == \
            payload_canonico(r2)['mao_obra']


def test_hash_nao_inclui_os_bytes_da_foto():
    """A assinatura não pode amarrar-se ao formato de armazenamento.

    A Task 15 migra as fotos de base64 no banco para arquivo em disco.
    Se o hash cobrisse os bytes, toda assinatura anterior à migração
    ficaria inválida por uma mudança que não alterou o conteúdo
    declarado.
    """
    from models import RDOFoto
    from services.rdo_hash import calcular_hash, payload_canonico

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        foto = RDOFoto(
            admin_id=admin.id, rdo_id=rdo.id,
            nome_arquivo='p3.webp', caminho_arquivo='uploads/rdo/x/p3.webp',
            nome_original='p3.jpg', descricao='Painel P3 montado',
            ordem=0, imagem_otimizada_base64='data:image/webp;base64,AAAA')
        db.session.add(foto)
        db.session.commit()
        db.session.refresh(rdo)

        antes = calcular_hash(rdo)
        assert payload_canonico(rdo)['fotos'] == \
            [[foto.id, 'p3.jpg', 'Painel P3 montado']]

        foto.imagem_otimizada_base64 = None
        foto.arquivo_otimizado = 'uploads/rdo/x/p3.webp'
        db.session.commit()
        db.session.refresh(rdo)
        assert calcular_hash(rdo) == antes, (
            'mover a foto de base64 para disco invalidou a assinatura — o '
            'hash está cobrindo bytes de armazenamento')


def test_verificar_integridade_detecta_adulteracao():
    from models import RDOAssinatura
    from services.rdo_hash import calcular_hash, verificar_integridade

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        rdo = _rdo(obra, admin.id)
        a = RDOAssinatura(
            rdo_id=rdo.id, admin_id=admin.id, usuario_id=op.id,
            funcionario_id=func.id, papel='executor',
            nome_signatario=op.nome, hash_conteudo=calcular_hash(rdo),
            algoritmo='sha256', provedor='interno')
        db.session.add(a)
        db.session.commit()

        assert verificar_integridade(a) is True

        # Adulteração por fora do ORM: UPDATE direto no banco, que é
        # exatamente o cenário contra o qual o hash existe.
        from sqlalchemy import text
        db.session.execute(
            text("UPDATE rdo SET comentario_geral = :c WHERE id = :i"),
            {'c': 'texto trocado no banco', 'i': rdo.id})
        db.session.commit()
        db.session.expire_all()

        assert verificar_integridade(a) is False
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase5_rdo_assinatura.py -v -k "hash or integridade"
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'services.rdo_hash'`.

- [ ] **Step 3: Implemente o hash**

Crie `services/rdo_hash.py`:

```python
#!/usr/bin/env python3
"""Hash canônico do RDO — SIGE Fase 5.

Serve à parte "integridade" da assinatura: um SHA-256 sobre uma
representação DETERMINÍSTICA do conteúdo declarado do RDO. Se alguém
mexer no documento depois de assinado — inclusive por UPDATE direto no
banco, driblando a guarda `before_flush` — a verificação acusa.

O que ENTRA no payload: os campos que a pessoa declarou (clima, comentário,
subatividades e percentuais, equipe e horas, equipamentos, ocorrências,
apontamentos de cronograma) mais a IDENTIDADE das fotos.

O que NÃO entra, e por quê:

  * **Os bytes das fotos.** A Task 15 do plano migra `rdo_foto` de três
    cópias base64 no banco (16 GB medidos) para arquivo em disco. Se o
    hash cobrisse bytes, toda assinatura anterior viraria "adulterada"
    por uma mudança que não tocou em nada que a pessoa declarou. Entram
    `(id, nome_original, descricao)` — identidade e legenda.
  * **`updated_at`, `created_at`, `status`, `estado`.** São metadados do
    sistema; o estado muda por transição legítima depois da assinatura
    (assinado → aprovado) e não pode invalidar nada.
  * **Campos derivados** (`quantidade_acumulada`, `percentual_realizado`
    consolidado). São recalculados pelo `recomputar_cadeia`
    (services/cronograma_apontamento_service.py:92) quando um RDO
    ANTERIOR é corrigido — não é adulteração deste documento.

Formato: JSON com `sort_keys=True`, `ensure_ascii=False`,
`separators=(',', ':')`, UTF-8. Números normalizados com
`round(float(x), 4)` para que 8.0 e 8 gerem o mesmo hash. Coleções
ordenadas por chave estável, nunca pela ordem de inserção.
"""
from __future__ import annotations

import hashlib
import json
import logging

logger = logging.getLogger('rdo.hash')

VERSAO_PAYLOAD = 1  # muda se o conjunto de campos mudar; vai dentro do hash


def _num(valor):
    """Normaliza número para o payload. None continua None."""
    if valor is None:
        return None
    try:
        return round(float(valor), 4)
    except (TypeError, ValueError):
        return None


def _txt(valor):
    """Normaliza texto: None e '' são a mesma coisa (None)."""
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None


def payload_canonico(rdo) -> dict:
    """Representação determinística do conteúdo declarado do RDO."""
    from models import (RDOApontamentoCronograma, RDOEquipamento, RDOFoto,
                        RDOMaoObra, RDOOcorrencia, RDOServicoSubatividade)

    cabecalho = {
        'versao': VERSAO_PAYLOAD,
        'rdo_id': rdo.id,
        'numero_rdo': _txt(rdo.numero_rdo),
        'obra_id': rdo.obra_id,
        'data_relatorio': (rdo.data_relatorio.isoformat()
                           if rdo.data_relatorio else None),
        'local': _txt(rdo.local),
        'clima_geral': _txt(rdo.clima_geral),
        'temperatura_media': _txt(rdo.temperatura_media),
        'umidade_relativa': _num(rdo.umidade_relativa),
        'vento_velocidade': _txt(rdo.vento_velocidade),
        'precipitacao': _txt(rdo.precipitacao),
        'condicoes_trabalho': _txt(rdo.condicoes_trabalho),
        'observacoes_climaticas': _txt(rdo.observacoes_climaticas),
        'comentario_geral': _txt(rdo.comentario_geral),
        'criado_por_id': rdo.criado_por_id,
    }

    subs = sorted(
        ([_txt(s.nome_subatividade), s.servico_id,
          _num(s.percentual_conclusao), _num(s.quantidade_produzida),
          _txt(s.observacoes_tecnicas)]
         for s in RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id).all()),
        key=lambda linha: (str(linha[0] or ''), linha[1] or 0))

    mao_obra = sorted(
        ([m.funcionario_id, _txt(m.funcao_exercida),
          _num(m.horas_trabalhadas), m.subatividade_id,
          m.tarefa_cronograma_id]
         for m in RDOMaoObra.query.filter_by(rdo_id=rdo.id).all()),
        key=lambda linha: (linha[0] or 0, str(linha[1] or ''),
                           linha[2] or 0.0, linha[3] or 0, linha[4] or 0))

    equipamentos = sorted(
        ([_txt(e.nome_equipamento), _num(e.quantidade), _num(e.horas_uso),
          _txt(e.estado_conservacao)]
         for e in RDOEquipamento.query.filter_by(rdo_id=rdo.id).all()),
        key=lambda linha: (str(linha[0] or ''), linha[1] or 0.0))

    ocorrencias = sorted(
        ([_txt(o.tipo_ocorrencia), _txt(o.severidade),
          _txt(o.descricao_ocorrencia), _txt(o.acoes_corretivas)]
         for o in RDOOcorrencia.query.filter_by(rdo_id=rdo.id).all()),
        key=lambda linha: (str(linha[0] or ''), str(linha[2] or '')))

    # Só o que a pessoa DIGITOU no dia. `quantidade_acumulada` e
    # `percentual_realizado` são derivados e podem ser recalculados pelo
    # recomputo em cadeia de um RDO anterior.
    apontamentos = sorted(
        ([a.tarefa_cronograma_id, _txt(getattr(a, 'tipo_apontamento', None)),
          _num(a.quantidade_executada_dia),
          _num(getattr(a, 'percentual_acumulado', None))]
         for a in RDOApontamentoCronograma.query.filter_by(rdo_id=rdo.id).all()),
        key=lambda linha: (linha[0] or 0,))

    fotos = sorted(
        ([f.id, _txt(f.nome_original) or _txt(f.nome_arquivo),
          _txt(f.descricao) or _txt(f.legenda)]
         for f in RDOFoto.query.filter_by(rdo_id=rdo.id).all()),
        key=lambda linha: linha[0])

    return {
        **cabecalho,
        'subatividades': subs,
        'mao_obra': mao_obra,
        'equipamentos': equipamentos,
        'ocorrencias': ocorrencias,
        'apontamentos': apontamentos,
        'fotos': fotos,
    }


def serializar(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), default=str)


def calcular_hash(rdo) -> str:
    """SHA-256 hexdigest (64 chars) do payload canônico do RDO."""
    texto = serializar(payload_canonico(rdo))
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()


def verificar_integridade(assinatura) -> bool:
    """True se o RDO continua batendo com o hash gravado na assinatura.

    Falha FECHADA: qualquer erro devolve False e loga. Uma verificação
    que não conseguiu rodar não é uma verificação bem-sucedida.
    """
    try:
        if assinatura is None or assinatura.rdo is None:
            return False
        if (assinatura.algoritmo or 'sha256') != 'sha256':
            logger.warning('[rdo-hash] algoritmo desconhecido %r na '
                           'assinatura %s', assinatura.algoritmo,
                           assinatura.id)
            return False
        return calcular_hash(assinatura.rdo) == assinatura.hash_conteudo
    except Exception:
        logger.exception('[rdo-hash] falha ao verificar assinatura %s',
                         getattr(assinatura, 'id', None))
        return False
```

- [ ] **Step 4: Rode os testes**

```bash
python -m pytest tests/test_fase5_rdo_assinatura.py -v
```

Esperado: os 10 testes do arquivo PASSAM.

- [ ] **Step 5: Commit**

```bash
git add services/rdo_hash.py tests/test_fase5_rdo_assinatura.py
git commit -m "feat(fase5): hash canonico do RDO

SHA-256 sobre JSON determinista do conteudo DECLARADO. Nao inclui bytes
de foto de proposito: a Task 15 migra rdo_foto de base64 para disco e
isso nao pode invalidar assinatura nenhuma. Nao inclui derivados
(quantidade_acumulada) porque recomputar_cadeia os reescreve
legitimamente quando um RDO anterior e corrigido."
```

---

## Task 7: Rota de assinatura (`POST /rdo/<id>/assinar`)

**Files:**
- Create: `services/rdo_assinatura.py`
- Modify: `views/rdo.py` (rota nova após `finalizar_rdo`, linha 1594)
- Test: `tests/test_fase5_rdo_assinatura.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente ao final de `tests/test_fase5_rdo_assinatura.py`:

```python
# ---------------------------------------------------------------------------
# Rota de assinatura
# ---------------------------------------------------------------------------

def _preencher(rdo, usuario):
    from services.rdo_ciclo_vida import PREENCHIDO, transicionar
    transicionar(rdo, PREENCHIDO, usuario=usuario)
    db.session.commit()


def test_apontador_assina_e_o_rdo_fica_assinado():
    from models import RDOAssinatura
    from services.rdo_ciclo_vida import ASSINADO

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        _vincular(op, obra, PapelObra.APONTADOR)
        rdo = _rdo(obra, admin.id, criado_por_id=op.id)
        _preencher(rdo, op)
        rid, opid, fid = rdo.id, op.id, func.id

    cliente = _cliente_de(opid)
    resposta = cliente.post(f'/rdo/{rid}/assinar',
                            data={'observacao': 'conferido em campo'},
                            follow_redirects=False)
    assert resposta.status_code in (200, 302)

    with app.app_context():
        rdo = db.session.get(RDO, rid)
        assert rdo.estado == ASSINADO
        assinaturas = RDOAssinatura.query.filter_by(rdo_id=rid).all()
        assert len(assinaturas) == 1
        a = assinaturas[0]
        assert a.papel == RDOAssinatura.PAPEL_EXECUTOR
        assert a.funcionario_id == fid, (
            'a assinatura não ficou ancorada na identidade real da Fase 1')
        assert a.usuario_id == opid
        assert len(a.hash_conteudo) == 64
        assert a.provedor == 'interno'
        assert a.assinado_em is not None


def test_assinatura_grava_ip_e_user_agent():
    from models import RDOAssinatura

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        _vincular(op, obra, PapelObra.APONTADOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, op)
        rid, opid = rdo.id, op.id

    cliente = _cliente_de(opid)
    cliente.post(f'/rdo/{rid}/assinar',
                 headers={'X-Forwarded-For': '203.0.113.42',
                          'User-Agent': 'SIGE-Teste/9.0'})

    with app.app_context():
        a = RDOAssinatura.query.filter_by(rdo_id=rid).first()
        assert a is not None
        assert a.ip == '203.0.113.42', (
            f'IP gravado foi {a.ip!r} — ProxyFix(x_for=1) está em app.py:94')
        assert a.user_agent == 'SIGE-Teste/9.0'


def test_hash_gravado_confere_com_o_conteudo():
    from models import RDOAssinatura
    from services.rdo_hash import verificar_integridade

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        _vincular(op, obra, PapelObra.APONTADOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, op)
        rid, opid = rdo.id, op.id

    _cliente_de(opid).post(f'/rdo/{rid}/assinar')

    with app.app_context():
        a = RDOAssinatura.query.filter_by(rdo_id=rid).first()
        assert verificar_integridade(a) is True


def test_leitor_nao_assina():
    from models import RDOAssinatura
    from services.rdo_ciclo_vida import PREENCHIDO

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        _vincular(op, obra, PapelObra.LEITOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, op)
        rid, opid = rdo.id, op.id

    resposta = _cliente_de(opid).post(f'/rdo/{rid}/assinar',
                                      follow_redirects=False)
    assert resposta.status_code in (302, 403, 404)

    with app.app_context():
        assert RDOAssinatura.query.filter_by(rdo_id=rid).count() == 0
        assert db.session.get(RDO, rid).estado == PREENCHIDO


def test_anonimo_nao_assina():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, admin)
        rid = rdo.id

    resposta = app.test_client().post(f'/rdo/{rid}/assinar',
                                      follow_redirects=False)
    assert resposta.status_code in (302, 401), (
        f'/rdo/{rid}/assinar devolveu {resposta.status_code} para anônimo')


def test_nao_assina_rdo_em_rascunho():
    from models import RDOAssinatura
    from services.rdo_ciclo_vida import RASCUNHO

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        _vincular(op, obra, PapelObra.APONTADOR)
        rdo = _rdo(obra, admin.id)  # continua rascunho
        rid, opid = rdo.id, op.id

    _cliente_de(opid).post(f'/rdo/{rid}/assinar')

    with app.app_context():
        assert db.session.get(RDO, rid).estado == RASCUNHO
        assert RDOAssinatura.query.filter_by(rdo_id=rid).count() == 0


def test_usuario_sem_vinculo_de_funcionario_nao_assina():
    """Sem identidade real (Fase 1), não há autoria a registrar."""
    from models import RDOAssinatura

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        suf = _sfx()
        sem_vinculo = Usuario(
            username=f'f5n_{suf}', email=f'f5n_{suf}@test.local',
            nome='Sem vinculo', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin.id,
        )
        db.session.add(sem_vinculo)
        db.session.commit()
        _vincular(sem_vinculo, obra, PapelObra.APONTADOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, admin)
        rid, uid = rdo.id, sem_vinculo.id

    _cliente_de(uid).post(f'/rdo/{rid}/assinar')

    with app.app_context():
        assert RDOAssinatura.query.filter_by(rdo_id=rid).count() == 0, (
            'assinou sem identidade — voltamos a adivinhar quem é a pessoa')


def test_rdo_assinado_nao_aceita_mais_edicao_pela_rota():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        _vincular(op, obra, PapelObra.APONTADOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, op)
        rid, oid, opid, aid = rdo.id, obra.id, op.id, admin.id

    _cliente_de(opid).post(f'/rdo/{rid}/assinar')

    _cliente_de(aid).post('/salvar-rdo-flexivel', data={
        'rdo_id': str(rid), 'obra_id': str(oid),
        'data_relatorio': '2026-06-22',
        'comentario_geral': 'reescrita pós-assinatura',
    }, follow_redirects=True)

    with app.app_context():
        assert db.session.get(RDO, rid).comentario_geral == \
            'Montagem dos perfis de aço do painel P3.'
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase5_rdo_assinatura.py -v -k "assina or assinatura_grava or hash_gravado"
```

Esperado: FAIL — `/rdo/<id>/assinar` devolve 404 (rota inexistente).

- [ ] **Step 3: Implemente o serviço de assinatura**

Crie `services/rdo_assinatura.py`:

```python
#!/usr/bin/env python3
"""Assinatura e aprovação de RDO — SIGE Fase 5.

Concentra as três operações que mudam o estado terminal do RDO:
`assinar`, `aprovar` e `criar_retificador`. A AUTORIZAÇÃO fica na rota
(utils/autorizacao.py, Fase 1); aqui mora a regra de negócio e a
gravação da evidência.

Identidade: SEMPRE por `utils.identidade.funcionario_do_usuario()`. Antes
da Fase 1 este módulo teria que adivinhar quem é a pessoa — por e-mail
sem `admin_id`, por substring de nome, e no último fallback CRIANDO um
`Funcionario` chamado "Administrador Sistema" (views/rdo.py:2698-2708).
Assinatura em cima de palpite não é assinatura; por isso, sem vínculo,
este módulo se recusa a assinar.
"""
from __future__ import annotations

import logging

from models import RDOAssinatura, db
from services.rdo_ciclo_vida import (APROVADO, ASSINADO, CicloVidaInvalido,
                                     PREENCHIDO, estado_de, transicionar)
from services.rdo_hash import calcular_hash

logger = logging.getLogger('rdo.assinatura')


class AssinaturaInvalida(CicloVidaInvalido):
    """Mensagem apta à UI para recusa de assinatura."""


class SemIdentidade(AssinaturaInvalida):
    """Usuário sem `Usuario.funcionario_id` — não há autoria a registrar."""


def _contexto_request():
    """(ip, user_agent) do request atual, ou (None, None) fora de request."""
    try:
        from flask import request
        return (request.remote_addr,
                (request.headers.get('User-Agent') or '')[:400] or None)
    except Exception:
        return None, None


def assinar(rdo, usuario, *, papel=RDOAssinatura.PAPEL_EXECUTOR,
            observacao=None):
    """Registra a assinatura e leva o RDO de `preenchido` a `assinado`.

    Não faz commit — quem chama decide a transação. Levanta
    `AssinaturaInvalida` (ou subclasse) em qualquer recusa.
    """
    from utils.identidade import funcionario_do_usuario

    if papel not in RDOAssinatura.PAPEIS:
        raise AssinaturaInvalida(f'Papel de assinatura inválido: {papel!r}')

    atual = estado_de(rdo)
    if atual != PREENCHIDO:
        raise AssinaturaInvalida(
            f'Só um RDO preenchido pode ser assinado — este está em '
            f'"{atual}". Submeta o RDO antes de assinar.')

    funcionario = funcionario_do_usuario(usuario)
    if funcionario is None:
        raise SemIdentidade(
            'Seu login não está vinculado a um cadastro de funcionário. '
            'Sem esse vínculo não é possível registrar a autoria da '
            'assinatura. Peça ao administrador para vincular seu usuário '
            '(Fase 1 — utils/identidade.py).')

    if RDOAssinatura.query.filter_by(rdo_id=rdo.id, papel=papel).first():
        raise AssinaturaInvalida(
            f'Este RDO já tem assinatura de {papel}. Para corrigir, emita '
            f'um RDO retificador.')

    ip, user_agent = _contexto_request()
    cargo = None
    funcao_ref = getattr(funcionario, 'funcao_ref', None)
    if funcao_ref is not None:
        cargo = getattr(funcao_ref, 'nome', None)
    cargo = cargo or getattr(funcionario, 'cargo', None)

    assinatura = RDOAssinatura(
        rdo_id=rdo.id,
        admin_id=rdo.admin_id or rdo.obra.admin_id,
        usuario_id=usuario.id,
        funcionario_id=funcionario.id,
        papel=papel,
        nome_signatario=(funcionario.nome or usuario.nome or
                         usuario.username)[:200],
        cargo_signatario=(cargo or '')[:120] or None,
        hash_conteudo=calcular_hash(rdo),
        algoritmo='sha256',
        provedor='interno',
        ip=ip,
        user_agent=user_agent,
        observacao=observacao,
    )
    db.session.add(assinatura)
    db.session.flush()

    transicionar(rdo, ASSINADO, usuario=usuario, funcionario=funcionario,
                 motivo=observacao, ip=ip,
                 detalhes={'assinatura_id': assinatura.id, 'papel': papel})

    logger.info('[assinatura] rdo=%s papel=%s usuario=%s funcionario=%s '
                'hash=%s ip=%s', rdo.id, papel, usuario.id, funcionario.id,
                assinatura.hash_conteudo[:12], ip)
    return assinatura


def aprovar(rdo, usuario, *, observacao=None):
    """Aceite do gestor: `assinado` → `aprovado` + assinatura de gestor.

    Não faz commit.
    """
    from utils.identidade import funcionario_do_usuario

    atual = estado_de(rdo)
    if atual != ASSINADO:
        raise AssinaturaInvalida(
            f'Só um RDO assinado pode ser aprovado — este está em '
            f'"{atual}".')

    funcionario = funcionario_do_usuario(usuario)
    ip, user_agent = _contexto_request()

    ja_existe = RDOAssinatura.query.filter_by(
        rdo_id=rdo.id, papel=RDOAssinatura.PAPEL_GESTOR).first()
    assinatura = ja_existe
    if ja_existe is None:
        assinatura = RDOAssinatura(
            rdo_id=rdo.id,
            admin_id=rdo.admin_id or rdo.obra.admin_id,
            usuario_id=usuario.id,
            funcionario_id=getattr(funcionario, 'id', None),
            papel=RDOAssinatura.PAPEL_GESTOR,
            nome_signatario=(getattr(funcionario, 'nome', None) or
                             usuario.nome or usuario.username)[:200],
            cargo_signatario='Gestor da obra',
            hash_conteudo=calcular_hash(rdo),
            algoritmo='sha256',
            provedor='interno',
            ip=ip,
            user_agent=user_agent,
            observacao=observacao,
        )
        db.session.add(assinatura)
        db.session.flush()

    transicionar(rdo, APROVADO, usuario=usuario, funcionario=funcionario,
                 motivo=observacao, ip=ip,
                 detalhes={'assinatura_id': assinatura.id,
                           'papel': RDOAssinatura.PAPEL_GESTOR})

    logger.info('[assinatura] rdo=%s APROVADO por usuario=%s ip=%s',
                rdo.id, usuario.id, ip)
    return assinatura
```

- [ ] **Step 4: Implemente a rota**

Em `views/rdo.py`, imediatamente após o fim de `finalizar_rdo` (linha 1594, antes do `@main_bp.route('/rdo/<int:id>/duplicar', ...)` da linha 1596), insira:

```python
# ── Fase 5 — ciclo de vida e assinatura ──────────────────────────────
def _rdo_do_tenant_ou_404(rdo_id):
    """RDO do tenant do usuário logado, ou 404.

    404 e não 403 de propósito: não vazar sequer a existência de RDO de
    outra empresa. Mesma escolha travada em
    tests/test_cronograma_permissoes.py.
    """
    from flask import abort

    from utils.tenant import get_tenant_admin_id
    tenant = get_tenant_admin_id()
    if tenant is None:
        abort(404)
    rdo = RDO.query.join(Obra).filter(
        RDO.id == rdo_id, Obra.admin_id == tenant).first()
    if rdo is None:
        abort(404)
    return rdo


@main_bp.route('/rdo/<int:id>/assinar', methods=['POST'])
@login_required
def assinar_rdo(id):
    """Assina o RDO (papel 'executor') e o torna imutável.

    Autorização: `pode_apontar_na_obra` (Fase 1) — GESTOR ou APONTADOR da
    obra. LEITOR não assina.
    """
    from services.rdo_assinatura import assinar
    from services.rdo_ciclo_vida import CicloVidaInvalido
    from utils.autorizacao import pode_apontar_na_obra

    rdo = _rdo_do_tenant_ou_404(id)

    if not pode_apontar_na_obra(rdo.obra_id):
        flash('Você não tem permissão para assinar RDO nesta obra.', 'error')
        return redirect(url_for('main.visualizar_rdo', id=id))

    try:
        assinatura = assinar(
            rdo, current_user,
            observacao=(request.form.get('observacao') or '').strip() or None)
        db.session.commit()
        flash(f'RDO {rdo.numero_rdo} assinado por '
              f'{assinatura.nome_signatario}. O documento não aceita mais '
              f'edição — para corrigir, emita um RDO retificador.', 'success')
    except CicloVidaInvalido as e:
        db.session.rollback()
        flash(str(e), 'error')
    except Exception as e:
        db.session.rollback()
        logger.error(f"ERRO ASSINAR RDO {id}: {e}", exc_info=True)
        flash('Erro ao assinar o RDO.', 'error')

    return redirect(url_for('main.visualizar_rdo', id=id))
```

- [ ] **Step 5: Rode os testes**

```bash
python -m pytest tests/test_fase5_rdo_assinatura.py -v
```

Esperado: os 18 testes do arquivo PASSAM.

- [ ] **Step 6: Commit**

```bash
git add services/rdo_assinatura.py views/rdo.py tests/test_fase5_rdo_assinatura.py
git commit -m "feat(fase5): rota POST /rdo/<id>/assinar

Autorizacao por pode_apontar_na_obra (Fase 1) e identidade por
funcionario_do_usuario — sem vinculo, recusa assinar. Grava hash SHA-256,
carimbo de tempo do servidor, IP real e user-agent, e transiciona para
assinado, que e imutavel."
```

---

## Task 8: Rota de aprovação (`POST /rdo/<id>/aprovar`) e reabertura

**Files:**
- Modify: `views/rdo.py` (duas rotas novas após `assinar_rdo`)
- Test: `tests/test_fase5_rdo_assinatura.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente ao final de `tests/test_fase5_rdo_assinatura.py`:

```python
# ---------------------------------------------------------------------------
# Aprovação e reabertura
# ---------------------------------------------------------------------------

def _assinar_pela_rota(rdo_id, usuario_id):
    _cliente_de(usuario_id).post(f'/rdo/{rdo_id}/assinar')


def test_gestor_aprova_rdo_assinado():
    from models import RDOAssinatura
    from services.rdo_ciclo_vida import APROVADO

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        f_ap, f_ge = _funcionario(admin.id, 'Ap'), _funcionario(admin.id, 'Ge')
        ap, ge = _operador(admin.id, f_ap), _operador(admin.id, f_ge, 'Gestor')
        _vincular(ap, obra, PapelObra.APONTADOR)
        _vincular(ge, obra, PapelObra.GESTOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, ap)
        rid, apid, geid = rdo.id, ap.id, ge.id

    _assinar_pela_rota(rid, apid)
    resposta = _cliente_de(geid).post(f'/rdo/{rid}/aprovar',
                                      follow_redirects=False)
    assert resposta.status_code in (200, 302)

    with app.app_context():
        assert db.session.get(RDO, rid).estado == APROVADO
        papeis = {a.papel for a in RDOAssinatura.query.filter_by(rdo_id=rid)}
        assert papeis == {RDOAssinatura.PAPEL_EXECUTOR,
                          RDOAssinatura.PAPEL_GESTOR}


def test_apontador_nao_aprova():
    from services.rdo_ciclo_vida import ASSINADO

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        ap = _operador(admin.id, func)
        _vincular(ap, obra, PapelObra.APONTADOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, ap)
        rid, apid = rdo.id, ap.id

    _assinar_pela_rota(rid, apid)
    _cliente_de(apid).post(f'/rdo/{rid}/aprovar')

    with app.app_context():
        assert db.session.get(RDO, rid).estado == ASSINADO, (
            'APONTADOR aprovou o próprio RDO — aprovação é do GESTOR')


def test_nao_aprova_rdo_apenas_preenchido():
    from services.rdo_ciclo_vida import PREENCHIDO

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id, 'Ge')
        ge = _operador(admin.id, func, 'Gestor')
        _vincular(ge, obra, PapelObra.GESTOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, ge)
        rid, geid = rdo.id, ge.id

    _cliente_de(geid).post(f'/rdo/{rid}/aprovar')

    with app.app_context():
        assert db.session.get(RDO, rid).estado == PREENCHIDO


def test_gestor_reabre_rdo_preenchido():
    from models import RDOTransicaoEstado
    from services.rdo_ciclo_vida import RASCUNHO

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id, 'Ge')
        ge = _operador(admin.id, func, 'Gestor')
        _vincular(ge, obra, PapelObra.GESTOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, ge)
        rid, geid = rdo.id, ge.id

    _cliente_de(geid).post(f'/rdo/{rid}/reabrir',
                           data={'motivo': 'horas lançadas erradas'})

    with app.app_context():
        assert db.session.get(RDO, rid).estado == RASCUNHO
        ultima = (RDOTransicaoEstado.query.filter_by(rdo_id=rid)
                  .order_by(RDOTransicaoEstado.id.desc()).first())
        assert ultima.estado_novo == RASCUNHO
        assert ultima.motivo == 'horas lançadas erradas'


def test_apontador_nao_reabre():
    from services.rdo_ciclo_vida import PREENCHIDO

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        ap = _operador(admin.id, func)
        _vincular(ap, obra, PapelObra.APONTADOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, ap)
        rid, apid = rdo.id, ap.id

    _cliente_de(apid).post(f'/rdo/{rid}/reabrir', data={'motivo': 'quero'})

    with app.app_context():
        assert db.session.get(RDO, rid).estado == PREENCHIDO


def test_nao_reabre_rdo_assinado():
    from services.rdo_ciclo_vida import ASSINADO

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        f_ap, f_ge = _funcionario(admin.id, 'Ap'), _funcionario(admin.id, 'Ge')
        ap, ge = _operador(admin.id, f_ap), _operador(admin.id, f_ge, 'Gestor')
        _vincular(ap, obra, PapelObra.APONTADOR)
        _vincular(ge, obra, PapelObra.GESTOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, ap)
        rid, apid, geid = rdo.id, ap.id, ge.id

    _assinar_pela_rota(rid, apid)
    _cliente_de(geid).post(f'/rdo/{rid}/reabrir', data={'motivo': 'errei'})

    with app.app_context():
        assert db.session.get(RDO, rid).estado == ASSINADO, (
            'RDO assinado foi reaberto — imutabilidade furada')


def test_finalizar_rdo_leva_de_rascunho_para_preenchido():
    """`finalizar_rdo` (views/rdo.py:1520) é a rota de SUBMISSÃO.

    Ela já gravava `status='Finalizado'` (linha 1539) e emitia
    `rdo_finalizado` + `obra.rdo_publicado` (linhas 1570 e 1583). O que
    faltava era mover o `estado` — sem isso o RDO nunca sai de rascunho
    e nunca pode ser assinado.
    """
    from services.rdo_ciclo_vida import PREENCHIDO, RASCUNHO

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        ap = _operador(admin.id, func)
        _vincular(ap, obra, PapelObra.APONTADOR)
        rdo = _rdo(obra, admin.id, criado_por_id=ap.id)
        assert rdo.estado == RASCUNHO
        rid, aid = rdo.id, admin.id

    _cliente_de(aid).post(f'/rdo/{rid}/finalizar', follow_redirects=True)

    with app.app_context():
        recarregado = db.session.get(RDO, rid)
        assert recarregado.estado == PREENCHIDO
        assert recarregado.status == 'Finalizado', (
            'o status legado tem que continuar Finalizado — nove '
            'consumidores filtram por ele')


def test_finalizar_rdo_ja_preenchido_e_no_op():
    """Reenvio de formulário não pode duplicar trilha nem quebrar."""
    from models import RDOTransicaoEstado
    from services.rdo_ciclo_vida import PREENCHIDO

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        rid, aid = rdo.id, admin.id

    cliente = _cliente_de(aid)
    cliente.post(f'/rdo/{rid}/finalizar', follow_redirects=True)
    cliente.post(f'/rdo/{rid}/finalizar', follow_redirects=True)

    with app.app_context():
        assert db.session.get(RDO, rid).estado == PREENCHIDO
        transicoes = RDOTransicaoEstado.query.filter_by(
            rdo_id=rid, estado_novo=PREENCHIDO).count()
        assert transicoes == 1, (
            f'{transicoes} transições para preenchido — o no-op de '
            f'`transicionar` não está funcionando')
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase5_rdo_assinatura.py -v -k "aprova or reabre or finalizar"
```

Esperado: FAIL — `/rdo/<id>/aprovar` e `/rdo/<id>/reabrir` devolvem 404, e `finalizar_rdo` deixa o RDO em `rascunho`.

- [ ] **Step 3: Implemente as rotas**

Em `views/rdo.py`, imediatamente após o fim de `assinar_rdo` (criada na Task 7), insira:

```python
@main_bp.route('/rdo/<int:id>/aprovar', methods=['POST'])
@login_required
def aprovar_rdo(id):
    """Aceite do gestor da obra: `assinado` → `aprovado`.

    Autorização: `pode_editar_obra` (Fase 1) — só o GESTOR da obra e o
    ADMIN do tenant. APONTADOR assina o que executou; não homologa.
    """
    from services.rdo_assinatura import aprovar
    from services.rdo_ciclo_vida import CicloVidaInvalido
    from utils.autorizacao import pode_editar_obra

    rdo = _rdo_do_tenant_ou_404(id)

    if not pode_editar_obra(rdo.obra_id):
        flash('Só o gestor da obra pode aprovar o RDO.', 'error')
        return redirect(url_for('main.visualizar_rdo', id=id))

    try:
        aprovar(rdo, current_user,
                observacao=(request.form.get('observacao') or '').strip() or None)
        db.session.commit()
        flash(f'RDO {rdo.numero_rdo} aprovado.', 'success')
    except CicloVidaInvalido as e:
        db.session.rollback()
        flash(str(e), 'error')
    except Exception as e:
        db.session.rollback()
        logger.error(f"ERRO APROVAR RDO {id}: {e}", exc_info=True)
        flash('Erro ao aprovar o RDO.', 'error')

    return redirect(url_for('main.visualizar_rdo', id=id))


@main_bp.route('/rdo/<int:id>/reabrir', methods=['POST'])
@login_required
def reabrir_rdo(id):
    """Devolve o RDO de `preenchido` para `rascunho`, com motivo.

    Só existe enquanto o RDO NÃO foi assinado — a máquina de estados
    (services/rdo_ciclo_vida.TRANSICOES_VALIDAS) não tem aresta saindo de
    `assinado` para trás, então mesmo que a autorização passe, a
    transição é recusada.
    """
    from services.rdo_ciclo_vida import (CicloVidaInvalido, RASCUNHO,
                                         transicionar)
    from utils.autorizacao import pode_editar_obra

    rdo = _rdo_do_tenant_ou_404(id)

    if not pode_editar_obra(rdo.obra_id):
        flash('Só o gestor da obra pode reabrir um RDO.', 'error')
        return redirect(url_for('main.visualizar_rdo', id=id))

    motivo = (request.form.get('motivo') or '').strip()
    if not motivo:
        flash('Informe o motivo da reabertura.', 'error')
        return redirect(url_for('main.visualizar_rdo', id=id))

    try:
        transicionar(rdo, RASCUNHO, usuario=current_user, motivo=motivo,
                     ip=request.remote_addr)
        db.session.commit()
        flash(f'RDO {rdo.numero_rdo} reaberto para edição.', 'success')
    except CicloVidaInvalido as e:
        db.session.rollback()
        flash(str(e), 'error')
    except Exception as e:
        db.session.rollback()
        logger.error(f"ERRO REABRIR RDO {id}: {e}", exc_info=True)
        flash('Erro ao reabrir o RDO.', 'error')

    return redirect(url_for('main.visualizar_rdo', id=id))
```

- [ ] **Step 4: Ligue `finalizar_rdo` à máquina de estados**

`finalizar_rdo` (`views/rdo.py:1520`) é a rota de **submissão**: ela já
emite os dois eventos (`rdo_finalizado` na linha 1570 e
`obra.rdo_publicado` na 1583). Faltam três coisas:

1. **Mover o `estado`.** Sem isso o RDO nunca sai de `rascunho` e nunca
   pode ser assinado.
2. **Trocar `@admin_required` por `@login_required` + `pode_apontar_na_obra`.**
   `auth.py:29` recusa `TipoUsuario.FUNCIONARIO` — ou seja, hoje o
   APONTADOR **não consegue submeter o próprio RDO**, e o botão
   "Submeter" da Task 12 apontaria para uma rota que o rejeita.
3. **Consertar o guard morto da linha 1533.** Ele testa
   `if rdo.status == 'Finalizado'` — e `models.py:860` faz TODO RDO
   nascer com esse valor. Na prática a rota inteira sempre caía no
   `return` com "RDO já está finalizado". Esta é a segunda rota morta do
   módulo, ao lado do `duplicar_rdo` (bug 6d, Task 10). O guard passa a
   olhar o `estado`, que é onde o ciclo de vida realmente mora.

Em `views/rdo.py`, substitua o bloco das linhas 1520-1539 (do decorator
até `rdo.status = 'Finalizado'`, inclusive) por:

```python
@main_bp.route('/rdo/<int:id>/finalizar', methods=['POST'])
@login_required   # Fase 5 — era @admin_required, que recusa FUNCIONARIO
                  # (auth.py:29). O APONTADOR não conseguia submeter o
                  # próprio RDO. A autorização fina é por obra, abaixo.
def finalizar_rdo(id):
    """Submeter o RDO: `rascunho` → `preenchido`.

    Publica o dia: lança os custos de mão de obra (via
    `rdo_finalizado` → `event_manager.lancar_custos_rdo`), recalcula a
    medição e notifica pelo webhook `obra.rdo_publicado`.
    """
    from services.rdo_ciclo_vida import (CicloVidaInvalido, PREENCHIDO,
                                         RASCUNHO, estado_de, transicionar)
    from utils.autorizacao import pode_apontar_na_obra

    try:
        rdo = _rdo_do_tenant_ou_404(id)
        admin_id = rdo.admin_id or rdo.obra.admin_id

        if not pode_apontar_na_obra(rdo.obra_id):
            flash('Você não tem permissão para lançar RDO nesta obra.',
                  'error')
            return redirect(url_for('main.visualizar_rdo', id=id))

        # Fase 5 — o guard antigo era `if rdo.status == 'Finalizado'`, e
        # `models.py:860` faz TODO RDO nascer com esse valor: a rota
        # inteira sempre retornava aqui. Agora o guard é o estado real.
        if estado_de(rdo) != RASCUNHO:
            flash(f'RDO {rdo.numero_rdo} já foi submetido.', 'warning')
            return redirect(url_for('main.visualizar_rdo', id=id))

        # `status` continua 'Finalizado' — nove consumidores filtram por
        # ele (cronograma_views.py:2315,2345; portal_obras_views.py:187;
        # services/medicao_service.py:243; services/rdo_custos.py:330;
        # services/metricas_produtividade.py:186,972,1302,1320).
        rdo.status = 'Finalizado'
        transicionar(rdo, PREENCHIDO, usuario=current_user,
                     ip=request.remote_addr,
                     detalhes={'origem': 'finalizar_rdo'})
```

> O resto do corpo original da função — cálculo de produtividade,
> `db.session.commit()`, os dois `emit` e o `except` final — permanece
> **exatamente como está**. A única mudança adicional é que a linha
> `admin_id = current_user.id if ...` da linha 1525 sai (o `admin_id` já
> vem resolvido do RDO acima) e as linhas 1527-1531 (o `RDO.query.join(Obra)…first_or_404()`)
> também saem, substituídas pelo `_rdo_do_tenant_ou_404(id)`.
>
> Acrescente ainda, logo antes do `try:` do bloco `except CicloVidaInvalido`
> não existir na função original: envolva a chamada de `transicionar` no
> `try/except Exception` que já existe (linha 1590), que trata o
> `rollback` e o `flash` de erro. `CicloVidaInvalido` é subclasse de
> `ValueError`, então já é capturada por ele — a mensagem cai no flash
> genérico "Erro ao finalizar RDO", o que é aceitável para uma transição
> que a UI já impede.

- [ ] **Step 5: Rode os testes**

```bash
python -m pytest tests/test_fase5_rdo_assinatura.py -v
```

Esperado: os 26 testes do arquivo PASSAM.

- [ ] **Step 6: Commit**

```bash
git add views/rdo.py tests/test_fase5_rdo_assinatura.py
git commit -m "feat(fase5): rotas de aprovacao e reabertura do RDO + submissao

aprovar exige pode_editar_obra (GESTOR); reabrir exige motivo e so vale
antes da assinatura — a maquina de estados nao tem aresta saindo de
assinado para tras. finalizar_rdo passa a mover o estado para
'preenchido', que e o que destrava a assinatura; o status legado
continua 'Finalizado'."
```

---

## Task 9: RDO retificador (`rdo_retificado_id`) e migration 263

**Files:**
- Modify: `models.py` (dentro de `class RDO`, junto de `estado`)
- Modify: `migrations.py` (função nova + registro)
- Modify: `services/rdo_assinatura.py` (acrescenta `criar_retificador`)
- Modify: `views/rdo.py` (rota nova após `reabrir_rdo`)
- Test: `tests/test_fase5_rdo_assinatura.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente ao final de `tests/test_fase5_rdo_assinatura.py`:

```python
# ---------------------------------------------------------------------------
# RDO retificador
# ---------------------------------------------------------------------------

def test_retificar_cria_rdo_novo_e_marca_o_original():
    from services.rdo_ciclo_vida import RASCUNHO, RETIFICADO

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        f_ap, f_ge = _funcionario(admin.id, 'Ap'), _funcionario(admin.id, 'Ge')
        ap, ge = _operador(admin.id, f_ap), _operador(admin.id, f_ge, 'Gestor')
        _vincular(ap, obra, PapelObra.APONTADOR)
        _vincular(ge, obra, PapelObra.GESTOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, ap)
        rid, apid, geid, oid = rdo.id, ap.id, ge.id, obra.id

    _assinar_pela_rota(rid, apid)
    resposta = _cliente_de(geid).post(
        f'/rdo/{rid}/retificar',
        data={'motivo': 'horas do Márcio lançadas em dobro'},
        follow_redirects=False)
    assert resposta.status_code in (200, 302)

    with app.app_context():
        original = db.session.get(RDO, rid)
        assert original.estado == RETIFICADO

        novo = RDO.query.filter_by(rdo_retificado_id=rid).first()
        assert novo is not None, 'nenhum RDO retificador foi criado'
        assert novo.id != rid
        assert novo.estado == RASCUNHO
        assert novo.obra_id == oid
        assert novo.data_relatorio == original.data_relatorio, (
            'o retificador tem que ser do MESMO dia do original')
        assert novo.numero_rdo != original.numero_rdo


def test_retificador_copia_o_conteudo_do_original():
    from models import RDOMaoObra, RDOServicoSubatividade

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        f_ap, f_ge = _funcionario(admin.id, 'Ap'), _funcionario(admin.id, 'Ge')
        ap, ge = _operador(admin.id, f_ap), _operador(admin.id, f_ge, 'Gestor')
        _vincular(ap, obra, PapelObra.APONTADOR)
        _vincular(ge, obra, PapelObra.GESTOR)
        rdo = _rdo(obra, admin.id)
        db.session.add(RDOMaoObra(
            rdo_id=rdo.id, admin_id=admin.id, funcionario_id=f_ap.id,
            funcao_exercida='Montador', horas_trabalhadas=8.0))
        db.session.add(RDOServicoSubatividade(
            rdo_id=rdo.id, admin_id=admin.id,
            nome_subatividade='Montagem de painel', percentual_conclusao=40.0,
            ordem_execucao=1))
        db.session.commit()
        _preencher(rdo, ap)
        rid, apid, geid = rdo.id, ap.id, ge.id

    _assinar_pela_rota(rid, apid)
    _cliente_de(geid).post(f'/rdo/{rid}/retificar', data={'motivo': 'ajuste'})

    with app.app_context():
        novo = RDO.query.filter_by(rdo_retificado_id=rid).first()
        assert novo.comentario_geral == \
            'Montagem dos perfis de aço do painel P3.'
        assert RDOMaoObra.query.filter_by(rdo_id=novo.id).count() == 1
        assert RDOServicoSubatividade.query.filter_by(
            rdo_id=novo.id).count() == 1
        sub = RDOServicoSubatividade.query.filter_by(rdo_id=novo.id).first()
        assert sub.percentual_conclusao == 40.0


def test_original_retificado_continua_imutavel():
    from services.rdo_ciclo_vida import RDOImutavel

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        f_ap, f_ge = _funcionario(admin.id, 'Ap'), _funcionario(admin.id, 'Ge')
        ap, ge = _operador(admin.id, f_ap), _operador(admin.id, f_ge, 'Gestor')
        _vincular(ap, obra, PapelObra.APONTADOR)
        _vincular(ge, obra, PapelObra.GESTOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, ap)
        rid, apid, geid = rdo.id, ap.id, ge.id

    _assinar_pela_rota(rid, apid)
    _cliente_de(geid).post(f'/rdo/{rid}/retificar', data={'motivo': 'ajuste'})

    with app.app_context():
        original = db.session.get(RDO, rid)
        original.comentario_geral = 'mexendo no retificado'
        with pytest.raises(RDOImutavel):
            db.session.commit()
        db.session.rollback()


def test_retificar_exige_motivo():
    from services.rdo_ciclo_vida import ASSINADO

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        f_ap, f_ge = _funcionario(admin.id, 'Ap'), _funcionario(admin.id, 'Ge')
        ap, ge = _operador(admin.id, f_ap), _operador(admin.id, f_ge, 'Gestor')
        _vincular(ap, obra, PapelObra.APONTADOR)
        _vincular(ge, obra, PapelObra.GESTOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, ap)
        rid, apid, geid = rdo.id, ap.id, ge.id

    _assinar_pela_rota(rid, apid)
    _cliente_de(geid).post(f'/rdo/{rid}/retificar', data={'motivo': '  '})

    with app.app_context():
        assert db.session.get(RDO, rid).estado == ASSINADO
        assert RDO.query.filter_by(rdo_retificado_id=rid).count() == 0


def test_nao_retifica_rdo_em_rascunho():
    """RDO não assinado se corrige editando, não retificando."""
    from services.rdo_ciclo_vida import RASCUNHO

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id, 'Ge')
        ge = _operador(admin.id, func, 'Gestor')
        _vincular(ge, obra, PapelObra.GESTOR)
        rdo = _rdo(obra, admin.id)
        rid, geid = rdo.id, ge.id

    _cliente_de(geid).post(f'/rdo/{rid}/retificar', data={'motivo': 'x'})

    with app.app_context():
        assert db.session.get(RDO, rid).estado == RASCUNHO
        assert RDO.query.filter_by(rdo_retificado_id=rid).count() == 0
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase5_rdo_assinatura.py -v -k retific
```

Esperado: FAIL — `AttributeError: type object 'RDO' has no attribute 'rdo_retificado_id'` na coleção do primeiro teste.

- [ ] **Step 3: Adicione a coluna ao modelo**

Em `models.py`, dentro de `class RDO`, imediatamente após o bloco `estado = db.Column(...)` da Task 1, insira:

```python
    # Fase 5 — RDO retificador. Um RDO é um documento de DATA: "versionar"
    # o RDO de 22/06 é emitir outro RDO de 22/06 que diz o que o primeiro
    # deveria ter dito, com o primeiro preservado e marcado 'retificado'.
    # É a prática de campo, e resolve o UNIQUE de `numero_rdo` sem gambiarra.
    # ON DELETE SET NULL: apagar o retificador não pode estourar a FK do
    # original (que, por ser 'retificado', a guarda de imutabilidade
    # impede de apagar mesmo).
    rdo_retificado_id = db.Column(
        db.Integer, db.ForeignKey('rdo.id', ondelete='SET NULL'),
        nullable=True, index=True)
    motivo_retificacao = db.Column(db.Text, nullable=True)

    rdo_retificado = db.relationship(
        'RDO', remote_side=[id], foreign_keys=[rdo_retificado_id],
        backref=db.backref('retificadores', lazy='dynamic'))
```

> **Atenção:** `remote_side=[id]` referencia a coluna `id` declarada na linha 837 da mesma classe. Se você inseriu este bloco antes da declaração de `id`, o SQLAlchemy levanta `NameError` na importação.

- [ ] **Step 4: Escreva a migration 263**

Em `migrations.py`, imediatamente antes de `def executar_migracoes():`, insira:

```python
def migration_263_rdo_retificador():
    """Fase 5 — rdo.rdo_retificado_id + rdo.motivo_retificacao.

    Aditiva e idempotente. Auto-FK: o RDO retificador aponta para o RDO
    que ele substitui. Nenhuma linha histórica é preenchida — não há como
    saber, retroativamente, qual RDO antigo corrigiu qual.
    """
    logger.info("[Migration 263] Iniciando — rdo.rdo_retificado_id")

    db.session.execute(text("""
        ALTER TABLE rdo
        ADD COLUMN IF NOT EXISTS rdo_retificado_id INTEGER
    """))
    db.session.execute(text("""
        ALTER TABLE rdo
        ADD COLUMN IF NOT EXISTS motivo_retificacao TEXT
    """))
    db.session.commit()

    existe_fk = db.session.execute(text("""
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_rdo_retificado_id'
          AND table_name = 'rdo'
        LIMIT 1
    """)).fetchone()
    if not existe_fk:
        db.session.execute(text("""
            ALTER TABLE rdo
            ADD CONSTRAINT fk_rdo_retificado_id
            FOREIGN KEY (rdo_retificado_id) REFERENCES rdo(id)
            ON DELETE SET NULL
        """))
        db.session.commit()
        logger.info("[Migration 263] FK fk_rdo_retificado_id criada")

    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_rdo_rdo_retificado_id
        ON rdo (rdo_retificado_id)
    """))
    db.session.commit()

    logger.info("[Migration 263] Concluída com sucesso")
```

- [ ] **Step 5: Registre a migration**

Em `migrations.py`, na lista `migrations_to_run`, logo após a entrada `262`, adicione:

```python
            (263, "Fase 5 — rdo.rdo_retificado_id + motivo_retificacao (RDO retificador)", migration_263_rdo_retificador),
```

- [ ] **Step 6: Implemente `criar_retificador`**

Ao final de `services/rdo_assinatura.py`, adicione:

```python
# Campos do cabeçalho do RDO que o retificador herda. `status` fica de
# fora porque é preenchido pelo default ('Finalizado'); `estado` fica de
# fora porque o retificador nasce em rascunho.
_CAMPOS_CABECALHO = (
    'clima_geral', 'temperatura_media', 'umidade_relativa',
    'vento_velocidade', 'precipitacao', 'condicoes_trabalho',
    'observacoes_climaticas', 'local', 'comentario_geral',
)


def criar_retificador(rdo, usuario, *, motivo):
    """Emite um RDO retificador do `rdo` e marca o original.

    O retificador nasce em `rascunho`, no MESMO dia do original, com uma
    cópia do conteúdo (cabeçalho, subatividades, mão de obra,
    equipamentos, ocorrências). Fotos e apontamentos de cronograma NÃO
    são copiados de propósito:

      * fotos são 442 KB de base64 por unidade (medido: 28.870 fotos =
        16 GB em `rdo_foto`) — duplicá-las por retificação dobra o custo
        do problema que a Task 15 existe para resolver;
      * apontamentos de cronograma são acumulativos entre RDOs
        (services/cronograma_apontamento_service.py:213-224). Copiar
        somaria produção duas vezes. Quem retifica reapontar o que mudou.

    Não faz commit. Devolve o RDO novo.
    """
    from models import (RDO, RDOEquipamento, RDOMaoObra, RDOOcorrencia,
                        RDOServicoSubatividade)
    from services.rdo_ciclo_vida import (ESTADOS_IMUTAVEIS, RASCUNHO,
                                         RETIFICADO)

    motivo = (motivo or '').strip()
    if not motivo:
        raise AssinaturaInvalida(
            'Informe o motivo da retificação — ele fica no documento.')

    atual = estado_de(rdo)
    if atual not in ESTADOS_IMUTAVEIS or atual == RETIFICADO:
        raise AssinaturaInvalida(
            f'Só um RDO assinado ou aprovado pode ser retificado — este '
            f'está em "{atual}". Se ele ainda é editável, corrija-o '
            f'direto.')

    from views.rdo import _gerar_numero_rdo_unico

    admin_id = rdo.admin_id or rdo.obra.admin_id
    novo = RDO(
        obra_id=rdo.obra_id,
        data_relatorio=rdo.data_relatorio,
        admin_id=admin_id,
        criado_por_id=usuario.id,
        numero_rdo=_gerar_numero_rdo_unico(rdo.obra_id, rdo.data_relatorio,
                                           admin_id),
        estado=RASCUNHO,
        rdo_retificado_id=rdo.id,
        motivo_retificacao=motivo,
    )
    for campo in _CAMPOS_CABECALHO:
        setattr(novo, campo, getattr(rdo, campo, None))
    db.session.add(novo)
    db.session.flush()

    for sub in RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id).all():
        db.session.add(RDOServicoSubatividade(
            rdo_id=novo.id, admin_id=admin_id, servico_id=sub.servico_id,
            nome_subatividade=sub.nome_subatividade,
            descricao_subatividade=sub.descricao_subatividade,
            percentual_conclusao=sub.percentual_conclusao,
            percentual_anterior=sub.percentual_anterior,
            incremento_dia=sub.incremento_dia,
            observacoes_tecnicas=sub.observacoes_tecnicas,
            ordem_execucao=sub.ordem_execucao,
            subatividade_mestre_id=sub.subatividade_mestre_id,
            quantidade_produzida=sub.quantidade_produzida,
            meta_produtividade_snapshot=sub.meta_produtividade_snapshot,
            unidade_medida_snapshot=sub.unidade_medida_snapshot,
        ))

    for mo in RDOMaoObra.query.filter_by(rdo_id=rdo.id).all():
        db.session.add(RDOMaoObra(
            rdo_id=novo.id, admin_id=admin_id,
            funcionario_id=mo.funcionario_id,
            funcao_exercida=mo.funcao_exercida,
            horas_trabalhadas=mo.horas_trabalhadas,
            tarefa_cronograma_id=mo.tarefa_cronograma_id,
            peso_distribuicao=mo.peso_distribuicao,
        ))

    for eq in RDOEquipamento.query.filter_by(rdo_id=rdo.id).all():
        db.session.add(RDOEquipamento(
            rdo_id=novo.id, admin_id=admin_id,
            nome_equipamento=eq.nome_equipamento, quantidade=eq.quantidade,
            horas_uso=eq.horas_uso,
            estado_conservacao=eq.estado_conservacao,
        ))

    for oc in RDOOcorrencia.query.filter_by(rdo_id=rdo.id).all():
        db.session.add(RDOOcorrencia(
            rdo_id=novo.id, admin_id=admin_id,
            tipo_ocorrencia=oc.tipo_ocorrencia, severidade=oc.severidade,
            descricao_ocorrencia=oc.descricao_ocorrencia,
            problemas_identificados=oc.problemas_identificados,
            acoes_corretivas=oc.acoes_corretivas,
            responsavel_acao=oc.responsavel_acao,
            prazo_resolucao=oc.prazo_resolucao,
            status_resolucao=oc.status_resolucao,
        ))

    ip, _ua = _contexto_request()
    transicionar(rdo, RETIFICADO, usuario=usuario, motivo=motivo, ip=ip,
                 detalhes={'rdo_retificador_id': novo.id})
    transicionar(novo, RASCUNHO, usuario=usuario, motivo=motivo, ip=ip,
                 detalhes={'rdo_retificado_id': rdo.id})

    logger.info('[assinatura] rdo=%s RETIFICADO por rdo=%s usuario=%s '
                'motivo=%r', rdo.id, novo.id, usuario.id, motivo)
    return novo
```

> Nota: `transicionar(novo, RASCUNHO, ...)` é um no-op de estado (o RDO já nasce em `rascunho`) e devolve `None` — não grava trilha. Está aqui de propósito, como documentação executável de que o retificador nasce editável; se o default mudar, o teste `test_retificar_cria_rdo_novo_e_marca_o_original` acusa.

- [ ] **Step 7: Implemente a rota**

Em `views/rdo.py`, imediatamente após o fim de `reabrir_rdo`, insira:

```python
@main_bp.route('/rdo/<int:id>/retificar', methods=['POST'])
@login_required
def retificar_rdo(id):
    """Emite um RDO retificador de um RDO assinado/aprovado.

    Autorização: `pode_editar_obra` (Fase 1). Retificar é ato de gestão —
    o documento original fica no acervo, marcado `retificado`.
    """
    from services.rdo_assinatura import criar_retificador
    from services.rdo_ciclo_vida import CicloVidaInvalido
    from utils.autorizacao import pode_editar_obra

    rdo = _rdo_do_tenant_ou_404(id)

    if not pode_editar_obra(rdo.obra_id):
        flash('Só o gestor da obra pode emitir RDO retificador.', 'error')
        return redirect(url_for('main.visualizar_rdo', id=id))

    try:
        novo = criar_retificador(
            rdo, current_user, motivo=request.form.get('motivo'))
        db.session.commit()
        flash(f'RDO retificador {novo.numero_rdo} criado a partir do '
              f'{rdo.numero_rdo}. Corrija e assine o novo documento.',
              'success')
        return redirect(url_for('main.visualizar_rdo', id=novo.id))
    except CicloVidaInvalido as e:
        db.session.rollback()
        flash(str(e), 'error')
    except Exception as e:
        db.session.rollback()
        logger.error(f"ERRO RETIFICAR RDO {id}: {e}", exc_info=True)
        flash('Erro ao emitir o RDO retificador.', 'error')

    return redirect(url_for('main.visualizar_rdo', id=id))
```

- [ ] **Step 8: Aplique a migration e rode os testes**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "Migration 263|ERRO|ERROR"
python -m pytest tests/test_fase5_rdo_assinatura.py -v
```

Esperado: `[Migration 263] Concluída com sucesso` e os 29 testes do arquivo PASSAM.

- [ ] **Step 9: Commit**

```bash
git add models.py migrations.py services/rdo_assinatura.py views/rdo.py tests/test_fase5_rdo_assinatura.py
git commit -m "feat(fase5): RDO retificador

RDO assinado nao se edita: retifica. O retificador nasce em rascunho, no
mesmo dia, com copia do conteudo; o original vira 'retificado' e continua
imutavel. Fotos e apontamentos NAO sao copiados — fotos custam 442 KB de
base64 cada e apontamento de cronograma e acumulativo entre RDOs."
```

---

## Task 10: Bug 6d — conserto do `duplicar_rdo`

**Files:**
- Modify: `views/rdo.py:1596-1719` (a função inteira)
- Test: `tests/test_fase5_rdo_ciclo_vida.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente ao final de `tests/test_fase5_rdo_ciclo_vida.py`:

```python
# ---------------------------------------------------------------------------
# Bug 6d — duplicar_rdo
# ---------------------------------------------------------------------------

def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


def test_duplicar_rdo_nao_quebra_em_atributo_fantasma():
    """Regressão do bug 6d, parte 1.

    Antes: views/rdo.py:1624 lia `rdo_original.tempo_manha`, que NÃO é
    coluna de RDO (as colunas de clima são clima_geral, temperatura_media,
    umidade_relativa, vento_velocidade, precipitacao, condicoes_trabalho,
    observacoes_climaticas). A leitura levantava AttributeError, a função
    caía no `except` da linha 1715 e a rota NUNCA duplicava nada.
    """
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        rid, aid, oid = rdo.id, admin.id, obra.id

    resposta = _cliente_de(aid).post(f'/rdo/{rid}/duplicar',
                                     follow_redirects=False)
    assert resposta.status_code in (200, 302)

    with app.app_context():
        copias = RDO.query.filter(RDO.obra_id == oid, RDO.id != rid).all()
        assert len(copias) == 1, (
            'duplicar_rdo não criou o RDO copiado — provavelmente ainda '
            'morre no atributo fantasma tempo_manha (views/rdo.py:1624)')
        assert copias[0].clima_geral == 'Nublado'


def test_duplicar_rdo_nasce_em_rascunho():
    """Regressão do bug 6d, parte 2.

    Antes: views/rdo.py:1629 gravava status='Finalizado' na cópia. Um RDO
    duplicado é um ponto de partida para edição, não um documento
    publicado — e era exatamente essa premissa falsa que justificava o
    webhook da linha 1708.
    """
    from services.rdo_ciclo_vida import RASCUNHO

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        rid, aid, oid = rdo.id, admin.id, obra.id

    _cliente_de(aid).post(f'/rdo/{rid}/duplicar')

    with app.app_context():
        copia = RDO.query.filter(RDO.obra_id == oid, RDO.id != rid).first()
        assert copia.estado == RASCUNHO


def test_duplicar_rdo_nao_emite_webhook(monkeypatch):
    """Regressão do bug 6d, parte 3 — o bug nomeado no ESTADO-ATUAL.md.

    `duplicar_rdo` era a ÚNICA rota de escrita de RDO que chamava
    `emit_obra_rdo_publicado` (views/rdo.py:1708) sem chamar
    `EventManager.emit('rdo_finalizado')` — que é quem dispara
    `lancar_custos_rdo` (event_manager.py:578) e
    `recalcular_medicao_apos_rdo` (event_manager.py:1357). As irmãs
    emitem os dois (:1570/:1583, :1819/:1831, :4769/:4781).

    A correção adotada NÃO é "emitir os dois": é não emitir nenhum,
    porque um RDO duplicado nasce em rascunho e ainda não publicou nada.
    O webhook sai quando ele for submetido/assinado.
    """
    emitidos = []

    import utils.catalogo_eventos as catalogo
    monkeypatch.setattr(catalogo, 'emit_obra_rdo_publicado',
                        lambda rdo, admin_id: emitidos.append(rdo.id))

    from event_manager import EventManager
    eventos_legados = []
    original_emit = EventManager.emit
    monkeypatch.setattr(
        EventManager, 'emit',
        staticmethod(lambda nome, dados, admin_id=None: (
            eventos_legados.append(nome) or original_emit(nome, dados, admin_id)
            if nome != 'rdo_finalizado' else eventos_legados.append(nome))))

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        rid, aid = rdo.id, admin.id

    _cliente_de(aid).post(f'/rdo/{rid}/duplicar')

    assert emitidos == [], (
        'duplicar_rdo emitiu obra.rdo_publicado para um RDO que nasce em '
        'rascunho — bug 6d')
    assert 'rdo_finalizado' not in eventos_legados


def test_duplicar_rdo_nao_lanca_custo_de_mao_de_obra():
    """A outra metade do bug 6d: webhook sem custo.

    Se o RDO duplicado não publica, também não pode gerar RDOCustoDiario
    nem GestaoCustoFilho — nem pelo evento, nem por chamada direta.
    """
    from models import RDOCustoDiario, RDOMaoObra

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = Funcionario(
            nome=f'Montador {_sfx()}', cpf=_sfx().ljust(14, '0')[:14],
            codigo=f'FD{_sfx()[:6].upper()}', data_admissao=date(2025, 1, 1),
            admin_id=admin.id, ativo=True, tipo_remuneracao='diaria',
            valor_diaria=200.0)
        db.session.add(func)
        rdo = _rdo(obra, admin.id)
        db.session.commit()
        db.session.add(RDOMaoObra(
            rdo_id=rdo.id, admin_id=admin.id, funcionario_id=func.id,
            funcao_exercida='Montador', horas_trabalhadas=8.0))
        db.session.commit()
        rid, aid, oid = rdo.id, admin.id, obra.id

    _cliente_de(aid).post(f'/rdo/{rid}/duplicar')

    with app.app_context():
        copia = RDO.query.filter(RDO.obra_id == oid, RDO.id != rid).first()
        assert RDOMaoObra.query.filter_by(rdo_id=copia.id).count() == 1, (
            'a mão de obra não foi copiada')
        assert RDOCustoDiario.query.filter_by(rdo_id=copia.id).count() == 0, (
            'RDO duplicado em rascunho lançou custo diário')


def test_duplicar_rdo_de_outro_tenant_devolve_404():
    with app.app_context():
        admin_a, admin_b = _admin('A'), _admin('B')
        obra_b = _obra(admin_b.id)
        rdo_b = _rdo(obra_b, admin_b.id)
        rid, aid = rdo_b.id, admin_a.id

    resposta = _cliente_de(aid).post(f'/rdo/{rid}/duplicar',
                                     follow_redirects=False)
    assert resposta.status_code in (302, 404)

    with app.app_context():
        assert RDO.query.filter_by(obra_id=obra_b.id).count() == 1


def test_duplicar_rdo_assinado_e_permitido():
    """Duplicar não é editar: o original não é tocado."""
    from services.rdo_ciclo_vida import ASSINADO

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        _assinar_direto(rdo, admin)
        rid, aid, oid = rdo.id, admin.id, obra.id

    _cliente_de(aid).post(f'/rdo/{rid}/duplicar')

    with app.app_context():
        assert db.session.get(RDO, rid).estado == ASSINADO
        assert RDO.query.filter(RDO.obra_id == oid, RDO.id != rid).count() == 1
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase5_rdo_ciclo_vida.py -v -k duplicar
```

Esperado: FAIL. `test_duplicar_rdo_nao_quebra_em_atributo_fantasma` falha com `AssertionError: duplicar_rdo não criou o RDO copiado` — a prova de que a rota está morta hoje.

- [ ] **Step 3: Reescreva `duplicar_rdo`**

Em `views/rdo.py`, substitua a função inteira das linhas 1596-1719 (do decorator `@main_bp.route('/rdo/<int:id>/duplicar', methods=['POST'])` até o `return redirect(url_for('main.rdos'))` do `except`) por:

```python
@main_bp.route('/rdo/<int:id>/duplicar', methods=['POST'])
@login_required
def duplicar_rdo(id):
    """Cria um RDO novo a partir de outro, como ponto de partida de edição.

    ── Bug 6d, corrigido na Fase 5 ──────────────────────────────────────
    A versão anterior tinha três defeitos empilhados:

      1. Lia `rdo_original.tempo_manha`, `.tempo_tarde`, `.tempo_noite` e
         `.observacoes_meteorologicas` (linhas 1624-1627). NENHUM desses
         atributos é coluna de `RDO` — as colunas de clima são
         `clima_geral`, `temperatura_media`, `umidade_relativa`,
         `vento_velocidade`, `precipitacao`, `condicoes_trabalho` e
         `observacoes_climaticas` (models.py:844-851). A leitura
         levantava `AttributeError`, a função caía no `except` e a rota
         NUNCA duplicou nada.
      2. Copiava `mao_original.observacoes`, que também não existe em
         `RDOMaoObra` (models.py:917-966).
      3. Se os dois anteriores fossem consertados isoladamente, apareceria
         o bug catalogado como 6d: era a ÚNICA rota de escrita de RDO que
         chamava `emit_obra_rdo_publicado` (webhook n8n) sem chamar
         `EventManager.emit('rdo_finalizado')`, que é quem lança os custos
         de mão de obra (`event_manager.py:578`) e recalcula a medição
         (`event_manager.py:1357`). O cliente recebia "RDO publicado" de
         um documento que não existia no custo.

    A correção não é emitir os dois eventos: é **não emitir nenhum**. Um
    RDO duplicado nasce em `rascunho`. Ele publica — e aí sim emite —
    quando for submetido e assinado, pelos caminhos da Fase 5.
    """
    from services.rdo_ciclo_vida import RASCUNHO

    rdo_original = _rdo_do_tenant_ou_404(id)
    admin_id = rdo_original.admin_id or rdo_original.obra.admin_id

    try:
        novo_rdo = RDO(
            obra_id=rdo_original.obra_id,
            data_relatorio=date.today(),
            admin_id=admin_id,
            criado_por_id=current_user.id,
            estado=RASCUNHO,
            comentario_geral=(
                f'Duplicado de {rdo_original.numero_rdo}. '
                f'{rdo_original.comentario_geral or ""}').strip(),
        )
        novo_rdo.numero_rdo = _gerar_numero_rdo_unico(
            novo_rdo.obra_id, novo_rdo.data_relatorio, admin_id)

        # Clima: os nomes REAIS das colunas (models.py:844-851).
        for campo in ('clima_geral', 'temperatura_media', 'umidade_relativa',
                      'vento_velocidade', 'precipitacao', 'condicoes_trabalho',
                      'observacoes_climaticas', 'local'):
            setattr(novo_rdo, campo, getattr(rdo_original, campo, None))

        db.session.add(novo_rdo)
        db.session.flush()

        for sub in RDOServicoSubatividade.query.filter_by(
                rdo_id=rdo_original.id).all():
            db.session.add(RDOServicoSubatividade(
                rdo_id=novo_rdo.id,
                admin_id=admin_id,
                servico_id=sub.servico_id,
                nome_subatividade=sub.nome_subatividade,
                descricao_subatividade=sub.descricao_subatividade,
                percentual_conclusao=sub.percentual_conclusao,
                percentual_anterior=sub.percentual_anterior,
                observacoes_tecnicas=sub.observacoes_tecnicas,
                ordem_execucao=sub.ordem_execucao,
                subatividade_mestre_id=sub.subatividade_mestre_id,
                meta_produtividade_snapshot=sub.meta_produtividade_snapshot,
                unidade_medida_snapshot=sub.unidade_medida_snapshot,
            ))

        for mo in RDOMaoObra.query.filter_by(rdo_id=rdo_original.id).all():
            db.session.add(RDOMaoObra(
                rdo_id=novo_rdo.id,
                admin_id=admin_id,
                funcionario_id=mo.funcionario_id,
                # `funcao_exercida` é NOT NULL (models.py:924).
                funcao_exercida=mo.funcao_exercida or 'Geral',
                horas_trabalhadas=mo.horas_trabalhadas,
                tarefa_cronograma_id=mo.tarefa_cronograma_id,
                peso_distribuicao=mo.peso_distribuicao,
            ))

        db.session.commit()

        # Nenhum evento é emitido aqui. Ver o bloco "Bug 6d" no docstring.
        logger.info('[RDO] %s duplicado a partir de %s — nasce em rascunho, '
                    'sem evento', novo_rdo.numero_rdo, rdo_original.numero_rdo)

        flash(f'RDO duplicado como {novo_rdo.numero_rdo} (rascunho). '
              f'Revise, submeta e assine.', 'success')
        return redirect(url_for('main.visualizar_rdo', id=novo_rdo.id))

    except Exception as e:
        db.session.rollback()
        logger.error(f"ERRO DUPLICAR RDO {id}: {e}", exc_info=True)
        flash('Erro ao duplicar RDO.', 'error')
        return redirect(url_for('main.rdos'))
```

- [ ] **Step 4: Rode os testes**

```bash
python -m pytest tests/test_fase5_rdo_ciclo_vida.py -v -k duplicar
```

Esperado: os 6 testes de `duplicar` PASSAM.

- [ ] **Step 5: Prove que os atributos fantasma sumiram**

```bash
grep -n "tempo_manha\|tempo_tarde\|tempo_noite\|observacoes_meteorologicas" views/rdo.py
```

Esperado: as ocorrências das linhas 1624-1627 sumiram. Restam as de `views/rdo.py:688` e `:2732`, que são **escritas** em atributo inexistente (silenciosamente descartadas pelo SQLAlchemy, sem erro) — dívida separada, fora do escopo desta fase.

- [ ] **Step 6: Commit**

```bash
git add views/rdo.py tests/test_fase5_rdo_ciclo_vida.py
git commit -m "fix(fase5): bug 6d — duplicar_rdo estava morto e emitiria webhook sem custo

A rota morria em AttributeError no atributo fantasma tempo_manha
(views/rdo.py:1624) e nunca chegava ao emit da linha 1708. Consertados os
quatro atributos inexistentes de clima, o mao_original.observacoes, e o
proprio 6d: o RDO duplicado agora nasce em rascunho e NAO emite
obra.rdo_publicado nem rdo_finalizado. Ele publica quando for assinado."
```

---

## Task 11: Fechar `visualizar_rdo` e o `excluir_rdo` de RDO imutável

**Files:**
- Modify: `views/rdo.py:926-928`
- Modify: `views/rdo.py:462-464` (`excluir_rdo`)
- Test: `tests/test_fase5_rdo_ciclo_vida.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente ao final de `tests/test_fase5_rdo_ciclo_vida.py`:

```python
# ---------------------------------------------------------------------------
# Rotas anônimas e exclusão
# ---------------------------------------------------------------------------

def test_visualizar_rdo_exige_login():
    """views/rdo.py:928 dizia literalmente 'SEM VERIFICAÇÃO DE PERMISSÃO'.

    Um RDO assinado que qualquer anônimo lê pela URL não tem valor
    probatório nenhum — e a numeração (`RDO-<admin_id>-<ano>-NNN`) é
    sequencial e adivinhável.
    """
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        rid = rdo.id

    resposta = app.test_client().get(f'/rdo/{rid}', follow_redirects=False)
    assert resposta.status_code in (302, 401), (
        f'/rdo/{rid} devolveu {resposta.status_code} para anônimo')
    if resposta.status_code == 302:
        assert '/login' in resposta.headers.get('Location', '')


def test_visualizar_rdo_de_outro_tenant_devolve_404():
    with app.app_context():
        admin_a, admin_b = _admin('A'), _admin('B')
        obra_b = _obra(admin_b.id)
        rdo_b = _rdo(obra_b, admin_b.id)
        rid, aid = rdo_b.id, admin_a.id

    resposta = _cliente_de(aid).get(f'/rdo/{rid}', follow_redirects=False)
    assert resposta.status_code in (302, 404), (
        f'RDO de outro tenant devolveu {resposta.status_code}')


def test_excluir_rdo_assinado_pela_rota_e_recusado():
    from services.rdo_ciclo_vida import ASSINADO

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        _assinar_direto(rdo, admin)
        rid, aid = rdo.id, admin.id

    _cliente_de(aid).post(f'/rdo/excluir/{rid}', follow_redirects=True)

    with app.app_context():
        sobrevivente = db.session.get(RDO, rid)
        assert sobrevivente is not None, 'RDO assinado foi excluído'
        assert sobrevivente.estado == ASSINADO


def test_excluir_rdo_em_rascunho_continua_funcionando():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        rid, aid = rdo.id, admin.id

    _cliente_de(aid).post(f'/rdo/excluir/{rid}', follow_redirects=True)

    with app.app_context():
        assert db.session.get(RDO, rid) is None
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase5_rdo_ciclo_vida.py -v -k "visualizar or excluir"
```

Esperado: FAIL — `/rdo/<id>` devolve 200 para anônimo; a exclusão do assinado devolve erro genérico mas o teste de rascunho pode já passar.

- [ ] **Step 3: Feche `visualizar_rdo`**

Em `views/rdo.py`, substitua as linhas 926-928:

```python
@main_bp.route('/rdo/<int:id>')
def visualizar_rdo(id):
    """Visualizar RDO específico - SEM VERIFICAÇÃO DE PERMISSÃO"""
```

por:

```python
@main_bp.route('/rdo/<int:id>')
@login_required   # Fase 5 — a rota estava SEM decorator nenhum, e o
                  # docstring dizia "SEM VERIFICAÇÃO DE PERMISSÃO". Um RDO
                  # assinado legível por qualquer anônimo pela URL não tem
                  # valor probatório, e `numero_rdo` é sequencial.
def visualizar_rdo(id):
    """Visualizar RDO específico do tenant do usuário logado."""
```

E, logo no início do corpo `try:` da função (antes do primeiro `logger.info`), acrescente o filtro de tenant:

```python
        # Fase 5 — filtro de tenant explícito. Antes desta linha a função
        # carregava o RDO por id puro, sem predicado de empresa.
        from utils.tenant import get_tenant_admin_id
        _tenant = get_tenant_admin_id()
        if _tenant is None:
            flash('Sessão sem empresa vinculada; refaça o login.', 'error')
            return redirect(url_for('main.login'))
        if not RDO.query.join(Obra).filter(
                RDO.id == id, Obra.admin_id == _tenant).first():
            from flask import abort
            abort(404)
```

- [ ] **Step 4: Recuse a exclusão de RDO imutável**

Em `views/rdo.py`, dentro de `excluir_rdo`, logo após o bloco que faz `if not rdo: ... return redirect(...)` (linha 476-478) e ANTES da chamada a `cancelar_custos_rdo`, insira:

```python
        # Fase 5 — RDO assinado/aprovado/retificado não se apaga. A guarda
        # `before_flush` (services/rdo_ciclo_vida) barraria o delete de
        # qualquer jeito, mas ela levanta no commit, depois de o
        # `cancelar_custos_rdo` abaixo já ter mexido no financeiro. Este
        # early-return evita o efeito colateral e dá uma mensagem decente.
        from services.rdo_ciclo_vida import ROTULOS, e_imutavel, estado_de
        if e_imutavel(rdo):
            flash(f'RDO {rdo.numero_rdo} está '
                  f'{ROTULOS[estado_de(rdo)].lower()} e não pode ser '
                  f'excluído. Para corrigir, emita um RDO retificador.',
                  'error')
            return redirect(url_for('main.visualizar_rdo', id=rdo_id))
```

- [ ] **Step 5: Rode os testes**

```bash
python -m pytest tests/test_fase5_rdo_ciclo_vida.py -v
python -m pytest tests/ -m "not browser" -k "rdo" -q 2>&1 | tail -20
```

Esperado: `test_fase5_rdo_ciclo_vida.py` todo verde. Na segunda linha, compare com a baseline: testes que chamavam `/rdo/<id>` sem login passam a receber 302 — se algum quebrar, o certo é o teste passar a injetar `sess['_user_id']`, não reabrir a rota.

- [ ] **Step 6: Commit**

```bash
git add views/rdo.py tests/test_fase5_rdo_ciclo_vida.py
git commit -m "fix(sec,fase5): fecha /rdo/<id> e proibe excluir RDO imutavel

A rota de visualizacao nao tinha decorator nenhum e o docstring assumia
isso. Agora exige login e filtra por tenant, devolvendo 404 para RDO de
outra empresa. excluir_rdo recusa RDO assinado ANTES de mexer no
financeiro."
```

---

## Task 12: Selo de estado, botões e assinatura no PDF

**Files:**
- Modify: `views/rdo.py` (contexto do `render_template` em `views/rdo.py:1459-1473`)
- Modify: `templates/rdo/visualizar_rdo_moderno.html:1077-1083`
- Modify: `services/rdo_pdf_service.py:798-865` (`_signature_block`)
- Test: `tests/test_fase5_rdo_assinatura.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente ao final de `tests/test_fase5_rdo_assinatura.py`:

```python
# ---------------------------------------------------------------------------
# UI e PDF
# ---------------------------------------------------------------------------

def test_tela_do_rdo_mostra_o_selo_de_estado():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        rid, aid = rdo.id, admin.id

    corpo = _cliente_de(aid).get(f'/rdo/{rid}').get_data(as_text=True)
    assert 'Rascunho' in corpo, 'o selo de estado não apareceu na tela'


def test_tela_mostra_botao_de_assinar_para_quem_pode():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        _vincular(op, obra, PapelObra.APONTADOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, op)
        rid, opid = rdo.id, op.id

    corpo = _cliente_de(opid).get(f'/rdo/{rid}').get_data(as_text=True)
    assert f'/rdo/{rid}/assinar' in corpo


def test_tela_nao_mostra_botao_de_assinar_para_leitor():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        _vincular(op, obra, PapelObra.LEITOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, op)
        rid, opid = rdo.id, op.id

    corpo = _cliente_de(opid).get(f'/rdo/{rid}').get_data(as_text=True)
    assert f'/rdo/{rid}/assinar' not in corpo


def test_tela_do_rdo_assinado_mostra_quem_assinou():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        _vincular(op, obra, PapelObra.APONTADOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, op)
        rid, opid, nome = rdo.id, op.id, func.nome

    _assinar_pela_rota(rid, opid)
    corpo = _cliente_de(opid).get(f'/rdo/{rid}').get_data(as_text=True)
    assert nome in corpo
    assert 'Assinado' in corpo


def test_pdf_do_rdo_assinado_e_gerado_com_a_assinatura():
    from models import RDOAssinatura
    from services.rdo_pdf_service import gerar_pdf_rdo

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        _vincular(op, obra, PapelObra.APONTADOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, op)
        rid, opid = rdo.id, op.id

    _assinar_pela_rota(rid, opid)

    with app.app_context():
        rdo = db.session.get(RDO, rid)
        assinaturas = RDOAssinatura.query.filter_by(rdo_id=rid).all()
        assert len(assinaturas) == 1
        pdf = gerar_pdf_rdo(rdo)
        assert pdf, 'gerar_pdf_rdo devolveu vazio para RDO assinado'
        assert pdf[:4] == b'%PDF'


def test_pdf_do_rdo_sem_assinatura_continua_gerando():
    """Regressão: o bloco de assinatura manuscrita não pode sumir."""
    from services.rdo_pdf_service import gerar_pdf_rdo

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        pdf = gerar_pdf_rdo(rdo)
        assert pdf and pdf[:4] == b'%PDF'
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase5_rdo_assinatura.py -v -k "tela or pdf"
```

Esperado: FAIL — o selo e os links não estão no HTML.

- [ ] **Step 3: Passe o ciclo de vida ao template**

Em `views/rdo.py`, no `return render_template('rdo/visualizar_rdo_moderno.html', ...)` que começa na linha 1459, substitua a **última linha** da chamada:

```python
                             indice_medio_por_subatividade=indice_medio_por_subatividade)
```

por:

```python
                             indice_medio_por_subatividade=indice_medio_por_subatividade,
                             # ── Fase 5 — ciclo de vida ──────────────
                             estado_rdo=_estado_para_template(rdo),
                             assinaturas_rdo=list(rdo.assinaturas or []),
                             acoes_rdo=_acoes_para_template(rdo))
```

E, imediatamente antes de `@main_bp.route('/rdo/<int:id>')` (linha 926), insira os dois helpers:

```python
def _estado_para_template(rdo):
    """Rótulo + cor do estado, para o selo da tela. Nunca levanta."""
    try:
        from services.rdo_ciclo_vida import CORES, ROTULOS, estado_de
        atual = estado_de(rdo)
        return {'valor': atual,
                'rotulo': ROTULOS.get(atual, atual),
                'cor': CORES.get(atual, 'secondary')}
    except Exception:
        logger.warning('[Fase5] estado do RDO ilegível', exc_info=True)
        return {'valor': 'rascunho', 'rotulo': 'Rascunho', 'cor': 'secondary'}


def _acoes_para_template(rdo):
    """Quais botões de transição este usuário vê. Falha FECHADA."""
    vazio = {'submeter': False, 'assinar': False, 'aprovar': False,
             'reabrir': False, 'retificar': False}
    try:
        from services.rdo_ciclo_vida import (APROVADO, ASSINADO, PREENCHIDO,
                                             RASCUNHO, estado_de)
        from utils.autorizacao import pode_apontar_na_obra, pode_editar_obra
        atual = estado_de(rdo)
        aponta = pode_apontar_na_obra(rdo.obra_id)
        edita = pode_editar_obra(rdo.obra_id)
        return {
            'submeter': aponta and atual == RASCUNHO,
            'assinar': aponta and atual == PREENCHIDO,
            'aprovar': edita and atual == ASSINADO,
            'reabrir': edita and atual == PREENCHIDO,
            'retificar': edita and atual in (ASSINADO, APROVADO),
        }
    except Exception:
        logger.warning('[Fase5] ações do RDO ilegíveis', exc_info=True)
        return vazio
```

- [ ] **Step 4: Acrescente o selo e os botões ao template**

Em `templates/rdo/visualizar_rdo_moderno.html`, substitua o bloco `<div class="header-right"> … </div>` (linhas 1077-1083) por:

```html
            <div class="header-right">
                {# Fase 5 — selo de estado do ciclo de vida #}
                <span class="badge bg-{{ estado_rdo.cor }}"
                      style="font-size:.95rem;padding:.55rem .9rem;margin-right:.5rem;vertical-align:middle;">
                    {{ estado_rdo.rotulo }}
                </span>

                {% if acoes_rdo.submeter %}
                <form method="POST" action="{{ url_for('main.finalizar_rdo', id=rdo.id) }}" class="d-inline">
                    <button type="submit" class="btn-voltar" style="margin-right:.5rem;background:#0d6efd;border-color:#0d6efd;color:#fff;">
                        <i class="fas fa-paper-plane"></i> Submeter
                    </button>
                </form>
                {% endif %}

                {% if acoes_rdo.assinar %}
                <form method="POST" action="{{ url_for('main.assinar_rdo', id=rdo.id) }}" class="d-inline"
                      onsubmit="return confirm('Assinar este RDO? Depois de assinado ele não aceita mais edição — a correção passa a ser por RDO retificador.');">
                    <input type="hidden" name="observacao" value="">
                    <button type="submit" class="btn-voltar" style="margin-right:.5rem;background:#198754;border-color:#198754;color:#fff;">
                        <i class="fas fa-signature"></i> Assinar
                    </button>
                </form>
                {% endif %}

                {% if acoes_rdo.aprovar %}
                <form method="POST" action="{{ url_for('main.aprovar_rdo', id=rdo.id) }}" class="d-inline">
                    <button type="submit" class="btn-voltar" style="margin-right:.5rem;background:#198754;border-color:#198754;color:#fff;">
                        <i class="fas fa-check-double"></i> Aprovar
                    </button>
                </form>
                {% endif %}

                {% if acoes_rdo.reabrir %}
                <form method="POST" action="{{ url_for('main.reabrir_rdo', id=rdo.id) }}" class="d-inline"
                      onsubmit="this.motivo.value = prompt('Motivo da reabertura:') || ''; return this.motivo.value.trim() !== '';">
                    <input type="hidden" name="motivo" value="">
                    <button type="submit" class="btn-voltar" style="margin-right:.5rem;">
                        <i class="fas fa-lock-open"></i> Reabrir
                    </button>
                </form>
                {% endif %}

                {% if acoes_rdo.retificar %}
                <form method="POST" action="{{ url_for('main.retificar_rdo', id=rdo.id) }}" class="d-inline"
                      onsubmit="this.motivo.value = prompt('Motivo da retificação (fica no documento):') || ''; return this.motivo.value.trim() !== '';">
                    <input type="hidden" name="motivo" value="">
                    <button type="submit" class="btn-voltar" style="margin-right:.5rem;background:#fd7e14;border-color:#fd7e14;color:#fff;">
                        <i class="fas fa-file-pen"></i> Retificar
                    </button>
                </form>
                {% endif %}

                <a href="{{ url_for('main.exportar_rdo_pdf', rdo_id=rdo.id) }}" class="btn-voltar" style="margin-right:.5rem;background:#dc3545;border-color:#dc3545;color:#fff;">
                    <i class="fas fa-file-pdf"></i> Exportar PDF
                </a>
                <a href="{{ url_for('main.funcionario_rdo_consolidado') }}" class="btn-voltar">
                    <i class="fas fa-arrow-left"></i> Voltar
                </a>
            </div>
```

E, imediatamente após o fechamento do `<div class="page-header">` (a linha `</div>` que fecha o header, logo antes do comentário `<!-- Cards de Estatísticas -->`), acrescente o painel de assinaturas:

```html
    {# Fase 5 — evidência de assinatura #}
    {% if assinaturas_rdo %}
    <div class="card" style="margin:1rem 0;border-left:4px solid #198754;">
        <div class="card-body">
            <h5 style="margin-bottom:.75rem;">
                <i class="fas fa-signature"></i> Assinaturas
            </h5>
            <div class="table-responsive">
                <table class="table table-sm" style="margin-bottom:0;">
                    <thead>
                        <tr>
                            <th>Papel</th><th>Assinado por</th><th>Cargo</th>
                            <th>Data/hora (UTC)</th><th>IP</th><th>Hash SHA-256</th>
                        </tr>
                    </thead>
                    <tbody>
                    {% for a in assinaturas_rdo %}
                        <tr>
                            <td>{{ a.papel|capitalize }}</td>
                            <td>{{ a.nome_signatario }}</td>
                            <td>{{ a.cargo_signatario or '—' }}</td>
                            <td>{{ a.assinado_em.strftime('%d/%m/%Y %H:%M:%S') }}</td>
                            <td>{{ a.ip or '—' }}</td>
                            <td><code style="font-size:.75rem;">{{ a.hash_conteudo[:16] }}…</code></td>
                        </tr>
                    {% endfor %}
                    </tbody>
                </table>
            </div>
            {% if rdo.rdo_retificado_id %}
            <p style="margin:.75rem 0 0;">
                <i class="fas fa-file-pen"></i>
                Este RDO retifica o
                <a href="{{ url_for('main.visualizar_rdo', id=rdo.rdo_retificado_id) }}">RDO&nbsp;#{{ rdo.rdo_retificado_id }}</a>.
                Motivo: {{ rdo.motivo_retificacao }}
            </p>
            {% endif %}
        </div>
    </div>
    {% endif %}
```

- [ ] **Step 5: Imprima a assinatura eletrônica no PDF**

Em `services/rdo_pdf_service.py`, substitua a função `_signature_block` inteira (linhas 798-865, do `def _signature_block(rdo, config, styles):` até o `return KeepTogether(row)`) por:

```python
def _signature_block(rdo, config, styles):
    """Bloco de assinaturas no rodapé do conteúdo.

    Fase 5: quando existe `RDOAssinatura` (assinatura eletrônica com
    hash + carimbo de tempo + IP), o PDF imprime a EVIDÊNCIA — nome,
    papel, data/hora, IP e prefixo do hash — em vez da linha em branco
    para caneta. Sem assinatura eletrônica, o comportamento antigo é
    preservado integralmente: coluna do responsável pelo preenchimento +
    coluna do engenheiro responsável, com linha para assinar à mão.
    """
    assinaturas = list(getattr(rdo, 'assinaturas', None) or [])

    if assinaturas:
        cabecalho_style = ParagraphStyle(
            'sig_head', parent=styles['body'], fontSize=8, leading=10,
            textColor=INK)
        celula_style = ParagraphStyle(
            'sig_cell', parent=styles['body'], fontSize=7.5, leading=9.5,
            textColor=INK)

        linhas = [[
            Paragraph('<b>Papel</b>', cabecalho_style),
            Paragraph('<b>Assinado por</b>', cabecalho_style),
            Paragraph('<b>Data/hora (UTC)</b>', cabecalho_style),
            Paragraph('<b>IP</b>', cabecalho_style),
            Paragraph('<b>SHA-256</b>', cabecalho_style),
        ]]
        for a in assinaturas:
            quando = (a.assinado_em.strftime('%d/%m/%Y %H:%M:%S')
                      if a.assinado_em else '—')
            nome = a.nome_signatario or '—'
            if a.cargo_signatario:
                nome = f'{nome}<br/><font size="6.5">{a.cargo_signatario}</font>'
            linhas.append([
                Paragraph((a.papel or '').capitalize(), celula_style),
                Paragraph(nome, celula_style),
                Paragraph(quando, celula_style),
                Paragraph(a.ip or '—', celula_style),
                Paragraph((a.hash_conteudo or '')[:24] + '…', celula_style),
            ])

        tabela = Table(linhas, colWidths=[52, 150, 92, 72, 134])
        tabela.setStyle(TableStyle([
            ('LINEBELOW', (0, 0), (-1, 0), 0.6, INK),
            ('LINEBELOW', (0, 1), (-1, -1), 0.25, INK),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))

        nota = Paragraph(
            'Assinatura eletrônica com registro de autoria e verificação de '
            'integridade (SHA-256 sobre o conteúdo do RDO), nos termos do '
            'art. 10, §2º da MP 2.200-2/2001. Carimbo de tempo do servidor.',
            ParagraphStyle('sig_nota', parent=styles['body_muted'],
                           fontSize=6.5, leading=8.5))

        return KeepTogether([_section_rule('Assinaturas', styles), tabela,
                             Spacer(1, 4), nota])

    # ── Sem assinatura eletrônica: comportamento pré-Fase 5 ──────────
    responsavel_nome = rdo.criado_por.nome if rdo.criado_por else 'Responsável pelo preenchimento'
    responsavel_cargo = 'Apontador / Mestre de Obras'

    eng = None
    if config and config.engenheiro_padrao_id:
        eng = EngenheiroResponsavel.query.get(config.engenheiro_padrao_id)
    if not eng and config:
        if config.assinatura_nome:
            eng_nome = config.assinatura_nome
            eng_cargo = config.assinatura_cargo or 'Responsável Técnico'
            eng_crea = ''
        else:
            return None
    elif eng:
        eng_nome = eng.nome
        eng_cargo = 'Engenheiro Responsável'
        eng_crea = f'CREA {eng.crea}' if eng.crea else ''
    else:
        return None

    def sig_col(nome, cargo, extra=''):
        line_style = ParagraphStyle(
            'sigline', parent=styles['body'], alignment=1,
            fontSize=8.5, leading=11, textColor=INK,
        )
        cargo_style = ParagraphStyle(
            'sigcargo', parent=styles['body_muted'], alignment=1,
            fontSize=7.5, leading=10,
        )
        rule = Table([['']], colWidths=[200], rowHeights=[0.6])
        rule.setStyle(TableStyle([
            ('LINEABOVE', (0, 0), (-1, -1), 0.6, INK),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        inner = [
            [Spacer(1, 22)],
            [rule],
            [Paragraph(f'<b>{nome}</b>', line_style)],
            [Paragraph(cargo + (f' · {extra}' if extra else ''), cargo_style)],
        ]
        t = Table(inner, colWidths=[220])
        t.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        return t

    row = Table([[
        sig_col(responsavel_nome, responsavel_cargo),
        '',
        sig_col(eng_nome, eng_cargo, eng_crea),
    ]], colWidths=[220, 60, 220])
    row.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    return KeepTogether(row)
```

- [ ] **Step 6: Rode os testes**

```bash
python -m pytest tests/test_fase5_rdo_assinatura.py -v
```

Esperado: os 35 testes do arquivo PASSAM.

- [ ] **Step 7: Commit**

```bash
git add views/rdo.py templates/rdo/visualizar_rdo_moderno.html services/rdo_pdf_service.py tests/test_fase5_rdo_assinatura.py
git commit -m "feat(fase5): selo de estado, botoes de transicao e assinatura no PDF

Os botoes aparecem por papel na obra (Fase 1) e por estado — falha
fechada quando a autorizacao nao resolve. O PDF passa a imprimir a
evidencia (nome, papel, data/hora, IP, hash) em vez da linha em branco
para caneta; sem assinatura eletronica o bloco antigo e preservado."
```

---

# Bloco de risco — `rdo_foto` (Tasks 13 a 15)

> **Leia isto antes de tocar nas três tasks seguintes.**
>
> As Tasks 13 e 14 são seguras e podem rodar hoje: consertam bugs e param
> a sangria de dado novo. A **Task 15 é destrutiva** e tem pré-requisito
> de infra que **eu não consigo satisfazer** — depende do Cássio no painel
> do EasyPanel. Ela está escrita para ser executada em duas passadas
> reversíveis; não pule nenhuma.
>
> **O que eu medi** (banco de desenvolvimento, 2026-07-21):
>
> | | |
> |---|---|
> | `pg_database_size` | 16 GB |
> | `pg_total_relation_size('rdo_foto')` | **16 GB** |
> | `pg_relation_size('rdo_foto')` (heap) | 11 MB |
> | TOAST de `rdo_foto` (as três base64) | **16 GB** |
> | Fotos | 28.870, em 5.532 RDOs |
> | Fotos **com** caminho em disco preenchido | 28.860 |
> | Fotos **sem** caminho (base64-only, legado) | **10** |
> | Linha típica | original 313.615 + otimizada 122.983 + thumbnail 16.203 caracteres ≈ **442 KB** |
> | `du -sh static/uploads` | **13 GB** |
> | `UPLOADS_PATH` | **não definido** |
>
> Ou seja: o arquivo já está em disco em 99,97% dos casos. O banco carrega
> uma **duplicata** de 16 GB. Mas o disco é o filesystem efêmero do
> container — e foi exatamente por isso que a base64 nasceu
> (`models.py:1095-1096`). Apagar a base64 sem volume montado destrói a
> foto no primeiro deploy.

---

## Task 13: Consertar o armazenamento em disco (pré-requisito técnico)

**Files:**
- Modify: `services/rdo_foto_service.py` (nova função de resolução de caminho)
- Modify: `crud_rdo_completo.py:718-728`, `:804`, `:901`
- Modify: `models.py` (coluna `RDOFoto.armazenamento`)
- Modify: `migrations.py` (migration 264 + registro)
- Test: `tests/test_fase5_rdo_fotos.py`

- [ ] **Step 1: Escreva os testes que falham**

Crie `tests/test_fase5_rdo_fotos.py`:

```python
"""Fase 5 — armazenamento das fotos de RDO.

Medido em 2026-07-21 no banco de desenvolvimento:

    pg_total_relation_size('rdo_foto') = 16 GB   (TOAST = 16 GB)
    pg_relation_size('rdo_foto')       = 11 MB
    28.870 fotos, das quais 28.860 JÁ têm arquivo em disco
    du -sh static/uploads              = 13 GB
    UPLOADS_PATH                       = não definido

A base64 é duplicata do que já está em disco. O problema é que o disco é
efêmero (services/rdo_foto_service.py:21-53 cai em
`static/uploads/rdo` quando UPLOADS_PATH não existe) — e há um bug que
impede o volume de funcionar mesmo quando montado: `salvar_foto_rdo`
grava em `$UPLOADS_PATH/rdo/...` e `servir_foto`
(crud_rdo_completo.py:804) procura em `os.getcwd()/static/...`.
"""
import os
import sys
import uuid
from datetime import date
from io import BytesIO

import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os 54 blueprints antes de qualquer request
from app import app, db
from models import Cliente, Obra, RDO, RDOFoto, TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase5-fotos'
    yield


def _sfx():
    return uuid.uuid4().hex[:8]


def _admin():
    suf = _sfx()
    u = Usuario(
        username=f'f5p_{suf}', email=f'f5p_{suf}@test.local',
        nome=f'Admin Fotos {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id):
    suf = _sfx()
    cli = Cliente(nome=f'CLI-F5P-{suf}', admin_id=admin_id)
    db.session.add(cli)
    db.session.flush()
    o = Obra(nome=f'Obra Fotos {suf}', codigo=f'OP5{suf[:6].upper()}',
             data_inicio=date(2026, 1, 1), admin_id=admin_id,
             cliente_id=cli.id, valor_contrato=50000)
    db.session.add(o)
    db.session.commit()
    return o


def _rdo(obra, admin_id):
    r = RDO(numero_rdo=f'RDO-F5P-{_sfx()}', data_relatorio=date(2026, 6, 22),
            obra_id=obra.id, admin_id=admin_id, comentario_geral='Fotos')
    db.session.add(r)
    db.session.commit()
    return r


def _imagem_falsa(nome='foto.jpg', cor=(200, 30, 30)):
    buf = BytesIO()
    Image.new('RGB', (640, 480), cor).save(buf, format='JPEG')
    buf.seek(0)
    return FileStorage(stream=buf, filename=nome,
                       content_type='image/jpeg')


# ---------------------------------------------------------------------------
# Resolução de caminho
# ---------------------------------------------------------------------------

def test_caminho_absoluto_respeita_uploads_path(tmp_path, monkeypatch):
    """O bug que impede o volume de funcionar.

    `salvar_foto_rdo` grava em `$UPLOADS_PATH/rdo/...` mas devolve o
    caminho relativo `uploads/rdo/...`; `servir_foto`
    (crud_rdo_completo.py:804) montava
    `os.path.join(os.getcwd(), 'static', caminho)` — que ignora
    UPLOADS_PATH e vai procurar no lugar errado.
    """
    from services.rdo_foto_service import caminho_absoluto

    monkeypatch.setenv('UPLOADS_PATH', str(tmp_path))
    esperado = os.path.join(str(tmp_path), 'rdo', '7', '99', 'a.webp')
    assert caminho_absoluto('uploads/rdo/7/99/a.webp') == esperado


def test_caminho_absoluto_sem_uploads_path_usa_static(monkeypatch):
    from services.rdo_foto_service import caminho_absoluto

    monkeypatch.delenv('UPLOADS_PATH', raising=False)
    resultado = caminho_absoluto('uploads/rdo/7/99/a.webp')
    assert resultado.endswith(os.path.join('static', 'uploads', 'rdo', '7',
                                           '99', 'a.webp'))


def test_caminho_absoluto_recusa_travessia_de_diretorio(monkeypatch, tmp_path):
    """`caminho` vem do banco, mas nunca confie: path traversal."""
    from services.rdo_foto_service import caminho_absoluto

    monkeypatch.setenv('UPLOADS_PATH', str(tmp_path))
    assert caminho_absoluto('uploads/../../etc/passwd') is None
    assert caminho_absoluto('/etc/passwd') is None


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def test_upload_pela_rota_crud_grava_os_campos_not_null():
    """crud_rdo_completo.py:718 criava RDOFoto SEM nome_arquivo nem
    caminho_arquivo, que são NOT NULL no banco (verificado em
    information_schema). O INSERT estourava IntegrityError."""
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        rid, aid = rdo.id, admin.id

    cliente = app.test_client()
    with cliente.session_transaction() as sess:
        sess['_user_id'] = str(aid)
        sess['_fresh'] = True

    resposta = cliente.post(
        f'/rdo/{rid}/fotos/upload',
        data={'fotos[]': _imagem_falsa()},
        content_type='multipart/form-data')
    assert resposta.status_code == 201, (
        f'upload devolveu {resposta.status_code}: {resposta.get_data(as_text=True)[:300]}')

    with app.app_context():
        foto = RDOFoto.query.filter_by(rdo_id=rid).first()
        assert foto is not None
        assert foto.nome_arquivo, 'nome_arquivo (NOT NULL) ficou vazio'
        assert foto.caminho_arquivo, 'caminho_arquivo (NOT NULL) ficou vazio'


def test_coluna_armazenamento_existe_com_default_banco():
    with app.app_context():
        assert hasattr(RDOFoto, 'armazenamento')
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        f = RDOFoto(admin_id=admin.id, rdo_id=rdo.id,
                    nome_arquivo='x.webp', caminho_arquivo='uploads/rdo/x.webp')
        db.session.add(f)
        db.session.commit()
        assert f.armazenamento in ('banco', 'disco')


def test_backfill_da_migration_marcou_o_acervo():
    from sqlalchemy import text

    with app.app_context():
        nulos = db.session.execute(text(
            "SELECT count(*) FROM rdo_foto WHERE armazenamento IS NULL")).scalar()
        assert nulos == 0, f'{nulos} fotos ficaram sem marcador de armazenamento'
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase5_rdo_fotos.py -v
```

Esperado: FAIL — `ImportError: cannot import name 'caminho_absoluto'` e `AssertionError` na coluna `armazenamento`.

- [ ] **Step 3: Acrescente `caminho_absoluto` ao serviço de fotos**

Em `services/rdo_foto_service.py`, imediatamente após a linha 55 (`UPLOAD_BASE = get_upload_base()`), insira:

```python
def caminho_absoluto(caminho_relativo):
    """Resolve o caminho gravado no banco para um caminho absoluto real.

    Fase 5 — conserta a inconsistência que impede o volume persistente de
    funcionar. `salvar_foto_rdo` (linha 377) devolve sempre o relativo
    `uploads/rdo/<admin>/<rdo>/<arquivo>`, mas GRAVA em `UPLOAD_BASE`,
    que é `$UPLOADS_PATH/rdo` quando a variável existe. Quem serve a foto
    (crud_rdo_completo.py:804 e :901) montava
    `os.path.join(os.getcwd(), 'static', caminho)` — que só acerta quando
    UPLOADS_PATH está VAZIO. Definir a variável quebrava a exibição de
    todas as fotos, o que na prática impedia migrar para o volume.

    Devolve `None` para caminho vazio, absoluto ou com travessia de
    diretório — o valor vem do banco, mas isso não é motivo para confiar.
    """
    if not caminho_relativo:
        return None
    relativo = str(caminho_relativo).strip().lstrip('/')
    if not relativo or os.path.isabs(caminho_relativo):
        return None

    # `uploads/rdo/...` é o formato gravado; o prefixo `uploads/` mapeia
    # para a raiz de UPLOAD_BASE menos o sufixo 'rdo'.
    if relativo.startswith('uploads/'):
        sufixo = relativo[len('uploads/'):]
        base = os.path.dirname(UPLOAD_BASE)  # $UPLOADS_PATH ou .../static/uploads
        if os.environ.get('UPLOADS_PATH'):
            base = os.environ['UPLOADS_PATH']
            candidato = os.path.join(base, sufixo)
        else:
            candidato = os.path.join(os.getcwd(), 'static', relativo)
    else:
        candidato = os.path.join(os.getcwd(), 'static', relativo)

    candidato = os.path.normpath(candidato)
    raiz = os.path.normpath(
        os.environ.get('UPLOADS_PATH')
        or os.path.join(os.getcwd(), 'static', 'uploads'))
    if not candidato.startswith(raiz + os.sep) and candidato != raiz:
        logger.error("🚫 caminho fora da raiz de uploads recusado: %r",
                     caminho_relativo)
        return None
    return candidato
```

- [ ] **Step 4: Use `caminho_absoluto` em `crud_rdo_completo.py`**

Em `crud_rdo_completo.py`, substitua a linha 804:

```python
        caminho_completo = os.path.join(os.getcwd(), 'static', caminho)
```

por:

```python
        # Fase 5 — resolve por UPLOADS_PATH quando o volume está montado.
        from services.rdo_foto_service import caminho_absoluto
        caminho_completo = caminho_absoluto(caminho)
        if not caminho_completo:
            return "Caminho inválido", 400
```

E a linha 901, dentro de `deletar_foto`:

```python
                caminho_completo = os.path.join(os.getcwd(), 'static', caminho_rel)
```

por:

```python
                from services.rdo_foto_service import caminho_absoluto
                caminho_completo = caminho_absoluto(caminho_rel)
                if not caminho_completo:
                    continue
```

- [ ] **Step 5: Conserte o `INSERT` sem os campos NOT NULL**

Em `crud_rdo_completo.py`, substitua o bloco das linhas 718-728:

```python
                nova_foto = RDOFoto(
                    admin_id=admin_id,
                    rdo_id=rdo_id,
                    descricao=legenda,
                    arquivo_original=resultado['arquivo_original'],
                    arquivo_otimizado=resultado['arquivo_otimizado'],
                    thumbnail=resultado['thumbnail'],
                    nome_original=resultado['nome_original'],
                    tamanho_bytes=resultado['tamanho_bytes'],
                    ordem=fotos_existentes + len(fotos_criadas)
                )
```

por:

```python
                nova_foto = RDOFoto(
                    admin_id=admin_id,
                    rdo_id=rdo_id,
                    # Fase 5 — nome_arquivo e caminho_arquivo são NOT NULL
                    # no banco (information_schema conferido em
                    # 2026-07-21). Este INSERT estourava IntegrityError e
                    # a rota nunca chegou a salvar foto nenhuma.
                    nome_arquivo=resultado['nome_original'],
                    caminho_arquivo=resultado['arquivo_otimizado'],
                    descricao=legenda,
                    legenda=legenda,
                    arquivo_original=resultado['arquivo_original'],
                    arquivo_otimizado=resultado['arquivo_otimizado'],
                    thumbnail=resultado['thumbnail'],
                    nome_original=resultado['nome_original'],
                    tamanho_bytes=resultado['tamanho_bytes'],
                    ordem=fotos_existentes + len(fotos_criadas),
                    armazenamento='disco',
                )
```

- [ ] **Step 6: Acrescente a coluna `armazenamento` ao modelo**

Em `models.py`, dentro de `class RDOFoto`, imediatamente após a linha 1099 (`thumbnail_base64 = ...`), insira:

```python
    # ── Fase 5 — marcador de onde a foto realmente mora ───────────────
    # 'banco' = as colunas base64 acima são a fonte de verdade.
    # 'disco' = os caminhos arquivo_original/arquivo_otimizado/thumbnail
    #           são a fonte de verdade e a base64 pode ser liberada.
    #
    # Medido em 2026-07-21: rdo_foto ocupa 16 GB (TOAST), com 28.870
    # fotos das quais 28.860 JÁ têm arquivo em disco — a base64 é
    # duplicata. O marcador existe para que a migração
    # (scripts/migrar_fotos_rdo_para_disco.py) seja feita em duas
    # passadas reversíveis: primeiro marca 'disco' com a base64 ainda
    # presente, só depois libera o TEXT.
    armazenamento = db.Column(db.String(10), nullable=False, default='banco',
                              server_default='banco', index=True)
```

- [ ] **Step 7: Escreva a migration 264**

Em `migrations.py`, imediatamente antes de `def executar_migracoes():`, insira:

```python
def migration_264_rdo_foto_armazenamento():
    """Fase 5 — rdo_foto.armazenamento ('banco' | 'disco').

    APENAS o marcador. NÃO move nem apaga NADA — a migração de dado é
    feita por `scripts/migrar_fotos_rdo_para_disco.py`, que roda em
    dry-run por padrão e exige volume persistente montado.

    Backfill conservador: TUDO que tem base64 fica 'banco', mesmo já
    tendo arquivo em disco. Marcar 'disco' aqui declararia que o arquivo
    foi verificado — e neste ponto ninguém verificou.
    """
    logger.info("[Migration 264] Iniciando — rdo_foto.armazenamento")

    db.session.execute(text("""
        ALTER TABLE rdo_foto
        ADD COLUMN IF NOT EXISTS armazenamento VARCHAR(10)
    """))
    db.session.commit()

    com_base64 = db.session.execute(text("""
        UPDATE rdo_foto SET armazenamento = 'banco'
        WHERE armazenamento IS NULL
          AND (imagem_original_base64 IS NOT NULL
               OR imagem_otimizada_base64 IS NOT NULL
               OR thumbnail_base64 IS NOT NULL)
    """)).rowcount
    so_disco = db.session.execute(text("""
        UPDATE rdo_foto SET armazenamento = 'disco'
        WHERE armazenamento IS NULL
    """)).rowcount
    db.session.commit()
    logger.info("[Migration 264] backfill: %s marcadas 'banco', "
                "%s marcadas 'disco' (não tinham base64)",
                com_base64, so_disco)

    db.session.execute(text("""
        ALTER TABLE rdo_foto ALTER COLUMN armazenamento SET DEFAULT 'banco'
    """))
    db.session.execute(text("""
        ALTER TABLE rdo_foto ALTER COLUMN armazenamento SET NOT NULL
    """))
    db.session.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_rdo_foto_armazenamento
        ON rdo_foto (armazenamento)
    """))
    db.session.commit()

    logger.info("[Migration 264] Concluída com sucesso")
```

- [ ] **Step 8: Registre a migration**

Em `migrations.py`, na lista `migrations_to_run`, logo após a entrada `263`, adicione:

```python
            (264, "Fase 5 — rdo_foto.armazenamento ('banco'|'disco'): marcador da migração de fotos", migration_264_rdo_foto_armazenamento),
```

- [ ] **Step 9: Aplique e rode**

```bash
python -c "
from app import app
from migrations import executar_migracoes
with app.app_context():
    executar_migracoes()
" 2>&1 | grep -E "Migration 264|ERRO|ERROR"
python -m pytest tests/test_fase5_rdo_fotos.py -v
```

Esperado: `[Migration 264] Concluída com sucesso` com a contagem do backfill, e os 6 testes PASSAM.

- [ ] **Step 10: Commit**

```bash
git add services/rdo_foto_service.py crud_rdo_completo.py models.py migrations.py tests/test_fase5_rdo_fotos.py
git commit -m "fix(fase5): conserta o armazenamento em disco das fotos de RDO

caminho_absoluto() resolve por UPLOADS_PATH — antes, definir a variavel
quebrava a exibicao de TODAS as fotos, o que na pratica impedia migrar
para o volume persistente. Conserta tambem o INSERT de
crud_rdo_completo.py:718, que omitia nome_arquivo e caminho_arquivo (NOT
NULL). Migration 264 acrescenta o marcador rdo_foto.armazenamento sem
mover byte nenhum."
```

---

## Task 14: Parar de gravar base64 e parar de carregá-la em toda consulta

**Files:**
- Modify: `services/rdo_foto_service.py:365-395` (`salvar_foto_rdo`)
- Modify: `views/rdo.py:803-819` e `views/rdo.py:4536-4550`
- Modify: `models.py:1104` (`lazy` das fotos) e `models.py:1097-1099` (colunas deferred)
- Modify: `templates/rdo/visualizar_rdo_moderno.html:1806-1810` e `:1854`
- Modify: `templates/portal/_portal_rdos.html:19-22`
- Test: `tests/test_fase5_rdo_fotos.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente ao final de `tests/test_fase5_rdo_fotos.py`:

```python
# ---------------------------------------------------------------------------
# Parar a sangria
# ---------------------------------------------------------------------------

def test_upload_novo_nao_grava_base64():
    """A partir da Fase 5, foto nova vai só para o disco."""
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        rid, aid = rdo.id, admin.id

    cliente = app.test_client()
    with cliente.session_transaction() as sess:
        sess['_user_id'] = str(aid)
        sess['_fresh'] = True
    cliente.post(f'/rdo/{rid}/fotos/upload',
                 data={'fotos[]': _imagem_falsa()},
                 content_type='multipart/form-data')

    with app.app_context():
        foto = RDOFoto.query.filter_by(rdo_id=rid).first()
        assert foto is not None
        assert foto.imagem_original_base64 is None, (
            'upload novo ainda grava base64 — 442 KB por foto no banco')
        assert foto.imagem_otimizada_base64 is None
        assert foto.thumbnail_base64 is None
        assert foto.armazenamento == 'disco'
        assert foto.arquivo_otimizado


def test_salvar_foto_rdo_nao_devolve_mais_base64(tmp_path, monkeypatch):
    from services.rdo_foto_service import salvar_foto_rdo

    monkeypatch.setenv('UPLOADS_PATH', str(tmp_path))
    with app.app_context():
        resultado = salvar_foto_rdo(_imagem_falsa(), 1, 1)
    assert 'imagem_original_base64' not in resultado
    assert 'imagem_otimizada_base64' not in resultado
    assert 'thumbnail_base64' not in resultado
    assert resultado['arquivo_otimizado'].startswith('uploads/rdo/1/1/')


def test_consulta_de_rdo_nao_carrega_base64_por_padrao():
    """models.py:1104 era lazy='selectin': TODA consulta de RDO puxava as
    três colunas TEXT de todas as fotos — inclusive a listagem paginada
    de crud_rdo_completo.py:80."""
    from sqlalchemy import inspect as sa_inspect

    with app.app_context():
        mapper = sa_inspect(RDOFoto)
        for coluna in ('imagem_original_base64', 'imagem_otimizada_base64',
                       'thumbnail_base64'):
            assert mapper.attrs[coluna].deferred is True, (
                f'{coluna} não está deferred — continua vindo em toda query')

        relacao = sa_inspect(RDO).relationships['fotos']
        assert relacao.lazy != 'selectin', (
            'RDO.fotos ainda é selectin: cada listagem de RDO puxa o TOAST '
            'inteiro das fotos')


def test_url_da_foto_e_servida_do_disco():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        rid, aid = rdo.id, admin.id

    cliente = app.test_client()
    with cliente.session_transaction() as sess:
        sess['_user_id'] = str(aid)
        sess['_fresh'] = True
    cliente.post(f'/rdo/{rid}/fotos/upload',
                 data={'fotos[]': _imagem_falsa()},
                 content_type='multipart/form-data')

    with app.app_context():
        foto_id = RDOFoto.query.filter_by(rdo_id=rid).first().id

    resposta = cliente.get(f'/rdo/foto/{foto_id}/thumbnail')
    assert resposta.status_code == 200, (
        f'servir_foto devolveu {resposta.status_code} — a foto não está '
        f'sendo encontrada no disco')
    assert resposta.headers['Content-Type'].startswith('image/')


def test_tela_do_rdo_usa_url_e_nao_data_uri():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        rid, aid = rdo.id, admin.id

    cliente = app.test_client()
    with cliente.session_transaction() as sess:
        sess['_user_id'] = str(aid)
        sess['_fresh'] = True
    cliente.post(f'/rdo/{rid}/fotos/upload',
                 data={'fotos[]': _imagem_falsa()},
                 content_type='multipart/form-data')

    corpo = cliente.get(f'/rdo/{rid}').get_data(as_text=True)
    assert '/rdo/foto/' in corpo, 'a tela não usa a URL de servir_foto'
    assert 'data:image/webp;base64' not in corpo, (
        'a tela ainda embute a imagem inteira no HTML')
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase5_rdo_fotos.py -v -k "base64 or url or deferred or carrega"
```

Esperado: FAIL — o upload ainda grava base64 e o HTML ainda traz `data:image/webp;base64`.

- [ ] **Step 3: Pare de gerar base64 no upload**

Em `services/rdo_foto_service.py`, substitua o bloco final de `salvar_foto_rdo` (linhas 365-395, do comentário `# 7. Processar versões Base64` até o `return resultado`) por:

```python
    # ── Fase 5 — base64 NÃO é mais gerada no upload ──────────────────
    # Até 2026-07-21 esta função gerava, além dos três arquivos em disco,
    # TRÊS cópias base64 do mesmo conteúdo, gravadas em colunas TEXT.
    # Medição do banco de desenvolvimento nesse dia:
    #   pg_total_relation_size('rdo_foto') = 16 GB (TOAST = 16 GB)
    #   28.870 fotos × ~442 KB de base64 cada
    #   28.860 delas JÁ tinham o arquivo em disco — pura duplicata.
    # A função `processar_imagem_base64` continua existindo: é o que o
    # script de migração usa para RECUPERAR as 10 fotos legadas que só
    # existem em base64, e o caminho de restauração de emergência.

    base_relativo = f"uploads/rdo/{admin_id}/{rdo_id}"

    resultado = {
        'arquivo_original': f"{base_relativo}/{os.path.basename(caminho_original)}",
        'arquivo_otimizado': f"{base_relativo}/{os.path.basename(caminho_otimizado)}",
        'thumbnail': f"{base_relativo}/{os.path.basename(caminho_thumbnail)}",
        'nome_original': file.filename,
        'tamanho_bytes': tamanho,
    }

    logger.info("✅ Foto processada (disco): %s → %s (%s bytes)",
                file.filename, resultado['arquivo_otimizado'], tamanho)
    return resultado
```

- [ ] **Step 4: Pare de gravar base64 nos dois construtores de `views/rdo.py`**

Em `views/rdo.py`, no bloco das linhas 803-819 (dentro de `criar_rdo`), substitua a construção do `RDOFoto` por:

```python
                        nova_foto = RDOFoto(
                            admin_id=admin_id,
                            rdo_id=rdo.id,
                            # NOT NULL no banco.
                            nome_arquivo=resultado['nome_original'],
                            caminho_arquivo=resultado['arquivo_otimizado'],
                            descricao='',
                            arquivo_original=resultado['arquivo_original'],
                            arquivo_otimizado=resultado['arquivo_otimizado'],
                            thumbnail=resultado['thumbnail'],
                            nome_original=resultado['nome_original'],
                            tamanho_bytes=resultado['tamanho_bytes'],
                            # Fase 5 — sem base64. Ver
                            # services/rdo_foto_service.salvar_foto_rdo.
                            armazenamento='disco',
                        )
```

E, em `views/rdo.py`, no bloco das linhas 4536-4550 (dentro de `salvar_rdo_flexivel`), substitua a construção por:

```python
                            nova_foto = RDOFoto(
                                admin_id=admin_id,
                                rdo_id=rdo.id,
                                nome_arquivo=resultado['nome_original'],
                                caminho_arquivo=resultado['arquivo_otimizado'],
                                descricao=legenda,
                                legenda=legenda,
                                arquivo_original=resultado['arquivo_original'],
                                arquivo_otimizado=resultado['arquivo_otimizado'],
                                thumbnail=resultado['thumbnail'],
                                nome_original=resultado['nome_original'],
                                tamanho_bytes=resultado['tamanho_bytes'],
                                # Fase 5 — sem base64.
                                armazenamento='disco',
                            )
```

- [ ] **Step 5: Pare de carregar a base64 em toda consulta**

Em `models.py`, substitua as linhas 1097-1099:

```python
    imagem_original_base64 = db.Column(db.Text)  # Backup completo da imagem original
    imagem_otimizada_base64 = db.Column(db.Text)  # Versão otimizada (1200px) para visualização
    thumbnail_base64 = db.Column(db.Text)  # Miniatura (300px) para listagem rápida
```

por:

```python
    # ── Fase 5 — LEGADO em processo de migração ──────────────────────
    # `db.deferred(...)`: estas três colunas TEXT somam 16 GB (medido em
    # 2026-07-21) e NÃO podem vir em toda consulta. Elas só carregam
    # quando explicitamente acessadas — o que hoje só acontece no script
    # de migração e no caminho de fallback de `servir_foto`.
    #
    # ATENÇÃO: é `db.deferred(db.Column(...))`, NÃO
    # `db.Column(..., deferred=True)`. Conferido nesta versão
    # (SQLAlchemy 2.0.41 + Flask-SQLAlchemy 3.1.1): passar `deferred` como
    # kwarg de Column levanta
    # `TypeError: Additional arguments should be named <dialectname>_<argument>`.
    imagem_original_base64 = db.deferred(db.Column(db.Text))
    imagem_otimizada_base64 = db.deferred(db.Column(db.Text))
    thumbnail_base64 = db.deferred(db.Column(db.Text))
```

E substitua a linha 1104:

```python
    rdo = db.relationship('RDO', backref=db.backref('fotos', lazy='selectin', order_by='RDOFoto.ordem', cascade='all, delete-orphan', passive_deletes=True))
```

por:

```python
    # Fase 5 — `lazy='selectin'` fazia TODA consulta de RDO (inclusive a
    # listagem paginada de crud_rdo_completo.py:80) carregar as fotos de
    # todos os RDOs da página. Com as colunas base64 deferred isso ficou
    # barato, mas 'select' evita o SELECT extra quando ninguém pede foto.
    rdo = db.relationship('RDO', backref=db.backref(
        'fotos', lazy='select', order_by='RDOFoto.ordem',
        cascade='all, delete-orphan', passive_deletes=True))
```

- [ ] **Step 6: Sirva a foto por URL nos templates**

Em `templates/rdo/visualizar_rdo_moderno.html`, substitua o bloco das linhas 1806-1810 (a `<img>` do thumbnail) por:

```html
                        {% if foto.armazenamento == 'disco' or foto.thumbnail %}
                            <img src="{{ url_for('rdo_crud.servir_foto', foto_id=foto.id, tipo='thumbnail') }}"
                                 alt="{{ foto.descricao or foto.legenda or 'Foto do RDO' }}"
                                 loading="lazy"
                                 style="width:100%;height:150px;object-fit:cover;border-radius:6px;">
                        {% elif foto.thumbnail_base64 %}
                            <img src="{{ foto.thumbnail_base64 }}"
                                 alt="{{ foto.descricao or foto.legenda or 'Foto do RDO' }}"
                                 loading="lazy"
                                 style="width:100%;height:150px;object-fit:cover;border-radius:6px;">
```

E, na linha 1854, substitua a `<img>` do lightbox por:

```html
        {% if foto.armazenamento == 'disco' or foto.arquivo_otimizado %}
            <img src="{{ url_for('rdo_crud.servir_foto', foto_id=foto.id, tipo='otimizado') }}"
                 alt="{{ foto.descricao or foto.legenda or 'Foto do RDO' }}"
                 class="img-fluid">
        {% elif foto.imagem_otimizada_base64 %}
            <img src="{{ foto.imagem_otimizada_base64 }}"
                 alt="{{ foto.descricao or foto.legenda or 'Foto do RDO' }}"
                 class="img-fluid">
```

Em `templates/portal/_portal_rdos.html`, substitua as linhas 19-22 por:

```html
                    {% if foto.armazenamento == 'disco' or foto.thumbnail %}
                    <img src="{{ url_for('portal_obras.portal_foto', token=obra.token_portal, foto_id=foto.id) }}" alt="" loading="lazy">
                    {% elif foto.thumbnail_base64 %}
                    <img src="{{ foto.thumbnail_base64 if foto.thumbnail_base64.startswith('data:') else 'data:image/webp;base64,' ~ foto.thumbnail_base64 }}" alt="">
                    {% endif %}
```

> **Nota sobre o portal:** `portal_obras.portal_foto` **não existe** — o portal serve por token, não por login, e `rdo_crud.servir_foto` exige `@login_required` (`crud_rdo_completo.py:790`). Criar essa rota é trabalho da Fase 9a, junto do login de cliente. **Até lá, deixe o portal como está** e aplique só a mudança de `templates/rdo/visualizar_rdo_moderno.html`. Isto está escrito aqui para que a dívida fique registrada no lugar certo, não para ser executado agora.

- [ ] **Step 7: Rode os testes**

```bash
python -m pytest tests/test_fase5_rdo_fotos.py -v
python -m pytest tests/ -m "not browser" -k "foto or importacao_fisico" -q 2>&1 | tail -20
```

Esperado: `test_fase5_rdo_fotos.py` verde. Na segunda linha, atenção a
`tests/test_importacao_fisico_financeiro.py::test_import_anexa_fotos_do_rdo`:
`services/importacao_fisico_financeiro.py:370-386` passa
`imagem_original_base64=res['imagem_original_base64']` — chave que não
existe mais no retorno. Corrija ali substituindo as três linhas de base64
por `armazenamento='disco',` e removendo-as de `_FOTO_COLS`
(`services/importacao_fisico_financeiro.py:394-397`).

- [ ] **Step 8: Commit**

```bash
git add services/rdo_foto_service.py views/rdo.py models.py templates/rdo/visualizar_rdo_moderno.html services/importacao_fisico_financeiro.py tests/test_fase5_rdo_fotos.py
git commit -m "perf(fase5): foto de RDO nova vai so para o disco

Para a sangria: cada upload gravava ~442 KB de base64 em tres colunas
TEXT alem dos tres arquivos em disco. As colunas legadas viram deferred e
RDO.fotos deixa de ser selectin — a listagem paginada de RDO nao puxa
mais o TOAST. A tela passa a servir a foto por URL em vez de embutir a
imagem inteira no HTML. NENHUM dado antigo e apagado aqui."
```

---

## Task 15: ⚠️ Backfill das fotos legadas (DESTRUTIVA — depende de infra)

> **Esta task NÃO pode ser executada sem os pré-requisitos abaixo
> satisfeitos e conferidos pelo Cássio.** Ela é o único ponto desta fase
> que apaga dado. Os passos 1-6 são reversíveis; o passo 7 não é.

**Pré-requisitos de infra — bloqueantes, humanos:**

| # | Pré-requisito | Como conferir |
|---|---|---|
| 1 | Volume persistente montado no container, com **≥ 25 GB** livres | `df -h $UPLOADS_PATH` |
| 2 | `UPLOADS_PATH` definido no painel do EasyPanel apontando para esse volume | `echo $UPLOADS_PATH` dentro do container |
| 3 | Task 13 aplicada (`caminho_absoluto`) — **senão as fotos somem da tela no instante em que a variável for definida** | `python -m pytest tests/test_fase5_rdo_fotos.py -k caminho -v` |
| 4 | Dump COMPLETO do banco (com as fotos) guardado fora do servidor | `python scripts/backup_banco.py` — 16 GB, **não** use `--sem-fotos` |
| 5 | Snapshot do volume confirmado com a Hostinger | pendência já registrada em `ESTADO-ATUAL.md:38-42` |
| 6 | Janela de manutenção: o passo 7 faz `VACUUM FULL`, que **trava a tabela** | combinado com o Cássio |

**Files:**
- Create: `scripts/migrar_fotos_rdo_para_disco.py`
- Test: `tests/test_fase5_rdo_fotos.py` (acrescenta)

- [ ] **Step 1: Escreva os testes que falham**

Acrescente ao final de `tests/test_fase5_rdo_fotos.py`:

```python
# ---------------------------------------------------------------------------
# Backfill (tarefa de risco)
# ---------------------------------------------------------------------------

def _foto_base64_only(admin_id, rdo_id, ordem=0):
    """Foto legada: existe SÓ em base64, sem arquivo em disco."""
    import base64
    from io import BytesIO

    from PIL import Image
    buf = BytesIO()
    Image.new('RGB', (320, 240), (10, 120, 200)).save(buf, format='WEBP')
    dados = base64.b64encode(buf.getvalue()).decode('utf-8')
    uri = f'data:image/webp;base64,{dados}'
    f = RDOFoto(admin_id=admin_id, rdo_id=rdo_id,
                nome_arquivo='legada.webp', caminho_arquivo='legada.webp',
                nome_original='legada.jpg', descricao='foto legada',
                ordem=ordem, armazenamento='banco',
                imagem_original_base64=uri, imagem_otimizada_base64=uri,
                thumbnail_base64=uri)
    db.session.add(f)
    db.session.commit()
    return f


def test_migrar_dry_run_nao_escreve(tmp_path, monkeypatch):
    from scripts.migrar_fotos_rdo_para_disco import migrar_para_disco

    monkeypatch.setenv('UPLOADS_PATH', str(tmp_path))
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        foto = _foto_base64_only(admin.id, rdo.id)
        fid = foto.id

        relatorio = migrar_para_disco(admin_id=admin.id, aplicar=False)
        assert relatorio['migradas'] >= 1
        db.session.expire_all()
        recarregada = db.session.get(RDOFoto, fid)
        assert recarregada.armazenamento == 'banco'
        assert recarregada.imagem_otimizada_base64 is not None


def test_migrar_escreve_o_arquivo_e_marca_disco(tmp_path, monkeypatch):
    from services.rdo_foto_service import caminho_absoluto
    from scripts.migrar_fotos_rdo_para_disco import migrar_para_disco

    monkeypatch.setenv('UPLOADS_PATH', str(tmp_path))
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        foto = _foto_base64_only(admin.id, rdo.id)
        fid = foto.id

        migrar_para_disco(admin_id=admin.id, aplicar=True)
        db.session.expire_all()
        recarregada = db.session.get(RDOFoto, fid)
        assert recarregada.armazenamento == 'disco'
        # Passada 1 NÃO libera a base64 — reversibilidade.
        assert recarregada.imagem_otimizada_base64 is not None
        for campo in ('arquivo_original', 'arquivo_otimizado', 'thumbnail'):
            caminho = caminho_absoluto(getattr(recarregada, campo))
            assert caminho and os.path.exists(caminho), (
                f'{campo} não foi escrito em disco')
            assert os.path.getsize(caminho) > 0


def test_migrar_e_idempotente(tmp_path, monkeypatch):
    from scripts.migrar_fotos_rdo_para_disco import migrar_para_disco

    monkeypatch.setenv('UPLOADS_PATH', str(tmp_path))
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        _foto_base64_only(admin.id, rdo.id)

        migrar_para_disco(admin_id=admin.id, aplicar=True)
        segunda = migrar_para_disco(admin_id=admin.id, aplicar=True)
        assert segunda['migradas'] == 0


def test_verificar_recusa_liberar_quando_o_arquivo_sumiu(tmp_path, monkeypatch):
    """A trava que impede perder a foto."""
    from services.rdo_foto_service import caminho_absoluto
    from scripts.migrar_fotos_rdo_para_disco import (liberar_base64,
                                                     migrar_para_disco)

    monkeypatch.setenv('UPLOADS_PATH', str(tmp_path))
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        foto = _foto_base64_only(admin.id, rdo.id)
        migrar_para_disco(admin_id=admin.id, aplicar=True)
        db.session.expire_all()
        fid = foto.id

        # Simula perda do arquivo (deploy sem volume montado).
        alvo = caminho_absoluto(db.session.get(RDOFoto, fid).arquivo_otimizado)
        os.remove(alvo)

        relatorio = liberar_base64(admin_id=admin.id, aplicar=True)
        assert relatorio['liberadas'] == 0
        assert relatorio['recusadas'] >= 1
        db.session.expire_all()
        assert db.session.get(RDOFoto, fid).imagem_otimizada_base64 is not None, (
            'a base64 foi apagada com o arquivo ausente — perda de dado')


def test_liberar_base64_zera_as_tres_colunas(tmp_path, monkeypatch):
    from scripts.migrar_fotos_rdo_para_disco import (liberar_base64,
                                                     migrar_para_disco)

    monkeypatch.setenv('UPLOADS_PATH', str(tmp_path))
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        foto = _foto_base64_only(admin.id, rdo.id)
        fid = foto.id

        migrar_para_disco(admin_id=admin.id, aplicar=True)
        relatorio = liberar_base64(admin_id=admin.id, aplicar=True)
        assert relatorio['liberadas'] >= 1

        db.session.expire_all()
        r = db.session.get(RDOFoto, fid)
        assert r.imagem_original_base64 is None
        assert r.imagem_otimizada_base64 is None
        assert r.thumbnail_base64 is None
        assert r.armazenamento == 'disco'


def test_reverter_volta_para_banco(tmp_path, monkeypatch):
    """Rollback da passada 1: enquanto a base64 existir, é um comando."""
    from scripts.migrar_fotos_rdo_para_disco import migrar_para_disco, reverter

    monkeypatch.setenv('UPLOADS_PATH', str(tmp_path))
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        foto = _foto_base64_only(admin.id, rdo.id)
        fid = foto.id

        migrar_para_disco(admin_id=admin.id, aplicar=True)
        relatorio = reverter(admin_id=admin.id, aplicar=True)
        assert relatorio['revertidas'] >= 1
        db.session.expire_all()
        assert db.session.get(RDOFoto, fid).armazenamento == 'banco'
```

- [ ] **Step 2: Rode e confirme a falha**

```bash
python -m pytest tests/test_fase5_rdo_fotos.py -v -k "migrar or liberar or reverter or verificar_recusa"
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'scripts.migrar_fotos_rdo_para_disco'`.

- [ ] **Step 3: Escreva o script**

Crie `scripts/migrar_fotos_rdo_para_disco.py`:

```python
#!/usr/bin/env python3
"""Migração de `rdo_foto` de base64 no banco para arquivo em disco.

═══════════════════════════════════════════════════════════════════════
POR QUE ISTO EXISTE (medido em 2026-07-21, banco de desenvolvimento)
═══════════════════════════════════════════════════════════════════════

    pg_database_size(current_database())  = 16 GB
    pg_total_relation_size('rdo_foto')    = 16 GB   ← praticamente tudo
    pg_relation_size('rdo_foto') (heap)   = 11 MB
    TOAST de rdo_foto                     = 16 GB   ← as três base64
    28.870 fotos em 5.532 RDOs
    28.860 já com arquivo em disco · 10 só em base64
    linha típica: 313.615 + 122.983 + 16.203 chars ≈ 442 KB

Isso define o RPO real do backup: um dump completo é de 16 GB e não cabe
em janela curta. As colunas de caminho (`arquivo_original`,
`arquivo_otimizado`, `thumbnail`) já existem e já estão preenchidas.

═══════════════════════════════════════════════════════════════════════
DUAS PASSADAS, PORQUE A PRIMEIRA É REVERSÍVEL E A SEGUNDA NÃO
═══════════════════════════════════════════════════════════════════════

  Passada 1 — `migrar_para_disco()`
      Garante que o arquivo existe em disco (escrevendo a partir da
      base64 quando faltar), VERIFICA que ele abre como imagem, e marca
      `armazenamento='disco'`. A base64 continua no banco.
      Rollback: `reverter()`, um comando.

  Passada 2 — `liberar_base64()`  ⚠️ DESTRUTIVA
      Para cada foto marcada 'disco', reverifica os três arquivos e só
      então zera as três colunas TEXT. Recusa qualquer foto cujo arquivo
      não abra. Depois disso, a foto SÓ existe no volume — se o volume
      não for persistente, o próximo deploy destrói o acervo.

PRÉ-REQUISITOS DA PASSADA 2 (ver docs/fase-5-rollout.md):
  volume persistente montado · UPLOADS_PATH definido · Task 13 aplicada ·
  dump completo guardado fora do servidor · snapshot do volume ·
  janela de manutenção para o VACUUM FULL.

Uso:
    python scripts/migrar_fotos_rdo_para_disco.py --admin-id 7
    python scripts/migrar_fotos_rdo_para_disco.py --admin-id 7 --aplicar
    python scripts/migrar_fotos_rdo_para_disco.py --admin-id 7 --liberar
    python scripts/migrar_fotos_rdo_para_disco.py --admin-id 7 --liberar --aplicar
    python scripts/migrar_fotos_rdo_para_disco.py --admin-id 7 --reverter --aplicar
"""
from __future__ import annotations

import argparse
import base64
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('migrar_fotos_rdo')

LOTE_PADRAO = 200


def _decodificar(valor):
    """Bytes de uma coluna base64 (com ou sem prefixo data URI)."""
    if not valor:
        return None
    texto = valor.split(',', 1)[1] if ',' in valor[:64] else valor
    try:
        return base64.b64decode(texto)
    except Exception:
        logger.warning('base64 ilegível — ignorada')
        return None


def _escrever(caminho_absoluto_alvo, dados):
    os.makedirs(os.path.dirname(caminho_absoluto_alvo), exist_ok=True)
    temporario = caminho_absoluto_alvo + '.parcial'
    with open(temporario, 'wb') as fh:
        fh.write(dados)
    os.replace(temporario, caminho_absoluto_alvo)


def _arquivo_valido(caminho):
    """True se o arquivo existe, tem bytes e abre como imagem."""
    if not caminho or not os.path.exists(caminho):
        return False
    try:
        if os.path.getsize(caminho) <= 0:
            return False
        from PIL import Image
        with Image.open(caminho) as img:
            img.verify()
        return True
    except Exception:
        return False


# Mapa: coluna de caminho → coluna base64 correspondente + sufixo do nome.
_TRIO = (
    ('arquivo_original', 'imagem_original_base64', '_original.webp'),
    ('arquivo_otimizado', 'imagem_otimizada_base64', '.webp'),
    ('thumbnail', 'thumbnail_base64', '_thumb.webp'),
)


def migrar_para_disco(admin_id=None, aplicar=False, lote=LOTE_PADRAO,
                      limite=None):
    """Passada 1 — REVERSÍVEL. Garante o arquivo em disco e marca 'disco'."""
    from app import app, db
    from models import RDOFoto
    from services.rdo_foto_service import caminho_absoluto

    relatorio = {'analisadas': 0, 'migradas': 0, 'ja_em_disco': 0,
                 'falhas': [], 'aplicar': aplicar}

    with app.app_context():
        query = RDOFoto.query.filter(RDOFoto.armazenamento == 'banco')
        if admin_id is not None:
            query = query.filter(RDOFoto.admin_id == admin_id)
        query = query.order_by(RDOFoto.id.asc())
        if limite:
            query = query.limit(limite)

        pendentes = query.all()
        logger.info('%s foto(s) marcadas "banco"%s', len(pendentes),
                    f' no tenant {admin_id}' if admin_id else '')

        for indice, foto in enumerate(pendentes, start=1):
            relatorio['analisadas'] += 1
            base_relativa = f'uploads/rdo/{foto.admin_id}/{foto.rdo_id}'
            nome_base = os.path.splitext(
                os.path.basename(foto.arquivo_otimizado
                                 or foto.nome_arquivo
                                 or f'foto{foto.id}'))[0]

            caminhos_ok = True
            atualizacoes = {}
            for coluna_caminho, coluna_b64, sufixo in _TRIO:
                relativo = getattr(foto, coluna_caminho, None)
                if not relativo:
                    relativo = f'{base_relativa}/{nome_base}{sufixo}'
                    atualizacoes[coluna_caminho] = relativo
                alvo = caminho_absoluto(relativo)
                if alvo is None:
                    caminhos_ok = False
                    relatorio['falhas'].append(
                        {'foto_id': foto.id, 'motivo': 'caminho_invalido',
                         'caminho': relativo})
                    break
                if _arquivo_valido(alvo):
                    continue
                dados = _decodificar(getattr(foto, coluna_b64, None))
                if dados is None:
                    caminhos_ok = False
                    relatorio['falhas'].append(
                        {'foto_id': foto.id, 'motivo': 'sem_origem',
                         'coluna': coluna_b64})
                    break
                if aplicar:
                    _escrever(alvo, dados)
                    if not _arquivo_valido(alvo):
                        caminhos_ok = False
                        relatorio['falhas'].append(
                            {'foto_id': foto.id, 'motivo': 'escrita_invalida',
                             'caminho': relativo})
                        break

            if not caminhos_ok:
                continue

            relatorio['migradas'] += 1
            if aplicar:
                for coluna, valor in atualizacoes.items():
                    setattr(foto, coluna, valor)
                foto.armazenamento = 'disco'
                if indice % lote == 0:
                    db.session.commit()
                    logger.info('… %s/%s', indice, len(pendentes))

        if aplicar:
            db.session.commit()

    logger.info('passada 1: %s analisada(s), %s migrada(s), %s falha(s) '
                '[%s]', relatorio['analisadas'], relatorio['migradas'],
                len(relatorio['falhas']),
                'APLICADO' if aplicar else 'DRY-RUN')
    return relatorio


def liberar_base64(admin_id=None, aplicar=False, lote=LOTE_PADRAO,
                   limite=None):
    """Passada 2 — ⚠️ DESTRUTIVA. Zera as três colunas TEXT.

    Só libera a foto cujos TRÊS arquivos abram como imagem AGORA. Uma
    foto cujo arquivo sumiu mantém a base64 e entra em `recusadas`.
    """
    from app import app, db
    from models import RDOFoto
    from services.rdo_foto_service import caminho_absoluto

    relatorio = {'analisadas': 0, 'liberadas': 0, 'recusadas': 0,
                 'detalhe_recusas': [], 'aplicar': aplicar}

    with app.app_context():
        query = RDOFoto.query.filter(RDOFoto.armazenamento == 'disco')
        if admin_id is not None:
            query = query.filter(RDOFoto.admin_id == admin_id)
        query = query.order_by(RDOFoto.id.asc())
        if limite:
            query = query.limit(limite)

        candidatas = query.all()
        logger.info('%s foto(s) marcadas "disco"%s', len(candidatas),
                    f' no tenant {admin_id}' if admin_id else '')

        for indice, foto in enumerate(candidatas, start=1):
            relatorio['analisadas'] += 1
            faltando = [
                coluna for coluna, _b64, _s in _TRIO
                if not _arquivo_valido(caminho_absoluto(getattr(foto, coluna, None)))
            ]
            if faltando:
                relatorio['recusadas'] += 1
                relatorio['detalhe_recusas'].append(
                    {'foto_id': foto.id, 'rdo_id': foto.rdo_id,
                     'faltando': faltando})
                logger.warning('foto %s RECUSADA — arquivo ausente: %s',
                               foto.id, faltando)
                continue

            relatorio['liberadas'] += 1
            if aplicar:
                foto.imagem_original_base64 = None
                foto.imagem_otimizada_base64 = None
                foto.thumbnail_base64 = None
                if indice % lote == 0:
                    db.session.commit()
                    logger.info('… %s/%s', indice, len(candidatas))

        if aplicar:
            db.session.commit()

    logger.info('passada 2: %s analisada(s), %s liberada(s), %s recusada(s) '
                '[%s]', relatorio['analisadas'], relatorio['liberadas'],
                relatorio['recusadas'],
                'APLICADO' if aplicar else 'DRY-RUN')
    if relatorio['recusadas']:
        logger.error('⚠️ %s foto(s) recusadas — resolva ANTES de seguir',
                     relatorio['recusadas'])
    return relatorio


def reverter(admin_id=None, aplicar=False):
    """Rollback da passada 1: volta 'disco' → 'banco'.

    Só faz sentido enquanto a base64 ainda estiver lá. Fotos já liberadas
    (base64 nula) não são revertidas — não há para onde voltar.
    """
    from app import app, db
    from models import RDOFoto

    relatorio = {'revertidas': 0, 'sem_base64': 0, 'aplicar': aplicar}

    with app.app_context():
        query = RDOFoto.query.filter(RDOFoto.armazenamento == 'disco')
        if admin_id is not None:
            query = query.filter(RDOFoto.admin_id == admin_id)
        for foto in query.order_by(RDOFoto.id.asc()).all():
            if foto.imagem_otimizada_base64 is None:
                relatorio['sem_base64'] += 1
                continue
            relatorio['revertidas'] += 1
            if aplicar:
                foto.armazenamento = 'banco'
        if aplicar:
            db.session.commit()

    logger.info('reversão: %s revertida(s), %s sem base64 [%s]',
                relatorio['revertidas'], relatorio['sem_base64'],
                'APLICADO' if aplicar else 'DRY-RUN')
    return relatorio


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--admin-id', type=int, default=None,
                        help='limita a um tenant (recomendado)')
    parser.add_argument('--aplicar', action='store_true',
                        help='sem esta flag, roda em DRY-RUN')
    parser.add_argument('--liberar', action='store_true',
                        help='passada 2: zera a base64 (DESTRUTIVO)')
    parser.add_argument('--reverter', action='store_true',
                        help='rollback da passada 1')
    parser.add_argument('--lote', type=int, default=LOTE_PADRAO)
    parser.add_argument('--limite', type=int, default=None,
                        help='processa no máximo N fotos (ensaio)')
    args = parser.parse_args()

    if args.liberar and args.aplicar and not os.environ.get('UPLOADS_PATH'):
        logger.error('❌ UPLOADS_PATH não definido. Liberar a base64 sem '
                     'volume persistente montado APAGA as fotos no próximo '
                     'deploy. Abortado.')
        return 2

    if args.reverter:
        relatorio = reverter(admin_id=args.admin_id, aplicar=args.aplicar)
    elif args.liberar:
        relatorio = liberar_base64(admin_id=args.admin_id,
                                   aplicar=args.aplicar, lote=args.lote,
                                   limite=args.limite)
    else:
        relatorio = migrar_para_disco(admin_id=args.admin_id,
                                      aplicar=args.aplicar, lote=args.lote,
                                      limite=args.limite)

    print(relatorio)
    return 0


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 4: Rode os testes**

```bash
python -m pytest tests/test_fase5_rdo_fotos.py -v
```

Esperado: os 17 testes do arquivo PASSAM.

- [ ] **Step 5: Commit (o código, não a execução)**

```bash
git add scripts/migrar_fotos_rdo_para_disco.py tests/test_fase5_rdo_fotos.py
git commit -m "feat(fase5): script de migracao das fotos de RDO para disco

Duas passadas: a primeira garante e VERIFICA o arquivo em disco e marca
armazenamento='disco' (reversivel por um comando); a segunda zera as tres
colunas base64 e recusa qualquer foto cujo arquivo nao abra. Aborta se
UPLOADS_PATH nao estiver definido. Nenhuma execucao em producao aqui."
```

- [ ] **Step 6: ⚠️ Execução — só com os seis pré-requisitos conferidos**

Ensaio primeiro, num tenant pequeno e com limite:

```bash
python scripts/migrar_fotos_rdo_para_disco.py --admin-id <ID> --limite 50
python scripts/migrar_fotos_rdo_para_disco.py --admin-id <ID> --limite 50 --aplicar
```

Abra a tela de um RDO desse tenant e confirme que as fotos aparecem.
Depois, o tenant inteiro:

```bash
python scripts/migrar_fotos_rdo_para_disco.py --admin-id <ID> --aplicar
```

**Pare aqui por pelo menos um ciclo de deploy.** O objetivo é provar que
o volume sobrevive ao restart — que é a única coisa que a base64
garantia. Só depois:

```bash
python scripts/migrar_fotos_rdo_para_disco.py --admin-id <ID> --liberar
```

Se `recusadas > 0`, **não siga**: alguma foto perdeu o arquivo. Só com
`recusadas == 0`:

```bash
python scripts/migrar_fotos_rdo_para_disco.py --admin-id <ID> --liberar --aplicar
```

- [ ] **Step 7: Recupere o espaço (janela de manutenção)**

`UPDATE ... SET coluna = NULL` não devolve espaço ao sistema operacional
— o TOAST vira espaço morto. Em janela de manutenção, com a tabela
travada:

```bash
python -c "
from app import app, db
from sqlalchemy import text
with app.app_context():
    conexao = db.engine.connect().execution_options(isolation_level='AUTOCOMMIT')
    conexao.execute(text('VACUUM FULL ANALYZE rdo_foto'))
    linha = conexao.execute(text('''
        SELECT pg_size_pretty(pg_total_relation_size(:t)) tabela,
               pg_size_pretty(pg_database_size(current_database())) banco
    '''), {'t': 'rdo_foto'}).fetchone()
    print(dict(linha._mapping))
    conexao.close()
"
```

Esperado: `rdo_foto` cai de ~16 GB para dezenas de MB e o banco inteiro
cai na mesma proporção. **Anote os dois números no documento de fecho** —
é a evidência do que a fase entregou.

---

## Task 16: Matriz de autorização, runbook e gate

**Files:**
- Create: `tests/test_fase5_matriz_rdo.py`
- Create: `docs/fase-5-rollout.md`
- Test: a própria matriz + `bash run_tests.sh --gate`

- [ ] **Step 1: Escreva a matriz papel × estado × ação**

Crie `tests/test_fase5_matriz_rdo.py`:

```python
"""Fase 5 — matriz papel × estado × ação, numa tabela só.

Cada linha do parametrize é uma frase de negócio verificável:
"um APONTADOR num RDO preenchido PODE assinar e NÃO PODE aprovar".
As tabelas do plano e o comportamento do código ficam presos um ao outro.
"""
import os
import sys
import uuid
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os 54 blueprints antes de qualquer request
from app import app, db
from models import (Cliente, Funcionario, Obra, PapelObra, RDO, TipoUsuario,
                    Usuario, UsuarioObra)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase5-matriz'
    yield


def _sfx():
    return uuid.uuid4().hex[:8]


def _montar_cenario(papel_na_obra, estado_alvo):
    """Cria admin, obra, pessoa com `papel_na_obra` e um RDO em `estado_alvo`.

    Devolve (rdo_id, usuario_id).
    """
    from services.rdo_ciclo_vida import (ASSINADO, PREENCHIDO, RASCUNHO,
                                         transicionar)

    suf = _sfx()
    admin = Usuario(
        username=f'f5m_{suf}', email=f'f5m_{suf}@test.local',
        nome=f'Admin Matriz {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
    db.session.add(admin)
    db.session.commit()

    cli = Cliente(nome=f'CLI-M5-{suf}', admin_id=admin.id)
    db.session.add(cli)
    db.session.flush()
    obra = Obra(nome=f'Obra Matriz {suf}', codigo=f'OM5{suf[:6].upper()}',
                data_inicio=date(2026, 1, 1), admin_id=admin.id,
                cliente_id=cli.id, valor_contrato=100000)
    db.session.add(obra)
    db.session.commit()

    func = Funcionario(
        codigo=f'M5{suf[:6].upper()}', nome=f'Pessoa {suf}',
        cpf=suf.ljust(14, '0')[:14], email=f'f5mf_{suf}@test.local',
        data_admissao=date(2025, 1, 1), admin_id=admin.id, ativo=True)
    db.session.add(func)
    db.session.commit()

    if papel_na_obra == 'admin':
        ator = admin
    else:
        ator = Usuario(
            username=f'f5mu_{suf}', email=f'f5mu_{suf}@test.local',
            nome=f'Ator {suf}', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin.id, funcionario_id=func.id)
        db.session.add(ator)
        db.session.commit()
        db.session.add(UsuarioObra(
            usuario_id=ator.id, obra_id=obra.id, papel=papel_na_obra,
            admin_id=admin.id, ativo=True))
        db.session.commit()

    rdo = RDO(numero_rdo=f'RDO-M5-{suf}', data_relatorio=date(2026, 6, 22),
              obra_id=obra.id, admin_id=admin.id, criado_por_id=ator.id,
              comentario_geral='Conteúdo original do dia.')
    db.session.add(rdo)
    db.session.commit()

    if estado_alvo != RASCUNHO:
        transicionar(rdo, PREENCHIDO, usuario=admin)
        db.session.commit()
    if estado_alvo == ASSINADO:
        from services.rdo_assinatura import assinar
        assinar(rdo, admin)
        db.session.commit()

    return rdo.id, ator.id


def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


# (papel_na_obra, estado_inicial, acao, estado_esperado_depois)
MATRIZ = [
    # LEITOR não faz nada.
    (PapelObra.LEITOR, 'rascunho', 'finalizar', 'rascunho'),
    (PapelObra.LEITOR, 'preenchido', 'assinar', 'preenchido'),
    (PapelObra.LEITOR, 'preenchido', 'reabrir', 'preenchido'),

    # APONTADOR submete e assina; não aprova, não reabre, não retifica.
    (PapelObra.APONTADOR, 'preenchido', 'assinar', 'assinado'),
    (PapelObra.APONTADOR, 'preenchido', 'reabrir', 'preenchido'),
    (PapelObra.APONTADOR, 'assinado', 'aprovar', 'assinado'),
    (PapelObra.APONTADOR, 'assinado', 'retificar', 'assinado'),

    # GESTOR faz tudo.
    (PapelObra.GESTOR, 'preenchido', 'assinar', 'assinado'),
    (PapelObra.GESTOR, 'preenchido', 'reabrir', 'rascunho'),
    (PapelObra.GESTOR, 'assinado', 'aprovar', 'aprovado'),
    (PapelObra.GESTOR, 'assinado', 'retificar', 'retificado'),

    # ADMIN do tenant enxerga toda obra como GESTOR (Fase 1).
    ('admin', 'preenchido', 'assinar', 'assinado'),
    ('admin', 'assinado', 'aprovar', 'aprovado'),

    # Transições que a máquina de estados recusa, independente do papel.
    (PapelObra.GESTOR, 'rascunho', 'assinar', 'rascunho'),
    (PapelObra.GESTOR, 'rascunho', 'aprovar', 'rascunho'),
    (PapelObra.GESTOR, 'preenchido', 'aprovar', 'preenchido'),
    (PapelObra.GESTOR, 'rascunho', 'retificar', 'rascunho'),
    (PapelObra.GESTOR, 'assinado', 'reabrir', 'assinado'),
]

_ROTA = {
    'finalizar': '/rdo/{}/finalizar',
    'assinar': '/rdo/{}/assinar',
    'aprovar': '/rdo/{}/aprovar',
    'reabrir': '/rdo/{}/reabrir',
    'retificar': '/rdo/{}/retificar',
}


@pytest.mark.parametrize('papel,estado_inicial,acao,esperado', MATRIZ)
def test_matriz_papel_estado_acao(papel, estado_inicial, acao, esperado):
    nome_papel = papel if isinstance(papel, str) else papel.value

    with app.app_context():
        rdo_id, ator_id = _montar_cenario(papel, estado_inicial)

    dados = {'motivo': 'motivo de teste', 'observacao': 'obs de teste'}
    _cliente_de(ator_id).post(_ROTA[acao].format(rdo_id), data=dados,
                              follow_redirects=True)

    with app.app_context():
        atual = db.session.get(RDO, rdo_id).estado
        assert atual == esperado, (
            f'{nome_papel} em RDO {estado_inicial} tentando "{acao}": '
            f'estado ficou {atual!r}, esperado {esperado!r}')


def test_rdo_assinado_nunca_muda_de_conteudo_em_nenhum_caminho():
    """Fecho da fase: a frase que a Fase 5 existe para tornar verdadeira."""
    with app.app_context():
        rdo_id, ator_id = _montar_cenario(PapelObra.GESTOR, 'assinado')

    cliente = _cliente_de(ator_id)
    for rota, dados in (
        ('/salvar-rdo-flexivel', {'rdo_id': rdo_id,
                                  'comentario_geral': 'invasão 1'}),
        ('/rdo/salvar', {'rdo_id': rdo_id, 'comentario_geral': 'invasão 2'}),
        (f'/rdo/{rdo_id}/atualizar', {'data_relatorio': '2026-06-23'}),
        (f'/rdo/editar/{rdo_id}/salvar', {'observacoes_gerais': 'invasão 3'}),
        (f'/rdo/excluir/{rdo_id}', {}),
    ):
        cliente.post(rota, data=dados, follow_redirects=True)

    with app.app_context():
        sobrevivente = db.session.get(RDO, rdo_id)
        assert sobrevivente is not None, 'o RDO assinado foi excluído'
        assert sobrevivente.comentario_geral == 'Conteúdo original do dia.', (
            'algum caminho de escrita alterou um RDO assinado')
        assert sobrevivente.data_relatorio == date(2026, 6, 22)
```

- [ ] **Step 2: Rode a matriz**

```bash
python -m pytest tests/test_fase5_matriz_rdo.py -v
```

Esperado: 19 testes PASSAM (18 da matriz + o fecho).

- [ ] **Step 3: Escreva o runbook**

Crie `docs/fase-5-rollout.md`:

```markdown
# Fase 5 — runbook de rollout

Duas partes com riscos muito diferentes. **Não misture as duas no mesmo
deploy.**

| Parte | Tasks | Risco | Depende de humano? |
|---|---|---|---|
| Ciclo de vida + assinatura | 1–12, 16 | Baixo, aditivo | não |
| Migração das fotos | 13–15 | **Alto, destrutivo no passo final** | **sim** |

## Parte A — ciclo de vida e assinatura

Aditiva por construção. Depois das migrations 260–263, todos os RDOs
existentes estão em `estado='preenchido'`, que é mutável — a
imutabilidade só passa a existir quando alguém clicar em "Assinar".

1. **Rode as migrations.**

       python -c "
       from app import app
       from migrations import executar_migracoes
       with app.app_context():
           executar_migracoes()
       " 2>&1 | grep -E "Migration 26[0-4]"

2. **Confira o backfill.** O número que importa é quantos RDOs ficaram
   em `assinado` — tem que ser **zero**.

       python -c "
       from app import app, db
       from sqlalchemy import text
       with app.app_context():
           for linha in db.session.execute(text(
                   'SELECT estado, count(*) FROM rdo GROUP BY estado ORDER BY 2 DESC')):
               print(linha)
       "

3. **Confira que a guarda subiu.** No log do boot tem que aparecer
   `[OK] Fase 5: guarda de imutabilidade de RDO ativa`. Se aparecer o
   `[ERRO]`, o import de `services.rdo_ciclo_vida` falhou e **não existe
   imutabilidade nenhuma** — o resto da fase vira decoração.

4. **Assine um RDO de teste** numa obra de homologação e confirme que a
   tela recusa a edição depois.

### Rollback da parte A

Não precisa de rollback de schema. Um comando devolve todos os RDOs ao
comportamento mutável:

    UPDATE rdo SET estado = 'preenchido' WHERE estado IN ('assinado', 'aprovado');

As assinaturas e a trilha continuam gravadas — a informação de quem
assinou não se perde, só deixa de travar a edição.

## Parte B — migração das fotos (16 GB)

### Os seis pré-requisitos, todos bloqueantes

1. Volume persistente montado, **≥ 25 GB** livres (`df -h $UPLOADS_PATH`).
2. `UPLOADS_PATH` definido no painel do EasyPanel apontando para ele.
3. Task 13 **já em produção**. Sem ela, definir `UPLOADS_PATH` faz TODAS
   as fotos sumirem da tela no mesmo instante — `salvar_foto_rdo` grava
   em `$UPLOADS_PATH/rdo/…` e o `servir_foto` antigo procurava em
   `static/uploads/rdo/…`.
4. Dump COMPLETO do banco, com as fotos, guardado **fora** do servidor:

       python scripts/backup_banco.py        # 16 GB — NÃO use --sem-fotos

5. Snapshot do volume confirmado com a Hostinger (pendência já anotada em
   `ESTADO-ATUAL.md`).
6. Janela de manutenção para o `VACUUM FULL`, que trava a tabela.

### A ordem

    # 1. Ensaio: 50 fotos de um tenant, dry-run e depois aplicado
    python scripts/migrar_fotos_rdo_para_disco.py --admin-id <ID> --limite 50
    python scripts/migrar_fotos_rdo_para_disco.py --admin-id <ID> --limite 50 --aplicar
    # → abra a tela de um RDO desse tenant e confirme que as fotos aparecem

    # 2. Tenant inteiro, passada 1 (reversível)
    python scripts/migrar_fotos_rdo_para_disco.py --admin-id <ID>
    python scripts/migrar_fotos_rdo_para_disco.py --admin-id <ID> --aplicar

    # 3. ESPERE UM CICLO DE DEPLOY.
    #    É a única forma de provar que o volume sobrevive ao restart —
    #    exatamente o que a base64 garantia e o que se está abrindo mão.

    # 4. Passada 2 em dry-run. Se `recusadas > 0`, PARE.
    python scripts/migrar_fotos_rdo_para_disco.py --admin-id <ID> --liberar

    # 5. Passada 2 aplicada (DESTRUTIVA)
    python scripts/migrar_fotos_rdo_para_disco.py --admin-id <ID> --liberar --aplicar

    # 6. Janela de manutenção: recupera o espaço
    VACUUM FULL ANALYZE rdo_foto;

### Rollback da parte B

| Momento | Rollback |
|---|---|
| Depois da passada 1 | `--reverter --aplicar`. Um comando; a base64 nunca saiu do banco |
| Depois da passada 2 | **Só restore do dump do pré-requisito 4.** Por isso o dump vem antes, e por isso o passo 3 existe |

## O que a Fase 5 deliberadamente NÃO fez

- **Não migrou o portal do cliente para servir foto por URL.**
  `rdo_crud.servir_foto` exige `@login_required` e o portal é por token.
  Criar a rota equivalente por token é Fase 9a, junto do login de
  cliente. Até lá `templates/portal/_portal_rdos.html` continua lendo
  `thumbnail_base64` — o que significa que a **passada 2 da parte B
  quebra a miniatura do portal** para as fotos liberadas. Decida com o
  Cássio: ou a Fase 9a vem antes da passada 2, ou o portal fica sem
  miniatura no intervalo.
- **Não unificou os oito caminhos de escrita de RDO.** A guarda
  `before_flush` os cobre todos, mas `views/rdo.py` continua com 5.092
  linhas e seis rotas que fazem quase a mesma coisa. Refatoração é outra
  fase.
- **Não criou assinatura do cliente.** `RDOAssinatura.PAPEL_CLIENTE`
  existe e a coluna aceita, mas não há rota que o preencha — é Fase 9a.
- **Não implementou clima manhã/tarde, alerta de RDO em atraso nem
  link ocorrência→requisição**, que a `DEVOLUTIVA.md:243` lista junto
  desta fase. Clima manhã/tarde esbarra nos atributos fantasma
  `tempo_manha`/`tempo_tarde` que ainda são escritos sem efeito em
  `views/rdo.py:688` e `:2732`; o link ocorrência→requisição depende de
  `Requisicao`, que é da Fase 3.
- **Não tocou no modo de apontamento** (percentual × quantidade). É o
  plano irmão `2026-07-21-cronograma-editavel-rdo-percentual.md`.
```

- [ ] **Step 4: Rode o gate completo**

```bash
bash run_tests.sh --gate 2>&1 | tail -40
```

Esperado: nenhuma regressão contra a baseline anotada no início da fase.
Anote a linha final de passados/falhados — a `DEVOLUTIVA.md:196` exige
que ela esteja colada no documento de fecho, e o R5 documenta o que
acontece quando não está.

Pontos de atenção conhecidos, com o conserto já indicado nas tasks:

| Sintoma provável | Onde | Conserto |
|---|---|---|
| Teste que fazia `GET /rdo/<id>` anônimo agora recebe 302 | qualquer `tests/test_rdo_*` | injetar `sess['_user_id']` no teste; **não** reabrir a rota |
| `KeyError: 'imagem_original_base64'` | `services/importacao_fisico_financeiro.py:370-397` | Task 14, Step 7 |
| `RDOImutavel` num teste que edita RDO | teste que assinou e depois editou | é o comportamento novo; ajustar o teste |

- [ ] **Step 5: Commit**

```bash
git add tests/test_fase5_matriz_rdo.py docs/fase-5-rollout.md
git commit -m "test(fase5): matriz papel x estado x acao + runbook de rollout

18 combinacoes numa tabela so, mais o teste de que nenhum dos cinco
caminhos de escrita altera um RDO assinado. O runbook separa a parte
aditiva (ciclo de vida) da parte destrutiva (fotos), com os seis
pre-requisitos de infra e o rollback de cada momento."
```

---

## Encerramento da fase

- [ ] **Atualize `ESTADO-ATUAL.md`:**
  - marque a Fase 5 como concluída na tabela de fases (linha 56);
  - na tabela "O que está em aberto da Fase 0.5" (linha 102), substitua
    `duplicar_rdo emite webhook sem lançar custos (bug 6d) | ❌` por
    `✅ Fase 5 — a rota estava morta em AttributeError; corrigida e o RDO
    duplicado passa a nascer em rascunho, sem emitir evento`;
  - na armadilha nº 2 (linha 121), substitua a descrição de `rdo_foto`
    pelo estado real após as Tasks 13-15 e aponte para
    `docs/fase-5-rollout.md`;
  - atualize a contagem de rotas sem autenticação (`visualizar_rdo`
    saiu da lista).
- [ ] **Cole no documento de fecho:** a linha final do `--gate`, a
  distribuição de `rdo.estado` por contagem, e — se a parte B tiver
  rodado — o `pg_total_relation_size('rdo_foto')` antes e depois.
- [ ] **Não rode a parte B do runbook** sem os seis pré-requisitos
  conferidos pelo Cássio.
- [ ] **Verifique que a Fase 6 está destravada:** o padrão de
  versionamento por documento encadeado (`rdo_retificado_id` +
  `RDOTransicaoEstado`) é o mesmo que o aditivo de orçamento da Fase 6
  vai precisar. Se ela extrair um helper genérico, `services/
  rdo_ciclo_vida.py` passa a consumi-lo sem mudar a API pública.

---

## Decisões que precisam do Cássio

Nenhuma bloqueia a execução — todas já têm resposta adotada no plano.

| # | Decisão | Recomendação adotada | O que muda se você discordar |
|---|---|---|---|
| 1 | **Valor jurídico da assinatura** | **`Recomendado:` registro de autoria + integridade (hash SHA-256 + carimbo de tempo do servidor + IP + user-agent), ancorado em `Usuario.funcionario_id`. Sem ICP-Brasil.** Base: MP 2.200-2/2001, art. 10, §2º. O RDO é documento interno construtora ↔ equipe. ICP-Brasil / Clicksign / D4Sign ficam para o que é oponível a terceiro — a medição assinada pelo cliente, Fase 9a | `RDOAssinatura.provedor` nasce `'interno'` e `referencia_externa` já existe: trocar por provedor externo é uma rota nova, sem migração de schema. Custo estimado: R$/assinatura + integração + fluxo de e-mail |
| 2 | **Os cinco estados** | `rascunho → preenchido → assinado → aprovado`, com `retificado` como saída dos dois terminais. `preenchido` é o equivalente semântico do `'Finalizado'` de hoje, e é onde os 5.532 RDOs históricos caíram | Se você quiser um estado de "ciência do cliente" separado, ele entra entre `assinado` e `aprovado` — uma entrada em `TRANSICOES_VALIDAS` e um papel em `RDOAssinatura.PAPEIS` |
| 3 | **Quem assina, quem aprova** | APONTADOR e GESTOR **assinam** (`pode_apontar_na_obra`); só GESTOR **aprova** e **retifica** (`pode_editar_obra`). ADMIN do tenant é GESTOR implícito em toda obra (regra da Fase 1) | É uma linha em `views/rdo.py` por rota. A matriz de `tests/test_fase5_matriz_rdo.py` documenta a regra atual |
| 4 | **Reabrir RDO preenchido** | Permitido ao GESTOR, com motivo obrigatório, **só antes da assinatura**. A máquina de estados não tem aresta saindo de `assinado` para trás | Proibir a reabertura é remover `RASCUNHO` de `TRANSICOES_VALIDAS[PREENCHIDO]` — aí toda correção vira retificação, inclusive erro de digitação no mesmo dia |
| 5 | **Backfill do histórico** | Todos os 5.532 RDOs existentes → `preenchido`. **Nenhum vira `assinado`** | Se você quiser considerar os RDOs antigos como assinados pelo `criado_por_id`, seria fabricar autoria retroativa de 5.532 documentos. Recomendo fortemente não |
| 6 | **Duplicar RDO não publica** | O RDO duplicado nasce `rascunho` e não emite `rdo_finalizado` nem `obra.rdo_publicado`. Publica quando for submetido e assinado | A alternativa seria emitir os DOIS eventos na duplicação — o que lançaria custo de mão de obra de um RDO que ninguém revisou. Foi por isso que virou bug 6d |
| 7 | **Migrar `rdo_foto` para disco** | **Sim, mas em duas passadas e só com volume persistente montado.** As Tasks 13-14 (seguras) podem ir hoje; a Task 15 espera você | Sem migrar, o banco fica em 16 GB, o backup completo não cabe em janela curta e o RPO real continua sendo o que o `ESTADO-ATUAL.md` descreve. Note que 13 GB **já estão em disco** — a base64 é duplicata; o que falta é o volume ser persistente |
| 8 | **Portal do cliente e a passada 2** | A passada 2 quebra a miniatura do portal para as fotos liberadas, porque `templates/portal/_portal_rdos.html:19` lê `thumbnail_base64` e o portal é por token, não por login | Duas saídas: (a) fazer a rota de foto por token antes da passada 2 (é meia hora, mas mexe em portal, que é território da Fase 9a), ou (b) aceitar o portal sem miniatura no intervalo. Não decidi por você |

---

## Autorrevisão feita sobre este plano

**Cobertura do escopo pedido.** Cada item do briefing tem tarefa:

| Pedido | Onde |
|---|---|
| Estados do RDO | Tasks 1, 3 |
| Guardas de transição | Task 3 (`TRANSICOES_VALIDAS`, `transicionar`), Task 16 (matriz) |
| Assinatura vinculada a `Usuario.funcionario_id` | Tasks 5, 6, 7 — e `test_usuario_sem_vinculo_de_funcionario_nao_assina` prova que sem identidade não assina |
| Imutabilidade após assinatura | Task 4 (guarda `before_flush`), Task 11 (exclusão), Task 16 (fecho de 5 rotas) |
| Se editar, versiona | Task 9 (RDO retificador) |
| Correção do bug 6d | Task 10 |
| `rdo_foto` avaliada, com backfill reversível e pré-requisitos de infra | Tasks 13, 14, 15 + runbook |
| Fronteira com o plano irmão | seção "Fronteira de escopo", com contrato `garantir_editavel()` |
| Faixa de migrations 260–269 | usadas 260, 261, 262, 263, 264 — sobram 265-269 |
| Trilha de auditoria | Task 2 (`RDOTransicaoEstado`), no molde de `CronogramaImportacaoEvento` |

**O aviso do briefing se confirmou, e o diagnóstico desatualizado era o do
bug 6d.** O `ESTADO-ATUAL.md:102` descreve o bug que existiria se a rota
funcionasse; a rota morre antes, em `AttributeError` na linha 1624. A
Task 10 conserta as duas camadas e o plano registra a diferença em vez de
repetir o diagnóstico antigo.

**Achado colateral, encontrado ao construir a máquina de estados:**
`finalizar_rdo` (`views/rdo.py:1520`) é a **segunda** rota morta do
módulo. O guard da linha 1533 testa `if rdo.status == 'Finalizado'` e
`models.py:860` faz todo RDO nascer exatamente com esse valor — a rota
sempre retorna "RDO já está finalizado" sem executar nada. Isso explica
por que os efeitos colaterais de publicação (custo de mão de obra,
recálculo de medição, webhook) na prática só saem por
`salvar_rdo_flexivel` e `atualizar_rdo`. Corrigido na Task 8, Step 4,
junto da troca de `@admin_required` — que hoje impede o próprio apontador
de submeter o RDO que ele lançou.

**Riscos identificados e onde estão endereçados:**

1. *A guarda `before_flush` derrubar fluxos legítimos.* Endereçado pelo
   backfill que deixa tudo em `preenchido` (mutável), pelo `ContextVar`
   de bypass com `test_bypass_nao_vaza_entre_transacoes`, e pela
   verificação de regressão no Step 6 da Task 4.
2. *A guarda não ser registrada no boot* — falha silenciosa que anularia
   a fase inteira. Endereçado pelo log explícito em `app.py` e pelo
   passo 3 do runbook.
3. *Perder foto na migração.* Endereçado pelas duas passadas, pela
   verificação com `PIL.Image.verify()` em cada arquivo antes de liberar,
   pelo `--reverter`, pelo abort quando `UPLOADS_PATH` está vazio, e pelo
   ciclo de deploy obrigatório entre as passadas.
4. *Assinatura invalidada pela migração de fotos.* Endereçado pelo desenho
   do payload canônico (`test_hash_nao_inclui_os_bytes_da_foto`).
5. *Quebrar os nove consumidores de `status == 'Finalizado'`.* Endereçado
   pela coluna nova e por `test_status_legado_continua_finalizado`.

**Consistência de nomes, conferida contra todos os usos nos testes:**
`RASCUNHO`/`PREENCHIDO`/`ASSINADO`/`APROVADO`/`RETIFICADO`, `ESTADOS`,
`ESTADOS_IMUTAVEIS`, `TRANSICOES_VALIDAS`, `ROTULOS`, `CORES`,
`estado_de`, `e_imutavel`, `garantir_editavel`, `pode_transicionar`,
`transicionar`, `escrita_de_ciclo_de_vida`, `bypass_ativo`,
`CicloVidaInvalido`, `TransicaoInvalida`, `RDOImutavel`
(`services/rdo_ciclo_vida.py`); `payload_canonico`, `serializar`,
`calcular_hash`, `verificar_integridade`, `VERSAO_PAYLOAD`
(`services/rdo_hash.py`); `assinar`, `aprovar`, `criar_retificador`,
`AssinaturaInvalida`, `SemIdentidade` (`services/rdo_assinatura.py`);
`caminho_absoluto` (`services/rdo_foto_service.py`); `migrar_para_disco`,
`liberar_base64`, `reverter` (`scripts/migrar_fotos_rdo_para_disco.py`);
`assinar_rdo`, `aprovar_rdo`, `reabrir_rdo`, `retificar_rdo`,
`duplicar_rdo`, `_rdo_do_tenant_ou_404`, `_estado_para_template`,
`_acoes_para_template` (`views/rdo.py`).

**Assinaturas conferidas no código, não presumidas:**

- `_gerar_numero_rdo_unico(obra_id, data_relatorio, admin_id)` —
  `views/rdo.py:25`, usado por `criar_retificador` e `duplicar_rdo`.
- `_section_rule(label, styles)` — `services/rdo_pdf_service.py:259`,
  usado no bloco de assinatura novo.
- `RDOMaoObra.funcao_exercida` é NOT NULL (`models.py:924`) — por isso o
  `or 'Geral'` em `duplicar_rdo`.
- `rdo_foto.nome_arquivo` e `caminho_arquivo` são NOT NULL **no banco**
  (`information_schema` conferido) — por isso o conserto do INSERT em
  `crud_rdo_completo.py:718`.
- `db.deferred(db.Column(db.Text))` e **não** `db.Column(..., deferred=True)`:
  o segundo levanta `TypeError` em SQLAlchemy 2.0.41 / Flask-SQLAlchemy 3.1.1,
  verificado executando.
- `ProxyFix(x_for=1)` em `app.py:94` — por isso `request.remote_addr` é
  o IP real e o teste usa `X-Forwarded-For`.
- `Obra.cliente_id` é NOT NULL — todas as fixtures criam `Cliente` antes.
- `pode_apontar_na_obra`, `pode_editar_obra`, `PapelObra`, `UsuarioObra`,
  `funcionario_do_usuario` vêm da Fase 1, com as assinaturas exatas do
  plano `2026-07-21-fase-1-identidade-papeis.md` (linhas 1160-1221,
  1802-1813).
- Números de migration: 260-264. A maior registrada hoje é a **213**
  (`migrations.py:4014`); a Fase 1 usa 214-216. Confira antes de aplicar,
  caso outra branch tenha avançado.
