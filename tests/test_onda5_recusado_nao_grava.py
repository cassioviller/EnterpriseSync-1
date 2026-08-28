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


def test_handler_500_nao_manda_traceback_em_producao():
    """🔴 Achado do grep de fecho: `error_handlers.py` (handler 500 global,
    SEM gate de ambiente) e 5 rotas de `production_routes.py` renderizavam o
    traceback completo em `error.html` — a mesma classe da Task 1, viva em
    TODO 500 do app. O desenho certo já existia em `main.py`: detalhe só
    fora de produção; em produção, o detalhe vive no log."""
    import inspect

    import error_handlers
    import production_routes

    for modulo in (error_handlers, production_routes):
        fonte = inspect.getsource(modulo)
        assert 'error_details=full_error_details,' not in fonte, (
            f'{modulo.__name__}: o traceback ainda vai cru para a resposta, '
            'sem gate de ambiente')
        assert '_detalhes_na_resposta' in fonte, (
            f'{modulo.__name__}: falta o gate de produção nos detalhes')


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


# ---------------------------------------------------------------------------
# Task 5 — o progresso que é apagado e o retrocesso que passa
# ---------------------------------------------------------------------------

def test_toggle_reverso_nao_apaga_progresso_parcial():
    """🔴 `entregas_terceiros.py:340` — o toggle reverso zerava
    `percentual_concluido` de TODA tarefa visível não marcada: subempreitada
    em 45% era apagada no próximo salvamento de RDO que não a marcasse.

    Reverter é desfazer a MARCA (100 + data_entrega_real), não apagar
    progresso parcial — progresso é dado real, não estado do toggle.
    """
    from datetime import date
    from types import SimpleNamespace

    from test_cronograma_versao_service import _ambiente

    from models import TarefaCronograma
    from services.entregas_terceiros import aplicar_entregas_no_rdo

    with app.app_context():
        admin, obra = _ambiente()

        def tarefa_terceiro(pct, entregue):
            t = TarefaCronograma(
                obra_id=obra.id, admin_id=admin.id,
                nome_tarefa=f'Sub {uuid.uuid4().hex[:6]}', ordem=0,
                responsavel='terceiros', duracao_dias=5,
                percentual_concluido=pct,
                data_entrega_real=date(2026, 8, 1) if entregue else None)
            db.session.add(t)
            db.session.flush()
            return t

        em_andamento = tarefa_terceiro(45.0, entregue=False)
        marcada = tarefa_terceiro(100.0, entregue=True)
        db.session.commit()

        rdo_falso = SimpleNamespace(obra_id=obra.id,
                                    data_relatorio=date(2026, 8, 20))
        form = {'terceiros_tarefa_ids_lista[]': [str(em_andamento.id),
                                                 str(marcada.id)],
                'entrega_tarefa_ids[]': []}
        qtd, revertidas = aplicar_entregas_no_rdo(
            rdo_falso, form, admin_id=admin.id)
        db.session.commit()

        depois_45 = db.session.get(TarefaCronograma, em_andamento.id)
        depois_100 = db.session.get(TarefaCronograma, marcada.id)
        assert float(depois_45.percentual_concluido) == 45.0, (
            'o toggle reverso apagou os 45% da subempreitada em andamento')
        assert float(depois_100.percentual_concluido) == 0.0, (
            'desmarcar a tarefa ENTREGUE deve revertê-la para pendente')
        assert depois_100.data_entrega_real is None
        assert revertidas == 1


def test_falha_no_meio_das_entregas_nao_deixa_escrita_parcial():
    """🔴 `entregas_terceiros.py:357` — o `except` devolvia `(0, 0)` DEPOIS
    de os laços já terem mutado `TarefaCronograma` na sessão, e o chamador
    commitava: escrita parcial reportando que nada foi aplicado.

    ⚠️ **Reescrito no fix round de 28/08.** A versão original procurava a
    palavra `rollback` no texto do `except` com `inspect.getsource()`. Passava
    verde sobre um `db.session.rollback()` que era da sessão INTEIRA e apagava
    a transação do chamador — o defeito que o code review encontrou depois do
    gate verde. Um teste que lê o código não vê o que o código faz: agora a
    afirmação é olhada no banco. A cobertura do descarte da transação do
    chamador está em
    `tests/test_onda5_fix_round_edicao_e_rollback.py`.
    """
    from datetime import date
    from types import SimpleNamespace

    from test_cronograma_versao_service import _ambiente

    from models import TarefaCronograma
    from services.entregas_terceiros import aplicar_entregas_no_rdo

    with app.app_context():
        admin, obra = _ambiente()
        alvo = TarefaCronograma(
            obra_id=obra.id, admin_id=admin.id,
            nome_tarefa=f'Sub {uuid.uuid4().hex[:6]}', ordem=0,
            responsavel='terceiros', duracao_dias=5,
            percentual_concluido=0.0)
        db.session.add(alvo)
        db.session.commit()
        alvo_id = alvo.id

        # `rdo` sem `obra_id`: o laço quebra DEPOIS de já ter marcado a
        # tarefa como entregue na sessão.
        rdo_quebrado = SimpleNamespace(data_relatorio=date(2026, 8, 20))
        qtd, revertidas = aplicar_entregas_no_rdo(
            rdo_quebrado, {'entrega_tarefa_ids[]': [str(alvo_id)]},
            admin_id=admin.id)
        assert (qtd, revertidas) == (0, 0)

        db.session.commit()  # o chamador commita, como sempre faz

        depois = db.session.get(TarefaCronograma, alvo_id)
        assert float(depois.percentual_concluido) == 0.0, (
            'a mutação parcial dos laços foi commitada pelo chamador, com a '
            'função reportando (0, 0) — "nada aplicado"')
        assert depois.data_entrega_real is None


def test_regressao_real_depois_de_superexecucao_e_barrada():
    """🔴 `cronograma_apontamento_service.py:397` — `pct_ant` lia só
    `percentual_realizado` (travado em 100) enquanto `recomputar_cadeia`
    prefere `percentual_acumulado`. Depois de uma superexecução (120/100),
    uma regressão real para 110% passava por baixo da guarda
    `RetrocessoNaoPermitido` e gravava +10, que qualquer recompute vira −10.
    """
    from datetime import date

    from test_cronograma_apontamento_service import _rdo, _tarefa
    from test_cronograma_versao_service import _ambiente

    from services.cronograma_apontamento_service import (
        RetrocessoNaoPermitido, registrar_apontamento)

    with app.app_context():
        admin, obra = _ambiente()
        ctx = {'admin_id': admin.id, 'obra_id': obra.id}
        tarefa = _tarefa(ctx, quantidade_total=None)

        rdo1 = _rdo(ctx, date(2026, 8, 10))
        registrar_apontamento(rdo1, tarefa, percentual_acumulado=120.0,
                              admin_id=admin.id, permitir_sobreexecucao=True)
        db.session.commit()

        rdo2 = _rdo(ctx, date(2026, 8, 12))
        # 110 ainda é sobre-execução (>100), então o chamador a confirma — e
        # é exatamente assim que a regressão real passava por baixo da guarda
        # de retrocesso: 110 < 120 (acumulado), mas o pct_ant lido era o
        # realizado travado em 100, e 110 > 100 não disparava nada.
        with pytest.raises(RetrocessoNaoPermitido):
            registrar_apontamento(rdo2, tarefa, percentual_acumulado=110.0,
                                  admin_id=admin.id,
                                  permitir_sobreexecucao=True)
        db.session.rollback()


def test_reuso_por_chave_natural_restaura_a_tarefa_arquivada():
    """🔴 `cronograma_proposta.py:602`/`:675` — os ramos de reúso por chave
    natural reaproveitavam a tarefa casada SEM restaurar `ativa`:
    item suprimido e re-adicionado como novo ficava sem tarefa viva, em
    silêncio (`natural_key_index` não filtra `ativa` — casa a arquivada).
    """
    import inspect

    from services import cronograma_proposta

    fonte = inspect.getsource(cronograma_proposta)
    reusos = []
    for numero, linha in enumerate(fonte.splitlines(), start=1):
        if '— reuso' in linha or '- reusar' in linha.lower() \
                or 'reusar' in linha.lower():
            reusos.append(numero)
    assert len(reusos) >= 2, 'os dois ramos de reúso sumiram do fonte?'

    assert fonte.count('.ativa = True') >= 2, (
        'os ramos de reúso não restauram `ativa` — item suprimido e '
        're-adicionado fica sem tarefa viva, em silêncio')


# ---------------------------------------------------------------------------
# Task 6 — os RDOs que quebram, duplicam ou perdem dado
# ---------------------------------------------------------------------------

def _rdo_de_ambiente():
    """Admin V2 + obra + RDO reais, pelo arreio existente."""
    from datetime import date

    from test_cronograma_apontamento_service import _rdo
    from test_cronograma_versao_service import _ambiente

    admin, obra = _ambiente()
    ctx = {'admin_id': admin.id, 'obra_id': obra.id}
    rdo = _rdo(ctx, date(2026, 8, 15))
    return admin, obra, rdo


def test_atualizar_rdo_volta_a_funcionar():
    """🔴 `views/rdo.py:2161` — a rota lia `rdo.tempo_manha` (default do
    form.get), atributo que `RDO` NÃO tem: todo POST levantava
    AttributeError e caía no except — a rota estava morta em runtime."""
    with app.app_context():
        admin, obra, rdo = _rdo_de_ambiente()
        admin_id, rdo_id = admin.id, rdo.id
        data_str = rdo.data_relatorio.strftime('%Y-%m-%d')

    resposta = cliente_de(admin_id).post(
        f'/rdo/{rdo_id}/atualizar',
        data={'data_relatorio': data_str, 'clima_geral': 'Ensolarado'},
        follow_redirects=False)
    assert resposta.status_code in (302, 200)

    with app.app_context():
        from models import RDO
        depois = db.session.get(RDO, rdo_id)
        assert depois.clima_geral == 'Ensolarado', (
            'o POST em /rdo/<id>/atualizar não persistiu nada — '
            'a rota continua morta (AttributeError engolido)')


def test_nenhum_rdo_escreve_atributo_que_o_modelo_nao_tem():
    """🔴 Escritas em atributos não mapeados são perdidas em silêncio —
    inclusive `finalizado_em`/`finalizado_por_id` (a autoria da finalização,
    que a trilha `RDOTransicaoEstado` já captura de verdade)."""
    import inspect

    import crud_rdo_completo
    import views.rdo as vrdo

    orfaos = ('rdo.tempo_manha =', 'rdo.tempo_tarde =', 'rdo.tempo_noite =',
              'rdo.temperatura =', 'rdo.condicoes_climaticas =',
              'rdo.finalizado_em =', 'rdo.finalizado_por_id =')
    for modulo in (vrdo, crud_rdo_completo):
        fonte = inspect.getsource(modulo)
        for padrao in orfaos:
            assert padrao not in fonte, (
                f'{modulo.__name__}: escrita em atributo não mapeado '
                f'({padrao.strip()}) — o valor é perdido em silêncio')


def test_edicao_unificada_tem_obra_id_vinculada():
    """🔴 `rdo_salvar_unificado` — no ramo de edição `obra_id` nunca era
    atribuída, e o uso em `:3132` levantava NameError que ESCAPAVA do
    `except (ValueError, IndexError)` local: a edição inteira abortava."""
    import inspect

    import views.rdo as vrdo
    fonte = inspect.getsource(vrdo.rdo_salvar_unificado)
    assert 'obra_id = rdo.obra_id' in fonte, (
        'o ramo de edição não vincula obra_id — NameError no fallback de '
        'último serviço aborta a edição')


def test_salvar_rdo_legado_nao_passa_kwargs_que_rdo_nao_aceita():
    """🔴 `crud_rdo_completo.py:324` — `func` não importado e kwargs
    (`sequencial_ano`, `ano`) que `RDO` não aceita. Sem rota hoje, mas
    reservada para o Módulo 07: quebrada é pior que ausente."""
    import inspect

    import crud_rdo_completo
    fonte = inspect.getsource(crud_rdo_completo.salvar_rdo)
    assert 'sequencial_ano' not in fonte and 'func.max' not in fonte, (
        'salvar_rdo ainda usa func nao importado / kwargs inexistentes — '
        'NameError e TypeError garantidos no primeiro uso')


def test_flexivel_honra_rdo_id_em_vez_de_banir_o_segundo_rdo_do_dia():
    """🔴 `salvar_rdo_flexivel` ignora `rdo_id`: quem manda o id de um RDO
    existente pedindo edição recebe um RDO NOVO. Essa é a metade do achado
    `views/rdo.py:4002` que produz duplicata de verdade.

    ⚠️ A outra metade — "não tem guarda de obra+data" — foi corrigida com uma
    guarda cega e **revertida em 28/08**: dois RDOs na mesma obra e mesmo dia
    são estado LEGAL do domínio, não duplicata. `custo_funcionario_dia.py`
    rateia a diária entre os RDOs do dia e recalcula os vizinhos em cruz, e a
    Onda 3 / Task 9 desta mesma auditoria aprofundou exatamente esse caso.
    A guarda cega recusava com 302+flash — sucesso aos olhos de todo chamador
    que confere status —, matava o toggle reverso de terceiros e derrubava 6
    testes de caracterização que congelam a regra de propósito.

    Este teste fixa as duas pontas: sem `rdo_id`, cria; com `rdo_id`, edita.
    """
    with app.app_context():
        from test_cronograma_versao_service import _ambiente

        admin, obra = _ambiente()
        admin_id, obra_id = admin.id, obra.id

    cliente = cliente_de(admin_id)
    form = {'obra_id': str(obra_id), 'data_relatorio': '2026-08-18'}

    # Sem `rdo_id`: o segundo RDO do dia é legal e tem de nascer.
    cliente.post('/salvar-rdo-flexivel', data=form)
    cliente.post('/salvar-rdo-flexivel', data=form)

    with app.app_context():
        from datetime import date

        from models import RDO
        rdos = RDO.query.filter_by(
            obra_id=obra_id, admin_id=admin_id,
            data_relatorio=date(2026, 8, 18)).order_by(RDO.id).all()
        assert len(rdos) == 2, (
            f'{len(rdos)} RDO(s) para obra+data — dois RDOs no mesmo dia são '
            'estado legal: a diária é rateada entre eles')
        alvo_id = rdos[0].id

    # Com `rdo_id`: é pedido de EDIÇÃO. Não pode nascer um terceiro.
    cliente.post('/salvar-rdo-flexivel',
                 data={**form, 'rdo_id': str(alvo_id),
                       'observacoes_gerais': 'editado pelo flexivel'})

    with app.app_context():
        from datetime import date

        from models import RDO
        depois = RDO.query.filter_by(
            obra_id=obra_id, admin_id=admin_id,
            data_relatorio=date(2026, 8, 18)).all()
        assert len(depois) == 2, (
            f'POST com rdo_id criou RDO novo em vez de editar: {len(depois)} '
            'no total — é este o produtor real das duplicatas')
        alvo = RDO.query.get(alvo_id)
        assert alvo.comentario_geral == 'editado pelo flexivel', (
            'o rdo_id foi aceito mas a edição não chegou ao RDO apontado')


def test_flexivel_checa_colisao_de_numero_globalmente():
    """A coluna `numero_rdo` é UNIQUE global; checar colisão filtrando por
    admin_id deixa a linha de outro tenant invisível e o INSERT explode em
    laço permanente."""
    import inspect

    import views.rdo as vrdo
    fonte = inspect.getsource(vrdo.salvar_rdo_flexivel)
    assert 'numero_rdo=numero_proposto,\n                admin_id' \
        not in fonte and "numero_rdo=numero_proposto, admin_id" not in fonte, (
        'a checagem de colisão ainda filtra por admin_id numa coluna '
        'UNIQUE global')


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
# ---------------------------------------------------------------------------
# Task 7 — frota, transporte e reembolso
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Task 8 — os índices que discordam das queries, e o resto da Fase 6
# ---------------------------------------------------------------------------

def test_indice_de_vigencia_casa_com_as_queries():
    """🔴 `uq_contrato_versao_vigente` era UNIQUE (obra_id) enquanto todo
    leitor filtra por (obra_id, admin_id): uma linha com admin_id divergente
    (precedente real: migration 266) travava a obra PERMANENTEMENTE —
    abrir_versao não a via, nunca a fechava, e o INSERT violava o índice.
    Escolha registrada: o ÍNDICE ganha admin_id (mantém o escopo por tenant
    em toda parte)."""
    from models import ObraContratoVersao

    indice = next(
        (i for i in ObraContratoVersao.__table__.indexes
         if i.name == 'uq_contrato_versao_vigente'), None)
    assert indice is not None
    colunas = {c.name for c in indice.columns}
    assert colunas == {'obra_id', 'admin_id'}, (
        f'o índice de vigência cobre {colunas} — as queries filtram por '
        '(obra_id, admin_id)')


def test_versao_de_orcamento_tem_server_default():
    """🔴 `Orcamento.versao` sem server_default: schema criado por
    create_all (tenant novo, CI) discordava de produção migrada — INSERT
    fora do ORM funcionava lá e quebrava aqui, em silêncio."""
    from models import Orcamento
    assert Orcamento.__table__.c.versao.server_default is not None, (
        'Orcamento.versao sem server_default — os dois schemas discordam')


def test_aditivos_do_backref_tem_cascade():
    """⚪ `AditivoContrato.obra` usava passive_deletes sem o cascade que o
    irmão ObraContratoVersao.obra (mesmo hunk) tem."""
    from sqlalchemy import inspect as sa_inspect

    from models import Obra
    rel = sa_inspect(Obra).relationships['aditivos_contrato']
    assert rel.cascade.delete_orphan, (
        'Obra.aditivos_contrato sem cascade all, delete-orphan')


def test_versao_encerrada_em_memoria_nao_e_vigente():
    """⚪ `_versao_vigente_da_obra` devolvia a versão que a PRÓPRIA transação
    acabou de encerrar (vigente_ate posto em memória, ainda não flushado):
    a query em no_autoflush lê o estado do banco, não o da sessão."""
    from datetime import date

    from test_cronograma_versao_service import _ambiente

    from models import ObraContratoVersao
    from services.contrato_obra import _versao_vigente_da_obra

    with app.app_context():
        admin, obra = _ambiente()
        versao = ObraContratoVersao(
            obra_id=obra.id, admin_id=admin.id, versao=1,
            valor=100000, origem_tipo='contrato_original',
            vigente_de=date(2026, 1, 1), vigente_ate=None)
        db.session.add(versao)
        db.session.commit()

        # A transação encerra a vigência EM MEMÓRIA (sem flush) — é o que
        # abrir_versao faz antes de abrir a seguinte.
        versao.vigente_ate = date(2026, 8, 27)
        vigente = _versao_vigente_da_obra(obra)
        assert vigente is None or vigente.vigente_ate is None, (
            'a versão recém-encerrada em memória voltou como vigente')
        db.session.rollback()


def test_aprovar_aditivo_none_nao_estoura_e_moeda_nao_come_o_ponto_final():
    """⚪ `aprovar` fazia float(versao.valor) DEPOIS do commit com versao
    possivelmente None; e o reformat de moeda era aplicado à FRASE inteira
    (o ponto final virava vírgula)."""
    import inspect

    import views.aditivos_views as av
    fonte = inspect.getsource(av.aprovar)
    assert 'if versao is None' in fonte, (
        'aprovar não guarda o None de aprovar_aditivo')
    assert ".replace(',', 'X')" not in fonte.split('flash(')[1].split(
        'success')[0] or '_moeda' in fonte or 'valor_fmt' in fonte, (
        'o reformat de moeda ainda é aplicado à frase inteira')


def test_leitor_nao_ve_botao_de_aprovar():
    """⚪ `pode_editar=True` fixo: usuário só-leitura via 'Aprovar' e levava
    404 opaco."""
    import inspect

    import views.aditivos_views as av
    fonte = inspect.getsource(av)
    assert 'pode_editar=True' not in fonte, (
        'pode_editar segue fixo em True para qualquer papel')


def test_rotulos_de_origem_casam_com_o_vocabulario():
    """⚪ O mapa do template usava proposta/manual, mas ORIGEM_TIPO grava
    proposta_aprovada, cadastro_manual, contrato_original... — só 'aditivo'
    casava."""
    corpo = open('templates/aditivos/listar.html').read()
    from services.contrato_obra import ORIGENS
    for origem in ORIGENS:
        assert origem in corpo, (
            f'o rótulo de {origem!r} não existe no template — cai no cru')


def test_card_do_contrato_nao_depende_de_blueprint_engolido():
    """⚪ `app.py` engole DE PROPÓSITO a falha de registro do aditivos_bp,
    mas a página fazia url_for('aditivos.listar') sem guarda: no cenário que
    o app.py foi escrito para sobreviver, toda obra com contrato dava
    BuildError 500. `obra_form.html` usa href literal e está safe — mesmo
    idioma."""
    corpo = open('templates/obras/detalhes_obra_profissional.html').read()
    assert "url_for('aditivos.listar'" not in corpo, (
        'o card do contrato ainda quebra a página se o aditivos_bp não '
        'registrar')


def test_odometro_nao_anda_para_tras():
    """🔴 `frota_views.py:499` — `veiculo.km_atual = km_final` sem comparação:
    uso retroativo fazia o odômetro regredir e calava o alerta de manutenção.
    As três rotas irmãs têm a guarda; só esta ficou de fora."""
    import inspect

    import frota_views
    fonte = inspect.getsource(frota_views)
    for numero, linha in enumerate(fonte.splitlines(), start=1):
        if 'veiculo.km_atual = novo_uso.km_final' in linha:
            contexto = fonte.splitlines()[max(0, numero - 6):numero]
            assert any('km_atual' in l and ('>' in l or 'max(' in l)
                       for l in contexto), (
                f'frota_views:{numero}: km_atual atualizado sem comparar '
                'com o valor atual — uso retroativo regride o odômetro')


def test_edicao_de_uso_le_todos_os_passageiros():
    """🔴 `frota_views.py:741` — a edição lia passageiros de `to_dict()` (só
    o PRIMEIRO valor do multi-select) enquanto a criação usa getlist+CSV; e
    apagava responsavel_veiculo/observacoes quando o campo não vinha."""
    import inspect

    import frota_views
    fonte = inspect.getsource(frota_views)
    assert "uso.passageiros_frente = ','.join(passageiros_frente_list)" \
        in fonte, (
        'a edição ainda lê passageiros de to_dict() — só o primeiro valor '
        'do multi-select sobrevive')
    assert "uso.responsavel_veiculo = dados.get('responsavel_veiculo')" \
        not in fonte, (
        'a edição ainda apaga responsavel_veiculo quando o campo não vem')


def test_dashboard_tco_nao_duplica_o_join():
    """🔴 `frota_views.py:1063` — `.join(FrotaVeiculo)` duplicado (tipo +
    status): confirmado no SA 2.0.41 que o segundo join não é deduplicado —
    o filtro por tipo do dashboard TCO sempre errava."""
    import inspect

    import frota_views
    fonte = inspect.getsource(frota_views)
    # O padrão duplicado existia em TRÊS builders do mesmo dashboard:
    # query_custos, tco_total e query_km. Nenhuma linha pode ter join
    # seguido de filter na mesma cadeia condicionada duas vezes.
    for numero, linha in enumerate(fonte.splitlines(), start=1):
        if '.join(FrotaVeiculo).filter(' in linha:
            raise AssertionError(
                f'frota_views:{numero}: join(FrotaVeiculo) encadeado com '
                'filter dentro de condição — o segundo join da mesma query '
                'duplica linhas e infla o TCO')


def test_lote_de_transporte_grava_origem_id():
    """🔴 `transporte_views.py:442` — o lote gravava GestaoCustoFilho SEM
    `origem_id`, e `_limpar_gestao_custo_filho` filtra por ele: excluir
    lançamento de lote deixava o valor vivo em Contas a Pagar dizendo
    'Gestão de Custos atualizada'."""
    import inspect

    import transporte_views
    fonte = inspect.getsource(transporte_views.novo_massa_post)
    assert 'origem_id=' in fonte, (
        'o lote ainda registra custo sem origem_id — a exclusão não acha o '
        'filho e o valor fica vivo em Contas a Pagar')


def test_reembolso_sem_v2_redireciona_em_vez_de_500():
    """🔴 `reembolso_views.py:34` — `url_for('main_bp.dashboard')`, mas o
    blueprint chama-se `main`: tenant sem V2 clicando em Reembolsos levava
    BuildError 500 em vez do aviso."""
    import inspect

    import reembolso_views
    fonte = inspect.getsource(reembolso_views)
    assert 'main_bp.dashboard' not in fonte, (
        "url_for('main_bp.dashboard') — o blueprint chama-se 'main'; "
        'tenant sem V2 leva BuildError 500 em vez do aviso')


