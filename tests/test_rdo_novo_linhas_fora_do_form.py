"""RDO novo: as linhas de ocorrência/equipamento têm de pertencer ao formulário.

🔬 21/08 — no navegador, o `<form id="formNovoRDO">` fecha antes dos cards de
cronograma, equipamentos, ocorrências, observações e fotos (a contagem de
`</div>` dentro do form chega a −4; o parser fecha o form na linha 317 do
template). Os inputs de foto já levam `form="formNovoRDO"` à mão e os
apontamentos são injetados como hidden direto no form — mas as linhas de
ocorrência/equipamento, criadas por `adicionarLinhaRepetivel`, nasciam sem
dono: o usuário preenchia a ocorrência e o POST não a levava. O backend grava
quando recebe (`utils/rdo_equip_ocorr.parse_ocorrencias`); quem perdia era o
navegador. Este teste pina o atributo `form` nos dois templates de linha.
"""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401
from app import app
from test_cronograma_endpoints_m05 import _client_como
from test_cronograma_versao_service import _ambiente

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-rdo-novo-form'
    yield


def _html_do_rdo_novo():
    with app.app_context():
        admin, obra = _ambiente()
        admin_id, obra_id = admin.id, obra.id
    r = _client_como(admin_id).get(f'/rdo/novo?obra_id={obra_id}')
    assert r.status_code == 200
    return r.get_data(as_text=True)


def test_linhas_repetiveis_declaram_o_form_dono():
    html = _html_do_rdo_novo()
    i = html.index('function adicionarLinhaRepetivel')
    bloco = html[i:i + 4000]
    for campo in ('ocorr_tipo[]', 'ocorr_severidade[]', 'ocorr_descricao[]', 'ocorr_status[]',
                  'equip_nome[]', 'equip_quantidade[]', 'equip_horas_uso[]', 'equip_estado[]'):
        tag = re.search(r'<(input|select)[^>]*name="' + re.escape(campo) + r'"[^>]*>', bloco)
        assert tag, f'{campo} não está no template de linha'
        assert 'form="${formId}"' in tag.group(0), (
            f'{campo} sem form="${{formId}}" — a linha nasce fora do form e o POST a perde')
