"""A24a e E12a — números de encargo honestos, e rota que não mente.

**TESTE A (B2.14).** `salvar_folha_processada` gravava o INSS patronal como
`encargos_patronais * 0.7`, um fator fixo que só é exato quando o FGTS vale
8% — e a alíquota de FGTS é configurável por tenant. Com 8%, `0.20/0.28 =
0.714285…`, não `0.7`: **28 centavos a menos por R$ 840 de encargo**, e a linha
gravada passa a violar o próprio invariante `fgts + inss_patronal =
custo_total_empresa − salario_bruto` DENTRO dela mesma.

🔬 **Por que um guarda textual não pegaria, nem se existisse.** No molde dos
pacotes, `assert "Decimal('0.20')" in open('services/folha_service.py').read()`
**passa verde hoje**: a constante certa está mesmo em `:981`. O erro nasce 160
linhas abaixo, na aritmética que reconstrói o valor a partir do total.
**Texto de arquivo não sabe multiplicar.**

O terceiro passo é o que separa "consertaram a aritmética" de "trocaram um número
mágico por outro": com FGTS a 8,5%, qualquer fator fixo erra.
"""
import os
import sys
from datetime import date
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import FolhaProcessada

from helpers_tenant import um_tenant

pytestmark = pytest.mark.integration

ANO, MES = 2026, 3


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    if not app.secret_key:
        app.secret_key = 'test-encargos'
    yield


def _dados(salario_bruto, fgts, encargos_patronais):
    """`dados_folha` na mesma forma que `processar_folha_funcionario` devolve
    (`services/folha_service.py:1068-1094`) — floats, não Decimal."""
    return {
        'salario_base': salario_bruto,
        'salario_bruto': salario_bruto,
        'total_proventos': salario_bruto,
        'total_descontos': 0.0,
        'salario_liquido': salario_bruto,
        'valor_he_50': 0.0,
        'valor_he_100': 0.0,
        'valor_dsr': 0.0,
        'fgts': fgts,
        'encargos_patronais': encargos_patronais,
        'custo_total_empresa': salario_bruto + encargos_patronais,
        'inss': 0.0,
        'irrf': 0.0,
        'desconto_faltas': 0.0,
        'desconto_atrasos': 0.0,
        'horas_trabalhadas': 220.0,
        'horas_extras_50': 0.0,
        'horas_extras_100': 0.0,
        'horas_falta': 0.0,
    }


def _linha(t):
    db.session.expire_all()
    return FolhaProcessada.query.filter_by(
        funcionario_id=t.funcionario_id, obra_id=t.obra_id,
        ano=ANO, mes=MES).first()


def _invariante(linha):
    """`fgts + inss_patronal` tem de fechar com `custo_total − salario_bruto`.

    É o detector exato: nenhum fator fixo satisfaz isso para toda alíquota de
    FGTS, e a violação é interna à linha — não depende de comparar com nada.
    """
    return (Decimal(linha.encargos_fgts) + Decimal(linha.encargos_inss_patronal),
            Decimal(linha.custo_total_empresa) - Decimal(linha.salario_bruto))


def test_inss_patronal_gravado_por_subtracao_e_nao_por_fator():
    """Os três passos do recorte, na ordem: INSERT, UPDATE e alíquota não-padrão.

    Salário 3.000, FGTS 240 (8%), encargos 840 → INSS patronal = **600,00**.
    Com o fator 0.7 gravava 588,00, e a linha dizia 240 + 588 = 828 quando
    `custo_total − salario_bruto` = 840.
    """
    from services.folha_service import salvar_folha_processada

    with app.app_context():
        t = um_tenant('encargo', data_ref=date(ANO, MES, 15), com_fatos=False)

        # ── Passo 1: ramo INSERT ──
        assert salvar_folha_processada(
            t.funcionario_id, t.obra_id, ANO, MES,
            _dados(3000.00, 240.00, 840.00), t.admin_id) is True

        linha = _linha(t)
        assert linha is not None, 'a folha não foi gravada'
        assert Decimal(linha.encargos_inss_patronal) == Decimal('600.00'), (
            f'INSERT gravou {linha.encargos_inss_patronal} — 588.00 é o fator '
            f'0.7 aplicado sobre os 840 de encargo total')
        assert Decimal(linha.encargos_fgts) == Decimal('240.00')
        soma, esperado = _invariante(linha)
        assert soma == esperado == Decimal('840.00'), (
            f'a linha viola o próprio invariante: fgts+inss={soma}, '
            f'custo_total-salario={esperado}')

        # ── Passo 2: ramo UPDATE, com os mesmos números ──
        assert salvar_folha_processada(
            t.funcionario_id, t.obra_id, ANO, MES,
            _dados(3000.00, 240.00, 840.00), t.admin_id) is True

        linha = _linha(t)
        assert Decimal(linha.encargos_inss_patronal) == Decimal('600.00'), (
            f'UPDATE gravou {linha.encargos_inss_patronal}, diferente do '
            f'INSERT — correção pela metade')
        soma, esperado = _invariante(linha)
        assert soma == esperado == Decimal('840.00')

        # ── Passo 3: FGTS a 8,5%, que nenhum fator fixo acerta ──
        assert salvar_folha_processada(
            t.funcionario_id, t.obra_id, ANO, MES,
            _dados(3000.00, 255.00, 855.00), t.admin_id) is True

        linha = _linha(t)
        assert Decimal(linha.encargos_inss_patronal) == Decimal('600.00'), (
            f'com FGTS a 8,5% gravou {linha.encargos_inss_patronal} — um fator '
            f'fixo de 20/28 daria 610.71, e é isto que separa "consertaram a '
            f'aritmética" de "trocaram um número mágico por outro"')
        soma, esperado = _invariante(linha)
        assert soma == esperado == Decimal('855.00')


def test_a_chave_inss_patronal_chega_ao_consumidor():
    """A fonte do defeito desaparece, não só o sintoma.

    `processar_folha_funcionario` já calculava `inss_patronal` (`:987`) e o
    jogava fora ao montar o dict de retorno. Sem essa chave, o consumidor não
    tinha escolha senão reconstituir a parcela por aritmética inversa — que foi
    exatamente o que produziu o `* 0.7`.

    É **acréscimo, nunca renomeação**: `folha_pagamento_views.py:172-189` lê o
    dict chave a chave por nome e quebraria se `fgts` ou `encargos_patronais`
    mudassem.
    """
    import inspect

    from services import folha_service

    fonte = inspect.getsource(folha_service.processar_folha_funcionario)
    assert "'inss_patronal': encargos['inss_patronal']" in fonte, (
        'o dict de retorno não expõe inss_patronal — o consumidor continua '
        'obrigado a reconstituir a parcela por subtração')
    assert "'fgts': encargos['fgts']" in fonte, (
        'a chave fgts sumiu ou foi renomeada — folha_pagamento_views lê por nome')
    assert "'encargos_patronais': encargos['total']" in fonte, (
        'a chave encargos_patronais sumiu ou foi renomeada')
