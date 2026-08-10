"""Mescla export+WhatsApp (scripts/preparar_carga_obra.py — função pura).

O que estes testes travam:

  • dia só no WhatsApp vira item NOVO;
  • dia com campo vazio no sistema é ENRIQUECIDO com delta mínimo — o item
    não repete o que o sistema já tem (o upsert não deve tocar nisso);
  • campo preenchido NOS DOIS lados e diferente vira `_conflito` +
    pendência, e o campo NÃO entra no delta;
  • "Não informado" conta como vazio: não sobrescreve clima real nem conflita;
  • RDO imutável é pulado com pendência;
  • apontamento com chave fora do mapa vira pendência e sai do payload;
  • dia com foto já no banco: aviso, fotos do WhatsApp fora do delta.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/../scripts'))

from preparar_carga_obra import mesclar  # noqa: E402

MAPA = {'-208': {'nome': 'Reforço da laje', 'pai': None, 'caminho': []}}


def _sistema(**extra):
    base = {'data': '2026-07-14', 'clima': 'Ensolarado',
            '_numero_rdo': 'RDO-X-1', '_estado': 'preenchido'}
    base.update(extra)
    return {base['data']: base}


def _whats(**extra):
    item = {'data': '2026-07-14', 'clima': 'Não informado',
            'precipitacao': 'Não informado',
            'comentario': 'Execução do forro.',
            'mao_de_obra': 0}
    item.update(extra)
    return [item]


def test_dia_so_no_whatsapp_vira_item_novo():
    payload, rel = mesclar({}, _whats(data='2026-07-15'), MAPA)
    assert rel['novos'] == ['2026-07-15']
    item = payload[0]
    assert item['comentario'] == 'Execução do forro.'
    # 'Não informado' e mao_de_obra=0 não entram: item novo só com substância
    assert 'clima' not in item


def test_dia_vazio_no_sistema_e_enriquecido_com_delta_minimo():
    sistema = _sistema(comentario=None)
    payload, rel = mesclar(sistema, _whats(), MAPA)
    assert rel['enriquecidos'] == ['2026-07-14']
    item = payload[0]
    assert item == {'data': '2026-07-14', 'comentario': 'Execução do forro.'}, \
        'delta mínimo: clima real do sistema não pode ser tocado'


def test_conflito_real_vira_pendencia_e_campo_fica_fora():
    sistema = _sistema(comentario='Texto que o sistema já tem.')
    payload, rel = mesclar(sistema, _whats(), MAPA)
    assert rel['conflitos'] == ['2026-07-14']
    assert any('comentario' in p for p in rel['pendencias'])
    item = payload[0]
    assert 'comentario' not in item, 'campo em conflito não entra no delta'
    assert item['_conflito'][0]['campo'] == 'comentario'
    assert item['_conflito'][0]['sistema'] == 'Texto que o sistema já tem.'


def test_nao_informado_nao_sobrescreve_nem_conflita():
    sistema = _sistema(comentario=None, precipitacao='Chuva forte')
    payload, rel = mesclar(sistema, _whats(), MAPA)
    item = payload[0]
    assert 'clima' not in item and 'precipitacao' not in item
    assert rel['conflitos'] == []


def test_dia_sem_nenhuma_mudanca_fica_fora_do_payload():
    sistema = _sistema(comentario='Execução do forro.')
    payload, rel = mesclar(sistema, _whats(), MAPA)
    assert payload == []
    assert rel['sem_mudanca'] == ['2026-07-14']


def test_rdo_imutavel_e_pulado_com_pendencia():
    sistema = _sistema(_estado='assinado', comentario=None)
    payload, rel = mesclar(sistema, _whats(), MAPA)
    assert payload == []
    assert any('assinado' in p for p in rel['pendencias'])


def test_apontamento_fora_do_mapa_vira_pendencia():
    whats = _whats(data='2026-07-15',
                   apontamentos=[{'tarefa_mpp': -208, 'pct': 40},
                                 {'tarefa_mpp': 999, 'pct': 10}])
    payload, rel = mesclar({}, whats, MAPA)
    assert payload[0]['apontamentos'] == [{'tarefa_mpp': -208, 'pct': 40}]
    assert any('999' in p for p in rel['pendencias'])


def test_foto_ja_no_banco_gera_aviso_e_fica_fora():
    sistema = _sistema(comentario=None, _fotos_no_banco=3)
    whats = _whats(fotos=[{'arquivo': '1.jpg', 'legenda': 'x'}])
    payload, rel = mesclar(sistema, whats, MAPA)
    assert 'fotos' not in payload[0]
    assert any('preserva' in a for a in rel['avisos'])


def test_ano_implausivel_vira_pendencia_e_fica_fora():
    whats = _whats(data='2016-03-09')
    payload, rel = mesclar({}, whats, MAPA)
    assert payload == []
    assert any('implausível' in p or 'implausivel' in p for p in rel['pendencias'])


# ── distribuição de % do .mpp pelos dias de RDO ───────────────────────
from preparar_carga_obra import distribuir_pct  # noqa: E402


def _folha(uid, pct, fim, resumo=False, nome='Tarefa'):
    return {'uid': uid, 'pct_project': pct, 'fim': fim, 'resumo': resumo,
            'nome': nome}


def test_cem_por_cento_cai_no_primeiro_dia_apos_o_fim():
    payload, rel = distribuir_pct(
        [], ['2026-02-10', '2026-03-10', '2026-04-10'],
        [_folha(7, 100, '2026-02-20')])
    assert payload == [{'data': '2026-03-10',
                        'apontamentos': [{'tarefa_mpp': 7, 'pct': 100.0}]}]
    assert rel['apontados_100'] == 1


def test_fim_anterior_ao_primeiro_rdo_cai_no_primeiro():
    payload, _ = distribuir_pct(
        [], ['2026-02-10', '2026-03-10'], [_folha(7, 100, '2025-10-01')])
    assert payload[0]['data'] == '2026-02-10'


def test_fim_depois_do_ultimo_rdo_cai_no_ultimo_com_aviso():
    payload, rel = distribuir_pct(
        [], ['2026-02-10', '2026-03-10'], [_folha(7, 100, '2026-08-18')])
    assert payload[0]['data'] == '2026-03-10'
    assert any('depois do último RDO' in a for a in rel['avisos'])


def test_parcial_cai_no_ultimo_dia():
    payload, rel = distribuir_pct(
        [], ['2026-02-10', '2026-03-10'], [_folha(9, 42, '2026-02-15')])
    assert payload == [{'data': '2026-03-10',
                        'apontamentos': [{'tarefa_mpp': 9, 'pct': 42.0}]}]
    assert rel['apontados_parciais'] == 1


def test_resumo_e_pct_zero_ficam_de_fora():
    payload, _ = distribuir_pct(
        [], ['2026-02-10'],
        [_folha(1, 100, '2026-01-01', resumo=True), _folha(2, 0, '2026-01-01')])
    assert payload == []


def test_dia_imutavel_nao_e_alvo():
    payload, _ = distribuir_pct(
        [], ['2026-02-10', '2026-03-10'], [_folha(7, 100, '2026-01-01')],
        imutaveis=['2026-02-10'])
    assert payload[0]['data'] == '2026-03-10'


def test_apontamento_soma_em_item_ja_existente_do_payload():
    existente = [{'data': '2026-03-10', 'comentario': 'dia já no payload'}]
    payload, _ = distribuir_pct(
        existente, ['2026-02-10', '2026-03-10'], [_folha(7, 100, '2026-02-20')])
    assert len(payload) == 1
    assert payload[0]['comentario'] == 'dia já no payload'
    assert payload[0]['apontamentos'] == [{'tarefa_mpp': 7, 'pct': 100.0}]


def test_item_novo_nao_carrega_mao_de_obra_nem_chaves_ignoradas():
    payload, _ = mesclar({}, _whats(data='2026-07-15'), MAPA)
    assert set(payload[0].keys()) == {'data', 'comentario'}, \
        'item novo só com chaves que o updater lê'


def test_data_duplicada_no_sistema_segura_o_texto_com_pendencia():
    sistema = _sistema(comentario=None)
    payload, rel = mesclar(sistema, _whats(), MAPA,
                           datas_duplicadas={'2026-07-14'})
    assert payload == [], 'texto não entra em dia com RDO duplicado'
    assert any('mais de um RDO' in p for p in rel['pendencias'])


def test_data_duplicada_deixa_fotos_e_apontamentos_passarem():
    sistema = _sistema(comentario=None)
    whats = _whats(fotos=[{'arquivo': '1.jpg', 'legenda': 'x'}],
                   apontamentos=[{'tarefa_mpp': -208, 'pct': 40}])
    payload, rel = mesclar(sistema, whats, MAPA,
                           datas_duplicadas={'2026-07-14'})
    item = payload[0]
    assert 'comentario' not in item
    assert item['fotos'] and item['apontamentos']


def test_politica_sistema_mantem_o_texto_do_sistema_sem_pendencia():
    sistema = _sistema(comentario='Registro manual curado.')
    payload, rel = mesclar(sistema, _whats(), MAPA,
                           politica_conflito='sistema')
    assert payload == [], 'nada a aplicar: sistema vence e nada mais mudou'
    assert rel['pendencias'] == []
    assert any('mantido o texto do SISTEMA' in a for a in rel['avisos'])


def test_politica_sistema_ainda_preenche_o_que_esta_vazio():
    sistema = _sistema(comentario=None)
    payload, rel = mesclar(sistema, _whats(), MAPA,
                           politica_conflito='sistema')
    assert payload[0]['comentario'] == 'Execução do forro.', \
        'sistema vence CONFLITO; campo vazio continua sendo completado'


def test_politica_sistema_rebaixa_duplicada_para_aviso():
    sistema = _sistema(comentario=None)
    payload, rel = mesclar(sistema, _whats(), MAPA,
                           datas_duplicadas={'2026-07-14'},
                           politica_conflito='sistema')
    assert rel['pendencias'] == []
    assert any('mais de um RDO' in a for a in rel['avisos'])
