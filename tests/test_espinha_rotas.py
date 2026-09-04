"""As telas da espinha financeira — Task 7 do resgate do PR #6.

Três perguntas, e a do meio é a que importa:

  1. quem pode, vê (200);
  2. **quem é de outro tenant leva 404** — teste de VAZAMENTO, não de
     existência. Uma rota nova que responde 200 para obra alheia é uma porta
     aberta, e o `first_or_404` por (id, admin_id) é o que a fecha;
  3. sem v2, redireciona — as telas da espinha são gated (`is_v2_active`).

O arreio de tenant é o de `tests/helpers_tenant.py`, e a armadilha que ele
documenta vale aqui: cada `cliente_de(...).get()` fica FORA de qualquer
`app_context` aberto pelo teste, senão o flask-login reaproveita o
`_login_user` guardado em `flask.g` e o segundo request autentica como o
primeiro usuário — que é exatamente o vazamento que este arquivo procura.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db  # noqa: E402
from helpers_tenant import cliente_de, dois_tenants, um_tenant  # noqa: E402
from models import Usuario  # noqa: E402

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-espinha-rotas'
    yield


def _rotas_da_obra(obra_id):
    return [f'/obras/{obra_id}/resultado', f'/obras/{obra_id}/caixa']


def test_telas_da_obra_respondem_para_quem_pode():
    with app.app_context():
        t = um_tenant('rota-esp', com_fatos=False)
        obra_id, admin_id = t.obra_id, t.admin_id
    c = cliente_de(admin_id)
    for rota in _rotas_da_obra(obra_id):
        resp = c.get(rota)
        assert resp.status_code == 200, f'{rota} devolveu {resp.status_code}'


def test_portfolio_responde_para_quem_pode():
    with app.app_context():
        t = um_tenant('rota-port', com_fatos=False)
        admin_id = t.admin_id
    assert cliente_de(admin_id).get('/resultado/portfolio').status_code == 200


def test_importar_obra_pela_tela_responde():
    """Só o GET: o POST depende de `scripts.importar_baia_easypanel`, que
    chega na Task 9. O import de lá é preguiçoso, dentro do ramo do POST —
    de propósito, para a tela existir antes do script."""
    with app.app_context():
        t = um_tenant('rota-imp', com_fatos=False)
        admin_id = t.admin_id
    assert cliente_de(admin_id).get('/resultado/importar-obra').status_code == 200


def test_obra_de_outro_tenant_da_404():
    """O teste de vazamento. B pede a obra de A: tem de levar 404, não 200 e
    não 500 — 'não existe para você' é a única resposta que não conta ao B
    que a obra do A existe."""
    with app.app_context():
        a, b = dois_tenants('rota-vaz', com_fatos=False)
        obra_de_a, admin_de_b, marca_de_a = a.obra_id, b.admin_id, a.marca
    cliente_b = cliente_de(admin_de_b)
    for rota in _rotas_da_obra(obra_de_a):
        resp = cliente_b.get(rota)
        assert resp.status_code == 404, (
            f'{rota} devolveu {resp.status_code} para tenant alheio')
        assert marca_de_a.encode() not in resp.data, (
            f'{rota} vazou o nome da obra do outro tenant no corpo do 404')


def test_sem_v2_redireciona():
    """As telas da espinha são gated por `is_v2_active`. Sem v2 a resposta é
    302 — e não 200 nem 404: o recurso existe, o plano é que não alcança."""
    with app.app_context():
        t = um_tenant('rota-v1', com_fatos=False)
        admin_id, obra_id = t.admin_id, t.obra_id
        Usuario.query.filter_by(id=admin_id).update({'versao_sistema': 'v1'})
        db.session.commit()
    c = cliente_de(admin_id)
    for rota in _rotas_da_obra(obra_id) + ['/resultado/portfolio',
                                           '/resultado/importar-obra']:
        resp = c.get(rota)
        assert resp.status_code == 302, (
            f'{rota} devolveu {resp.status_code} para tenant sem v2')
