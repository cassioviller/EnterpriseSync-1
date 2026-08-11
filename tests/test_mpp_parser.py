"""M03 Task 3 — despacho por extensão, subprocess MPXJ isolado e erros tipados.

`.xml` nunca exige Java (parse in-process); `.mpp` exige e roda em worker
subprocess com timeout; toda falha vira MppParserError com motivo em
{java_indisponivel, arquivo_corrompido, timeout, erro_mpxj, extensao_invalida}.
Testes que sobem a JVM levam o marker `java` + skipif (registrado em
tests/conftest.py) — rodam onde houver JDK (ex.: este ambiente dev).
"""
import os

import pytest

from services import mpp_parser
from services.mpp_parser import MppParserError, java_disponivel, parse_cronograma

FIXTURE_XML = os.path.join(os.path.dirname(__file__), 'fixtures', 'mspdi_minimo.xml')
_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MPP_REAL = os.path.join(_RAIZ, 'CRONOGRAMA 16.07.mpp')
XML_REAL = os.path.join(_RAIZ, 'CRONOGRAMA 16.07.xml')

requer_java = pytest.mark.skipif(not java_disponivel(), reason='JVM indisponível')
requer_par_real = pytest.mark.skipif(
    not (os.path.exists(MPP_REAL) and os.path.exists(XML_REAL)),
    reason='par CRONOGRAMA 16.07 (.mpp/.xml) ausente',
)


def test_xml_despacha_in_process_sem_java(monkeypatch):
    """.xml não pode exigir Java nem subprocess (adendo §4.1)."""
    monkeypatch.setattr(mpp_parser, 'java_disponivel', lambda: False)
    dados = mpp_parser.parse_cronograma(FIXTURE_XML)
    assert [t['id'] for t in dados['tarefas']] == [1, 2]


def test_mpp_sem_java_da_erro_acionavel(monkeypatch, tmp_path):
    monkeypatch.setattr(mpp_parser, 'java_disponivel', lambda: False)
    falso = tmp_path / 'x.mpp'
    falso.write_bytes(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1')
    with pytest.raises(MppParserError) as exc:
        mpp_parser.parse_cronograma(str(falso))
    assert exc.value.motivo == 'java_indisponivel'
    assert 'Salvar como' in str(exc.value)


def test_extensao_invalida(tmp_path):
    arq = tmp_path / 'cronograma.txt'
    arq.write_text('nao sou cronograma', encoding='utf-8')
    with pytest.raises(MppParserError) as exc:
        parse_cronograma(str(arq))
    assert exc.value.motivo == 'extensao_invalida'


@pytest.mark.java
@requer_java
@requer_par_real
def test_timeout_do_worker_e_tipado():
    """O worker nunca trava o chamador: subprocess abortado vira 'timeout'."""
    with pytest.raises(MppParserError) as exc:
        parse_cronograma(MPP_REAL, timeout_s=0.01)
    assert exc.value.motivo == 'timeout'


@pytest.mark.java
@requer_java
@requer_par_real
def test_mpp_e_xml_produzem_o_mesmo_contrato():
    """Caminho MPXJ (subprocess) ≡ caminho MSPDI (stdlib) no par real 16.07.

    Compara o contrato INTEIRO — projeto + todas as tarefas com wbs, datas,
    dias, pct, marco/resumo e predecessoras tipadas (tipo/lag). Um teste que
    só olhasse (id, uid, nome) deixaria passar divergência de vínculo, lag,
    duração ou nome do projeto — exatamente o que a Task 3 precisa garantir.
    """
    via_mpp = parse_cronograma(MPP_REAL)
    via_xml = parse_cronograma(XML_REAL)
    assert len(via_mpp['tarefas']) == len(via_xml['tarefas']) == 103
    assert via_mpp['projeto'] == via_xml['projeto']
    assert via_mpp['tarefas'] == via_xml['tarefas']


# ---------------------------------------------------------------------------
# Lag em unidades DECORRIDAS (11/08). O MPXJ devolve a unidade do Project como
# ela foi digitada; até aqui o worker só conhecia as de tempo ÚTIL e levantava
# RuntimeError em qualquer outra — o que derrubava o ARQUIVO INTEIRO por causa
# de um vínculo. Aconteceu com o cronograma da Angela de 05/08/2026, que tem
# UM link FS +2ed ("Medição em obra dos demais itens").
#
# Não sobem JVM: exercitam a conversão sobre um dublê com a mesma superfície
# que o worker usa (getLag / getDuration / getUnits().toString()).
# ---------------------------------------------------------------------------

class _UnidadeFalsa:
    def __init__(self, texto):
        self._texto = texto

    def toString(self):
        return self._texto


class _LagFalso:
    def __init__(self, duracao, unidade):
        self._duracao = duracao
        self._unidade = unidade

    def getDuration(self):
        return self._duracao

    def getUnits(self):
        return _UnidadeFalsa(self._unidade)


class _RelacaoFalsa:
    def __init__(self, lag):
        self._lag = lag

    def getLag(self):
        return self._lag


def _lag(duracao, unidade):
    from services.mpp_parser_worker import _lag_dias
    return _lag_dias(_RelacaoFalsa(_LagFalso(duracao, unidade)))


def test_lag_em_unidades_uteis_nao_mudou():
    """Regressão: a tabela de tempo útil continua valendo como antes."""
    assert _lag(2.0, 'd') == 2.0
    assert _lag(8.0, 'h') == 1.0
    assert _lag(480.0, 'm') == 1.0
    assert _lag(1.0, 'w') == 5.0
    assert _lag(1.0, 'mo') == 20.0
    assert _lag(-6.0, 'd') == -6.0  # lag negativo existe no cronograma real


def test_lag_decorrido_vira_dia_util():
    """2 dias CORRIDOS ≈ 1,43 dias úteis — e o scheduler, que faz int(), agenda
    como +1. Confere no caso comum: 2 dias corridos a partir de uma sexta caem
    no domingo, e o próximo dia útil é a segunda."""
    assert _lag(2.0, 'ed') == round(2.0 * 5 / 7, 6)
    assert int(_lag(2.0, 'ed')) == 1
    assert _lag(1.0, 'ew') == 5.0        # 7 corridos = 5 úteis, exato
    assert _lag(24.0, 'eh') == _lag(1.0, 'ed')
    assert _lag(1440.0, 'em') == _lag(1.0, 'ed')
    assert _lag(0.0, 'ed') == 0.0


def test_lag_percentual_continua_recusado():
    """'%' é relativo à duração da predecessora — não dá para converter sem
    ela, então tem de falhar alto em vez de virar um número inventado."""
    with pytest.raises(RuntimeError, match='não tratada'):
        _lag(50.0, '%')
    with pytest.raises(RuntimeError, match='não tratada'):
        _lag(50.0, 'e%')


def test_lag_ausente_e_zero():
    from services.mpp_parser_worker import _lag_dias
    assert _lag_dias(_RelacaoFalsa(None)) == 0.0
