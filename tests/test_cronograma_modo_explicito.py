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
