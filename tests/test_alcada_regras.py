"""Alçadas avançadas — as quatro condições, fracionamento e emergência.

Spec: docs/superpowers/specs/2026-08-16-alcadas-avancadas-design.md
Plano: docs/superpowers/plans/2026-08-16-plano-execucao-alcadas-avancadas.md

Molde de tests/test_recebimento_atesto.py: fixtures locais, tenant por uuid4,
sem depender de seed.
"""
import os
import sys
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import (Cliente, EstadoRequisicao, FaixaAlcada, Obra,
                    RequisicaoCompra, TipoUsuario, Usuario)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-alcada-regras'
    yield


def _admin():
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'alc_{suf}', email=f'alc_{suf}@test.local', nome=f'Adm {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id):
    suf = uuid.uuid4().hex[:8]
    cliente = Cliente(nome=f'Cliente {suf}', admin_id=admin_id)
    db.session.add(cliente)
    db.session.commit()
    o = Obra(nome=f'Obra {suf}', codigo=f'A{suf[:6].upper()}',
             data_inicio=date(2026, 1, 1), admin_id=admin_id,
             cliente_id=cliente.id, ativo=True)
    db.session.add(o)
    db.session.commit()
    return o


def _sc(admin_id, obra_id, valor, estado=EstadoRequisicao.AGUARDANDO_APROVACAO,
        osc_id=None, dias_atras=0, urgencia='normal', solicitante_id=None):
    """Requisição crua, sem passar pelo serviço — o objetivo é montar cenário."""
    suf = uuid.uuid4().hex[:6].upper()
    r = RequisicaoCompra(
        numero=f'RC-{suf}', admin_id=admin_id, obra_id=obra_id,
        obra_servico_custo_id=osc_id, solicitante_id=solicitante_id or admin_id,
        estado=estado, valor_estimado=Decimal(str(valor)), urgencia=urgencia,
        created_at=datetime.utcnow() - timedelta(days=dias_atras))
    db.session.add(r)
    db.session.commit()
    return r


def test_colunas_da_migracao_287_existem_com_o_default_do_legado():
    """SC nasce 'normal', sem carimbo e sem emergência; faixa nasce pedindo 2."""
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        sc = _sc(admin.id, obra.id, 1000)
        assert sc.urgencia == 'normal'
        assert sc.justificativa_urgencia is None
        assert sc.faixa_exigida_id is None
        assert sc.alcada_degraus == 0
        assert sc.alcada_motivos is None
        assert sc.alcada_carimbada_em is None
        assert sc.emergencia_ativada_em is None

        faixa = FaixaAlcada(admin_id=admin.id, ordem=1,
                            valor_ate=Decimal('5000.00'),
                            aprovacoes_necessarias=1)
        db.session.add(faixa)
        db.session.commit()
        assert faixa.fornecedores_minimos == 2


# ═══════════════════════════════════════════════════════════════════════
# Anti-fracionamento: a soma da janela
# ═══════════════════════════════════════════════════════════════════════

def test_soma_do_fracionamento_junta_a_mesma_obra_e_etapa_na_janela():
    from services.alcada_regras import soma_da_janela
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _sc(admin.id, obra.id, 4000, dias_atras=5)
        _sc(admin.id, obra.id, 3000, dias_atras=29)
        alvo = _sc(admin.id, obra.id, 2000)
        soma, somadas = soma_da_janela(alvo)
        assert soma == Decimal('7000.00')
        assert len(somadas) == 2


def test_soma_ignora_a_propria_sc():
    """No carimbo a SC já está em AGUARDANDO — sem a exclusão ela se somaria
    a si mesma e todo valor contaria em dobro."""
    from services.alcada_regras import soma_da_janela
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        alvo = _sc(admin.id, obra.id, 2000)
        soma, somadas = soma_da_janela(alvo)
        assert soma == Decimal('0')
        assert somadas == []


def test_soma_respeita_a_borda_de_30_dias():
    from services.alcada_regras import soma_da_janela
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _sc(admin.id, obra.id, 1000, dias_atras=29)   # dentro
        _sc(admin.id, obra.id, 9000, dias_atras=31)   # fora
        alvo = _sc(admin.id, obra.id, 500)
        soma, _ = soma_da_janela(alvo)
        assert soma == Decimal('1000.00')


@pytest.mark.parametrize('estado,conta', [
    (EstadoRequisicao.AGUARDANDO_APROVACAO, True),
    (EstadoRequisicao.APROVADA, True),
    (EstadoRequisicao.CONVERTIDA, True),
    (EstadoRequisicao.RASCUNHO, False),
    (EstadoRequisicao.REJEITADA, False),
    (EstadoRequisicao.CANCELADA, False),
])
def test_soma_conta_so_o_que_e_compromisso(estado, conta):
    from services.alcada_regras import soma_da_janela
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        _sc(admin.id, obra.id, 1000, estado=estado, dias_atras=2)
        alvo = _sc(admin.id, obra.id, 500)
        soma, _ = soma_da_janela(alvo)
        assert soma == (Decimal('1000.00') if conta else Decimal('0'))


def test_soma_nao_mistura_etapas_nem_obras_nem_tenants():
    from services.alcada_regras import soma_da_janela
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        outra = _obra(admin.id)
        alheio = _admin()
        obra_alheia = _obra(alheio.id)
        _sc(admin.id, outra.id, 8000, dias_atras=1)          # outra obra
        _sc(alheio.id, obra_alheia.id, 8000, dias_atras=1)   # outro tenant
        _sc(admin.id, obra.id, 8000, dias_atras=1)           # balde da obra
        alvo = _sc(admin.id, obra.id, 500)
        soma, _ = soma_da_janela(alvo)
        assert soma == Decimal('8000.00')


# ═══════════════════════════════════════════════════════════════════════
# As quatro condições, os degraus e o teto
# ═══════════════════════════════════════════════════════════════════════

def _faixas(admin_id):
    """As três faixas recomendadas, com o piso de cotações da fase nova."""
    for ordem, ate, aprov, adm, mapa, forn in [
            (1, Decimal('5000.00'), 1, False, False, 2),
            (2, Decimal('30000.00'), 2, True, False, 2),
            (3, None, 2, True, True, 3)]:
        db.session.add(FaixaAlcada(
            admin_id=admin_id, ordem=ordem, valor_ate=ate,
            aprovacoes_necessarias=aprov, exige_admin=adm,
            exige_mapa_concorrencia=mapa, fornecedores_minimos=forn,
            ativo=True))
    db.session.commit()


def test_sem_concorrencia_sobe_um_degrau():
    from services.alcada_regras import avaliar_alcada
    with app.app_context():
        admin = _admin()
        _faixas(admin.id)
        obra = _obra(admin.id)
        sc = _sc(admin.id, obra.id, 1000)          # faixa 1 pelo valor
        av = avaliar_alcada(sc)
        assert [c['codigo'] for c in av.condicoes] == ['sem_concorrencia']
        assert av.degraus == 1
        assert av.faixa_final.ordem == 2


def test_urgente_soma_com_sem_concorrencia_e_sobe_dois():
    from services.alcada_regras import avaliar_alcada
    with app.app_context():
        admin = _admin()
        _faixas(admin.id)
        obra = _obra(admin.id)
        sc = _sc(admin.id, obra.id, 1000, urgencia='urgente')
        av = avaliar_alcada(sc)
        assert sorted(c['codigo'] for c in av.condicoes) == \
            ['sem_concorrencia', 'urgente']
        assert av.degraus == 2
        assert av.faixa_final.ordem == 3


def test_degraus_nao_passam_da_faixa_mais_alta():
    """Teto: dois degraus a partir da faixa 2 não apontam para faixa 4."""
    from services.alcada_regras import avaliar_alcada
    with app.app_context():
        admin = _admin()
        _faixas(admin.id)
        obra = _obra(admin.id)
        sc = _sc(admin.id, obra.id, 10000, urgencia='urgente')   # faixa 2
        av = avaliar_alcada(sc)
        assert av.degraus == 2
        assert av.faixa_final.ordem == 3
        assert av.faixa_final.valor_ate is None


def test_fracionamento_leva_a_faixa_da_soma():
    """R$ 4 mil que fecham R$ 32 mil no mês são julgados pela faixa de 30 mil+."""
    from services.alcada_regras import avaliar_alcada
    with app.app_context():
        admin = _admin()
        _faixas(admin.id)
        obra = _obra(admin.id)
        _sc(admin.id, obra.id, 28000, dias_atras=3)
        sc = _sc(admin.id, obra.id, 4000)
        av = avaliar_alcada(sc)
        assert av.valor_efetivo == Decimal('32000.00')
        assert av.faixa_base.ordem == 3
        assert len(av.somadas) == 1


def test_tenant_sem_faixa_continua_na_faixa_de_seguranca():
    """Falha fechada: nenhuma condição pode afrouxar o tenant sem configuração."""
    from services.alcada_regras import avaliar_alcada
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        sc = _sc(admin.id, obra.id, 1000)
        av = avaliar_alcada(sc)
        assert av.faixa_final.aprovacoes_necessarias == 2
        assert av.faixa_final.exige_admin is True


# ═══════════════════════════════════════════════════════════════════════
# O carimbo
# ═══════════════════════════════════════════════════════════════════════

def _enviar(sc, usuario):
    from services.requisicao_compra import transicionar
    transicionar(sc, EstadoRequisicao.AGUARDANDO_APROVACAO, usuario,
                 motivo='envio de teste')
    db.session.commit()
    return sc


def test_envio_carimba_a_faixa_e_o_porque():
    with app.app_context():
        admin = _admin()
        _faixas(admin.id)
        obra = _obra(admin.id)
        sc = _sc(admin.id, obra.id, 1000, estado=EstadoRequisicao.RASCUNHO)
        _enviar(sc, admin)
        assert sc.alcada_carimbada_em is not None
        assert sc.alcada_degraus == 1                    # sem concorrência
        assert sc.faixa_exigida_id is not None
        assert sc.alcada_motivos['condicoes'][0]['codigo'] == 'sem_concorrencia'


def test_carimbo_nao_muda_por_fato_posterior():
    """Uma SC de R$ 28 mil criada DEPOIS não pode mudar a régua de quem já
    está em aprovação."""
    from services.alcada_compras import pendencias_de_aprovacao
    with app.app_context():
        admin = _admin()
        _faixas(admin.id)
        obra = _obra(admin.id)
        sc = _sc(admin.id, obra.id, 1000, estado=EstadoRequisicao.RASCUNHO)
        _enviar(sc, admin)
        antes = list(pendencias_de_aprovacao(sc))

        _sc(admin.id, obra.id, 28000)      # fato novo na mesma obra/etapa
        assert list(pendencias_de_aprovacao(sc)) == antes


def test_sc_sem_carimbo_continua_avaliada_na_leitura():
    """SC anterior à fase (sem carimbo) não pode quebrar."""
    from services.alcada_compras import pendencias_de_aprovacao
    with app.app_context():
        admin = _admin()
        _faixas(admin.id)
        obra = _obra(admin.id)
        sc = _sc(admin.id, obra.id, 1000)   # criada crua, sem passar pelo envio
        assert sc.alcada_carimbada_em is None
        assert pendencias_de_aprovacao(sc)   # não levanta, e cobra algo


def test_reenvio_depois_de_rejeicao_recarimba():
    """Rodada nova, régua nova: o que mudou entre uma e outra vale agora."""
    from services.requisicao_compra import transicionar
    with app.app_context():
        admin = _admin()
        _faixas(admin.id)
        obra = _obra(admin.id)
        sc = _sc(admin.id, obra.id, 1000, estado=EstadoRequisicao.RASCUNHO)
        _enviar(sc, admin)
        primeiro = sc.alcada_carimbada_em
        assert sc.alcada_motivos['valor_efetivo'] == 1000.0

        transicionar(sc, EstadoRequisicao.REJEITADA, admin, motivo='faltou dado')
        transicionar(sc, EstadoRequisicao.RASCUNHO, admin, motivo='corrigindo')
        db.session.commit()
        _sc(admin.id, obra.id, 28000)       # fato novo, entre as rodadas
        _enviar(sc, admin)

        assert sc.alcada_carimbada_em >= primeiro
        assert sc.alcada_motivos['valor_efetivo'] == 29000.0


# ═══════════════════════════════════════════════════════════════════════
# Urgência na SC
# ═══════════════════════════════════════════════════════════════════════

def test_urgente_sem_justificativa_e_recusado():
    from services.requisicao_compra import DadosInvalidos, validar_urgencia
    with app.app_context():
        with pytest.raises(DadosInvalidos):
            validar_urgencia('urgente', '')
        assert validar_urgencia('urgente', 'concretagem parada') == \
            ('urgente', 'concretagem parada')
        assert validar_urgencia('normal', '') == ('normal', None)
        with pytest.raises(DadosInvalidos):
            validar_urgencia('urgentissimo', 'qualquer coisa')
