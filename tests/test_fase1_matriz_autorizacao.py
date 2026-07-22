"""Fase 1 — matriz papel × obra × ação.

Uma tabela só, para que a regressão apareça como célula errada e não
como teste solto. Mesmo espírito de
`tests/test_cronograma_permissoes.py::_rotas`.
"""
import os
import sys
import uuid
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401
from app import app, db
from models import (Cliente, Obra, PapelObra, TipoUsuario, Usuario,
                    UsuarioObra)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase1-matriz'
    yield


def _usuario(tipo, admin_id=None, nome='U'):
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'm1_{suf}', email=f'm1_{suf}@test.local', nome=f'{nome} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=tipo, ativo=True, admin_id=admin_id, versao_sistema='v2')
    db.session.add(u)
    db.session.commit()
    return u


def _obra_de(admin_id):
    suf = uuid.uuid4().hex[:8]
    cliente = Cliente(nome=f'Cli {suf}', admin_id=admin_id)
    db.session.add(cliente)
    db.session.commit()
    o = Obra(nome=f'Obra {suf}', codigo=f'M{suf[:6].upper()}',
             data_inicio=date(2026, 1, 1), admin_id=admin_id,
             cliente_id=cliente.id, ativo=True)
    db.session.add(o)
    db.session.commit()
    return o


def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


# ator → (ver, editar, apontar) na obra do PRÓPRIO tenant, flag LIGADA
MATRIZ = {
    'admin':            (True,  True,  True),
    'gestor':           (True,  True,  True),
    'apontador':        (True,  False, True),
    'leitor':           (True,  False, False),
    'sem_vinculo':      (False, False, False),
    'admin_outro':      (False, False, False),
    'anonimo':          (False, False, False),
}


@pytest.fixture(scope='module')
def cenario():
    """Um tenant, uma obra, um ator de cada tipo. Devolve só ids."""
    with app.app_context():
        from scripts.flag_escopo_obra import definir_flag

        admin = _usuario(TipoUsuario.ADMIN, nome='Dono')
        outro = _usuario(TipoUsuario.ADMIN, nome='Concorrente')
        obra = _obra_de(admin.id)

        atores = {'admin': admin.id, 'admin_outro': outro.id, 'anonimo': None}
        for chave, papel in (('gestor', PapelObra.GESTOR),
                             ('apontador', PapelObra.APONTADOR),
                             ('leitor', PapelObra.LEITOR)):
            u = _usuario(TipoUsuario.FUNCIONARIO, admin_id=admin.id, nome=chave)
            db.session.add(UsuarioObra(usuario_id=u.id, obra_id=obra.id,
                                       papel=papel, admin_id=admin.id))
            atores[chave] = u.id
        atores['sem_vinculo'] = _usuario(
            TipoUsuario.FUNCIONARIO, admin_id=admin.id, nome='orfao').id
        db.session.commit()
        definir_flag(admin.id, True)

        return {'obra_id': obra.id, 'atores': atores}


@pytest.mark.parametrize('ator', sorted(MATRIZ))
def test_matriz_de_autorizacao(cenario, ator):
    from utils.autorizacao import (pode_apontar_na_obra, pode_editar_obra,
                                   pode_ver_obra)

    esperado_ver, esperado_editar, esperado_apontar = MATRIZ[ator]
    user_id = cenario['atores'][ator]
    obra_id = cenario['obra_id']

    cliente = app.test_client() if user_id is None else _cliente_de(user_id)
    with cliente:
        cliente.get('/dashboard')
        assert pode_ver_obra(obra_id) is esperado_ver, (
            f'{ator}: pode_ver_obra deveria ser {esperado_ver}')
        assert pode_editar_obra(obra_id) is esperado_editar, (
            f'{ator}: pode_editar_obra deveria ser {esperado_editar}')
        assert pode_apontar_na_obra(obra_id) is esperado_apontar, (
            f'{ator}: pode_apontar_na_obra deveria ser {esperado_apontar}')


@pytest.mark.parametrize('ator', sorted(MATRIZ))
def test_detalhe_da_obra_respeita_a_matriz(cenario, ator):
    esperado_ver = MATRIZ[ator][0]
    user_id = cenario['atores'][ator]
    obra_id = cenario['obra_id']

    cliente = app.test_client() if user_id is None else _cliente_de(user_id)
    r = cliente.get(f'/obras/{obra_id}', follow_redirects=False)

    if esperado_ver:
        assert r.status_code == 200, f'{ator}: esperava 200, veio {r.status_code}'
    elif user_id is None:
        assert r.status_code in (302, 401), f'{ator}: anônimo veio {r.status_code}'
    else:
        assert r.status_code == 404, (
            f'{ator}: esperava 404 (sem vazar existência), veio {r.status_code}')
