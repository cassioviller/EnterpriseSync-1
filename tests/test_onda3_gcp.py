"""Onda 3 — o pai compartilhado do GestaoCusto não morre pelos filhos alheios.

O arreio de tenant é `tests/helpers_tenant.py`. Todas as contagens são
escopadas por `admin_id` porque o banco de teste é compartilhado com outro
trabalho concorrente — contar global daria falso positivo/negativo.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from helpers_tenant import cliente_de, um_tenant  # noqa: F401

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-onda3-gcp'
    yield


# ---------------------------------------------------------------------------
# Task 4 — o pai compartilhado do reembolso
# ---------------------------------------------------------------------------

def test_excluir_um_reembolso_nao_apaga_os_dos_colegas():
    """🔴 `reembolso_views.py:330` apagava o GestaoCustoPai COMPARTILHADO.

    O cascade `all, delete-orphan` (`models.py:7203`) levava junto os filhos
    de todos os outros reembolsos do mesmo funcionário.
    """
    from models import GestaoCustoFilho, ReembolsoFuncionario

    with app.app_context():
        t = um_tenant('onda3_reemb', com_fatos=False)
        admin_id, func_id, obra_id = t.admin_id, t.funcionario_id, t.obra_id

    cliente = cliente_de(admin_id)
    for i, valor in enumerate(('100,00', '250,00'), start=1):
        resposta = cliente.post('/reembolsos/novo', data={
            'funcionario_id': str(func_id), 'obra_id': str(obra_id),
            'categoria': 'transporte', 'descricao': f'corrida {i}',
            'valor': valor, 'data_despesa': '2026-08-25',
        }, follow_redirects=True)
        assert resposta.status_code == 200

    with app.app_context():
        reembolsos = ReembolsoFuncionario.query.filter_by(
            admin_id=admin_id, funcionario_id=func_id).all()
        assert len(reembolsos) == 2, 'o fixture precisa de dois reembolsos'
        primeiro, segundo = reembolsos[0].id, reembolsos[1].id
        filhos_antes = GestaoCustoFilho.query.filter_by(
            admin_id=admin_id).count()
        assert filhos_antes == 2, 'pré-condição: um filho por reembolso'

    cliente.post(f'/reembolsos/{primeiro}/excluir', follow_redirects=True)

    with app.app_context():
        assert ReembolsoFuncionario.query.get(segundo) is not None, (
            'o reembolso do colega foi apagado junto')
        filhos_depois = GestaoCustoFilho.query.filter_by(
            admin_id=admin_id).count()
        assert filhos_depois == filhos_antes - 1, (
            f'apagou {filhos_antes - filhos_depois} filhos; devia apagar 1')

        # O sobrevivente ainda tem seu filho e seu pai, com o total coerente.
        from models import GestaoCustoPai
        segundo_reembolso = ReembolsoFuncionario.query.get(segundo)
        gcp = GestaoCustoPai.query.filter_by(
            id=segundo_reembolso.origem_id, admin_id=admin_id).first()
        assert gcp is not None, 'o pai compartilhado foi apagado'
        filhos_do_pai = GestaoCustoFilho.query.filter_by(
            pai_id=gcp.id, admin_id=admin_id).all()
        assert len(filhos_do_pai) == 1
        assert filhos_do_pai[0].origem_id == segundo, (
            'o filho sobrevivente não é o do reembolso do colega')


def test_editar_reembolso_nao_sobrescreve_o_total_do_pai_com_o_proprio_valor():
    """🔴 `reembolso_views.py:293` fazia `gcp.valor_total = valor` com o valor
    de UM reembolso: os irmãos evaporavam do total do pai compartilhado.
    """
    from models import GestaoCustoFilho, GestaoCustoPai, ReembolsoFuncionario
    from decimal import Decimal

    with app.app_context():
        t = um_tenant('onda3_reemb_ed', com_fatos=False)
        admin_id, func_id, obra_id = t.admin_id, t.funcionario_id, t.obra_id

    cliente = cliente_de(admin_id)
    for i, valor in enumerate(('100,00', '250,00'), start=1):
        resposta = cliente.post('/reembolsos/novo', data={
            'funcionario_id': str(func_id), 'obra_id': str(obra_id),
            'categoria': 'transporte', 'descricao': f'corrida {i}',
            'valor': valor, 'data_despesa': '2026-08-25',
        }, follow_redirects=True)
        assert resposta.status_code == 200

    with app.app_context():
        reembolsos = ReembolsoFuncionario.query.filter_by(
            admin_id=admin_id, funcionario_id=func_id).order_by(
            ReembolsoFuncionario.id).all()
        assert len(reembolsos) == 2, 'o fixture precisa de dois reembolsos'
        primeiro = reembolsos[0].id

    resposta = cliente.post(f'/reembolsos/{primeiro}/editar', data={
        'valor': '175,00', 'descricao': 'corrida 1 revisada',
        'categoria': 'transporte', 'data_despesa': '2026-08-25',
        'obra_id': str(obra_id),
    }, follow_redirects=True)
    assert resposta.status_code == 200

    with app.app_context():
        primeiro_reembolso = ReembolsoFuncionario.query.get(primeiro)
        gcp = GestaoCustoPai.query.filter_by(
            id=primeiro_reembolso.origem_id, admin_id=admin_id).first()
        assert gcp is not None
        soma_filhos = sum(
            (f.valor for f in GestaoCustoFilho.query.filter_by(
                pai_id=gcp.id, admin_id=admin_id).all()),
            Decimal('0'))
        assert Decimal(str(gcp.valor_total)) == soma_filhos, (
            f'gcp.valor_total ({gcp.valor_total}) diverge da soma dos filhos '
            f'({soma_filhos}) — o irmão evaporou do total')
        assert soma_filhos == Decimal('175.00') + Decimal('250.00')
