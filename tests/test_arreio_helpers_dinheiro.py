"""Autoteste dos coletores de `helpers_dinheiro` — B0.2 Step 2.

Um coletor errado é pior que coletor nenhum: ele deixa o arreio inteiro verde
sobre o defeito, que foi exatamente o que aconteceu com os testes textuais do
p1. Então os coletores se provam antes de serem usados.

O que se prova aqui:
  * o coletor ENCONTRA um custo semeado à mão (sem passar por código de produção);
  * o coletor de um tenant NÃO enxerga o custo do outro — a garantia sem a qual
    toda contagem deste arreio seria global e a base de dev, compartilhada entre
    execuções, faria o número subir a cada rodada;
  * `assert_custo_do_dia` FALHA quando deve, e a mensagem distingue "perdeu o
    custo" de "contou a mais". A asserção do p1 (`<= 1`) era verdadeira para
    zero — este teste existe para que a substituta não tenha o mesmo furo.
"""
import os
import sys
from datetime import date
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints antes de qualquer request
from app import app, db
from models import GestaoCustoFilho, GestaoCustoPai

from helpers_dinheiro import (assert_custo_do_dia, custos_obra,
                              filhos_mao_de_obra, soma)
from helpers_tenant import dois_tenants

pytestmark = pytest.mark.integration

DATA = date(2026, 6, 15)


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-arreio-dinheiro'
    yield


def _semear_filho_mao_de_obra(tenant, valor, data=DATA):
    """Cria pai + filho de mão de obra à mão.

    À mão de propósito: um coletor validado contra `registrar_custo_automatico`
    provaria que os dois concordam, não que o coletor lê o banco.
    """
    pai = GestaoCustoPai(
        admin_id=tenant.admin_id, tipo_categoria='SALARIO',
        entidade_nome=f'Funcionario {tenant.marca}',
        entidade_id=tenant.funcionario_id, obra_id=tenant.obra_id)
    db.session.add(pai)
    db.session.flush()

    filho = GestaoCustoFilho(
        pai_id=pai.id, admin_id=tenant.admin_id, obra_id=tenant.obra_id,
        data_referencia=data, descricao=f'Custo {tenant.marca}',
        valor=Decimal(str(valor)), origem_tabela='rdo_mao_obra')
    db.session.add(filho)
    db.session.commit()
    return filho


def test_o_coletor_encontra_o_custo_semeado():
    with app.app_context():
        a, _b = dois_tenants('coletor', com_fatos=False)
        _semear_filho_mao_de_obra(a, 124.00)

        linhas = filhos_mao_de_obra(a, DATA)

        assert len(linhas) == 1
        assert soma(linhas) == pytest.approx(124.00)


def test_o_coletor_de_um_tenant_nao_enxerga_o_custo_do_outro():
    """A garantia que sustenta toda contagem deste arreio.

    Sem ela, a base de dev compartilhada entre execuções faria o número subir a
    cada rodada e o arreio inteiro viraria ruído.
    """
    with app.app_context():
        a, b = dois_tenants('cruzado', com_fatos=False)
        _semear_filho_mao_de_obra(a, 124.00)
        _semear_filho_mao_de_obra(b, 999.00)

        de_a = filhos_mao_de_obra(a, DATA)
        de_b = filhos_mao_de_obra(b, DATA)

        assert len(de_a) == 1 and soma(de_a) == pytest.approx(124.00)
        assert len(de_b) == 1 and soma(de_b) == pytest.approx(999.00)


def test_com_fatos_false_nao_semeia_custo_nem_ponto():
    """O tenant limpo precisa nascer limpo, senão o arreio de RDO mede a guarda
    `existe_ponto_no_dia` em vez do custo."""
    with app.app_context():
        from models import RegistroPonto

        a, _b = dois_tenants('limpo', com_fatos=False)

        assert filhos_mao_de_obra(a, DATA) == []
        assert custos_obra(a, DATA) == []
        assert RegistroPonto.query.filter_by(
            admin_id=a.admin_id, data=DATA).count() == 0


def test_com_fatos_true_continua_semeando_os_tres_fatos():
    """O default não pode ter mudado — quatro testes do p1 dependem dele."""
    with app.app_context():
        from models import RegistroPonto

        a, _b = dois_tenants('cheio')

        assert len(custos_obra(a, DATA)) == 1
        assert RegistroPonto.query.filter_by(
            admin_id=a.admin_id, data=DATA).count() == 1


def test_assert_custo_do_dia_acusa_perda_e_diz_qual_lado_quebrou():
    """Zero linhas tem de falhar dizendo 'perdeu o custo'.

    É o caso exato que `len(custos) <= 1` deixava passar.
    """
    with app.app_context():
        a, _b = dois_tenants('perda', com_fatos=False)

        with pytest.raises(AssertionError, match='perdeu o custo'):
            assert_custo_do_dia(a, DATA, 124.00, linhas_esperadas=1)


def test_assert_custo_do_dia_acusa_duplicata():
    with app.app_context():
        a, _b = dois_tenants('dupla', com_fatos=False)
        _semear_filho_mao_de_obra(a, 124.00)
        _semear_filho_mao_de_obra(a, 124.00)

        with pytest.raises(AssertionError, match='contou a mais'):
            assert_custo_do_dia(a, DATA, 124.00, linhas_esperadas=1)


def test_assert_custo_do_dia_acusa_valor_divergente_com_a_contagem_certa():
    """Contagem certa e soma errada — o caso que só a soma pega."""
    with app.app_context():
        a, _b = dois_tenants('valor', com_fatos=False)
        _semear_filho_mao_de_obra(a, 62.00)

        with pytest.raises(AssertionError, match='valor divergente'):
            assert_custo_do_dia(a, DATA, 124.00, linhas_esperadas=1)


def test_assert_custo_do_dia_passa_quando_esta_certo():
    with app.app_context():
        a, _b = dois_tenants('certo', com_fatos=False)
        _semear_filho_mao_de_obra(a, 124.00)

        linhas = assert_custo_do_dia(a, DATA, 124.00, linhas_esperadas=1)
        assert len(linhas) == 1
