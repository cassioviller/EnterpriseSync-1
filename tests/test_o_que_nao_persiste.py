"""O que não persiste, e o que persiste pela metade.

A regra destes testes: a afirmação é olhada NO BANCO, depois do teardown da
requisição. `assert` dentro do mesmo contexto vê a SESSÃO, não o banco — e a
diferença entre as duas é exatamente onde estes defeitos moram.

Nenhum teste aqui prova por `inspect.getsource()`.
"""
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import SQLAlchemyError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from helpers_tenant import cliente_de, um_tenant

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-nao-persiste'
    yield


def test_erro_ao_aprovar_compra_nao_conta_a_excecao_ao_anonimo(monkeypatch):
    """🔴 `portal_obras_views.py:648` — `flash(f'Erro ao aprovar compra: {e}')`.

    O portal é acessado por TOKEN, sem autenticação. `str(e)` de erro
    SQLAlchemy carrega o SQL e os parâmetros vinculados, e vai para a tela de
    quem tem o link.

    Nota de gatilho: `compra_id` inexistente NÃO chega ao `except` —
    `_get_compra_do_portal` (`portal_obras_views.py:530`) usa
    `.first_or_404()` e aborta ANTES do `try` (`:557`, antes do `:593`). Um
    teste que dependesse disso passaria verde sem nunca ter exercitado o
    `except` — o mesmo andaime-que-não-podia-falhar que a Task R8 da onda
    anterior tirou de `test_porta_irma.py`. Em vez disso, o erro é INJETADO:
    `processar_compra_aprovada_cliente` (chamada dentro do `try`,
    `portal_obras_views.py:627`) é trocada por uma que estoura
    `SQLAlchemyError` com SQL e parâmetros no texto, de forma
    determinística.

    A prova de que o gatilho funcionou vem do BANCO — `PortalAcessoEvento`
    com `detalhes={'resultado': 'erro'}`, gravado só dentro do `except`
    (`:645-647`) — antes de olhar o corpo da resposta. Sem essa prova
    primeiro, um teste que nunca chegasse ao `except` passaria verde do
    mesmo jeito, só que sem ter provado nada.
    """
    from models import Fornecedor, Obra, PedidoCompra, PortalAcessoEvento
    import compras_views

    def _estoura(*args, **kwargs):
        raise SQLAlchemyError(
            "(psycopg2.errors.UniqueViolation) duplicate key value "
            "violates unique constraint \"gestao_custo_pai_pkey\"\n"
            "[SQL: INSERT INTO gestao_custo_pai (obra_id, valor) "
            "VALUES (%(obra_id)s, %(valor)s)]\n"
            "[parameters: {'obra_id': 5, 'valor': Decimal('1000.00')}]")

    monkeypatch.setattr(compras_views, 'processar_compra_aprovada_cliente',
                        _estoura)

    with app.app_context():
        t = um_tenant('portal-erro', com_fatos=False)
        obra = db.session.get(Obra, t.obra_id)
        # 🔬 Campo conferido: `Obra.token_cliente` (`models.py:397`).
        obra.token_cliente = token = uuid.uuid4().hex
        # `token_cliente_expira_em` fica NULO — `_get_obra_by_token` (:89)
        # trata token expirado como ausência (404) e só NULL segue valendo.

        forn = Fornecedor(nome='Fornecedor Teste', cnpj=uuid.uuid4().hex[:18],
                          admin_id=t.admin_id, ativo=True)
        db.session.add(forn)
        db.session.flush()

        compra = PedidoCompra(
            fornecedor_id=forn.id, data_compra=date(2026, 8, 1),
            obra_id=obra.id, condicao_pagamento='a_vista', parcelas=1,
            valor_total=Decimal('1000.00'), tipo_compra='aprovacao_cliente',
            processada_apos_aprovacao=False, admin_id=t.admin_id,
            status_aprovacao_cliente='AGUARDANDO_APROVACAO_CLIENTE')
        db.session.add(compra)
        db.session.commit()
        compra_id = compra.id
        obra_id = obra.id

    cliente = app.test_client()
    resposta = cliente.post(f'/portal/obra/{token}/compra/{compra_id}/aprovar',
                            data={}, follow_redirects=True)
    corpo = resposta.get_data(as_text=True)

    with app.app_context():
        eventos_de_erro = [
            ev for ev in PortalAcessoEvento.query.filter_by(
                obra_id=obra_id, acao='compra_aprovar',
                alvo_tipo='pedido_compra', alvo_id=compra_id).all()
            if (ev.detalhes or {}).get('resultado') == 'erro'
        ]
        # PRIMEIRO: o gatilho tem que ter funcionado de verdade — senão o
        # que segue passa verde sem ter exercitado o `except`.
        assert len(eventos_de_erro) == 1, (
            'o `except` de aprovar_compra não rodou — o gatilho (erro '
            'injetado em processar_compra_aprovada_cliente) parou de '
            'funcionar, e este teste não prova mais nada')

    for vazamento in ('[SQL:', '[parameters:', 'psycopg2.', 'sqlalchemy.exc',
                      'Traceback (most recent call last)'):
        assert vazamento not in corpo, (
            f'{vazamento!r} vazou para visitante anônimo do portal')
