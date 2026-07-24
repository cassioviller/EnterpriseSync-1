"""Fase 5 (editor v2) — manual de uso em PDF (plano Step D).

Cobre o spec §7: botão "Manual (PDF)" na toolbar da página do cronograma
servindo `static/docs/manual-cronograma.pdf`:

  * flag ON → o link para o PDF aparece na página;
  * flag OFF → não aparece (byte-idêntico ao legado);
  * o arquivo versionado existe, é um PDF de verdade e tem tamanho
    plausível (as capturas de tela estão embutidas);
  * `GET /static/...` serve o arquivo com Content-Type de PDF.

NOTA de harness (mesma disciplina das fases 1–4): requests dos test
clients ficam FORA de app_context aberto.
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import ConfiguracaoEmpresa
from test_cronograma_endpoints_m05 import _client_como
from test_cronograma_versao_service import _ambiente, _tarefa

pytestmark = pytest.mark.integration

CAMINHO_PDF = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'static', 'docs', 'manual-cronograma.pdf')
HREF_PDF = 'docs/manual-cronograma.pdf'
ROTULO = 'Manual (PDF)'


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-manual-cronograma'
    yield


def _flag_editor_v2(admin_id: int, ativo: bool) -> None:
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    if config is None:
        config = ConfiguracaoEmpresa(admin_id=admin_id,
                                     nome_empresa=f'Empresa {admin_id}')
        db.session.add(config)
    config.cronograma_editor_v2 = bool(ativo)
    db.session.commit()


def _cenario(flag: bool = True) -> dict:
    with app.app_context():
        admin, obra = _ambiente()
        _flag_editor_v2(admin.id, flag)
        _tarefa(obra, admin, 'Fundação', ordem=0, duracao_dias=5,
                data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 7))
        return {'admin_id': admin.id, 'obra_id': obra.id}


def test_flag_on_pagina_tem_o_botao_do_manual():
    """(1) Com a flag ligada, a toolbar linka o PDF do manual."""
    ctx = _cenario(flag=True)
    c = _client_como(ctx['admin_id'])
    r = c.get(f"/cronograma/obra/{ctx['obra_id']}")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert HREF_PDF in html
    assert ROTULO in html


def test_flag_off_pagina_nao_tem_o_botao():
    """(2) Flag desligada = cabeçalho legado, sem link para o manual."""
    ctx = _cenario(flag=False)
    c = _client_como(ctx['admin_id'])
    r = c.get(f"/cronograma/obra/{ctx['obra_id']}")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert HREF_PDF not in html
    assert ROTULO not in html


def test_pdf_versionado_existe_e_e_um_pdf_com_capturas():
    """(3) O arquivo estático do repo é um PDF real e não está vazio.

    O limiar de 200 KB garante que as capturas de tela (o grosso do
    tamanho) foram embutidas — um PDF só de texto ficaria bem abaixo.
    """
    assert os.path.isfile(CAMINHO_PDF), CAMINHO_PDF
    with open(CAMINHO_PDF, 'rb') as fh:
        cabecalho = fh.read(5)
    assert cabecalho == b'%PDF-'
    assert os.path.getsize(CAMINHO_PDF) > 200 * 1024


def test_static_serve_o_pdf():
    """(4) A URL usada pelo botão responde 200 com Content-Type de PDF."""
    ctx = _cenario(flag=True)
    c = _client_como(ctx['admin_id'])
    r = c.get('/static/docs/manual-cronograma.pdf')
    assert r.status_code == 200
    assert r.mimetype == 'application/pdf'
    assert r.get_data()[:5] == b'%PDF-'
