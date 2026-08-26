"""Onda 2 — o tenant para de vazar.

O arreio é `tests/helpers_tenant.py` (`dois_tenants`, `cliente_de`), que existe
desde o p1. A regra dele: nada é compartilhado entre A e B, e a busca é PELA
MARCA — contar dá o mesmo número quando cada tenant tem um registro.
"""
import os
import sys
import uuid
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from helpers_tenant import cliente_de, dois_tenants
from models import TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-onda2-tenant'
    yield


# ---------------------------------------------------------------------------
# Task 4 — o portal
# ---------------------------------------------------------------------------

def _obra_com_token(admin_id):
    from datetime import date, timedelta

    from models import Obra
    obra = Obra.query.filter_by(admin_id=admin_id).first()
    obra.token_cliente = uuid.uuid4().hex
    obra.token_cliente_expira_em = date.today() + timedelta(days=30)
    obra.portal_ativo = True
    db.session.flush()
    return obra


def _fornecedor(admin_id):
    """`PedidoCompra.fornecedor_id` e `.data_compra` são NOT NULL
    (`models.py:5754-5755`) — o brief não citava, mas a violação de
    integridade apareceu no vermelho da 1ª tentativa. Um fornecedor mínimo
    do próprio tenant resolve.
    """
    from models import Fornecedor
    suf = uuid.uuid4().hex[:8]
    f = Fornecedor(
        nome=f'Fornecedor {suf}',
        cnpj=f'{uuid.uuid4().int % 10 ** 14:014d}',
        admin_id=admin_id,
    )
    db.session.add(f)
    db.session.flush()
    return f


def test_compra_interna_aprovada_nao_aparece_no_portal():
    """🔴 `portal_obras_views.py:304` — `compras_resolvidas` não filtra tipo.

    O docstring de `_get_compra_do_portal` (`:511`) descreve ESTE vazamento
    como corrigido e aponta a linha. A correção entrou nas rotas de ação e não
    na listagem.
    """
    from models import PedidoCompra

    with app.app_context():
        a, _b = dois_tenants('onda2_portal', com_fatos=False)
        obra = _obra_com_token(a.admin_id)
        fornecedor = _fornecedor(a.admin_id)
        interna = PedidoCompra(
            admin_id=a.admin_id, obra_id=obra.id,
            fornecedor_id=fornecedor.id,
            data_compra=date.today(),
            numero=f'INTERNA-{a.marca}',
            tipo_compra='normal',
            status_aprovacao_cliente='APROVADO',
            valor_total=1234.00)
        db.session.add(interna)
        db.session.commit()
        token = obra.token_cliente

    resposta = app.test_client().get(f'/portal/obra/{token}')
    corpo = resposta.get_data(as_text=True)
    assert f'INTERNA-{a.marca}' not in corpo, (
        'compra tipo_compra=normal vazou na vitrine do cliente')


def test_comprovante_de_compra_interna_nao_e_servido_a_anonimo():
    """`upload_comprovante:645` e `ver_comprovante:720` resolviam a compra por
    `filter_by(id, obra_id)` — sem admin_id e sem tipo_compra. O segundo faz
    `send_file`.

    As duas rotas vivem no MESMO caminho (`/portal/obra/<token>/compra/
    <compra_id>/comprovante`), diferenciadas pelo método: GET é
    `ver_comprovante`, POST é `upload_comprovante`. Confirmado com
    `grep -n "comprovante" portal_obras_views.py | grep "route"` — não há
    sufixo `/ver` como o brief original citava.

    A compra ganha um `comprovante_pagamento_url` para um arquivo real em
    disco: sem isso, `ver_comprovante` devolveria 404 de qualquer forma (via
    `_arquivo_comprovante`, por falta de arquivo) e o teste passaria mesmo
    sem o filtro de tenant — o falso-verde que a task pede pra vigiar.
    """
    import portal_obras_views as pov
    from models import PedidoCompra

    pov._ensure_upload_folder()
    nome_arquivo = f'onda2_portal_{uuid.uuid4().hex}.txt'
    caminho = os.path.join(pov.UPLOAD_FOLDER, nome_arquivo)
    with open(caminho, 'w') as fh:
        fh.write('comprovante de teste — onda 2')

    try:
        with app.app_context():
            a, _b = dois_tenants('onda2_compr', com_fatos=False)
            obra = _obra_com_token(a.admin_id)
            fornecedor = _fornecedor(a.admin_id)
            interna = PedidoCompra(
                admin_id=a.admin_id, obra_id=obra.id,
                fornecedor_id=fornecedor.id,
                data_compra=date.today(),
                numero=f'INT2-{a.marca}', tipo_compra='normal',
                status_aprovacao_cliente='APROVADO', valor_total=99.00,
                comprovante_pagamento_url=f'/persistent-uploads/comprovantes/{nome_arquivo}')
            db.session.add(interna)
            db.session.commit()
            token, cid = obra.token_cliente, interna.id

        cliente = app.test_client()
        assert cliente.get(f'/portal/obra/{token}/compra/{cid}/comprovante'
                           ).status_code == 404
        assert cliente.post(f'/portal/obra/{token}/compra/{cid}/comprovante',
                            data={}).status_code == 404
    finally:
        if os.path.exists(caminho):
            os.remove(caminho)
