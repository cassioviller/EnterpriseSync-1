"""Fase 3 — alçada de aprovação de compras.

Até 2026-07-21 não existia alçada nenhuma: `grep -rni "alcada|alçada"`
só casava a palavra 'calcada' em listas de palavras-chave de cronograma
(services/cronograma_normalizacao.py:69). Qualquer usuário autenticado
com V2 registrava compra de qualquer valor em `compras_views.py:532`.

Os VALORES das faixas são RECOMENDAÇÃO (ver 'Decisões que precisam do
Cássio', D1), semeados pela migration 243 e editáveis por tenant. Estes
testes travam o MECANISMO, não os números: eles criam as próprias faixas
sempre que testam limites, e o único teste que olha o seed está marcado
como tal.
"""
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import (Cliente, EstadoRequisicao, FaixaAlcada, Obra, PapelObra,
                    RequisicaoCompra, TipoUsuario, Usuario, UsuarioObra)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase3-alcada'
    yield


def _admin(nome='Admin'):
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'f3l_{suf}', email=f'f3l_{suf}@test.local',
        nome=f'{nome} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _operador(admin_id, nome='Operador'):
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'f3p_{suf}', email=f'f3p_{suf}@test.local',
        nome=f'{nome} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
        admin_id=admin_id, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id, nome='Obra'):
    suf = uuid.uuid4().hex[:8]
    cliente = Cliente(nome=f'Cliente {suf}', admin_id=admin_id)
    db.session.add(cliente)
    db.session.commit()
    o = Obra(nome=f'{nome} {suf}', codigo=f'O{suf[:6].upper()}',
             data_inicio=date(2026, 1, 1), admin_id=admin_id,
             cliente_id=cliente.id, ativo=True)
    db.session.add(o)
    db.session.commit()
    return o


def _vincular(usuario, obra, papel):
    v = UsuarioObra(usuario_id=usuario.id, obra_id=obra.id, papel=papel,
                    admin_id=obra.admin_id, ativo=True)
    db.session.add(v)
    db.session.commit()
    return v


def _faixas_de_teste(admin_id):
    """Faixas próprias, independentes do seed — o teste trava o mecanismo."""
    FaixaAlcada.query.filter_by(admin_id=admin_id).delete()
    db.session.add(FaixaAlcada(
        admin_id=admin_id, ordem=1, valor_ate=Decimal('100.00'),
        aprovacoes_necessarias=1, exige_admin=False,
        exige_mapa_concorrencia=False, ativo=True))
    db.session.add(FaixaAlcada(
        admin_id=admin_id, ordem=2, valor_ate=Decimal('1000.00'),
        aprovacoes_necessarias=2, exige_admin=True,
        exige_mapa_concorrencia=False, ativo=True))
    db.session.add(FaixaAlcada(
        admin_id=admin_id, ordem=3, valor_ate=None,
        aprovacoes_necessarias=2, exige_admin=True,
        exige_mapa_concorrencia=True, ativo=True))
    db.session.commit()


def _requisicao(admin, obra, solicitante, valor):
    from services.requisicao_compra import proximo_numero
    r = RequisicaoCompra(
        numero=proximo_numero(admin.id), obra_id=obra.id,
        solicitante_id=solicitante.id, admin_id=admin.id,
        valor_estimado=Decimal(valor), justificativa='teste')
    db.session.add(r)
    db.session.commit()
    return r


# ---------------------------------------------------------------------------
# Seleção de faixa
# ---------------------------------------------------------------------------

def test_faixa_e_escolhida_pelo_teto_mais_baixo_que_cobre_o_valor():
    from services.alcada_compras import faixa_para_valor

    with app.app_context():
        admin = _admin()
        _faixas_de_teste(admin.id)
        assert faixa_para_valor(admin.id, Decimal('50.00')).ordem == 1
        assert faixa_para_valor(admin.id, Decimal('100.00')).ordem == 1
        assert faixa_para_valor(admin.id, Decimal('100.01')).ordem == 2
        assert faixa_para_valor(admin.id, Decimal('1000.00')).ordem == 2
        assert faixa_para_valor(admin.id, Decimal('1000.01')).ordem == 3
        assert faixa_para_valor(admin.id, Decimal('999999.00')).ordem == 3


def test_tenant_sem_faixa_cai_na_faixa_de_seguranca():
    """Falha FECHADA: sem configuração, exige o máximo, não o mínimo."""
    from services.alcada_compras import faixa_para_valor

    with app.app_context():
        admin = _admin()
        FaixaAlcada.query.filter_by(admin_id=admin.id).delete()
        db.session.commit()
        faixa = faixa_para_valor(admin.id, Decimal('10.00'))
        assert faixa.aprovacoes_necessarias == 2
        assert faixa.exige_admin is True
        assert faixa.id is None, 'a faixa de segurança não é persistida'


def test_faixa_inativa_e_ignorada():
    from services.alcada_compras import faixa_para_valor

    with app.app_context():
        admin = _admin()
        _faixas_de_teste(admin.id)
        f1 = FaixaAlcada.query.filter_by(admin_id=admin.id, ordem=1).one()
        f1.ativo = False
        db.session.commit()
        assert faixa_para_valor(admin.id, Decimal('50.00')).ordem == 2


# ---------------------------------------------------------------------------
# Separação de funções — o invariante duro da fase
# ---------------------------------------------------------------------------

def test_solicitante_nunca_aprova_a_propria_requisicao():
    from services.alcada_compras import pode_aprovar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _faixas_de_teste(admin.id)
        gestor = _operador(admin.id, 'Gestor')
        _vincular(gestor, obra, PapelObra.GESTOR)
        r = _requisicao(admin, obra, gestor, '50.00')
        r.estado = EstadoRequisicao.AGUARDANDO_APROVACAO
        db.session.commit()

        ok, motivo = pode_aprovar(r, gestor)
        assert ok is False
        assert 'solicitante' in motivo.lower()


def test_admin_tambem_nao_aprova_a_propria_requisicao():
    """Sem exceção para ADMIN. Numa empresa pequena a mesma pessoa acumula
    papéis — é justamente aí que a separação de funções tem que valer."""
    from services.alcada_compras import pode_aprovar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _faixas_de_teste(admin.id)
        r = _requisicao(admin, obra, admin, '50.00')
        r.estado = EstadoRequisicao.AGUARDANDO_APROVACAO
        db.session.commit()

        ok, motivo = pode_aprovar(r, admin)
        assert ok is False
        assert 'solicitante' in motivo.lower()


def test_ninguem_aprova_duas_vezes_a_mesma_requisicao():
    from services.alcada_compras import pode_aprovar, registrar_aprovacao

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _faixas_de_teste(admin.id)
        gestor = _operador(admin.id, 'Gestor')
        solicitante = _operador(admin.id, 'Solicitante')
        _vincular(gestor, obra, PapelObra.GESTOR)
        r = _requisicao(admin, obra, solicitante, '500.00')  # faixa 2: 2 aprovações
        r.estado = EstadoRequisicao.AGUARDANDO_APROVACAO
        db.session.commit()

        registrar_aprovacao(r, gestor, papel='GESTOR')
        db.session.commit()

        ok, motivo = pode_aprovar(r, gestor)
        assert ok is False
        assert 'já aprovou' in motivo.lower()


# ---------------------------------------------------------------------------
# Contagem de aprovações
# ---------------------------------------------------------------------------

def test_uma_aprovacao_basta_na_faixa_baixa():
    from services.alcada_compras import (aprovacoes_registradas,
                                         esta_totalmente_aprovada,
                                         registrar_aprovacao)

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _faixas_de_teste(admin.id)
        gestor = _operador(admin.id, 'Gestor')
        solicitante = _operador(admin.id, 'Solicitante')
        _vincular(gestor, obra, PapelObra.GESTOR)
        r = _requisicao(admin, obra, solicitante, '50.00')
        r.estado = EstadoRequisicao.AGUARDANDO_APROVACAO
        db.session.commit()

        assert esta_totalmente_aprovada(r) is False
        registrar_aprovacao(r, gestor, papel='GESTOR')
        db.session.commit()
        assert aprovacoes_registradas(r) == 1
        assert esta_totalmente_aprovada(r) is True


def test_faixa_alta_exige_duas_aprovacoes_sendo_uma_do_admin():
    from services.alcada_compras import (esta_totalmente_aprovada,
                                         registrar_aprovacao)

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _faixas_de_teste(admin.id)
        gestor = _operador(admin.id, 'Gestor')
        outro = _operador(admin.id, 'Outro')
        solicitante = _operador(admin.id, 'Solicitante')
        _vincular(gestor, obra, PapelObra.GESTOR)
        _vincular(outro, obra, PapelObra.GESTOR)
        r = _requisicao(admin, obra, solicitante, '500.00')
        r.estado = EstadoRequisicao.AGUARDANDO_APROVACAO
        db.session.commit()

        registrar_aprovacao(r, gestor, papel='GESTOR')
        registrar_aprovacao(r, outro, papel='GESTOR')
        db.session.commit()
        # duas aprovações, mas NENHUMA de ADMIN — a faixa exige_admin=True
        assert esta_totalmente_aprovada(r) is False

        registrar_aprovacao(r, admin, papel='ADMIN')
        db.session.commit()
        assert esta_totalmente_aprovada(r) is True


def test_faixa_de_topo_exige_mapa_concluido():
    from models import MapaConcorrenciaV2, MapaFornecedor
    from services.alcada_compras import (esta_totalmente_aprovada,
                                         registrar_aprovacao,
                                         pendencias_de_aprovacao)

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _faixas_de_teste(admin.id)
        gestor = _operador(admin.id, 'Gestor')
        solicitante = _operador(admin.id, 'Solicitante')
        _vincular(gestor, obra, PapelObra.GESTOR)
        r = _requisicao(admin, obra, solicitante, '5000.00')  # faixa 3
        r.estado = EstadoRequisicao.AGUARDANDO_APROVACAO
        db.session.commit()

        registrar_aprovacao(r, gestor, papel='GESTOR')
        registrar_aprovacao(r, admin, papel='ADMIN')
        db.session.commit()
        assert esta_totalmente_aprovada(r) is False
        assert any('mapa' in p.lower() for p in pendencias_de_aprovacao(r))

        mapa = MapaConcorrenciaV2(obra_id=obra.id, admin_id=admin.id,
                                  nome='Perfis', status='concluido')
        db.session.add(mapa)
        db.session.flush()
        db.session.add(MapaFornecedor(mapa_id=mapa.id, admin_id=admin.id,
                                      nome='Forn A', ordem=0))
        db.session.add(MapaFornecedor(mapa_id=mapa.id, admin_id=admin.id,
                                      nome='Forn B', ordem=1))
        r.mapa_v2_id = mapa.id
        db.session.commit()
        assert esta_totalmente_aprovada(r) is True


def test_mapa_com_um_fornecedor_so_nao_conta_como_concorrencia():
    from models import MapaConcorrenciaV2, MapaFornecedor
    from services.alcada_compras import (esta_totalmente_aprovada,
                                         registrar_aprovacao)

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _faixas_de_teste(admin.id)
        gestor = _operador(admin.id, 'Gestor')
        solicitante = _operador(admin.id, 'Solicitante')
        _vincular(gestor, obra, PapelObra.GESTOR)
        r = _requisicao(admin, obra, solicitante, '5000.00')
        r.estado = EstadoRequisicao.AGUARDANDO_APROVACAO
        mapa = MapaConcorrenciaV2(obra_id=obra.id, admin_id=admin.id,
                                  nome='Unico', status='concluido')
        db.session.add(mapa)
        db.session.flush()
        db.session.add(MapaFornecedor(mapa_id=mapa.id, admin_id=admin.id,
                                      nome='Forn A', ordem=0))
        r.mapa_v2_id = mapa.id
        db.session.commit()

        registrar_aprovacao(r, gestor, papel='GESTOR')
        registrar_aprovacao(r, admin, papel='ADMIN')
        db.session.commit()
        assert esta_totalmente_aprovada(r) is False


# ---------------------------------------------------------------------------
# Seed recomendado (D1) — trava os NÚMEROS da recomendação adotada
# ---------------------------------------------------------------------------

def test_seed_recomendado_cria_tres_faixas_para_tenant_novo():
    """Estes números são a RECOMENDAÇÃO do plano (D1), não uma regra do
    Cássio. Se ele definir outros, ajuste aqui E na migration 243."""
    from services.alcada_compras import garantir_faixas_do_tenant

    with app.app_context():
        admin = _admin()
        FaixaAlcada.query.filter_by(admin_id=admin.id).delete()
        db.session.commit()
        garantir_faixas_do_tenant(admin.id)
        db.session.commit()

        faixas = (FaixaAlcada.query.filter_by(admin_id=admin.id)
                  .order_by(FaixaAlcada.ordem).all())
        assert [f.valor_ate for f in faixas] == [
            Decimal('5000.00'), Decimal('30000.00'), None]
        assert [f.aprovacoes_necessarias for f in faixas] == [1, 2, 2]
        assert [f.exige_admin for f in faixas] == [False, True, True]
        assert [f.exige_mapa_concorrencia for f in faixas] == [False, False, True]


def test_garantir_faixas_e_idempotente():
    from services.alcada_compras import garantir_faixas_do_tenant

    with app.app_context():
        admin = _admin()
        garantir_faixas_do_tenant(admin.id)
        db.session.commit()
        garantir_faixas_do_tenant(admin.id)
        db.session.commit()
        assert FaixaAlcada.query.filter_by(admin_id=admin.id).count() == 3
