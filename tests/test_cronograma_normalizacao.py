"""M04 — normalização determinística do cronograma bruto.

Contrato (plano 2026-07-20-modulo-04-implementacao-normalizacao.md):
entrada = json_bruto do M03; saída = json_normalizado validado por
schema versionado, com chave (uid→wbs→fp), caminho, fingerprint,
categoria sugerida e avisos determinísticos.
"""
import json
import os
import re
import subprocess
import sys

import pytest

from services.cronograma_normalizacao import (
    NORMALIZADOR_VERSAO,
    NormalizacaoError,
    caminho_hierarquico,
    classificar,
    fingerprint,
    normalizar,
    normalizar_nome,
)

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XML_REAL = os.path.join(RAIZ, 'CRONOGRAMA 16.07.xml')


# ---------------------------------------------------------------------------
# Helpers: bruto mínimo válido contra o schema (todos os campos do M03).
# ---------------------------------------------------------------------------

def _t(tid, **kw):
    t = {
        'id': tid, 'uid': tid, 'wbs': None, 'outline': 1,
        'nome': f'Tarefa {tid}', 'inicio': '2026-07-01', 'fim': '2026-07-02',
        'dias': 2.0, 'pct_project': 0.0, 'resumo': False, 'marco': False,
        'predecessoras': [], 'notas': None,
    }
    t.update(kw)
    return t


def _bruto(*tarefas):
    return {'projeto': {'nome': 'Obra Teste', 'data_status': None},
            'tarefas': list(tarefas)}


def _avisos(res, codigo):
    return [a for a in res['avisos'] if a['codigo'] == codigo]


# ---------------------------------------------------------------------------
# normalizar_nome
# ---------------------------------------------------------------------------

CASOS_NOME = [
    ('Ferragens p/ fundação', 'FERRAGENS P FUNDACAO'),   # acento + '/'
    ('Baia 01', 'BAIA 01'),                               # dígito significativo
    ('  Estudo   de  Solo ', 'ESTUDO DE SOLO'),           # espaços múltiplos
    ('pintura externa', 'PINTURA EXTERNA'),               # caixa
    ('Alvenaria (2)', 'ALVENARIA'),                       # sufixo de duplicata
    ('Baia 02 (3)', 'BAIA 02'),                           # sufixo, dígito fica
    ('Instalação Elétrica', 'INSTALACAO ELETRICA'),
    ('Concreto-magro, usinado', 'CONCRETO MAGRO USINADO'),
    ('Mob.\x07 Equipe\x00', 'MOB EQUIPE'),                # control chars fora
    ('Concreto (magro) especial', 'CONCRETO MAGRO ESPECIAL'),
]


@pytest.mark.parametrize('bruto,esperado', CASOS_NOME)
def test_normalizar_nome_tabela(bruto, esperado):
    assert normalizar_nome(bruto) == esperado


@pytest.mark.parametrize('bruto,_', CASOS_NOME)
def test_normalizar_nome_idempotente(bruto, _):
    uma = normalizar_nome(bruto)
    assert normalizar_nome(uma) == uma


# ---------------------------------------------------------------------------
# fingerprint / caminho
# ---------------------------------------------------------------------------

def test_fingerprint_estavel_e_16_hex():
    a = fingerprint('FERRAGENS P FUNDACAO', 'OBRA/FUNDACAO', 6.0)
    b = fingerprint('FERRAGENS P FUNDACAO', 'OBRA/FUNDACAO', 6.0)
    assert a == b
    assert re.fullmatch(r'[0-9a-f]{16}', a)


def test_fingerprint_sensivel_a_nome_pai_e_dias():
    base = fingerprint('ALVENARIA', 'OBRA/BAIA 01', 3.0)
    assert fingerprint('ALVENARIA X', 'OBRA/BAIA 01', 3.0) != base
    assert fingerprint('ALVENARIA', 'OBRA/BAIA 02', 3.0) != base
    assert fingerprint('ALVENARIA', 'OBRA/BAIA 01', 4.0) != base


def test_fingerprint_nao_muda_quando_so_datas_mudam():
    """Datas ficam FORA da fórmula: replanejamento não pode trocar a identidade."""
    t1 = _t(1, inicio='2026-07-01', fim='2026-07-02')
    t2 = _t(1, inicio='2026-09-10', fim='2026-09-30')
    fp1 = normalizar(_bruto(t1))['tarefas'][0]['fingerprint']
    fp2 = normalizar(_bruto(t2))['tarefas'][0]['fingerprint']
    assert fp1 == fp2


def test_caminho_hierarquico():
    assert caminho_hierarquico('FUNDACAO', 'OBRA') == 'OBRA/FUNDACAO'
    assert caminho_hierarquico('OBRA', None) == 'OBRA'


# ---------------------------------------------------------------------------
# classificar (tabela generalizada de etapa_de, sem casos da obra)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('nome,categoria', [
    ('Instalação Hidráulica', 'HIDRO'),
    ('Instalação Elétrica e Iluminação', 'ELET'),
    ('Estudo de Solo SPT', 'PRELIM'),
    ('Execução de projetos LSF', 'PRELIM'),   # 'projetos' vence 'lsf' (ordem)
    ('Portões das baias', 'PORTAO'),
    ('Pintura externa', 'PINT'),
    ('Plaqueamento OSB', 'FECHA'),
    ('Montagem LSF', 'ESTLSF'),
    ('Telhado Shingle', 'COBERT'),
    ('Estrutura metálica', 'ESTMET'),
    ('Ferragens p/ fundação', 'FUND'),
    ('Limpeza geral', None),                  # caso da obra excluído da tabela
    ('Fazenda Santa Mônica', None),           # idem
    ('Tarefa qualquer', None),                # sem match ⇒ None, nunca inventa
])
def test_classificar_categoria(nome, categoria):
    r = classificar(_t(1, nome=nome))
    assert r['categoria_sugerida'] == categoria


def test_classificar_propaga_resumo_e_marco():
    r = classificar(_t(1, resumo=True, marco=False))
    assert r['is_resumo'] is True and r['is_marco'] is False


# ---------------------------------------------------------------------------
# chave, pai_chave, hierarquia
# ---------------------------------------------------------------------------

def test_chave_prefere_uid_depois_wbs_depois_fingerprint():
    res = normalizar(_bruto(
        _t(1, uid=100, wbs='1'),
        _t(2, uid=None, wbs='1.2'),
        _t(3, uid=None, wbs=None),
    ))
    t1, t2, t3 = res['tarefas']
    assert t1['chave'] == 'uid:100'
    assert t2['chave'] == 'wbs:1.2'
    assert t3['chave'] == 'fp:' + t3['fingerprint']


def test_hierarquia_por_pilha_de_outline():
    res = normalizar(_bruto(
        _t(0, uid=0, outline=0, nome='Obra', resumo=True),
        _t(1, uid=1, outline=1, nome='Fundação', resumo=True),
        _t(2, uid=2, outline=2, nome='Brocas'),
        _t(3, uid=3, outline=1, nome='Cobertura'),
    ))
    raiz, fund, brocas, cob = res['tarefas']
    assert raiz['pai_chave'] is None          # raiz não tem pai
    assert fund['pai_chave'] == 'uid:0'
    assert brocas['pai_chave'] == 'uid:1'
    assert cob['pai_chave'] == 'uid:0'        # volta de outline fecha a pilha
    assert brocas['caminho'] == 'OBRA/FUNDACAO/BROCAS'
    assert [t['nivel'] for t in res['tarefas']] == [0, 1, 2, 1]
    assert [t['ordem'] for t in res['tarefas']] == [0, 1, 2, 3]


def test_predecessora_resolvida_pela_chave_da_tarefa_alvo():
    res = normalizar(_bruto(
        _t(1, uid=100),
        _t(2, uid=200, predecessoras=[
            {'id': 1, 'uid': 100, 'tipo': 'FS', 'lag_dias': 1.0}]),
    ))
    assert res['tarefas'][1]['predecessoras'] == [
        {'chave': 'uid:100', 'tipo': 'FS', 'lag_dias': 1.0}]


def test_quantidade_e_unidade_sempre_null_no_normalizado():
    """O bruto do M03 não traz quantidade/unidade — saem null, nunca inventados."""
    t = normalizar(_bruto(_t(1)))['tarefas'][0]
    assert t['quantidade_total'] is None and t['unidade'] is None


# ---------------------------------------------------------------------------
# Avisos — um teste por código
# ---------------------------------------------------------------------------

def test_aviso_fim_antes_inicio():
    res = normalizar(_bruto(_t(1, inicio='2026-07-10', fim='2026-07-01')))
    avs = _avisos(res, 'fim_antes_inicio')
    assert [a['tarefa_chave'] for a in avs] == ['uid:1']


def test_aviso_folha_sem_datas_ignora_resumo():
    res = normalizar(_bruto(
        _t(1, resumo=True, inicio=None, fim=None),
        _t(2, inicio=None, fim=None),
    ))
    avs = _avisos(res, 'folha_sem_datas')
    assert [a['tarefa_chave'] for a in avs] == ['uid:2']


def test_aviso_duracao_zero_sem_marco():
    res = normalizar(_bruto(
        _t(1, dias=0.0, marco=False),
        _t(2, dias=0.0, marco=True),      # marco legítimo: sem aviso
    ))
    avs = _avisos(res, 'duracao_zero_sem_marco')
    assert [a['tarefa_chave'] for a in avs] == ['uid:1']


def test_aviso_predecessora_inexistente_descarta_o_vinculo():
    res = normalizar(_bruto(
        _t(1, predecessoras=[{'id': 99, 'uid': 999, 'tipo': 'FS', 'lag_dias': 0.0}]),
    ))
    avs = _avisos(res, 'predecessora_inexistente')
    assert [a['tarefa_chave'] for a in avs] == ['uid:1']
    assert res['tarefas'][0]['predecessoras'] == []


def test_aviso_ciclo_predecessoras():
    res = normalizar(_bruto(
        _t(1, predecessoras=[{'id': 2, 'uid': 2, 'tipo': 'FS', 'lag_dias': 0.0}]),
        _t(2, predecessoras=[{'id': 1, 'uid': 1, 'tipo': 'FS', 'lag_dias': 0.0}]),
    ))
    assert len(_avisos(res, 'ciclo_predecessoras')) == 1


def test_aviso_outline_salto_ainda_pendura_no_ultimo_menor():
    res = normalizar(_bruto(
        _t(0, uid=0, outline=0, nome='Obra', resumo=True),
        _t(1, uid=1, outline=2, nome='Órfã'),   # 0 → 2: saltou o nível 1
    ))
    assert [a['tarefa_chave'] for a in _avisos(res, 'outline_salto')] == ['uid:1']
    assert res['tarefas'][1]['pai_chave'] == 'uid:0'


def test_aviso_nomes_duplicados_mesmo_pai_sem_colisao_de_fingerprint():
    res = normalizar(_bruto(
        _t(0, uid=0, outline=0, nome='Obra', resumo=True),
        _t(1, uid=1, outline=1, nome='Alvenaria', dias=2.0),
        _t(2, uid=2, outline=1, nome='Alvenaria', dias=3.0),   # dias difere ⇒ fp difere
    ))
    assert len(_avisos(res, 'nomes_duplicados_mesmo_pai')) == 1
    assert _avisos(res, 'ambiguidade_potencial') == []


def test_aviso_ambiguidade_potencial_quando_fingerprint_tambem_colide():
    res = normalizar(_bruto(
        _t(0, uid=0, outline=0, nome='Obra', resumo=True),
        _t(1, uid=1, outline=1, nome='Alvenaria', dias=2.0),
        _t(2, uid=2, outline=1, nome='Alvenaria', dias=2.0),   # tudo igual ⇒ mesmo fp
    ))
    assert len(_avisos(res, 'ambiguidade_potencial')) == 1
    assert _avisos(res, 'nomes_duplicados_mesmo_pai') == []


def test_aviso_pct_project_agregado_unico():
    res = normalizar(_bruto(
        _t(1, pct_project=50.0),
        _t(2, pct_project=100.0),
        _t(3, pct_project=0.0),
    ))
    avs = _avisos(res, 'pct_project_sera_ignorado')
    assert len(avs) == 1
    assert avs[0]['tarefa_chave'] is None
    assert '2' in avs[0]['mensagem']


def test_contadores_contam_avisos_por_codigo():
    res = normalizar(_bruto(
        _t(1, inicio=None, fim=None),
        _t(2, pct_project=10.0),
    ))
    c = res['contadores']
    assert c['n_tarefas'] == 2 and c['n_folhas'] == 2
    assert c['n_avisos'] == {'folha_sem_datas': 1, 'pct_project_sera_ignorado': 1}


# ---------------------------------------------------------------------------
# Sanitização
# ---------------------------------------------------------------------------

def test_sanitizacao_trunca_nome_e_notas_e_remove_control_chars():
    res = normalizar(_bruto(
        _t(1, nome='A' * 300, notas='x' * 3000),
        _t(2, nome='Mob.\x07 Equipe'),
    ))
    t1, t2 = res['tarefas']
    assert len(t1['nome_original']) == 255
    assert len(t1['notas']) == 2000
    assert '\x07' not in t2['nome_original']


# ---------------------------------------------------------------------------
# Schema: payload inválido ⇒ NormalizacaoError com o path do erro
# ---------------------------------------------------------------------------

def test_payload_invalido_tarefas_como_string():
    with pytest.raises(NormalizacaoError, match='tarefas'):
        normalizar({'projeto': {'nome': 'X', 'data_status': None}, 'tarefas': 'oops'})


def test_payload_invalido_campo_id_faltando():
    t = _t(1)
    del t['id']
    with pytest.raises(NormalizacaoError, match='tarefas'):
        normalizar(_bruto(t))


# ---------------------------------------------------------------------------
# Determinismo e módulo puro
# ---------------------------------------------------------------------------

def test_determinismo_bit_a_bit_fixture_pequena():
    bruto = _bruto(_t(1), _t(2, pct_project=30.0), _t(3, inicio=None, fim=None))
    assert (json.dumps(normalizar(bruto), sort_keys=True)
            == json.dumps(normalizar(bruto), sort_keys=True))


def test_import_lint_modulo_puro_em_subprocess():
    """O módulo não pode arrastar flask/sqlalchemy/models/app/requests."""
    codigo = (
        "import services.cronograma_normalizacao, sys; "
        "proibidos=[m for m in sys.modules "
        "if m.split('.')[0] in ('flask','sqlalchemy','requests','models','app')]; "
        "assert not proibidos, proibidos"
    )
    r = subprocess.run([sys.executable, '-c', codigo], cwd=RAIZ,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# ---------------------------------------------------------------------------
# Pipeline real: CRONOGRAMA 16.07.xml (103 tarefas, zero perda)
# ---------------------------------------------------------------------------

pytestmark_real = pytest.mark.skipif(
    not os.path.exists(XML_REAL), reason='CRONOGRAMA 16.07.xml ausente')


@pytestmark_real
def test_pipeline_real_16_07_zero_perda_e_chaves_unicas():
    from services.mspdi_parser import parse_mspdi
    bruto = parse_mspdi(XML_REAL)
    res = normalizar(bruto)

    assert res['versao'] == NORMALIZADOR_VERSAO == '1.0'
    tarefas = res['tarefas']
    assert len(tarefas) == 103
    assert res['contadores']['n_tarefas'] == 103
    # zero perda: todo id do bruto está no normalizado, na mesma ordem
    assert [t['id_arquivo'] for t in tarefas] == [t['id'] for t in bruto['tarefas']]

    chaves = [t['chave'] for t in tarefas]
    assert len(set(chaves)) == 103

    # predecessoras 100% resolvidas para chaves existentes
    assert _avisos(res, 'predecessora_inexistente') == []
    universo = set(chaves)
    assert all(p['chave'] in universo
               for t in tarefas for p in t['predecessoras'])

    # n_folhas coerente com o parser
    assert res['contadores']['n_folhas'] == sum(
        1 for t in bruto['tarefas'] if not t['resumo'])


@pytestmark_real
def test_pipeline_real_deterministico_com_dois_parses():
    from services.mspdi_parser import parse_mspdi
    a = json.dumps(normalizar(parse_mspdi(XML_REAL)), sort_keys=True)
    b = json.dumps(normalizar(parse_mspdi(XML_REAL)), sort_keys=True)
    assert a == b
