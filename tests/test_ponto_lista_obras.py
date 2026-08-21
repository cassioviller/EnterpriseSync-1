"""Listagem /ponto/lista-obras — paginada e sem a contagem de ponto por obra.

🔬 21/08: a rota fazia um `count()` de `registro_ponto` POR OBRA para montar
`registros_hoje` — chave que `templates/ponto/lista_obras.html` nunca imprime
(o card mostra o total global de funcionários, igual em todos). Medido no
tenant demo (1.358 obras ativas): **5,09 s, 2,29 MB, 1.365 consultas, 1.358
delas em `registro_ponto`**. Era a última página no limite da varredura depois
que `/obras` foi corrigida — mesmo defeito, mesma forma.
"""
import os
import re
import sys
from datetime import date

import pytest
from sqlalchemy import event

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import Obra
from test_cronograma_endpoints_m05 import _client_como
from test_cronograma_versao_service import _ambiente, _suf

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-ponto-lista-obras'
    yield


def _tenant_com_obras(n_extra: int):
    """Admin novo com 1 + n_extra obras ativas, nomeadas 'Turno NNN'."""
    with app.app_context():
        admin, obra = _ambiente()
        obra.nome = 'Turno 000'
        for i in range(1, n_extra + 1):
            suf = _suf()
            db.session.add(Obra(
                nome=f'Turno {i:03d}', codigo=f'TN-{suf[:12]}',
                admin_id=admin.id, cliente_id=obra.cliente_id,
                status='Em andamento', ativo=True,
                data_inicio=date(2026, 7, 1)))
        db.session.commit()
        return admin.id


def _cards(html: str) -> int:
    """Um card = um link para o dashboard de ponto daquela obra."""
    return len(re.findall(r'href="/ponto/obra/\d+"', html))


def _sql_emitido(client, path):
    """Lista de statements SQL disparados durante UM GET."""
    stmts = []

    def _captura(conn, cursor, statement, parameters, context, executemany):
        stmts.append(statement.lower())

    with app.app_context():
        engine = db.engine          # `db.engine` exige contexto; o listener não
    event.listen(engine, 'before_cursor_execute', _captura)
    try:
        resp = client.get(path)
    finally:
        event.remove(engine, 'before_cursor_execute', _captura)
    assert resp.status_code == 200, resp.status_code
    return stmts


def test_lista_nao_cresce_em_consultas_com_o_numero_de_obras():
    """Nenhum trabalho por obra: o card não mostra nada que dependa da obra
    além do que veio na própria listagem."""
    poucas = _sql_emitido(_client_como(_tenant_com_obras(0)), '/ponto/lista-obras')
    muitas = _sql_emitido(_client_como(_tenant_com_obras(40)), '/ponto/lista-obras')

    assert len(muitas) <= len(poucas) + 2, (
        f'{len(poucas)} consultas com 1 obra, {len(muitas)} com 41 — '
        f'a listagem ainda faz trabalho por obra')
    assert not any('from registro_ponto' in s for s in muitas), (
        'a listagem ainda conta registro_ponto por obra — número que o card '
        'não mostra')


def test_lista_pagina_de_50_e_preserva_o_filtro():
    admin_id = _tenant_com_obras(50)          # 51 obras
    client = _client_como(admin_id)

    r1 = client.get('/ponto/lista-obras?nome=Turno')
    assert r1.status_code == 200
    html1 = r1.get_data(as_text=True)
    assert _cards(html1) == 50, _cards(html1)
    assert re.search(r'href="[^"]*page=2[^"]*"', html1), 'sem link para a página 2'
    link2 = re.search(r'href="([^"]*page=2[^"]*)"', html1).group(1)
    assert 'nome=Turno' in link2, link2

    r2 = client.get('/ponto/lista-obras?nome=Turno&page=2')
    assert _cards(r2.get_data(as_text=True)) == 1
