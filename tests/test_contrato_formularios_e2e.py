"""O contrato entre os formulários e a suíte browser, conferido no gate.

Por que este arquivo existe: em 05/08 o formulário de nova proposta trocou
`input[name="cliente_nome"]` por `<select name="cliente_id">` (commit
1394d907, correção do A22 — nome digitado livre duplicava Cliente). O helper
`_criar_proposta` de `test_browser_all_modules.py` continuou preenchendo o
campo extinto e passou 28 dias vermelho sem ninguém ver, porque a única prova
que o veria mora na família `browser`, que o gate deseleciona.

Esta guarda põe a mesma prova no gate: sem browser, em segundos. Ela NÃO
testa comportamento de negócio — testa que os seletores que os testes E2E
digitam existem na página que eles abrem.

⚠️ Se um seletor daqui mudar de propósito, o conserto é atualizar ESTE arquivo
E os testes E2E na mesma rodada. Atualizar só o template é o defeito que este
arquivo existe para tornar barulhento.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app
from helpers_tenant import cliente_de, um_tenant

pytestmark = pytest.mark.integration


ROTAS = ('/propostas/nova', '/almoxarifado/entrada')


@pytest.fixture(scope='module')
def html_por_rota():
    """Um tenant, um GET por rota — reusado por todos os casos parametrizados.

    Escopo de MÓDULO de propósito: `um_tenant` escreve no banco, e criar um
    tenant por caso (são 18) encheria o banco de dev de lixo sem provar nada a
    mais. O contrato é sobre o TEMPLATE, que não varia por tenant.

    `com_fatos=False` porque os fatos operacionais (ponto, alimentação, custo)
    que o arreio semeia por padrão não são lidos por nenhuma destas páginas.
    """
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-contrato-formularios'
    # `um_tenant` escreve pela sessão do SQLAlchemy: precisa de app_context
    # explícito (o conftest só registra blueprints, não empurra contexto).
    with app.app_context():
        admin_id = um_tenant('contrato', com_fatos=False).admin_id
    c = cliente_de(admin_id)
    paginas = {}
    for rota in ROTAS:
        resp = c.get(rota)
        assert resp.status_code == 200, (
            f'{rota} respondeu {resp.status_code}, não 200 — a guarda de '
            f'seletor não chegou a olhar o formulário. Conserte a rota antes '
            f'do contrato.'
        )
        paginas[rota] = resp.get_data(as_text=True)
    return paginas


# Os seletores que os testes E2E digitam, por página. A fonte de cada um é o
# arquivo:linha que o usa — citado para que quem quebrar saiba o que consertar.
CONTRATO_PROPOSTA_NOVA = [
    # test_browser_all_modules.py::_criar_proposta + jornada:305-320
    'name="cliente_id"',
    'data-testid="proposta-cliente-id"',
    'name="numero_proposta"',
    'name="assunto"',
    'name="objeto"',
    'data-testid="proposta-salvar"',
    'id="formNovaProposta"',
    # as três classes de item que _criar_proposta preenche
    'servico-descricao',
    'servico-quantidade',
    'servico-valor-unitario',
]

# O campo que o A22 removeu de propósito. Se ele VOLTAR, o dedup de Cliente
# volta a ser furado — e esta linha é o alarme.
CONTRATO_PROPOSTA_EXTINTO = ['name="cliente_nome"']

CONTRATO_ALMOX_ENTRADA = [
    # test_browser_all_modules.py::_preencher_entrada_almoxarifado:1034-1066
    'id="formEntrada"',
    'id="item_id"',
    'id="tipo_controle"',
    'id="quantidade"',
    'id="valor_unitario"',
    'id="nota_fiscal"',
    'id="fornecedor_id"',
]


@pytest.mark.parametrize('marca', CONTRATO_PROPOSTA_NOVA)
def test_proposta_nova_tem_o_seletor(marca, html_por_rota):
    html = html_por_rota['/propostas/nova']
    assert marca in html, (
        f'/propostas/nova não contém {marca!r}. A suíte browser '
        f'(test_browser_all_modules.py::_criar_proposta) e a jornada E2E '
        f'digitam esse seletor — se o formulário mudou de propósito, atualize '
        f'os dois testes E ESTA lista na mesma rodada.'
    )


@pytest.mark.parametrize('marca', CONTRATO_PROPOSTA_EXTINTO)
def test_proposta_nova_nao_ressuscita_o_campo_extinto(marca, html_por_rota):
    html = html_por_rota['/propostas/nova']
    assert marca not in html, (
        f'/propostas/nova voltou a conter {marca!r}. O A22 (commit 1394d907) '
        f'removeu esse campo porque nome digitado livre criava Cliente '
        f'DUPLICADO com a obra amarrada nele. Se voltou, o dedup furou.'
    )


@pytest.mark.parametrize('marca', CONTRATO_ALMOX_ENTRADA)
def test_almoxarifado_entrada_tem_o_seletor(marca, html_por_rota):
    html = html_por_rota['/almoxarifado/entrada']
    assert marca in html, (
        f'/almoxarifado/entrada não contém {marca!r}. '
        f'test_browser_all_modules.py::_preencher_entrada_almoxarifado digita '
        f'esse seletor — atualize o teste E ESTA lista na mesma rodada.'
    )


# ---------------------------------------------------------------------------
# O helper de flash da suíte browser não pode confundir painel com mensagem
# ---------------------------------------------------------------------------
# `_flash_em_pagina` casava `.alert-info` genérico e devolvia o cartão ESTÁTICO
# de /almoxarifado/entrada ("Tipo de Controle / Unidade / Estoque Atual") em vez
# do flash. Pior: o cartão nasce `display:none`, e innerText de elemento não
# renderizado cai para textContent por especificação — o helper leu texto de um
# elemento invisível e o reportou como mensagem do sistema. Foi isso que deixou
# a falha do A09 sem diagnóstico por uma rodada inteira.
#
# O flash real tem assinatura própria: base.html:992 e base_completo.html:1170
# renderizam TODO flash como `alert alert-<cat> alert-dismissible fade show`
# com `role="alert"`. Conferido: `alert-dismissible` não ocorre em
# templates/almoxarifado/entrada.html nem em templates/propostas/nova_proposta.html.

def test_painel_estatico_da_entrada_nao_se_parece_com_flash(html_por_rota):
    """O cartão informativo de /almoxarifado/entrada não pode casar o seletor
    de flash — se casar, o helper da suíte browser volta a mentir."""
    html = html_por_rota['/almoxarifado/entrada']
    assert 'alert-info' in html, (
        'o cartão estático sumiu de /almoxarifado/entrada — se foi de '
        'propósito, esta guarda perdeu o objeto e deve ser reescrita, não '
        'apagada: o ponto é que painel e flash não se confundam'
    )
    assert 'alert-dismissible' not in html, (
        '/almoxarifado/entrada passou a conter alert-dismissible. O seletor de '
        'flash de test_browser_all_modules.py::_flash_em_pagina se apoia em '
        'alert-dismissible para separar flash de painel — se um painel estático '
        'ganhar essa classe, o helper volta a devolver painel como mensagem.'
    )
