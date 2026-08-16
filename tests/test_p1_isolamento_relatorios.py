"""p1 Step A — os 9 pontos de `relatorios_funcionais.py` não podem vazar.

Cada teste semeia **dois tenants completos** (Step 0), autentica como o A e
afirma que a marca do B não aparece na resposta. Procurar pela marca, e não
contar linhas, é deliberado: contagem dá o mesmo número quando cada tenant tem
um registro — o vazamento passaria despercebido.

Antes do Step A **todos falham**. É o critério de pronto do pacote.

Quatro funções do mesmo arquivo já eram escopadas antes disto
(`_relatorio_veiculos`, `_dashboard_executivo`, `_progresso_obras`,
`_rentabilidade`, carimbadas `Fase 0 / R3`) — elas ganham teste aqui também,
como regressão: o padrão que o Step A replica é o delas.
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from helpers_tenant import cliente_de, dois_tenants

pytestmark = pytest.mark.integration

DATA = date(2026, 6, 15)
PERIODO = {'dataInicio': '2026-06-01', 'dataFim': '2026-06-30'}


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-p1-isolamento'
    with app.app_context():
        yield


@pytest.fixture(scope='module')
def _par():
    """Um par de tenants para o módulo — semear é caro e nada aqui escreve."""
    with app.app_context():
        return dois_tenants('rel', DATA)


def _gerar(tenant, tipo, **filtros):
    corpo = dict(PERIODO)
    corpo.update(filtros)
    return cliente_de(tenant.admin_id).post(f'/relatorios/gerar/{tipo}',
                                            json=corpo)


def _texto(resposta):
    assert resposta.status_code == 200, resposta.status_code
    return resposta.get_data(as_text=True)


# ---------------------------------------------------------------------------
# Os 6 relatórios do Step A
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('tipo', [
    'funcionarios',
    'ponto',
    'horas-extras',
    'alimentacao',
    'obras',
    'custos-obra',
])
def test_relatorio_nao_mostra_dado_do_outro_tenant(_par, tipo):
    a, b = _par
    corpo = _texto(_gerar(a, tipo))
    assert b.marca not in corpo, (
        f'relatório {tipo!r} devolveu dado do tenant B para o tenant A')


@pytest.mark.parametrize('tipo', [
    'funcionarios',
    'ponto',
    'horas-extras',
    'alimentacao',
    'obras',
    'custos-obra',
])
def test_relatorio_continua_mostrando_o_proprio_dado(_par, tipo):
    """O escopo não pode ser um filtro que zera tudo — o inverso do vazamento
    é o relatório vazio, e ele também é defeito."""
    a, _b = _par
    assert a.marca in _texto(_gerar(a, tipo)), (
        f'relatório {tipo!r} perdeu o dado do próprio tenant')


# ---------------------------------------------------------------------------
# `obra_id` recebido por parâmetro — o escopo não pode furar pela porta lateral
# ---------------------------------------------------------------------------

def test_obra_de_outro_tenant_passada_por_parametro_nao_abre_dado(_par):
    """Filtrar por `obra` é do usuário; a obra ser dele, não.

    A resposta certa é **404** — não 403, e não 200 com lista vazia. 403
    confirmaria que a obra existe em outra empresa, e é o critério que
    `tests/test_gestao_custo_filho_tenant.py:114` já registrou na casa.
    """
    a, b = _par
    for tipo in ('ponto', 'horas-extras', 'alimentacao', 'obras', 'custos-obra'):
        resposta = _gerar(a, tipo, obra=str(b.obra_id))
        assert resposta.status_code == 404, (
            f'{tipo!r} respondeu {resposta.status_code} para obra de outro '
            f'tenant — esperado 404')
        assert b.marca.encode() not in resposta.get_data()


# ---------------------------------------------------------------------------
# As 3 exportações
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('formato', ['csv', 'excel', 'pdf'])
def test_exportacao_nao_leva_dado_do_outro_tenant(_par, formato):
    a, b = _par
    resposta = cliente_de(a.admin_id).post(
        f'/relatorios/exportar/{formato}',
        data={'dataInicio': '2026-06-01', 'dataFim': '2026-06-30'})
    assert resposta.status_code == 200, resposta.status_code
    conteudo = resposta.get_data()
    assert b.marca.encode() not in conteudo, (
        f'exportação {formato!r} levou dado do tenant B')


# ---------------------------------------------------------------------------
# Regressão: os 4 que já eram escopados continuam escopados
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('tipo', [
    'veiculos',
    'dashboard-executivo',
    'progresso-obras',
    'rentabilidade',
])
def test_os_ja_corrigidos_seguem_isolados(_par, tipo):
    a, b = _par
    assert b.marca not in _texto(_gerar(a, tipo))


def test_relatorio_de_veiculos_so_mostra_a_frota_do_proprio_tenant(_par):
    """`veiculos` NÃO estava escopado, ao contrário do que o docstring do topo
    deste arquivo afirmava — `Veiculo.query.all()` servia a frota do banco
    inteiro.

    O teste acima não pegava isso por dois motivos que se somavam:
    `dois_tenants` não semeia veículo (então não havia o que vazar), e a rota
    estourava 500 em `veiculo.status` — atributo que o modelo não tem — assim
    que QUALQUER tenant do banco tivesse um veículo. Como a query era global, o
    resultado dependia de a suíte ter criado veículo antes: verde falso em
    13/08, `AttributeError` no gate de 16/08.

    Aqui a frota é semeada nos dois lados, de propósito, para que o isolamento
    tenha o que provar.
    """
    from models import Veiculo
    from app import db

    a, b = _par
    criados = []
    try:
        for t in (a, b):
            v = Veiculo(placa=f'{t.marca[:7]}', marca=t.marca, modelo='Modelo',
                        ano=2024, tipo='Van', km_atual=1000, ativo=True,
                        admin_id=t.admin_id)
            db.session.add(v)
            criados.append(v)
        db.session.commit()

        corpo = _texto(_gerar(a, 'veiculos'))
        assert a.marca in corpo, 'o tenant perdeu a própria frota'
        assert b.marca not in corpo, 'a frota do tenant B vazou para o A'
    finally:
        for v in criados:
            db.session.delete(v)
        db.session.commit()
