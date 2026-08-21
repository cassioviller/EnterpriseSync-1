"""A página do RDO mostra o estado do ciclo de vida — não o `status` legado.

🔬 21/08 (captura do manual visual): um RDO em RASCUNHO aparecia com o selo
"Finalizado" no bloco de informações, ao lado da pílula "Rascunho" do
cabeçalho. `RDO.status` é a coluna legada que ≥9 consumidores filtram por
'Finalizado' (services/rdo_ciclo_vida.py, docstring) — ela não é tocada pelo
ciclo de vida, então vale 'Finalizado' até para rascunho. Mostrá-la ensina
errado: o estado real é `estado_rdo`, que a view já passa ao template.
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401
from app import app, db
from models import RDO
from test_cronograma_endpoints_m05 import _client_como
from test_cronograma_versao_service import _ambiente, _suf

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-rdo-estado-real'
    yield


def _rdo_em_rascunho():
    with app.app_context():
        admin, obra = _ambiente()
        rdo = RDO(numero_rdo=f'RDO-T-{_suf()[:14]}', data_relatorio=date(2026, 8, 21),
                  obra_id=obra.id, admin_id=admin.id, criado_por_id=admin.id)
        db.session.add(rdo)
        db.session.commit()
        assert rdo.estado == 'rascunho'
        return admin.id, rdo.id


def test_rascunho_nao_aparece_como_finalizado():
    admin_id, rdo_id = _rdo_em_rascunho()
    r = _client_como(admin_id).get(f'/rdo/{rdo_id}')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert '>Finalizado<' not in html, 'o selo legado "Finalizado" ainda aparece num rascunho'
    assert html.count('Rascunho') >= 2, 'o estado real tem de aparecer no cabeçalho E no bloco de informações'
