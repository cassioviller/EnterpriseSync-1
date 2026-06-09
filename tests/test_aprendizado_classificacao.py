"""
Fase E (Passo 11) — Correção + Memória Exata (persistência por tenant).

registrar_correcao(admin_id, lanc, categoria_id): grava CorrecaoClassificacao
(upsert por admin_id+texto_norm). carregar_memoria_exata(admin_id): devolve o
dict {texto_norm: (cat_id, cat_nome)} que o classificador consome (§7.3).

Usa flush + rollback — não polui o banco.
"""
import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db


@pytest.fixture(scope="module", autouse=True)
def _app_ctx():
    app.config["TESTING"] = True
    with app.app_context():
        db.create_all()
        yield


@pytest.fixture
def admin_com_categorias():
    from models import Usuario, TipoUsuario, CategoriaFluxoCaixa
    from werkzeug.security import generate_password_hash

    s = datetime.utcnow().strftime("%f%S")
    admin = Usuario(
        username=f"corrpck_{s}", email=f"corrpck_{s}@sige.test", nome="Corr PCK",
        tipo_usuario=TipoUsuario.ADMIN,
        password_hash=generate_password_hash("Test@1234"),
        versao_sistema="v2", ativo=True,
    )
    db.session.add(admin)
    db.session.flush()
    CategoriaFluxoCaixa.seed_defaults(admin.id)
    db.session.flush()
    yield admin.id
    db.session.rollback()


def _cat_id(admin_id, nome):
    from models import CategoriaFluxoCaixa
    from services.classificador_cadastro import _norm
    return next(c.id for c in CategoriaFluxoCaixa.query.filter_by(admin_id=admin_id).all()
               if _norm(c.nome) == _norm(nome))


def test_correcao_vira_memoria_exata_consumivel_pelo_classificador(admin_com_categorias):
    from services.seed_palavras_chave import registrar_correcao, carregar_memoria_exata
    from services.classificador_cadastro import (
        classificar, Lancamento, Contexto, texto_norm,
    )
    admin_id = admin_com_categorias
    cat = _cat_id(admin_id, "Materiais de Obra")

    lanc = Lancamento(descricao="reembolso pf conferir", fornecedor="Joao Silva",
                      tipo="SAIDA")
    registrar_correcao(admin_id, lanc, categoria_id=cat)

    # A Memória Exata carregada reaplica a categoria em texto idêntico
    mem = carregar_memoria_exata(admin_id)
    assert texto_norm(lanc) in mem
    ctx = Contexto(regras=[], memoria_exata=mem)
    v = classificar(lanc, ctx)
    assert v.categoria_id == cat
    assert v.origem_decisao == "memoria_exata"


def test_registrar_correcao_e_upsert_nao_duplica(admin_com_categorias):
    from services.seed_palavras_chave import registrar_correcao
    from services.classificador_cadastro import Lancamento
    from models import CorrecaoClassificacao
    admin_id = admin_com_categorias
    cat_a = _cat_id(admin_id, "Materiais de Obra")
    cat_b = _cat_id(admin_id, "Subempreitada")

    lanc = Lancamento(descricao="pagamento semana", fornecedor="Equipe X", tipo="SAIDA")
    registrar_correcao(admin_id, lanc, categoria_id=cat_a)
    registrar_correcao(admin_id, lanc, categoria_id=cat_b)   # mesma chave → atualiza

    linhas = CorrecaoClassificacao.query.filter_by(admin_id=admin_id).all()
    assert len(linhas) == 1                       # upsert, não duplicou
    assert linhas[0].categoria_fluxo_caixa_id == cat_b   # ficou a última
