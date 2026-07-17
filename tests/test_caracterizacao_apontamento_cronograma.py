"""
Módulo 1 (cronograma .mpp) — Testes de CARACTERIZAÇÃO dos dois caminhos de
apontamento de produção do cronograma, ANTES da extração do serviço único
(`services/cronograma_apontamento_service.py`).

Congelam o comportamento ATUAL (valores exatos de `quantidade_acumulada`,
`percentual_realizado`, `percentual_planejado` e `percentual_concluido` da
tarefa) dos dois caminhos duplicados:

  Caminho A — POST /salvar-rdo-flexivel (views/rdo.py, bloco "V2: Processar
              apontamentos de produção do cronograma"): campos de formulário
              `cronograma_tarefa_<id>=<qty>`; sempre CRIA um novo
              RDOApontamentoCronograma; ignora qty <= 0.
  Caminho B — POST /cronograma/rdo/<id>/apontar (cronograma_views.py,
              apontar_producao): JSON {tarefa_cronograma_id,
              quantidade_executada_dia}; UPSERT (atualiza o apontamento
              existente do mesmo RDO+tarefa).

Fórmula congelada (idêntica nos dois caminhos):
  acum_anterior = SUM(quantidade_executada_dia) de RDOs com
                  data_relatorio < data do RDO atual (mesma tarefa/admin)
  nova_acumulada = acum_anterior + qty_dia
  percentual_realizado = min(100.0, round(nova_acumulada / quantidade_total
                          * 100, 2)) quando quantidade_total > 0; senão 0.0
                          (fallback percentual — tarefa sem quantidade física)
  percentual_planejado = calcular_progresso_rdo(...)['percentual_planejado']
                          (100.0 com data_fim no passado; 0.0 com data_inicio
                          no futuro; None sem plano calculável)

Invariantes congeladas: incremento = diferença de acumulados; fallback
percentual quando não há `quantidade_total`; teto min(100.0, ...);
arredondamento round(..., 2).

Qualquer mudança de comportamento na extração do serviço DEVE quebrar
estes testes.
"""
import os
import sys
from datetime import date, datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from werkzeug.security import generate_password_hash

from models import (
    Usuario, TipoUsuario, Cliente, Obra,
    TarefaCronograma, RDO, RDOApontamentoCronograma,
)

pytestmark = pytest.mark.integration

SENHA = 'Senha@2026'
# Datas fixas (determinísticas) — o "hoje" do cenário é D0.
D0 = date(2026, 6, 15)


def _suffix() -> str:
    return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')


@pytest.fixture(scope='module')
def ambiente():
    """Admin V2 + cliente + obra compartilhados pelos testes do módulo."""
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    suf = _suffix()
    with app.app_context():
        admin = Usuario(
            username=f'carac_apont_{suf}',
            email=f'carac_apont_{suf}@test.local',
            nome='Caracterização Apontamento',
            password_hash=generate_password_hash(SENHA),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True,
            versao_sistema='v2',
        )
        db.session.add(admin)
        db.session.flush()
        cliente = Cliente(
            admin_id=admin.id, nome=f'Cliente Carac {suf}',
            email=f'cli_carac_{suf}@test.local', telefone='11988887777',
        )
        db.session.add(cliente)
        db.session.flush()
        obra = Obra(
            nome=f'Obra Caracterização {suf}',
            codigo=f'CARAC-{suf[:10]}',
            admin_id=admin.id,
            cliente_id=cliente.id,
            status='Em andamento',
            data_inicio=D0 - timedelta(days=60),
        )
        db.session.add(obra)
        db.session.commit()
        dados = {
            'admin_id': admin.id,
            'admin_email': admin.email,
            'obra_id': obra.id,
        }
    return dados


@pytest.fixture(scope='module')
def client(ambiente):
    """Test client autenticado como o admin V2 do cenário."""
    c = app.test_client()
    r = c.post('/login', data={
        'email': ambiente['admin_email'], 'password': SENHA,
    }, follow_redirects=False)
    assert r.status_code in (302, 303), f'login falhou (status={r.status_code})'
    return c


# ───────────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────────

def _criar_tarefa(ambiente, *, quantidade_total, com_plano='passado'):
    """Cria TarefaCronograma folha. `com_plano`:
    'passado' → data_fim antes de D0 (planejado congela em 100.0);
    'futuro'  → data_inicio depois de D0 (planejado congela em 0.0);
    None      → sem data_inicio (planejado congela em None)."""
    suf = _suffix()
    kw = dict(
        obra_id=ambiente['obra_id'], admin_id=ambiente['admin_id'],
        nome_tarefa=f'Tarefa Carac {suf}', ordem=1,
        quantidade_total=quantidade_total, responsavel='empresa',
    )
    if com_plano == 'passado':
        kw.update(duracao_dias=10,
                  data_inicio=D0 - timedelta(days=30),
                  data_fim=D0 - timedelta(days=20))
    elif com_plano == 'futuro':
        kw.update(duracao_dias=10,
                  data_inicio=D0 + timedelta(days=10),
                  data_fim=D0 + timedelta(days=20))
    else:
        kw.update(duracao_dias=1, data_inicio=None, data_fim=None)
    with app.app_context():
        t = TarefaCronograma(**kw)
        db.session.add(t)
        db.session.commit()
        return t.id


def _post_rdo_flexivel(client, ambiente, data_rdo, apontamentos: dict):
    """Caminho A: POST /salvar-rdo-flexivel com cronograma_tarefa_<id>=qty."""
    form = {
        'obra_id': str(ambiente['obra_id']),
        'admin_id_form': str(ambiente['admin_id']),
        'data_relatorio': data_rdo.isoformat(),
        'observacoes_gerais': 'RDO caracterização apontamento',
    }
    for tid, qty in apontamentos.items():
        form[f'cronograma_tarefa_{tid}'] = str(qty)
    r = client.post('/salvar-rdo-flexivel', data=form, follow_redirects=False)
    assert r.status_code in (200, 302, 303), \
        f'POST /salvar-rdo-flexivel falhou (status={r.status_code})'
    return r


def _criar_rdo_direto(ambiente, data_rdo):
    """Cria um RDO direto no banco (para o caminho B, que aponta em RDO já existente)."""
    suf = _suffix()
    with app.app_context():
        rdo = RDO(
            numero_rdo=f'RC-{suf[4:]}'[:20],  # varchar(20)
            obra_id=ambiente['obra_id'], admin_id=ambiente['admin_id'],
            data_relatorio=data_rdo, local='Campo', status='Finalizado',
        )
        db.session.add(rdo)
        db.session.commit()
        return rdo.id


def _post_apontar(client, rdo_id, tarefa_id, qty):
    """Caminho B: POST /cronograma/rdo/<id>/apontar."""
    r = client.post(
        f'/cronograma/rdo/{rdo_id}/apontar',
        json={'tarefa_cronograma_id': tarefa_id, 'quantidade_executada_dia': qty},
    )
    assert r.status_code == 200, \
        f'POST /cronograma/rdo/{rdo_id}/apontar falhou (status={r.status_code})'
    return r.get_json()


def _apontamentos(tarefa_id):
    """Apontamentos da tarefa ordenados por data do RDO."""
    with app.app_context():
        return [
            {
                'id': ap.id,
                'rdo_id': ap.rdo_id,
                'data': rdo_data,
                'qty_dia': ap.quantidade_executada_dia,
                'acum': ap.quantidade_acumulada,
                'perc_real': ap.percentual_realizado,
                'perc_plan': ap.percentual_planejado,
            }
            for ap, rdo_data in (
                db.session.query(RDOApontamentoCronograma, RDO.data_relatorio)
                .join(RDO, RDO.id == RDOApontamentoCronograma.rdo_id)
                .filter(RDOApontamentoCronograma.tarefa_cronograma_id == tarefa_id)
                .order_by(RDO.data_relatorio)
                .all()
            )
        ]


def _percentual_concluido(tarefa_id):
    with app.app_context():
        return db.session.get(TarefaCronograma, tarefa_id).percentual_concluido


# ───────────────────────────────────────────────────────────────────────────
# Caminho A — POST /salvar-rdo-flexivel
# ───────────────────────────────────────────────────────────────────────────

def test_path_a_quantitativo_dois_dias(client, ambiente):
    """Dia 1: qty=50 de 200 → acum=50, 25.0%. Dia 2: qty=30 → acum=80, 40.0%.
    Incremento = diferença de acumulados. Planejado congelado em 100.0
    (data_fim no passado). percentual_concluido da tarefa segue o último RDO."""
    tid = _criar_tarefa(ambiente, quantidade_total=200.0, com_plano='passado')

    _post_rdo_flexivel(client, ambiente, D0, {tid: 50})
    aps = _apontamentos(tid)
    assert len(aps) == 1
    assert aps[0]['qty_dia'] == 50.0
    assert aps[0]['acum'] == 50.0
    assert aps[0]['perc_real'] == 25.0
    assert aps[0]['perc_plan'] == 100.0
    assert _percentual_concluido(tid) == 25.0

    _post_rdo_flexivel(client, ambiente, D0 + timedelta(days=1), {tid: 30})
    aps = _apontamentos(tid)
    assert len(aps) == 2
    assert aps[1]['qty_dia'] == 30.0
    assert aps[1]['acum'] == 80.0
    assert aps[1]['perc_real'] == 40.0
    assert aps[1]['perc_plan'] == 100.0
    # Invariante: incremento do dia == diferença dos acumulados
    assert aps[1]['acum'] - aps[0]['acum'] == aps[1]['qty_dia']
    assert _percentual_concluido(tid) == 40.0


def test_path_a_arredondamento_e_teto(client, ambiente):
    """quantidade_total=3: 1/3 → round(33.333..., 2) = 33.33; 2/3 → 66.67;
    acumulado além do total → teto min(100.0, ...)."""
    tid = _criar_tarefa(ambiente, quantidade_total=3.0, com_plano='passado')

    _post_rdo_flexivel(client, ambiente, D0, {tid: 1})
    aps = _apontamentos(tid)
    assert aps[0]['acum'] == 1.0
    assert aps[0]['perc_real'] == 33.33

    _post_rdo_flexivel(client, ambiente, D0 + timedelta(days=1), {tid: 1})
    aps = _apontamentos(tid)
    assert aps[1]['acum'] == 2.0
    assert aps[1]['perc_real'] == 66.67

    _post_rdo_flexivel(client, ambiente, D0 + timedelta(days=2), {tid: 5})
    aps = _apontamentos(tid)
    assert aps[2]['acum'] == 7.0
    assert aps[2]['perc_real'] == 100.0  # teto
    assert _percentual_concluido(tid) == 100.0


def test_path_a_fallback_sem_quantidade_total(client, ambiente):
    """Tarefa sem quantidade_total (fallback percentual): a quantidade
    acumula, mas percentual_realizado congela em 0.0 e percentual_planejado
    em None (sem plano calculável). percentual_concluido segue o
    percentual_realizado do último apontamento → 0.0."""
    tid = _criar_tarefa(ambiente, quantidade_total=None, com_plano=None)

    _post_rdo_flexivel(client, ambiente, D0, {tid: 5})
    aps = _apontamentos(tid)
    assert len(aps) == 1
    assert aps[0]['qty_dia'] == 5.0
    assert aps[0]['acum'] == 5.0
    assert aps[0]['perc_real'] == 0.0
    assert aps[0]['perc_plan'] is None
    assert _percentual_concluido(tid) == 0.0


def test_path_a_qty_zero_ignorada(client, ambiente):
    """qty <= 0 no formulário NÃO cria apontamento (caminho A ignora)."""
    tid = _criar_tarefa(ambiente, quantidade_total=100.0, com_plano='passado')
    _post_rdo_flexivel(client, ambiente, D0, {tid: 0})
    assert _apontamentos(tid) == []


def test_path_a_planejado_zero_tarefa_futura(client, ambiente):
    """Tarefa com data_inicio no futuro: planejado congela em 0.0 (mas o
    apontamento é gravado normalmente)."""
    tid = _criar_tarefa(ambiente, quantidade_total=100.0, com_plano='futuro')
    _post_rdo_flexivel(client, ambiente, D0, {tid: 10})
    aps = _apontamentos(tid)
    assert len(aps) == 1
    assert aps[0]['acum'] == 10.0
    assert aps[0]['perc_real'] == 10.0
    assert aps[0]['perc_plan'] == 0.0


# ───────────────────────────────────────────────────────────────────────────
# Caminho B — POST /cronograma/rdo/<id>/apontar
# ───────────────────────────────────────────────────────────────────────────

def test_path_b_quantitativo_dois_dias(client, ambiente):
    """Mesma fórmula do caminho A: dia 1 qty=50/200 → 25.0%; dia 2 qty=30 →
    acum=80, 40.0%. Resposta JSON congelada."""
    tid = _criar_tarefa(ambiente, quantidade_total=200.0, com_plano='passado')
    rdo1 = _criar_rdo_direto(ambiente, D0)
    rdo2 = _criar_rdo_direto(ambiente, D0 + timedelta(days=1))

    body = _post_apontar(client, rdo1, tid, 50)
    assert body['status'] == 'ok'
    assert body['apontamento']['quantidade_executada_dia'] == 50.0
    assert body['apontamento']['quantidade_acumulada'] == 50.0
    assert body['apontamento']['percentual_realizado'] == 25.0
    assert body['apontamento']['percentual_planejado'] == 100.0
    assert _percentual_concluido(tid) == 25.0

    body = _post_apontar(client, rdo2, tid, 30)
    assert body['apontamento']['quantidade_acumulada'] == 80.0
    assert body['apontamento']['percentual_realizado'] == 40.0
    aps = _apontamentos(tid)
    assert len(aps) == 2
    assert aps[1]['acum'] - aps[0]['acum'] == aps[1]['qty_dia']
    assert _percentual_concluido(tid) == 40.0


def test_path_b_arredondamento_e_teto(client, ambiente):
    """round(..., 2) e teto min(100.0, ...) idênticos ao caminho A."""
    tid = _criar_tarefa(ambiente, quantidade_total=3.0, com_plano='passado')
    rdo1 = _criar_rdo_direto(ambiente, D0)
    rdo2 = _criar_rdo_direto(ambiente, D0 + timedelta(days=1))

    body = _post_apontar(client, rdo1, tid, 1)
    assert body['apontamento']['percentual_realizado'] == 33.33

    body = _post_apontar(client, rdo2, tid, 5)
    assert body['apontamento']['quantidade_acumulada'] == 6.0
    assert body['apontamento']['percentual_realizado'] == 100.0  # teto
    assert _percentual_concluido(tid) == 100.0


def test_path_b_fallback_sem_quantidade_total(client, ambiente):
    """Fallback percentual no caminho B: percentual_realizado 0.0,
    planejado None, quantidade acumula."""
    tid = _criar_tarefa(ambiente, quantidade_total=None, com_plano=None)
    rdo1 = _criar_rdo_direto(ambiente, D0)

    body = _post_apontar(client, rdo1, tid, 5)
    assert body['apontamento']['quantidade_acumulada'] == 5.0
    assert body['apontamento']['percentual_realizado'] == 0.0
    assert body['apontamento']['percentual_planejado'] is None
    assert _percentual_concluido(tid) == 0.0


def test_path_b_upsert_mesmo_rdo(client, ambiente):
    """Reapontar o MESMO RDO+tarefa atualiza a linha existente (UPSERT do
    caminho B — diferente do caminho A, que sempre cria)."""
    tid = _criar_tarefa(ambiente, quantidade_total=100.0, com_plano='passado')
    rdo1 = _criar_rdo_direto(ambiente, D0)

    b1 = _post_apontar(client, rdo1, tid, 20)
    b2 = _post_apontar(client, rdo1, tid, 35)
    assert b2['apontamento']['id'] == b1['apontamento']['id']
    aps = _apontamentos(tid)
    assert len(aps) == 1  # nenhuma duplicata
    assert aps[0]['qty_dia'] == 35.0
    assert aps[0]['acum'] == 35.0  # acum_anterior (0) + qty nova
    assert aps[0]['perc_real'] == 35.0


def test_path_b_qty_zero_upsert(client, ambiente):
    """Caminho B ACEITA qty=0 (zera o dia) — diferente do caminho A."""
    tid = _criar_tarefa(ambiente, quantidade_total=100.0, com_plano='passado')
    rdo1 = _criar_rdo_direto(ambiente, D0)

    _post_apontar(client, rdo1, tid, 10)
    body = _post_apontar(client, rdo1, tid, 0)
    assert body['apontamento']['quantidade_executada_dia'] == 0.0
    assert body['apontamento']['quantidade_acumulada'] == 0.0
    assert body['apontamento']['percentual_realizado'] == 0.0
    aps = _apontamentos(tid)
    assert len(aps) == 1
