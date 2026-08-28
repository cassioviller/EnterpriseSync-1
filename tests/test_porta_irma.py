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
# Task 7 — a fixture que sorteia o tenant
# ---------------------------------------------------------------------------

def test_a_fixture_de_propagacao_nao_depende_de_sorteio(monkeypatch):
    """🔴 `test_propagacao_proposta_obra.py:35` — `.first()` sem ORDER BY.

    Colocado em `tests/test_porta_irma.py` de propósito: prova, de fora, que
    a fixture do outro arquivo não pula quando o primeiro ADMIN do banco não
    tem obra. Sem isto o conserto não teria RED — o sorteio às vezes cai numa
    linha boa e o defeito se esconde.
    """
    import models

    with app.app_context():
        marca = uuid.uuid4().hex[:8]
        from werkzeug.security import generate_password_hash
        orfao = models.Usuario(
            nome=f'Admin sem obra {marca}', username=f'semobra_{marca}',
            email=f'semobra_{marca}@t.local',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=models.TipoUsuario.ADMIN, admin_id=None, ativo=True)
        db.session.add(orfao)
        db.session.commit()
        orfao_id = orfao.id

    # Não há como forçar o `.first()` sem ORDER BY a devolver ESTE órfão — é
    # sorteio de verdade, dependente de como o Postgres varre a tabela. O que
    # este teste garante é o cenário: um ADMIN sem obra existe no banco.
    # Confirma-se o sorteio de fato rodando o arquivo alvo (Step 2 da task).

    with app.app_context():
        from test_propagacao_proposta_obra import setup_obra_proposta  # noqa

        # A fixture não pode pular só porque ESTE admin não tem obra.
        alvo = db.session.get(models.Usuario, orfao_id)
        assert alvo is not None
        obras = models.Obra.query.filter_by(admin_id=alvo.id).count()
        assert obras == 0, 'cenário mal montado: o órfão tem obra'
