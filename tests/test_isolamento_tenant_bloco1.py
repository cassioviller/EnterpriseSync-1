"""Bloco 1 — o censo dos resolvedores de tenant, em vez do caso avulso.

📖 O `2026-06-02-bloco1-blindagem-acesso-plan.md` prometeu este arquivo e ele
nunca foi escrito. Três testes cobrem hoje o **efeito** do isolamento
(`test_p1_isolamento_relatorios.py`, `test_gestao_custo_filho_tenant.py`,
`test_arreio_almoxarifado_e_tenant.py`), e **nenhum** cobre a **raiz**: quem
responde à pergunta "de que empresa é este usuário?".

Por isso este arquivo é um **censo**, não um caso. A pergunta que ele faz não é
"a rota X vaza?" — é "todos os que respondem essa pergunta respondem a mesma
coisa?". O defeito que ele impede não é um vazamento: é o **quarto resolvedor**
nascer, discordando dos outros três em um papel que ninguém testou.

## Por que a raiz, e não o efeito

📖 `multitenant_helper.py` conta a história no próprio cabeçalho: ele **tinha** a
própria lógica, e ela discordava de `utils.tenant.get_tenant_admin_id` em
exatamente dois papéis — GESTOR_EQUIPES e ALMOXARIFE caíam num `return
current_user.id` que os mandava para um tenant inexistente. Oito módulos o
importam, e dois deles com o nome do resolvedor certo (`get_admin_id as
get_tenant_admin_id`, em `ponto_service.py:9` e `ponto_views.py:28`) — o defeito
era **invisível na leitura do chamador**. Nenhum teste de efeito o pegaria: cada
rota, isolada, parece correta.

## O que o censo de 01/09 achou

🔬 16 resolvedores × 5 papéis = 80 combinações. **Quatro divergiam**, todas no
mesmo papel e pela mesma causa: comparam `== TipoUsuario.ADMIN` e esquecem
`SUPER_ADMIN`, que o resolvedor canônico trata junto (`utils/tenant.py:29`).

| Módulo | SUPER_ADMIN recebia |
|---|---|
| 🔴 `propostas_consolidated` | **10** — um tenant concreto, chumbado no `return` de fallback |
| `contabilidade_views` | `None` |
| `folha_pagamento_views` | `None` |
| `crud_rdo_completo` | `None` |

🔴 O de `propostas_consolidated` era hole de tenant vivo, não divergência
acadêmica: um SUPER_ADMIN abrindo o módulo de propostas **lia e gravava dentro
da empresa 10**. É o mesmo `return 10` que `categoria_servicos.py` e
`api_funcionarios.py` já haviam removido dos seus, cada um com a sua lápide —
sobreviveu aqui porque ninguém tinha perguntado a todos ao mesmo tempo.

Os outros três falham fechado (`None`), o que não vaza mas tranca o SUPER_ADMIN
para fora de contabilidade, folha e RDO sem dizer por quê.

Os quatro papéis restantes concordavam nos dezesseis — inclusive GESTOR_EQUIPES e
ALMOXARIFE, os dois que o cabeçalho do `multitenant_helper` cita: aquela correção
entrou e este censo a mantém entrada.

## O que este censo ainda NÃO pergunta

⚠️ Uma linha ficou de fora, deliberadamente: **FUNCIONARIO sem `admin_id`**.
📖 `crud_rdo_completo.get_admin_id` tem, para esse caso, um ramo que resolve o
tenant por FK (`utils.identidade.funcionario_do_usuario`), e o canônico
devolveria `None` ali — os dois discordam, e nenhum dos dois está obviamente
certo. Exercitar a linha tornaria o censo vermelho sobre uma decisão de produto
(o RDO deve funcionar para funcionário sem vínculo de usuário?) que a Onda 6 não
tem mandato para tomar. Por isso os três outros divergentes passaram a **delegar**
ao canônico e este recebeu só a correção do papel medido, com a razão escrita no
fonte. Quem for consolidar os resolvedores começa por aqui.
"""
import importlib
import os
import sys
import uuid

import pytest
from flask_login import login_user
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from models import TipoUsuario, Usuario

pytestmark = pytest.mark.integration

# Todo módulo do parque que expõe um `get_admin_id()` próprio. A lista é o
# censo: um módulo novo com resolvedor próprio tem de entrar aqui, e é isso que
# impede o quarto resolvedor de nascer sem ninguém perguntar nada a ele.
RESOLVEDORES = [
    'alimentacao_views',
    'analytics_preditivos',
    'api_funcionarios',
    'api_servicos_obra_limpa',
    'categoria_servicos',
    'clientes_views',
    'contabilidade_views',
    'crm_views',
    'crud_rdo_completo',
    'dashboards_especificos',
    'equipe_views',
    'exportacao_relatorios',
    'folha_pagamento_views',
    'multitenant_helper',
    'propostas_consolidated',
    'views.almoxarifado',
]

PAPEIS = ['ADMIN', 'SUPER_ADMIN', 'GESTOR_EQUIPES', 'ALMOXARIFE', 'FUNCIONARIO']


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-isolamento-bloco1'
    yield


@pytest.fixture(scope='module')
def parque():
    """Um admin e um usuário de cada papel sob ele.

    Escopo de módulo porque o censo é read-only: nenhum destes testes escreve.
    O SUPER_ADMIN nasce **sem** `admin_id` de propósito — é assim que o papel
    existe no sistema, e é exatamente o caso em que os resolvedores divergem.
    """
    with app.app_context():
        marca = uuid.uuid4().hex[:6]
        admin = Usuario(
            username=f'adm{marca}', email=f'adm{marca}@t.local', nome='Admin',
            password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True)
        db.session.add(admin)
        db.session.commit()

        ids = {'ADMIN': admin.id}
        for papel in PAPEIS:
            if papel == 'ADMIN':
                continue
            usuario = Usuario(
                username=f'{papel[:6].lower()}{marca}',
                email=f'{papel[:6].lower()}{marca}@t.local', nome=papel,
                password_hash=generate_password_hash('x'),
                tipo_usuario=getattr(TipoUsuario, papel), ativo=True,
                admin_id=(None if papel == 'SUPER_ADMIN' else admin.id))
            db.session.add(usuario)
            db.session.commit()
            ids[papel] = usuario.id
        return ids


def _como(usuario_id, funcao):
    """Roda `funcao()` num request autenticado como `usuario_id`.

    Request context de verdade, e não um mock de `current_user`: metade dos
    resolvedores consulta `current_user.is_authenticated`, que um duplo simples
    responderia errado — e o teste passaria contra um resolvedor quebrado.
    """
    with app.test_request_context('/'):
        login_user(db.session.get(Usuario, usuario_id))
        return funcao()


def _canonico(usuario_id):
    from utils.tenant import get_tenant_admin_id

    return _como(usuario_id, get_tenant_admin_id)


# ---------------------------------------------------------------------------
# O censo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('modulo', RESOLVEDORES)
@pytest.mark.parametrize('papel', PAPEIS)
def test_o_resolvedor_do_modulo_concorda_com_o_canonico(parque, modulo, papel):
    """🔬 16 × 5. Um módulo que responda diferente do canônico é o defeito.

    A afirmação é de **acordo**, não de valor: não interessa aqui qual é o
    admin_id certo — interessa que não haja dois. Onde os dezesseis concordam,
    uma mudança no canônico chega a todos; onde um discorda, ele tem um tenant
    particular que nenhum outro teste conhece.
    """
    resolvedor = getattr(importlib.import_module(modulo), 'get_admin_id')

    esperado = _canonico(parque[papel])
    obtido = _como(parque[papel], resolvedor)

    assert obtido == esperado, (
        f'{modulo}.get_admin_id() devolve {obtido!r} para {papel}, e '
        f'utils.tenant.get_tenant_admin_id() devolve {esperado!r} — são dois '
        f'resolvedores com respostas diferentes para a mesma pergunta')


@pytest.mark.parametrize('papel', PAPEIS)
def test_require_tenant_devolve_o_mesmo_que_o_resolvedor(parque, papel):
    """A terceira porta: quem exige tenant tem de exigir o mesmo tenant.

    `require_tenant()` é o que as rotas sensíveis chamam. Se ele resolvesse
    diferente de `get_tenant_admin_id()`, uma rota autorizaria por um tenant e
    consultaria por outro — a forma mais silenciosa possível deste defeito.
    """
    from utils.tenant import require_tenant

    esperado = _canonico(parque[papel])
    obtido = _como(parque[papel], require_tenant)

    assert obtido == esperado, (
        f'require_tenant() devolve {obtido!r} para {papel} e o resolvedor '
        f'devolve {esperado!r} — autoriza por um tenant e consulta por outro')


@pytest.mark.parametrize('papel', PAPEIS)
def test_o_tenant_resolvido_e_um_usuario_real(parque, papel):
    """🔴 Nenhum papel pode resolver para um tenant que não é o dele.

    Existe para pegar a família de defeito que este censo achou em
    `propostas_consolidated` — o `return 10` de fallback: um id **concreto e
    chumbado**, que aponta para uma empresa real de produção e passa por
    qualquer teste que só verifique "devolveu um número".
    """
    resolvido = _canonico(parque[papel])
    esperados = {parque['ADMIN'], parque['SUPER_ADMIN']}

    assert resolvido in esperados, (
        f'{papel} resolveu para o tenant {resolvido!r}, que não é nem o admin '
        f'do parque nem ele mesmo — se for um id chumbado no código, ele '
        f'aponta para uma empresa de verdade em produção')


def test_a_lista_do_censo_cobre_quem_tem_resolvedor_proprio():
    """O censo não pode envelhecer em silêncio.

    Um módulo novo com `get_admin_id()` próprio precisa entrar em
    `RESOLVEDORES` — senão o quarto resolvedor nasce fora do alcance deste
    arquivo, que é a única coisa que ele existe para impedir. A varredura é
    pelo símbolo importável, não por texto do fonte.
    """
    faltando = []
    for modulo in RESOLVEDORES:
        if not hasattr(importlib.import_module(modulo), 'get_admin_id'):
            faltando.append(modulo)

    assert not faltando, (
        f'estes módulos estão no censo mas não expõem mais get_admin_id: '
        f'{faltando} — ou foram consolidados (tire-os da lista) ou o símbolo '
        f'mudou de nome (e o censo parou de olhar para ele)')
