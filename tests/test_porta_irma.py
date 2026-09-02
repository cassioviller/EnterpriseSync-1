"""A porta irmã — a guarda fechou um caminho e deixou o gêmeo aberto.

A regra destes testes: NENHUM prova por `inspect.getsource()`. Três testes da
Onda 5 liam o texto do código e passaram verdes por cima de defeitos reais —
é o que este plano existe para reparar. O que se afirma é olhado no banco ou
na resposta HTTP.

E todo teste de guarda itera sobre o CONJUNTO de portas equivalentes, nunca
sobre a instância que o defeito da vez expôs.
"""
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

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
        app.secret_key = 'test-porta-irma'
    yield


def _funcionario_logavel(admin_id, marca):
    """Usuário FUNCIONARIO do tenant — o papel que NÃO deve poder aprovar.

    `um_tenant` semeia o ADMIN; aqui nasce o subordinado, que é quem prova a
    guarda. Sem ele o teste provaria só que admin pode, que não é a pergunta.
    """
    from werkzeug.security import generate_password_hash

    from models import TipoUsuario, Usuario

    u = Usuario(
        nome=f'Func {marca}', username=f'func_{marca}',
        email=f'func_{marca}@t.local',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.FUNCIONARIO, admin_id=admin_id, ativo=True)
    db.session.add(u)
    db.session.commit()
    return u.id


# ---------------------------------------------------------------------------
# Task 1 — o aditivo
# ---------------------------------------------------------------------------

def test_funcionario_nao_aprova_aditivo():
    """🔴 `views/aditivos_views.py` — rotas `novo` e `aprovar` do aditivo.

    Com `escopo_obra_ativo` desligado (`models.py:4441`, `default=False` — o
    estado de todo tenant existente), `papel_de_usuario_na_obra`
    (`utils/autorizacao.py:147-160`) devolve GESTOR para QUALQUER usuário
    autenticado do tenant. Aprovar aditivo grava `ObraContratoVersao`, lança
    delta contábil e desloca cronograma — irreversível por desenho.

    O fallback permissivo é decisão consciente e documentada; o defeito é
    pendurar ação irreversível nele. Ver D5.

    Fix round 2 (achados Important 1 e 2 da revisão) — a versão anterior
    tinha dois vícios:

    1. Afirmava sobre `ObraContratoVersao`, mas `/aditivos/novo` só cria
       `AditivoContrato` em `rascunho` — quem toca `ObraContratoVersao` é
       `/aditivos/<id>/aprovar` (`services/contrato_obra.py:570-`). A
       asserção nunca falharia nesta rota, mesmo se o FUNCIONARIO abrisse
       aditivos à vontade. Agora `/novo` é medido por `AditivoContrato`
       (o que ele de fato escreve) e `/aprovar` é exercida à parte, medida
       por `ObraContratoVersao` E pelo `status` do aditivo (o que ELA
       escreve).
    2. Aceitava 302 como prova de recusa, mas 302 também é o código de
       SUCESSO (redirect para `aditivos.listar`). O RED "verde por engano"
       veio da chave errada do form (`justificativa`, que a rota não lê —
       o campo é `motivo`), não da guarda. Corrigida a chave; a prova de
       recusa não depende mais do código de status, só do banco.

    Nota de arreio: cada `cliente.post(...)` fica FORA de qualquer
    `with app.app_context()` que este teste abra, e cada leitura/gravação de
    banco tem o seu próprio bloco — mesmo padrão de
    `tests/test_fase6_aditivo.py::test_quem_nao_e_gestor_da_obra_nao_aprova_aditivo`.
    Não é estilo: `app.test_client().post()` só empurra um contexto de app
    novo quando NENHUM está ativo. Envolver dois `.post()` de usuários
    DIFERENTES no mesmo `with app.app_context()` externo faz os dois
    reaproveitarem o mesmo `flask.g` — e `current_user` do PRIMEIRO fica
    pendurado para o SEGUNDO (visto na prática: o POST do ADMIN, depois do
    POST do FUNCIONARIO no mesmo bloco, autenticava como o FUNCIONARIO).
    """
    from models import AditivoContrato, Obra, ObraContratoVersao
    from services.contrato_obra import ORIGEM_CADASTRO, definir_valor_contrato

    marca = uuid.uuid4().hex[:8]
    with app.app_context():
        t = um_tenant('adit-authz', com_fatos=False)
        func_id = _funcionario_logavel(t.admin_id, marca)

        # `um_tenant` grava `valor_contrato` por atribuição direta — sem
        # passar pelo escritor único não nasce `ObraContratoVersao` v1, e
        # `abrir_aditivo` exige contrato vigente (D2). Sem isto, mesmo SEM
        # guarda nenhuma o POST falharia (400, contrato inexistente) e o
        # teste provaria nada — o mesmo vício do achado 1, um nível abaixo.
        obra = db.session.get(Obra, t.obra_id)
        obra.valor_contrato = 0
        db.session.flush()
        definir_valor_contrato(obra, 100000.0, ORIGEM_CADASTRO,
                               motivo='contrato original')
        db.session.commit()

        aditivos_antes = AditivoContrato.query.filter_by(
            obra_id=t.obra_id).count()

    # --- /aditivos/novo -------------------------------------------------
    cliente = cliente_de(func_id)
    resposta_abrir = cliente.post(
        f'/obras/{t.obra_id}/aditivos/novo',
        data={'tipo': 'acrescimo', 'valor_novo': '150.000,00',
              'prazo_delta_dias': '30', 'motivo': f'invasao-{marca}'},
        follow_redirects=False)

    with app.app_context():
        aditivos_depois = AditivoContrato.query.filter_by(
            obra_id=t.obra_id).count()
        assert aditivos_depois == aditivos_antes, (
            'FUNCIONARIO abriu aditivo — '
            f'{aditivos_depois - aditivos_antes} novo(s) registro(s) em '
            f'AditivoContrato (POST devolveu {resposta_abrir.status_code})')

    # --- /aditivos/<id>/aprovar ------------------------------------------
    # A ação irreversível de verdade — abre o rascunho como ADMIN (sucesso,
    # não é o que este teste mede) e tenta aprovar como FUNCIONARIO, que é
    # a pergunta.
    admin_cliente = cliente_de(t.admin_id)
    resposta_abrir_admin = admin_cliente.post(
        f'/obras/{t.obra_id}/aditivos/novo',
        data={'tipo': 'acrescimo', 'valor_novo': '150.000,00',
              'motivo': f'admin-abre-{marca}'},
        follow_redirects=False)
    assert resposta_abrir_admin.status_code in (302, 303), (
        'setup do teste falhou: ADMIN não abriu aditivo '
        f'({resposta_abrir_admin.status_code})')

    with app.app_context():
        aditivo = AditivoContrato.query.filter_by(obra_id=t.obra_id).one()
        assert aditivo.status == 'rascunho'
        aditivo_id = aditivo.id

        versoes_antes = ObraContratoVersao.query.filter_by(
            obra_id=t.obra_id).count()

    resposta_aprovar = cliente.post(
        f'/obras/{t.obra_id}/aditivos/{aditivo_id}/aprovar',
        follow_redirects=False)

    with app.app_context():
        aditivo_depois = AditivoContrato.query.filter_by(
            id=aditivo_id).one()
        assert aditivo_depois.status == 'rascunho', (
            'FUNCIONARIO aprovou aditivo — status virou '
            f'{aditivo_depois.status!r} '
            f'(POST devolveu {resposta_aprovar.status_code})')

        versoes_depois = ObraContratoVersao.query.filter_by(
            obra_id=t.obra_id).count()
        assert versoes_depois == versoes_antes, (
            'FUNCIONARIO moveu a linha de base do contrato ao aprovar — '
            f'{versoes_depois - versoes_antes} versão(ões) nova(s)')


def test_gestor_nao_admin_aprova_aditivo_com_escopo_ativo():
    """R5 — com `escopo_obra_ativo` LIGADA, `obra_required(PapelObra.GESTOR)`
    já é guarda de verdade (Fase 1): quem tem vínculo `UsuarioObra` como
    GESTOR da obra tem de conseguir abrir E aprovar aditivo, mesmo sem ser
    ADMIN da conta.

    Esta é a metade que faltava do caso de `test_funcionario_nao_aprova_aditivo`
    — sem ela, nada impede alguém de trocar a guarda nova por um
    `@admin_required` incondicional de novo amanhã. Foi exatamente essa troca
    larga demais que quebrou
    `tests/test_fase6_aditivo.py::test_quem_nao_e_gestor_da_obra_nao_aprova_aditivo`
    no primeiro round desta task.
    """
    from models import (AditivoContrato, Obra, ObraContratoVersao, PapelObra,
                        UsuarioObra)
    from scripts.flag_escopo_obra import definir_flag
    from services.contrato_obra import ORIGEM_CADASTRO, definir_valor_contrato

    with app.app_context():
        marca = uuid.uuid4().hex[:8]
        t = um_tenant('adit-gestor', com_fatos=False)

        # `um_tenant` já semeia `valor_contrato=100000`, mas por atribuição
        # direta — sem passar por `definir_valor_contrato`, não existe
        # `ObraContratoVersao` v1 ainda, e `abrir_aditivo` exige contrato
        # vigente (D2). Zera e regrava pelo escritor único para nascer o
        # baseline de verdade.
        obra = db.session.get(Obra, t.obra_id)
        obra.valor_contrato = 0
        db.session.flush()
        definir_valor_contrato(obra, 100000.0, ORIGEM_CADASTRO,
                               motivo='contrato original')
        db.session.commit()

        definir_flag(t.admin_id, True)
        db.session.commit()

        gestor_id = _funcionario_logavel(t.admin_id, marca)
        db.session.add(UsuarioObra(
            usuario_id=gestor_id, obra_id=t.obra_id, papel=PapelObra.GESTOR,
            admin_id=t.admin_id, ativo=True))
        db.session.commit()

        cliente = cliente_de(gestor_id)

        resposta_abrir = cliente.post(
            f'/obras/{t.obra_id}/aditivos/novo',
            data={'tipo': 'acrescimo', 'valor_novo': '130.000,00',
                  'motivo': f'reforco-{marca}'},
            follow_redirects=False)
        # 302 sozinho não distingue sucesso (→ `aditivos.listar`) de recusa
        # (→ `main.dashboard`, o que `admin_required` faz) — os dois são
        # redirect. É o DESTINO que prova qual dos dois aconteceu.
        destino_abrir = resposta_abrir.headers.get('Location') or ''
        assert resposta_abrir.status_code in (302, 303) and (
            f'/obras/{t.obra_id}/aditivos' in destino_abrir), (
            'GESTOR não-admin não conseguiu abrir aditivo com escopo ativo '
            f'(status={resposta_abrir.status_code}, destino={destino_abrir!r})')

        aditivo = AditivoContrato.query.filter_by(obra_id=t.obra_id).one()

        resposta_aprovar = cliente.post(
            f'/obras/{t.obra_id}/aditivos/{aditivo.id}/aprovar',
            follow_redirects=False)
        destino_aprovar = resposta_aprovar.headers.get('Location') or ''
        assert resposta_aprovar.status_code in (302, 303) and (
            f'/obras/{t.obra_id}/aditivos' in destino_aprovar), (
            'GESTOR não-admin não conseguiu aprovar aditivo com escopo ativo '
            f'(status={resposta_aprovar.status_code}, destino={destino_aprovar!r})')

        versoes = ObraContratoVersao.query.filter_by(
            obra_id=t.obra_id).count()
        assert versoes == 2, (
            'aprovação do GESTOR não-admin não abriu a versão 2 do '
            f'contrato — {versoes} versão(ões) encontrada(s)')


# ---------------------------------------------------------------------------
# Task 2 — a medição do portal
# ---------------------------------------------------------------------------

def test_gerar_medicao_e_fechada_nas_duas_urls():
    """🔴 `medicao_views.py:445-448` — a mesma view em DUAS rotas, só
    `@login_required`.

    A Onda 5 fechou `portal_obras.gerar_medicao` com `@admin_required`. Quem
    for barrado lá ainda POSTa em `/medicao/obra/<id>/gerar` ou
    `/obras/<id>/medicao/fechar` e cria a `MedicaoObra` — mais a conta a
    receber que ela auto-cria. O privilégio se recupera trocando a URL.

    O teste itera sobre AS DUAS, de propósito: fechar uma e deixar a outra é
    exatamente o defeito.

    Nota de arreio: os dois `cliente.post()` ficam FORA do
    `with app.app_context()` de semeadura/conferência — mesmo padrão de
    `test_funcionario_nao_aprova_aditivo` acima. Aqui os dois posts são do
    MESMO usuário (`func_id`), então a armadilha de `flask.g` compartilhado
    entre usuários DIFERENTES não mudaria o veredito da identidade — mas o
    padrão fica junto de qualquer forma: não é só sobre qual usuário
    autentica, é sobre não reaproveitar o `AppContext` (e o teardown que ele
    dispara) entre requests.

    Nota de fixture: `gerar_medicao_quinzenal`
    (`services/medicao_service.py:87-96`) recusa gerar SEM nenhum
    `ItemMedicaoComercial` cadastrado — "Nenhum item de medição comercial
    cadastrado para esta obra" — e devolve `erro` sem criar `MedicaoObra`,
    de propósito, independente de quem faz o POST. Sem semear um item aqui
    o teste passaria verde por essa recusa de dados, não pela guarda de
    autorização que é o que se quer provar — o mesmo vício da chave de form
    errada no teste de aditivo. Um item com `valor_comercial` basta.
    """
    from models import ItemMedicaoComercial, MedicaoObra

    marca = uuid.uuid4().hex[:8]
    with app.app_context():
        t = um_tenant('medicao-authz', com_fatos=False)
        obra_id = t.obra_id
        func_id = _funcionario_logavel(t.admin_id, marca)

        db.session.add(ItemMedicaoComercial(
            admin_id=t.admin_id, obra_id=obra_id,
            nome=f'Item {marca}', valor_comercial=Decimal('1000.00')))
        db.session.commit()

        antes = MedicaoObra.query.filter_by(obra_id=obra_id).count()

    cliente = cliente_de(func_id)

    for rota in (f'/medicao/obra/{obra_id}/gerar',
                 f'/obras/{obra_id}/medicao/fechar'):
        resposta = cliente.post(rota, data={}, follow_redirects=False)
        assert resposta.status_code in (302, 403, 404), (
            f'{rota}: FUNCIONARIO recebeu {resposta.status_code}')

    with app.app_context():
        depois = MedicaoObra.query.filter_by(obra_id=obra_id).count()
        assert depois == antes, (
            f'FUNCIONARIO gerou {depois - antes} medição(ões) por URL alternativa')


# ---------------------------------------------------------------------------
# Task 3 — o traceback na resposta
# ---------------------------------------------------------------------------

# Diretórios que não são código desta aplicação: dependências vendorizadas,
# caches de build e o museu. Varrer isso devolve dezenas de falsos positivos
# do gunicorn/pytest/tensorflow e o guarda vira ruído que ninguém lê.
_FORA_DA_VARREDURA = (
    'pythonlibs/', 'cache/', 'archive/', 'entrega_baia_rev10/', '.venv/',
    'node_modules/', 'migrations/', 'tests/', 'static/', 'attached_assets/',
)


def _arquivos_da_aplicacao():
    """Todo `.py` desta aplicação — a lista cresce sozinha.

    O guarda da Onda 5 nomeava dois módulos à mão
    (`test_onda5_recusado_nao_grava.py:44` itera sobre `ponto_views` e
    `equipe_views`). Foi por isso que `views/rdo.py` passou: não estava na
    lista. Uma lista escrita à mão num app de centenas de módulos é a mesma
    porta irmã que este plano inteiro persegue, só que em escala maior — por
    isso aqui não há lista, há varredura.
    """
    import pathlib

    raiz = pathlib.Path(__file__).resolve().parent.parent
    for caminho in sorted(raiz.rglob('*.py')):
        relativo = caminho.relative_to(raiz).as_posix()
        if any(relativo.startswith(p) or f'/{p}' in relativo
               for p in _FORA_DA_VARREDURA):
            continue
        if caminho.name.startswith('_') or 'test' in caminho.name:
            continue
        yield relativo, caminho


def test_nenhum_modulo_de_view_manda_traceback_para_a_resposta():
    """🔴 `views/rdo.py:3581` e `views/obras.py:2279` — `flash()` com o
    `format_exc()` inteiro dentro.

    A Onda 5 fechou esta classe em `ponto_views` e `equipe_views` e escreveu
    um guarda que itera sobre esses DOIS módulos. Este substitui: varre a
    aplicação inteira e exige que o traceback só apareça em linha de log.

    Duas formas de vazamento, porque as duas existem no mundo:
      1. `t = format_exc()` e depois `flash(f'...{t}')` — o caso dos dois
         defeitos de hoje;
      2. `flash(f'...{traceback.format_exc()}')` direto, sem variável.

    O que NÃO é vazamento, e por isso não entra: `format_exc()` guardado em
    dict de diagnóstico (`utils/observability.py:120`,
    `utils/production_error_handler.py:38`) ou passado a `logger`. Atribuir
    o traceback é legítimo — o que não pode é ele chegar à RESPOSTA. Um
    guarda que reprovasse essas três linhas seria ruído, e guarda ruidoso
    vira guarda desligado.
    """
    ALVOS = ('flash(', 'render_template(')
    suspeitos = []

    for relativo, caminho in _arquivos_da_aplicacao():
        fonte = caminho.read_text(encoding='utf-8', errors='replace')
        if 'format_exc' not in fonte:
            continue
        linhas = fonte.splitlines()
        for numero, linha in enumerate(linhas, start=1):
            if 'format_exc' not in linha:
                continue
            if 'logger.' in linha or 'logging.' in linha:
                continue

            # (2) o traceback entra direto na chamada que responde.
            if any(alvo in linha for alvo in ALVOS):
                suspeitos.append(
                    f'{relativo}:{numero} traceback direto na resposta '
                    f'→ {linha.strip()[:80]}')
                continue

            # (1) o traceback vira variável — segue-se a variável.
            if '=' not in linha:
                continue
            nome_var = linha.split('=')[0].strip()
            if not nome_var.isidentifier():
                continue
            for n2, l2 in enumerate(linhas, start=1):
                if nome_var not in l2 or not any(alvo in l2 for alvo in ALVOS):
                    continue
                if '_detalhes_na_resposta' in l2:
                    continue   # o gate de produção já existe
                suspeitos.append(
                    f'{relativo}:{n2} manda {nome_var} para a resposta '
                    f'→ {l2.strip()[:80]}')

    assert not suspeitos, (
        'traceback pode chegar à resposta em:\n  ' + '\n  '.join(suspeitos))


def test_erro_ao_salvar_rdo_nao_vaza_frames_nem_email():
    """A prova pela porta: o POST que quebra não conta a vida do usuário.

    A varredura acima lê texto; esta lê a RESPOSTA — é a que valeria mesmo
    se alguém reescrevesse o vazamento numa forma que o texto não pega.

    Nota de gatilho: o plano mandava POSTar `obra_id` inexistente. Não serve
    — `views/rdo.py:2951-2956` trata obra ausente com `flash('Obra não
    encontrada.')` e redirect, um caminho VALIDADO que nunca chega ao
    `except`. O teste passaria verde antes da correção, provando nada: é o
    mesmo andaime que não podia falhar que o R8 tirou daqui.

    O que quebra de verdade é a data: `datetime.strptime(..., '%Y-%m-%d')`
    (`:2948`) roda ANTES da busca da obra e estoura `ValueError` em formato
    diferente — cai no `except Exception` que monta o flash com o traceback.
    """
    with app.app_context():
        t = um_tenant('rdo-flash', com_fatos=False)
        admin_id = t.admin_id

    cliente = cliente_de(admin_id)

    # Data em formato brasileiro: `strptime('%Y-%m-%d')` estoura e a rota cai
    # no `except Exception` — o caminho que vazava frames, e-mail e admin_id.
    resposta = cliente.post('/rdo/salvar',
                            data={'obra_id': '999999999',
                                  'data_relatorio': '31/08/2026'},
                            follow_redirects=True)
    corpo = resposta.get_data(as_text=True)
    for vazamento in ('Traceback (most recent call last)', 'File "/home/',
                      'ADMIN_ID:', 'TRACE:'):
        assert vazamento not in corpo, f'{vazamento!r} vazou na resposta'


# ---------------------------------------------------------------------------
# Task 4 — a mensagem que não passa pelo gate
# ---------------------------------------------------------------------------

def test_rotas_safe_nao_mandam_excecao_crua_na_mensagem(monkeypatch):
    """🔴 `production_routes.py:124,201,279,336,387` —
    `error_message=f"...{str(e)}"` SEM gate.

    `_detalhes_na_resposta()` (`356c2cf9`) fechou `error_details` e deixou a
    mensagem intocada. `templates/error.html:17` renderiza
    `{{ error_message }}` CRU — só `error_details` está atrás do `{% if %}`
    (`:30`). Num erro de SQLAlchemy, `str(e)` traz
    `'(psycopg2.errors.X) ... [SQL: SELECT ...] [parameters: {...}]'` para
    dentro do `<h5>`.

    Nota de gatilho — o plano avisava, e com razão: se nenhuma rota quebrar,
    o teste passa sem provar nada, e teste-que-nasce-verde é exatamente o
    que deixou estes defeitos passarem. Em vez de forçar o erro à mão uma
    vez e desfazer, o erro é INJETADO aqui: `get_safe_admin_id` é chamada
    dentro do `try` das cinco rotas (`:46,134,240,292,349`), então trocá-la
    por uma que estoura `ProgrammingError` leva as cinco ao `except` de
    forma determinística — e o teste segue sendo guarda depois desta rodada,
    não só uma conferência manual.

    O que se afirma é o INVARIANTE de produção, não o texto: sob
    `IS_PRODUCTION`, nenhuma das cinco pode devolver SQL na resposta.
    """
    import app as app_module
    import production_routes
    from sqlalchemy.exc import ProgrammingError

    def _estoura(*args, **kwargs):
        raise ProgrammingError(
            'SELECT funcionario.id FROM funcionario WHERE admin_id = %(id)s',
            {'id': 42},
            Exception('coluna "x" nao existe'))

    monkeypatch.setattr(production_routes, 'get_safe_admin_id', _estoura)

    with app.app_context():
        t = um_tenant('prod-safe', com_fatos=False)
        admin_id = t.admin_id

    cliente = cliente_de(admin_id)
    rotas = ('/prod/safe-funcionarios', '/prod/safe-dashboard',
             '/prod/safe-obras', '/prod/safe-veiculos',
             '/prod/safe-alimentacao')

    monkeypatch.setattr(app_module, 'IS_PRODUCTION', True)

    for rota in rotas:
        resposta = cliente.get(rota)
        corpo = resposta.get_data(as_text=True)
        # A rota tem de ter QUEBRADO — senão o teste não olhou o caminho
        # de erro e o verde não vale.
        assert resposta.status_code == 500, (
            f'{rota}: respondeu {resposta.status_code}, não entrou no except '
            '— o gatilho de erro parou de funcionar e este teste virou andaime')
        for vazamento in ('[SQL:', '[parameters:', 'psycopg2.',
                          'sqlalchemy.exc', 'ProgrammingError',
                          'Traceback (most recent call last)'):
            assert vazamento not in corpo, (
                f'{rota}: {vazamento!r} vazou na resposta em produção')


# ---------------------------------------------------------------------------
# Task 5 — o geofencing pulável por omissão
# ---------------------------------------------------------------------------

def _funcionario_identificavel(monkeypatch, funcionario_id):
    """Faz o reconhecimento facial ACERTAR, para o teste chegar ao geofencing.

    Sem isto o POST morre em 404 'Nenhum funcionário com foto cadastrada'
    (conferido: é o que a rota devolve para o payload do plano) e o teste
    passa verde sem nunca ter olhado a guarda — o mesmo andaime que o R8
    tirou daqui e que já apareceu duas vezes nesta onda.

    Dois grampos, nos dois pontos que barram a foto sintética:
      - `validar_qualidade_foto_avancada` (`ponto_views.py:2375`), que
        recusa um PNG 1x1;
      - `identificar_por_cache` (`:2393`), que devolve o id do funcionário.
        A rota ainda busca esse id COM filtro de `admin_id` (`:2401`), então
        o grampo não fura o escopo de tenant — só entrega a identificação.
    """
    import ponto_views

    monkeypatch.setattr(ponto_views, 'validar_qualidade_foto_avancada',
                        lambda *a, **k: (True, 'ok', {}))
    monkeypatch.setattr(ponto_views, 'identificar_por_cache',
                        lambda *a, **k: (funcionario_id, 0.10, None))


@pytest.mark.parametrize('caso,payload_extra', [
    ('obra_id omitido', {}),
    ('obra_id de outro tenant', {'obra_id': 999999999}),
])
def test_ponto_facial_nao_pula_geofencing_por_obra_id(
        monkeypatch, caso, payload_extra):
    """🔴 `ponto_views.py:2453` — `if obra_id:` / `if obra:`.

    O comentário em `:2447` diz que o defeito ANTIGO era "bastava não mandar
    latitude/longitude". A frase continua verdadeira trocando uma palavra:
    hoje basta não mandar `obra_id` — ele vem de `data.get('obra_id')`
    (`:2311`) sem checagem. Nos dois casos o validador não roda e o
    RegistroPonto nasce com obra_id=None.

    Os dois casos são parametrizados de propósito: consertar a omissão e
    deixar o id-de-outro-tenant é repetir o padrão que este plano fecha.
    """
    from models import Funcionario, RegistroPonto

    with app.app_context():
        t = um_tenant('ponto-geo', com_fatos=False)
        admin_id, func_id = t.admin_id, t.funcionario_id
        # A rota só considera funcionários COM foto: sem isto ela para em
        # 404 antes do geofencing.
        f = db.session.get(Funcionario, func_id)
        f.foto_base64 = 'data:image/png;base64,iVBORw0KGgo='
        db.session.commit()
        antes = RegistroPonto.query.filter_by(funcionario_id=func_id).count()

    _funcionario_identificavel(monkeypatch, func_id)

    payload = {'foto_base64': 'data:image/png;base64,iVBORw0KGgo=',
               'tipo_ponto': 'entrada'}
    payload.update(payload_extra)
    # 🔬 Rota conferida: `@ponto_bp.route('/api/identificar-e-registrar')`
    # sobre `url_prefix='/ponto'`.
    resposta = cliente_de(admin_id).post('/ponto/api/identificar-e-registrar',
                                         json=payload)

    assert resposta.status_code in (400, 403, 404), (
        f'{caso}: recebeu {resposta.status_code} — geofencing pulado')

    with app.app_context():
        depois = RegistroPonto.query.filter_by(funcionario_id=func_id).count()
        assert depois == antes, (
            f'{caso}: gravou ponto sem passar pelo geofencing')


# ---------------------------------------------------------------------------
# Task 6 — a guarda que não via o RDO irmão do mesmo dia
# ---------------------------------------------------------------------------

def _tarefa_e_dois_rdos(prefixo, dia, **kwargs_tarefa):
    """Uma tarefa e DOIS RDOs da mesma obra no MESMO dia.

    Dois RDOs, não um: `registrar_apontamento` faz UPSERT por (rdo, tarefa),
    então um só atualizaria a própria linha e não exercitaria a janela do
    acumulado anterior — que é o que está sob teste.
    """
    from models import RDO, TarefaCronograma

    t = um_tenant(prefixo, com_fatos=False)
    campos = dict(obra_id=t.obra_id, admin_id=t.admin_id,
                  nome_tarefa=f'Tarefa {uuid.uuid4().hex[:6]}', ordem=0,
                  responsavel='propria', duracao_dias=10,
                  percentual_concluido=0.0)
    campos.update(kwargs_tarefa)
    tarefa = TarefaCronograma(**campos)
    db.session.add(tarefa)

    rdos = []
    for sufixo in ('A', 'B'):
        r = RDO(numero_rdo=f'RDO-{uuid.uuid4().hex[:8]}-{sufixo}',
                obra_id=t.obra_id, data_relatorio=dia, local='Campo',
                admin_id=t.admin_id)
        db.session.add(r)
        rdos.append(r)
    db.session.commit()
    return t, tarefa, rdos[0], rdos[1]


def test_retrocesso_e_barrado_entre_rdos_do_mesmo_dia():
    """🔴 `cronograma_apontamento_service.py:398` — janela com `<` estrito.

    O commit `ed85d117` afirma, em `views/rdo.py:4035`, que dois RDOs na
    mesma obra e mesmo dia são estado LEGAL (a diária é rateada entre eles).
    E `recomputar_cadeia` (`:183`) reprocessa em ordem `(data_relatorio,
    id)`, logo ENXERGA o irmão do mesmo dia.

    A guarda não enxergava: RDO A do dia 20 registra acumulado 120
    (superexecução confirmada); RDO B, mesma obra e MESMO dia 20, registra
    50. `pct_ant` lia só o estritamente anterior ao dia 20, achava 0, e
    50 > 0 passava. O recompute depois virava isso em incremento de −70.
    """
    from services.cronograma_apontamento_service import (
        RetrocessoNaoPermitido, registrar_apontamento)

    with app.app_context():
        t, tarefa, rdo_a, rdo_b = _tarefa_e_dois_rdos(
            'retro-mesmo-dia', date(2026, 8, 20))

        # 🔬 `quantidade_dia` XOR `percentual_acumulado` (`:311`). A
        # superexecução de 120 exige `permitir_sobreexecucao=True`, senão a
        # guarda de SOBRE-execução barra antes e o teste provaria a guarda
        # errada.
        registrar_apontamento(rdo_a, tarefa, percentual_acumulado=120.0,
                              admin_id=t.admin_id,
                              permitir_sobreexecucao=True)
        db.session.commit()

        with pytest.raises(RetrocessoNaoPermitido):
            registrar_apontamento(rdo_b, tarefa, percentual_acumulado=50.0,
                                  admin_id=t.admin_id)


def test_acumulado_quantitativo_enxerga_o_rdo_irmao_do_mesmo_dia():
    """🔴 A porta irmã DENTRO da Task 6: `acum_ant` (`:378`) tem a MESMA
    janela estrita de `pct_ant` (`:398`).

    O plano só nomeia o `pct_ant`. Mas o modo quantitativo soma
    `quantidade_executada_dia` na mesma janela `RDO.data_relatorio <
    rdo.data_relatorio` — e `recomputar_cadeia` acumula percorrendo as
    linhas em `(data_relatorio, id)`, somando o irmão do mesmo dia como
    qualquer outro. Consertar só o percentual e deixar o quantitativo é
    literalmente o padrão que este plano existe para fechar.

    Cenário: tarefa de 100 un. RDO A do dia 20 executa 30 un. RDO B, mesmo
    dia, executa 40. O acumulado de B tem de ser 70 — não 40.
    """
    from services.cronograma_apontamento_service import registrar_apontamento

    with app.app_context():
        t, tarefa, rdo_a, rdo_b = _tarefa_e_dois_rdos(
            'acum-mesmo-dia', date(2026, 8, 20),
            unidade_medida='un', quantidade_total=100.0)

        registrar_apontamento(rdo_a, tarefa, quantidade_dia=30.0,
                              admin_id=t.admin_id)
        db.session.commit()

        ap_b = registrar_apontamento(rdo_b, tarefa, quantidade_dia=40.0,
                                     admin_id=t.admin_id)
        db.session.commit()

        assert float(ap_b.quantidade_acumulada) == 70.0, (
            'o acumulado de B ignorou as 30 un do RDO irmão do mesmo dia — '
            f'leu {ap_b.quantidade_acumulada}, e o recompute lê 70')
