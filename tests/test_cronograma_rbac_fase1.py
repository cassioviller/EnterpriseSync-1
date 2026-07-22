"""RBAC da Fase 1 aplicado às rotas de tarefa/apontamento do cronograma.

Até a Fase 1 o único eixo era o tenant: `cronograma_views.criar_tarefa`
filtra `Obra.query.filter_by(id=obra_id, admin_id=admin_id)` e pronto —
qualquer usuário autenticado do tenant edita o cronograma de qualquer obra
da empresa.

Estes testes travam o segundo eixo, em TODAS as rotas que mutam, não só nas
quatro mais óbvias. `reordenar` e `recalcular` reescrevem a estrutura do
cronograma tanto quanto `criar_tarefa`; proteger umas e não outras daria uma
falsa sensação de cobertura.

Com `escopo_obra_ativo` DESLIGADA o comportamento tem que ser idêntico ao de
antes — a flag existe justamente para que o deploy não tire acesso de
ninguém, e é o que torna a mudança reversível sem rollback.

NOTA de harness: requests do test client ficam FORA de app_context aberto —
Flask-Login cacheia `g._login_user` e congela o primeiro usuário resolvido.
Por isso todo teste captura os IDs (int) dentro do contexto e só depois faz
o request.
"""
import os
import sys
import uuid
from contextlib import contextmanager
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import (Cliente, Obra, PapelObra, TarefaCronograma, TipoUsuario,
                    Usuario, UsuarioObra)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-cronograma-rbac'
    yield


def _suf() -> str:
    return uuid.uuid4().hex[:10]


@contextmanager
def _escopo_ligado(admin_id: int):
    """Liga a flag e SEMPRE religa desligada ao sair.

    Recebe `admin_id` (int), não o objeto Usuario: fora do app_context em que
    foi carregado o objeto está detached e expirado (`expire_on_commit`), e
    ler `.id` dele levantaria DetachedInstanceError — o teardown nunca rodaria
    e a flag ficaria ligada. O `finally` cobre o caso de o assert falhar.
    """
    from scripts.flag_escopo_obra import definir_flag
    with app.app_context():
        definir_flag(admin_id, True)
    try:
        yield
    finally:
        with app.app_context():
            definir_flag(admin_id, False)


def _cenario(papel=None):
    """admin + obra + funcionário (opcionalmente vinculado) + tarefa + RDO.

    Devolve só IDs — nada de objeto ORM atravessando app_context.
    """
    from models import RDO

    with app.app_context():
        suf = _suf()
        admin = Usuario(
            username=f'cra_{suf}', email=f'cra_{suf}@test.local',
            nome=f'Adm {suf}',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
        )
        db.session.add(admin)
        db.session.commit()

        func = Usuario(
            username=f'crf_{suf}', email=f'crf_{suf}@test.local',
            nome=f'Fun {suf}',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin.id,
        )
        db.session.add(func)

        cliente = Cliente(nome=f'Cliente RBAC {suf}', admin_id=admin.id)
        db.session.add(cliente)
        db.session.flush()
        obra = Obra(nome=f'Obra RBAC {suf}', codigo=f'RB-{suf[:8].upper()}',
                    admin_id=admin.id, cliente_id=cliente.id,
                    data_inicio=date(2026, 1, 1))
        db.session.add(obra)
        db.session.flush()

        tarefa = TarefaCronograma(obra_id=obra.id, admin_id=admin.id,
                                  nome_tarefa=f'Alvo {suf}', ordem=0,
                                  duracao_dias=1, is_cliente=False)
        db.session.add(tarefa)

        rdo = RDO(numero_rdo=f'RDO-{suf[:8]}', data_relatorio=date(2026, 1, 5),
                  obra_id=obra.id, admin_id=admin.id)
        db.session.add(rdo)
        db.session.flush()

        if papel is not None:
            db.session.add(UsuarioObra(usuario_id=func.id, obra_id=obra.id,
                                       papel=papel, admin_id=admin.id))
        db.session.commit()
        return {'admin_id': admin.id, 'user_id': func.id, 'obra_id': obra.id,
                'tarefa_id': tarefa.id, 'rdo_id': rdo.id}


def _http(user_id: int):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


# ---------------------------------------------------------------------------
# Rotas que MUTAM a estrutura do cronograma → pode_editar_obra
# ---------------------------------------------------------------------------
# Cada entrada: (nome, callable(client, cenario) -> Response, status quando OK).
# `reordenar` e `recalcular` estavam fora do escopo original e são exatamente
# tão destrutivas quanto as outras: uma reescreve a ordem, a outra recalcula
# datas da obra inteira.
ROTAS_EDICAO = [
    ('criar_tarefa', lambda c, k: c.post(
        f"/cronograma/obra/{k['obra_id']}/tarefa",
        json={'nome_tarefa': 'Nova'}), 201),
    ('atualizar_tarefa', lambda c, k: c.put(
        f"/cronograma/obra/{k['obra_id']}/tarefa/{k['tarefa_id']}",
        json={'nome_tarefa': 'Renomeada'}), 200),
    ('excluir_tarefa', lambda c, k: c.delete(
        f"/cronograma/obra/{k['obra_id']}/tarefa/{k['tarefa_id']}"), 200),
    ('reordenar', lambda c, k: c.post(
        f"/cronograma/obra/{k['obra_id']}/reordenar",
        json={'ordem': [k['tarefa_id']]}), 200),
    ('recalcular', lambda c, k: c.post(
        f"/cronograma/obra/{k['obra_id']}/recalcular", json={}), 200),
]

ROTAS_APONTAMENTO = [
    ('apontar_producao', lambda c, k: c.post(
        f"/cronograma/rdo/{k['rdo_id']}/apontar",
        json={'tarefa_cronograma_id': k['tarefa_id'],
              'percentual_acumulado': 10})),
    ('apontar_subempreitada', lambda c, k: c.post(
        f"/cronograma/rdo/{k['rdo_id']}/apontar-subempreitada",
        json={'tarefa_cronograma_id': k['tarefa_id'], 'qtd_pessoas': 1})),
]


@pytest.mark.parametrize('nome,chamar,ok', ROTAS_EDICAO,
                         ids=[r[0] for r in ROTAS_EDICAO])
def test_flag_desligada_preserva_o_comportamento_antigo(nome, chamar, ok):
    """Sem a flag, funcionário do tenant continua editando — como antes."""
    k = _cenario()
    r = chamar(_http(k['user_id']), k)
    assert r.status_code == ok, (
        f'{nome}: flag desligada mudou o comportamento — '
        f'{r.status_code}: {r.get_data(as_text=True)[:200]}')


@pytest.mark.parametrize('nome,chamar,ok', ROTAS_EDICAO,
                         ids=[r[0] for r in ROTAS_EDICAO])
def test_flag_ligada_sem_vinculo_recusa(nome, chamar, ok):
    """404 e não 403: a existência de obra fora do alcance não vaza."""
    k = _cenario()
    with _escopo_ligado(k['admin_id']):
        r = chamar(_http(k['user_id']), k)
    assert r.status_code == 404, (
        f'{nome}: usuário sem vínculo editou a obra — {r.status_code}')


@pytest.mark.parametrize('nome,chamar,ok', ROTAS_EDICAO,
                         ids=[r[0] for r in ROTAS_EDICAO])
def test_flag_ligada_gestor_da_obra_edita(nome, chamar, ok):
    k = _cenario(papel=PapelObra.GESTOR)
    with _escopo_ligado(k['admin_id']):
        r = chamar(_http(k['user_id']), k)
    assert r.status_code == ok, (
        f'{nome}: GESTOR foi barrado — {r.get_data(as_text=True)[:200]}')


@pytest.mark.parametrize('nome,chamar,ok', ROTAS_EDICAO,
                         ids=[r[0] for r in ROTAS_EDICAO])
def test_flag_ligada_apontador_nao_edita_a_estrutura(nome, chamar, ok):
    """APONTADOR lança RDO; não reestrutura o cronograma."""
    k = _cenario(papel=PapelObra.APONTADOR)
    with _escopo_ligado(k['admin_id']):
        r = chamar(_http(k['user_id']), k)
    assert r.status_code == 404, (
        f'{nome}: APONTADOR reestruturou o cronograma — {r.status_code}')


@pytest.mark.parametrize('nome,chamar,ok', ROTAS_EDICAO,
                         ids=[r[0] for r in ROTAS_EDICAO])
def test_admin_do_tenant_sempre_edita_mesmo_com_flag_ligada(nome, chamar, ok):
    """ADMIN não precisa de linha em usuario_obra (decisão 4 da Fase 1)."""
    k = _cenario()
    with _escopo_ligado(k['admin_id']):
        r = chamar(_http(k['admin_id']), k)
    assert r.status_code == ok, (
        f'{nome}: ADMIN do tenant foi barrado — '
        f'{r.get_data(as_text=True)[:200]}')


def test_excluir_tarefa_recusada_nao_apaga_nada():
    """404 tem que ser recusa de verdade, não 'apagou e devolveu erro'."""
    k = _cenario()
    with _escopo_ligado(k['admin_id']):
        r = _http(k['user_id']).delete(
            f"/cronograma/obra/{k['obra_id']}/tarefa/{k['tarefa_id']}")
    assert r.status_code == 404
    with app.app_context():
        assert db.session.get(TarefaCronograma, k['tarefa_id']) is not None


# ---------------------------------------------------------------------------
# Rotas de APONTAMENTO → pode_apontar_na_obra (GESTOR e APONTADOR passam)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('nome,chamar', ROTAS_APONTAMENTO,
                         ids=[r[0] for r in ROTAS_APONTAMENTO])
def test_apontamento_sem_vinculo_recusa(nome, chamar):
    k = _cenario()
    with _escopo_ligado(k['admin_id']):
        r = chamar(_http(k['user_id']), k)
    assert r.status_code == 404, (
        f'{nome}: usuário sem vínculo apontou na obra — {r.status_code}')


@pytest.mark.parametrize('papel', [PapelObra.GESTOR, PapelObra.APONTADOR],
                         ids=['gestor', 'apontador'])
@pytest.mark.parametrize('nome,chamar', ROTAS_APONTAMENTO,
                         ids=[r[0] for r in ROTAS_APONTAMENTO])
def test_apontamento_permitido_para_quem_aponta(nome, chamar, papel):
    """O eixo de apontamento é mais largo que o de edição: APONTADOR passa."""
    k = _cenario(papel=papel)
    with _escopo_ligado(k['admin_id']):
        r = chamar(_http(k['user_id']), k)
    assert r.status_code != 404, (
        f'{nome}/{papel}: quem pode apontar foi barrado pelo escopo — '
        f'{r.get_data(as_text=True)[:200]}')


def test_excluir_apontamento_subempreitada_respeita_escopo():
    """A rota recebe `apt_id`, não `obra_id` — o escopo sai do RDO."""
    from models import RDOSubempreitadaApontamento, Subempreiteiro

    k = _cenario()
    with app.app_context():
        sub = Subempreiteiro(nome=f'Sub {_suf()}', ativo=True,
                             admin_id=k['admin_id'])
        db.session.add(sub)
        db.session.flush()
        apt = RDOSubempreitadaApontamento(
            rdo_id=k['rdo_id'], tarefa_cronograma_id=k['tarefa_id'],
            subempreiteiro_id=sub.id,
            admin_id=k['admin_id'], qtd_pessoas=1)
        db.session.add(apt)
        db.session.commit()
        apt_id = apt.id

    with _escopo_ligado(k['admin_id']):
        r = _http(k['user_id']).delete(
            f'/cronograma/rdo/apontamento-subempreitada/{apt_id}')
    assert r.status_code == 404
    with app.app_context():
        assert db.session.get(RDOSubempreitadaApontamento, apt_id) is not None
