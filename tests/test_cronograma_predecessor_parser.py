"""Fase 1 (editor v2) — parser de predecessoras em formato MS Project.

Step E item 2 do plano `2026-07-24-cronograma-fase1-plano.md`: testes
unitários PUROS (sem DB, sem app) de `parsear_predecessoras` /
`formatar_predecessoras`, cobrindo a gramática, as mensagens de erro exatas
(pt-BR, 400-friendly) e o round-trip formatar ↔ parsear.

Convenção de mapa: linha visual (1-based) → id de tarefa. Aqui usamos ids
sintéticos (linha N → id 100+N) para deixar explícito que linha ≠ id.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.cronograma_predecessor_parser import (
    ErroParsePredecessora,
    VinculoParseado,
    formatar_predecessoras,
    parsear_predecessoras,
)

# Grade sintética: linhas 1..20 → ids 101..120
LINHA_PARA_TAREFA = {n: 100 + n for n in range(1, 21)}
TAREFA_PARA_LINHA = {v: k for k, v in LINHA_PARA_TAREFA.items()}


# ─────────────────────────────────────────────────────────────────────────────
# Entradas válidas
# ─────────────────────────────────────────────────────────────────────────────

def test_numero_simples_vira_ti_lag_zero():
    assert parsear_predecessoras('12', LINHA_PARA_TAREFA) == [
        VinculoParseado(predecessora_id=112, tipo='TI', lag_dias=0)
    ]


def test_tipo_explicito_sem_lag():
    assert parsear_predecessoras('12TI', LINHA_PARA_TAREFA) == [
        VinculoParseado(predecessora_id=112, tipo='TI', lag_dias=0)
    ]


def test_tipo_com_lag_positivo():
    assert parsear_predecessoras('12TI+3', LINHA_PARA_TAREFA) == [
        VinculoParseado(predecessora_id=112, tipo='TI', lag_dias=3)
    ]


def test_tipo_com_lag_negativo():
    assert parsear_predecessoras('12II-2', LINHA_PARA_TAREFA) == [
        VinculoParseado(predecessora_id=112, tipo='II', lag_dias=-2)
    ]


def test_multiplas_entradas_separadas_por_ponto_e_virgula():
    assert parsear_predecessoras('12;15TT+1', LINHA_PARA_TAREFA) == [
        VinculoParseado(predecessora_id=112, tipo='TI', lag_dias=0),
        VinculoParseado(predecessora_id=115, tipo='TT', lag_dias=1),
    ]


def test_espacos_e_minusculas_sao_tolerados():
    assert parsear_predecessoras('  12 ; 15tt+1  ', LINHA_PARA_TAREFA) == [
        VinculoParseado(predecessora_id=112, tipo='TI', lag_dias=0),
        VinculoParseado(predecessora_id=115, tipo='TT', lag_dias=1),
    ]


def test_virgula_como_separador_e_tolerada():
    assert parsear_predecessoras('12, 15TT+1', LINHA_PARA_TAREFA) == [
        VinculoParseado(predecessora_id=112, tipo='TI', lag_dias=0),
        VinculoParseado(predecessora_id=115, tipo='TT', lag_dias=1),
    ]


def test_todos_os_tipos_validos():
    texto = '1TI;2II;3TT;4IT'
    tipos = [v.tipo for v in parsear_predecessoras(texto, LINHA_PARA_TAREFA)]
    assert tipos == ['TI', 'II', 'TT', 'IT']


def test_string_vazia_remove_todos_os_vinculos():
    assert parsear_predecessoras('', LINHA_PARA_TAREFA) == []
    assert parsear_predecessoras('   ', LINHA_PARA_TAREFA) == []
    assert parsear_predecessoras(None, LINHA_PARA_TAREFA) == []


def test_separador_sobrando_nao_gera_erro():
    assert parsear_predecessoras('12;', LINHA_PARA_TAREFA) == [
        VinculoParseado(predecessora_id=112, tipo='TI', lag_dias=0)
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Entradas inválidas — mensagens exatas do plano
# ─────────────────────────────────────────────────────────────────────────────

def test_linha_inexistente():
    with pytest.raises(ErroParsePredecessora) as exc:
        parsear_predecessoras('99', LINHA_PARA_TAREFA)
    assert str(exc.value) == 'Linha 99 não existe na grade'


def test_tipo_invalido_xx():
    with pytest.raises(ErroParsePredecessora) as exc:
        parsear_predecessoras('12XX', LINHA_PARA_TAREFA)
    assert str(exc.value) == "Tipo de vínculo inválido: 'XX' (use TI, II, TT ou IT)"


def test_tipo_invalido_com_lag_tambem_acusa_tipo():
    with pytest.raises(ErroParsePredecessora) as exc:
        parsear_predecessoras('12XX+3', LINHA_PARA_TAREFA)
    assert str(exc.value) == "Tipo de vínculo inválido: 'XX' (use TI, II, TT ou IT)"


def test_auto_referencia():
    with pytest.raises(ErroParsePredecessora) as exc:
        parsear_predecessoras('12', LINHA_PARA_TAREFA, sucessora_id=112)
    assert str(exc.value) == 'Uma tarefa não pode ser predecessora dela mesma'


def test_tarefa_resumo():
    with pytest.raises(ErroParsePredecessora) as exc:
        parsear_predecessoras('12', LINHA_PARA_TAREFA, ids_resumo={112})
    assert str(exc.value) == 'Linha 12 é uma tarefa-resumo — vincule apenas tarefas-folha'


def test_lixo_formato_invalido():
    with pytest.raises(ErroParsePredecessora) as exc:
        parsear_predecessoras('12T+', LINHA_PARA_TAREFA)
    assert str(exc.value) == "Formato inválido: '12T+'. Exemplos: 12, 12TI+3, 12II-2"


@pytest.mark.parametrize('texto', ['abc', 'TI12', '12TI+', '+3', '12 15', '12TI3'])
def test_outros_lixos_sao_formato_invalido(texto):
    with pytest.raises(ErroParsePredecessora) as exc:
        parsear_predecessoras(texto, LINHA_PARA_TAREFA)
    assert str(exc.value).startswith('Formato inválido:')


def test_linha_duplicada_na_mesma_string():
    with pytest.raises(ErroParsePredecessora) as exc:
        parsear_predecessoras('12;12TI+3', LINHA_PARA_TAREFA)
    assert str(exc.value) == 'Linha 12 informada mais de uma vez'


def test_sem_sucessora_e_sem_resumo_nao_valida_esses_casos():
    # Contrato explícito: sem `sucessora_id`/`ids_resumo`, essas checagens
    # ficam a cargo do chamador — o parse aceita normalmente.
    assert parsear_predecessoras('12', LINHA_PARA_TAREFA) == [
        VinculoParseado(predecessora_id=112, tipo='TI', lag_dias=0)
    ]


# ─────────────────────────────────────────────────────────────────────────────
# formatar_predecessoras — inverso do parse
# ─────────────────────────────────────────────────────────────────────────────

def test_formatar_ti_lag_zero_vira_so_o_numero():
    v = [VinculoParseado(predecessora_id=112, tipo='TI', lag_dias=0)]
    assert formatar_predecessoras(v, TAREFA_PARA_LINHA) == '12'


def test_formatar_tipo_nao_ti_sem_lag():
    v = [VinculoParseado(predecessora_id=112, tipo='II', lag_dias=0)]
    assert formatar_predecessoras(v, TAREFA_PARA_LINHA) == '12II'


def test_formatar_com_lag_usa_sinal_explicito():
    vs = [
        VinculoParseado(predecessora_id=112, tipo='TI', lag_dias=3),
        VinculoParseado(predecessora_id=115, tipo='II', lag_dias=-2),
    ]
    assert formatar_predecessoras(vs, TAREFA_PARA_LINHA) == '12TI+3;15II-2'


def test_formatar_lista_vazia_vira_string_vazia():
    assert formatar_predecessoras([], TAREFA_PARA_LINHA) == ''


def test_formatar_aceita_dicts():
    vs = [{'predecessora_id': 112, 'tipo': 'TT', 'lag_dias': 1}]
    assert formatar_predecessoras(vs, TAREFA_PARA_LINHA) == '12TT+1'


def test_formatar_tarefa_fora_da_grade_e_erro():
    v = [VinculoParseado(predecessora_id=999, tipo='TI', lag_dias=0)]
    with pytest.raises(ErroParsePredecessora):
        formatar_predecessoras(v, TAREFA_PARA_LINHA)


@pytest.mark.parametrize('texto', ['12', '12II', '12TI+3', '12II-2', '12;15TT+1', '1;2II;3TT;4IT'])
def test_round_trip_parse_depois_formatar(texto):
    # Textos já na forma canônica (TI+lag 0 = só o número) round-trippam
    # byte a byte.
    vinculos = parsear_predecessoras(texto, LINHA_PARA_TAREFA)
    assert formatar_predecessoras(vinculos, TAREFA_PARA_LINHA) == texto


def test_formatar_canonicaliza_ti_lag_zero_explicito():
    # '12TI' é aceito no parse, mas a forma canônica de saída é '12'.
    vinculos = parsear_predecessoras('12TI', LINHA_PARA_TAREFA)
    assert formatar_predecessoras(vinculos, TAREFA_PARA_LINHA) == '12'


def test_round_trip_formatar_depois_parse():
    originais = [
        VinculoParseado(predecessora_id=112, tipo='TI', lag_dias=0),
        VinculoParseado(predecessora_id=115, tipo='TT', lag_dias=1),
        VinculoParseado(predecessora_id=103, tipo='II', lag_dias=-2),
    ]
    texto = formatar_predecessoras(originais, TAREFA_PARA_LINHA)
    assert parsear_predecessoras(texto, LINHA_PARA_TAREFA) == originais
