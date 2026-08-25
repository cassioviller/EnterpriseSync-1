"""A única leitura de dinheiro digitado.

Antes deste módulo o repositório tinha CINCO parsers artesanais — em
`views/aditivos_views.py`, `compras_views.py`, `services/faixa_alcada_admin.py`,
`financeiro_views.py` e `views/orcamentos_views.py` — e os cinco discordavam
sobre `1.500`. Três erravam por 1000×; um, o do aditivo, lia `150000.00` como
quinze milhões e lançava a diferença no razão.

A regra aqui é uma só: **entrada ambígua é recusada**. O milhar brasileiro
agrupa sempre em três, então um único ponto com exatamente três casas depois
não tem leitura segura — e adivinhar custa mil vezes o valor.
"""
from decimal import Decimal, InvalidOperation

__all__ = ['SEM_DEFAULT', 'ValorAmbiguo', 'ValorInvalido', 'parse_decimal_br']


class ValorInvalido(ValueError):
    """O texto não é um número que se possa cobrar de alguém."""


class ValorAmbiguo(ValorInvalido):
    """`1.500` tanto pode ser mil e quinhentos quanto um e meio."""


SEM_DEFAULT = object()

# 'R$', espaço comum, espaço não-quebrável e o separador estreito que o
# `Intl.NumberFormat` do navegador produz em pt-BR.
_LIXO = ('R$', 'r$', ' ', '\xa0', ' ')


def _limpar(texto):
    for ruido in _LIXO:
        texto = texto.replace(ruido, '')
    return texto.strip()


def _normalizar_separadores(texto, campo):
    """Devolve o texto com '.' como separador decimal e nada de milhar."""
    tem_virgula = ',' in texto
    tem_ponto = '.' in texto

    if tem_virgula and tem_ponto:
        # o ÚLTIMO separador é o decimal: 1.234,56 é BR, 1,234.56 é EN
        if texto.rfind(',') > texto.rfind('.'):
            return texto.replace('.', '').replace(',', '.')
        return texto.replace(',', '')

    if tem_virgula:
        # mais de uma vírgula só pode ser milhar EN
        if texto.count(',') > 1:
            return texto.replace(',', '')
        return texto.replace(',', '.')

    if tem_ponto:
        # mais de um ponto só pode ser milhar BR
        if texto.count('.') > 1:
            return texto.replace('.', '')
        inteiro, _, fracao = texto.partition('.')
        if len(fracao) == 3 and inteiro.lstrip('+-').isdigit():
            raise ValorAmbiguo(
                f'{campo}: {texto!r} é ambíguo — o ponto com três casas tanto '
                f'pode ser milhar quanto decimal. Escreva '
                f'{texto.replace(".", "")},00 para o valor cheio, ou '
                f'{inteiro},{fracao} para a fração.')
        return texto

    return texto


def parse_decimal_br(raw, *, campo='valor', default=SEM_DEFAULT,
                     minimo=None, maximo=None):
    """Lê um valor em dinheiro digitado por gente, em pt-BR ou en-US.

    `campo` entra na mensagem de erro — é o que o operador vê na tela.
    `default` é usado para entrada vazia; sem ele, vazio LEVANTA.
    `minimo`/`maximo` são inclusivos e valem também para o `default`.
    """
    if isinstance(raw, Decimal):
        valor = raw
    elif isinstance(raw, bool):
        # bool é int em Python, e ninguém quis dizer "True reais"
        raise ValorInvalido(f'{campo}: {raw!r} não é um valor válido')
    elif isinstance(raw, (int, float)):
        valor = Decimal(str(raw))
    else:
        texto = _limpar(str(raw)) if raw is not None else ''
        if not texto:
            if default is SEM_DEFAULT:
                raise ValorInvalido(f'{campo}: não pode ficar em branco')
            if default is None:
                return None
            valor = (default if isinstance(default, Decimal)
                     else Decimal(str(default)))
            return _conferir_faixa(valor, campo, minimo, maximo)
        try:
            valor = Decimal(_normalizar_separadores(texto, campo))
        except ValorInvalido:
            raise
        except (InvalidOperation, ValueError, ArithmeticError):
            raise ValorInvalido(f'{campo}: {raw!r} não é um valor válido')
        if not valor.is_finite():
            raise ValorInvalido(f'{campo}: {raw!r} não é um valor válido')

    return _conferir_faixa(valor, campo, minimo, maximo)


def _conferir_faixa(valor, campo, minimo, maximo):
    if minimo is not None and valor < minimo:
        raise ValorInvalido(f'{campo}: precisa ser no mínimo {minimo}')
    if maximo is not None and valor > maximo:
        raise ValorInvalido(f'{campo}: acima do limite de {maximo}')
    return valor
