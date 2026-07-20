"""M03 / Task 4 — upload de cronograma.

POST /obras/<obra_id>/cronograma/importacoes: valida, deduplica, persiste,
audita e faz o parse síncrono. Cada teste monta seu próprio admin/obra com
sufixo único (isolamento) e escreve os arquivos em `tmp_path` via
UPLOADS_PATH, para não sujar o repositório.
"""
import io
import os
import sys
import uuid
from datetime import date, datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash

from app import app, db
from models import (
    CronogramaImportacao,
    CronogramaImportacaoEvento,
    Cliente,
    Obra,
    TipoUsuario,
    Usuario,
)

pytestmark = pytest.mark.integration

SENHA = 'Senha@2026'

# Caminho do MSPDI real (103 tarefas) usado no caso feliz.
XML_REAL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'CRONOGRAMA 16.07.xml',
)


def _suf() -> str:
    return f'{datetime.utcnow().strftime("%H%M%S%f")}_{uuid.uuid4().hex[:6]}'


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-upload-cronograma'
    yield


@pytest.fixture(autouse=True)
def _uploads_isolados(tmp_path, monkeypatch):
    """Nunca escreve no static/uploads real durante os testes."""
    monkeypatch.setenv('UPLOADS_PATH', str(tmp_path))
    yield


def _novo_admin(suf):
    admin = Usuario(
        username=f'up_{suf}',
        email=f'up_{suf}@test.local',
        nome=f'Admin Upload {suf}',
        password_hash=generate_password_hash(SENHA),
        tipo_usuario=TipoUsuario.ADMIN,
        ativo=True,
    )
    db.session.add(admin)
    db.session.flush()
    return admin


def _nova_obra(admin, suf):
    cliente = Cliente(
        admin_id=admin.id,
        nome=f'Cliente {suf}',
        email=f'cli_{suf}@test.local',
        telefone='11988887777',
    )
    db.session.add(cliente)
    db.session.flush()
    obra = Obra(
        nome=f'Obra Upload {suf}',
        codigo=f'UP-{suf[:12]}',
        admin_id=admin.id,
        cliente_id=cliente.id,
        status='Em andamento',
        data_inicio=date(2026, 6, 8),
    )
    db.session.add(obra)
    db.session.commit()
    return obra


def _ambiente():
    """Cria admin+cliente+obra e devolve (admin_id, obra_id)."""
    suf = _suf()
    admin = _novo_admin(suf)
    obra = _nova_obra(admin, suf)
    return admin.id, obra.id


def _client_como(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


def _post(c, obra_id, conteudo, nome):
    data = {'arquivo': (io.BytesIO(conteudo), nome)}
    return c.post(
        f'/obras/{obra_id}/cronograma/importacoes',
        data=data,
        content_type='multipart/form-data',
    )


def _bytes_xml_real():
    with open(XML_REAL, 'rb') as fh:
        return fh.read()


# ───────────────────────────────────────────────────────────────────────────
# 1. Caso feliz — MSPDI real → 201, parseado, 103 tarefas, 2 eventos.
# ───────────────────────────────────────────────────────────────────────────
def test_upload_mspdi_real_parseia():
    with app.app_context():
        admin_id, obra_id = _ambiente()
        c = _client_como(admin_id)
        resp = _post(c, obra_id, _bytes_xml_real(), 'CRONOGRAMA 16.07.xml')

        assert resp.status_code == 201, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body['status'] == 'parseado'
        imp_id = body['importacao_id']

        imp = db.session.get(CronogramaImportacao, imp_id)
        assert imp.status == 'parseado'
        assert imp.origem == 'upload_mspdi'
        assert imp.parser_nome == 'mspdi_stdlib'
        assert len(imp.json_bruto['tarefas']) == 103
        assert len(imp.arquivo_sha256) == 64

        eventos = CronogramaImportacaoEvento.query.filter_by(
            importacao_id=imp_id
        ).all()
        tipos = {e.evento for e in eventos}
        assert tipos == {'upload', 'parse_ok'}


# ───────────────────────────────────────────────────────────────────────────
# 2. Mesmo arquivo de novo → 409 com importacao_existente_id.
# ───────────────────────────────────────────────────────────────────────────
def test_dedup_retorna_409():
    with app.app_context():
        admin_id, obra_id = _ambiente()
        c = _client_como(admin_id)
        conteudo = _bytes_xml_real()

        r1 = _post(c, obra_id, conteudo, 'CRONOGRAMA 16.07.xml')
        assert r1.status_code == 201
        primeiro_id = r1.get_json()['importacao_id']

        r2 = _post(c, obra_id, conteudo, 'CRONOGRAMA 16.07.xml')
        assert r2.status_code == 409
        assert r2.get_json()['importacao_existente_id'] == primeiro_id


# ───────────────────────────────────────────────────────────────────────────
# 3. Extensão não suportada (.txt) → 422.
# ───────────────────────────────────────────────────────────────────────────
def test_extensao_invalida_422():
    with app.app_context():
        admin_id, obra_id = _ambiente()
        c = _client_como(admin_id)
        resp = _post(c, obra_id, b'qualquer coisa', 'notas.txt')
        assert resp.status_code == 422
        assert 'erro' in resp.get_json()


# ───────────────────────────────────────────────────────────────────────────
# 4. XML não-MSPDI → 422 antes de persistir.
# ───────────────────────────────────────────────────────────────────────────
def test_xml_nao_mspdi_422():
    with app.app_context():
        admin_id, obra_id = _ambiente()
        c = _client_como(admin_id)
        resp = _post(c, obra_id, b'<foo/>', 'estranho.xml')
        assert resp.status_code == 422
        # Nada foi persistido para esta obra.
        assert CronogramaImportacao.query.filter_by(obra_id=obra_id).count() == 0


# ───────────────────────────────────────────────────────────────────────────
# 5. Obra de outro admin → 404 (isolamento de tenant).
# ───────────────────────────────────────────────────────────────────────────
def test_obra_de_outro_admin_404():
    with app.app_context():
        admin_id_1, _ = _ambiente()
        _, obra_id_2 = _ambiente()  # obra pertence a OUTRO admin
        c = _client_como(admin_id_1)
        resp = _post(c, obra_id_2, _bytes_xml_real(), 'CRONOGRAMA 16.07.xml')
        assert resp.status_code == 404


# ───────────────────────────────────────────────────────────────────────────
# 6. Funcionário (não admin) → 403 pelo decorator.
# ───────────────────────────────────────────────────────────────────────────
def test_funcionario_recebe_403():
    with app.app_context():
        suf = _suf()
        admin = _novo_admin(suf)
        obra = _nova_obra(admin, suf)
        func = Usuario(
            username=f'func_{suf}',
            email=f'func_{suf}@test.local',
            nome=f'Funcionário {suf}',
            password_hash=generate_password_hash(SENHA),
            tipo_usuario=TipoUsuario.FUNCIONARIO,
            admin_id=admin.id,
            ativo=True,
        )
        db.session.add(func)
        db.session.commit()

        c = _client_como(func.id)
        resp = _post(c, obra.id, _bytes_xml_real(), 'CRONOGRAMA 16.07.xml')
        assert resp.status_code == 403


# ───────────────────────────────────────────────────────────────────────────
# 7. .mpp sem Java → 422 com instrução de exportar XML ('Salvar como').
# ───────────────────────────────────────────────────────────────────────────
def test_mpp_sem_java_422(monkeypatch):
    with app.app_context():
        admin_id, obra_id = _ambiente()
        c = _client_como(admin_id)

        from services.mpp_parser import MppParserError

        def _sem_java(_caminho, timeout_s=120):
            raise MppParserError(
                'java_indisponivel',
                'Este servidor não lê .mpp. No MS Project: Arquivo → '
                'Salvar como → tipo XML (.xml), e suba o .xml.',
            )

        monkeypatch.setattr(
            'views.cronograma_importacao.parse_cronograma', _sem_java
        )

        # .mpp com magic bytes OLE2 válidos para passar do sniffing.
        conteudo = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1' + b'\x00' * 32
        resp = _post(c, obra_id, conteudo, 'cronograma.mpp')

        assert resp.status_code == 422
        body = resp.get_json()
        assert 'Salvar como' in body['erro']
        assert body['importacao_id'] is not None

        imp = db.session.get(CronogramaImportacao, body['importacao_id'])
        assert imp.status == 'falhou'
        assert imp.origem == 'upload_mpp'


# ───────────────────────────────────────────────────────────────────────────
# 8. Bomba de entidades XML (billion laughs) → 422, sem expandir/persistir.
# ───────────────────────────────────────────────────────────────────────────
def test_xml_billion_laughs_rejeitado():
    """Auditoria A1: defusedxml barra a expansão de entidades antes de tocar
    disco/memória — 422, nada persistido, worker intacto."""
    with app.app_context():
        admin_id, obra_id = _ambiente()
        c = _client_como(admin_id)
        bomba = (
            b'<?xml version="1.0"?>'
            b'<!DOCTYPE Project [<!ENTITY a "AAAAAAAAAA">'
            b'<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">'
            b'<!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">]>'
            b'<Project xmlns="http://schemas.microsoft.com/project">&c;</Project>'
        )
        resp = _post(c, obra_id, bomba, 'bomba.xml')
        assert resp.status_code == 422
        assert CronogramaImportacao.query.filter_by(obra_id=obra_id).count() == 0


# ───────────────────────────────────────────────────────────────────────────
# 9. MSPDI bem-formado com conteúdo inválido → 422 (falhou), nunca 500/órfão.
# ───────────────────────────────────────────────────────────────────────────
def test_mspdi_conteudo_invalido_vira_422_nao_500():
    """Auditoria M1: XML bem-formado com <ID> não-numérico passa a validação
    de raiz, mas o parse levanta ValueError → precisa virar MppParserError e
    sair 422 com registro 'falhou' (consistente), não 500."""
    with app.app_context():
        admin_id, obra_id = _ambiente()
        c = _client_como(admin_id)
        xml = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<Project xmlns="http://schemas.microsoft.com/project">'
            b'<Name>x</Name><Tasks><Task><UID>1</UID><ID>abc</ID>'
            b'<Name>t</Name></Task></Tasks></Project>'
        )
        resp = _post(c, obra_id, xml, 'ruim.xml')
        assert resp.status_code == 422
        imps = CronogramaImportacao.query.filter_by(obra_id=obra_id).all()
        assert len(imps) == 1
        assert imps[0].status == 'falhou'
