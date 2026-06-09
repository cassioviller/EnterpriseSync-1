"""
Fase F (Passo 14) — endpoint classificar-termo (loop ao vivo).

POST /importacao/fluxo-caixa/classificar-termo: cria a Regra do usuário para o
Termo e RECLASSIFICA o payload em memória (payload-como-estado, HMAC), devolvendo
as seções + fila atualizadas. Sem re-upload.

NÃO seguramos um app_context de módulo: o Flask-Login cacheia o usuário em `g`
(que pertence ao app context), então um contexto compartilhado faria o 2º request
enxergar o usuário do 1º. Cada cli.post cria o seu próprio contexto (g limpo);
operações diretas de DB usam `with app.app_context()` pontualmente.
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
        app.secret_key = "test-secret-classificar-termo"
    if "importacao" not in app.blueprints:
        from importacao_views import importacao_bp
        app.register_blueprint(importacao_bp)
    with app.app_context():
        db.create_all()
    yield


def _novo_admin():
    """Cria um tenant com categorias padrão; devolve o admin_id (committed)."""
    from models import Usuario, TipoUsuario, CategoriaFluxoCaixa
    from werkzeug.security import generate_password_hash
    with app.app_context():
        s = datetime.utcnow().strftime("%f%S")
        admin = Usuario(
            username=f"epterm_{s}", email=f"epterm_{s}@sige.test", nome="EP Termo",
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


def _token(payload, admin_id):
    from importacao_views import _assinar_payload
    with app.app_context():
        return _assinar_payload([payload], admin_id, "fluxo_caixa")


def _add_regra(admin_id, palavras, categoria_nome, campo_alvo="fornecedor",
               prioridade=40, tipo="SAIDA"):
    from models import PalavraChaveCategoria
    cid = _cat_id(admin_id, categoria_nome)
    with app.app_context():
        db.session.add(PalavraChaveCategoria(
            admin_id=admin_id, categoria_fluxo_caixa_id=cid, palavras=palavras,
            campo_alvo=campo_alvo, prioridade=prioridade, tipo=tipo,
            origem="usuario", ativo=True))
        db.session.commit()
    return cid


def test_corrigir_linha_grava_memoria_fixa_a_linha_e_oferece_refinada():
    admin_id = _novo_admin()
    _add_regra(admin_id, "maranhao", "Subempreitada")   # regra do termo (conflitará)
    cat_mat = _cat_id(admin_id, "Materiais de Obra")

    linha = {"tipo": "saida", "descricao": "compra de material hidraulico",
             "fornecedor": "Maranhão Ltda", "plano_contas": "", "obra_id": None,
             "valor": 300.0, "categoria_nome": "Subempreitada"}
    payload = {"entradas": [], "saidas_auto": [linha], "saidas_manual": [],
               "transferencias": []}
    token = _token(payload, admin_id)

    cli = _client_logado(admin_id)
    resp = cli.post("/importacao/fluxo-caixa/corrigir-linha", json={
        "dados_json": token, "descricao": linha["descricao"],
        "fornecedor": linha["fornecedor"], "categoria_id": cat_mat, "tipo": "SAIDA"})

    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    # a linha foi fixada na categoria corrigida (mesmo a regra dizendo Subempreitada)
    alvo = [r for r in body["saidas_auto"] + body["saidas_manual"]
            if r["fornecedor"] == "Maranhão Ltda"][0]
    assert alvo["categoria_nome"] == "Materiais de Obra"
    # oferece a regra refinada: maranhão + (contexto) → Materiais, prioridade vencedora
    sr = body["sugestao_refinada"]
    assert sr is not None
    assert "maranhao" in sr["palavras"]
    assert "material" in sr["gatilho_extra"]
    assert sr["categoria_id"] == cat_mat
    assert sr["prioridade"] < 40


def test_confirmar_regra_refinada_cria_regra_e_reclassifica():
    admin_id = _novo_admin()
    _add_regra(admin_id, "maranhao", "Subempreitada")
    cat_mat = _cat_id(admin_id, "Materiais de Obra")

    linha = {"tipo": "saida", "descricao": "compra de material", "fornecedor": "Maranhão Ltda",
             "plano_contas": "", "obra_id": None, "valor": 300.0,
             "categoria_nome": "Subempreitada"}
    payload = {"entradas": [], "saidas_auto": [linha], "saidas_manual": [],
               "transferencias": []}
    token = _token(payload, admin_id)

    cli = _client_logado(admin_id)
    resp = cli.post("/importacao/fluxo-caixa/confirmar-regra-refinada", json={
        "dados_json": token, "palavras": ["maranhao"], "gatilho_extra": ["material"],
        "campo_alvo": "fornecedor", "campo_extra": "descricao",
        "categoria_id": cat_mat, "prioridade": 39, "tipo": "SAIDA"})

    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    # a regra refinada (maranhão E material) vence a do termo → linha vira Materiais
    alvo = [r for r in body["saidas_auto"] + body["saidas_manual"]
            if r["fornecedor"] == "Maranhão Ltda"][0]
    assert alvo["categoria_nome"] == "Materiais de Obra"

    from models import PalavraChaveCategoria
    with app.app_context():
        refinada = PalavraChaveCategoria.query.filter_by(
            admin_id=admin_id, gatilho_extra="material").first()
        assert refinada is not None
        assert refinada.prioridade == 39


def test_classificar_termo_cria_regra_e_reclassifica_ao_vivo():
    admin_id = _novo_admin()
    saida = {
        "tipo": "saida", "descricao": "compra avulsa", "fornecedor": "Loja Nova Zyx",
        "plano_contas": "", "obra_id": None, "valor": 800.0,
        "categoria_nome": "Outras Saídas", "categoria_fluxo_caixa_id": None,
    }
    payload = {"entradas": [], "saidas_auto": [], "saidas_manual": [saida],
               "transferencias": []}
    token = _token(payload, admin_id)
    cat = _cat_id(admin_id, "Materiais de Obra")

    cli = _client_logado(admin_id)
    resp = cli.post("/importacao/fluxo-caixa/classificar-termo", json={
        "dados_json": token, "termo": "loja nova zyx",
        "categoria_id": cat, "tipo": "SAIDA",
    })

    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body["ok"] is True
    assert len(body["saidas_manual"]) == 0
    assert len(body["saidas_auto"]) == 1
    assert body["saidas_auto"][0]["categoria_nome"] == "Materiais de Obra"
    assert body["dados_json"]

    from models import PalavraChaveCategoria
    with app.app_context():
        regra = PalavraChaveCategoria.query.filter_by(
            admin_id=admin_id, origem="usuario", palavras="loja nova zyx").first()
        assert regra is not None
        assert regra.campo_alvo == "fornecedor"
        assert regra.categoria_fluxo_caixa_id == cat


def test_classificar_termo_rejeita_categoria_de_outro_tenant():
    admin_id = _novo_admin()
    outro_id = _novo_admin()
    cat_outro = _cat_id(outro_id, "Materiais de Obra")

    payload = {"entradas": [], "saidas_auto": [], "saidas_manual": [], "transferencias": []}
    token = _token(payload, admin_id)

    cli = _client_logado(admin_id)
    resp = cli.post("/importacao/fluxo-caixa/classificar-termo", json={
        "dados_json": token, "termo": "abc", "categoria_id": cat_outro, "tipo": "SAIDA",
    })
    assert resp.status_code == 404, resp.get_json()   # categoria não é do tenant logado
