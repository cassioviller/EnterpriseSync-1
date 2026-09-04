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

## A linha que estava fora do censo entrou (01/09)

A exceção deliberada — **FUNCIONARIO sem `admin_id`** — acabou: a decisão de
produto que a Onda 6 não tinha mandato para tomar foi tomada em 01/09
(`2026-09-01-decisoes-respondidas.md` §admin_id): usuário nesse estado é
**defeito de dado** e falha FECHADO, como `utils/tenant.py` documenta. O ramo
de `crud_rdo_completo.get_admin_id` que resolvia o tenant por FK
(`utils.identidade.funcionario_do_usuario`) saiu; o módulo delega ao canônico
como os outros três. O caso é exercitado por
`test_funcionario_sem_admin_id_falha_fechado_tambem_no_rdo`, e o tamanho do
reparo de dado em produção é medido por
`scripts/medir_funcionarios_sem_admin_id.py` — rodar ANTES do deploy.
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
# Entrada: 'modulo' (símbolo padrão get_admin_id) ou 'modulo:símbolo' —
# Task 11 de 01/09: o parque tem resolvedor com três nomes (_get_admin_id,
# _admin_id, get_admin_id_dinamico) e o censo por um nome só deixava
# dez deles do lado de fora.
RESOLVEDORES = [
    'alimentacao_views',
    'analytics_preditivos',
    'api_funcionarios',
    'api_servicos_obra_limpa',
    'cadastros_views:_get_admin_id',
    'categoria_servicos',
    'clientes_views',
    'compras_views:_admin_id',
    'contabilidade_views',
    'crm_views',
    'cronograma_views:_admin_id',
    'crud_rdo_completo',
    'dashboards_especificos',
    'equipe_views',
    'folha_pagamento_views',
    'medicao_views:_admin_id',
    'multitenant_helper',
    'propostas_consolidated',
    'resultado_views:_admin_id',
    'subempreiteiros_views:_admin_id',
    'transporte_views:_get_admin_id',
    'views.almoxarifado',
    'views.catalogo_views:_admin_id',
    'views.helpers:get_admin_id_dinamico',
    'views.helpers:get_admin_id_robusta',
    'views.metricas_views:_admin_id',
    'views.obras:get_admin_id_robusta',
    'views.orcamento_operacional_views:_admin_id',
    'views.orcamentos_views:_admin_id',
    'views.quick_create_views:_admin_id',
    'vinculos_audit_views:_admin_id',
]

# Resolvedores com GATE de papel embutido: devolvem None de propósito para
# papéis sem acesso ao módulo (autorização, não divergência de tenant — o
# mesmo falso alarme que o censo do B6.7 aprendeu a não contar). Ficam fora
# da matriz de acordo por papel, mas DENTRO da sonda do tenant fantasma:
# gate nenhum autoriza inventar tenant.
RESOLVEDORES_COM_GATE = [
    'views.catalogos_views:_get_admin_id',  # só ADMIN/SUPER_ADMIN entram no catálogo
]


def _resolvedor(entrada):
    modulo, _, simbolo = entrada.partition(':')
    return getattr(importlib.import_module(modulo), simbolo or 'get_admin_id')

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

        # A sonda do tenant fantasma (Task 11 de 01/09): FUNCIONARIO com
        # admin_id vazio e sem FK — defeito de dado. O canônico falha
        # fechado (None); todo resolvedor com `return current_user.id` de
        # fallback inventa um tenant que não existe. Fora de PAPEIS de
        # propósito: não é papel, é defeito.
        orfao = Usuario(
            username=f'orfao{marca}', email=f'orfao{marca}@t.local',
            nome='Órfão', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True, admin_id=None)
        db.session.add(orfao)
        db.session.commit()
        ids['FUNCIONARIO_ORFAO'] = orfao.id
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

@pytest.mark.parametrize('entrada', RESOLVEDORES)
@pytest.mark.parametrize('papel', PAPEIS)
def test_o_resolvedor_do_modulo_concorda_com_o_canonico(parque, entrada, papel):
    """🔬 23 × 5. Um módulo que responda diferente do canônico é o defeito.

    A afirmação é de **acordo**, não de valor: não interessa aqui qual é o
    admin_id certo — interessa que não haja dois. Onde todos concordam,
    uma mudança no canônico chega a todos; onde um discorda, ele tem um tenant
    particular que nenhum outro teste conhece.
    """
    esperado = _canonico(parque[papel])
    obtido = _como(parque[papel], _resolvedor(entrada))

    assert obtido == esperado, (
        f'{entrada} devolve {obtido!r} para {papel}, e '
        f'utils.tenant.get_tenant_admin_id() devolve {esperado!r} — são dois '
        f'resolvedores com respostas diferentes para a mesma pergunta')


@pytest.mark.parametrize('entrada', RESOLVEDORES + RESOLVEDORES_COM_GATE)
def test_nenhum_resolvedor_inventa_tenant_para_o_orfao(parque, entrada):
    """🔴 A sonda do tenant fantasma (Task 11 de 01/09).

    FUNCIONARIO sem `admin_id` é defeito de dado; o canônico falha fechado.
    O padrão `admin_id if set else current_user.id`, copiado em vários
    módulos, devolve aqui o id do PRÓPRIO usuário como tenant — uma
    empresa que não existe (ou pior: que existe e é de outro). Vale também
    para os resolvedores com gate: gate nenhum autoriza inventar tenant.
    """
    from werkzeug.exceptions import HTTPException

    esperado = _canonico(parque['FUNCIONARIO_ORFAO'])
    assert esperado is None, (
        'pré-condição: o canônico falha FECHADO para o órfão — se isso '
        'mudou, o censo inteiro mudou de premissa')

    try:
        obtido = _como(parque['FUNCIONARIO_ORFAO'], _resolvedor(entrada))
    except HTTPException as e:
        # abortar 401/403 é falhar MAIS fechado que devolver None — é o que
        # require_tenant faz (vinculos_audit_views) e é aceito
        assert e.code in (401, 403), (
            f'{entrada} abortou {e.code} para o órfão — só 401/403 são '
            f'falha fechada legítima')
        return

    assert obtido == esperado, (
        f'{entrada} devolve {obtido!r} para FUNCIONARIO sem admin_id — um '
        f'tenant fantasma onde o canônico falha fechado (None)')


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


def test_funcionario_sem_admin_id_falha_fechado_tambem_no_rdo(parque):
    """A linha deliberadamente fora do censo entra (decisão de 01/09).

    FUNCIONARIO com `admin_id` vazio mas com a FK `funcionario_id` viva:
    `crud_rdo_completo.get_admin_id` resolvia o tenant pela FK onde o
    canônico falha fechado (`None` ⇒ 403 nas guardas). Decisão registrada:
    usuário nesse estado é DEFEITO DE DADO — conserta-se o dado, não se
    adivinha o tenant. A medição do reparo em produção é
    `scripts/medir_funcionarios_sem_admin_id.py`.
    """
    import crud_rdo_completo
    from models import Funcionario
    from datetime import date

    with app.app_context():
        marca = uuid.uuid4().hex[:6]
        funcionario = Funcionario(
            codigo=f'X{marca[:5]}', nome=f'Órfão {marca}',
            data_admissao=date(2026, 1, 1), admin_id=parque['ADMIN'],
            ativo=True)
        db.session.add(funcionario)
        db.session.flush()
        usuario = Usuario(
            username=f'orfao{marca}', email=f'orfao{marca}@t.local',
            nome='Órfão', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=None, funcionario_id=funcionario.id)
        db.session.add(usuario)
        db.session.commit()
        uid = usuario.id

    esperado = _canonico(uid)
    assert esperado is None, (
        'pré-condição: o canônico falha FECHADO para FUNCIONARIO sem '
        'admin_id — se isso mudou, o censo inteiro mudou de premissa')

    obtido = _como(uid, crud_rdo_completo.get_admin_id)
    assert obtido == esperado, (
        f'crud_rdo_completo.get_admin_id devolve {obtido!r} onde o canônico '
        f'falha fechado (None) — o ramo de FK ressuscitou, e um defeito de '
        f'dado volta a virar tenant por adivinhação')


# Resolvedores medidos e deliberadamente FORA do censo, com o porquê.
# Task 11 de 01/09 — registrar aqui é o que impede a exclusão silenciosa.
FORA_DO_CENSO = {
    # não resolve "de que empresa é este usuário": repara admin_id de LINHAS
    # de tabela via FK, outra pergunta (get_admin_id_via_relationship/mode)
    'fix_all_admin_id_universal',
    # resolvedores ANINHADOS dentro de função (rdo_editar_sistema.py:29,
    # views/rdo.py:2864) — não importáveis; consolidá-los é refactor das
    # funções-mãe, registrado para a onda das automações
    'rdo_editar_sistema',
    'views.rdo',
}

_NOMES_DE_RESOLVEDOR = ('get_admin_id', '_get_admin_id', '_admin_id',
                        'get_admin_id_dinamico', 'get_admin_id_robusta')


def test_a_lista_do_censo_cobre_quem_tem_resolvedor_proprio():
    """O censo não pode envelhecer em silêncio — nas DUAS direções.

    (1) Toda entrada da lista ainda expõe o símbolo que diz expor. (2) Todo
    módulo do parque com um `def` de resolvedor no nível do módulo está no
    censo ou em FORA_DO_CENSO com razão escrita. A varredura (2) é por
    texto do fonte de propósito: foi um censo só por `hasattr('get_admin_id')`
    que deixou dez resolvedores (_get_admin_id, _admin_id, …) fora por dois
    meses — medido em 01/09.
    """
    import re

    # direção 1: a lista não aponta para símbolo morto
    faltando = []
    for entrada in RESOLVEDORES + RESOLVEDORES_COM_GATE:
        modulo, _, simbolo = entrada.partition(':')
        if not hasattr(importlib.import_module(modulo), simbolo or 'get_admin_id'):
            faltando.append(entrada)
    assert not faltando, (
        f'estas entradas do censo não expõem mais o símbolo: {faltando} — '
        f'ou foram consolidadas (tire-as da lista) ou o símbolo mudou de '
        f'nome (e o censo parou de olhar para ele)')

    # direção 2: nenhum resolvedor do parque fora do censo
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    padrao = re.compile(
        r'^def (' + '|'.join(_NOMES_DE_RESOLVEDOR) + r')\(', re.MULTILINE)
    censo = {e.partition(':')[0] for e in RESOLVEDORES + RESOLVEDORES_COM_GATE}
    fora = []
    for pasta in ('', 'views'):
        base = os.path.join(raiz, pasta)
        for arquivo in sorted(os.listdir(base)):
            if not arquivo.endswith('.py'):
                continue
            caminho = os.path.join(base, arquivo)
            with open(caminho, encoding='utf-8') as f:
                if not padrao.search(f.read()):
                    continue
            nome = arquivo[:-3]
            modulo = f'{pasta}.{nome}' if pasta else nome
            if modulo == 'views.__init__':
                continue
            # views/almoxarifado é pacote e já está no censo; utils/tenant
            # é o próprio canônico
            if modulo not in censo and modulo not in FORA_DO_CENSO:
                fora.append(modulo)

    assert not fora, (
        f'módulos com resolvedor próprio FORA do censo: {fora} — inclua em '
        f'RESOLVEDORES (ou RESOLVEDORES_COM_GATE, se o None for gate '
        f'deliberado de papel), ou em FORA_DO_CENSO com a razão escrita')
