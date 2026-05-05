"""
tests/test_custo_diario.py

Testes unitários do módulo services/custo_funcionario_dia.py.

Cenários cobertos:
  1. Diarista simples — 1 RDO, 8h, sem extras
  2. Mensalista com hora extra — custo extra = vh × 1.5
  3. Mensalista em 2 RDOs no mesmo dia — rateio fecha o custo total do dia
  4. Mudança de salário não afeta RDOs antigos (snapshot imutável)
  5. Idempotência — salvar 2× não duplica linha
  6. Job de cobertura ociosa — mensalista sem RDOs tem dias ociosos criados
  7. remover_custo_diario_rdo — remove apenas linhas do RDO alvo
"""

import os
import sys
import logging
from datetime import date, datetime
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import (
    Usuario, TipoUsuario, Funcionario, Obra, Cliente,
    RDO, RDOMaoObra, RDOCustoDiario,
)
from werkzeug.security import generate_password_hash

logging.basicConfig(level=logging.WARNING)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers de fixture
# ──────────────────────────────────────────────────────────────────────────────

def _suffix():
    return datetime.utcnow().strftime('%f')


class Fixtures:
    """Container de objetos criados para o módulo de testes."""
    admin = None
    obra = None
    obra2 = None
    s = ''  # sufixo único da sessão de testes


_fx = Fixtures()


@pytest.fixture(scope='module', autouse=True)
def setup_module():
    """Cria admin + obras compartilhadas para todos os testes."""
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    with app.app_context():
        s = _suffix()

        admin = Usuario(
            username=f'custo_dia_{s}',
            email=f'custo_dia_{s}@sige.test',
            nome='Test Custo Dia',
            tipo_usuario=TipoUsuario.ADMIN,
            password_hash=generate_password_hash('Test@1234'),
            versao_sistema='v2',
            ativo=True,
        )
        db.session.add(admin)
        db.session.flush()

        cli = Cliente(nome=f'CLI-CD-{s}', admin_id=admin.id)
        db.session.add(cli)
        db.session.flush()

        obra = Obra(
            nome=f'Obra CD {s}',
            codigo=f'OCD{s[:6]}',
            data_inicio=date(2026, 1, 1),
            admin_id=admin.id,
            cliente_id=cli.id,
            valor_contrato=100000,
        )
        db.session.add(obra)

        cli2 = Cliente(nome=f'CLI-CD2-{s}', admin_id=admin.id)
        db.session.add(cli2)
        db.session.flush()

        obra2 = Obra(
            nome=f'Obra CD2 {s}',
            codigo=f'OC2{s[:6]}',
            data_inicio=date(2026, 1, 1),
            admin_id=admin.id,
            cliente_id=cli2.id,
            valor_contrato=50000,
        )
        db.session.add(obra2)
        db.session.commit()

        _fx.admin = admin
        _fx.obra = obra
        _fx.obra2 = obra2
        _fx.s = s

        yield


def _func(tipo='salario', salario=3000.0, valor_diaria=0.0,
          valor_va=15.0, valor_vt=10.0, extra_cpf=''):
    """Cria e persiste um Funcionario."""
    s = _suffix()
    cpf_raw = f'111{s}{extra_cpf}'[:14]
    cpf = cpf_raw.ljust(14, '0')[:14]
    f = Funcionario(
        nome=f'Func CD {s}',
        cpf=cpf,
        codigo=f'FC{s[:8]}',
        data_admissao=date(2025, 1, 1),
        admin_id=_fx.admin.id,
        tipo_remuneracao=tipo,
        salario=salario,
        valor_diaria=valor_diaria,
        valor_va=valor_va,
        valor_vt=valor_vt,
        ativo=True,
    )
    db.session.add(f)
    db.session.flush()
    return f


def _rdo(obra, data, numero_suffix):
    r = RDO(
        numero_rdo=f'RDO-CDT-{_fx.s}-{numero_suffix}',
        obra_id=obra.id,
        data_relatorio=data,
        admin_id=_fx.admin.id,
        status='Finalizado',
        criado_por_id=_fx.admin.id,
    )
    db.session.add(r)
    db.session.flush()
    return r


def _mo(rdo, func, horas, extras=0.0):
    mo = RDOMaoObra(
        rdo_id=rdo.id,
        funcionario_id=func.id,
        funcao_exercida='Pedreiro',
        horas_trabalhadas=horas,
        horas_extras=extras,
        admin_id=_fx.admin.id,
    )
    db.session.add(mo)
    db.session.flush()
    return mo


# ──────────────────────────────────────────────────────────────────────────────
# Testes
# ──────────────────────────────────────────────────────────────────────────────

def test_1_diarista_simples():
    """Diarista 1 RDO 8h: custo = valor_diaria + VA + VT."""
    with app.app_context():
        func = _func(tipo='diaria', valor_diaria=150.0, valor_va=15.0, valor_vt=10.0)
        rdo = _rdo(_fx.obra, date(2026, 2, 10), '01')
        _mo(rdo, func, horas=8.0)
        db.session.commit()

        from services.custo_funcionario_dia import gravar_custo_funcionario_rdo
        gravar_custo_funcionario_rdo(rdo, _fx.admin.id)

        reg = RDOCustoDiario.query.filter_by(
            rdo_id=rdo.id, funcionario_id=func.id
        ).first()
        assert reg is not None
        assert reg.tipo_remuneracao_snapshot == 'diaria'
        assert float(reg.componente_folha) == pytest.approx(150.0, abs=0.02)
        assert float(reg.componente_va) == pytest.approx(15.0, abs=0.02)
        assert float(reg.componente_vt) == pytest.approx(10.0, abs=0.02)
        assert float(reg.custo_total_dia) == pytest.approx(175.0, abs=0.02)
        assert reg.tipo_lancamento == 'rdo'


def test_2_mensalista_hora_extra():
    """Mensalista 8h normal + 1h extra: componente_extra = vh × 1.5."""
    with app.app_context():
        func = _func(tipo='salario', salario=3300.0, valor_va=0.0, valor_vt=0.0)
        data = date(2026, 2, 11)
        rdo = _rdo(_fx.obra, data, '02')
        _mo(rdo, func, horas=8.0, extras=1.0)
        db.session.commit()

        from services.custo_funcionario_dia import gravar_custo_funcionario_rdo
        gravar_custo_funcionario_rdo(rdo, _fx.admin.id)

        reg = RDOCustoDiario.query.filter_by(
            rdo_id=rdo.id, funcionario_id=func.id
        ).first()
        assert reg is not None
        assert float(reg.horas_extras) == pytest.approx(1.0, abs=0.01)
        assert float(reg.componente_extra) > 0

        from utils import calcular_valor_hora_periodo
        vh = calcular_valor_hora_periodo(func, data, data)
        expected_extra = vh * 1.5 * 1.0
        assert float(reg.componente_extra) == pytest.approx(expected_extra, abs=0.05)


def test_3_mensalista_dois_rdos_rateio():
    """Mensalista em 2 RDOs (5h + 3h): custo total do dia fecha em 8h de trabalho."""
    with app.app_context():
        func = _func(tipo='salario', salario=2640.0, valor_va=15.0, valor_vt=10.0)
        data = date(2026, 2, 12)
        rdo_a = _rdo(_fx.obra, data, '03A')
        rdo_b = _rdo(_fx.obra2, data, '03B')
        _mo(rdo_a, func, horas=5.0)
        _mo(rdo_b, func, horas=3.0)
        db.session.commit()

        from services.custo_funcionario_dia import gravar_custo_funcionario_rdo
        gravar_custo_funcionario_rdo(rdo_a, _fx.admin.id)
        gravar_custo_funcionario_rdo(rdo_b, _fx.admin.id)

        reg_a = RDOCustoDiario.query.filter_by(
            rdo_id=rdo_a.id, funcionario_id=func.id
        ).first()
        reg_b = RDOCustoDiario.query.filter_by(
            rdo_id=rdo_b.id, funcionario_id=func.id
        ).first()
        assert reg_a and reg_b

        from utils import calcular_valor_hora_periodo
        vh = calcular_valor_hora_periodo(func, data, data)
        custo_8h = vh * 8.0 + 15.0 + 10.0  # VA+VT do dia inteiro

        total_gravado = float(reg_a.custo_total_dia) + float(reg_b.custo_total_dia)
        assert total_gravado == pytest.approx(custo_8h, abs=0.15), (
            f"Soma não fecha: {total_gravado:.2f} ≠ {custo_8h:.2f}"
        )


def test_4_snapshot_imutavel_mudanca_salario():
    """Linha retroativa conserva custo original após mudança de salário."""
    with app.app_context():
        func = _func(tipo='salario', salario=2000.0, valor_va=0.0, valor_vt=0.0)
        data = date(2026, 1, 15)

        from services.custo_funcionario_dia import calcular_custo_funcionario_no_rdo
        comp = calcular_custo_funcionario_no_rdo(func, 8.0, 8.0, 0.0, data)
        custo_original = float(comp['custo_total_dia'])

        reg = RDOCustoDiario(
            rdo_id=None,
            funcionario_id=func.id,
            admin_id=_fx.admin.id,
            data=data,
            tipo_lancamento='rdo',
            retroativo=True,
            tipo_remuneracao_snapshot='salario',
            componente_folha=comp['componente_folha'],
            componente_va=comp['componente_va'],
            componente_vt=comp['componente_vt'],
            componente_extra=comp['componente_extra'],
            custo_total_dia=comp['custo_total_dia'],
            horas_normais=comp['horas_normais'],
            horas_extras=comp['horas_extras'],
            custo_hora_normal=comp['custo_hora_normal'],
            dias_uteis_mes_referencia=comp.get('dias_uteis_mes_referencia'),
        )
        db.session.add(reg)
        db.session.commit()

        reg_id = reg.id
        func.salario = 5000.0
        db.session.commit()

        reg_check = db.session.get(RDOCustoDiario, reg_id)
        assert float(reg_check.custo_total_dia) == pytest.approx(custo_original, abs=0.02)
        assert reg_check.retroativo is True

        func.salario = 2000.0
        db.session.commit()


def test_5_idempotencia():
    """Salvar o mesmo RDO 2× não duplica linhas em RDOCustoDiario."""
    with app.app_context():
        func = _func(tipo='salario', salario=3000.0, valor_va=0.0, valor_vt=0.0)
        data = date(2026, 2, 16)
        rdo = _rdo(_fx.obra, data, '05')
        _mo(rdo, func, horas=8.0)
        db.session.commit()

        from services.custo_funcionario_dia import gravar_custo_funcionario_rdo
        gravar_custo_funcionario_rdo(rdo, _fx.admin.id)
        gravar_custo_funcionario_rdo(rdo, _fx.admin.id)

        count = RDOCustoDiario.query.filter_by(
            rdo_id=rdo.id, funcionario_id=func.id
        ).count()
        assert count == 1, f"Esperava 1 linha, encontrou {count}"


def test_6_cobertura_ociosa():
    """Mensalista sem RDOs em jan/2025 ganha dias ociosos criados."""
    with app.app_context():
        func = _func(tipo='salario', salario=2800.0, valor_va=0.0, valor_vt=0.0)

        from services.custo_funcionario_dia import gerar_dias_ociosos_mensalista, dias_uteis_mes
        criados = gerar_dias_ociosos_mensalista(func.id, 2025, 1, _fx.admin.id)
        db.session.commit()

        du = dias_uteis_mes(2025, 1)
        assert criados == du, f"Esperava {du} dias ociosos, criou {criados}"

        regs = RDOCustoDiario.query.filter_by(
            funcionario_id=func.id,
            tipo_lancamento='ocioso_mensal',
        ).all()
        assert len(regs) == du

        # Idempotência: rodar de novo não cria mais
        criados2 = gerar_dias_ociosos_mensalista(func.id, 2025, 1, _fx.admin.id)
        assert criados2 == 0, f"Segunda execução deveria criar 0, criou {criados2}"


def test_7_remover_custo_diario():
    """remover_custo_diario_rdo remove apenas linhas tipo='rdo' do RDO alvo."""
    with app.app_context():
        func = _func(tipo='salario', salario=3000.0, valor_va=0.0, valor_vt=0.0)
        data = date(2026, 2, 17)
        rdo = _rdo(_fx.obra, data, '07')
        _mo(rdo, func, horas=8.0)
        db.session.commit()

        from services.custo_funcionario_dia import (
            gravar_custo_funcionario_rdo, remover_custo_diario_rdo,
        )
        gravar_custo_funcionario_rdo(rdo, _fx.admin.id)
        assert RDOCustoDiario.query.filter_by(rdo_id=rdo.id).count() == 1

        n = remover_custo_diario_rdo(rdo.id)
        db.session.commit()

        assert n == 1
        assert RDOCustoDiario.query.filter_by(rdo_id=rdo.id).count() == 0
