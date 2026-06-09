"""
Fase C (TDD) — seed das Regras de Classificação do sistema no banco, por tenant.

seed_para_admin(admin_id): persiste REGRAS_SISTEMA como PalavraChaveCategoria
(origem='sistema'), resolvendo categoria_nome → categoria_fluxo_caixa_id do tenant.
Idempotente. regras_do_tenant(admin_id): lê de volta como objetos Regra.

Usa flush + rollback — não polui o banco.
"""
import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db


@pytest.fixture(scope="module", autouse=True)
def _app_ctx():
    app.config["TESTING"] = True
    with app.app_context():
        db.create_all()
        yield


@pytest.fixture
def admin_com_categorias():
    """Tenant com as 44 categorias padrão semeadas; desfaz no fim."""
    from models import Usuario, TipoUsuario, CategoriaFluxoCaixa
    from werkzeug.security import generate_password_hash

    s = datetime.utcnow().strftime("%f%S")
    admin = Usuario(
        username=f"seedpck_{s}", email=f"seedpck_{s}@sige.test", nome="Seed PCK",
        tipo_usuario=TipoUsuario.ADMIN,
        password_hash=generate_password_hash("Test@1234"),
        versao_sistema="v2", ativo=True,
    )
    db.session.add(admin)
    db.session.flush()
    CategoriaFluxoCaixa.seed_defaults(admin.id)
    db.session.flush()

    yield admin.id

    db.session.rollback()


def test_seed_cria_regras_do_sistema_e_e_idempotente(admin_com_categorias):
    from services.seed_palavras_chave import seed_para_admin
    from models import PalavraChaveCategoria

    admin_id = admin_com_categorias

    n1 = seed_para_admin(admin_id)
    total1 = PalavraChaveCategoria.query.filter_by(
        admin_id=admin_id, origem="sistema").count()
    assert n1 > 0
    assert total1 == n1

    # 2a execução não cria nada novo (idempotente)
    n2 = seed_para_admin(admin_id)
    total2 = PalavraChaveCategoria.query.filter_by(
        admin_id=admin_id, origem="sistema").count()
    assert n2 == 0
    assert total2 == total1


def test_regras_do_tenant_round_trip_com_gatilho_extra(admin_com_categorias):
    from services.seed_palavras_chave import seed_para_admin, regras_do_tenant

    admin_id = admin_com_categorias
    seed_para_admin(admin_id)

    regras = regras_do_tenant(admin_id)
    assert len(regras) > 0

    # a regra km+dígito (Transporte de Obra) deve voltar com a condição extra
    km = [r for r in regras
          if r.categoria_nome == "Transporte de Obra" and r.gatilho_extra]
    assert km, "regra com gatilho_extra deveria sobreviver ao round-trip"
    assert set("0123456789").issubset(set(km[0].gatilho_extra))
