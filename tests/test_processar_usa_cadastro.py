"""
Fase D (Passo 8) — ImportacaoFluxoCaixa.processar consome o cadastro.

Prova de integração: com as Regras do tenant semeadas no banco, processar()
classifica cada Lançamento do Excel real IGUAL ao classificador legado (nos
mesmos campos e mesmo tem_obra que processar() usou) e redefine auto vs manual
pelo resultado (fallback genérico → fila manual). Ver §3 do spec / ADR-0002.

Usa flush + rollback — não polui o banco.
"""
import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db

XLSX = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "1. FLUXO DE CAIXA_Veks Engenharia.xlsx",
)
FALLBACK = {"Outras Saídas", "Outros Recebimentos"}


@pytest.fixture(scope="module", autouse=True)
def _app_ctx():
    app.config["TESTING"] = True
    with app.app_context():
        db.create_all()
        yield


@pytest.fixture
def admin_semeado():
    """Tenant com categorias padrão + Regras do sistema semeadas; desfaz no fim."""
    from models import Usuario, TipoUsuario, CategoriaFluxoCaixa
    from werkzeug.security import generate_password_hash
    from services.seed_palavras_chave import seed_para_admin

    s = datetime.utcnow().strftime("%f%S")
    admin = Usuario(
        username=f"procpck_{s}", email=f"procpck_{s}@sige.test", nome="Proc PCK",
        tipo_usuario=TipoUsuario.ADMIN,
        password_hash=generate_password_hash("Test@1234"),
        versao_sistema="v2", ativo=True,
    )
    db.session.add(admin)
    db.session.flush()
    CategoriaFluxoCaixa.seed_defaults(admin.id)
    db.session.flush()
    seed_para_admin(admin.id)
    db.session.flush()

    yield admin.id

    db.session.rollback()


def test_processar_classifica_via_cadastro_igual_ao_legado(admin_semeado):
    if not os.path.exists(XLSX):
        pytest.skip(f"Excel não encontrado: {XLSX}")

    from services.importacao_excel import (
        ImportacaoFluxoCaixa, _classificar_categoria_nomeada,
    )

    res = ImportacaoFluxoCaixa().processar(XLSX, admin_semeado)

    entradas = res["entradas"]
    saidas_auto = res["saidas_auto"]
    saidas_manual = res["saidas_manual"]
    assert entradas or saidas_auto or saidas_manual, "preview veio vazio"

    # Entradas: motor novo == legado nos mesmos campos
    for r in entradas:
        legado = _classificar_categoria_nomeada(
            "ENTRADA", r.get("plano_contas"), r.get("descricao"), r.get("cliente"))
        assert r["categoria_nome"] == legado

    # Saídas: idem, com o tem_obra que processar() de fato usou (bool(obra_id))
    for r in saidas_auto + saidas_manual:
        legado = _classificar_categoria_nomeada(
            "SAIDA", r.get("plano_contas"), r.get("descricao"), r.get("fornecedor"),
            tem_obra=bool(r.get("obra_id")))
        assert r["categoria_nome"] == legado


def test_processar_redefine_auto_vs_manual_pelo_fallback(admin_semeado):
    if not os.path.exists(XLSX):
        pytest.skip(f"Excel não encontrado: {XLSX}")

    from services.importacao_excel import ImportacaoFluxoCaixa

    res = ImportacaoFluxoCaixa().processar(XLSX, admin_semeado)

    # Toda saída AUTO tem categoria específica; toda MANUAL caiu no fallback (§3).
    for r in res["saidas_auto"]:
        assert r["categoria_nome"] not in FALLBACK
    for r in res["saidas_manual"]:
        assert r["categoria_nome"] in FALLBACK


def test_processar_deriva_macro_da_categoria_nomeada(admin_semeado):
    if not os.path.exists(XLSX):
        pytest.skip(f"Excel não encontrado: {XLSX}")

    from services.importacao_excel import ImportacaoFluxoCaixa
    from services.classificador_cadastro import derivar_macro

    res = ImportacaoFluxoCaixa().processar(XLSX, admin_semeado)

    for r in res["saidas_auto"] + res["saidas_manual"] + res["entradas"]:
        assert r["tipo_categoria"] == derivar_macro(r["categoria_nome"])


def test_processar_devolve_sugestoes_dos_pendentes(admin_semeado):
    if not os.path.exists(XLSX):
        pytest.skip(f"Excel não encontrado: {XLSX}")

    from services.importacao_excel import ImportacaoFluxoCaixa

    res = ImportacaoFluxoCaixa().processar(XLSX, admin_semeado)
    sugestoes = res["sugestoes"]
    assert isinstance(sugestoes, list)
    # havendo pendentes, a fila por Termo não vem vazia
    if res["saidas_manual"]:
        assert sugestoes
    for s in sugestoes:
        assert {"termo", "ocorrencias", "soma_valor", "exemplo", "tipo"} <= set(s)
        assert s["ocorrencias"] >= 1
    # ordenadas por impacto (decrescente)
    impactos = [s["ocorrencias"] * s["soma_valor"] for s in sugestoes]
    assert impactos == sorted(impactos, reverse=True)


def test_processar_aplica_memoria_exata_de_correcao_previa(admin_semeado):
    if not os.path.exists(XLSX):
        pytest.skip(f"Excel não encontrado: {XLSX}")

    from services.importacao_excel import ImportacaoFluxoCaixa
    from services.seed_palavras_chave import registrar_correcao
    from services.classificador_cadastro import Lancamento, _norm
    from models import CategoriaFluxoCaixa

    svc = ImportacaoFluxoCaixa()
    res1 = svc.processar(XLSX, admin_semeado)
    if not res1["saidas_manual"]:
        pytest.skip("sem pendentes para exercitar Memória Exata")

    alvo = res1["saidas_manual"][0]
    cat = next(c.id for c in CategoriaFluxoCaixa.query.filter_by(admin_id=admin_semeado).all()
               if _norm(c.nome) == _norm("Materiais de Obra"))
    registrar_correcao(admin_semeado, Lancamento(
        descricao=alvo["descricao"], fornecedor=alvo["fornecedor"], tipo="SAIDA"),
        categoria_id=cat)

    res2 = svc.processar(XLSX, admin_semeado)
    chave = (alvo["descricao"], alvo["fornecedor"])
    ainda_pendente = {(r["descricao"], r["fornecedor"]) for r in res2["saidas_manual"]}
    assert chave not in ainda_pendente   # Memória Exata reclassificou; saiu da fila
