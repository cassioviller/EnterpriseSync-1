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
