"""B6.8 — lote e: a cauda heterogênea, e o único oráculo de enumeração da família.

**Estado medido em 31/08: a Task B6.8 nunca foi executada** — como as outras
quatro da família 404 (`grep -c 'except HTTPException'` = 0 nos arquivos do
lote). Este arquivo trata os sítios da cauda, e **um deles é diferente dos
demais e foi corrigido junto**:

🔴 `views/admin.py:441` (`admin_webhooks_reenviar`) era, nas palavras do plano
(`rodada-b6:747-751`), *"o ÚNICO oráculo de enumeração vivo da família"*:
`db.session.get(WebhookEntrega, id)` sem tenant, seguido de **duas mensagens
distintas** — "Entrega #N não encontrada" para id inexistente, "Você não tem
permissão" para entrega de outro tenant. A diferença entre as duas respostas
**é** a informação: um admin de A descobre quais ids de entrega existem em B.

Os demais sítios da cauda continuam como `xfail(strict=True)`: são 302 onde
deveria haver 404, sem oráculo (as duas respostas são idênticas), e consertá-los
é o refactor de ~60 sítios que a Onda 6 não comporta.
"""
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from helpers_tenant import cliente_de, dois_tenants

pytestmark = pytest.mark.integration

INEXISTENTE = 999_999_999


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-b6-404-cauda'
    yield


@pytest.fixture
def _webhook_ligado(monkeypatch):
    """`admin_webhooks_reenviar` sai pela porta "webhook desligado" antes do
    lookup quando `N8N_WEBHOOK_URL` não está configurada — que é o caso na
    suíte. Sem este arreio o teste do oráculo passaria verde sem nunca ter
    chegado à guarda que ele veio medir.
    """
    import utils.webhook_dispatcher as wd

    monkeypatch.setattr(wd, 'is_enabled', lambda: True)
    monkeypatch.setattr(wd, 'reentregar_uma', lambda _id: True)
    yield


def _entrega(admin_id):
    from models import WebhookEntrega

    e = WebhookEntrega(admin_id=admin_id, event='rdo.criado',
                       payload={'marca': uuid.uuid4().hex[:8]},
                       status='erro', tentativas=1)
    db.session.add(e)
    db.session.commit()
    return e


# ---------------------------------------------------------------------------
# views/admin.py:441 — o oráculo de enumeração (CORRIGIDO nesta onda)
# ---------------------------------------------------------------------------

def test_o_dono_reenvia_a_propria_entrega_precondicao(_webhook_ligado):
    """Precondição do teste do oráculo: a rota funciona para o dono.

    Sem ela, uma rota que respondesse 404 para todo mundo — inclusive para o
    dono — faria o teste do oráculo passar verde enquanto o reenvio inteiro
    estivesse quebrado.
    """
    with app.app_context():
        a, _b = dois_tenants('b6cauda_pre', com_fatos=False)
        entrega = _entrega(a.admin_id)

        resposta = cliente_de(a.admin_id).post(
            f'/admin/webhooks/{entrega.id}/reenviar')

        assert resposta.status_code == 302, (
            f'o dono recebeu {resposta.status_code} ao reenviar a própria '
            f'entrega — andaime quebrado')
        assert resposta.headers.get('Location', '').endswith('/admin/webhooks')


def test_reenviar_entrega_alheia_nao_diz_se_ela_existe(_webhook_ligado):
    """🔴 O oráculo de enumeração — `views/admin.py:441`.

    O admin do tenant B pede reenvio de duas coisas: uma entrega que **existe**
    (é do tenant A) e um id que **não existe em lugar nenhum**. As duas
    respostas têm de ser indistinguíveis — status e corpo. Enquanto forem
    diferentes, a rota responde a pergunta "esse id existe?" para quem não pode
    vê-lo.

    RED medido em 31/08, antes do fix:
        existente → 302 + flash 'Você não tem permissão para reenviar esta
                    entrega.'
        inexistente → 302 + flash 'Entrega #999999999 não encontrada.'

    A regra da casa é 404 com mensagem única, nunca 403 —
    `views/almoxarifado/movimentos.py:276-280` a escreve por extenso: *"404,
    nunca 403: 403 confirma que o fornecedor existe em outra empresa e
    transforma a rota em oráculo de enumeração."*
    """
    with app.app_context():
        a, b = dois_tenants('b6cauda_oraculo', com_fatos=False)
        entrega_de_a = _entrega(a.admin_id)

        cli_b = cliente_de(b.admin_id)
        alheia = cli_b.post(f'/admin/webhooks/{entrega_de_a.id}/reenviar',
                            follow_redirects=True)
        inexistente = cli_b.post(f'/admin/webhooks/{INEXISTENTE}/reenviar',
                                 follow_redirects=True)

        # ⚠️ `follow_redirects=True` é o que torna a medição honesta. Antes do
        # fix os dois casos respondiam o MESMO 302 para `/admin/webhooks`, e um
        # teste que olhasse só o status passaria verde: a informação não estava
        # no status, estava no flash — que só é renderizado na página seguinte,
        # que é a que o usuário lê.
        alheia_txt = alheia.get_data(as_text=True)
        inexistente_txt = inexistente.get_data(as_text=True)

        assert alheia.status_code == inexistente.status_code, (
            f'a rota distingue existente ({alheia.status_code}) de inexistente '
            f'({inexistente.status_code}) no status')
        assert alheia.status_code == 404, (
            f'a recusa respondeu {alheia.status_code}; a regra da casa é 404')
        assert alheia_txt == inexistente_txt, (
            'os corpos diferem — o texto que o usuário lê ainda diz qual dos '
            'dois casos ocorreu')
        assert 'permissão' not in alheia_txt, (
            'a resposta ainda fala em permissão, que é o que confirma a '
            'existência do recurso em outra empresa')


def test_a_entrega_alheia_nao_e_reenviada(_webhook_ligado, monkeypatch):
    """A recusa é recusa de verdade, não só de status.

    O 404 não pode ser cosmético: `reentregar_uma` não pode ter sido chamada.
    Um espião registra as chamadas — sem isso, uma rota que reenviasse e
    **depois** respondesse 404 passaria no teste de cima.
    """
    import utils.webhook_dispatcher as wd

    chamadas = []
    monkeypatch.setattr(wd, 'reentregar_uma', lambda _id: chamadas.append(_id))

    with app.app_context():
        a, b = dois_tenants('b6cauda_naoreenvia', com_fatos=False)
        entrega_de_a = _entrega(a.admin_id)

        cliente_de(b.admin_id).post(
            f'/admin/webhooks/{entrega_de_a.id}/reenviar')

        assert chamadas == [], (
            f'a entrega de outro tenant foi reenviada mesmo assim: {chamadas}')


# ---------------------------------------------------------------------------
# O resto da cauda — 302 onde deveria ser 404, sem oráculo
# ---------------------------------------------------------------------------

def test_o_dono_edita_o_proprio_funcionario_precondicao():
    """Precondição do xfail de `POST /funcionarios/<id>/editar`."""
    with app.app_context():
        a, _b = dois_tenants('b6cauda_pre_func', com_fatos=False)

        resposta = cliente_de(a.admin_id).post(
            f'/funcionarios/{a.funcionario_id}/editar',
            data={'nome': 'Nome Novo', 'cpf': '12345678901'})

        assert resposta.status_code in (200, 302), (
            f'o dono recebeu {resposta.status_code} ao editar o próprio '
            f'funcionário — andaime quebrado')


@pytest.mark.xfail(strict=True, reason='B6.8 nunca executada (medido em 31/08) '
                   '— views/api.py:550 responde flash + 302 onde deveria 404')
def test_editar_funcionario_de_outro_tenant_da_404():
    """`POST /funcionarios/<id>/editar` — `views/api.py:550`.

    A afirmação sobre o DADO vem antes da do status, e fora do que o `xfail`
    cobre: o nome do funcionário de A não pode ter mudado.
    """
    from models import Funcionario

    with app.app_context():
        a, b = dois_tenants('b6cauda_api', com_fatos=False)
        nome_original = db.session.get(Funcionario, a.funcionario_id).nome

        resposta = cliente_de(b.admin_id).post(
            f'/funcionarios/{a.funcionario_id}/editar',
            data={'nome': 'INVASOR', 'cpf': '12345678901'})

        assert db.session.get(Funcionario, a.funcionario_id).nome == nome_original, (
            '🔴 o funcionário do tenant A foi renomeado por B — isto é bem pior '
            'que o 404 que falta')
        assert resposta.status_code == 404, (
            f'edição de funcionário alheio respondeu {resposta.status_code}')
