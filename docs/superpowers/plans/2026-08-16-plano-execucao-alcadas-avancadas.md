# Alçadas avançadas — plano de execução

> **Para quem executa:** os passos usam checkbox (`- [ ]`) para acompanhamento. Cada
> passo é uma ação de 2-5 minutos. TDD: o teste vem antes, e roda vermelho antes de
> ficar verde.

**Spec:** `docs/superpowers/specs/2026-08-16-alcadas-avancadas-design.md`

**Objetivo:** a exigência de aprovação de uma requisição de compra deixa de olhar só o
valor — passa a considerar fracionamento, orçamento da etapa, concorrência e urgência, e
fica **carimbada** no documento no momento em que entra em aprovação.

**Arquitetura:** um módulo novo (`services/alcada_regras.py`) calcula a avaliação; o
motor de faixas existente (`services/alcada_compras.py`) passa a consumi-la em vez de
recalcular. O chokepoint único de transição (`services/requisicao_compra.py:116`) grava
o carimbo. Nada da Fase 3 é reescrito.

**Stack:** Flask + SQLAlchemy 2 + Postgres, pytest. Migração idempotente no padrão da
casa (`IF NOT EXISTS`, registrada em `executar_migracoes`).

**Banco de teste:** este host tem um banco descartável já com o schema completo. Rode a
suíte com

```bash
export DATABASE_URL="$(python -c "import os,re;print(re.sub(r'/[^/?]+(\?|$)', r'/sige_gate_local\1', os.environ['DATABASE_URL']))")"
```

---

### Task 1: Migração 287 e as colunas

**Arquivos:**
- Modificar: `models.py` (classe `RequisicaoCompra`, classe `FaixaAlcada`)
- Modificar: `migrations.py` (função nova + registro em `executar_migracoes`)
- Testar: `tests/test_alcada_regras.py` (arquivo novo)

- [ ] **Step 1: Conferir que 287 está livre**

```bash
python -c "
import os, sqlalchemy as sa, re
u=re.sub(r'/[^/?]+(\?|\$)', r'/sige_gate_local\1', os.environ['DATABASE_URL'])
e=sa.create_engine(u)
with e.connect() as c:
    print(c.execute(sa.text('select max(numero) from migration_history')).scalar())
"
```

Esperado: `286`. Se vier outro número, pare e realoque — é a lição da B6.1.

- [ ] **Step 2: Escrever o teste que falha**

Criar `tests/test_alcada_regras.py` com o cabeçalho abaixo (fixtures no molde de
`tests/test_recebimento_atesto.py`) e o primeiro teste:

```python
"""Alçadas avançadas — as quatro condições, fracionamento e emergência.

Spec: docs/superpowers/specs/2026-08-16-alcadas-avancadas-design.md
Plano: docs/superpowers/plans/2026-08-16-plano-execucao-alcadas-avancadas.md

Molde de tests/test_recebimento_atesto.py: fixtures locais, tenant por uuid4,
sem depender de seed.
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
from models import (Cliente, EstadoRequisicao, FaixaAlcada, Obra,
                    RequisicaoCompra, TipoUsuario, Usuario)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-alcada-regras'
    yield


def _admin():
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'alc_{suf}', email=f'alc_{suf}@test.local', nome=f'Adm {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id):
    suf = uuid.uuid4().hex[:8]
    cliente = Cliente(nome=f'Cliente {suf}', admin_id=admin_id)
    db.session.add(cliente)
    db.session.commit()
    o = Obra(nome=f'Obra {suf}', codigo=f'A{suf[:6].upper()}',
             data_inicio=date(2026, 1, 1), admin_id=admin_id,
             cliente_id=cliente.id, ativo=True)
    db.session.add(o)
    db.session.commit()
    return o


def _sc(admin_id, obra_id, valor, estado=EstadoRequisicao.AGUARDANDO_APROVACAO,
        osc_id=None, dias_atras=0, urgencia='normal', solicitante_id=None):
    """Requisição crua, sem passar pelo serviço — o objetivo é montar cenário."""
    suf = uuid.uuid4().hex[:6].upper()
    r = RequisicaoCompra(
        numero=f'RC-{suf}', admin_id=admin_id, obra_id=obra_id,
        obra_servico_custo_id=osc_id, solicitante_id=solicitante_id or admin_id,
        estado=estado, valor_estimado=Decimal(str(valor)), urgencia=urgencia,
        created_at=datetime.utcnow() - timedelta(days=dias_atras))
    db.session.add(r)
    db.session.commit()
    return r


def test_colunas_da_migracao_287_existem_com_o_default_do_legado():
    """SC nasce 'normal', sem carimbo e sem emergência; faixa nasce pedindo 2."""
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        sc = _sc(admin.id, obra.id, 1000)
        assert sc.urgencia == 'normal'
        assert sc.justificativa_urgencia is None
        assert sc.faixa_exigida_id is None
        assert sc.alcada_degraus == 0
        assert sc.alcada_motivos is None
        assert sc.alcada_carimbada_em is None
        assert sc.emergencia_ativada_em is None

        faixa = FaixaAlcada(admin_id=admin.id, ordem=1,
                            valor_ate=Decimal('5000.00'),
                            aprovacoes_necessarias=1)
        db.session.add(faixa)
        db.session.commit()
        assert faixa.fornecedores_minimos == 2
```

- [ ] **Step 3: Rodar e ver falhar**

```bash
python -m pytest tests/test_alcada_regras.py -q -p no:cacheprovider
```

Esperado: FAIL com `TypeError: 'urgencia' is an invalid keyword argument` (a coluna
ainda não existe no modelo).

- [ ] **Step 4: Acrescentar as colunas ao modelo**

Em `models.py`, na classe `RequisicaoCompra`, logo depois de `valor_estimado`:

```python
    # ── Alçadas avançadas (spec 2026-08-16) ──────────────────────────
    # Urgência é da SC, não da faixa: ela SOBE um degrau (não afrouxa).
    urgencia = db.Column(db.String(10), nullable=False, default='normal')
    justificativa_urgencia = db.Column(db.Text, nullable=True)

    # O CARIMBO. Gravado ao entrar em AGUARDANDO_APROVACAO, para a barra
    # não se mover debaixo de quem aprova. NULL = SC anterior à fase, e
    # nesse caso `pendencias_de_aprovacao` recalcula na leitura.
    faixa_exigida_id = db.Column(
        db.Integer, db.ForeignKey('faixa_alcada.id', ondelete='SET NULL'),
        nullable=True)
    alcada_degraus = db.Column(db.SmallInteger, nullable=False, default=0)
    alcada_motivos = db.Column(db.JSON, nullable=True)
    alcada_carimbada_em = db.Column(db.DateTime, nullable=True)

    # Rito de emergência: um admin aprova sozinho AGORA, o resto vira
    # dívida com prazo. O prazo é GRAVADO, não derivado — se as 48h
    # virarem 72h amanhã, a SC já acionada mantém o prazo dela.
    emergencia_ativada_em = db.Column(db.DateTime, nullable=True)
    emergencia_prazo = db.Column(db.DateTime, nullable=True)
    emergencia_por_id = db.Column(
        db.Integer, db.ForeignKey('usuario.id', ondelete='SET NULL'),
        nullable=True)
    emergencia_regularizada_em = db.Column(db.DateTime, nullable=True)
```

Na classe `FaixaAlcada`, depois de `exige_mapa_concorrencia`:

```python
    # Quantos fornecedores o mapa precisa ter para servir de concorrência
    # NESTA faixa. É onde mora o "corte de 3 cotações": a faixa aberta
    # pede 3, as de baixo pedem 2. Não existe um segundo conceito de
    # corte por valor — as faixas já SÃO o corte por valor.
    fornecedores_minimos = db.Column(db.SmallInteger, nullable=False, default=2)
```

- [ ] **Step 5: Escrever a migração 287**

Em `migrations.py`, imediatamente antes de `def _migration_282_backfill_dropdown_crm():`:

```python
def _migration_287_alcadas_avancadas():
    """Alçadas avançadas — carimbo, urgência, emergência e o piso de cotações.

    Todas as colunas são ADITIVAS e o default descreve o legado: SC existente
    é 'normal', sem carimbo (e por isso continua sendo avaliada na leitura) e
    sem emergência; faixa existente continua pedindo 2 fornecedores, que é o
    número fixo que `_mapa_serve_de_concorrencia` usava antes desta fase.

    Sem backfill de propósito: carimbar SC que já está em aprovação mudaria a
    régua de uma rodada em curso, que é exatamente o que o carimbo existe para
    impedir.

    Alocação: 287. Conferido em `migration_history` em 16/08 — a última
    aplicada é a 286 (timbre dos PDFs), depois do merge que trouxe 283-285 do
    recebimento.
    """
    from sqlalchemy import text as sa_text
    with db.engine.begin() as conn:
        for coluna, tipo in [
            ("urgencia", "VARCHAR(10) NOT NULL DEFAULT 'normal'"),
            ("justificativa_urgencia", "TEXT"),
            ("faixa_exigida_id", "INTEGER REFERENCES faixa_alcada(id) ON DELETE SET NULL"),
            ("alcada_degraus", "SMALLINT NOT NULL DEFAULT 0"),
            ("alcada_motivos", "JSONB"),
            ("alcada_carimbada_em", "TIMESTAMP"),
            ("emergencia_ativada_em", "TIMESTAMP"),
            ("emergencia_prazo", "TIMESTAMP"),
            ("emergencia_por_id", "INTEGER REFERENCES usuario(id) ON DELETE SET NULL"),
            ("emergencia_regularizada_em", "TIMESTAMP"),
        ]:
            conn.execute(sa_text(
                f"ALTER TABLE requisicao_compra ADD COLUMN IF NOT EXISTS "
                f"{coluna} {tipo}"))

        conn.execute(sa_text(
            "ALTER TABLE faixa_alcada ADD COLUMN IF NOT EXISTS "
            "fornecedores_minimos SMALLINT NOT NULL DEFAULT 2"))

        # Índice para a soma do fracionamento: a consulta é sempre
        # (admin, obra, etapa, created_at) e roda a cada carimbo.
        conn.execute(sa_text(
            "CREATE INDEX IF NOT EXISTS ix_requisicao_fracionamento "
            "ON requisicao_compra (admin_id, obra_id, obra_servico_custo_id, "
            "created_at)"))

    logger.info("[Migration 287] requisicao_compra ganhou urgência, carimbo de "
                "alçada e emergência; faixa_alcada ganhou fornecedores_minimos.")
```

E o registro, logo depois da linha da 286 em `executar_migracoes`:

```python
            (287, "Alçadas avançadas — urgência na SC, carimbo da faixa exigida (com motivos), rito de emergência 48h e fornecedores_minimos por faixa", _migration_287_alcadas_avancadas),
```

- [ ] **Step 6: Aplicar e rodar o teste**

```bash
python pre_start.py 2>&1 | grep -E "Migration 287|Falhas"
python -m pytest tests/test_alcada_regras.py -q -p no:cacheprovider
```

Esperado: `[Migration 287] ...` no log, `❌ Falhas: 0`, e `1 passed`.

- [ ] **Step 7: Commit**

```bash
git add models.py migrations.py tests/test_alcada_regras.py
git commit -m "feat(compras): migração 287 — urgência, carimbo de alçada e emergência na requisição"
```

---

### Task 2: A soma do fracionamento

**Arquivos:**
- Criar: `services/alcada_regras.py`
- Testar: `tests/test_alcada_regras.py`

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `tests/test_alcada_regras.py`:

```python
def test_soma_do_fracionamento_junta_a_mesma_obra_e_etapa_na_janela():
    from services.alcada_regras import soma_da_janela
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _sc(admin.id, obra.id, 4000, dias_atras=5)
        _sc(admin.id, obra.id, 3000, dias_atras=29)
        alvo = _sc(admin.id, obra.id, 2000)
        soma, somadas = soma_da_janela(alvo)
        assert soma == Decimal('7000.00')
        assert len(somadas) == 2


def test_soma_ignora_a_propria_sc():
    """No carimbo a SC já está em AGUARDANDO — sem a exclusão ela se somaria
    a si mesma e todo valor contaria em dobro."""
    from services.alcada_regras import soma_da_janela
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        alvo = _sc(admin.id, obra.id, 2000)
        soma, somadas = soma_da_janela(alvo)
        assert soma == Decimal('0')
        assert somadas == []


def test_soma_respeita_a_borda_de_30_dias():
    from services.alcada_regras import soma_da_janela
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _sc(admin.id, obra.id, 1000, dias_atras=30)   # dentro
        _sc(admin.id, obra.id, 9000, dias_atras=31)   # fora
        alvo = _sc(admin.id, obra.id, 500)
        soma, _ = soma_da_janela(alvo)
        assert soma == Decimal('1000.00')


@pytest.mark.parametrize('estado,conta', [
    (EstadoRequisicao.AGUARDANDO_APROVACAO, True),
    (EstadoRequisicao.APROVADA, True),
    (EstadoRequisicao.CONVERTIDA, True),
    (EstadoRequisicao.RASCUNHO, False),
    (EstadoRequisicao.REJEITADA, False),
    (EstadoRequisicao.CANCELADA, False),
])
def test_soma_conta_so_o_que_e_compromisso(estado, conta):
    from services.alcada_regras import soma_da_janela
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _sc(admin.id, obra.id, 1000, estado=estado, dias_atras=2)
        alvo = _sc(admin.id, obra.id, 500)
        soma, _ = soma_da_janela(alvo)
        assert soma == (Decimal('1000.00') if conta else Decimal('0'))


def test_soma_nao_mistura_etapas_nem_obras_nem_tenants():
    from services.alcada_regras import soma_da_janela
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        outra = _obra(admin.id)
        alheio = _admin()
        obra_alheia = _obra(alheio.id)
        _sc(admin.id, outra.id, 8000, dias_atras=1)          # outra obra
        _sc(alheio.id, obra_alheia.id, 8000, dias_atras=1)   # outro tenant
        _sc(admin.id, obra.id, 8000, dias_atras=1, osc_id=None)  # balde da obra
        alvo = _sc(admin.id, obra.id, 500)
        soma, _ = soma_da_janela(alvo)
        assert soma == Decimal('8000.00')
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
python -m pytest tests/test_alcada_regras.py -q -p no:cacheprovider
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'services.alcada_regras'`.

- [ ] **Step 3: Escrever o módulo**

Criar `services/alcada_regras.py`:

```python
"""As regras que sobem a alçada além do valor — spec 2026-08-16.

Separado de `alcada_compras.py` de propósito: as quatro condições consultam
quatro subsistemas diferentes (mapa de concorrência, custo orçado, outras
requisições, a própria SC). Empurrar isso para dentro do motor de faixas o
tornaria o arquivo que ninguém mais entende.

Este módulo não decide permissão e não escreve estado. Ele responde uma
pergunta só: **que faixa esta requisição exige, e por quê**.
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from models import EstadoRequisicao, RequisicaoCompra, db

logger = logging.getLogger('alcada_regras')

# Janela do anti-fracionamento, em dias CORRIDOS. Não é mês-calendário:
# mês fechado convida a esperar o dia 1º.
JANELA_DIAS = 30

# Estados que representam COMPROMISSO de gasto. Rascunho não é compromisso
# (e um rascunho abandonado elevaria a exigência de quem está trabalhando);
# rejeitada e cancelada são a prova de que o dinheiro não vai sair.
ESTADOS_QUE_SOMAM = (
    EstadoRequisicao.AGUARDANDO_APROVACAO,
    EstadoRequisicao.APROVADA,
    EstadoRequisicao.CONVERTIDA,
)


def _d(v):
    return Decimal(str(v or 0))


def soma_da_janela(requisicao, agora=None):
    """(soma, somadas) das outras SCs da mesma obra+etapa nos 30 dias.

    `somadas` é uma lista de dicts prontos para o carimbo — é o que a tela
    mostra quando alguém pergunta por que a exigência subiu.

    A própria requisição fica de fora (`id !=`): no momento do carimbo ela
    já está em AGUARDANDO_APROVACAO, e sem isso se somaria a si mesma.

    Etapa NULL casa com etapa NULL — é o balde único da obra, e é o que
    impede que deixar o centro de custo em branco desligue a regra.
    """
    agora = agora or datetime.utcnow()
    corte = agora - timedelta(days=JANELA_DIAS)

    q = (RequisicaoCompra.query
         .filter(RequisicaoCompra.admin_id == requisicao.admin_id,
                 RequisicaoCompra.obra_id == requisicao.obra_id,
                 RequisicaoCompra.id != requisicao.id,
                 RequisicaoCompra.estado.in_(ESTADOS_QUE_SOMAM),
                 RequisicaoCompra.created_at >= corte))
    if requisicao.obra_servico_custo_id is None:
        q = q.filter(RequisicaoCompra.obra_servico_custo_id.is_(None))
    else:
        q = q.filter(RequisicaoCompra.obra_servico_custo_id ==
                     requisicao.obra_servico_custo_id)

    somadas, total = [], Decimal('0')
    for outra in q.order_by(RequisicaoCompra.created_at).all():
        total += _d(outra.valor_estimado)
        somadas.append({
            'numero': outra.numero,
            'valor': float(_d(outra.valor_estimado)),
            'data': outra.created_at.date().isoformat() if outra.created_at else None,
        })
    return total, somadas
```

- [ ] **Step 4: Rodar e ver passar**

```bash
python -m pytest tests/test_alcada_regras.py -q -p no:cacheprovider
```

Esperado: `11 passed` (1 da Task 1 + 10 destes, contando a parametrização).

- [ ] **Step 5: Commit**

```bash
git add services/alcada_regras.py tests/test_alcada_regras.py
git commit -m "feat(compras): soma da janela de 30 dias — a base do anti-fracionamento"
```

---

### Task 3: As quatro condições e os degraus

**Arquivos:**
- Modificar: `services/alcada_regras.py`
- Testar: `tests/test_alcada_regras.py`

- [ ] **Step 1: Escrever os testes que falham**

```python
def _faixas(admin_id):
    """As três faixas recomendadas, com o piso de cotações da fase nova."""
    for ordem, ate, aprov, adm, mapa, forn in [
            (1, Decimal('5000.00'), 1, False, False, 2),
            (2, Decimal('30000.00'), 2, True, False, 2),
            (3, None, 2, True, True, 3)]:
        db.session.add(FaixaAlcada(
            admin_id=admin_id, ordem=ordem, valor_ate=ate,
            aprovacoes_necessarias=aprov, exige_admin=adm,
            exige_mapa_concorrencia=mapa, fornecedores_minimos=forn,
            ativo=True))
    db.session.commit()


def test_sem_concorrencia_sobe_um_degrau():
    from services.alcada_regras import avaliar_alcada
    with app.app_context():
        admin = _admin()
        _faixas(admin.id)
        obra = _obra(admin.id)
        sc = _sc(admin.id, obra.id, 1000)          # faixa 1 pelo valor
        av = avaliar_alcada(sc)
        assert [c['codigo'] for c in av.condicoes] == ['sem_concorrencia']
        assert av.degraus == 1
        assert av.faixa_final.ordem == 2


def test_urgente_soma_com_sem_concorrencia_e_sobe_dois():
    from services.alcada_regras import avaliar_alcada
    with app.app_context():
        admin = _admin()
        _faixas(admin.id)
        obra = _obra(admin.id)
        sc = _sc(admin.id, obra.id, 1000, urgencia='urgente')
        av = avaliar_alcada(sc)
        assert sorted(c['codigo'] for c in av.condicoes) == \
            ['sem_concorrencia', 'urgente']
        assert av.degraus == 2
        assert av.faixa_final.ordem == 3


def test_degraus_nao_passam_da_faixa_mais_alta():
    """Teto: três degraus a partir da faixa 1 não apontam para faixa 4."""
    from services.alcada_regras import avaliar_alcada
    with app.app_context():
        admin = _admin()
        _faixas(admin.id)
        obra = _obra(admin.id)
        sc = _sc(admin.id, obra.id, 1000, urgencia='urgente')
        sc.emergencia_ativada_em = None
        db.session.commit()
        av = avaliar_alcada(sc)
        assert av.faixa_final.ordem == 3
        assert av.faixa_final.valor_ate is None


def test_fracionamento_leva_a_faixa_da_soma():
    """R$ 4 mil que fecham R$ 32 mil no mês são julgados pela faixa de 30 mil+."""
    from services.alcada_regras import avaliar_alcada
    with app.app_context():
        admin = _admin()
        _faixas(admin.id)
        obra = _obra(admin.id)
        _sc(admin.id, obra.id, 28000, dias_atras=3)
        sc = _sc(admin.id, obra.id, 4000)
        av = avaliar_alcada(sc)
        assert av.valor_efetivo == Decimal('32000.00')
        assert av.faixa_base.ordem == 3
        assert len(av.somadas) == 1


def test_tenant_sem_faixa_continua_na_faixa_de_seguranca():
    """Falha fechada: nenhuma condição pode afrouxar o tenant sem configuração."""
    from services.alcada_regras import avaliar_alcada
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        sc = _sc(admin.id, obra.id, 1000)
        av = avaliar_alcada(sc)
        assert av.faixa_final.aprovacoes_necessarias == 2
        assert av.faixa_final.exige_admin is True
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
python -m pytest tests/test_alcada_regras.py -q -p no:cacheprovider -k "degrau or fracionamento or seguranca or urgente"
```

Esperado: FAIL com `ImportError: cannot import name 'avaliar_alcada'`.

- [ ] **Step 3: Implementar as condições**

Acrescentar a `services/alcada_regras.py`:

```python
class Avaliacao:
    """O que o motor decidiu, e com que números. Não persiste nada."""

    def __init__(self, valor_estimado, valor_efetivo, somadas, faixa_base,
                 condicoes, faixa_final):
        self.valor_estimado = valor_estimado
        self.valor_efetivo = valor_efetivo
        self.somadas = somadas
        self.faixa_base = faixa_base
        self.condicoes = condicoes
        self.degraus = len(condicoes)
        self.faixa_final = faixa_final

    def motivos_para_carimbo(self):
        """O JSON que vai para `requisicao_compra.alcada_motivos`."""
        return {
            'valor_estimado': float(self.valor_estimado),
            'valor_efetivo': float(self.valor_efetivo),
            'somadas': self.somadas,
            'faixa_base_ordem': getattr(self.faixa_base, 'ordem', None),
            'condicoes': self.condicoes,
        }


def _sem_concorrencia(requisicao):
    """A SC teve concorrência? Piso FIXO de 2 fornecedores.

    Não usa o `fornecedores_minimos` da faixa de propósito: amarrar a
    condição à faixa final seria circular (a faixa depende dos degraus, que
    dependem da condição) e inútil — só dispararia onde a pendência de
    `exige_mapa_concorrencia` já barra. São duas perguntas diferentes:
    aqui, "houve concorrência?"; lá, "esta faixa aceita fechar sem mapa?".
    """
    from services.alcada_compras import mapa_serve_de_concorrencia
    if mapa_serve_de_concorrencia(requisicao, minimo=2):
        return None
    return {'codigo': 'sem_concorrencia',
            'texto': 'compra sem mapa de concorrência com ao menos 2 fornecedores',
            'numeros': {}}


def _estoura_orcamento(requisicao, comprometido):
    """Realizado + comprometido + esta SC passa do orçado da etapa?

    Sem etapa, a base é a obra inteira. Orçado indisponível NÃO dispara — e
    o motivo registra isso, em vez de mentir um número.
    """
    from services.custo_orcado import (custo_orcado_da_obra,
                                       projecao_de_custo_por_servico)
    osc_id = requisicao.obra_servico_custo_id
    if osc_id:
        projecao = projecao_de_custo_por_servico(
            requisicao.obra_id, requisicao.admin_id).get(osc_id) or {}
        orcado = _d(projecao.get('orcado'))
        realizado = _d(projecao.get('realizado'))
        base = f'etapa {osc_id}'
    else:
        orcado = _d(custo_orcado_da_obra(requisicao.obra_id, requisicao.admin_id))
        realizado = Decimal('0')
        base = 'obra'

    if orcado <= 0:
        return None

    total = realizado + comprometido + _d(requisicao.valor_estimado)
    if total <= orcado:
        return None
    return {'codigo': 'estoura_orcamento',
            'texto': f'o pedido leva o custo de {base} acima do orçado',
            'numeros': {'orcado': float(orcado), 'realizado': float(realizado),
                        'comprometido': float(comprometido),
                        'esta_sc': float(_d(requisicao.valor_estimado))}}


def _nao_menor_preco(requisicao):
    """Existe cotação mais barata que a selecionada, em algum item do mapa?

    Valor zero é "não cotou", não "de graça" — fica de fora da comparação.
    """
    from models import MapaCotacao
    if not requisicao.mapa_v2_id:
        return None
    cotacoes = (MapaCotacao.query
                .filter_by(mapa_id=requisicao.mapa_v2_id,
                           admin_id=requisicao.admin_id)
                .filter(MapaCotacao.valor_unitario > 0)
                .all())
    por_item = {}
    for c in cotacoes:
        por_item.setdefault(c.item_id, []).append(c)

    for item_id, lista in por_item.items():
        escolhida = next((c for c in lista if c.selecionado), None)
        if escolhida is None:
            continue
        menor = min(_d(c.valor_unitario) for c in lista)
        if _d(escolhida.valor_unitario) > menor:
            return {'codigo': 'nao_menor_preco',
                    'texto': 'o fornecedor escolhido não é o de menor preço',
                    'numeros': {'item_id': item_id,
                                'escolhido': float(_d(escolhida.valor_unitario)),
                                'menor': float(menor)}}
    return None


def _urgente(requisicao):
    if (requisicao.urgencia or 'normal') != 'urgente':
        return None
    return {'codigo': 'urgente',
            'texto': 'requisição marcada como urgente',
            'numeros': {}}


def _faixa_por_degraus(admin_id, faixa_base, degraus):
    """A faixa `degraus` acima da base, com teto na mais alta ativa."""
    from services.alcada_compras import faixas_ordenadas
    faixas = faixas_ordenadas(admin_id)
    if not faixas or getattr(faixa_base, 'id', None) is None:
        return faixa_base          # _FaixaSeguranca: já é o máximo
    try:
        i = faixas.index(faixa_base)
    except ValueError:
        return faixa_base
    return faixas[min(i + degraus, len(faixas) - 1)]


def avaliar_alcada(requisicao, agora=None):
    """A avaliação completa. Uma passada, sem laço."""
    from services.alcada_compras import faixa_para_valor

    comprometido, somadas = soma_da_janela(requisicao, agora=agora)
    valor_efetivo = _d(requisicao.valor_estimado) + comprometido
    faixa_base = faixa_para_valor(requisicao.admin_id, valor_efetivo)

    condicoes = [c for c in (
        _sem_concorrencia(requisicao),
        _estoura_orcamento(requisicao, comprometido),
        _nao_menor_preco(requisicao),
        _urgente(requisicao),
    ) if c]

    faixa_final = _faixa_por_degraus(requisicao.admin_id, faixa_base,
                                     len(condicoes))
    return Avaliacao(_d(requisicao.valor_estimado), valor_efetivo, somadas,
                     faixa_base, condicoes, faixa_final)
```

- [ ] **Step 4: Expor os dois auxiliares no motor de faixas**

Em `services/alcada_compras.py`, trocar `_mapa_serve_de_concorrencia` por uma versão
parametrizada e extrair a ordenação de faixas, que agora tem dois consumidores:

```python
def faixas_ordenadas(admin_id):
    """As faixas ativas do tenant, da menor para a maior. Teto por último."""
    return (FaixaAlcada.query
            .filter_by(admin_id=admin_id, ativo=True)
            .order_by(FaixaAlcada.valor_ate.asc().nullslast(),
                      FaixaAlcada.ordem.asc())
            .all())


def mapa_serve_de_concorrencia(requisicao, minimo=2):
    """Mapa V2 concluído, do mesmo tenant e da mesma obra, com >= `minimo`
    fornecedores. Um fornecedor só não é concorrência — é orçamento.

    `minimo` passou a ser parâmetro na fase de alçadas avançadas: a condição
    que sobe degrau usa o piso fixo de 2, e a pendência da faixa usa o
    `fornecedores_minimos` dela (o "corte de 3 cotações").
    """
    if not requisicao.mapa_v2_id:
        return False
    mapa = db.session.get(MapaConcorrenciaV2, requisicao.mapa_v2_id)
    if mapa is None:
        return False
    if mapa.obra_id != requisicao.obra_id or mapa.admin_id != requisicao.admin_id:
        return False
    if mapa.status != 'concluido':
        return False
    return len(mapa.fornecedores) >= minimo
```

E substituir o corpo de `faixa_para_valor` para usar `faixas_ordenadas(admin_id)` em vez
da query embutida, mantendo o resto idêntico. O nome antigo
`_mapa_serve_de_concorrencia` deixa de existir; o único chamador é
`pendencias_de_aprovacao`, atualizado na Task 4.

- [ ] **Step 5: Rodar e ver passar**

```bash
python -m pytest tests/test_alcada_regras.py -q -p no:cacheprovider
```

Esperado: todos verdes.

- [ ] **Step 6: Commit**

```bash
git add services/alcada_regras.py services/alcada_compras.py tests/test_alcada_regras.py
git commit -m "feat(compras): as quatro condições que sobem degrau, somando com teto"
```

---

### Task 4: O carimbo

**Arquivos:**
- Modificar: `services/alcada_regras.py`, `services/alcada_compras.py`,
  `services/requisicao_compra.py:116-154`
- Testar: `tests/test_alcada_regras.py`

- [ ] **Step 1: Escrever os testes que falham**

```python
def _enviar(sc, usuario):
    from services.requisicao_compra import transicionar
    transicionar(sc, EstadoRequisicao.AGUARDANDO_APROVACAO, usuario,
                 motivo='envio de teste')
    db.session.commit()
    return sc


def test_envio_carimba_a_faixa_e_o_porque():
    with app.app_context():
        admin = _admin()
        _faixas(admin.id)
        obra = _obra(admin.id)
        sc = _sc(admin.id, obra.id, 1000, estado=EstadoRequisicao.RASCUNHO)
        _enviar(sc, admin)
        assert sc.alcada_carimbada_em is not None
        assert sc.alcada_degraus == 1                    # sem concorrência
        assert sc.faixa_exigida_id is not None
        assert sc.alcada_motivos['condicoes'][0]['codigo'] == 'sem_concorrencia'


def test_carimbo_nao_muda_por_fato_posterior():
    """Uma SC de R$ 28 mil criada DEPOIS não pode mudar a régua de quem já
    está em aprovação."""
    from services.alcada_compras import pendencias_de_aprovacao
    with app.app_context():
        admin = _admin()
        _faixas(admin.id)
        obra = _obra(admin.id)
        sc = _sc(admin.id, obra.id, 1000, estado=EstadoRequisicao.RASCUNHO)
        _enviar(sc, admin)
        antes = list(pendencias_de_aprovacao(sc))

        _sc(admin.id, obra.id, 28000)      # fato novo na mesma obra/etapa
        assert list(pendencias_de_aprovacao(sc)) == antes


def test_sc_sem_carimbo_continua_avaliada_na_leitura():
    """SC anterior à fase (sem carimbo) não pode quebrar."""
    from services.alcada_compras import pendencias_de_aprovacao
    with app.app_context():
        admin = _admin()
        _faixas(admin.id)
        obra = _obra(admin.id)
        sc = _sc(admin.id, obra.id, 1000)   # criada crua, sem passar pelo envio
        assert sc.alcada_carimbada_em is None
        assert pendencias_de_aprovacao(sc)   # não levanta, e cobra algo
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
python -m pytest tests/test_alcada_regras.py -q -p no:cacheprovider -k carimb
```

Esperado: FAIL — `alcada_carimbada_em is not None` dá `None`.

- [ ] **Step 3: Implementar o carimbo**

Em `services/alcada_regras.py`:

```python
def carimbar_alcada(requisicao, agora=None):
    """Grava na SC a faixa exigida, os degraus e o porquê. NÃO commita.

    Roda na entrada em AGUARDANDO_APROVACAO — a mesma fronteira que o motor
    de votos usa para abrir rodada, para que carimbo e rodada nasçam juntos.
    """
    av = avaliar_alcada(requisicao, agora=agora)
    requisicao.faixa_exigida_id = getattr(av.faixa_final, 'id', None)
    requisicao.alcada_degraus = av.degraus
    requisicao.alcada_motivos = av.motivos_para_carimbo()
    requisicao.alcada_carimbada_em = agora or datetime.utcnow()
    db.session.flush()
    logger.info('alçada carimbada: requisicao=%s faixa=%s degraus=%s',
                requisicao.numero, requisicao.faixa_exigida_id, av.degraus)
    return av
```

Em `services/requisicao_compra.py`, dentro de `transicionar`, logo depois de
`requisicao.estado = novo_estado`:

```python
    # Alçadas avançadas: a exigência é decidida AQUI, na entrada da rodada
    # de aprovação, e não muda mais até um reenvio abrir rodada nova.
    if novo_estado == EstadoRequisicao.AGUARDANDO_APROVACAO:
        from services.alcada_regras import carimbar_alcada
        carimbar_alcada(requisicao)
```

Em `services/alcada_compras.py`, no topo de `pendencias_de_aprovacao`, trocar a linha
que resolve a faixa:

```python
    faixa = faixa_exigida(requisicao)
```

e acrescentar a função:

```python
def faixa_exigida(requisicao):
    """A faixa carimbada; recalculada na leitura quando não houver carimbo.

    O fallback é o que mantém a SC anterior às alçadas avançadas funcionando
    sem backfill — carimbar retroativamente mudaria a régua de rodadas em
    curso, que é o que o carimbo existe para impedir.
    """
    if getattr(requisicao, 'alcada_carimbada_em', None) and \
            requisicao.faixa_exigida_id:
        faixa = db.session.get(FaixaAlcada, requisicao.faixa_exigida_id)
        if faixa is not None:
            return faixa
    return faixa_para_valor(requisicao.admin_id, requisicao.valor_estimado)
```

E trocar, no mesmo arquivo, a chamada de concorrência para usar o mínimo da faixa:

```python
    if faixa.exige_mapa_concorrencia and not mapa_serve_de_concorrencia(
            requisicao, minimo=getattr(faixa, 'fornecedores_minimos', 2)):
        faltando.append(
            f'falta mapa de concorrência concluído com pelo menos '
            f'{getattr(faixa, "fornecedores_minimos", 2)} fornecedores '
            f'vinculado a esta requisição')
```

- [ ] **Step 4: Rodar e ver passar**

```bash
python -m pytest tests/test_alcada_regras.py tests/test_fase3_alcada.py -q -p no:cacheprovider
```

Esperado: verdes nos dois arquivos — o segundo é a regressão da Fase 3.

- [ ] **Step 5: Commit**

```bash
git add services/ tests/test_alcada_regras.py
git commit -m "feat(compras): a alçada exigida é carimbada ao entrar em aprovação"
```

---

### Task 5: Urgência na SC

**Arquivos:**
- Modificar: `compras_views.py` (rota `requisicao_nova_post`, por volta de `:1639`),
  `templates/compras/requisicao_nova.html`
- Testar: `tests/test_alcada_regras.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
def test_urgente_sem_justificativa_e_recusado():
    from services.requisicao_compra import DadosInvalidos, validar_urgencia
    with app.app_context():
        with pytest.raises(DadosInvalidos):
            validar_urgencia('urgente', '')
        validar_urgencia('urgente', 'concretagem parada, caminhão a caminho')
        validar_urgencia('normal', '')
```

- [ ] **Step 2: Rodar e ver falhar**

Esperado: `ImportError: cannot import name 'validar_urgencia'`.

- [ ] **Step 3: Implementar**

Em `services/requisicao_compra.py`:

```python
class DadosInvalidos(ValueError):
    """Dado de formulário que a regra recusa. A rota vira flash."""


URGENCIAS = ('normal', 'urgente')


def validar_urgencia(urgencia, justificativa):
    """Urgente exige justificativa escrita. Devolve a dupla normalizada.

    A validação é do serviço e não do schema: `NOT NULL` obrigaria backfill
    em SC legada que nunca teve urgência, e um default inventado ('—') seria
    pior do que a ausência.
    """
    urgencia = (urgencia or 'normal').strip().lower()
    if urgencia not in URGENCIAS:
        raise DadosInvalidos(f'Urgência inválida: {urgencia!r}.')
    justificativa = (justificativa or '').strip()
    if urgencia == 'urgente' and not justificativa:
        raise DadosInvalidos(
            'Requisição urgente exige justificativa — ela sobe a alçada, '
            'e quem aprova precisa saber por quê.')
    return urgencia, (justificativa or None)
```

Na rota `requisicao_nova_post` de `compras_views.py`, antes de montar a
`RequisicaoCompra`:

```python
        try:
            urgencia, justificativa_urgencia = validar_urgencia(
                request.form.get('urgencia'),
                request.form.get('justificativa_urgencia'))
        except DadosInvalidos as e:
            flash(str(e), 'danger')
            return redirect(url_for('compras.requisicao_nova'))
```

e passar `urgencia=urgencia, justificativa_urgencia=justificativa_urgencia` no
construtor.

No template `templates/compras/requisicao_nova.html`, dentro do formulário:

```html
<div class="col-md-4">
  <label class="form-label">Urgência</label>
  <select name="urgencia" id="urgencia" class="form-select">
    <option value="normal" selected>Normal</option>
    <option value="urgente">Urgente</option>
  </select>
</div>
<div class="col-md-8" id="bloco-justificativa-urgencia" style="display:none">
  <label class="form-label">Justificativa da urgência</label>
  <input type="text" name="justificativa_urgencia" class="form-control"
         placeholder="Por que não pode esperar o fluxo normal?">
  <div class="form-text">Urgente sobe um degrau de alçada.</div>
</div>
<script>
  document.getElementById('urgencia').addEventListener('change', function () {
    document.getElementById('bloco-justificativa-urgencia').style.display =
      this.value === 'urgente' ? '' : 'none';
  });
</script>
```

- [ ] **Step 4: Rodar e ver passar**

```bash
python -m pytest tests/test_alcada_regras.py -q -p no:cacheprovider -k urgen
```

- [ ] **Step 5: Commit**

```bash
git add services/requisicao_compra.py compras_views.py templates/compras/requisicao_nova.html tests/test_alcada_regras.py
git commit -m "feat(compras): urgência na requisição, com justificativa obrigatória"
```

---

### Task 6: O rito de emergência

**Arquivos:**
- Modificar: `services/alcada_regras.py`, `services/alcada_compras.py`
- Testar: `tests/test_alcada_regras.py`

- [ ] **Step 1: Escrever os testes que falham**

```python
def test_emergencia_deixa_um_admin_aprovar_sozinho():
    from services.alcada_compras import (esta_totalmente_aprovada,
                                         registrar_aprovacao)
    from services.alcada_regras import ativar_emergencia
    with app.app_context():
        admin = _admin()
        _faixas(admin.id)
        obra = _obra(admin.id)
        outro = _admin()
        outro.admin_id = admin.id
        db.session.commit()
        sc = _sc(admin.id, obra.id, 40000, estado=EstadoRequisicao.RASCUNHO,
                 solicitante_id=outro.id)
        _enviar(sc, outro)
        assert not esta_totalmente_aprovada(sc)      # faixa 3: 2 + admin + mapa

        ativar_emergencia(sc, admin, 'obra parada, betoneira a caminho')
        registrar_aprovacao(sc, admin)
        db.session.commit()
        assert esta_totalmente_aprovada(sc)
        assert sc.emergencia_prazo > sc.emergencia_ativada_em


def test_nao_admin_nao_aciona_emergencia():
    from services.alcada_regras import EmergenciaRecusada, ativar_emergencia
    with app.app_context():
        admin = _admin()
        _faixas(admin.id)
        obra = _obra(admin.id)
        comum = Usuario(username=f'c_{uuid.uuid4().hex[:8]}',
                        email=f'c_{uuid.uuid4().hex[:8]}@t.local', nome='Comum',
                        password_hash=generate_password_hash('x'),
                        tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
                        admin_id=admin.id)
        db.session.add(comum)
        db.session.commit()
        sc = _sc(admin.id, obra.id, 40000)
        with pytest.raises(EmergenciaRecusada):
            ativar_emergencia(sc, comum, 'preciso agora')


def test_emergencia_exige_motivo():
    from services.alcada_regras import EmergenciaRecusada, ativar_emergencia
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        sc = _sc(admin.id, obra.id, 40000)
        with pytest.raises(EmergenciaRecusada):
            ativar_emergencia(sc, admin, '   ')


def test_divida_vencida_trava_nova_emergencia_na_obra_e_nao_trava_o_resto():
    from services.alcada_regras import (ativar_emergencia,
                                        pode_ativar_emergencia)
    from services.alcada_compras import pendencias_de_aprovacao
    with app.app_context():
        admin = _admin()
        _faixas(admin.id)
        obra = _obra(admin.id)
        devedora = _sc(admin.id, obra.id, 40000)
        ativar_emergencia(devedora, admin, 'primeira urgência')
        devedora.emergencia_prazo = datetime.utcnow() - timedelta(hours=1)
        db.session.commit()

        ok, motivo = pode_ativar_emergencia(obra.id, admin.id)
        assert ok is False and devedora.numero in motivo

        # a compra normal da obra continua andando
        normal = _sc(admin.id, obra.id, 1000)
        assert isinstance(pendencias_de_aprovacao(normal), list)


def test_regularizar_fecha_a_divida():
    from services.alcada_compras import registrar_aprovacao
    from services.alcada_regras import (ativar_emergencia,
                                        pode_ativar_emergencia,
                                        regularizar_se_couber)
    with app.app_context():
        admin = _admin()
        db.session.add(FaixaAlcada(admin_id=admin.id, ordem=1, valor_ate=None,
                                   aprovacoes_necessarias=2, exige_admin=True,
                                   exige_mapa_concorrencia=False,
                                   fornecedores_minimos=2, ativo=True))
        db.session.commit()
        obra = _obra(admin.id)
        outro = _admin()
        outro.admin_id = admin.id
        db.session.commit()
        sc = _sc(admin.id, obra.id, 40000, solicitante_id=outro.id)
        ativar_emergencia(sc, admin, 'obra parada')
        registrar_aprovacao(sc, admin)
        registrar_aprovacao(sc, outro)
        regularizar_se_couber(sc)
        db.session.commit()
        assert sc.emergencia_regularizada_em is not None
        assert pode_ativar_emergencia(obra.id, admin.id)[0] is True
```

- [ ] **Step 2: Rodar e ver falhar**

Esperado: `ImportError: cannot import name 'ativar_emergencia'`.

- [ ] **Step 3: Implementar o rito**

Em `services/alcada_regras.py`:

```python
HORAS_DE_PRAZO = 48


class EmergenciaRecusada(Exception):
    """O rito não pode ser acionado. A mensagem é exibida ao usuário."""


def emergencia_ativa(requisicao):
    return (requisicao.emergencia_ativada_em is not None
            and requisicao.emergencia_regularizada_em is None)


def divida_vencida(requisicao, agora=None):
    agora = agora or datetime.utcnow()
    return (emergencia_ativa(requisicao)
            and requisicao.emergencia_prazo is not None
            and requisicao.emergencia_prazo < agora)


def pode_ativar_emergencia(obra_id, admin_id, agora=None):
    """(bool, motivo). Recusa quando a obra tem dívida de emergência vencida.

    Só a NOVA emergência é travada: a SC em curso anda, e a compra normal da
    obra segue livre. Ataca o abuso — usar emergência como rotina — sem
    parar o trabalho.
    """
    abertas = (RequisicaoCompra.query
               .filter(RequisicaoCompra.obra_id == obra_id,
                       RequisicaoCompra.admin_id == admin_id,
                       RequisicaoCompra.emergencia_ativada_em.isnot(None),
                       RequisicaoCompra.emergencia_regularizada_em.is_(None))
               .all())
    vencidas = [r for r in abertas if divida_vencida(r, agora)]
    if vencidas:
        numeros = ', '.join(r.numero for r in vencidas)
        return False, (f'Esta obra tem emergência não regularizada fora do '
                       f'prazo ({numeros}). Regularize antes de acionar outra.')
    return True, ''


def ativar_emergencia(requisicao, usuario, motivo, agora=None):
    """Um admin assume a compra agora; o resto vira dívida com prazo."""
    from models import TipoUsuario
    from models import RequisicaoTransicao

    agora = agora or datetime.utcnow()
    if getattr(usuario, 'tipo_usuario', None) not in (
            TipoUsuario.ADMIN, TipoUsuario.SUPER_ADMIN):
        raise EmergenciaRecusada(
            'Só um administrador aciona o rito de emergência.')
    if usuario.id != requisicao.admin_id and \
            getattr(usuario, 'admin_id', None) != requisicao.admin_id:
        raise EmergenciaRecusada('Requisição de outra empresa.')
    motivo = (motivo or '').strip()
    if not motivo:
        raise EmergenciaRecusada('Não há emergência sem explicação escrita.')

    ok, recusa = pode_ativar_emergencia(requisicao.obra_id,
                                        requisicao.admin_id, agora)
    if not ok:
        raise EmergenciaRecusada(recusa)

    requisicao.emergencia_ativada_em = agora
    requisicao.emergencia_prazo = agora + timedelta(hours=HORAS_DE_PRAZO)
    requisicao.emergencia_por_id = usuario.id
    db.session.add(RequisicaoTransicao(
        requisicao_id=requisicao.id, admin_id=requisicao.admin_id,
        de_estado=requisicao.estado, para_estado=requisicao.estado,
        usuario_id=usuario.id, papel_aplicado='ADMIN',
        valor_no_momento=requisicao.valor_estimado,
        motivo=f'[emergencia] {motivo}'))
    db.session.flush()
    logger.info('emergencia acionada: requisicao=%s por=%s prazo=%s',
                requisicao.numero, usuario.id, requisicao.emergencia_prazo)
    return requisicao


def regularizar_se_couber(requisicao, agora=None):
    """Fecha a dívida quando as pendências originais somem. Sem ação de tela."""
    from services.alcada_compras import pendencias_da_faixa
    if not emergencia_ativa(requisicao):
        return False
    if pendencias_da_faixa(requisicao):
        return False
    requisicao.emergencia_regularizada_em = agora or datetime.utcnow()
    db.session.flush()
    logger.info('emergencia regularizada: requisicao=%s', requisicao.numero)
    return True
```

Em `services/alcada_compras.py`, separar "o que a faixa pede" de "o que bloqueia agora":

```python
def pendencias_da_faixa(requisicao):
    """O que a FAIXA exige e ainda não foi atendido — ignora a emergência.

    É o que o rito transforma em dívida, e o que `regularizar_se_couber`
    consulta para saber se a dívida foi paga.
    """
    faixa = faixa_exigida(requisicao)
    faltando = []

    registradas = aprovacoes_registradas(requisicao)
    if registradas < faixa.aprovacoes_necessarias:
        restam = faixa.aprovacoes_necessarias - registradas
        faltando.append(
            f'faltam {restam} aprovação(ões) de {faixa.aprovacoes_necessarias}')

    if faixa.exige_admin and not _tem_aprovacao_de_admin(requisicao):
        faltando.append('falta a aprovação de um administrador')

    minimo = getattr(faixa, 'fornecedores_minimos', 2)
    if faixa.exige_mapa_concorrencia and not mapa_serve_de_concorrencia(
            requisicao, minimo=minimo):
        faltando.append(f'falta mapa de concorrência concluído com pelo menos '
                        f'{minimo} fornecedores vinculado a esta requisição')

    return faltando


def pendencias_de_aprovacao(requisicao):
    """O que BLOQUEIA a aprovação agora.

    Com emergência ativa, a faixa inteira dá lugar a uma única exigência —
    um administrador assumindo a compra. O resto continua devido (ver
    `dividas_de_emergencia`), com prazo, mas não trava a SC.
    """
    from services.alcada_regras import emergencia_ativa

    if emergencia_ativa(requisicao):
        if _tem_aprovacao_de_admin(requisicao):
            return []
        return ['emergência acionada: falta a aprovação de um administrador']
    return pendencias_da_faixa(requisicao)


def dividas_de_emergencia(requisicao):
    """O que a emergência adiou, para a tela mostrar com o prazo."""
    from services.alcada_regras import emergencia_ativa
    if not emergencia_ativa(requisicao):
        return []
    return pendencias_da_faixa(requisicao)
```

E chamar `regularizar_se_couber` ao fim de `registrar_aprovacao`:

```python
    from services.alcada_regras import regularizar_se_couber
    regularizar_se_couber(requisicao)
    return voto
```

- [ ] **Step 4: Rodar e ver passar**

```bash
python -m pytest tests/test_alcada_regras.py -q -p no:cacheprovider
```

- [ ] **Step 5: Commit**

```bash
git add services/ tests/test_alcada_regras.py
git commit -m "feat(compras): rito de emergência 48h — um admin assume agora, o resto vira dívida"
```

---

### Task 7: A tela diz por quê

**Arquivos:**
- Modificar: `compras_views.py` (rota `requisicao_detalhe`, `:1764`; rota nova de
  emergência), `templates/compras/requisicao_detalhe.html`
- Testar: `tests/test_alcada_regras.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
def test_detalhe_mostra_o_porque_da_exigencia():
    with app.app_context():
        admin = _admin()
        _faixas(admin.id)
        obra = _obra(admin.id)
        antiga = _sc(admin.id, obra.id, 28000, dias_atras=3)
        sc = _sc(admin.id, obra.id, 4000, estado=EstadoRequisicao.RASCUNHO)
        _enviar(sc, admin)
        sc_id, numero_antiga = sc.id, antiga.numero
    with app.test_client() as c:
        with c.session_transaction() as s:
            s['_user_id'] = str(admin.id)
            s['_fresh'] = True
        r = c.get(f'/compras/requisicoes/{sc_id}')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert numero_antiga in html          # a SC somada aparece nomeada
        assert 'sem mapa de concorrência' in html
```

- [ ] **Step 2: Rodar e ver falhar**

Esperado: FAIL no `assert numero_antiga in html`.

- [ ] **Step 3: Passar os motivos para o template**

Em `compras_views.py`, na rota `requisicao_detalhe`, acrescentar ao contexto:

```python
    from services.alcada_compras import dividas_de_emergencia, faixa_exigida
    from services.alcada_regras import divida_vencida
    contexto['alcada_motivos'] = requisicao.alcada_motivos or {}
    contexto['faixa_exigida'] = faixa_exigida(requisicao)
    contexto['dividas'] = dividas_de_emergencia(requisicao)
    contexto['divida_vencida'] = divida_vencida(requisicao)
```

(Se a rota devolver `render_template(..., chave=valor)` em vez de um dict, passar as
quatro chaves diretamente.)

Em `templates/compras/requisicao_detalhe.html`, ao lado do bloco de pendências:

```html
{% if alcada_motivos %}
<div class="card mb-3">
  <div class="card-header">Por que esta requisição exige o que exige</div>
  <div class="card-body">
    <p class="mb-2">
      Valor estimado R$ {{ '%.2f'|format(alcada_motivos.valor_estimado or 0) }};
      considerado para a faixa R$ {{ '%.2f'|format(alcada_motivos.valor_efetivo or 0) }}.
    </p>
    {% if alcada_motivos.somadas %}
    <p class="mb-1">Somadas (mesma obra e etapa, 30 dias):</p>
    <ul class="mb-2">
      {% for s in alcada_motivos.somadas %}
      <li>{{ s.numero }} — R$ {{ '%.2f'|format(s.valor) }} em {{ s.data }}</li>
      {% endfor %}
    </ul>
    {% endif %}
    {% if alcada_motivos.condicoes %}
    <p class="mb-1">Condições que subiram a alçada:</p>
    <ul class="mb-0">
      {% for c in alcada_motivos.condicoes %}<li>{{ c.texto }}</li>{% endfor %}
    </ul>
    {% endif %}
  </div>
</div>
{% endif %}

{% if dividas %}
<div class="alert {{ 'alert-danger' if divida_vencida else 'alert-warning' }}">
  <strong>Emergência acionada.</strong> Falta regularizar até
  {{ requisicao.emergencia_prazo.strftime('%d/%m/%Y %H:%M') }}:
  <ul class="mb-0">{% for d in dividas %}<li>{{ d }}</li>{% endfor %}</ul>
</div>
{% endif %}
```

- [ ] **Step 4: Rota do botão de emergência**

Em `compras_views.py`, ao lado de `requisicao_aprovar`:

```python
@compras_bp.route('/requisicoes/<int:requisicao_id>/emergencia', methods=['POST'])
@login_required
@admin_required
def requisicao_emergencia(requisicao_id):
    """Aciona o rito. Só admin — a checagem dura está no serviço."""
    from services.alcada_regras import EmergenciaRecusada, ativar_emergencia
    requisicao = _requisicao_do_tenant(requisicao_id)
    try:
        ativar_emergencia(requisicao, current_user,
                          request.form.get('motivo'))
        db.session.commit()
        flash('Emergência acionada — regularize em 48h.', 'warning')
    except EmergenciaRecusada as e:
        db.session.rollback()
        flash(str(e), 'danger')
    return redirect(url_for('compras.requisicao_detalhe',
                            requisicao_id=requisicao_id))
```

E o botão no template, dentro do bloco de ações:

```html
{% if current_user.tipo_usuario.name in ('ADMIN', 'SUPER_ADMIN')
      and not requisicao.emergencia_ativada_em %}
<form method="post"
      action="{{ url_for('compras.requisicao_emergencia', requisicao_id=requisicao.id) }}"
      class="d-inline"
      onsubmit="return confirm('Acionar emergência? Você assume a compra agora e a regularização vence em 48h.');">
  <input type="text" name="motivo" class="form-control form-control-sm d-inline-block"
         style="width:auto" placeholder="Motivo da emergência" required>
  <button class="btn btn-sm btn-outline-danger">Acionar emergência</button>
</form>
{% endif %}
```

- [ ] **Step 5: Rodar e ver passar**

```bash
python -m pytest tests/test_alcada_regras.py -q -p no:cacheprovider
```

- [ ] **Step 6: Commit**

```bash
git add compras_views.py templates/compras/ tests/test_alcada_regras.py
git commit -m "feat(compras): a tela diz por que a alçada subiu, e o admin aciona emergência por ela"
```

---

### Task 8: Semente das faixas e gate final

**Arquivos:**
- Modificar: `services/alcada_compras.py` (`FAIXAS_RECOMENDADAS`)
- Testar: suíte inteira

- [ ] **Step 1: Atualizar a recomendação semeada**

```python
FAIXAS_RECOMENDADAS = [
    # (ordem, valor_ate, aprovacoes, exige_admin, exige_mapa, fornecedores_minimos)
    (1, Decimal('5000.00'), 1, False, False, 2),
    (2, Decimal('30000.00'), 2, True, False, 2),
    (3, None, 2, True, True, 3),      # a faixa aberta pede TRÊS cotações
]
```

E `garantir_faixas_do_tenant` passa a desempacotar seis valores, gravando
`fornecedores_minimos=forn`.

- [ ] **Step 2: Rodar as suítes vizinhas**

```bash
python -m pytest tests/ -k "alcada or requisicao or compra" -m "not browser and not java" -q -p no:cacheprovider
```

Esperado: verde.

- [ ] **Step 3: Gate completo**

```bash
python -m pytest tests/ -m "not browser and not java" -q -p no:cacheprovider
```

Esperado: verde. O gate de 16/08 fechou em `2252 passed`; esperar esse número mais os
testes novos.

- [ ] **Step 4: Commit e push**

```bash
git add services/alcada_compras.py
git commit -m "feat(compras): a faixa aberta passa a pedir três cotações"
git push origin main
```

---

## Gate final (checklist da fase)

- [ ] `tests/test_alcada_regras.py` inteiro verde.
- [ ] `tests/test_fase3_alcada.py` (regressão da Fase 3) verde.
- [ ] Migração 287 aplicada num banco que já tinha a 286, sem falha.
- [ ] Gate completo verde no CI.
- [ ] Runbook do spec executado à mão em dev: duas SCs de R$ 4 mil na mesma etapa e a
      segunda subindo de faixa, com a primeira nomeada na tela.

---

## Status da execução — 2026-08-16

Todas as 8 tasks executadas na mesma sessão em que o plano foi escrito, em TDD:
teste vermelho pelo motivo certo antes de cada implementação.

| Task | Commit | Testes |
|---|---|---|
| 1 — Migração 287 e colunas | `8dfa25a` | 1 |
| 2 — Soma da janela | `44e26e5` | 11 |
| 3 — As quatro condições | `4afc412` | 16 (+63 da Fase 3) |
| 4 — O carimbo | `9756e38` | 83 com a regressão junto |
| 5 — Urgência na SC | `9544021` | 21 |
| 6 — Rito de emergência | `832c22b` | 26 (+85 da Fase 3) |
| 7 — A tela diz por quê | `7ccdbe6` | 29 |
| 8 — Semente e gate | — | ver abaixo |

### Três desvios do plano, todos achados executando

1. **`migrations.py:4589` desempacotava a tupla das faixas em cinco.** A
   migração 243 importa `FAIXAS_RECOMENDADAS` do serviço, então acrescentar
   `fornecedores_minimos` à constante quebraria a 243 **em banco novo** — que é
   exatamente o caminho do CI. Virou `*_`, com o comentário de que a tupla
   cresce a cada fase e a 243 não pode gravar coluna que a 287 ainda vai criar.
   Provado rodando a cadeia inteira num banco criado do zero: 0 falhas.

2. **A rota do detalhe montava a faixa com `faixa_para_valor(valor_estimado)`.**
   A tela contaria uma história diferente da do motor a partir do primeiro
   carimbo. Passou a usar `faixa_exigida`, e ganhou teste próprio
   (`test_detalhe_mostra_a_faixa_CARIMBADA_e_nao_a_do_valor`).

3. **Teste de emergência precisava de um segundo ADMIN no MESMO tenant.**
   O helper `_admin()` cria admin de tenant próprio; sem o
   `_admin_do_tenant(admin_id)`, `pode_aprovar` recusava por "requisição de
   outra empresa" e o teste passaria pelo motivo errado — a mesma armadilha
   registrada no D1 da Fase 0.6.

### Testes acrescentados além do plano

- `test_reenvio_depois_de_rejeicao_recarimba` — rodada nova, régua nova, com um
  fato novo entrando entre as duas rodadas.
- `test_detalhe_mostra_a_faixa_CARIMBADA_e_nao_a_do_valor` — o desvio 2.
- `test_rota_de_emergencia_aciona_e_recusa_nao_admin` — a rota, não só o
  serviço.
- Em `test_divida_vencida_...`, a asserção de que **outra obra do mesmo tenant
  não é contaminada** pela dívida.
