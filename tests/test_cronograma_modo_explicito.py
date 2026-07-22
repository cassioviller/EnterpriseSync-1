"""Modo de apontamento como ESCOLHA da tarefa, não como dedução.

Até 2026-07-21 `services/cronograma_apontamento_service.py:73-82` decidia
sozinho: 'quantidade' quando a tarefa tinha `quantidade_total > 0` E
`unidade_medida` preenchida, 'percentual' caso contrário. O usuário não
escolhia nada — preencher "Quantidade" no modal do Gantt mudava o modo do
RDO como efeito colateral.

Estes testes travam a coluna explícita e, principalmente, travam que a
DEDUÇÃO ANTIGA continua valendo quando a coluna é NULL. Nada pode mudar de
comportamento para as tarefas que já existem.
"""
import os
import sys
import uuid
from datetime import date, timedelta

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import Cliente, Obra, TarefaCronograma, TipoUsuario, Usuario

pytestmark = pytest.mark.integration

D0 = date(2026, 6, 15)


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-modo-explicito'
    yield


def _suf() -> str:
    return uuid.uuid4().hex[:10]


@pytest.fixture()
def ctx():
    """Admin V2 + cliente + obra. Obra.cliente_id é NOT NULL."""
    with app.app_context():
        suf = _suf()
        admin = Usuario(
            username=f'modo_{suf}', email=f'modo_{suf}@test.local',
            nome='Modo Explicito',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
        )
        db.session.add(admin)
        db.session.flush()
        cliente = Cliente(admin_id=admin.id, nome=f'Cliente Modo {suf}',
                          email=f'cli_modo_{suf}@test.local',
                          telefone='11977776666')
        db.session.add(cliente)
        db.session.flush()
        obra = Obra(
            nome=f'Obra Modo {suf}', codigo=f'MD-{suf[:8].upper()}',
            admin_id=admin.id, cliente_id=cliente.id,
            status='Em andamento', data_inicio=D0 - timedelta(days=60),
        )
        db.session.add(obra)
        db.session.commit()
        yield {'admin_id': admin.id, 'obra_id': obra.id}


def _tarefa(ctx, **kw):
    t = TarefaCronograma(
        obra_id=ctx['obra_id'], admin_id=ctx['admin_id'],
        nome_tarefa=f'Tarefa Modo {_suf()}', ordem=1, responsavel='empresa',
        duracao_dias=kw.pop('duracao_dias', 10),
        data_inicio=kw.pop('data_inicio', D0 - timedelta(days=30)),
        data_fim=kw.pop('data_fim', D0 - timedelta(days=20)),
        **kw,
    )
    db.session.add(t)
    db.session.commit()
    return t


# ---------------------------------------------------------------------------
# Task 2 — a coluna
# ---------------------------------------------------------------------------

def test_tarefa_tem_coluna_modo_apontamento():
    with app.app_context():
        assert hasattr(TarefaCronograma, 'modo_apontamento'), (
            'TarefaCronograma.modo_apontamento não existe — o modo continua '
            'sendo deduzido de quantidade_total + unidade_medida')


def test_modo_apontamento_nasce_nulo(ctx):
    """NULL = 'ninguém escolheu' = dedução antiga. É o default de propósito."""
    with app.app_context():
        t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')
        assert t.modo_apontamento is None


def test_modo_apontamento_persiste(ctx):
    with app.app_context():
        t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                    modo_apontamento='percentual')
        tid = t.id
        db.session.expire_all()
        assert db.session.get(TarefaCronograma, tid).modo_apontamento == 'percentual'


def test_modo_apontamento_recusa_valor_fora_do_dominio(ctx):
    """CHECK no banco: só 'quantidade' ou 'percentual'."""
    from sqlalchemy.exc import DataError, IntegrityError

    with app.app_context():
        with pytest.raises((IntegrityError, DataError)):
            _tarefa(ctx, quantidade_total=1.0, modo_apontamento='qualquer')
        db.session.rollback()


# ---------------------------------------------------------------------------
# Task 3 — backfill congela o modo deduzido HOJE
# ---------------------------------------------------------------------------

def _backfill():
    from migrations import migration_221_backfill_modo_apontamento
    migration_221_backfill_modo_apontamento()


@pytest.mark.parametrize('kwargs,esperado,porque', [
    ({'quantidade_total': 100.0, 'unidade_medida': 'm2'}, 'quantidade',
     'quantidade + unidade => quantitativa (regra antiga)'),
    ({'quantidade_total': 100.0, 'unidade_medida': None}, 'percentual',
     'quantidade SEM unidade => percentual (regra antiga)'),
    ({'quantidade_total': 100.0, 'unidade_medida': '   '}, 'percentual',
     'unidade só com espaços conta como vazia (regra antiga usa .strip())'),
    ({'quantidade_total': 0.0, 'unidade_medida': 'm2'}, 'percentual',
     'quantidade zero => percentual (regra antiga)'),
    ({'quantidade_total': None, 'unidade_medida': None}, 'percentual',
     'sem quantidade => percentual'),
])
def test_backfill_grava_exatamente_o_modo_deduzido_hoje(ctx, kwargs, esperado,
                                                        porque):
    from services.cronograma_apontamento_service import _modo_deduzido

    with app.app_context():
        t = _tarefa(ctx, **kwargs)
        assert _modo_deduzido(t) == esperado, f'premissa quebrada: {porque}'
        tid = t.id

        _backfill()
        db.session.expire_all()
        assert db.session.get(TarefaCronograma, tid).modo_apontamento == esperado, (
            f'backfill divergiu da dedução: {porque}')


def test_backfill_marco_sempre_percentual(ctx):
    """Mesmo com quantidade + unidade, marco é percentual binário."""
    with app.app_context():
        m = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                    is_marco=True, duracao_dias=0)
        mid = m.id
        _backfill()
        db.session.expire_all()
        assert db.session.get(TarefaCronograma, mid).modo_apontamento == 'percentual'


def test_backfill_nao_sobrescreve_escolha_existente(ctx):
    """Idempotência: quem já escolheu não é reclassificado."""
    with app.app_context():
        t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                    modo_apontamento='percentual')
        tid = t.id
        _backfill()
        db.session.expire_all()
        assert db.session.get(TarefaCronograma, tid).modo_apontamento == 'percentual'


def test_backfill_e_idempotente(ctx):
    with app.app_context():
        t = _tarefa(ctx, quantidade_total=50.0, unidade_medida='un')
        tid = t.id
        _backfill()
        db.session.expire_all()
        primeiro = db.session.get(TarefaCronograma, tid).modo_apontamento
        _backfill()
        db.session.expire_all()
        assert db.session.get(TarefaCronograma, tid).modo_apontamento == primeiro


# ---------------------------------------------------------------------------
# Task 4 — resolução do modo
# ---------------------------------------------------------------------------

def test_coluna_vence_a_deducao(ctx):
    """O ponto do plano: a escolha do usuário manda."""
    from services.cronograma_apontamento_service import modo_da_tarefa

    with app.app_context():
        # Tarefa que a dedução chamaria de 'quantidade', marcada como percentual.
        t = _tarefa(ctx, quantidade_total=250.0, unidade_medida='m2',
                    modo_apontamento='percentual')
        assert modo_da_tarefa(t) == 'percentual'

        # E o inverso: sem quantidade nenhuma, mas marcada como quantidade.
        t2 = _tarefa(ctx, quantidade_total=None, unidade_medida=None,
                     modo_apontamento='quantidade')
        assert modo_da_tarefa(t2) == 'quantidade'


def test_coluna_nula_cai_na_deducao_antiga(ctx):
    from services.cronograma_apontamento_service import modo_da_tarefa

    with app.app_context():
        assert modo_da_tarefa(
            _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')) == 'quantidade'
        assert modo_da_tarefa(
            _tarefa(ctx, quantidade_total=100.0, unidade_medida=None)) == 'percentual'
        assert modo_da_tarefa(
            _tarefa(ctx, quantidade_total=None)) == 'percentual'


def test_marco_ignora_a_coluna(ctx):
    """Marco é binário; nem o usuário pode torná-lo quantitativo."""
    from services.cronograma_apontamento_service import modo_da_tarefa

    with app.app_context():
        m = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                    is_marco=True, duracao_dias=0, modo_apontamento='quantidade')
        assert modo_da_tarefa(m) == 'percentual'


def test_valor_invalido_na_coluna_cai_na_deducao(ctx):
    """Falha tolerante: lixo na coluna não pode derrubar o RDO.

    O CHECK do banco impede gravar lixo, mas o objeto em memória pode ter
    qualquer coisa antes do flush — e `modo_da_tarefa` é chamado dentro do
    laço de montagem de `tarefas_rdo` (cronograma_views.py:917), que serve
    a tela inteira.
    """
    from services.cronograma_apontamento_service import modo_da_tarefa

    with app.app_context():
        t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')
        # no_autoflush é parte do cenário, não conveniência: com o CHECK da
        # migration 220 no banco, o refresh de qualquer atributo expirado
        # (is_marco, após o commit da fixture) dispararia autoflush do
        # 'lixo' e morreria em CheckViolation ANTES de exercitar a
        # resolução — exatamente o tipo de morte que este teste exige que
        # modo_da_tarefa não tenha.
        with db.session.no_autoflush:
            t.modo_apontamento = 'lixo'
            assert modo_da_tarefa(t) == 'quantidade'
        db.session.rollback()


def test_modo_da_tarefa_aceita_objeto_sem_o_atributo(ctx):
    """Robustez: o serviço é chamado com objetos leves em alguns caminhos."""
    from services.cronograma_apontamento_service import modo_da_tarefa

    class TarefaFalsa:
        is_marco = False
        quantidade_total = 10.0
        unidade_medida = 'm'

    assert modo_da_tarefa(TarefaFalsa()) == 'quantidade'


def test_modos_validos_e_o_contrato_publico():
    from services.cronograma_apontamento_service import MODOS_APONTAMENTO

    assert MODOS_APONTAMENTO == ('quantidade', 'percentual')


# ---------------------------------------------------------------------------
# Task 5 — recomputo usa o mesmo classificador da UI
# ---------------------------------------------------------------------------

def _rdo(ctx, data_rdo):
    from models import RDO
    r = RDO(numero_rdo=f'MD-{_suf()[:12]}', obra_id=ctx['obra_id'],
            admin_id=ctx['admin_id'], data_relatorio=data_rdo,
            local='Campo', status='Finalizado')
    db.session.add(r)
    db.session.commit()
    return r


def test_recomputo_classifica_linha_antiga_pelo_modo_da_tarefa(ctx):
    """Linha pré-M02 (tipo_apontamento NULL) numa tarefa marcada percentual.

    Antes desta task o fallback de `recomputar_cadeia` olhava só
    `quantidade_total > 0` e chamaria a linha de 'quantitativo', divergindo
    do que a UI mostra (`modo_da_tarefa`).
    """
    from models import RDOApontamentoCronograma
    from services.cronograma_apontamento_service import recomputar_cadeia

    with app.app_context():
        t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                    modo_apontamento='percentual')
        r = _rdo(ctx, D0)
        ap = RDOApontamentoCronograma(
            rdo_id=r.id, tarefa_cronograma_id=t.id, admin_id=ctx['admin_id'],
            quantidade_executada_dia=0.0, quantidade_acumulada=0.0,
            percentual_realizado=42.0,
            tipo_apontamento=None,          # linha pré-M02
            percentual_acumulado=42.0,
        )
        db.session.add(ap)
        db.session.commit()

        recomputar_cadeia(t.id, D0, ctx['admin_id'])
        db.session.flush()

        assert ap.percentual_realizado == 42.0, (
            'a linha foi tratada como quantitativa: 0/100 zerou o percentual')
        assert ap.percentual_acumulado == 42.0


def test_recomputo_quantitativo_continua_igual(ctx):
    """Guarda de não-regressão do caminho quantitativo."""
    from services.cronograma_apontamento_service import (recomputar_cadeia,
                                                         registrar_apontamento)

    with app.app_context():
        t = _tarefa(ctx, quantidade_total=200.0, unidade_medida='m2',
                    modo_apontamento='quantidade')
        r1 = _rdo(ctx, D0 - timedelta(days=2))
        r2 = _rdo(ctx, D0)
        registrar_apontamento(r1, t, quantidade_dia=50.0,
                              admin_id=ctx['admin_id'])
        ap2 = registrar_apontamento(r2, t, quantidade_dia=30.0,
                                    admin_id=ctx['admin_id'])
        db.session.commit()

        recomputar_cadeia(t.id, D0 - timedelta(days=2), ctx['admin_id'])
        db.session.flush()
        assert ap2.quantidade_acumulada == 80.0
        assert ap2.percentual_realizado == 40.0


# ---------------------------------------------------------------------------
# Task 6 — o modo escolhido é respeitado na escrita
# ---------------------------------------------------------------------------

def test_quantidade_em_tarefa_marcada_percentual_e_recusada(ctx):
    from services.cronograma_apontamento_service import (ModoIncompativel,
                                                         registrar_apontamento)

    with app.app_context():
        t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                    modo_apontamento='percentual')
        with pytest.raises(ModoIncompativel):
            registrar_apontamento(_rdo(ctx, D0), t, quantidade_dia=10.0,
                                  admin_id=ctx['admin_id'])
        db.session.rollback()


def test_percentual_em_tarefa_marcada_quantidade_e_recusado(ctx):
    from services.cronograma_apontamento_service import (ModoIncompativel,
                                                         registrar_apontamento)

    with app.app_context():
        t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                    modo_apontamento='quantidade')
        with pytest.raises(ModoIncompativel):
            registrar_apontamento(_rdo(ctx, D0), t, percentual_acumulado=30.0,
                                  admin_id=ctx['admin_id'])
        db.session.rollback()


def test_sem_escolha_explicita_nada_e_recusado(ctx):
    """Decisão D3: coluna NULL => tolerância legada, os dois modos passam.

    É o que mantém verdes as fixtures que criam tarefa com
    quantidade_total sem unidade e apontam com quantidade_dia
    (tests/test_cronograma_apontamento_service.py:101).
    """
    from services.cronograma_apontamento_service import registrar_apontamento

    with app.app_context():
        t = _tarefa(ctx, quantidade_total=100.0, unidade_medida=None)
        assert t.modo_apontamento is None
        ap = registrar_apontamento(_rdo(ctx, D0), t, quantidade_dia=10.0,
                                   admin_id=ctx['admin_id'])
        db.session.commit()
        assert ap.tipo_apontamento == 'quantitativo'


def test_marco_continua_aceitando_percentual(ctx):
    """Marco resolve para 'percentual' antes de olhar a coluna."""
    from services.cronograma_apontamento_service import registrar_apontamento

    with app.app_context():
        m = _tarefa(ctx, quantidade_total=None, is_marco=True, duracao_dias=0,
                    modo_apontamento='percentual')
        ap = registrar_apontamento(_rdo(ctx, D0), m, percentual_acumulado=100.0,
                                   admin_id=ctx['admin_id'])
        db.session.commit()
        assert ap.percentual_realizado == 100.0


def test_modo_incompativel_e_valueerror(ctx):
    """Contrato do módulo: os laços legados de views/rdo.py protegem com
    `except (ValueError, TypeError)`. A exceção nova precisa cair ali, senão
    um item divergente derruba o RDO inteiro (views/rdo.py:4635)."""
    from services.cronograma_apontamento_service import ModoIncompativel

    assert issubclass(ModoIncompativel, ValueError)


def test_apontar_producao_devolve_422_no_modo_errado(ctx):
    """Caminho HTTP: cronograma_views.py:1203 mapeia ApontamentoInvalido→422."""
    with app.app_context():
        t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                    modo_apontamento='percentual')
        r = _rdo(ctx, D0)
        tid, rid, aid = t.id, r.id, ctx['admin_id']

    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(aid)
        sess['_fresh'] = True

    resp = c.post(f'/cronograma/rdo/{rid}/apontar',
                  json={'tarefa_cronograma_id': tid,
                        'quantidade_executada_dia': 5.0})
    assert resp.status_code == 422, resp.get_data(as_text=True)[:400]


# ---------------------------------------------------------------------------
# Task 7 — contrato HTTP
# ---------------------------------------------------------------------------

def _cliente(admin_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(admin_id)
        sess['_fresh'] = True
    return c


def test_criar_tarefa_aceita_modo_apontamento(ctx):
    oid, aid = ctx['obra_id'], ctx['admin_id']
    c = _cliente(aid)
    resp = c.post(f'/cronograma/obra/{oid}/tarefa',
                  json={'nome_tarefa': 'Montagem de painéis',
                        'modo_apontamento': 'percentual'})
    assert resp.status_code == 201, resp.get_data(as_text=True)[:400]
    corpo = resp.get_json()['tarefa']
    assert corpo['modo_apontamento'] == 'percentual'

    with app.app_context():
        t = db.session.get(TarefaCronograma, corpo['id'])
        assert t.modo_apontamento == 'percentual'


def test_criar_tarefa_sem_modo_deixa_nulo(ctx):
    """Sem escolha explícita, a dedução legada continua no comando."""
    oid, aid = ctx['obra_id'], ctx['admin_id']
    c = _cliente(aid)
    resp = c.post(f'/cronograma/obra/{oid}/tarefa',
                  json={'nome_tarefa': 'Tarefa sem modo',
                        'quantidade_total': 80, 'unidade_medida': 'm2'})
    assert resp.status_code == 201
    corpo = resp.get_json()['tarefa']
    with app.app_context():
        t = db.session.get(TarefaCronograma, corpo['id'])
        assert t.modo_apontamento is None


def test_criar_tarefa_recusa_modo_invalido(ctx):
    oid, aid = ctx['obra_id'], ctx['admin_id']
    c = _cliente(aid)
    resp = c.post(f'/cronograma/obra/{oid}/tarefa',
                  json={'nome_tarefa': 'Tarefa ruim',
                        'modo_apontamento': 'banana'})
    assert resp.status_code == 400
    assert 'modo_apontamento' in resp.get_json()['msg']


def test_atualizar_tarefa_muda_o_modo(ctx):
    with app.app_context():
        t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')
        oid, tid, aid = ctx['obra_id'], t.id, ctx['admin_id']
    c = _cliente(aid)
    resp = c.put(f'/cronograma/obra/{oid}/tarefa/{tid}',
                 json={'modo_apontamento': 'percentual'})
    assert resp.status_code == 200, resp.get_data(as_text=True)[:400]

    with app.app_context():
        assert db.session.get(
            TarefaCronograma, tid).modo_apontamento == 'percentual'


def test_atualizar_tarefa_limpa_o_modo_com_string_vazia(ctx):
    """Voltar para "automático" precisa ser possível pela UI."""
    with app.app_context():
        t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                    modo_apontamento='percentual')
        oid, tid, aid = ctx['obra_id'], t.id, ctx['admin_id']
    c = _cliente(aid)
    resp = c.put(f'/cronograma/obra/{oid}/tarefa/{tid}',
                 json={'modo_apontamento': ''})
    assert resp.status_code == 200

    with app.app_context():
        assert db.session.get(TarefaCronograma, tid).modo_apontamento is None


def test_atualizar_tarefa_recusa_modo_quantidade_em_marco(ctx):
    """Decisão D6: marco é sempre percentual."""
    with app.app_context():
        m = _tarefa(ctx, is_marco=True, duracao_dias=0)
        oid, mid, aid = ctx['obra_id'], m.id, ctx['admin_id']
    c = _cliente(aid)
    resp = c.put(f'/cronograma/obra/{oid}/tarefa/{mid}',
                 json={'modo_apontamento': 'quantidade'})
    assert resp.status_code == 400
    assert 'marco' in resp.get_json()['msg'].lower()


def test_tarefas_rdo_reflete_a_escolha(ctx):
    """`tipo_modo` é o contrato que templates/rdo/novo.html:1118 consome."""
    with app.app_context():
        t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                    modo_apontamento='percentual')
        oid, tid, aid = ctx['obra_id'], t.id, ctx['admin_id']
    c = _cliente(aid)
    resp = c.get(f'/cronograma/obra/{oid}/tarefas-rdo?data={D0.isoformat()}')
    assert resp.status_code == 200
    itens = {i['id']: i for i in resp.get_json()['tarefas']}
    assert itens[tid]['tipo_modo'] == 'percentual'
    assert itens[tid]['modo_apontamento'] == 'percentual'
    assert itens[tid]['saldo'] is None, (
        'saldo só faz sentido no modo quantidade')
