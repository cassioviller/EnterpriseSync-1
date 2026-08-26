"""Onda 2 — o tenant para de vazar.

O arreio é `tests/helpers_tenant.py` (`dois_tenants`, `cliente_de`), que existe
desde o p1. A regra dele: nada é compartilhado entre A e B, e a busca é PELA
MARCA — contar dá o mesmo número quando cada tenant tem um registro.
"""
import os
import sys
import uuid

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from helpers_tenant import cliente_de, dois_tenants
from models import TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-onda2-tenant'
    yield


def _usuario_com_papel(papel, admin_id):
    """Um usuário do papel pedido, pendurado num admin que NÃO é ele."""
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'onda2_{suf}', email=f'onda2_{suf}@test.local',
        nome=f'Papel {papel.value} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=papel, ativo=True, admin_id=admin_id,
    )
    db.session.add(u)
    db.session.flush()
    return u


# ---------------------------------------------------------------------------
# Task 2 — a raiz
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('papel', [TipoUsuario.GESTOR_EQUIPES,
                                   TipoUsuario.ALMOXARIFE])
def test_gestor_e_almoxarife_resolvem_o_tenant_do_dono(papel):
    """🔴 `multitenant_helper.py:25` devolvia `current_user.id` para estes dois.

    Um gestor com id=42 e admin_id=7 escrevia tudo em admin_id=42 — um tenant
    que não existe. Invisível para o admin 7, e leitura vazia de volta.
    """
    from multitenant_helper import get_admin_id
    from utils.tenant import get_tenant_admin_id

    with app.app_context():
        a, _b = dois_tenants('onda2_raiz', com_fatos=False)
        usuario = _usuario_com_papel(papel, admin_id=a.admin_id)
        db.session.commit()
        uid, esperado = usuario.id, a.admin_id

    assert uid != esperado, 'o fixture precisa distinguir id de admin_id'

    cliente = cliente_de(uid)
    with cliente.session_transaction():
        pass
    with app.test_request_context():
        from flask_login import login_user
        login_user(Usuario.query.get(uid))
        assert get_admin_id() == esperado, (
            f'{papel.value}: get_admin_id devolveu o próprio id, não o do dono')
        # e os dois resolvedores passam a concordar, que é o ponto da task
        assert get_admin_id() == get_tenant_admin_id()


@pytest.mark.parametrize('papel', [TipoUsuario.ADMIN, TipoUsuario.SUPER_ADMIN])
def test_admin_e_super_admin_nao_mudam(papel):
    """A delegação não pode mexer nos papéis que já estavam certos."""
    from multitenant_helper import get_admin_id

    with app.app_context():
        suf = uuid.uuid4().hex[:8]
        u = Usuario(username=f'onda2adm_{suf}',
                    email=f'onda2adm_{suf}@test.local', nome='Adm',
                    password_hash=generate_password_hash('Senha@2026'),
                    tipo_usuario=papel, ativo=True, versao_sistema='v2')
        db.session.add(u)
        db.session.commit()
        uid = u.id

    with app.test_request_context():
        from flask_login import login_user
        login_user(Usuario.query.get(uid))
        assert get_admin_id() == uid


def test_sem_request_context_devolve_none_em_vez_de_levantar():
    """A casca defensiva de hoje precisa sobreviver à delegação.

    `get_tenant_admin_id` acessa `current_user` direto e levanta fora de
    request; `get_admin_id` é chamado de job, seed e CLI.
    """
    from multitenant_helper import get_admin_id
    assert get_admin_id() is None


# ---------------------------------------------------------------------------
# Task 5 — FK vinda de formulário
# ---------------------------------------------------------------------------

def test_fk_do_tenant_aceita_o_que_e_do_tenant():
    from models import Obra
    from utils.fk_do_tenant import fk_do_tenant

    with app.app_context():
        a, _b = dois_tenants('onda2_fk_ok', com_fatos=False)
        with app.test_request_context():
            assert fk_do_tenant(Obra, a.obra_id, a.admin_id,
                                campo='obra') == a.obra_id
            assert fk_do_tenant(Obra, '', a.admin_id, campo='obra') is None
            assert fk_do_tenant(Obra, None, a.admin_id, campo='obra') is None


def test_fk_do_tenant_recusa_id_de_outro_tenant():
    from werkzeug.exceptions import BadRequest

    from models import Obra
    from utils.fk_do_tenant import fk_do_tenant

    with app.app_context():
        a, b = dois_tenants('onda2_fk_no', com_fatos=False)
        with app.test_request_context():
            with pytest.raises(BadRequest) as exc:
                fk_do_tenant(Obra, b.obra_id, a.admin_id, campo='obra')
            # a mensagem NÃO pode confirmar que a obra existe
            texto = str(exc.value).lower()
            assert 'outro tenant' not in texto
            assert 'não existe' not in texto


def test_fk_do_tenant_exige_quando_obrigatorio():
    from werkzeug.exceptions import BadRequest

    from models import Obra
    from utils.fk_do_tenant import fk_do_tenant

    with app.app_context():
        a, _b = dois_tenants('onda2_fk_ob', com_fatos=False)
        with app.test_request_context():
            with pytest.raises(BadRequest):
                fk_do_tenant(Obra, '', a.admin_id, campo='obra',
                             obrigatorio=True)


def test_lancamento_de_transporte_nao_prende_custo_na_obra_alheia():
    """🔴 `transporte_views.py` (`novo_post`) — cinco FKs entravam sem checagem.

    Só `osc_id` era validado. Um POST forjado prendia o lançamento e o
    `CustoObra` à obra de outro tenant, cujo nome passava a aparecer na
    listagem deste.

    Todos os campos são válidos e do tenant A, EXCETO `obra_id`, que é
    forjado com a obra do tenant B. `categoria_id` e `centro_custo_id` são
    `nullable=False` em `LancamentoTransporte` — sem eles a rota levanta
    `TypeError` em `int(request.form.get('categoria_id'))` antes mesmo de
    chegar em `obra_id`, e o teste "passa" por crash, não por validação.
    Isso já aconteceu uma vez nesta task (ver task-5-report.md) — daí o
    cuidado de semear os dois.
    """
    from models import CategoriaTransporte, CentroCusto, LancamentoTransporte

    with app.app_context():
        a, b = dois_tenants('onda2_transp', com_fatos=False)
        admin_a, obra_b, marca_b = a.admin_id, b.obra_id, b.marca

        categoria = CategoriaTransporte(nome=f'Categoria {a.marca}',
                                        admin_id=admin_a)
        centro_custo = CentroCusto(admin_id=admin_a, codigo=a.marca[:10],
                                   nome=f'Centro {a.marca}',
                                   tipo='departamento')
        db.session.add_all([categoria, centro_custo])
        db.session.commit()
        categoria_id, centro_custo_id = categoria.id, centro_custo.id

    resposta = cliente_de(admin_a).post('/transporte/novo', data={
        'obra_id': str(obra_b),
        'categoria_id': str(categoria_id),
        'centro_custo_id': str(centro_custo_id),
        'data_lancamento': '2026-08-25',
        'valor': '100,00',
        'descricao': f'forjado contra {marca_b}',
    }, follow_redirects=False)
    assert resposta.status_code in (400, 403, 302)

    with app.app_context():
        vazou = LancamentoTransporte.query.filter_by(obra_id=obra_b).count()
        assert vazou == 0, 'lançamento gravado na obra de outro tenant'


# ---------------------------------------------------------------------------
# Task 6 — setattr cego e mudança de dono por formulário
# ---------------------------------------------------------------------------

def test_veiculo_nao_tem_mais_setattr_cego():
    """🔴 `veiculos_services.py:167` — `hasattr` diz sim para `admin_id`."""
    import inspect

    import veiculos_services
    fonte = inspect.getsource(veiculos_services)
    assert 'if hasattr(veiculo, campo):' not in fonte, (
        'ainda há setattr cego: hasattr responde sim para admin_id')


def test_lista_branca_de_veiculo_nao_deixa_passar_dono_nem_id():
    from veiculos_services import CAMPOS_EDITAVEIS_VEICULO
    assert 'admin_id' not in CAMPOS_EDITAVEIS_VEICULO
    assert 'id' not in CAMPOS_EDITAVEIS_VEICULO


def test_post_com_admin_id_alheio_nao_transfere_o_veiculo():
    """O achado inteiro em uma asserção: o dicionário do formulário levava
    `admin_id=<outro tenant>` e o `setattr` cego transferia o veículo — e, por
    cascade, todo o histórico dele.
    """
    from models import Veiculo
    from veiculos_services import VeiculoService

    with app.app_context():
        a, b = dois_tenants('onda2_veic', com_fatos=False)
        veiculo = Veiculo(placa=f'AAA{uuid.uuid4().hex[:4].upper()}',
                          marca='Marca', modelo='Modelo', ano=2020,
                          admin_id=a.admin_id)
        db.session.add(veiculo)
        db.session.commit()
        vid, dono_antes, admin_b = veiculo.id, veiculo.admin_id, b.admin_id

    with app.app_context():
        # o dicionário chega como `request.form.to_dict()` chegaria
        _ok, _v, _msg = VeiculoService.atualizar_veiculo(
            vid, {'modelo': 'Modelo Novo', 'admin_id': str(admin_b)},
            admin_id=dono_antes)
        depois = Veiculo.query.get(vid)
        assert depois.admin_id == dono_antes, (
            'o veículo mudou de tenant por um campo do formulário')
        assert depois.modelo == 'Modelo Novo', (
            'a lista branca bloqueou um campo que era editável de verdade')


def test_rdo_nao_muda_de_obra_sem_checagem_de_tenant():
    """🔴 `rdo_editar_sistema.py:218` — `rdo.obra_id = obra_id` cru."""
    import inspect

    import rdo_editar_sistema
    fonte = inspect.getsource(rdo_editar_sistema)
    assert 'rdo.obra_id = obra_id' not in fonte, (
        'obra_id do formulário ainda entra sem validação de tenant')
