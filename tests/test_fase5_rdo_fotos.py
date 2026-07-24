"""Fase 5 — armazenamento das fotos de RDO.

Medido em 2026-07-21 no banco de desenvolvimento:

    pg_total_relation_size('rdo_foto') = 16 GB   (TOAST = 16 GB)
    pg_relation_size('rdo_foto')       = 11 MB
    28.870 fotos, das quais 28.860 JÁ têm arquivo em disco
    du -sh static/uploads              = 13 GB
    UPLOADS_PATH                       = não definido

A base64 é duplicata do que já está em disco. O problema é que o disco é
efêmero (services/rdo_foto_service.py:21-53 cai em
`static/uploads/rdo` quando UPLOADS_PATH não existe) — e o descasamento
gravar-em-volume/servir-de-static foi corrigido em 23/07 (`b6d01a0b`,
`_resolver_arquivo_foto` + tests/test_rdo_foto_uploads_path.py). Esta
task acrescenta o que faltava: `caminho_absoluto` no serviço (com recusa
de path traversal — o resolver de 23/07 não tinha), o uso dele em
`deletar_foto`, e o marcador `rdo_foto.armazenamento` (migration 264)
de que a migração destrutiva da Task 15 depende.
"""
import os
import sys
import uuid
from datetime import date
from io import BytesIO

import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os 54 blueprints antes de qualquer request
from app import app, db
from models import Cliente, Obra, RDO, RDOFoto, TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase5-fotos'
    yield


def _sfx():
    return uuid.uuid4().hex[:8]


def _admin():
    suf = _sfx()
    u = Usuario(
        username=f'f5p_{suf}', email=f'f5p_{suf}@test.local',
        nome=f'Admin Fotos {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id):
    suf = _sfx()
    cli = Cliente(nome=f'CLI-F5P-{suf}', admin_id=admin_id)
    db.session.add(cli)
    db.session.flush()
    o = Obra(nome=f'Obra Fotos {suf}', codigo=f'OP5{suf[:6].upper()}',
             data_inicio=date(2026, 1, 1), admin_id=admin_id,
             cliente_id=cli.id, valor_contrato=50000)
    db.session.add(o)
    db.session.commit()
    return o


def _rdo(obra, admin_id):
    r = RDO(numero_rdo=f'RDO-F5P-{_sfx()}', data_relatorio=date(2026, 6, 22),
            obra_id=obra.id, admin_id=admin_id, comentario_geral='Fotos')
    db.session.add(r)
    db.session.commit()
    return r


def _imagem_falsa(nome='foto.jpg', cor=(200, 30, 30)):
    buf = BytesIO()
    Image.new('RGB', (640, 480), cor).save(buf, format='JPEG')
    buf.seek(0)
    return FileStorage(stream=buf, filename=nome,
                       content_type='image/jpeg')


# ---------------------------------------------------------------------------
# Resolução de caminho
# ---------------------------------------------------------------------------

def test_caminho_absoluto_respeita_uploads_path(tmp_path, monkeypatch):
    """O bug que impede o volume de funcionar.

    `salvar_foto_rdo` grava em `$UPLOADS_PATH/rdo/...` mas devolve o
    caminho relativo `uploads/rdo/...`; `servir_foto`
    (crud_rdo_completo.py:804) montava
    `os.path.join(os.getcwd(), 'static', caminho)` — que ignora
    UPLOADS_PATH e vai procurar no lugar errado.
    """
    from services.rdo_foto_service import caminho_absoluto

    monkeypatch.setenv('UPLOADS_PATH', str(tmp_path))
    esperado = os.path.join(str(tmp_path), 'rdo', '7', '99', 'a.webp')
    assert caminho_absoluto('uploads/rdo/7/99/a.webp') == esperado


def test_caminho_absoluto_sem_uploads_path_usa_static(monkeypatch):
    from services.rdo_foto_service import caminho_absoluto

    monkeypatch.delenv('UPLOADS_PATH', raising=False)
    resultado = caminho_absoluto('uploads/rdo/7/99/a.webp')
    assert resultado.endswith(os.path.join('static', 'uploads', 'rdo', '7',
                                           '99', 'a.webp'))


def test_caminho_absoluto_recusa_travessia_de_diretorio(monkeypatch, tmp_path):
    """`caminho` vem do banco, mas nunca confie: path traversal."""
    from services.rdo_foto_service import caminho_absoluto

    monkeypatch.setenv('UPLOADS_PATH', str(tmp_path))
    assert caminho_absoluto('uploads/../../etc/passwd') is None
    assert caminho_absoluto('/etc/passwd') is None


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def test_upload_pela_rota_crud_grava_os_campos_not_null():
    """crud_rdo_completo.py:718 criava RDOFoto SEM nome_arquivo nem
    caminho_arquivo, que são NOT NULL no banco (verificado em
    information_schema). O INSERT estourava IntegrityError."""
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        rid, aid = rdo.id, admin.id

    cliente = app.test_client()
    with cliente.session_transaction() as sess:
        sess['_user_id'] = str(aid)
        sess['_fresh'] = True

    resposta = cliente.post(
        f'/rdo/{rid}/fotos/upload',
        data={'fotos[]': _imagem_falsa()},
        content_type='multipart/form-data')
    assert resposta.status_code == 201, (
        f'upload devolveu {resposta.status_code}: {resposta.get_data(as_text=True)[:300]}')

    with app.app_context():
        foto = RDOFoto.query.filter_by(rdo_id=rid).first()
        assert foto is not None
        assert foto.nome_arquivo, 'nome_arquivo (NOT NULL) ficou vazio'
        assert foto.caminho_arquivo, 'caminho_arquivo (NOT NULL) ficou vazio'


def test_coluna_armazenamento_existe_com_default_banco():
    with app.app_context():
        assert hasattr(RDOFoto, 'armazenamento')
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        f = RDOFoto(admin_id=admin.id, rdo_id=rdo.id,
                    nome_arquivo='x.webp', caminho_arquivo='uploads/rdo/x.webp')
        db.session.add(f)
        db.session.commit()
        assert f.armazenamento in ('banco', 'disco')


def test_backfill_da_migration_marcou_o_acervo():
    from sqlalchemy import text

    with app.app_context():
        nulos = db.session.execute(text(
            "SELECT count(*) FROM rdo_foto WHERE armazenamento IS NULL")).scalar()
        assert nulos == 0, f'{nulos} fotos ficaram sem marcador de armazenamento'


# ---------------------------------------------------------------------------
# Parar a sangria
# ---------------------------------------------------------------------------

def test_upload_novo_nao_grava_base64():
    """A partir da Fase 5, foto nova vai só para o disco."""
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        rid, aid = rdo.id, admin.id

    cliente = app.test_client()
    with cliente.session_transaction() as sess:
        sess['_user_id'] = str(aid)
        sess['_fresh'] = True
    cliente.post(f'/rdo/{rid}/fotos/upload',
                 data={'fotos[]': _imagem_falsa()},
                 content_type='multipart/form-data')

    with app.app_context():
        foto = RDOFoto.query.filter_by(rdo_id=rid).first()
        assert foto is not None
        assert foto.imagem_original_base64 is None, (
            'upload novo ainda grava base64 — 442 KB por foto no banco')
        assert foto.imagem_otimizada_base64 is None
        assert foto.thumbnail_base64 is None
        assert foto.armazenamento == 'disco'
        assert foto.arquivo_otimizado


def test_salvar_foto_rdo_nao_devolve_mais_base64(tmp_path, monkeypatch):
    from services.rdo_foto_service import salvar_foto_rdo

    monkeypatch.setenv('UPLOADS_PATH', str(tmp_path))
    with app.app_context():
        resultado = salvar_foto_rdo(_imagem_falsa(), 1, 1)
    assert 'imagem_original_base64' not in resultado
    assert 'imagem_otimizada_base64' not in resultado
    assert 'thumbnail_base64' not in resultado
    assert resultado['arquivo_otimizado'].startswith('uploads/rdo/1/1/')


def test_consulta_de_rdo_nao_carrega_base64_por_padrao():
    """models.py:1104 era lazy='selectin': TODA consulta de RDO puxava as
    três colunas TEXT de todas as fotos — inclusive a listagem paginada
    de crud_rdo_completo.py:80."""
    from sqlalchemy import inspect as sa_inspect

    with app.app_context():
        mapper = sa_inspect(RDOFoto)
        for coluna in ('imagem_original_base64', 'imagem_otimizada_base64',
                       'thumbnail_base64'):
            assert mapper.attrs[coluna].deferred is True, (
                f'{coluna} não está deferred — continua vindo em toda query')

        relacao = sa_inspect(RDO).relationships['fotos']
        assert relacao.lazy != 'selectin', (
            'RDO.fotos ainda é selectin: cada listagem de RDO puxa o TOAST '
            'inteiro das fotos')


def test_url_da_foto_e_servida_do_disco():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        rid, aid = rdo.id, admin.id

    cliente = app.test_client()
    with cliente.session_transaction() as sess:
        sess['_user_id'] = str(aid)
        sess['_fresh'] = True
    cliente.post(f'/rdo/{rid}/fotos/upload',
                 data={'fotos[]': _imagem_falsa()},
                 content_type='multipart/form-data')

    with app.app_context():
        foto_id = RDOFoto.query.filter_by(rdo_id=rid).first().id

    resposta = cliente.get(f'/rdo/foto/{foto_id}/thumbnail')
    assert resposta.status_code == 200, (
        f'servir_foto devolveu {resposta.status_code} — a foto não está '
        f'sendo encontrada no disco')
    assert resposta.headers['Content-Type'].startswith('image/')


def test_tela_do_rdo_usa_url_e_nao_data_uri():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        rid, aid = rdo.id, admin.id

    cliente = app.test_client()
    with cliente.session_transaction() as sess:
        sess['_user_id'] = str(aid)
        sess['_fresh'] = True
    cliente.post(f'/rdo/{rid}/fotos/upload',
                 data={'fotos[]': _imagem_falsa()},
                 content_type='multipart/form-data')

    corpo = cliente.get(f'/rdo/{rid}').get_data(as_text=True)
    assert '/rdo/foto/' in corpo, 'a tela não usa a URL de servir_foto'
    assert 'data:image/webp;base64' not in corpo, (
        'a tela ainda embute a imagem inteira no HTML')
