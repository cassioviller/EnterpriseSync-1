"""
Fase A (TDD) — modelos do Cadastro de Regras de Classificação de Fluxo de Caixa.

Spec: docs/superpowers/specs/2026-06-09-cadastro-palavras-chave-design.md §4
Linguagem (CONTEXT.md): Regra de Classificação, Gatilho, Prioridade, Sugestão,
Correção, Memória Exata.

Testa comportamento via interface pública (ORM): a Regra persiste, é consultável
por tenant e aplica os defaults de domínio. Não testa shape interno.

Os testes usam flush + rollback — não commitam, então não poluem o banco.
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
        db.create_all()  # materializa as tabelas novas a partir dos models
        yield


@pytest.fixture
def tenant():
    """Cria admin + uma CategoriaFluxoCaixa de destino; desfaz tudo no fim."""
    from models import Usuario, TipoUsuario, CategoriaFluxoCaixa
    from werkzeug.security import generate_password_hash

    s = datetime.utcnow().strftime("%f%S")
    admin = Usuario(
        username=f"pck_{s}",
        email=f"pck_{s}@sige.test",
        nome="Teste PCK",
        tipo_usuario=TipoUsuario.ADMIN,
        password_hash=generate_password_hash("Test@1234"),
        versao_sistema="v2",
        ativo=True,
    )
    db.session.add(admin)
    db.session.flush()

    cat = CategoriaFluxoCaixa(
        nome=f"Subempreitada {s}", tipo="SAIDA", admin_id=admin.id, ativo=True
    )
    db.session.add(cat)
    db.session.flush()

    yield admin.id, cat.id

    db.session.rollback()


def test_regra_de_classificacao_persiste_por_tenant(tenant):
    """Uma Regra de Classificação criada com gatilho + categoria é consultável
    pelo tenant e nasce com os defaults de domínio (prioridade 50, ativa,
    origem do usuário, busca em qualquer campo, indiferente a obra)."""
    from models import PalavraChaveCategoria

    admin_id, cat_id = tenant
    regra = PalavraChaveCategoria(
        admin_id=admin_id,
        categoria_fluxo_caixa_id=cat_id,
        palavras="maranhão",
        tipo="SAIDA",
    )
    db.session.add(regra)
    db.session.flush()

    achada = PalavraChaveCategoria.query.filter_by(admin_id=admin_id).one()
    assert achada.palavras == "maranhão"
    assert achada.categoria_fluxo_caixa_id == cat_id
    # defaults de domínio
    assert achada.prioridade == 50
    assert achada.ativo is True
    assert achada.origem == "usuario"
    assert achada.campo_alvo == "qualquer"
    assert achada.condicao_obra == "indiferente"


def test_sugestao_persiste_e_nasce_nao_descartada(tenant):
    """Uma Sugestão (termo recorrente da fila) persiste com seus agregados e
    nasce não-descartada (dismissed=False)."""
    from decimal import Decimal
    from models import PalavraChaveSugestao

    admin_id, _ = tenant
    sug = PalavraChaveSugestao(
        admin_id=admin_id,
        termo="maranhão",
        ocorrencias=18,
        soma_valor=Decimal("47300.00"),
        exemplo="Maranhão - empreita alvenaria bloco B",
        tipo="SAIDA",
    )
    db.session.add(sug)
    db.session.flush()

    achada = PalavraChaveSugestao.query.filter_by(admin_id=admin_id).one()
    assert achada.termo == "maranhão"
    assert achada.ocorrencias == 18
    assert achada.soma_valor == Decimal("47300.00")
    assert achada.dismissed is False


def test_correcao_persiste(tenant):
    """Uma Correção (decisão de linha) persiste com o texto normalizado, a
    categoria escolhida e o termo de origem."""
    from models import CorrecaoClassificacao

    admin_id, cat_id = tenant
    cor = CorrecaoClassificacao(
        admin_id=admin_id,
        texto_norm="compra de material na loja maranhao",
        categoria_fluxo_caixa_id=cat_id,
        termo_origem="maranhão",
        tipo="SAIDA",
    )
    db.session.add(cor)
    db.session.flush()

    achada = CorrecaoClassificacao.query.filter_by(admin_id=admin_id).one()
    assert achada.texto_norm == "compra de material na loja maranhao"
    assert achada.categoria_fluxo_caixa_id == cat_id
    assert achada.termo_origem == "maranhão"


def test_memoria_exata_e_unica_por_tenant_e_texto(tenant):
    """A Memória Exata é chaveada por (tenant, texto_norm): duas Correções com
    o mesmo texto para o mesmo tenant não podem coexistir."""
    from sqlalchemy.exc import IntegrityError
    from models import CorrecaoClassificacao

    admin_id, cat_id = tenant
    txt = "uber para a obra do centro"
    db.session.add(CorrecaoClassificacao(
        admin_id=admin_id, texto_norm=txt,
        categoria_fluxo_caixa_id=cat_id, tipo="SAIDA"))
    db.session.flush()

    db.session.add(CorrecaoClassificacao(
        admin_id=admin_id, texto_norm=txt,
        categoria_fluxo_caixa_id=cat_id, tipo="SAIDA"))
    with pytest.raises(IntegrityError):
        db.session.flush()
