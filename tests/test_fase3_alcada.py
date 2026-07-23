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


# ---------------------------------------------------------------------------
# PapelObra.COMPRADOR
# ---------------------------------------------------------------------------

def test_papel_obra_ganhou_comprador():
    """A Fase 1 parou em GESTOR/APONTADOR/LEITOR de propósito. O COMPRADOR
    só entra quando existem verbos: criar requisição e emitir pedido."""
    assert {p.name for p in PapelObra} == {
        'GESTOR', 'APONTADOR', 'LEITOR', 'COMPRADOR'}


def test_comprador_persiste_no_vinculo():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        op = _operador(admin.id)
        v = _vincular(op, obra, PapelObra.COMPRADOR)
        vid = v.id

    with app.app_context():
        recarregado = db.session.get(UsuarioObra, vid)
        assert recarregado.papel == PapelObra.COMPRADOR


def test_comprador_requisita_mas_nao_edita_a_obra():
    """COMPRADOR não é GESTOR de bolso: ele pede e emite, não manda na obra."""
    from utils.autorizacao import (PAPEIS_QUE_COMPRAM, PAPEIS_QUE_EDITAM_OBRA,
                                   PAPEIS_QUE_REQUISITAM)

    assert PapelObra.COMPRADOR in PAPEIS_QUE_REQUISITAM
    assert PapelObra.COMPRADOR in PAPEIS_QUE_COMPRAM
    assert PapelObra.COMPRADOR not in PAPEIS_QUE_EDITAM_OBRA


def test_gestor_requisita_mas_nao_emite_pedido():
    """Separação de funções no nível do papel: quem aprova não emite."""
    from utils.autorizacao import PAPEIS_QUE_COMPRAM, PAPEIS_QUE_REQUISITAM

    assert PapelObra.GESTOR in PAPEIS_QUE_REQUISITAM
    assert PapelObra.GESTOR not in PAPEIS_QUE_COMPRAM


def test_apontador_e_leitor_nao_requisitam():
    from utils.autorizacao import PAPEIS_QUE_REQUISITAM

    assert PapelObra.APONTADOR not in PAPEIS_QUE_REQUISITAM
    assert PapelObra.LEITOR not in PAPEIS_QUE_REQUISITAM


def test_predicados_de_obra_respondem_pelo_vinculo():
    from scripts.flag_escopo_obra import definir_flag
    from utils.autorizacao import pode_comprar_na_obra, pode_requisitar_na_obra

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        comprador = _operador(admin.id, 'Comprador')
        leitor = _operador(admin.id, 'Leitor')
        _vincular(comprador, obra, PapelObra.COMPRADOR)
        _vincular(leitor, obra, PapelObra.LEITOR)
        # O eixo de obra só estreita acesso com a flag ligada; sem ela,
        # papel_na_obra devolve GESTOR a todo autenticado (comportamento
        # pré-Fase 1) e o vínculo não distingue ninguém. É o escopo ligado
        # que faz o predicado "responder pelo vínculo".
        definir_flag(admin.id, True)
        db.session.commit()
        oid, cid, lid = obra.id, comprador.id, leitor.id

    cliente = app.test_client()
    with cliente.session_transaction() as sess:
        sess['_user_id'] = str(cid)
        sess['_fresh'] = True
    with app.test_request_context():
        from flask_login import login_user
        with app.app_context():
            login_user(db.session.get(Usuario, cid))
            assert pode_requisitar_na_obra(oid) is True
            assert pode_comprar_na_obra(oid) is True

    with app.test_request_context():
        from flask_login import login_user
        with app.app_context():
            login_user(db.session.get(Usuario, lid))
            assert pode_requisitar_na_obra(oid) is False
            assert pode_comprar_na_obra(oid) is False


# ---------------------------------------------------------------------------
# Rotas de aprovação
# ---------------------------------------------------------------------------

def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


def _cenario(valor, papel_do_aprovador=PapelObra.GESTOR):
    """admin + obra + solicitante + aprovador vinculado, requisição já
    aguardando aprovação. Devolve os ids (fora de app_context aberto).

    Liga escopo_obra_ativo: sem a flag, papel_na_obra devolve GESTOR a
    todo autenticado (comportamento pré-Fase 1) e LEITOR/COMPRADOR
    aprovariam — que é justamente o que estes testes negam. É o eixo de
    obra ligado que faz o papel valer.
    """
    from scripts.flag_escopo_obra import definir_flag
    from services.requisicao_compra import proximo_numero

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _faixas_de_teste(admin.id)
        solicitante = _operador(admin.id, 'Solicitante')
        aprovador = _operador(admin.id, 'Aprovador')
        _vincular(solicitante, obra, PapelObra.COMPRADOR)
        _vincular(aprovador, obra, papel_do_aprovador)
        definir_flag(admin.id, True)
        req = RequisicaoCompra(
            numero=proximo_numero(admin.id), obra_id=obra.id,
            solicitante_id=solicitante.id, admin_id=admin.id,
            estado=EstadoRequisicao.AGUARDANDO_APROVACAO,
            valor_estimado=Decimal(valor))
        db.session.add(req)
        db.session.commit()
        return {'admin': admin.id, 'obra': obra.id,
                'solicitante': solicitante.id, 'aprovador': aprovador.id,
                'req': req.id}


def test_aprovacao_unica_leva_para_aprovada():
    c = _cenario('50.00')  # faixa 1: 1 aprovação, sem admin
    r = _cliente_de(c['aprovador']).post(
        f"/compras/requisicoes/{c['req']}/aprovar", follow_redirects=False)
    assert r.status_code == 302
    with app.app_context():
        req = db.session.get(RequisicaoCompra, c['req'])
        assert req.estado == EstadoRequisicao.APROVADA


def test_primeira_de_duas_aprovacoes_nao_muda_o_estado():
    c = _cenario('500.00')  # faixa 2: 2 aprovações + admin
    _cliente_de(c['aprovador']).post(
        f"/compras/requisicoes/{c['req']}/aprovar", follow_redirects=False)
    with app.app_context():
        req = db.session.get(RequisicaoCompra, c['req'])
        assert req.estado == EstadoRequisicao.AGUARDANDO_APROVACAO


def test_segunda_aprovacao_do_admin_fecha_a_alcada():
    from services.alcada_compras import aprovacoes_registradas

    c = _cenario('500.00')
    _cliente_de(c['aprovador']).post(
        f"/compras/requisicoes/{c['req']}/aprovar", follow_redirects=False)
    _cliente_de(c['admin']).post(
        f"/compras/requisicoes/{c['req']}/aprovar", follow_redirects=False)
    with app.app_context():
        req = db.session.get(RequisicaoCompra, c['req'])
        assert aprovacoes_registradas(req) == 2
        assert req.estado == EstadoRequisicao.APROVADA


def test_solicitante_nao_aprova_pela_rota():
    c = _cenario('50.00')
    _cliente_de(c['solicitante']).post(
        f"/compras/requisicoes/{c['req']}/aprovar", follow_redirects=False)
    with app.app_context():
        req = db.session.get(RequisicaoCompra, c['req'])
        assert req.estado == EstadoRequisicao.AGUARDANDO_APROVACAO


def test_leitor_da_obra_nao_aprova():
    c = _cenario('50.00', papel_do_aprovador=PapelObra.LEITOR)
    _cliente_de(c['aprovador']).post(
        f"/compras/requisicoes/{c['req']}/aprovar", follow_redirects=False)
    with app.app_context():
        req = db.session.get(RequisicaoCompra, c['req'])
        assert req.estado == EstadoRequisicao.AGUARDANDO_APROVACAO


def test_comprador_nao_aprova():
    """COMPRADOR pede e emite; não aprova. É a separação de funções."""
    c = _cenario('50.00', papel_do_aprovador=PapelObra.COMPRADOR)
    _cliente_de(c['aprovador']).post(
        f"/compras/requisicoes/{c['req']}/aprovar", follow_redirects=False)
    with app.app_context():
        req = db.session.get(RequisicaoCompra, c['req'])
        assert req.estado == EstadoRequisicao.AGUARDANDO_APROVACAO


def test_aprovador_de_outro_tenant_recebe_404():
    c = _cenario('50.00')
    with app.app_context():
        estranho = _admin('Estranho')
        eid = estranho.id
    r = _cliente_de(eid).post(
        f"/compras/requisicoes/{c['req']}/aprovar", follow_redirects=False)
    assert r.status_code == 404


def test_rejeicao_exige_motivo_e_grava_trilha():
    from models import RequisicaoTransicao

    c = _cenario('50.00')
    sem_motivo = _cliente_de(c['aprovador']).post(
        f"/compras/requisicoes/{c['req']}/rejeitar", data={'motivo': ''},
        follow_redirects=False)
    assert sem_motivo.status_code == 302
    with app.app_context():
        assert db.session.get(RequisicaoCompra, c['req']).estado == \
            EstadoRequisicao.AGUARDANDO_APROVACAO

    _cliente_de(c['aprovador']).post(
        f"/compras/requisicoes/{c['req']}/rejeitar",
        data={'motivo': 'sem verba neste mês'}, follow_redirects=False)
    with app.app_context():
        req = db.session.get(RequisicaoCompra, c['req'])
        assert req.estado == EstadoRequisicao.REJEITADA
        t = (RequisicaoTransicao.query
             .filter_by(requisicao_id=req.id,
                        para_estado=EstadoRequisicao.REJEITADA).one())
        assert 'sem verba' in t.motivo
        assert t.valor_no_momento == Decimal('50.00')


def test_valor_gravado_e_o_do_momento_da_aprovacao():
    """Editar a requisição depois não pode reescrever o histórico da alçada."""
    from services.alcada_compras import votos_de_aprovacao

    c = _cenario('50.00')
    _cliente_de(c['aprovador']).post(
        f"/compras/requisicoes/{c['req']}/aprovar", follow_redirects=False)
    with app.app_context():
        req = db.session.get(RequisicaoCompra, c['req'])
        req.valor_estimado = Decimal('99999.00')
        db.session.commit()
        voto = votos_de_aprovacao(req)[0]
        assert voto.valor_no_momento == Decimal('50.00')


# ---------------------------------------------------------------------------
# Emissão do pedido
# ---------------------------------------------------------------------------

def _cenario_aprovado(valor='50.00'):
    """Requisição com item, já APROVADA, e um COMPRADOR vinculado."""
    from scripts.flag_escopo_obra import definir_flag
    from models import Fornecedor, RequisicaoCompraItem
    from services.alcada_compras import registrar_aprovacao
    from services.requisicao_compra import (proximo_numero, recalcular_valor,
                                            transicionar)

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _faixas_de_teste(admin.id)
        solicitante = _operador(admin.id, 'Solicitante')
        gestor = _operador(admin.id, 'Gestor')
        comprador = _operador(admin.id, 'Comprador')
        _vincular(solicitante, obra, PapelObra.COMPRADOR)
        _vincular(gestor, obra, PapelObra.GESTOR)
        _vincular(comprador, obra, PapelObra.COMPRADOR)
        definir_flag(admin.id, True)

        forn = Fornecedor(nome='Forn Teste', cnpj=f'{uuid.uuid4().hex[:14]}',
                          admin_id=admin.id, ativo=True)
        db.session.add(forn)

        req = RequisicaoCompra(
            numero=proximo_numero(admin.id), obra_id=obra.id,
            solicitante_id=solicitante.id, admin_id=admin.id,
            estado=EstadoRequisicao.AGUARDANDO_APROVACAO)
        db.session.add(req)
        db.session.flush()
        db.session.add(RequisicaoCompraItem(
            requisicao_id=req.id, admin_id=admin.id, descricao='Perfil U90',
            unidade='m', quantidade=Decimal('10.000'),
            preco_estimado=Decimal(valor) / Decimal('10')))
        db.session.flush()
        recalcular_valor(req)
        registrar_aprovacao(req, gestor, papel='GESTOR')
        registrar_aprovacao(req, admin, papel='ADMIN')
        transicionar(req, EstadoRequisicao.APROVADA, gestor, motivo='ok')
        db.session.commit()
        return {'admin': admin.id, 'obra': obra.id, 'req': req.id,
                'comprador': comprador.id, 'gestor': gestor.id,
                'solicitante': solicitante.id, 'fornecedor': forn.id}


def test_emitir_pedido_cria_pedido_vinculado_com_obra():
    from models import PedidoCompra

    c = _cenario_aprovado()
    r = _cliente_de(c['comprador']).post(
        f"/compras/requisicoes/{c['req']}/emitir-pedido",
        data={'fornecedor_id': str(c['fornecedor']),
              'data_compra': '2026-08-01',
              'condicao_pagamento': 'a_vista', 'parcelas': '1'},
        follow_redirects=False)
    assert r.status_code == 302

    with app.app_context():
        pedido = PedidoCompra.query.filter_by(requisicao_id=c['req']).one()
        assert pedido.obra_id == c['obra'], 'pedido emitido sem obra'
        assert pedido.admin_id == c['admin']
        assert pedido.itens.count() == 1
        req = db.session.get(RequisicaoCompra, c['req'])
        assert req.estado == EstadoRequisicao.CONVERTIDA


def test_requisicao_nao_aprovada_nao_vira_pedido():
    from models import PedidoCompra

    c = _cenario('50.00')  # AGUARDANDO_APROVACAO
    with app.app_context():
        comprador = _operador(c['admin'], 'Comprador')
        obra = db.session.get(Obra, c['obra'])
        _vincular(comprador, obra, PapelObra.COMPRADOR)
        cid = comprador.id
        forn_id = None
        from models import Fornecedor
        f = Fornecedor(nome='F', cnpj=uuid.uuid4().hex[:14],
                       admin_id=c['admin'], ativo=True)
        db.session.add(f)
        db.session.commit()
        forn_id = f.id

    _cliente_de(cid).post(
        f"/compras/requisicoes/{c['req']}/emitir-pedido",
        data={'fornecedor_id': str(forn_id), 'data_compra': '2026-08-01'},
        follow_redirects=False)
    with app.app_context():
        assert PedidoCompra.query.filter_by(requisicao_id=c['req']).count() == 0


def test_gestor_que_aprovou_nao_emite_o_pedido():
    """Separação de funções: quem aprova não emite, quando a faixa exigiu
    mais de uma aprovação."""
    from models import PedidoCompra

    c = _cenario_aprovado()
    _cliente_de(c['gestor']).post(
        f"/compras/requisicoes/{c['req']}/emitir-pedido",
        data={'fornecedor_id': str(c['fornecedor']),
              'data_compra': '2026-08-01'},
        follow_redirects=False)
    with app.app_context():
        assert PedidoCompra.query.filter_by(requisicao_id=c['req']).count() == 0


def test_nao_se_emite_duas_vezes_a_mesma_requisicao():
    from models import PedidoCompra

    c = _cenario_aprovado()
    dados = {'fornecedor_id': str(c['fornecedor']),
             'data_compra': '2026-08-01', 'condicao_pagamento': 'a_vista'}
    cliente = _cliente_de(c['comprador'])
    cliente.post(f"/compras/requisicoes/{c['req']}/emitir-pedido", data=dados)
    cliente.post(f"/compras/requisicoes/{c['req']}/emitir-pedido", data=dados)
    with app.app_context():
        assert PedidoCompra.query.filter_by(requisicao_id=c['req']).count() == 1


def test_pedido_acima_do_valor_aprovado_e_recusado():
    """A alçada aprovou R$ 50; emitir R$ 5.000 seria burlar a faixa."""
    from models import PedidoCompra

    c = _cenario_aprovado()
    _cliente_de(c['comprador']).post(
        f"/compras/requisicoes/{c['req']}/emitir-pedido",
        data={'fornecedor_id': str(c['fornecedor']),
              'data_compra': '2026-08-01',
              'item_preco_real[]': ['500.00']},  # 10 x 500 = 5000
        follow_redirects=False)
    with app.app_context():
        assert PedidoCompra.query.filter_by(requisicao_id=c['req']).count() == 0


def test_emissao_gera_custo_na_obra():
    """O pedido emitido continua fazendo o que compras_views.py:162 sempre
    fez: GestaoCustoPai + GestaoCustoFilho na obra."""
    from models import GestaoCustoFilho, PedidoCompra

    c = _cenario_aprovado()
    _cliente_de(c['comprador']).post(
        f"/compras/requisicoes/{c['req']}/emitir-pedido",
        data={'fornecedor_id': str(c['fornecedor']),
              'data_compra': '2026-08-01', 'condicao_pagamento': 'a_vista'},
        follow_redirects=False)
    with app.app_context():
        pedido = PedidoCompra.query.filter_by(requisicao_id=c['req']).one()
        filhos = GestaoCustoFilho.query.filter_by(
            origem_tabela='pedido_compra', origem_id=pedido.id).all()
        assert filhos, 'emissão não gerou custo'
        assert all(f.obra_id == c['obra'] for f in filhos)


# ---------------------------------------------------------------------------
# Guard de governança no registro direto de compra
# ---------------------------------------------------------------------------

def _post_compra_direta(cliente, obra_id, fornecedor_id):
    return cliente.post('/compras/nova', data={
        'fornecedor_id': str(fornecedor_id),
        'data_compra': '2026-08-01',
        'condicao_pagamento': 'a_vista',
        'parcelas': '1',
        'obra_id': str(obra_id),
        'tipo_compra': 'normal',
        'item_descricao[]': ['Perfil U90'],
        'item_quantidade[]': ['10'],
        'item_preco[]': ['18,50'],
        'item_almoxarifado_id[]': [''],
    }, follow_redirects=False)


def _admin_obra_fornecedor():
    from models import Fornecedor
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        forn = Fornecedor(nome='Forn', cnpj=uuid.uuid4().hex[:14],
                          admin_id=admin.id, ativo=True)
        db.session.add(forn)
        db.session.commit()
        return admin.id, obra.id, forn.id


def test_com_flag_desligada_o_fluxo_antigo_continua_funcionando():
    """Nenhuma empresa pode acordar sem conseguir registrar compra."""
    from models import PedidoCompra

    aid, oid, fid = _admin_obra_fornecedor()
    r = _post_compra_direta(_cliente_de(aid), oid, fid)
    assert r.status_code == 302
    with app.app_context():
        assert PedidoCompra.query.filter_by(admin_id=aid).count() == 1


def test_com_flag_ligada_pedido_sem_requisicao_e_recusado():
    from models import PedidoCompra
    from scripts.flag_compras_governanca import definir_flag

    aid, oid, fid = _admin_obra_fornecedor()
    with app.app_context():
        definir_flag(aid, True)

    r = _post_compra_direta(_cliente_de(aid), oid, fid)
    assert r.status_code == 302
    with app.app_context():
        assert PedidoCompra.query.filter_by(admin_id=aid).count() == 0, (
            'pedido nasceu sem requisição aprovada com a governança ligada')


def test_com_flag_ligada_a_emissao_pela_requisicao_continua_funcionando():
    """A governança fecha o atalho, não o caminho."""
    from models import PedidoCompra
    from scripts.flag_compras_governanca import definir_flag

    c = _cenario_aprovado()
    with app.app_context():
        definir_flag(c['admin'], True)

    _cliente_de(c['comprador']).post(
        f"/compras/requisicoes/{c['req']}/emitir-pedido",
        data={'fornecedor_id': str(c['fornecedor']),
              'data_compra': '2026-08-01', 'condicao_pagamento': 'a_vista'},
        follow_redirects=False)
    with app.app_context():
        assert PedidoCompra.query.filter_by(requisicao_id=c['req']).count() == 1


# ---------------------------------------------------------------------------
# Correções pós-revisão de código
# ---------------------------------------------------------------------------

def test_votos_de_rodada_anterior_nao_contam_apos_reenvio():
    """Achado #2: rejeitar e reenviar abre rodada nova; o voto da rodada
    anterior não pode fechar a alçada da requisição reenviada."""
    from services.alcada_compras import (aprovacoes_registradas,
                                         esta_totalmente_aprovada,
                                         registrar_aprovacao)
    from services.requisicao_compra import transicionar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _faixas_de_teste(admin.id)
        gestor = _operador(admin.id, 'Gestor')
        solicitante = _operador(admin.id, 'Solicitante')
        _vincular(gestor, obra, PapelObra.GESTOR)
        r = _requisicao(admin, obra, solicitante, '500.00')  # faixa 2: 2 + admin

        transicionar(r, EstadoRequisicao.AGUARDANDO_APROVACAO, solicitante)
        registrar_aprovacao(r, gestor, papel='GESTOR')  # voto da rodada 1
        db.session.commit()
        assert aprovacoes_registradas(r) == 1

        # rejeita e reenvia
        transicionar(r, EstadoRequisicao.REJEITADA, admin, motivo='faltou cotação')
        transicionar(r, EstadoRequisicao.RASCUNHO, solicitante, motivo='corrigido')
        transicionar(r, EstadoRequisicao.AGUARDANDO_APROVACAO, solicitante)
        db.session.commit()

        # rodada nova: o voto do gestor da rodada 1 NÃO conta
        assert aprovacoes_registradas(r) == 0
        assert esta_totalmente_aprovada(r) is False


def test_itens_da_requisicao_vem_ordenados_por_id():
    """Achado #3: a emissão casa item↔preço por ORDEM; o relationship precisa
    devolver os itens sempre na mesma ordem determinística."""
    from models import RequisicaoCompraItem

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        r = _requisicao(admin, obra, admin, '0')
        for d in ['A', 'B', 'C', 'D']:
            db.session.add(RequisicaoCompraItem(
                requisicao_id=r.id, admin_id=admin.id, descricao=d,
                quantidade=Decimal('1'), preco_estimado=Decimal('1')))
        db.session.commit()
        ids = [i.id for i in r.itens.all()]
        assert ids == sorted(ids), 'itens fora de ordem de id'


def test_quantidade_nao_numerica_nao_derruba_o_form():
    """Achado #5: entrada não-numérica não pode virar HTTP 500."""
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        aid, oid = admin.id, obra.id

    r = _cliente_de(aid).post('/compras/requisicoes/nova', data={
        'obra_id': str(oid), 'justificativa': 'entrada suja',
        'item_descricao[]': ['Item'], 'item_unidade[]': ['un'],
        'item_quantidade[]': ['abc'], 'item_preco[]': ['xyz'],
        'item_almoxarifado_id[]': [''],
    }, follow_redirects=False)
    assert r.status_code == 302, f'esperava 302, veio {r.status_code}'
    with app.app_context():
        assert RequisicaoCompra.query.filter_by(admin_id=aid).count() == 1
