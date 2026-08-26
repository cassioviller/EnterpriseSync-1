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


def test_bater_ponto_rejeita_funcionario_e_obra_de_outro_tenant_sem_vazar_nome():
    """🔴 `ponto_views.py:777` (`api_bater_ponto`) — `funcionario_id`/`obra_id`
    entravam sem checagem de tenant, e `PontoService.bater_ponto_obra`
    (`ponto_service.py:166`) devolvia `funcionario_nome` na resposta: o
    vazamento aqui é de DADO PESSOAL, não só de escrita — por isso ganha
    teste de comportamento, diferente dos irmãos 3a/3b.

    Nota de status: o `abort(400)` de `fk_do_tenant` é engolido pelo
    `except Exception` largo de `api_bater_ponto` (`ponto_views.py:796-798`)
    e vira 500. Isso é achado sistêmico separado, para o fecho da onda — não
    desta task, e não é para ser consertado aqui. O que esta task garante é
    que nada é gravado e o nome não vaza, qualquer que seja o código HTTP.
    """
    from models import RegistroPonto

    with app.app_context():
        a, b = dois_tenants('onda2_bponto', com_fatos=False)
        admin_a = a.admin_id
        func_b_id, obra_b_id = b.funcionario_id, b.obra_id
        nome_b = f'Funcionario {b.marca}'

    resposta = cliente_de(admin_a).post('/ponto/api/bater-ponto', json={
        'funcionario_id': func_b_id,
        'tipo_ponto': 'entrada',
        'obra_id': obra_b_id,
    })

    assert resposta.status_code in (400, 403, 500), (
        f'status inesperado: {resposta.status_code}')
    corpo = resposta.get_data(as_text=True)
    assert nome_b not in corpo, (
        'o nome do funcionário de outro tenant vazou na resposta')

    with app.app_context():
        gravado = RegistroPonto.query.filter_by(funcionario_id=func_b_id).count()
        assert gravado == 0, (
            'RegistroPonto criado para funcionário de outro tenant')


def test_registrar_falta_rejeita_funcionario_de_outro_tenant():
    """🔴 mesmo achado de `api_bater_ponto`, na irmã `api_registrar_falta`
    (`ponto_views.py:998`) — ela não recebe `obra_id`, só `funcionario_id`.
    """
    from models import RegistroPonto

    with app.app_context():
        a, b = dois_tenants('onda2_falta', com_fatos=False)
        admin_a = a.admin_id
        func_b_id = b.funcionario_id

    resposta = cliente_de(admin_a).post('/ponto/api/registrar-falta', json={
        'funcionario_id': func_b_id,
        'data': '2026-06-15',
        'motivo': 'falta',
    })

    assert resposta.status_code in (400, 403, 500), (
        f'status inesperado: {resposta.status_code}')

    with app.app_context():
        gravado = RegistroPonto.query.filter_by(funcionario_id=func_b_id).count()
        assert gravado == 0, (
            'RegistroPonto (falta) criado para funcionário de outro tenant')


# ---------------------------------------------------------------------------
# Task 7 — consultas sem admin_id
# ---------------------------------------------------------------------------

def test_dedup_de_nf_e_por_tenant_nao_global():
    """🔴 `almoxarifado_utils.py:257` — `filter_by(xml_hash=...)` sem admin_id.

    Se outro tenant já importou aquele XML, este ouve "já foi importada" e
    NUNCA consegue importar. É o mesmo defeito que `entrada_ja_lancada`
    (`views/almoxarifado/movimentos.py:16`) documenta e evita uma camada
    abaixo.
    """
    import inspect

    import almoxarifado_utils
    fonte = inspect.getsource(almoxarifado_utils)
    assert 'NotaFiscal.query.filter_by(xml_hash=xml_hash)' not in fonte, (
        'dedup de NF ainda é global entre tenants')


def test_join_do_plano_de_contas_leva_admin_id():
    """🔴 `contabilidade_views.py:1300` — join só por `codigo`.

    A PK de `PlanoContas` é composta `(admin_id, codigo)` (`models.py:3266`).
    Cada tenant que possui aquele código soma uma linha duplicada: uma partida
    de R$ 840 em ~300 tenants semeados vira R$ 252.000, com `conta.nome` de um
    plano alheio.
    """
    import inspect

    import contabilidade_views
    fonte = inspect.getsource(contabilidade_views)
    assert 'PartidaContabil.conta_codigo == PlanoContas.codigo)' not in fonte, (
        'o join de PlanoContas ainda ignora admin_id')


def test_processar_integracao_recusa_documento_de_outro_tenant():
    """🔴 `contabilidade_views.py:1377` (`processar_integracao`) — `origem_id`
    vem do JSON do request e `contabilizar_proposta_aprovada`/
    `contabilizar_entrada_material` carregam por PK pelada, lançando sob o
    `admin_id` do documento, não o do usuário.

    Cobre os dois ramos (`proposta_aprovada` e `entrada_material`) com um
    documento pertencente a OUTRO tenant. A afirmação forte é sobre a função
    de contabilização NUNCA ter sido chamada — via mock/spy — porque uma
    asserção sobre a escrita em si é hoje pouco confiável: o achado de
    `contabilidade_utils.py:221` (Onda 4, atributos inexistentes) já barra a
    escrita por outro motivo, e um teste que olhasse só para a ausência de
    lançamento passaria pela razão errada mesmo sem esta guarda.
    """
    from datetime import date
    from unittest.mock import patch

    from models import Fornecedor, NotaFiscal, Proposta

    with app.app_context():
        a, b = dois_tenants('onda2_integr', com_fatos=False)
        admin_a, admin_b = a.admin_id, b.admin_id

        proposta_b = Proposta(numero=f'P-{uuid.uuid4().hex[:8]}',
                              cliente_nome='Cliente alheio',
                              admin_id=admin_b, status='aprovada')
        db.session.add(proposta_b)

        fornecedor_b = Fornecedor(nome='Fornecedor alheio',
                                  cnpj=f'{uuid.uuid4().int % 10**14:014d}',
                                  admin_id=admin_b)
        db.session.add(fornecedor_b)
        db.session.flush()

        nf_b = NotaFiscal(numero='999', serie='1',
                          chave_acesso=uuid.uuid4().hex[:44].ljust(44, '0'),
                          fornecedor_id=fornecedor_b.id,
                          data_emissao=date(2026, 1, 1),
                          valor_produtos=100, valor_total=100,
                          admin_id=admin_b)
        db.session.add(nf_b)
        db.session.commit()
        proposta_id, nf_id = proposta_b.id, nf_b.id

    with patch('contabilidade_utils.contabilizar_proposta_aprovada') as espia:
        resposta = cliente_de(admin_a).post(
            '/contabilidade/api/processar-integracao',
            json={'tipo': 'proposta_aprovada', 'origem_id': proposta_id})
        assert resposta.status_code == 400
        assert 'Documento inválido' in resposta.get_json()['message']
        assert not espia.called, (
            'contabilizar_proposta_aprovada foi chamada para documento de outro tenant')

    with patch('contabilidade_utils.contabilizar_entrada_material') as espia:
        resposta = cliente_de(admin_a).post(
            '/contabilidade/api/processar-integracao',
            json={'tipo': 'entrada_material', 'origem_id': nf_id})
        assert resposta.status_code == 400
        assert 'Documento inválido' in resposta.get_json()['message']
        assert not espia.called, (
            'contabilizar_entrada_material foi chamada para documento de outro tenant')


def test_salvar_configuracao_de_horario_recusa_obra_de_outro_tenant():
    """🔴 `ponto_service.py:264` / `ponto_views.py` (`api_salvar_configuracao`)
    — `obra_id` vinha cru do JSON. `Obra.id` é PK global auto-increment: sem
    validação, qualquer admin autenticado apontava a escrita de configuração
    de horário para a obra de outro tenant. Diferente do 3b (que só vira
    explorável quando a Onda 4 destravar a escrita), este é um buraco ATIVO
    hoje.

    Nota de status: o `abort(400)` de `fk_do_tenant` é engolido pelo
    `except Exception` largo de `api_salvar_configuracao` e vira 500 — achado
    sistêmico separado (mesmo padrão do `api_bater_ponto`, acima), registrado
    para o fecho da onda, não para consertar aqui. O que esta task garante é
    que nada é gravado para a obra alheia, qualquer que seja o código HTTP.
    """
    from models import ConfiguracaoHorario

    with app.app_context():
        a, b = dois_tenants('onda2_cfghor', com_fatos=False)
        admin_a, obra_b_id = a.admin_id, b.obra_id

    resposta = cliente_de(admin_a).post('/ponto/api/salvar-configuracao', json={
        'obra_id': obra_b_id,
        'entrada_padrao': '08:00',
        'saida_padrao': '17:00',
        'almoco_inicio': '12:00',
        'almoco_fim': '13:00',
    })

    assert resposta.status_code in (400, 403, 500), (
        f'status inesperado: {resposta.status_code}')

    with app.app_context():
        vazou = ConfiguracaoHorario.query.filter_by(obra_id=obra_b_id).count()
        assert vazou == 0, (
            'ConfiguracaoHorario criada/alterada para obra de outro tenant')
