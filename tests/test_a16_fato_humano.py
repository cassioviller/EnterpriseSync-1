"""B1.9 — unidade sobre `registro_ponto_tem_fato_humano`.

A função decide se o PLANO pode sobrescrever o registro do dia. Errar para o
lado permissivo destrói dado do usuário — atestado virando 8h trabalhadas —, e
errar para o lado restritivo só deixa de converter uma alocação, que é
recuperável à mão. Por isso ela é **fail-closed**, e por isso a lista branca é
fechada.

Testa a função DIRETO, sem banco: ela é pura sobre o objeto. O nível de rota
mora em `tests/test_arreio_presenca_rotas.py`, que exercita
`POST /equipe/api/sync-ponto` de verdade — os dois se complementam e nenhum
substitui o outro.
"""
import os
import sys
from datetime import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints antes de qualquer request
from models import (TIPOS_PONTO_NEUTROS_PARA_O_PLANO,
                    registro_ponto_tem_fato_humano)


class _Registro:
    """Dublê com as seis colunas que a função lê.

    Objeto simples em vez de `RegistroPonto` real: a função não toca no banco, e
    um dublê deixa cada caso declarar exatamente o que importa. Se ela um dia
    passar a consultar algo, este teste quebra na hora — que é o aviso certo.
    """

    def __init__(self, tipo_registro='trabalho_normal', hora_entrada=None,
                 hora_saida=None, hora_almoco_saida=None,
                 hora_almoco_retorno=None, horas_trabalhadas=0.0,
                 horas_extras=0.0):
        self.tipo_registro = tipo_registro
        self.hora_entrada = hora_entrada
        self.hora_saida = hora_saida
        self.hora_almoco_saida = hora_almoco_saida
        self.hora_almoco_retorno = hora_almoco_retorno
        self.horas_trabalhadas = horas_trabalhadas
        self.horas_extras = horas_extras


# ---------------------------------------------------------------------------
# Gatilho 1 — marca de horário
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('campo', ['hora_entrada', 'hora_saida',
                                   'hora_almoco_saida', 'hora_almoco_retorno'])
def test_qualquer_marca_de_horario_e_fato_humano(campo):
    """As QUATRO colunas contam, não só entrada e saída.

    A guarda antiga olhava `hora_entrada or hora_saida`. Um registro que só tem
    o almoço apontado — batida parcial, meio de expediente — passava por ela e
    era sobrescrito.
    """
    assert registro_ponto_tem_fato_humano(_Registro(**{campo: time(8, 0)}))


def test_registro_neutro_e_vazio_nao_e_fato_humano():
    """O caso legítimo: o plano PRECISA poder preencher este."""
    assert not registro_ponto_tem_fato_humano(_Registro())


# ---------------------------------------------------------------------------
# Gatilho 2 — horas medidas sem hora de relógio
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('campo,valor', [('horas_trabalhadas', 8.0),
                                         ('horas_extras', 2.0)])
def test_horas_medidas_sem_relogio_sao_fato_humano(campo, valor):
    """Importação de Excel grava horas sem hora de relógio.

    Recalcular por cima zeraria `horas_extras`, que ninguém mais reconstrói —
    o Excel é a única fonte delas.
    """
    assert registro_ponto_tem_fato_humano(_Registro(**{campo: valor}))


def test_horas_zeradas_nao_bloqueiam():
    assert not registro_ponto_tem_fato_humano(
        _Registro(horas_trabalhadas=0.0, horas_extras=0.0))


def test_horas_none_nao_explodem():
    """Coluna nullable: `None` tem de ser lido como zero, não estourar."""
    assert not registro_ponto_tem_fato_humano(
        _Registro(horas_trabalhadas=None, horas_extras=None))


# ---------------------------------------------------------------------------
# Gatilho 3 — tipo classificado, e a normalização de caixa
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('tipo', [
    'atestado', 'falta', 'falta_justificada', 'ferias',
    'sabado_folga', 'domingo_folga', 'feriado_folga', 'meio_periodo',
])
def test_ausencia_classificada_e_fato_humano(tipo):
    """O coração do A16-a: nenhum destes tem hora, e todos precisam sobreviver."""
    assert registro_ponto_tem_fato_humano(_Registro(tipo_registro=tipo))


@pytest.mark.parametrize('tipo', ['ATESTADO', 'FALTA', 'FALTA_J', 'FERIAS',
                                  'SAB_FOLGA', 'DOM_FOLGA', 'FER_FOLGA'])
def test_a_familia_em_caixa_alta_do_excel_e_fato_humano(tipo):
    """`services/ponto_importacao.py:598-599` grava em CAIXA ALTA.

    Comparação sensível a caixa deixaria toda esta família passar — e é a
    família que vem de planilha, ou seja, em volume.
    """
    assert registro_ponto_tem_fato_humano(_Registro(tipo_registro=tipo))


@pytest.mark.parametrize('tipo', ['sabado_horas_extras', 'domingo_horas_extras'])
def test_os_dois_que_parecem_neutros_e_nao_sao(tipo):
    """Sem escritor vivo, mas lidos com regra de pagamento própria.

    `utils.py:337-342` paga 1.5x/2.0x sobre TODAS as horas. Convertê-los para
    `'sabado_trabalhado'` não casa com ramo nenhum de `utils.py:326-344` e **o
    custo do dia vira zero** — perda de dinheiro silenciosa, disfarçada de
    normalização de vocabulário.
    """
    assert registro_ponto_tem_fato_humano(_Registro(tipo_registro=tipo))


def test_tipo_desconhecido_e_fato_humano():
    """Fail-closed.

    `ponto_views.py:1016` persiste `motivo` cru, sem allowlist: qualquer string
    digitada por um humano chega ao `tipo_registro`. A função não pode adivinhar
    o que ela significa, e a única resposta segura é não mexer.
    """
    assert registro_ponto_tem_fato_humano(
        _Registro(tipo_registro='licenca_paternidade_2026'))


@pytest.mark.parametrize('tipo', sorted(TIPOS_PONTO_NEUTROS_PARA_O_PLANO))
def test_a_lista_branca_inteira_e_neutra(tipo):
    """Cada valor da lista branca tem de deixar o plano passar.

    🔬 Este teste é o que pega o erro mais provável na manutenção da constante:
    acrescentar um valor JÁ EM CAIXA ALTA. A função normaliza com strip+lower
    antes de comparar, então um `'TRABALHADO'` na lista nunca casaria, o caso
    legítimo passaria a ser tratado como classificado, e o plano deixaria de
    converter tudo — em silêncio, e sem nenhum outro teste reclamando.
    """
    assert not registro_ponto_tem_fato_humano(_Registro(tipo_registro=tipo))
    assert tipo == tipo.strip().lower(), (
        f'{tipo!r} está na lista branca fora da forma normalizada — a função '
        f'compara com strip+lower e este valor nunca vai casar')


@pytest.mark.parametrize('tipo', ['  trabalho_normal  ', 'Trabalho_Normal',
                                  'TRABALHO_NORMAL', 'TRABALHADO'])
def test_neutro_com_espaco_ou_caixa_continua_neutro(tipo):
    """A normalização vale para os dois lados: o caso legítimo escrito torto
    pelo importador não pode virar 'classificado' e travar o plano."""
    assert not registro_ponto_tem_fato_humano(_Registro(tipo_registro=tipo))


def test_tipo_none_e_tratado_como_vazio():
    """Coluna tem default, mas nada impede `None` numa linha antiga."""
    assert not registro_ponto_tem_fato_humano(_Registro(tipo_registro=None))


# ---------------------------------------------------------------------------
# A precedência entre gatilhos
# ---------------------------------------------------------------------------

def test_ausencia_com_hora_gravada_por_engano_continua_protegida():
    """Se um registro de atestado tiver hora (dado sujo), protege igual.

    Os gatilhos são um OU, não um E — e é o que se quer: qualquer sinal de fato
    humano basta.
    """
    assert registro_ponto_tem_fato_humano(
        _Registro(tipo_registro='atestado', hora_entrada=time(8, 0)))
