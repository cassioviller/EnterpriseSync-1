import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

import pytest
from decimal import Decimal
from app import app, db
from models import MedicaoContrato


@pytest.mark.integration
def test_medicao_contrato_schema_existe():
    with app.app_context():
        cols = {c.name for c in MedicaoContrato.__table__.columns}
        assert {'obra_id', 'admin_id', 'nome', 'data', 'pct',
                'recebido_no_mes', 'obs', 'ordem'} <= cols
