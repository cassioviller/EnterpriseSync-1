"""Fase 1 Step B — motor de agendamento novo (services/cronograma_scheduler).

Testes UNITÁRIOS das funções PURAS — nada de DB/app: importa apenas a parte
pura do módulo (a persistência importa models tardiamente, dentro das
funções). Cobertura (§Step E item 1 do plano):
  * dias úteis: atravessar fim de semana, n negativo, n=0 normalizando
    sábado→segunda, duração 1, marco/duração 0;
  * cada tipo de vínculo TI/II/TT/IT com lag 0 / +3 / −2;
  * múltiplas predecessoras → vence a restrição MÁXIMA;
  * ciclo direto e indireto → ErroCiclo com NOMES na mensagem;
  * âncoras: tarefa iniciada (datas imutáveis mas empurra sucessoras) e
    "não começar antes de" (sem predecessora mantém o próprio início);
  * folga/caminho crítico: cadeia linear toda crítica; ramo paralelo curto
    com folga > 0; pai is_critica = any(filhas);
  * roll-up min/max/duração em DOIS níveis de hierarquia.

Datas de referência: semana de 2026-07-06 (segunda-feira).
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.cronograma_scheduler import (
    ErroCiclo,
    NoTarefa,
    VinculoSpec,
    calcular_agendamento,
    detectar_ciclo,
    dia_util_anterior,
    duracao_util_entre,
    eh_dia_util,
    fim_por_duracao,
    montar_grafo,
    ordenar_topologicamente,
    proximo_dia_util,
    somar_dias_uteis,
)

# Semana de referência (2026-07-06 é segunda)
SEG = date(2026, 7, 6)
TER = date(2026, 7, 7)
QUA = date(2026, 7, 8)
QUI = date(2026, 7, 9)
SEX = date(2026, 7, 10)
SAB = date(2026, 7, 11)
DOM = date(2026, 7, 12)
SEG2 = date(2026, 7, 13)
TER2 = date(2026, 7, 14)
# Semana anterior
QUI_ANT = date(2026, 7, 2)
SEX_ANT = date(2026, 7, 3)


def _no(id_, nome=None, dur=1, inicio=None, fim=None, pai=None,
        marco=False, ancorada=False):
    return NoTarefa(id=id_, nome=nome or f'T{id_}', duracao=dur, inicio=inicio,
                    fim=fim, pai_id=pai, is_marco=marco, ancorada=ancorada)


def _v(pred, suc, tipo='TI', lag=0):
    return VinculoSpec(predecessora_id=pred, sucessora_id=suc, tipo=tipo, lag=lag)


def test_datas_de_referencia_sao_o_que_dizem_ser():
    assert SEG.weekday() == 0 and SEX.weekday() == 4
    assert SAB.weekday() == 5 and DOM.weekday() == 6


# ---------------------------------------------------------------------------
# B1 — matemática de dias úteis
# ---------------------------------------------------------------------------

def test_eh_dia_util():
    assert eh_dia_util(SEG) and eh_dia_util(SEX)
    assert not eh_dia_util(SAB) and not eh_dia_util(DOM)


def test_proximo_dia_util_normaliza_fim_de_semana():
    assert proximo_dia_util(SAB) == SEG2
    assert proximo_dia_util(DOM) == SEG2
    assert proximo_dia_util(TER) == TER  # útil fica onde está


def test_dia_util_anterior():
    assert dia_util_anterior(SAB) == SEX
    assert dia_util_anterior(DOM) == SEX
    assert dia_util_anterior(SEG) == SEG


def test_somar_dias_uteis_atravessa_fim_de_semana():
    assert somar_dias_uteis(SEX, 1) == SEG2
    assert somar_dias_uteis(QUI, 3) == TER2  # sex, seg, ter


def test_somar_dias_uteis_negativo():
    assert somar_dias_uteis(SEG2, -1) == SEX
    assert somar_dias_uteis(SEG, -1) == SEX_ANT
    assert somar_dias_uteis(DOM, -1) == SEX  # parte do fim de semana p/ trás


def test_somar_dias_uteis_zero_normaliza_sabado_para_segunda():
    assert somar_dias_uteis(SAB, 0) == SEG2
    assert somar_dias_uteis(QUA, 0) == QUA


def test_fim_por_duracao_um_dia_e_marco():
    assert fim_por_duracao(SEG, 1) == SEG          # duração 1: fim == início
    assert fim_por_duracao(SEG, 0) == SEG          # marco/duração 0
    assert fim_por_duracao(SEG, 5) == SEX
    assert fim_por_duracao(SEX, 2) == SEG2         # atravessa o fim de semana


def test_duracao_util_entre():
    assert duracao_util_entre(SEG, SEX) == 5
    assert duracao_util_entre(SEG, SEG) == 1
    assert duracao_util_entre(SEG, SEG2) == 6      # inclui só os úteis
    assert duracao_util_entre(SAB, DOM) == 0
    assert duracao_util_entre(SEX, SEG) == 0       # fim < início


# ---------------------------------------------------------------------------
# B2 — grafo, ciclo, ordem topológica
# ---------------------------------------------------------------------------

def test_montar_grafo_ignora_vinculo_com_ponta_desconhecida():
    nos = [_no(1), _no(2)]
    grafo = montar_grafo(nos, [_v(99, 2), _v(1, 98), _v(1, 2)])
    assert [v.sucessora_id for v in grafo[1]] == [2]
    assert grafo[2] == []


def test_detectar_ciclo_devolve_none_em_grafo_aciclico():
    nos = [_no(1), _no(2), _no(3)]
    grafo = montar_grafo(nos, [_v(1, 2), _v(2, 3)])
    assert detectar_ciclo(nos, grafo) is None


def test_ordenar_topologicamente_respeita_dependencias():
    nos = [_no(3), _no(1), _no(2)]
    grafo = montar_grafo(nos, [_v(1, 2), _v(2, 3)])
    ordem = ordenar_topologicamente(nos, grafo)
    assert ordem.index(1) < ordem.index(2) < ordem.index(3)


def test_ciclo_direto_gera_erro_com_nomes_e_caminho():
    nos = [_no(1, 'Alvenaria', dur=2, inicio=SEG), _no(2, 'Reboco', dur=2)]
    with pytest.raises(ErroCiclo) as exc:
        calcular_agendamento(nos, [_v(1, 2), _v(2, 1)], hoje=SEG)
    assert str(exc.value) == (
        'Vínculo inválido: "Alvenaria" já depende de "Reboco" '
        '(ciclo: Alvenaria → Reboco → Alvenaria).')


def test_ciclo_indireto_gera_erro_com_todos_os_nomes():
    nos = [_no(1, 'Fundação', inicio=SEG), _no(2, 'Alvenaria'), _no(3, 'Reboco')]
    with pytest.raises(ErroCiclo) as exc:
        calcular_agendamento(nos, [_v(1, 2), _v(2, 3), _v(3, 1)], hoje=SEG)
    msg = str(exc.value)
    for nome in ('Fundação', 'Alvenaria', 'Reboco'):
        assert nome in msg
    assert 'ciclo:' in msg and '→' in msg
    assert exc.value.ciclo  # ids do caminho disponíveis para a API


# ---------------------------------------------------------------------------
# B4 — tipos de vínculo com lag 0 / +3 / −2
# (A: dur 3, SEG→QUA; B: dur 2, sem início próprio)
# ---------------------------------------------------------------------------

def _ab(tipo, lag):
    nos = [_no(1, 'A', dur=3, inicio=SEG), _no(2, 'B', dur=2)]
    res = calcular_agendamento(nos, [_v(1, 2, tipo, lag)], hoje=SEG)
    assert (res[1].inicio, res[1].fim) == (SEG, QUA)
    return res[2]


@pytest.mark.parametrize('lag, inicio_b, fim_b', [
    (0, QUI, SEX),                                   # dia útil seguinte ao fim
    (3, TER2, date(2026, 7, 15)),                    # +3 úteis de lag
    (-2, TER, QUA),                                  # antecipação de 2 úteis
])
def test_vinculo_ti(lag, inicio_b, fim_b):
    b = _ab('TI', lag)
    assert (b.inicio, b.fim) == (inicio_b, fim_b)


@pytest.mark.parametrize('lag, inicio_b, fim_b', [
    (0, SEG, TER),                                   # começa junto
    (3, QUI, SEX),
    (-2, QUI_ANT, SEX_ANT),
])
def test_vinculo_ii(lag, inicio_b, fim_b):
    b = _ab('II', lag)
    assert (b.inicio, b.fim) == (inicio_b, fim_b)


@pytest.mark.parametrize('lag, inicio_b, fim_b', [
    (0, TER, QUA),                                   # termina junto com A
    (3, SEX, SEG2),
    (-2, SEX_ANT, SEG),
])
def test_vinculo_tt(lag, inicio_b, fim_b):
    b = _ab('TT', lag)
    assert (b.inicio, b.fim) == (inicio_b, fim_b)


@pytest.mark.parametrize('lag, inicio_b, fim_b', [
    (0, SEX_ANT, SEG),                               # termina quando A começa
    (3, QUA, QUI),
    (-2, date(2026, 7, 1), QUI_ANT),
])
def test_vinculo_it(lag, inicio_b, fim_b):
    b = _ab('IT', lag)
    assert (b.inicio, b.fim) == (inicio_b, fim_b)


def test_multiplas_predecessoras_vence_restricao_maxima():
    nos = [_no(1, 'Longa', dur=5, inicio=SEG),       # SEG→SEX
           _no(2, 'Curta', dur=1, inicio=SEG),       # SEG→SEG
           _no(3, 'Sucessora', dur=1)]
    res = calcular_agendamento(nos, [_v(1, 3), _v(2, 3)], hoje=SEG)
    assert res[3].inicio == SEG2                     # max(SEG2, TER)
    assert res[3].fim == SEG2


def test_marco_sucessor_tem_fim_igual_ao_inicio():
    nos = [_no(1, 'A', dur=3, inicio=SEG),
           _no(2, 'Entrega', dur=5, marco=True)]     # duração ignorada p/ span
    res = calcular_agendamento(nos, [_v(1, 2)], hoje=SEG)
    assert res[2].inicio == QUI and res[2].fim == QUI


# ---------------------------------------------------------------------------
# Âncoras
# ---------------------------------------------------------------------------

def test_ancorada_datas_imutaveis_mas_empurra_sucessora():
    nos = [_no(1, 'Iniciada', dur=3, inicio=TER, fim=QUA, ancorada=True),
           _no(2, 'Depois', dur=1)]
    res = calcular_agendamento(nos, [_v(1, 2)], hoje=SEG)
    assert (res[1].inicio, res[1].fim) == (TER, QUA)  # intocadas
    assert res[2].inicio == QUI                       # empurrada pelo fim real


def test_ancorada_em_fim_de_semana_nao_e_normalizada():
    nos = [_no(1, 'Iniciada no sábado', dur=1, inicio=SAB, fim=SAB, ancorada=True)]
    res = calcular_agendamento(nos, [], hoje=SEG)
    assert (res[1].inicio, res[1].fim) == (SAB, SAB)


def test_ancorada_sem_fim_alimenta_sucessora_pelo_fim_derivado():
    nos = [_no(1, 'Iniciada', dur=3, inicio=SEG, fim=None, ancorada=True),
           _no(2, 'Depois', dur=1)]
    res = calcular_agendamento(nos, [_v(1, 2)], hoje=SEG)
    assert res[1].fim is None                         # nunca alterada
    assert res[2].inicio == QUI                       # fim efetivo = QUA


def test_ancorada_sem_datas_restricao_ignorada_com_fallback():
    nos = [_no(1, 'Iniciada sem datas', dur=3, ancorada=True),
           _no(2, 'Depois', dur=1, inicio=QUA)]
    res = calcular_agendamento(nos, [_v(1, 2)], hoje=SEG)
    assert res[2].inicio == QUA                       # cai no próprio início


def test_sem_predecessora_mantem_o_proprio_inicio():
    nos = [_no(1, 'Solta', dur=2, inicio=QUA)]
    res = calcular_agendamento(nos, [], hoje=SEG)
    assert (res[1].inicio, res[1].fim) == (QUA, QUI)


def test_sem_predecessora_inicio_em_sabado_normaliza_para_segunda():
    nos = [_no(1, 'Solta', dur=1, inicio=SAB)]
    res = calcular_agendamento(nos, [], hoje=SEG)
    assert (res[1].inicio, res[1].fim) == (SEG2, SEG2)


def test_sem_predecessora_e_sem_data_recebe_hoje_util():
    nos = [_no(1, 'Nova', dur=2)]
    res = calcular_agendamento(nos, [], hoje=SAB)     # "hoje" num sábado
    assert (res[1].inicio, res[1].fim) == (SEG2, TER2)


# ---------------------------------------------------------------------------
# B5 — folga e caminho crítico
# ---------------------------------------------------------------------------

def test_cadeia_linear_toda_critica():
    nos = [_no(1, 'A', dur=2, inicio=SEG),
           _no(2, 'B', dur=3),
           _no(3, 'C', dur=1)]
    res = calcular_agendamento(nos, [_v(1, 2), _v(2, 3)], hoje=SEG)
    for tid in (1, 2, 3):
        assert res[tid].folga_dias == 0, f'tarefa {tid} deveria ter folga 0'
        assert res[tid].is_critica


def test_ramo_paralelo_curto_tem_folga_positiva():
    nos = [_no(1, 'Longa', dur=5, inicio=SEG),
           _no(2, 'Curta', dur=1, inicio=SEG),
           _no(3, 'Junta', dur=1)]
    res = calcular_agendamento(nos, [_v(1, 3), _v(2, 3)], hoje=SEG)
    assert res[1].folga_dias == 0 and res[1].is_critica
    assert res[3].folga_dias == 0 and res[3].is_critica
    assert res[2].folga_dias == 4                     # SEG livre até SEX
    assert not res[2].is_critica


def test_folha_ancorada_pode_ser_critica():
    nos = [_no(1, 'Iniciada', dur=3, inicio=SEG, fim=QUA, ancorada=True),
           _no(2, 'Depois', dur=2)]
    res = calcular_agendamento(nos, [_v(1, 2)], hoje=SEG)
    assert res[1].folga_dias == 0 and res[1].is_critica


def test_pai_e_critico_se_qualquer_filha_for():
    nos = [_no(10, 'Grupo', dur=1),
           _no(1, 'Longa', dur=5, inicio=SEG, pai=10),
           _no(2, 'Curta', dur=1, inicio=SEG, pai=10),
           _no(3, 'Junta', dur=1)]
    res = calcular_agendamento(nos, [_v(1, 3), _v(2, 3)], hoje=SEG)
    assert res[10].is_critica                         # any(filhas)
    assert res[10].folga_dias == 0                    # min(filhas)


def test_pai_sem_filha_critica_herda_min_folga():
    nos = [_no(10, 'Grupo', dur=1),
           _no(1, 'Longa', dur=5, inicio=SEG),
           _no(2, 'Curta A', dur=1, inicio=SEG, pai=10),
           _no(3, 'Curta B', dur=2, inicio=SEG, pai=10),
           _no(4, 'Junta', dur=1)]
    res = calcular_agendamento(
        nos, [_v(1, 4), _v(2, 4), _v(3, 4)], hoje=SEG)
    assert res[2].folga_dias == 4
    assert res[3].folga_dias == 3
    assert res[10].folga_dias == 3                    # min(4, 3)
    assert not res[10].is_critica


# ---------------------------------------------------------------------------
# Roll-up em dois níveis de hierarquia
# ---------------------------------------------------------------------------

def test_rollup_dois_niveis_min_max_duracao():
    # Avô(1) ── Pai(2) ── D(3), E(4)   e   Avô(1) ── F(5)
    nos = [
        _no(1, 'Avô', dur=1),
        _no(2, 'Pai', dur=1, pai=1),
        _no(3, 'D', dur=2, inicio=SEG, pai=2),        # SEG→TER
        _no(4, 'E', dur=4, pai=2),                    # TI após D: QUA→SEG2
        _no(5, 'F', dur=1, inicio=SEG, pai=1),        # SEG→SEG
    ]
    res = calcular_agendamento(nos, [_v(3, 4)], hoje=SEG)

    assert (res[4].inicio, res[4].fim) == (QUA, SEG2)  # atravessa o fds
    # Pai = min/max das folhas D e E; duração em dias úteis inclusivos
    assert (res[2].inicio, res[2].fim, res[2].duracao) == (SEG, SEG2, 6)
    # Avô agrega Pai (já agregado) e a folha F
    assert (res[1].inicio, res[1].fim, res[1].duracao) == (SEG, SEG2, 6)
    # Folga/crítico sobem os dois níveis: D→E é o caminho crítico
    assert res[3].is_critica and res[4].is_critica
    assert res[5].folga_dias == 5 and not res[5].is_critica
    assert res[2].is_critica and res[2].folga_dias == 0
    assert res[1].is_critica and res[1].folga_dias == 0


def test_vinculo_apontando_para_pai_e_ignorado():
    nos = [_no(1, 'Pai', dur=1),
           _no(2, 'Filha', dur=2, inicio=SEG, pai=1),
           _no(3, 'Solta', dur=1, inicio=QUA)]
    # vínculo cuja predecessora é o PAI (resumo): ignorado com warning
    res = calcular_agendamento(nos, [_v(1, 3)], hoje=SEG)
    assert res[3].inicio == QUA                       # manteve o próprio início


def test_ancorada_em_fim_de_semana_deriva_o_fim_do_primeiro_dia_util():
    """Início gravado no sábado: o fim DERIVADO conta a partir da segunda.

    `fim_por_duracao` conta dias úteis a partir do dia em que se trabalha.
    Sem normalizar o início efetivo, sábado + 2 dias dava SEG — perdendo um
    dia útil, porque o trabalho começa SEG e termina TER. O erro não ficava
    na tarefa: `efetivas` alimenta as restrições das sucessoras, então a
    cadeia inteira andava um dia a menos.

    Em dev, 2.952 tarefas ativas têm `data_inicio` em fim de semana.
    """
    # duração 2 a partir de SAB (11/07): trabalho SEG2 (13/07) e TER2 (14/07)
    nos = [_no(1, 'Iniciada no sábado', dur=2, inicio=SAB, fim=None,
               ancorada=True),
           _no(2, 'Depois', dur=1)]
    res = calcular_agendamento(nos, [_v(1, 2)], hoje=SEG)

    # a data GRAVADA da ancorada continua intocada (contrato de ancoragem)
    assert res[1].inicio == SAB
    assert res[1].fim is None

    # a sucessora TI começa no dia útil seguinte ao fim efetivo (TER2)
    assert res[2].inicio == date(2026, 7, 15), (
        f'fim efetivo da ancorada saiu errado — sucessora em {res[2].inicio}')


def test_ancorada_com_fim_gravado_em_fim_de_semana_nao_e_derivada():
    """Quando o fim EXISTE, ele manda — normalizar o início não o inventa."""
    nos = [_no(1, 'Iniciada', dur=1, inicio=SAB, fim=SAB, ancorada=True),
           _no(2, 'Depois', dur=1)]
    res = calcular_agendamento(nos, [_v(1, 2)], hoje=SEG)
    assert (res[1].inicio, res[1].fim) == (SAB, SAB)
    assert res[2].inicio == SEG2      # dia útil seguinte a SAB
