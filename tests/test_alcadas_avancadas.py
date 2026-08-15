"""Alçadas avançadas — fase 3 do ciclo de compras.

Spec: docs/superpowers/specs/2026-08-15-alcadas-design.md
Plano: docs/superpowers/plans/2026-08-15-plano-execucao-alcadas.md

O valor deixa de ser a única pergunta: as quatro condições que sobem um degrau,
o anti-fracionamento por janela, o rito de emergência 48h e o corte de cotações
que vira dado da faixa.

Molde de tests/test_financeiro_dois_fluxos.py: fixtures locais, tenant por
uuid4, sem depender de seed.

A1 — só o esqueleto. Estes testes cobrem os DEFAULTS das colunas novas, e
default aqui não é detalhe: cada um deles é a descrição do registro histórico.
Requisição que já existia é `'simples'`, não emergencial e sem degrau; faixa
que já existia não exige cotação nenhuma por dado e não sobe degrau por
condição nenhuma; tenant que já existia tem a flag desligada. É o que garante
que a migration não reescreve o passado.
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
from models import (Cliente, ConfiguracaoEmpresa, EstadoRequisicao, FaixaAlcada,
                    Obra, RequisicaoCompra, TipoUsuario, Usuario)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-alcadas-avancadas'
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
    o = Obra(nome=f'Obra {suf}', codigo=f'O{suf[:6].upper()}',
             data_inicio=date(2026, 1, 1), admin_id=admin_id,
             cliente_id=cliente.id, ativo=True)
    db.session.add(o)
    db.session.commit()
    return o


def _faixa(admin_id, ordem=1, valor_ate=Decimal('5000.00')):
    f = FaixaAlcada(admin_id=admin_id, ordem=ordem, valor_ate=valor_ate,
                    aprovacoes_necessarias=1, exige_admin=False,
                    exige_mapa_concorrencia=False, ativo=True)
    db.session.add(f)
    db.session.commit()
    return f


def _requisicao(admin_id, obra_id, solicitante_id):
    r = RequisicaoCompra(
        numero=f'RC-{uuid.uuid4().hex[:8].upper()}', admin_id=admin_id,
        obra_id=obra_id, solicitante_id=solicitante_id,
        estado=EstadoRequisicao.RASCUNHO,
        valor_estimado=Decimal('4900.00'))
    db.session.add(r)
    db.session.commit()
    return r


def _configuracao(admin_id):
    cfg = ConfiguracaoEmpresa(admin_id=admin_id,
                              nome_empresa=f'Tenant {admin_id}')
    db.session.add(cfg)
    db.session.commit()
    return cfg


# ---------------------------------------------------------------------------
# A1 — o esqueleto: as colunas e os defaults que descrevem o passado
# ---------------------------------------------------------------------------

def test_faixa_de_alcada_nasce_sem_exigir_cotacao_por_dado():
    """`minimo_cotacoes` nasce 0 — a faixa não exige mapa por dado.

    0 é o valor que preserva o comportamento de quem já existia: quem exigia
    mapa exigia por `exige_mapa_concorrencia`, e é o backfill da 297 (não o
    default) que traduz aquele booleano em 2 cotações.
    """
    with app.app_context():
        adm = _admin()
        faixa = _faixa(adm.id)
        db.session.refresh(faixa)
        assert faixa.minimo_cotacoes == 0


def test_faixa_de_alcada_nasce_sem_condicao_ativa():
    """`condicoes_ativas` nasce `''` — nenhuma das quatro vale por padrão.

    Vazio é o comportamento de hoje: faixa que não ativa condição nenhuma
    nunca sobe degrau. Ligar condição é decisão do tenant, uma a uma.
    """
    with app.app_context():
        adm = _admin()
        faixa = _faixa(adm.id)
        db.session.refresh(faixa)
        assert faixa.condicoes_ativas == ''


def test_requisicao_nasce_em_regime_simples():
    """`regime_alcada` nasce `'simples'` — o motor de hoje.

    O regime é carimbado na linha na criação, a partir da flag. Requisição
    que já existia no banco é `'simples'` por definição: ela foi criada num
    mundo em que a alçada só olhava o valor.
    """
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        req = _requisicao(adm.id, obra.id, adm.id)
        db.session.refresh(req)
        assert req.regime_alcada == 'simples'


def test_requisicao_nasce_sem_emergencia_e_sem_degrau():
    """`emergencial` False, `ratificada_em` None, `degrau_aplicado` `''`.

    As três juntas dizem "esta requisição não invocou rito nenhum e não subiu
    de faixa por motivo nenhum" — que é a verdade sobre todo o histórico.
    """
    with app.app_context():
        adm = _admin()
        obra = _obra(adm.id)
        req = _requisicao(adm.id, obra.id, adm.id)
        db.session.refresh(req)
        assert req.emergencial is False
        assert req.ratificada_em is None
        assert req.degrau_aplicado == ''


def test_tenant_nasce_com_alcadas_avancadas_desligadas_e_janela_de_30_dias():
    """A flag nasce OFF e a janela do fracionamento nasce em 30 dias (D2).

    OFF porque ninguém vira sozinho — a virada é por tenant, e a cadeia de
    cinco elos é conferida pelo script da A2. Os 30 dias são a recomendação
    do spec, e são COLUNA justamente para poder virar 7 por UPDATE.
    """
    with app.app_context():
        adm = _admin()
        cfg = _configuracao(adm.id)
        db.session.refresh(cfg)
        assert cfg.alcadas_avancadas_ativa is False
        assert cfg.janela_fracionamento_dias == 30
