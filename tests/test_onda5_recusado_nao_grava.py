"""Onda 5 — o recusado para de ser gravado.

A regra dos testes desta onda: o que se afirma é olhado NO BANCO. Código de
status 400 não prova que nada foi gravado — foi exatamente essa confusão que
deixou o `_com_undo` empilhar edições recusadas.
"""
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from helpers_tenant import cliente_de, um_tenant

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-onda5-recusado'
    yield


# ---------------------------------------------------------------------------
# Task 1 — o traceback
# ---------------------------------------------------------------------------

def test_nenhum_traceback_fora_de_log():
    """🔴 `ponto_views.py:611` e `equipe_views.py:91` — `format_exc()` no HTML.

    Expunha caminhos, frames e SQL COM PARÂMETROS VINCULADOS a qualquer
    usuário autenticado. O critério é o do fecho da onda: `format_exc` só
    pode existir DENTRO de chamada de log — o plano literal proibia qualquer
    ocorrência, mas isso reprovaria os usos só-de-log que o próprio fecho
    permite.
    """
    import inspect

    import equipe_views
    import ponto_views

    for modulo in (ponto_views, equipe_views):
        fonte = inspect.getsource(modulo)
        for numero, linha in enumerate(fonte.splitlines(), start=1):
            if 'format_exc' not in linha:
                continue
            assert 'logger.' in linha or 'logging.' in linha, (
                f'{modulo.__name__}:{numero}: format_exc fora de log — '
                f'traceback pode vazar para a resposta → {linha.strip()[:100]}')


def test_ponto_com_erro_mostra_mensagem_nao_stack():
    """A prova pela porta: mesmo quebrando, a resposta não traz frames."""
    with app.app_context():
        t = um_tenant('onda5_ponto', com_fatos=False)
        admin_id = t.admin_id

    resposta = cliente_de(admin_id).get('/ponto/')
    corpo = resposta.get_data(as_text=True)
    for vazamento in ('Traceback (most recent call last)', 'File "/home/',
                      'sqlalchemy.exc'):
        assert vazamento not in corpo, f'{vazamento!r} vazou na resposta'


def test_geofencing_nao_e_pulado_quando_faltam_coordenadas():
    """🔴 `ponto_views.py:2459` — o validador só era chamado quando o cliente
    MANDAVA coordenadas: omitir latitude/longitude pulava o geofencing
    inteiro, tornando o controle consultivo.

    `utils_geofencing.validar_localizacao_na_obra` JÁ implementa a semântica
    certa (default `exigir_localizacao=True`: obra com geofence e sem
    coordenada → recusa; obra sem geofence → passa). A rota tem que chamá-lo
    sempre que há obra, não só quando o cliente coopera.
    """
    import inspect

    import ponto_views
    fonte = inspect.getsource(ponto_views)
    assert ('latitude_func is not None and longitude_func is not None'
            not in fonte), (
        'o geofencing ainda é pulado quando o cliente omite as coordenadas')


def test_obra_com_geofence_recusa_ponto_sem_coordenada():
    """O pino da semântica que a rota passa a usar: com geofence configurado,
    ausência de coordenada RECUSA; sem geofence configurado, passa."""
    from types import SimpleNamespace

    from utils_geofencing import validar_localizacao_na_obra

    obra_com_geofence = SimpleNamespace(
        nome='Obra Cercada', latitude=-23.5505, longitude=-46.6333,
        raio_geofence_metros=100)
    valido, distancia, msg = validar_localizacao_na_obra(
        None, None, obra_com_geofence)
    assert valido is False, 'obra com geofence aceitou ponto sem coordenada'
    assert distancia is None

    obra_sem_geofence = SimpleNamespace(
        nome='Obra Livre', latitude=None, longitude=None,
        raio_geofence_metros=None)
    valido, _, _ = validar_localizacao_na_obra(None, None, obra_sem_geofence)
    assert valido is True, 'obra sem geofence deveria seguir aceitando'


# ---------------------------------------------------------------------------
# Task 2 — a edição recusada
# ---------------------------------------------------------------------------

def _cenario_cronograma(com_vinculo=False):
    """Admin V2 com flag do editor v2 ligada, obra e tarefa reais.

    Reusa o arreio dos testes do editor v2 — mesmo idioma de
    `test_cronograma_undo_api._cenario`.
    """
    from test_cronograma_undo_api import _flag_editor_v2
    from test_cronograma_versao_service import _ambiente, _tarefa

    with app.app_context():
        admin, obra = _ambiente()
        _flag_editor_v2(admin.id, True)
        from datetime import date
        a = _tarefa(obra, admin, 'Fundação', ordem=0, duracao_dias=5,
                    data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 7))
        ctx = {'admin_id': admin.id, 'user_id': admin.id,
               'obra_id': obra.id, 'tarefa_id': a.id,
               'nome_antes': a.nome_tarefa}
        if com_vinculo:
            from models import TarefaVinculo
            b = _tarefa(obra, admin, 'Alvenaria', ordem=1, duracao_dias=3,
                        data_inicio=date(2026, 7, 1),
                        data_fim=date(2026, 7, 3))
            v = TarefaVinculo(admin_id=admin.id, obra_id=obra.id,
                              predecessora_id=a.id, sucessora_id=b.id,
                              tipo='TI', lag_dias=0)
            db.session.add(v)
            db.session.commit()
            ctx['vinculo_id'] = v.id
        return ctx


def test_modo_apontamento_invalido_nao_grava_nada():
    """🔴 `cronograma_views.py` (`atualizar_tarefa`) — `return 400` sem
    rollback.

    O `_com_undo` então commitava (via `registrar_acao`, que autoflusha), e a
    edição recusada era gravada E empilhada no undo. O docstring do decorador
    afirma o contrário como garantia.
    """
    from test_cronograma_endpoints_m05 import _client_como

    from models import TarefaCronograma

    ctx = _cenario_cronograma()
    resposta = _client_como(ctx['user_id']).put(
        f"/cronograma/obra/{ctx['obra_id']}/tarefa/{ctx['tarefa_id']}",
        json={'nome_tarefa': 'NOME NOVO QUE NAO DEVE ENTRAR',
              'modo_apontamento': 'VALOR_INVALIDO'})
    assert resposta.status_code == 400

    with app.app_context():
        depois = db.session.get(TarefaCronograma, ctx['tarefa_id'])
        assert depois.nome_tarefa == ctx['nome_antes'], (
            'a edição recusada foi gravada mesmo assim')


def test_vinculo_recusado_nao_muda_o_tipo():
    """🔴 `atualizar_vinculo` — com payload {tipo válido, lag_dias inválido},
    o `vinculo.tipo` já foi atribuído quando o `return 400` do lag chega:
    TI vira II em silêncio."""
    from test_cronograma_endpoints_m05 import _client_como

    from models import TarefaVinculo

    ctx = _cenario_cronograma(com_vinculo=True)
    resposta = _client_como(ctx['user_id']).put(
        f"/cronograma/obra/{ctx['obra_id']}/vinculo/{ctx['vinculo_id']}",
        json={'tipo': 'II', 'lag_dias': 'nao-e-numero'})
    assert resposta.status_code == 400

    with app.app_context():
        vinculo = db.session.get(TarefaVinculo, ctx['vinculo_id'])
        assert vinculo.tipo == 'TI', (
            f'o vínculo recusado mudou de tipo: TI → {vinculo.tipo}')


def test_o_decorador_garante_a_invariante_que_documenta():
    """A guarda que impede o quarto `return 400` sem rollback de nascer."""
    import inspect

    import cronograma_views
    fonte = inspect.getsource(cronograma_views._com_undo)
    assert '>= 400' in fonte and 'rollback' in fonte, (
        '_com_undo documenta depender do rollback da rota mas não o garante '
        '(a guarda de status >= 400 antes do registrar_acao sumiu)')
