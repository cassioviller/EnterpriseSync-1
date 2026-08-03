"""Fase 1 Step A — migrações 222/223 (tarefa_vinculo + backfill do legado).

O que importa aqui (§Step E item 4 do plano):
  * idempotência: 222 e 223 rodadas DUAS vezes não falham nem duplicam;
  * o backfill 223 materializa `predecessora_id` intra-obra como vínculo
    TI lag 0, e PULA auto-referência e predecessora cruzando obra/tenant
    (dado sujo real — ver tabela de riscos do plano);
  * schema: colunas novas (is_critica, folga_dias, cronograma_editor_v2)
    existem com os defaults corretos.

Nota: `db.create_all()` roda antes das migrações no boot, então a tabela
pode já existir quando a 222 roda — os testes cobrem exatamente esse
cenário (DDL todo IF NOT EXISTS).
"""
import os
import sys
import uuid
from datetime import date, datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash

from app import app, db
from models import Cliente, Obra, TarefaCronograma, TarefaVinculo, TipoUsuario, Usuario
from migrations import (
    _migration_222_tarefa_vinculo_e_colunas,
    _migration_223_backfill_vinculos_de_predecessora,
)

pytestmark = pytest.mark.integration

SENHA = 'Senha@2026'


def _suf() -> str:
    return f'{datetime.utcnow().strftime("%H%M%S%f")}_{uuid.uuid4().hex[:6]}'


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-migr-tarefa-vinculo'
    with app.app_context():
        yield


def _ambiente(n_obras=1):
    """admin V2 + cliente + n obras novos e isolados por sufixo."""
    suf = _suf()
    admin = Usuario(
        username=f'tv_{suf}',
        email=f'tv_{suf}@test.local',
        nome=f'Admin Vinculo {suf}',
        password_hash=generate_password_hash(SENHA),
        tipo_usuario=TipoUsuario.ADMIN,
        ativo=True,
        versao_sistema='v2',
    )
    db.session.add(admin)
    db.session.flush()
    cliente = Cliente(
        admin_id=admin.id,
        nome=f'Cliente {suf}',
        email=f'cli_{suf}@test.local',
        telefone='11988887777',
    )
    db.session.add(cliente)
    db.session.flush()
    obras = []
    for i in range(n_obras):
        obra = Obra(
            nome=f'Obra Vinculo {suf} #{i}',
            codigo=f'TV{i}-{suf[:11]}',
            admin_id=admin.id,
            cliente_id=cliente.id,
            status='Em andamento',
            data_inicio=date(2026, 7, 1),
        )
        db.session.add(obra)
        obras.append(obra)
    db.session.commit()
    return admin, obras


def _tarefa(obra, admin, nome, ordem=0, **kw):
    t = TarefaCronograma(
        obra_id=obra.id,
        admin_id=admin.id,
        nome_tarefa=nome,
        ordem=ordem,
        duracao_dias=kw.pop('duracao_dias', 5),
        data_inicio=kw.pop('data_inicio', date(2026, 7, 1)),
        data_fim=kw.pop('data_fim', date(2026, 7, 7)),
        is_cliente=False,
        **kw,
    )
    db.session.add(t)
    db.session.commit()
    return t


def _vinculos_do_admin(admin_id):
    return (TarefaVinculo.query
            .filter_by(admin_id=admin_id)
            .order_by(TarefaVinculo.predecessora_id, TarefaVinculo.sucessora_id)
            .all())


# ---------------------------------------------------------------------------
# Migração 222 — DDL
# ---------------------------------------------------------------------------

def test_migration_222_e_idempotente():
    """create_all já criou a tabela no boot; a 222 precisa ser no-op limpa
    e aguentar rodar de novo."""
    _migration_222_tarefa_vinculo_e_colunas()
    _migration_222_tarefa_vinculo_e_colunas()


def test_migration_222_tabela_e_colunas_existem():
    from sqlalchemy import text as sa_text
    _migration_222_tarefa_vinculo_e_colunas()
    with db.engine.connect() as conn:
        assert conn.execute(sa_text("""
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'tarefa_vinculo'
        """)).fetchone() is not None, 'tabela tarefa_vinculo não existe'

        linha = conn.execute(sa_text("""
            SELECT is_nullable, column_default FROM information_schema.columns
            WHERE table_name = 'tarefa_cronograma' AND column_name = 'is_critica'
        """)).fetchone()
        assert linha is not None, 'coluna is_critica não existe'
        assert linha[0] == 'NO'
        assert 'false' in str(linha[1]).lower()

        assert conn.execute(sa_text("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'tarefa_cronograma' AND column_name = 'folga_dias'
        """)).fetchone() is not None, 'coluna folga_dias não existe'

        # O default desta coluna era FALSE quando a 222 a criou (rollout por
        # tenant). A migração 277 (03/08/2026) ligou o editor v2 em todo o
        # parque e virou o default para TRUE — aqui só resta o contrato que
        # a 222 garante e a 277 não mexeu: a coluna existe, NOT NULL e com
        # default. O valor do default é asserido em
        # tests/test_migrations_editor_v2_parque.py.
        linha = conn.execute(sa_text("""
            SELECT is_nullable, column_default FROM information_schema.columns
            WHERE table_name = 'configuracao_empresa'
              AND column_name = 'cronograma_editor_v2'
        """)).fetchone()
        assert linha is not None, 'coluna cronograma_editor_v2 não existe'
        assert linha[0] == 'NO'
        assert str(linha[1]).lower() in ('false', 'true')


def test_constraints_da_tabela_valem():
    """Os CHECKs/UNIQUE nomeados existem de fato (via create_all OU 222)."""
    admin, (obra,) = _ambiente()
    a = _tarefa(obra, admin, 'A')
    b = _tarefa(obra, admin, 'B', ordem=1)

    # auto-vínculo barrado pelo CHECK
    db.session.add(TarefaVinculo(admin_id=admin.id, obra_id=obra.id,
                                 predecessora_id=a.id, sucessora_id=a.id))
    with pytest.raises(Exception):
        db.session.commit()
    db.session.rollback()

    # tipo fora do vocabulário barrado pelo CHECK
    db.session.add(TarefaVinculo(admin_id=admin.id, obra_id=obra.id,
                                 predecessora_id=a.id, sucessora_id=b.id,
                                 tipo='XX'))
    with pytest.raises(Exception):
        db.session.commit()
    db.session.rollback()

    # par duplicado barrado pelo UNIQUE
    db.session.add(TarefaVinculo(admin_id=admin.id, obra_id=obra.id,
                                 predecessora_id=a.id, sucessora_id=b.id))
    db.session.commit()
    db.session.add(TarefaVinculo(admin_id=admin.id, obra_id=obra.id,
                                 predecessora_id=a.id, sucessora_id=b.id,
                                 tipo='II'))
    with pytest.raises(Exception):
        db.session.commit()
    db.session.rollback()


# ---------------------------------------------------------------------------
# Migração 223 — backfill
# ---------------------------------------------------------------------------

def test_backfill_materializa_predecessora_intra_obra():
    admin, (obra,) = _ambiente()
    a = _tarefa(obra, admin, 'Fundação')
    b = _tarefa(obra, admin, 'Alvenaria', ordem=1, predecessora_id=a.id)
    c = _tarefa(obra, admin, 'Reboco', ordem=2, predecessora_id=b.id)

    _migration_223_backfill_vinculos_de_predecessora()

    vinculos = _vinculos_do_admin(admin.id)
    pares = {(v.predecessora_id, v.sucessora_id) for v in vinculos}
    assert pares == {(a.id, b.id), (b.id, c.id)}
    for v in vinculos:
        assert v.tipo == 'TI'
        assert v.lag_dias == 0
        assert v.obra_id == obra.id

    # legado congelado, não apagado
    db.session.refresh(b)
    assert b.predecessora_id == a.id


def test_backfill_e_idempotente_rodando_duas_vezes():
    admin, (obra,) = _ambiente()
    a = _tarefa(obra, admin, 'A')
    _tarefa(obra, admin, 'B', ordem=1, predecessora_id=a.id)

    _migration_223_backfill_vinculos_de_predecessora()
    _migration_223_backfill_vinculos_de_predecessora()

    assert len(_vinculos_do_admin(admin.id)) == 1


def test_backfill_ignora_predecessora_de_outra_obra():
    """Dado sujo real: predecessora cruzando obra — pulada, não migrada."""
    admin, (obra1, obra2) = _ambiente(n_obras=2)
    a = _tarefa(obra1, admin, 'A na obra 1')
    _tarefa(obra2, admin, 'B na obra 2', predecessora_id=a.id)

    _migration_223_backfill_vinculos_de_predecessora()

    assert _vinculos_do_admin(admin.id) == []


def test_backfill_ignora_predecessora_de_outro_tenant():
    admin1, (obra1,) = _ambiente()
    admin2, (obra2,) = _ambiente()
    a = _tarefa(obra1, admin1, 'A do tenant 1')
    # obra do tenant 2 apontando para tarefa do tenant 1 (sujo): mesmo se a
    # obra coincidisse, o filtro de admin_id barra.
    t2 = _tarefa(obra2, admin2, 'B do tenant 2')
    t2.predecessora_id = a.id
    db.session.commit()

    _migration_223_backfill_vinculos_de_predecessora()

    assert _vinculos_do_admin(admin1.id) == []
    assert _vinculos_do_admin(admin2.id) == []


def test_backfill_ignora_auto_referencia():
    admin, (obra,) = _ambiente()
    a = _tarefa(obra, admin, 'A')
    a.predecessora_id = a.id
    db.session.commit()

    _migration_223_backfill_vinculos_de_predecessora()

    assert _vinculos_do_admin(admin.id) == []


def test_backfill_nao_duplica_vinculo_ja_existente():
    """Par já materializado (ex.: dual-write futuro) não vira duplicata."""
    admin, (obra,) = _ambiente()
    a = _tarefa(obra, admin, 'A')
    b = _tarefa(obra, admin, 'B', ordem=1, predecessora_id=a.id)
    db.session.add(TarefaVinculo(admin_id=admin.id, obra_id=obra.id,
                                 predecessora_id=a.id, sucessora_id=b.id,
                                 tipo='TI', lag_dias=0))
    db.session.commit()

    _migration_223_backfill_vinculos_de_predecessora()

    assert len(_vinculos_do_admin(admin.id)) == 1
