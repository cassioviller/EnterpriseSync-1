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
