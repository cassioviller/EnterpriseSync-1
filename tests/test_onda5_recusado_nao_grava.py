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
# ---------------------------------------------------------------------------
# Task 3 — o portal para de ser administrável por qualquer um
# ---------------------------------------------------------------------------

def _usuario_funcionario(admin_id):
    from werkzeug.security import generate_password_hash

    from models import TipoUsuario, Usuario
    marca = f'func_{uuid.uuid4().hex[:8]}'
    usuario = Usuario(
        username=marca, email=f'{marca}@test.local', nome='Func Portal',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
        admin_id=admin_id, versao_sistema='v2')
    db.session.add(usuario)
    db.session.commit()
    return usuario.id


def test_funcionario_nao_administra_o_portal():
    """🔴 `portal_obras_views.py` — `toggle_portal` e `gerar_medicao` só com
    `@login_required`: qualquer FUNCIONARIO ligava o portal (recarimbando o
    token +180 dias) ou criava MedicaoObra. A prova é no banco."""
    from models import MedicaoObra, Obra

    with app.app_context():
        t = um_tenant('onda5_portal', com_fatos=False)
        admin_id, obra_id = t.admin_id, t.obra_id
        func_user_id = _usuario_funcionario(admin_id)
        obra = db.session.get(Obra, obra_id)
        portal_antes = bool(obra.portal_ativo)
        expira_antes = obra.token_cliente_expira_em
        medicoes_antes = MedicaoObra.query.filter_by(admin_id=admin_id).count()

    cliente = cliente_de(func_user_id)
    r1 = cliente.post(f'/portal/obra/{obra_id}/portal-toggle')
    r2 = cliente.post(f'/portal/obra/{obra_id}/medicao/gerar')
    assert r1.status_code in (302, 403) and r2.status_code in (302, 403)

    with app.app_context():
        obra = db.session.get(Obra, obra_id)
        assert bool(obra.portal_ativo) == portal_antes, (
            'FUNCIONARIO ligou/desligou o portal do cliente')
        assert obra.token_cliente_expira_em == expira_antes, (
            'FUNCIONARIO recarimbou a validade do token')
        medicoes_depois = MedicaoObra.query.filter_by(
            admin_id=admin_id).count()
        assert medicoes_depois == medicoes_antes, (
            'FUNCIONARIO criou MedicaoObra pelo portal')


def test_upload_do_portal_tem_teto_proprio():
    """🔴 `portal_obras_views.py:668` — o teto vinha de MAX_CONTENT_LENGTH
    (64 MB desde app.py:159): o fallback de 5 MB era código morto, e a rota
    anônima gravava blobs de 64 MB no volume a cada requisição."""
    import portal_obras_views
    teto = getattr(portal_obras_views, 'PORTAL_COMPROVANTE_MAX_BYTES', None)
    assert teto == 5 * 1024 * 1024, (
        'o teto do comprovante do portal não é mais os 5 MB declarados')

    import inspect
    fonte = inspect.getsource(portal_obras_views.upload_comprovante)
    assert 'PORTAL_COMPROVANTE_MAX_BYTES' in fonte, (
        'a rota de comprovante não usa o teto próprio do portal')
    assert 'MAX_CONTENT_LENGTH' not in fonte, (
        'a rota ainda herda o teto global de 64 MB')


def test_caminho_de_relatorio_nao_sai_de_static():
    """🔴 `portal_obras_views.py:958` — `os.path.join` sem checar que o
    resultado fica sob `static/`: um `../` na coluna de 500 chars viraria
    leitor de arquivo arbitrário."""
    import portal_obras_views

    with app.app_context():
        with app.test_request_context():
            sob = portal_obras_views._caminho_sob_static
            assert sob('../../etc/passwd') is None, (
                'um ../ escapou de static/')
            assert sob('/etc/passwd') is None, (
                'caminho absoluto escapou de static/')
            valido = sob('relatorios/qualquer.pdf')
            assert valido is not None and 'static' in valido


def test_tentativa_no_portal_deixa_exatamente_um_evento():
    """🔴 A trilha era registrada na entrada e 'persistida no commit adiante':
    retorno antecipado descartava o evento, e o ramo de governança registrava
    DE NOVO — dobrado. A regra: um evento por tentativa, olhado no banco."""
    from test_fase3_portal_seguranca import _admin, _compra, _obra_com_token

    from models import PortalAcessoEvento

    with app.app_context():
        admin = _admin()
        obra = _obra_com_token(admin.id)
        compra = _compra(admin.id, obra.id)
        token, oid, cid = obra.token_cliente, obra.id, compra.id

    anon = app.test_client()
    anon.post(f'/portal/obra/{token}/compra/{cid}/aprovar')

    with app.app_context():
        eventos = PortalAcessoEvento.query.filter_by(
            obra_id=oid, acao='compra_aprovar').count()
        assert eventos == 1, f'{eventos} eventos para 1 tentativa'

    # Segunda tentativa: idempotente — retorno antecipado que antes
    # DESCARTAVA a trilha.
    anon.post(f'/portal/obra/{token}/compra/{cid}/aprovar')

    with app.app_context():
        eventos = PortalAcessoEvento.query.filter_by(
            obra_id=oid, acao='compra_aprovar').all()
        assert len(eventos) == 2, (
            f'{len(eventos)} eventos para 2 tentativas — o retorno '
            'antecipado seguiu descartando (ou dobrando) a trilha')
        assert any((e.detalhes or {}).get('resultado') == 'ja_aprovada'
                   for e in eventos), 'a tentativa idempotente ficou sem trilha'


# ---------------------------------------------------------------------------
# Task 4 — as duas entregas da Fase 6 chegam à tela
# ---------------------------------------------------------------------------

def test_revisao_que_muda_so_o_preco_aparece_no_diff():
    """🔴 `services/proposta_diff.py:88` — lê `subtotal`, NULL fora da Task #89.

    Revisão que muda só `preco_unitario` saía como "mantido", com impacto
    R$ 0,00. `PropostaItem.subtotal_calculado` existe exatamente para isso.
    """
    import inspect

    from services import proposta_diff
    fonte = inspect.getsource(proposta_diff)
    assert 'subtotal_calculado' in fonte, (
        'o diff ainda lê `subtotal`, que é NULL para a maioria dos itens')
    for numero, linha in enumerate(fonte.splitlines(), start=1):
        if '.subtotal' in linha and 'subtotal_calculado' not in linha:
            raise AssertionError(
                f'proposta_diff:{numero} ainda lê .subtotal cru: '
                f'{linha.strip()[:80]}')


def test_o_diff_ve_o_item_sem_snapshot_de_subtotal():
    """A prova pelo dado: dois itens iguais exceto o preço, ambos com
    `subtotal` NULL (o caso da maioria) — o diff tem que acusar alteração."""
    from types import SimpleNamespace

    from services.proposta_diff import diff_versoes

    def item(id_, preco):
        return SimpleNamespace(
            id=id_, descricao='Alvenaria', unidade='m2', item_numero=1,
            quantidade=10, preco_unitario=preco, subtotal=None,
            subtotal_calculado=10 * preco,
            item_origem_id=None, servico_id=None, template_origem_id=None)

    antes = item(1, 100)
    depois = item(2, 150)
    depois.item_origem_id = 1
    linhas = diff_versoes(SimpleNamespace(itens=[antes]),
                          SimpleNamespace(itens=[depois]))
    alterados = [l for l in linhas if l['situacao'] == 'alterado']
    assert alterados, (
        'mudança só de preço saiu como "mantido" — impacto R$ 0,00')
    assert alterados[0]['delta_valor'] == 500


def test_a_tela_de_comparar_e_alcancavel_pela_navegacao():
    """Entrega inalcançável não é entrega."""
    import subprocess

    # O grep literal do plano passava vazio: os únicos hits eram COMENTÁRIOS
    # dentro dos próprios comparar.html. Link de verdade é url_for fora deles.
    for endpoint in ('orcamentos.comparar', 'propostas.comparar'):
        saida = subprocess.run(
            ['grep', '-rl', f"url_for('{endpoint}'", 'templates/'],
            capture_output=True, text=True).stdout
        arquivos = [a for a in saida.splitlines()
                    if not a.endswith('/comparar.html')]
        assert arquivos, (
            f'nenhum template linka {endpoint} — a Task 12 da Fase 6 '
            'segue inalcançável')
