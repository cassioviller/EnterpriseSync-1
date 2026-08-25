"""Onda 1 — os cinco lugares em que o dinheiro entrava errado.

Cada teste entra pela porta do operador (rota HTTP ou serviço), não pelo
parser: o parser já tem `tests/test_decimal_br.py`. O que se prova aqui é que
a correção chegou ao caminho vivo.
"""
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from models import Cliente, Obra, TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-onda1-dinheiro'
    yield


@pytest.fixture(autouse=True, scope='module')
def _schema():
    """As 271-273 são idempotentes; rodá-las aqui é seguro.

    O boot da suíte roda com SIGE_BOOT_DDL=0 (conftest) — nem create_all nem
    migrações.
    """
    from migrations import (_migration_271_obra_contrato_versao,
                            _migration_272_aditivo_contrato,
                            _migration_273_medicao_contrato_versionada)
    with app.app_context():
        _migration_271_obra_contrato_versao()
        _migration_272_aditivo_contrato()
        _migration_273_medicao_contrato_versionada()
    yield


def _novo_admin(prefixo='onda1'):
    suf = uuid.uuid4().hex[:8]
    admin = Usuario(
        username=f'{prefixo}_{suf}', email=f'{prefixo}_{suf}@test.local',
        nome=f'Admin {prefixo} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(admin)
    db.session.flush()
    return admin


def _nova_obra(admin, valor_contrato=0.0):
    suf = uuid.uuid4().hex[:8]
    cliente = Cliente(admin_id=admin.id, nome=f'Cliente {suf}',
                      email=f'cli_{suf}@test.local', telefone='11988887777')
    db.session.add(cliente)
    db.session.flush()
    obra = Obra(nome=f'Obra {suf}', codigo=f'OBR{suf}',
                data_inicio=date(2026, 1, 10), admin_id=admin.id,
                cliente_id=cliente.id, valor_contrato=valor_contrato)
    db.session.add(obra)
    db.session.flush()
    return obra


# ---------------------------------------------------------------------------
# Task 2 — o aditivo
# ---------------------------------------------------------------------------

def test_aditivo_nao_le_150000_ponto_00_como_quinze_milhoes():
    """🔴 `views/aditivos_views.py:102` fazia `.replace('.', '')` sem condição.

    Um teclado numérico produz ponto. `150000.00` virava `15000000`, e a
    aprovação gravava R$ 15.000.000,00 em `obra.valor_contrato` e lançava
    ~R$ 14,85M de receita no razão.
    """
    from services.contrato_obra import ORIGEM_CADASTRO, definir_valor_contrato
    with app.app_context():
        admin = _novo_admin('onda1_adit')
        obra = _nova_obra(admin, valor_contrato=0.0)
        definir_valor_contrato(obra, 100000.0, origem=ORIGEM_CADASTRO,
                               motivo='contrato original')
        db.session.commit()
        obra_id, admin_id = obra.id, admin.id

    cliente = app.test_client()
    with cliente.session_transaction() as sessao:
        sessao['_user_id'] = str(admin_id)
        sessao['_fresh'] = True

    resposta = cliente.post(
        f'/obras/{obra_id}/aditivos/novo',
        data={'tipo': 'acrescimo', 'motivo': 'acréscimo de escopo',
              'valor_novo': '150000.00'},
        follow_redirects=True)
    assert resposta.status_code in (200, 400)

    with app.app_context():
        from models import AditivoContrato
        aditivo = AditivoContrato.query.filter_by(obra_id=obra_id).first()
        assert aditivo is not None, 'o aditivo precisa ter sido aberto'
        assert Decimal(str(aditivo.valor_novo)) == Decimal('150000.00'), (
            f'150000.00 virou {aditivo.valor_novo} — o parser inflou o '
            f'contrato')


def test_aditivo_recusa_valor_ambiguo_em_vez_de_adivinhar():
    """`1.500` não é lido: é devolvido ao operador para desambiguar."""
    from services.contrato_obra import ORIGEM_CADASTRO, definir_valor_contrato
    with app.app_context():
        admin = _novo_admin('onda1_ambig')
        obra = _nova_obra(admin, valor_contrato=0.0)
        definir_valor_contrato(obra, 100000.0, origem=ORIGEM_CADASTRO,
                               motivo='contrato original')
        db.session.commit()
        obra_id, admin_id = obra.id, admin.id

    cliente = app.test_client()
    with cliente.session_transaction() as sessao:
        sessao['_user_id'] = str(admin_id)
        sessao['_fresh'] = True

    resposta = cliente.post(
        f'/obras/{obra_id}/aditivos/novo',
        data={'tipo': 'acrescimo', 'motivo': 'teste', 'valor_novo': '1.500'})
    assert resposta.status_code == 400
    assert 'ambíguo' in resposta.get_data(as_text=True)

    with app.app_context():
        from models import AditivoContrato
        assert AditivoContrato.query.filter_by(obra_id=obra_id).count() == 0, (
            'entrada ambígua não pode abrir aditivo nenhum')
