"""Onda 3 — o card e o detalhe da mesma tela param de discordar.

`FinanceiroService.calcular_fluxo_caixa` devolve, no MESMO dicionário, o KPI
(`saidas_previstas`, o card) e a lista `detalhes` (a tabela abaixo dele). Para
um `GestaoCustoPai` PARCIAL o KPI usa o `saldo` — o que ainda falta pagar — e o
laço dos filhos manuais somava cada filho pelo `valor` **cheio**, descartando em
silêncio o `resto` negativo. Dois filhos de R$ 500 com R$ 600 já pagos davam
card = R$ 400 e detalhe = R$ 1.000: os R$ 600 já pagos contados duas vezes na
mesma tela.

O oráculo aqui é a IGUALDADE entre as duas pontas, não um número escolhido a
dedo: é a discordância que o usuário vê. Todo tenant é próprio (`um_tenant`), e
`calcular_fluxo_caixa` recebe o `admin_id` dele — o banco de dev é compartilhado
com trabalho concorrente e nenhuma asserção aqui pode enxergar linha alheia.
"""
import os
import sys
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from models import GestaoCustoFilho, GestaoCustoPai

from financeiro_service import FinanceiroService
from helpers_tenant import um_tenant

pytestmark = pytest.mark.integration

HOJE = date(2026, 6, 15)
JANELA_FIM = HOJE + timedelta(days=30)


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-onda3-financeiro'
    yield


def _pai_parcial(admin_id, obra_id, valores_filhos, saldo):
    """Um Pai com filhos MANUAIS — a forma que dispara o laço de `detalhes`.

    `origem_tabela='lancamento_periodo_manual'` é o que faz `calcular_fluxo_caixa`
    explodir o Pai em uma linha por filho (`financeiro_service.py:742`); sem ele
    o Pai sai como linha única e o defeito não aparece.
    """
    total = sum(Decimal(str(v)) for v in valores_filhos)
    saldo = Decimal(str(saldo))
    pai = GestaoCustoPai(
        tipo_categoria='MATERIAL',
        entidade_nome=f'ONDA3-{uuid.uuid4().hex[:6]}',
        valor_total=total, saldo=saldo, valor_pago=total - saldo,
        status='PARCIAL', data_vencimento=HOJE + timedelta(days=5),
        admin_id=admin_id, obra_id=obra_id)
    db.session.add(pai)
    db.session.flush()
    for i, v in enumerate(valores_filhos):
        db.session.add(GestaoCustoFilho(
            pai_id=pai.id, admin_id=admin_id, obra_id=obra_id,
            descricao=f'lancamento {i}', valor=Decimal(str(v)),
            data_referencia=HOJE + timedelta(days=i),
            origem_tabela='lancamento_periodo_manual'))
    db.session.commit()
    return pai


def _previstas_do_detalhe(fluxo):
    """A soma que o usuário faz com o olho: as saídas ainda NÃO realizadas."""
    return sum(float(d['valor']) for d in fluxo['detalhes']
               if d['tipo'] == 'SAIDA' and not d.get('realizado'))


def test_card_e_detalhe_do_pai_parcial_batem():
    """🔴 `financeiro_service.py:759` — o `resto` negativo era descartado.

    Dois filhos de R$ 500, R$ 600 já pagos: o card usa o saldo (R$ 400) e o
    detalhe listava R$ 500 + R$ 500 = R$ 1.000.
    """
    with app.app_context():
        t = um_tenant('onda3_fin_parcial', com_fatos=False)
        _pai_parcial(t.admin_id, t.obra_id, [500, 500], saldo=400)

        fluxo = FinanceiroService.calcular_fluxo_caixa(
            t.admin_id, HOJE, JANELA_FIM)

        assert fluxo['saidas_previstas'] == pytest.approx(400.0)
        assert _previstas_do_detalhe(fluxo) == pytest.approx(400.0), (
            'o detalhe soma os filhos pelo valor cheio — os R$ 600 ja pagos '
            'aparecem de novo na mesma tela')


def test_rateio_nao_perde_centavo_em_divisao_inexata():
    """O rateio fecha na SOMA, não na divisão.

    Três filhos de R$ 100 com R$ 200 pagos: a fatia de cada um é R$ 33,33 e o
    arredondamento por linha entregaria R$ 99,99 — um centavo a menos que o
    card. O resíduo tem de cair na ÚLTIMA linha do rateio, e não sobrar para a
    linha agregada do `resto`: contar as linhas é o que separa as duas saídas,
    porque a soma fecha nas duas.
    """
    with app.app_context():
        t = um_tenant('onda3_fin_centavo', com_fatos=False)
        pai = _pai_parcial(t.admin_id, t.obra_id, [100, 100, 100], saldo=100)
        marca = pai.entidade_nome

        fluxo = FinanceiroService.calcular_fluxo_caixa(
            t.admin_id, HOJE, JANELA_FIM)

        previstas = [d for d in fluxo['detalhes']
                     if d['tipo'] == 'SAIDA' and not d.get('realizado')
                     and marca in (d['descricao'] or '')]
        assert fluxo['saidas_previstas'] == pytest.approx(100.0)
        assert sum(d['valor'] for d in previstas) == pytest.approx(100.0, abs=0.005)
        assert len(previstas) == 3, (
            'o centavo do arredondamento virou uma linha agregada de R$ 0,01')


def test_pai_com_saldo_maior_que_os_filhos_mantem_a_linha_de_resto():
    """Cão de guarda do caminho que já funcionava: quando o Pai vale MAIS que
    os filhos manuais, a diferença continua saindo como linha agregada — o
    rateio não pode comer o `resto` positivo."""
    with app.app_context():
        t = um_tenant('onda3_fin_resto', com_fatos=False)
        pai = _pai_parcial(t.admin_id, t.obra_id, [300], saldo=1000)
        marca = pai.entidade_nome

        fluxo = FinanceiroService.calcular_fluxo_caixa(
            t.admin_id, HOJE, JANELA_FIM)

        previstas = [d for d in fluxo['detalhes']
                     if d['tipo'] == 'SAIDA' and not d.get('realizado')
                     and marca in (d['descricao'] or '')]
        assert len(previstas) == 2, 'sumiu a linha do resto nao-manual'
        assert fluxo['saidas_previstas'] == pytest.approx(1000.0)
        assert _previstas_do_detalhe(fluxo) == pytest.approx(1000.0)
