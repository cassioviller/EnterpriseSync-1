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
    """🔴 `views/aditivos_views.py:144` — `@obra_required(PapelObra.GESTOR)`.

    Com `escopo_obra_ativo` desligado (`models.py:4441`, `default=False` — o
    estado de todo tenant existente), `papel_de_usuario_na_obra`
    (`utils/autorizacao.py:147-160`) devolve GESTOR para QUALQUER usuário
    autenticado do tenant. Aprovar aditivo grava `ObraContratoVersao`, lança
    delta contábil e desloca cronograma — irreversível por desenho.

    O fallback permissivo é decisão consciente e documentada; o defeito é
    pendurar ação irreversível nele. Ver D5.
    """
    from models import ObraContratoVersao

    with app.app_context():
        marca = uuid.uuid4().hex[:8]
        t = um_tenant('adit-authz', com_fatos=False)
        func_id = _funcionario_logavel(t.admin_id, marca)

        versoes_antes = ObraContratoVersao.query.filter_by(
            obra_id=t.obra_id).count()

        cliente = cliente_de(func_id)
        resposta = cliente.post(
            f'/obras/{t.obra_id}/aditivos/novo',
            data={'valor_novo': '150.000,00', 'prazo_delta_dias': '30',
                  'justificativa': f'invasao-{marca}'},
            follow_redirects=False)

        assert resposta.status_code in (302, 403, 404), (
            f'FUNCIONARIO recebeu {resposta.status_code} ao abrir aditivo')

        versoes_depois = ObraContratoVersao.query.filter_by(
            obra_id=t.obra_id).count()
        assert versoes_depois == versoes_antes, (
            'FUNCIONARIO moveu a linha de base do contrato — '
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
