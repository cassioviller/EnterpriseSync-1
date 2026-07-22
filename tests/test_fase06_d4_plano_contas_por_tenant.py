"""Fase 0.6 / D4 — o plano de contas só era semeado para o primeiro tenant.

`PlanoContas.codigo` era PK **global** (`models.py:2513`), apesar de a tabela
ter `admin_id`. O seed usava `ON CONFLICT (codigo) DO NOTHING`
(`contabilidade_utils.seed_plano_contas_if_needed`): do 2º tenant em diante
ele inseria **zero** contas — e mesmo assim marcava o tenant como semeado, no
cache `_v2_seeded_admins` e pela contagem `count == 0`.

Medido no banco de desenvolvimento em 2026-07-21:

  315 tenants com lançamentos contábeis
    2 tenants com plano de contas (admin 111 e 832)
  980 de 1.204 partidas apontam para um par (admin_id, conta) que não existe

Ou seja: 313 empresas lançavam contabilidade **no plano de contas de outra
empresa**. A FK global permitia, porque só exigia que o código existisse em
algum lugar. Renomear uma conta do tenant 832 mudaria o nome da conta na
contabilidade de todos os outros.

A correção troca a PK de `(codigo)` para `(admin_id, codigo)` e reconstrói as
seis FKs dependentes como compostas. Antes de trocar, a migração 218 faz o
backfill: para todo par (admin_id, conta) referenciado por um lançamento e
inexistente, copia a definição da conta — com toda a cadeia de pais — para
aquele tenant. Sem isso a troca de PK falharia nas 980 linhas.
"""
import os
import sys
import uuid

import pytest
from sqlalchemy import text as sa_text
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase06-d4'
    yield


def _admin():
    s = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'd4_{s}', email=f'd4_{s}@test.local', nome=f'Admin {s}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u.id


def _contas_de(admin_id):
    return db.session.execute(
        sa_text('SELECT codigo FROM plano_contas WHERE admin_id = :a'),
        {'a': admin_id},
    ).scalars().all()


# ---------------------------------------------------------------------------
# O schema: a conta pertence ao tenant
# ---------------------------------------------------------------------------

def test_pk_do_plano_de_contas_inclui_o_tenant():
    """A PK era só `codigo`. Duas empresas não podiam ter a conta '1.1.01.001'."""
    with app.app_context():
        cols = db.session.execute(sa_text("""
            SELECT a.attname
              FROM pg_index i
              JOIN pg_attribute a
                ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
             WHERE i.indrelid = 'plano_contas'::regclass AND i.indisprimary
        """)).scalars().all()

        assert set(cols) == {'admin_id', 'codigo'}, (
            f'PK do plano_contas é {sorted(cols)} — deveria ser '
            f"['admin_id', 'codigo']"
        )


def test_fks_para_plano_contas_sao_compostas():
    """As seis dependentes tinham FK só por `codigo`.

    Com FK simples, a partida do tenant A podia apontar para a conta do
    tenant B — e 980 das 1.204 partidas apontavam.
    """
    with app.app_context():
        fks = db.session.execute(sa_text("""
            SELECT conrelid::regclass::text, pg_get_constraintdef(oid)
              FROM pg_constraint
             WHERE confrelid = 'plano_contas'::regclass AND contype = 'f'
        """)).all()

        assert fks, 'nenhuma FK para plano_contas — o vínculo sumiu'
        simples = [f'{t}: {d}' for t, d in fks if 'admin_id' not in d]
        assert not simples, (
            'FK sem o tenant no vínculo:\n  ' + '\n  '.join(simples)
        )


# ---------------------------------------------------------------------------
# O comportamento: cada tenant ganha o seu plano
# ---------------------------------------------------------------------------

def test_segundo_tenant_tambem_recebe_o_plano_de_contas():
    """O coração do D4.

    Antes: o 1º tenant a chamar o seed levava todas as contas; do 2º em
    diante o `ON CONFLICT (codigo) DO NOTHING` inseria zero — e o tenant era
    marcado como semeado assim mesmo.
    """
    from contabilidade_utils import _V2_CONTAS_SEED, seed_plano_contas_if_needed

    with app.app_context():
        primeiro, segundo = _admin(), _admin()

        seed_plano_contas_if_needed(primeiro)
        db.session.commit()
        seed_plano_contas_if_needed(segundo)
        db.session.commit()

        esperado = {c[0] for c in _V2_CONTAS_SEED}
        assert set(_contas_de(primeiro)) == esperado
        assert set(_contas_de(segundo)) == esperado, (
            'o 2º tenant ficou com plano de contas vazio — é o D4'
        )


def test_contas_dos_tenants_sao_independentes():
    """Renomear a conta de um tenant não pode mexer na do outro."""
    from contabilidade_utils import seed_plano_contas_if_needed

    with app.app_context():
        a, b = _admin(), _admin()
        seed_plano_contas_if_needed(a)
        seed_plano_contas_if_needed(b)
        db.session.commit()

        db.session.execute(sa_text("""
            UPDATE plano_contas SET nome = 'Renomeada por A'
             WHERE admin_id = :a AND codigo = '6.1.01.002'
        """), {'a': a})
        db.session.commit()

        nome_b = db.session.execute(sa_text("""
            SELECT nome FROM plano_contas
             WHERE admin_id = :b AND codigo = '6.1.01.002'
        """), {'b': b}).scalar()
        assert nome_b == 'Despesa com Alimentação', (
            f'o tenant B viu a renomeação do tenant A: {nome_b!r}'
        )


def test_seed_e_idempotente(monkeypatch):
    """Chamar duas vezes não duplica nem levanta."""
    import contabilidade_utils as cu

    with app.app_context():
        aid = _admin()
        cu.seed_plano_contas_if_needed(aid)
        db.session.commit()
        n1 = len(_contas_de(aid))

        # O cache em memória mascararia a 2ª chamada; queremos exercitar o
        # caminho de banco.
        cu._v2_seeded_admins.discard(aid)
        cu.seed_plano_contas_if_needed(aid)
        db.session.commit()

        assert len(_contas_de(aid)) == n1


# ---------------------------------------------------------------------------
# O motor V2 passa a lançar no plano do próprio tenant
# ---------------------------------------------------------------------------

def test_lancamento_v2_de_tenant_novo_usa_conta_do_proprio_tenant():
    """Era isto que estava quebrado na prática: 313 empresas lançavam sobre
    o plano de contas de outra."""
    from datetime import date

    from contabilidade_utils import gerar_lancamento_contabil_automatico

    with app.app_context():
        aid = _admin()

        ok = gerar_lancamento_contabil_automatico(
            admin_id=aid, tipo_operacao='despesa_alimentacao', valor=500.0,
            data=date(2026, 3, 10), descricao='teste D4',
        )
        db.session.commit()
        assert ok

        orfas = db.session.execute(sa_text("""
            SELECT COUNT(*) FROM partida_contabil p
             WHERE p.admin_id = :a
               AND NOT EXISTS (
                   SELECT 1 FROM plano_contas pc
                    WHERE pc.codigo = p.conta_codigo
                      AND pc.admin_id = p.admin_id
               )
        """), {'a': aid}).scalar()
        assert orfas == 0, (
            f'{orfas} partida(s) do tenant apontando para conta de outro'
        )


def test_nenhuma_partida_do_banco_aponta_para_conta_de_outro_tenant():
    """Invariante global, pós-backfill da migração 218.

    Antes: 980 de 1.204. Esta asserção é o que o backfill tem que zerar —
    e é a mesma condição que a FK composta passa a impedir.
    """
    with app.app_context():
        orfas = db.session.execute(sa_text("""
            SELECT COUNT(*) FROM partida_contabil p
             WHERE NOT EXISTS (
                 SELECT 1 FROM plano_contas pc
                  WHERE pc.codigo = p.conta_codigo
                    AND pc.admin_id = p.admin_id
             )
        """)).scalar()
        assert orfas == 0, f'{orfas} partidas apontam para conta de outro tenant'
