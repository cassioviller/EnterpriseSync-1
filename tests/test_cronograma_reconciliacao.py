"""M05 Task 1 — reconciliação determinística por cascata (serviço PURO).

Contrato (plano 2026-07-20-modulo-05-implementacao-reconciliacao.md §4.1):
entrada = tarefas VIVAS (dicts extraídos pelo chamador) + json_normalizado
do M04; saída = RelatorioDiff {versao, resumo, mapeamentos,
sugestoes_split_merge}. Cascata: 1 mpp_uid · 2 wbs · 3 caminho · 4 nome
único · 5 fingerprint · 6 score composto · 7 resto. Ambíguo e split/merge
NUNCA se auto-aplicam: só marcam decisao_requerida.
"""
import json
import os
import re
import subprocess
import sys

from services.cronograma_reconciliacao import (
    RECONCILIADOR_VERSAO,
    SCORE_AMBIGUO,
    SCORE_MATCH,
    reconciliar,
)

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# Helpers: tarefa atual (shape TarefaAtual) e tarefa normalizada (M04).
# Defaults neutros: sem chaves fortes, sem datas/duração (score baixo).
# ---------------------------------------------------------------------------

def _atual(tid, nome, **kw):
    a = {
        'id': tid, 'mpp_uid': None, 'wbs_codigo': None,
        'nome_normalizado': nome, 'caminho': nome, 'fingerprint': None,
        'tarefa_pai_id': None, 'data_inicio': None, 'data_fim': None,
        'duracao_dias': None, 'quantidade_total': None,
        'unidade_medida': None, 'predecessoras': [],
    }
    a.update(kw)
    return a


def _novo(chave, nome, **kw):
    n = {
        'chave': chave, 'uid': None, 'wbs': None,
        'nome_normalizado': nome, 'caminho': nome, 'fingerprint': None,
        'pai_chave': None, 'ordem': 0, 'inicio': None, 'fim': None,
        'dias': None, 'quantidade_total': None, 'unidade': None,
        'predecessoras': [],
    }
    n.update(kw)
    return n


def _norm(*tarefas):
    ts = list(tarefas)
    for ordem, t in enumerate(ts):
        t['ordem'] = ordem
    return {'tarefas': ts}


def _por_atual(rel, tid):
    """Mapeamento cujo tarefa_atual_id == tid (deve ser único)."""
    ms = [m for m in rel['mapeamentos'] if m['tarefa_atual_id'] == tid]
    assert len(ms) == 1, f'esperava 1 mapeamento para id {tid}, veio {ms}'
    return ms[0]


def _por_chave(rel, chave):
    ms = [m for m in rel['mapeamentos'] if m['chave_nova'] == chave]
    assert len(ms) == 1, f'esperava 1 mapeamento para chave {chave}, veio {ms}'
    return ms[0]


# ---------------------------------------------------------------------------
# Cascata: um cenário por nível (§17)
# ---------------------------------------------------------------------------

def test_nivel1_mpp_uid_vence_mesmo_com_nome_diferente():
    rel = reconciliar(
        [_atual(1, 'fundacao radier', mpp_uid=7)],
        _norm(_novo('u7', 'cobertura telha metalica', uid=7)))
    m = _por_atual(rel, 1)
    assert m['nivel_match'] == 'mpp_uid'
    assert m['chave_nova'] == 'u7'
    assert 'renomeada' in m['tipo']
    assert m['decisao_requerida'] is False


def test_nivel1_uid_zero_e_valido():
    rel = reconciliar(
        [_atual(1, 'marco inicial', mpp_uid=0)],
        _norm(_novo('u0', 'marco de inicio da obra', uid=0)))
    assert _por_atual(rel, 1)['nivel_match'] == 'mpp_uid'


def test_nivel2_wbs_quando_nao_ha_uid():
    rel = reconciliar(
        [_atual(1, 'impermeabilizacao baldrame', wbs_codigo='1.2')],
        _norm(_novo('w12', 'cobertura telha metalica', wbs='1.2')))
    m = _por_atual(rel, 1)
    assert m['nivel_match'] == 'wbs'
    assert m['chave_nova'] == 'w12'


def test_nivel2_wbs_vazio_nunca_casa():
    rel = reconciliar(
        [_atual(1, 'impermeabilizacao baldrame', wbs_codigo='')],
        _norm(_novo('n1', 'cobertura telha metalica', wbs='')))
    assert _por_atual(rel, 1)['tipo'] == ['removida']
    assert _por_chave(rel, 'n1')['tipo'] == ['nova']


def test_nivel3_caminho_roda_antes_do_nome_unico():
    # Nome idêntico e único casaria no nível 4; caminho igual casa antes (3).
    rel = reconciliar(
        [_atual(1, 'alvenaria', caminho='terreo/alvenaria')],
        _norm(_novo('n1', 'alvenaria', caminho='terreo/alvenaria')))
    m = _por_atual(rel, 1)
    assert m['nivel_match'] == 'caminho'
    assert m['tipo'] == ['exata']


def test_nivel4_nome_unico_com_caminho_diferente():
    rel = reconciliar(
        [_atual(1, 'pintura', caminho='bloco a/pintura')],
        _norm(_novo('n1', 'pintura', caminho='bloco b/pintura')))
    m = _por_atual(rel, 1)
    assert m['nivel_match'] == 'nome_unico'
    assert 'exata' in m['tipo']


def test_nivel4_nome_repetido_e_pulado_e_vira_decisao_manual():
    # 2 atuais com o mesmo nome × 1 novo idêntico: o nível 4 exige unicidade
    # nos DOIS lados; sem datas o score fica na faixa ambígua ⇒ decisão manual.
    rel = reconciliar(
        [_atual(1, 'forma pilar', caminho='terreo/forma pilar'),
         _atual(2, 'forma pilar', caminho='superior/forma pilar')],
        _norm(_novo('n1', 'forma pilar', caminho='cobertura/forma pilar')))
    m1, m2 = _por_atual(rel, 1), _por_atual(rel, 2)
    for m in (m1, m2):
        assert m['tipo'] == ['ambigua']
        assert m['decisao_requerida'] is True
        assert [c['chave_nova'] for c in m['candidatos']] == ['n1']
    assert _por_chave(rel, 'n1')['tipo'] == ['nova']
    assert rel['resumo']['ambiguas'] == 2


def test_nivel5_fingerprint_quando_nome_mudou():
    rel = reconciliar(
        [_atual(1, 'alvenaria bloco ceramico', fingerprint='deadbeef12345678')],
        _norm(_novo('n1', 'vedacao em bloco ceramico',
                    fingerprint='deadbeef12345678')))
    m = _por_atual(rel, 1)
    assert m['nivel_match'] == 'fingerprint'
    assert 'renomeada' in m['tipo']


def test_nivel6_score_unico_alto_casa_sem_decisao():
    rel = reconciliar(
        [_atual(1, 'montagem de paineis',
                data_inicio='2026-07-01', data_fim='2026-07-10',
                duracao_dias=8)],
        _norm(
            _novo('n1', 'montagem de paineis do terreo',
                  inicio='2026-07-05', fim='2026-07-12', dias=8),
            _novo('n2', 'cobertura telha metalica')))
    m = _por_atual(rel, 1)
    assert m['nivel_match'] == 'score'
    assert m['chave_nova'] == 'n1'
    assert m['score'] is not None and m['score'] >= SCORE_MATCH
    assert m['decisao_requerida'] is False
    assert _por_chave(rel, 'n2')['tipo'] == ['nova']


def test_nivel6_dois_altos_viram_ambigua_nunca_auto_aplicada():
    rel = reconciliar(
        [_atual(1, 'pintura interna',
                data_inicio='2026-07-01', data_fim='2026-07-10',
                duracao_dias=8)],
        _norm(
            _novo('n1', 'pintura interna 1',
                  inicio='2026-07-01', fim='2026-07-10', dias=8),
            _novo('n2', 'pintura interna 2',
                  inicio='2026-07-01', fim='2026-07-10', dias=8)))
    m = _por_atual(rel, 1)
    assert m['tipo'] == ['ambigua']
    assert m['decisao_requerida'] is True
    assert m['chave_nova'] is None  # NUNCA aplica sozinho
    assert [c['chave_nova'] for c in m['candidatos']] == ['n1', 'n2']
    assert all(c['score'] >= SCORE_MATCH for c in m['candidatos'])
    # Os dois novos seguem disponíveis como 'nova' até a decisão manual.
    assert _por_chave(rel, 'n1')['tipo'] == ['nova']
    assert _por_chave(rel, 'n2')['tipo'] == ['nova']


def test_nivel6_faixa_media_e_ambigua():
    rel = reconciliar(
        [_atual(1, 'montagem de paineis')],
        _norm(_novo('n1', 'montagem de paineis do terreo')))
    m = _por_atual(rel, 1)
    assert m['tipo'] == ['ambigua']
    assert SCORE_AMBIGUO <= m['score'] < SCORE_MATCH


def test_nivel7_resto_novas_e_removidas():
    rel = reconciliar(
        [_atual(1, 'impermeabilizacao baldrame')],
        _norm(_novo('n1', 'cobertura telha metalica')))
    mr = _por_atual(rel, 1)
    assert mr['tipo'] == ['removida']
    assert mr['decisao_requerida'] is False
    mn = _por_chave(rel, 'n1')
    assert mn['tipo'] == ['nova']
    assert mn['tarefa_atual_id'] is None
    assert rel['resumo']['novas'] == 1
    assert rel['resumo']['removidas'] == 1


def test_removida_com_nome_colidido_vira_revisao_manual():
    rel = reconciliar(
        [_atual(1, 'servicos gerais'), _atual(2, 'servicos gerais'),
         _atual(3, 'limpeza final')],
        _norm())
    assert _por_atual(rel, 1)['tipo'] == ['revisao_manual']
    assert _por_atual(rel, 1)['decisao_requerida'] is True
    assert _por_atual(rel, 2)['tipo'] == ['revisao_manual']
    assert _por_atual(rel, 3)['tipo'] == ['removida']
    assert rel['resumo']['revisao_manual'] == 2
    assert rel['resumo']['removidas'] == 1


# ---------------------------------------------------------------------------
# Classificações cumulativas sobre pares casados
# ---------------------------------------------------------------------------

def test_cumulativos_todas_as_alteracoes_no_mesmo_par():
    atuais = [
        _atual(10, 'estrutura metalica', mpp_uid=1),
        _atual(11, 'cobertura', mpp_uid=2, tarefa_pai_id=10,
               data_inicio='2026-07-01', data_fim='2026-07-05',
               duracao_dias=4, quantidade_total=100, unidade_medida='m2',
               predecessoras=[10]),
    ]
    rel = reconciliar(atuais, _norm(
        _novo('u1', 'estrutura metalica', uid=1),
        _novo('u2', 'cobertura metalica', uid=2, pai_chave=None,
              inicio='2026-07-10', fim='2026-07-20', dias=9,
              quantidade_total=120, unidade='kg', predecessoras=[])))
    m = _por_atual(rel, 11)
    assert m['nivel_match'] == 'mpp_uid'
    for rotulo in ('renomeada', 'movida_hierarquia', 'datas_alteradas',
                   'duracao_alterada', 'predecessoras_alteradas',
                   'quantidade_alterada', 'unidade_alterada'):
        assert rotulo in m['tipo'], f'{rotulo} ausente de {m["tipo"]}'
    d = m['detalhes']
    assert (d['nome_de'], d['nome_para']) == ('cobertura', 'cobertura metalica')
    assert (d['pai_de'], d['pai_para']) == ('u1', None)
    assert d['datas_de'] == ['2026-07-01', '2026-07-05']
    assert d['datas_para'] == ['2026-07-10', '2026-07-20']
    assert (d['duracao_de'], d['duracao_para']) == (4, 9)
    assert d['predecessoras_de'] == ['u1']
    assert d['predecessoras_para'] == []
    assert (d['quantidade_de'], d['quantidade_para']) == (100, 120)
    assert (d['unidade_de'], d['unidade_para']) == ('m2', 'kg')
    assert rel['resumo']['renomeadas'] == 1
    assert rel['resumo']['alteracoes'] == {
        'datas': 1, 'duracao': 1, 'predecessoras': 1}


def test_par_identico_e_exata_sem_alteracoes():
    rel = reconciliar(
        [_atual(1, 'alvenaria', mpp_uid=5,
                data_inicio='2026-07-01', data_fim='2026-07-05',
                duracao_dias=4)],
        _norm(_novo('u5', 'alvenaria', uid=5,
                    inicio='2026-07-01', fim='2026-07-05', dias=4)))
    m = _por_atual(rel, 1)
    assert m['tipo'] == ['exata']
    assert m['detalhes'] == {}


def test_duracao_18_igual_18_ponto_0():
    rel = reconciliar(
        [_atual(1, 'alvenaria', mpp_uid=5, duracao_dias=18)],
        _norm(_novo('u5', 'alvenaria', uid=5, dias=18.0)))
    assert 'duracao_alterada' not in _por_atual(rel, 1)['tipo']


# ---------------------------------------------------------------------------
# Split/merge: SÓ sugestão, decisão sempre manual (§4.1)
# ---------------------------------------------------------------------------

def test_split_gabarito_em_duas_novas_sob_o_mesmo_pai():
    rel = reconciliar(
        [_atual(5, 'estrutura')],
        _norm(
            _novo('n1', 'estrutura fabricacao paineis parede'),
            _novo('n2', 'estrutura montagem lajes cobertura')))
    assert rel['sugestoes_split_merge'] == [{
        'tipo': 'dividida', 'antiga_id': 5, 'novas_chaves': ['n1', 'n2']}]
    ma = _por_atual(rel, 5)
    assert ma['tipo'] == ['dividida']
    assert ma['decisao_requerida'] is True
    for chave in ('n1', 'n2'):
        mn = _por_chave(rel, chave)
        assert mn['tipo'] == ['nova']
        assert mn['decisao_requerida'] is True


def test_fusao_espelho_duas_antigas_numa_nova():
    rel = reconciliar(
        [_atual(20, 'piso terreo'), _atual(21, 'piso superior')],
        _norm(_novo('nf', 'piso terreo superior regularizacao contrapiso')))
    assert rel['sugestoes_split_merge'] == [{
        'tipo': 'fundida', 'nova_chave': 'nf', 'antigas_ids': [20, 21]}]
    for tid in (20, 21):
        ma = _por_atual(rel, tid)
        assert ma['tipo'] == ['fundida']
        assert ma['decisao_requerida'] is True
    assert _por_chave(rel, 'nf')['decisao_requerida'] is True


def test_split_exige_pelo_menos_duas_filhas():
    # 1 removida cujo nome é prefixo de UMA nova só: sem sugestão.
    rel = reconciliar(
        [_atual(5, 'estrutura')],
        _norm(_novo('n1', 'estrutura fabricacao paineis parede')))
    assert rel['sugestoes_split_merge'] == []


# ---------------------------------------------------------------------------
# Determinismo, pureza e fronteira (multitenant é do chamador)
# ---------------------------------------------------------------------------

def _cenario_rico():
    atuais = [
        _atual(1, 'fundacao radier', mpp_uid=7),
        _atual(2, 'impermeabilizacao baldrame', wbs_codigo='1.2'),
        _atual(3, 'pintura', caminho='bloco a/pintura'),
        _atual(4, 'alvenaria bloco ceramico', fingerprint='deadbeef12345678'),
        _atual(5, 'estrutura'),
        _atual(6, 'pintura interna',
               data_inicio='2026-07-01', data_fim='2026-07-10',
               duracao_dias=8),
        _atual(7, 'servicos gerais'),
        _atual(8, 'servicos gerais'),
    ]
    normalizado = _norm(
        _novo('u7', 'fundacao em radier', uid=7),
        _novo('w12', 'impermeabilizacao de baldrames', wbs='1.2'),
        _novo('n3', 'pintura', caminho='bloco b/pintura'),
        _novo('n4', 'vedacao em bloco ceramico',
              fingerprint='deadbeef12345678'),
        _novo('n5a', 'estrutura fabricacao paineis parede'),
        _novo('n5b', 'estrutura montagem lajes cobertura'),
        _novo('n6a', 'pintura interna 1',
              inicio='2026-07-01', fim='2026-07-10', dias=8),
        _novo('n6b', 'pintura interna 2',
              inicio='2026-07-01', fim='2026-07-10', dias=8),
    )
    return atuais, normalizado


def test_determinismo_dupla_execucao_bit_a_bit():
    atuais, normalizado = _cenario_rico()
    r1 = reconciliar(atuais, normalizado)
    r2 = reconciliar(atuais, normalizado)
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)


def test_determinismo_independe_da_ordem_das_atuais():
    atuais, normalizado = _cenario_rico()
    r1 = reconciliar(atuais, normalizado)
    r2 = reconciliar(list(reversed(atuais)), normalizado)
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)


def test_id_temp_sequencial_e_versao():
    atuais, normalizado = _cenario_rico()
    rel = reconciliar(atuais, normalizado)
    assert rel['versao'] == RECONCILIADOR_VERSAO
    assert [m['id_temp'] for m in rel['mapeamentos']] == list(
        range(len(rel['mapeamentos'])))


def test_nao_inventa_matches_fora_do_que_recebeu():
    # Multitenant é responsabilidade do CHAMADOR: o serviço só enxerga as
    # listas recebidas e nunca referencia id/chave que não veio nelas.
    atuais, normalizado = _cenario_rico()
    rel = reconciliar(atuais, normalizado)
    ids_validos = {a['id'] for a in atuais} | {None}
    chaves_validas = {t['chave'] for t in normalizado['tarefas']} | {None}
    for m in rel['mapeamentos']:
        assert m['tarefa_atual_id'] in ids_validos
        assert m['chave_nova'] in chaves_validas
        for c in m['candidatos']:
            assert c['chave_nova'] in chaves_validas


def test_entradas_vazias():
    vazio = reconciliar([], _norm())
    assert vazio['mapeamentos'] == []
    assert vazio['sugestoes_split_merge'] == []
    assert vazio['resumo']['exatas'] == 0

    so_novas = reconciliar([], _norm(_novo('n1', 'alvenaria')))
    assert so_novas['resumo']['novas'] == 1

    so_removidas = reconciliar([_atual(1, 'alvenaria')], _norm())
    assert so_removidas['resumo']['removidas'] == 1


def test_import_lint_modulo_puro_em_subprocess():
    """O módulo não pode arrastar flask/sqlalchemy/models/app/requests."""
    codigo = (
        "import services.cronograma_reconciliacao, sys; "
        "proibidos=[m for m in sys.modules "
        "if m.split('.')[0] in ('flask','sqlalchemy','requests','models','app')]; "
        "assert not proibidos, proibidos"
    )
    r = subprocess.run([sys.executable, '-c', codigo], cwd=RAIZ,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_import_lint_fonte_nao_menciona_orm():
    fonte = open(os.path.join(
        RAIZ, 'services', 'cronograma_reconciliacao.py'),
        encoding='utf-8').read()
    proibido = re.compile(
        r'^\s*(from|import)\s+(models|app|flask|sqlalchemy|extensions)\b',
        re.MULTILINE)
    assert not proibido.search(fonte)
