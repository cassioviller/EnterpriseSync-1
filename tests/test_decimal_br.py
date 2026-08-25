"""A tabela de desambiguação de `parse_decimal_br`, caso a caso.

Sem banco, sem app, sem fixture: é função pura. Se este arquivo ficar lento,
alguma coisa está errada.

O caso que dá nome à onda é `1.500`: hoje quatro parsers do repositório o leem
de quatro jeitos e três deles erram por 1000×. Aqui ele é RECUSADO.
"""
from decimal import Decimal

import pytest

from utils.decimal_br import (SEM_DEFAULT, ValorAmbiguo, ValorInvalido,
                              parse_decimal_br)


@pytest.mark.parametrize('entrada,esperado', [
    ('1234.56', '1234.56'),
    ('1234,56', '1234.56'),
    ('1.234,56', '1234.56'),
    ('1,234.56', '1234.56'),
    ('1.234.567', '1234567'),
    ('1,234,567', '1234567'),
    ('1.5', '1.5'),
    ('1.50', '1.50'),
    ('1.5000', '1.5000'),
    ('150000.00', '150000.00'),
    ('1500', '1500'),
    ('R$ 1.234,56', '1234.56'),
    ('  25  ', '25'),
    ('0', '0'),
    ('-100', '-100'),
    ('-1.234,56', '-1234.56'),
])
def test_le_o_que_nao_e_ambiguo(entrada, esperado):
    assert parse_decimal_br(entrada) == Decimal(esperado)


@pytest.mark.parametrize('entrada', ['1.500', '150.000', '-1.500', '0.000'])
def test_recusa_o_ponto_com_tres_casas(entrada):
    """`1.500` tanto pode ser mil e quinhentos quanto um e meio.

    Adivinhar custa 1000×; é o defeito de `compras_views.py:2853` e de
    `services/faixa_alcada_admin.py:206`.
    """
    with pytest.raises(ValorAmbiguo) as exc:
        parse_decimal_br(entrada, campo='preço')
    # a mensagem precisa ensinar o operador a desambiguar, não só reclamar
    texto = str(exc.value)
    assert 'preço' in texto
    assert ',' in texto


def test_o_ambiguo_e_uma_especie_de_invalido():
    """Quem só quer saber se deu erro captura `ValorInvalido` e pega os dois."""
    assert issubclass(ValorAmbiguo, ValorInvalido)


@pytest.mark.parametrize('entrada', ['abc', 'R$', '--3', '1.2.3,4,5', '.'])
def test_recusa_o_que_nao_e_numero(entrada):
    with pytest.raises(ValorInvalido):
        parse_decimal_br(entrada, campo='valor')


def test_vazio_sem_default_levanta():
    """Campo de dinheiro em branco é decisão do chamador, não do parser."""
    for vazio in (None, '', '   '):
        with pytest.raises(ValorInvalido) as exc:
            parse_decimal_br(vazio, campo='valor_pago')
        assert 'valor_pago' in str(exc.value)


def test_vazio_com_default_devolve_o_default():
    assert parse_decimal_br('', default=Decimal('0')) == Decimal('0')
    assert parse_decimal_br(None, default=None) is None


def test_passa_numero_adiante_sem_mexer():
    """Chamador que já tem Decimal não deveria ter que virar string."""
    assert parse_decimal_br(Decimal('7.25')) == Decimal('7.25')
    assert parse_decimal_br(1500) == Decimal('1500')
    assert parse_decimal_br(1.5) == Decimal('1.5')


def test_minimo_e_maximo():
    assert parse_decimal_br('10', minimo=Decimal('0')) == Decimal('10')
    with pytest.raises(ValorInvalido) as exc:
        parse_decimal_br('-100', campo='valor_pago', minimo=Decimal('0'))
    assert 'valor_pago' in str(exc.value)
    with pytest.raises(ValorInvalido):
        parse_decimal_br('999', campo='teto', maximo=Decimal('500'))


def test_o_default_tambem_respeita_a_faixa():
    """Default fora da faixa é bug de chamador e precisa aparecer."""
    with pytest.raises(ValorInvalido):
        parse_decimal_br('', default=Decimal('-1'), minimo=Decimal('0'))


def test_sentinela_e_distinguivel_de_none():
    assert SEM_DEFAULT is not None


def test_os_tres_espacos_invisiveis_sao_removidos():
    """Um espaço invisível não sobrevive a copiar-e-colar.

    A primeira versão deste módulo perdeu o U+202F (o separador estreito que
    o `Intl.NumberFormat` do navegador produz em pt-BR) — ele virou um
    segundo U+0020, em silêncio, e `1 500,00` passou a ser recusado.
    Por isso este teste afirma sobre os CODEPOINTS, não só sobre o parse.
    """
    from utils.decimal_br import _LIXO
    espacos = {c for c in _LIXO if len(c) == 1}
    assert espacos == {' ', '\xa0', '\u202f'}, (
        f'faltou um espaço invisível: {[hex(ord(c)) for c in espacos]}')


@pytest.mark.parametrize('entrada,rotulo', [
    ('1 500,00', 'espaco-comum-U+0020'),
    ('1\xa0500,00', 'nbsp-U+00A0'),
    ('1\u202f500,00', 'narrow-nbsp-U+202F'),
], ids=lambda v: v if isinstance(v, str) and v.startswith(('espaco', 'nbsp', 'narrow')) else None)
def test_milhar_com_qualquer_espaco_invisivel_parseia(entrada, rotulo):
    """A vírgula decimal já desambigua — o espaço é só ruído de formatação.

    Os três casos são escritos com ESCAPE, nunca com o caractere literal: a
    primeira versão deste teste tinha os três como U+0020 e não cobria nada,
    porque os invisíveis não sobreviveram ao caminho até aqui. O `rotulo`
    existe para que o id do caso diga qual espaço é qual — sem ele, pytest
    numera `_0/_1/_2` e a colisão fica invisível no relatório.
    """
    assert parse_decimal_br(entrada) == Decimal('1500.00'), rotulo
