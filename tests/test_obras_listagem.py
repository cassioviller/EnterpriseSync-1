"""Listagem /obras — paginada e sem custo escondido por obra.

🔬 21/08: a rota calculava ~6 consultas de custo POR OBRA para um `obra.kpis`
que o template renderizado (`obras_moderno.html`) nunca leu — quem lia era
`templates/obras.html`, morto desde julho. Com 1.320 obras no tenant demo a
página levava 8,3 s e 5 MB, e a varredura de páginas caía por timeout.
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

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-obras-listagem'
    yield


def _tenant_com_obras(n_extra: int):
    """Admin novo com 1 + n_extra obras, todas com o nome começando em 'Lote'."""
    with app.app_context():
        admin, obra = _ambiente()
        obra.nome = 'Lote 000'
        for i in range(1, n_extra + 1):
            suf = _suf()
            db.session.add(Obra(
                nome=f'Lote {i:03d}', codigo=f'LT-{suf[:12]}',
                admin_id=admin.id, cliente_id=obra.cliente_id,
                status='Em andamento', data_inicio=date(2026, 7, 1)))
        db.session.commit()
        return admin.id


def _cards(html: str) -> int:
    return len(re.findall(r'data-obra-id="\d+"', html))


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


def test_listagem_pagina_de_50_e_preserva_o_filtro():
    admin_id = _tenant_com_obras(50)          # 51 obras
    client = _client_como(admin_id)

    r1 = client.get('/obras?nome=Lote')
    assert r1.status_code == 200
    html1 = r1.get_data(as_text=True)
    assert _cards(html1) == 50
    # o link da próxima página carrega o filtro junto
    assert re.search(r'href="[^"]*page=2[^"]*"', html1), 'sem link para a página 2'
    link2 = re.search(r'href="([^"]*page=2[^"]*)"', html1).group(1)
    assert 'nome=Lote' in link2

    r2 = client.get('/obras?nome=Lote&page=2')
    assert _cards(r2.get_data(as_text=True)) == 1


def test_listagem_nao_cresce_em_consultas_com_o_numero_de_obras():
    """O número de consultas da página não pode depender de quantas obras há:
    nem custo por obra, nem cliente/responsável carregados um a um."""
    poucas = _sql_emitido(_client_como(_tenant_com_obras(0)), '/obras')
    muitas = _sql_emitido(_client_como(_tenant_com_obras(40)), '/obras')

    assert len(muitas) <= len(poucas) + 2, (
        f'{len(poucas)} consultas com 1 obra, {len(muitas)} com 41 — '
        f'a listagem ainda faz trabalho por obra')
    for tabela in ('registro_ponto', 'outro_custo', 'registro_alimentacao',
                   'vehicle_expense', 'gestao_custo_filho'):
        assert not any(f'from {tabela}' in s for s in muitas), (
            f'a listagem ainda consulta {tabela} — custo que o card não mostra')


def test_template_obras_html_morto_foi_removido():
    """`templates/obras.html` era o único leitor de `obra.kpis` e nenhuma rota
    o renderiza. Sensor: o arquivo não existe e ninguém o cita como template."""
    assert not os.path.exists(os.path.join(RAIZ, 'templates', 'obras.html'))
    import subprocess
    saida = subprocess.run(
        ['grep', '-rn', '--include=*.py', '--include=*.html',
         "render_template('obras.html'", '.'],
        cwd=RAIZ, capture_output=True, text=True).stdout
    refs = [l for l in saida.splitlines()
            if not l.startswith('./.') and './archive/' not in l
            and not l.startswith('./tests/')]   # este arquivo cita o padrão
    assert refs == [], refs
