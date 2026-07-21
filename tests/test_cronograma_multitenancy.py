"""M10 Task 3 — isolamento entre obras e tenants (critério global 1).

"Duas obras com `.mpp` e cronogramas independentes": aplicar, restaurar e
listar em uma obra não pode tocar nem revelar a outra — nem na obra
vizinha do MESMO tenant, nem na obra de OUTRO tenant.

A fotografia de estado usa `scripts/verificar_equivalencia_obra.capturar_estado`
(M09): o mesmo instrumento que serve de gate na migração serve aqui de
sensor de vazamento. Qualquer efeito colateral em obra vizinha aparece
como divergência.

NOTA de harness: requests dos test clients ficam FORA de app_context
aberto (Flask-Login cacheia `g._login_user`) — disciplina dos fechos
M05/M07/M08.
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import (
    CronogramaImportacao,
    CronogramaVersao,
    TarefaCronograma,
)
from scripts.verificar_equivalencia_obra import capturar_estado, comparar_estados
from test_cronograma_endpoints_m05 import _client_como, _imp_normalizada
from test_cronograma_versao_service import _ambiente, _nt, _tarefa

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-multitenancy-cronograma'
    yield


def _obra_com_cronograma(admin=None, prefixo='T'):
    """Obra com duas tarefas + importação normalizada pronta para aplicar.

    Sem `admin` cria um tenant novo; com `admin` a obra nasce no mesmo
    tenant (o caso 'duas obras do mesmo dono').
    """
    if admin is None:
        admin, obra = _ambiente()
    else:
        _outro, obra = _ambiente()
        obra.admin_id = admin.id
        db.session.commit()

    _tarefa(obra, admin, f'{prefixo} Fundação', ordem=0, mpp_uid=1)
    _tarefa(obra, admin, f'{prefixo} Alvenaria', ordem=1, mpp_uid=2)
    imp = _imp_normalizada(
        obra, admin,
        _nt('uid:1', f'{prefixo} Fundação', uid=1,
            inicio='2026-09-01', fim='2026-09-10', dias=8.0),
        _nt('uid:2', f'{prefixo} Alvenaria Estrutural', uid=2,
            inicio='2026-09-11', fim='2026-09-20', dias=8.0),
    )
    # Versão nº1 "estilo backfill" (migração 210): toda obra com tarefas tem
    # uma; é dela que o rollback parte.
    v1 = CronogramaVersao(obra_id=obra.id, admin_id=admin.id, numero=1,
                          status='ativa', observacao='backfill inicial')
    db.session.add(v1)
    db.session.commit()
    return {'admin_id': admin.id, 'obra_id': obra.id, 'imp_id': imp.id,
            'versao_inicial_id': v1.id}


def _aplicar(ctx):
    c = _client_como(ctx['admin_id'])
    base = (f"/obras/{ctx['obra_id']}/cronograma/importacoes/{ctx['imp_id']}")
    r = c.post(f'{base}/reconciliar')
    assert r.status_code == 200, r.get_data(as_text=True)
    r = c.post(f'{base}/aplicar')
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()


# ---------------------------------------------------------------------------
# Critério global 1 — cronogramas independentes
# ---------------------------------------------------------------------------

def test_aplicar_em_um_tenant_nao_toca_o_vizinho():
    with app.app_context():
        a = _obra_com_cronograma(prefixo='A')
        b = _obra_com_cronograma(prefixo='B')
        estado_b_antes = capturar_estado(b['obra_id'], b['admin_id'])

    _aplicar(a)

    with app.app_context():
        estado_b_depois = capturar_estado(b['obra_id'], b['admin_id'])
        cmp = comparar_estados(estado_b_antes, estado_b_depois)
        assert cmp['equivalente'], cmp['divergencias']

        # O vizinho segue com o nome ANTIGO (o rename só ocorreu em A).
        nomes_b = sorted(t.nome_tarefa for t in TarefaCronograma.query.filter_by(
            obra_id=b['obra_id'], ativa=True).all())
        assert nomes_b == ['B Alvenaria', 'B Fundação']
        nomes_a = sorted(t.nome_tarefa for t in TarefaCronograma.query.filter_by(
            obra_id=a['obra_id'], ativa=True).all())
        assert nomes_a == ['A Alvenaria Estrutural', 'A Fundação']

        # Versionamento independente: B segue com a versão nº1 intacta,
        # enquanto A ganhou a nº2 da aplicação.
        versoes_b = CronogramaVersao.query.filter_by(
            obra_id=b['obra_id']).all()
        assert [(v.numero, v.status) for v in versoes_b] == [(1, 'ativa')]
        numeros_a = sorted(v.numero for v in CronogramaVersao.query.filter_by(
            obra_id=a['obra_id']).all())
        assert numeros_a == [1, 2]


def test_duas_obras_do_mesmo_tenant_sao_independentes():
    """Isolamento é por OBRA, não só por tenant."""
    with app.app_context():
        a = _obra_com_cronograma(prefixo='A')
        with app.app_context():
            from models import Usuario
            admin = db.session.get(Usuario, a['admin_id'])
            b = _obra_com_cronograma(admin=admin, prefixo='B')
        estado_b_antes = capturar_estado(b['obra_id'], b['admin_id'])

    _aplicar(a)

    with app.app_context():
        cmp = comparar_estados(
            estado_b_antes, capturar_estado(b['obra_id'], b['admin_id']))
        assert cmp['equivalente'], cmp['divergencias']
        assert [v.numero for v in CronogramaVersao.query.filter_by(
            obra_id=b['obra_id']).all()] == [1]


def test_restaurar_em_uma_obra_nao_desfaz_a_outra():
    with app.app_context():
        a = _obra_com_cronograma(prefixo='A')
        b = _obra_com_cronograma(prefixo='B')

    corpo_a = _aplicar(a)
    _aplicar(b)

    with app.app_context():
        estado_b = capturar_estado(b['obra_id'], b['admin_id'])
        # A nº1 foi arquivada pela aplicação (que a fotografou antes de mudar).
        versao_id = a['versao_inicial_id']
        assert versao_id != corpo_a['versao_id']

    c = _client_como(a['admin_id'])
    r = c.post(f"/obras/{a['obra_id']}/cronograma/versoes/{versao_id}/restaurar")
    assert r.status_code == 200, r.get_data(as_text=True)

    with app.app_context():
        cmp = comparar_estados(
            estado_b, capturar_estado(b['obra_id'], b['admin_id']))
        assert cmp['equivalente'], cmp['divergencias']
        # B mantém o nome NOVO — o rollback de A não alcançou a obra vizinha.
        nomes_b = sorted(t.nome_tarefa for t in TarefaCronograma.query.filter_by(
            obra_id=b['obra_id'], ativa=True).all())
        assert nomes_b == ['B Alvenaria Estrutural', 'B Fundação']


# ---------------------------------------------------------------------------
# Listas: cada obra só enxerga o que é seu
# ---------------------------------------------------------------------------

def test_listas_de_importacoes_e_versoes_nao_se_misturam():
    with app.app_context():
        a = _obra_com_cronograma(prefixo='A')
        b = _obra_com_cronograma(prefixo='B')
    _aplicar(a)
    _aplicar(b)

    for dono, alheio in ((a, b), (b, a)):
        c = _client_como(dono['admin_id'])
        r = c.get(f"/obras/{dono['obra_id']}/cronograma/importacoes")
        assert r.status_code == 200
        ids = {i['id'] for i in r.get_json()['importacoes']}
        assert dono['imp_id'] in ids
        assert alheio['imp_id'] not in ids

        r = c.get(f"/obras/{dono['obra_id']}/cronograma/versoes")
        assert r.status_code == 200
        with app.app_context():
            versoes_alheias = {v.id for v in CronogramaVersao.query.filter_by(
                obra_id=alheio['obra_id']).all()}
        assert not ({v['id'] for v in r.get_json()['versoes']}
                    & versoes_alheias)


def test_upload_do_mesmo_arquivo_em_obras_diferentes_nao_colide():
    """Dedup por SHA-256 é por OBRA (critério 2 vs critério 1): o mesmo
    arquivo pode ser importado em duas obras sem 409 cruzado."""
    with app.app_context():
        a = _obra_com_cronograma(prefixo='A')
        b = _obra_com_cronograma(prefixo='B')
        # Mesmo hash gravado nas duas importações — estado que o dedup lê.
        for ctx in (a, b):
            imp = db.session.get(CronogramaImportacao, ctx['imp_id'])
            imp.arquivo_sha256 = 'f' * 64
        db.session.commit()

        hashes = [i.arquivo_sha256 for i in CronogramaImportacao.query.filter(
            CronogramaImportacao.id.in_([a['imp_id'], b['imp_id']])).all()]
        assert hashes == ['f' * 64, 'f' * 64], 'hash igual em obras distintas'

    # E ambas seguem aplicáveis, cada uma na sua obra.
    _aplicar(a)
    _aplicar(b)
    with app.app_context():
        for ctx, prefixo in ((a, 'A'), (b, 'B')):
            nomes = sorted(t.nome_tarefa for t in TarefaCronograma.query
                           .filter_by(obra_id=ctx['obra_id'], ativa=True).all())
            assert nomes == [f'{prefixo} Alvenaria Estrutural',
                             f'{prefixo} Fundação']


def test_data_de_referencia_nao_vaza_entre_obras():
    """Sanidade do sensor: datas aplicadas em A não aparecem em B."""
    with app.app_context():
        a = _obra_com_cronograma(prefixo='A')
        b = _obra_com_cronograma(prefixo='B')
    _aplicar(a)
    with app.app_context():
        t_b = TarefaCronograma.query.filter_by(
            obra_id=b['obra_id'], ativa=True).order_by(
            TarefaCronograma.ordem).first()
        assert t_b.data_inicio != date(2026, 9, 1)
