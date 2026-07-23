"""Fotos de RDO × UPLOADS_PATH — regressão da armadilha nº 2 do ESTADO-ATUAL.

Três defeitos, corrigidos juntos em 23/07:

1. `crud_rdo_completo.py` usava `os.path` sem importar `os` — TODA chamada a
   `servir_foto` morria em NameError engolido pelo except genérico (500).
2. `servir_foto` montava o caminho sempre a partir de `getcwd()/static/`,
   enquanto `salvar_foto_rdo` grava sob `$UPLOADS_PATH/rdo/…` quando a
   variável existe. Definir UPLOADS_PATH (pré-requisito do volume
   persistente, item humano nº 3) faria toda foto nova sumir da tela — era
   exatamente o descasamento que impedia montar o volume.
3. `upload_foto_rdo` montava RDOFoto sem `nome_arquivo`/`caminho_arquivo`,
   NOT NULL no banco — IntegrityError em todo upload por essa rota.
"""
import io
import os
import sys
import uuid
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from crud_rdo_completo import _resolver_arquivo_foto
from models import Cliente, Obra, RDO, RDOFoto, TipoUsuario, Usuario

pytestmark = pytest.mark.integration

SENHA = 'Senha@2026'


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-rdo-foto-uploads'
    yield


# ───────────────────────────────────────────────────────────────────────────
# _resolver_arquivo_foto (unidade — sem banco)
# ───────────────────────────────────────────────────────────────────────────

def test_resolve_sob_uploads_path(monkeypatch, tmp_path):
    """Com UPLOADS_PATH definido, o relativo 'uploads/rdo/…' do banco é
    procurado sob $UPLOADS_PATH/rdo/… (o prefixo 'uploads/' não existe lá)."""
    volume = tmp_path / 'volume'
    fisico = volume / 'rdo' / '7' / '9'
    fisico.mkdir(parents=True)
    (fisico / 'x.webp').write_bytes(b'webp')
    monkeypatch.setenv('UPLOADS_PATH', str(volume))

    assert _resolver_arquivo_foto('uploads/rdo/7/9/x.webp') == str(fisico / 'x.webp')


def test_fallback_legado_em_static(monkeypatch, tmp_path):
    """Foto gravada ANTES da variável existir mora em static/uploads/ e tem
    de continuar sendo servida com UPLOADS_PATH apontando para outro lugar."""
    monkeypatch.setenv('UPLOADS_PATH', str(tmp_path / 'volume-sem-a-foto'))
    monkeypatch.chdir(tmp_path)
    legado = tmp_path / 'static' / 'uploads' / 'rdo' / '1' / '2'
    legado.mkdir(parents=True)
    (legado / 'y.webp').write_bytes(b'webp')

    assert _resolver_arquivo_foto('uploads/rdo/1/2/y.webp') == str(legado / 'y.webp')


def test_sem_uploads_path_usa_static(monkeypatch, tmp_path):
    monkeypatch.delenv('UPLOADS_PATH', raising=False)
    monkeypatch.chdir(tmp_path)
    legado = tmp_path / 'static' / 'uploads' / 'rdo' / '3' / '4'
    legado.mkdir(parents=True)
    (legado / 'z.webp').write_bytes(b'webp')

    assert _resolver_arquivo_foto('uploads/rdo/3/4/z.webp') == str(legado / 'z.webp')


def test_arquivo_inexistente_devolve_none(monkeypatch, tmp_path):
    monkeypatch.setenv('UPLOADS_PATH', str(tmp_path / 'vazio'))
    monkeypatch.chdir(tmp_path)
    assert _resolver_arquivo_foto('uploads/rdo/9/9/nada.webp') is None


# ───────────────────────────────────────────────────────────────────────────
# Cenário integrado (banco + rotas)
# ───────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope='module')
def cenario():
    suf = uuid.uuid4().hex[:8]
    with app.app_context():
        admin = Usuario(
            username=f'foto_{suf}', email=f'foto_{suf}@test.local',
            nome=f'Admin Foto {suf}',
            password_hash=generate_password_hash(SENHA),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
        )
        db.session.add(admin)
        db.session.commit()
        cliente = Cliente(nome=f'Cliente {suf}', admin_id=admin.id)
        db.session.add(cliente)
        db.session.commit()
        obra = Obra(nome=f'Obra Foto {suf}', codigo=f'F{suf[:6].upper()}',
                    data_inicio=date(2026, 1, 1), admin_id=admin.id,
                    cliente_id=cliente.id, ativo=True)
        db.session.add(obra)
        db.session.commit()
        rdo = RDO(numero_rdo=f'RF-{suf}'[:20], obra_id=obra.id,
                  admin_id=admin.id, data_relatorio=date(2026, 7, 23),
                  local='Campo', status='Rascunho')
        db.session.add(rdo)
        db.session.commit()
        return {'admin_id': admin.id, 'admin_email': admin.email,
                'rdo_id': rdo.id}


@pytest.fixture(scope='module')
def client(cenario):
    c = app.test_client()
    r = c.post('/login', data={'email': cenario['admin_email'],
                               'password': SENHA}, follow_redirects=False)
    assert r.status_code in (302, 303), f'login falhou (status={r.status_code})'
    return c


def test_servir_foto_le_do_uploads_path(monkeypatch, tmp_path, cenario, client):
    """Foto cujo arquivo físico só existe sob $UPLOADS_PATH tem de ser
    servida — antes da correção a rota nem chegava a olhar lá (e antes do
    `import os` nem chegava a rodar)."""
    admin_id, rdo_id = cenario['admin_id'], cenario['rdo_id']
    volume = tmp_path / 'volume'
    fisico = volume / 'rdo' / str(admin_id) / str(rdo_id)
    fisico.mkdir(parents=True)
    (fisico / 'obra.webp').write_bytes(b'RIFF....WEBP')
    monkeypatch.setenv('UPLOADS_PATH', str(volume))

    relativo = f'uploads/rdo/{admin_id}/{rdo_id}/obra.webp'
    with app.app_context():
        foto = RDOFoto(admin_id=admin_id, rdo_id=rdo_id,
                       nome_arquivo='obra.webp', caminho_arquivo=relativo,
                       arquivo_otimizado=relativo)
        db.session.add(foto)
        db.session.commit()
        foto_id = foto.id

    r = client.get(f'/rdo/foto/{foto_id}/otimizado')
    assert r.status_code == 200, f'esperava 200, veio {r.status_code}'
    assert r.data == b'RIFF....WEBP'


def _png_minimo():
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (32, 32), (200, 100, 50)).save(buf, format='PNG')
    buf.seek(0)
    return buf


def test_upload_preenche_campos_not_null(monkeypatch, tmp_path, cenario, client):
    """O upload por /rdo/<id>/fotos/upload tem de preencher os campos
    legados NOT NULL (`nome_arquivo`, `caminho_arquivo`) — sem eles o
    flush estourava IntegrityError e a rota devolvia 500."""
    import services.rdo_foto_service as svc
    base = tmp_path / 'upload-base'
    base.mkdir()
    monkeypatch.setattr(svc, 'UPLOAD_BASE', str(base))

    r = client.post(
        f"/rdo/{cenario['rdo_id']}/fotos/upload",
        data={'fotos[]': (_png_minimo(), 'canteiro.png')},
        content_type='multipart/form-data',
    )
    assert r.status_code == 201, f'esperava 201, veio {r.status_code}: {r.data[:200]}'
    payload = r.get_json()
    assert payload['total'] == 1, payload

    with app.app_context():
        foto = db.session.get(RDOFoto, payload['fotos'][0]['id'])
        assert foto.nome_arquivo == 'canteiro.png'
        assert foto.caminho_arquivo, 'caminho_arquivo ficou vazio'
