"""
Fase F2 (Passo 17) — CRUD das Regras de Classificação (/catalogos/palavras-chave).

Rotas de mutação (criar/editar/toggle/excluir/sugestões-lote) + detecção de
conflito (mesma palavra+prioridade+campo apontando para categoria diferente → avisa,
não grava). Validação de tenant em todas.
"""
import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db


@pytest.fixture(scope="module", autouse=True)
def _setup():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    if not app.secret_key:
        app.secret_key = "test-secret-pck-crud"
    if "catalogos" not in app.blueprints:
        from views.catalogos_views import catalogos_bp
        app.register_blueprint(catalogos_bp)
    with app.app_context():
        db.create_all()
    yield


def _novo_admin():
    from models import Usuario, TipoUsuario, CategoriaFluxoCaixa
    from werkzeug.security import generate_password_hash
    with app.app_context():
        s = datetime.utcnow().strftime("%f%S")
        admin = Usuario(
            username=f"pckcrud_{s}", email=f"pckcrud_{s}@sige.test", nome="PCK CRUD",
            tipo_usuario=TipoUsuario.ADMIN,
            password_hash=generate_password_hash("Test@1234"),
            versao_sistema="v2", ativo=True,
        )
        db.session.add(admin)
        db.session.flush()
        CategoriaFluxoCaixa.seed_defaults(admin.id)
        db.session.commit()
        return admin.id


def _client_logado(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True
    return c


def _cat_id(admin_id, nome):
    from models import CategoriaFluxoCaixa
    from services.classificador_cadastro import _norm
    with app.app_context():
        return next(c.id for c in CategoriaFluxoCaixa.query.filter_by(admin_id=admin_id).all()
                    if _norm(c.nome) == _norm(nome))


def test_criar_regra_e_detectar_conflito():
    from models import PalavraChaveCategoria
    admin_id = _novo_admin()
    cat_a = _cat_id(admin_id, "Materiais de Obra")
    cat_b = _cat_id(admin_id, "Subempreitada")
    cli = _client_logado(admin_id)

    # cria regra normal
    r = cli.post("/catalogos/palavras-chave/criar", data={
        "palavras": "Leroy", "categoria_id": cat_a, "campo_alvo": "fornecedor",
        "prioridade": 50, "tipo": "SAIDA"}, follow_redirects=False)
    assert r.status_code in (302, 303)
    with app.app_context():
        regras = PalavraChaveCategoria.query.filter_by(admin_id=admin_id).all()
        assert len(regras) == 1
        assert regras[0].palavras == "leroy"   # normalizado

    # conflito: mesma palavra+prioridade+campo, categoria DIFERENTE → não grava
    cli.post("/catalogos/palavras-chave/criar", data={
        "palavras": "leroy", "categoria_id": cat_b, "campo_alvo": "fornecedor",
        "prioridade": 50, "tipo": "SAIDA"})
    with app.app_context():
        assert PalavraChaveCategoria.query.filter_by(admin_id=admin_id).count() == 1


def test_toggle_e_excluir_regra():
    from models import PalavraChaveCategoria
    admin_id = _novo_admin()
    cat = _cat_id(admin_id, "Materiais de Obra")
    cli = _client_logado(admin_id)
    cli.post("/catalogos/palavras-chave/criar", data={
        "palavras": "brita", "categoria_id": cat, "campo_alvo": "qualquer",
        "prioridade": 60, "tipo": "SAIDA"})
    with app.app_context():
        rid = PalavraChaveCategoria.query.filter_by(admin_id=admin_id).first().id

    cli.post(f"/catalogos/palavras-chave/{rid}/toggle")
    with app.app_context():
        assert PalavraChaveCategoria.query.get(rid).ativo is False

    cli.post(f"/catalogos/palavras-chave/{rid}/excluir")
    with app.app_context():
        assert PalavraChaveCategoria.query.get(rid) is None


def test_sugestao_vira_regra_em_lote():
    from models import PalavraChaveCategoria, PalavraChaveSugestao
    admin_id = _novo_admin()
    cat = _cat_id(admin_id, "Materiais de Obra")
    with app.app_context():
        sug = PalavraChaveSugestao(admin_id=admin_id, termo="loja do ze",
                                   ocorrencias=5, soma_valor=2500, tipo="SAIDA")
        db.session.add(sug)
        db.session.commit()
        sug_id = sug.id

    cli = _client_logado(admin_id)
    cli.post("/catalogos/palavras-chave/sugestoes/cadastrar",
             data={f"cat_{sug_id}": cat})

    with app.app_context():
        regra = PalavraChaveCategoria.query.filter_by(
            admin_id=admin_id, palavras="loja do ze").first()
        assert regra is not None
        assert regra.campo_alvo == "fornecedor"
        assert regra.origem == "usuario"
        assert PalavraChaveSugestao.query.get(sug_id).dismissed is True


def test_regra_de_outro_tenant_nao_e_tocada():
    from models import PalavraChaveCategoria
    admin_id = _novo_admin()
    outro_id = _novo_admin()
    cat_outro = _cat_id(outro_id, "Materiais de Obra")
    # cria regra no OUTRO tenant
    cli_outro = _client_logado(outro_id)
    cli_outro.post("/catalogos/palavras-chave/criar", data={
        "palavras": "alheio", "categoria_id": cat_outro, "campo_alvo": "qualquer",
        "prioridade": 50, "tipo": "SAIDA"})
    with app.app_context():
        rid = PalavraChaveCategoria.query.filter_by(admin_id=outro_id).first().id

    # admin_id tenta excluir a regra do outro → bloqueado por ownership
    # (first_or_404 aborta ANTES do delete). NB: com TESTING=True o handler de 404
    # do app propaga um BuildError pré-existente (custos_escritorio.painel_mensal);
    # capturamos — o que importa é que a regra alheia SOBREVIVE.
    cli = _client_logado(admin_id)
    try:
        cli.post(f"/catalogos/palavras-chave/{rid}/excluir")
    except Exception:
        pass
    with app.app_context():
        assert PalavraChaveCategoria.query.get(rid) is not None   # regra alheia intacta
