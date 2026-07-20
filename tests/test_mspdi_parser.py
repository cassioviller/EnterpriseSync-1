"""M03 — parser MSPDI stdlib emite o contrato completo do plano.

Contrato (plano 2026-07-20-modulo-03-implementacao-upload-parser.md):
{"projeto": {"nome", "data_status"},
 "tarefas": [{"id", "uid", "wbs", "outline", "nome", "inicio", "fim",
              "dias", "pct_project", "resumo", "marco",
              "predecessoras": [{"id", "uid", "tipo", "lag_dias"}],
              "notas"}]}
"""
import os

import pytest

from services.mspdi_parser import parse_mspdi

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'mspdi_minimo.xml')
XML_REAL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'CRONOGRAMA 16.07.xml',
)


def test_parse_mspdi_emite_contrato_completo():
    dados = parse_mspdi(FIXTURE)
    assert set(dados) == {'projeto', 'tarefas'}
    assert dados['projeto']['nome'] == 'Obra Minima'

    tarefas = dados['tarefas']
    assert [t['id'] for t in tarefas] == [1, 2]
    raiz, filha = tarefas

    assert raiz['uid'] == 100
    assert raiz['wbs'] == '1'
    assert raiz['outline'] == 1
    assert raiz['nome'] == 'Fundacao'
    assert raiz['resumo'] is True
    assert raiz['marco'] is False
    assert raiz['inicio'] == '2026-07-06'
    assert raiz['fim'] == '2026-07-07'
    assert raiz['dias'] == 2.0
    assert raiz['pct_project'] == 0.0
    assert raiz['predecessoras'] == []

    assert filha['uid'] == 101
    assert filha['wbs'] == '1.1'
    assert filha['marco'] is True
    assert filha['resumo'] is False
    assert filha['dias'] == 0.0
    assert filha['pct_project'] == 50.0


def test_predecessora_mapeada_por_uid_e_tipada():
    """UID 100 no XML deve virar id 1 na saída — a armadilha da §2 do adendo."""
    dados = parse_mspdi(FIXTURE)
    filha = dados['tarefas'][1]
    assert filha['predecessoras'] == [
        {'id': 1, 'uid': 100, 'tipo': 'FS', 'lag_dias': 1.0},
    ]


def test_notas_e_data_status_null_quando_ausentes():
    dados = parse_mspdi(FIXTURE)
    assert dados['projeto']['data_status'] is None
    assert all(t['notas'] is None for t in dados['tarefas'])


def test_parse_mspdi_rejeita_xml_que_nao_e_mspdi(tmp_path):
    ruim = tmp_path / 'qualquer.xml'
    ruim.write_text('<?xml version="1.0"?><Qualquer/>', encoding='utf-8')
    with pytest.raises(ValueError, match='não é MSPDI'):
        parse_mspdi(str(ruim))


@pytest.mark.skipif(not os.path.exists(XML_REAL), reason='CRONOGRAMA 16.07.xml ausente')
def test_integracao_cronograma_real_16_07():
    dados = parse_mspdi(XML_REAL)
    assert dados['projeto']['nome'] == 'Obra Itu - Baias Fazenda Santa Mônica'
    assert dados['projeto']['data_status'] is None

    tarefas = dados['tarefas']
    assert len(tarefas) == 103
    assert all(t['uid'] is not None for t in tarefas)
    assert all(t['wbs'] is not None for t in tarefas)
    assert sum(len(t['predecessoras']) for t in tarefas) == 66
