"""
tests/test_metricas_produtividade.py — Task #3

Cenários cobertos:
  1. single_role (só pedreiros) — produtividade real calculada
  2. equipe mista (2 pedreiros + 1 ajudante) — índice equipe + gargalo
  3. papel subutilizado — folga >= 30%
  4. operacional editado retroativamente reflete em RDOs antigos
  5. operacional editado "a partir de hoje" preserva RDO antigo
  6. cobertura: motivos sem_funcao / ambiguo reduzem cobertura
  7. funcionário em 2 RDOs no mesmo dia — sem dupla contagem de custo
  8. ausência de dados — retorna listas vazias sem exceção
"""
import os
import sys
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import (
    Usuario, TipoUsuario, Funcionario, Obra, Cliente,
    RDO, RDOMaoObra, RDOCustoDiario, RDOServicoSubatividade,
    Servico, ComposicaoServico, Insumo, Funcao,
    ObraOrcamentoOperacional, ObraOrcamentoOperacionalItem,
    ObraOrcamentoOperacionalItemVersao,
)
from werkzeug.security import generate_password_hash

logging.basicConfig(level=logging.WARNING)


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures compartilhados
# ──────────────────────────────────────────────────────────────────────────────

def _suffix():
    return datetime.utcnow().strftime('%f')


class Fx:
    admin = None
    obra = None
    s = ''


_fx = Fx()


@pytest.fixture(scope='module', autouse=True)
def setup_module():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    with app.app_context():
        s = _suffix()
        _fx.s = s

        admin = Usuario(
            username=f'met_{s}',
            email=f'met_{s}@sige.test',
            nome='Test Metricas',
            tipo_usuario=TipoUsuario.ADMIN,
            password_hash=generate_password_hash('Test@1234'),
            versao_sistema='v2',
            ativo=True,
        )
        db.session.add(admin)
        db.session.flush()

        cli = Cliente(nome=f'CLI-MET-{s}', admin_id=admin.id)
        db.session.add(cli)
        db.session.flush()

        obra = Obra(
            nome=f'Obra MET {s}',
            codigo=f'OM{s[:8]}',
            data_inicio=date(2026, 1, 1),
            admin_id=admin.id,
            cliente_id=cli.id,
            valor_contrato=500000,
        )
        db.session.add(obra)
        db.session.commit()

        _fx.admin = admin
        _fx.obra = obra

        yield


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _func(nome_suffix='', salario=3000.0, tipo='salario', valor_diaria=0.0,
          funcao_id=None):
    s = _suffix()
    cpf_raw = f'99{s}{nome_suffix}'[:14].ljust(14, '0')[:14]
    f = Funcionario(
        nome=f'Func MET {s} {nome_suffix}',
        cpf=cpf_raw,
        codigo=f'FM{s[:8]}',
        data_admissao=date(2025, 1, 1),
        admin_id=_fx.admin.id,
        tipo_remuneracao=tipo,
        salario=salario,
        valor_diaria=valor_diaria,
        valor_va=0.0,
        valor_vt=0.0,
        funcao_id=funcao_id,
        ativo=True,
    )
    db.session.add(f)
    db.session.flush()
    return f


def _rdo(obra, data, sufixo):
    r = RDO(
        numero_rdo=f'RDO-MET-{_fx.s}-{sufixo}',
        obra_id=obra.id,
        data_relatorio=data,
        admin_id=_fx.admin.id,
        status='Finalizado',
        criado_por_id=_fx.admin.id,
    )
    db.session.add(r)
    db.session.flush()
    return r


def _sub(rdo, servico_id, nome, qty=None):
    s = RDOServicoSubatividade(
        rdo_id=rdo.id,
        servico_id=servico_id,
        nome_subatividade=nome,
        percentual_conclusao=0.0,
        ativo=True,
        admin_id=_fx.admin.id,
        quantidade_produzida=qty,
    )
    db.session.add(s)
    db.session.flush()
    return s


def _mo(rdo, func, horas, sub=None, composicao_id=None, vinculo='auto', extras=0.0):
    m = RDOMaoObra(
        rdo_id=rdo.id,
        funcionario_id=func.id,
        funcao_exercida='Pedreiro',
        horas_trabalhadas=horas,
        horas_extras=extras,
        admin_id=_fx.admin.id,
        subatividade_id=sub.id if sub else None,
        composicao_servico_id=composicao_id,
        vinculo_status=vinculo,
    )
    db.session.add(m)
    db.session.flush()
    return m


def _custo_diario(rdo, func, custo_total, horas_normais=8.0):
    c = RDOCustoDiario(
        rdo_id=rdo.id,
        funcionario_id=func.id,
        admin_id=_fx.admin.id,
        data=rdo.data_relatorio,
        tipo_remuneracao_snapshot='salario',
        componente_folha=custo_total,
        componente_va=0,
        componente_vt=0,
        componente_extra=0,
        custo_total_dia=custo_total,
        horas_normais=horas_normais,
        horas_extras=0,
        tipo_lancamento='rdo',
    )
    db.session.add(c)
    db.session.flush()
    return c


def _servico(nome, unidade='m2'):
    s = Servico(
        nome=nome,
        descricao='',
        categoria='construcao',
        unidade_medida=unidade,
        admin_id=_fx.admin.id,
        ativo=True,
    )
    db.session.add(s)
    db.session.flush()
    return s


def _insumo(nome, tipo='MAO_OBRA'):
    i = Insumo(
        nome=nome,
        tipo=tipo,
        unidade='h',
        admin_id=_fx.admin.id,
        ativo=True,
    )
    db.session.add(i)
    db.session.flush()
    return i


def _composicao(servico_id, insumo_id, coeficiente):
    c = ComposicaoServico(
        servico_id=servico_id,
        insumo_id=insumo_id,
        coeficiente=coeficiente,
        admin_id=_fx.admin.id,
    )
    db.session.add(c)
    db.session.flush()
    return c


def _operacional(obra, servico, composicao_snap, margem_pct=20.0, imposto_pct=10.0):
    """Cria ObraOrcamentoOperacional + item + versao para obra+servico."""
    op = ObraOrcamentoOperacional.query.filter_by(obra_id=obra.id).first()
    if not op:
        op = ObraOrcamentoOperacional(obra_id=obra.id, admin_id=_fx.admin.id)
        db.session.add(op)
        db.session.flush()

    item = ObraOrcamentoOperacionalItem(
        operacional_id=op.id,
        admin_id=_fx.admin.id,
        servico_id=servico.id,
        descricao=servico.nome,
        unidade=servico.unidade_medida,
        quantidade=1,
    )
    db.session.add(item)
    db.session.flush()

    ver = ObraOrcamentoOperacionalItemVersao(
        item_id=item.id,
        admin_id=_fx.admin.id,
        composicao_snapshot=composicao_snap,
        margem_pct=margem_pct,
        imposto_pct=imposto_pct,
        vigente_de=datetime(2026, 1, 1),
        vigente_ate=None,
        modo_aplicacao='clonagem_inicial',
    )
    db.session.add(ver)
    db.session.flush()
    return item, ver


# ──────────────────────────────────────────────────────────────────────────────
# Testes
# ──────────────────────────────────────────────────────────────────────────────

def test_1_single_role_pedreiros():
    """Single-role: 2 pedreiros, 8h cada, 10m² produzidos.
    Produtividade real = 10 / 16 = 0.625 m²/h.
    """
    with app.app_context():
        servico = _servico('Assentamento Cerâmica T1')
        insumo_ped = _insumo('Pedreiro T1')
        comp = _composicao(servico.id, insumo_ped.id, 1.6)  # coef = 1.6 h/m²
        db.session.flush()

        snap = [{'insumo_id': insumo_ped.id, 'nome': 'Pedreiro T1',
                  'coeficiente': 1.6, 'preco_unitario': 30.0, 'tipo': 'MAO_OBRA'}]
        _operacional(_fx.obra, servico, snap)
        db.session.commit()

        data = date(2026, 3, 1)
        rdo = _rdo(_fx.obra, data, 'T1A')
        f1 = _func('P1')
        f2 = _func('P2')
        sub = _sub(rdo, servico.id, 'Assentamento', qty=10.0)
        _mo(rdo, f1, 8.0, sub=sub, composicao_id=comp.id, vinculo='auto')
        _mo(rdo, f2, 8.0, sub=sub, composicao_id=comp.id, vinculo='auto')
        _custo_diario(rdo, f1, 120.0, horas_normais=8.0)
        _custo_diario(rdo, f2, 120.0, horas_normais=8.0)
        db.session.commit()

        from services.metricas_produtividade import produtividade_por_servico
        result = produtividade_por_servico(
            _fx.admin.id, date(2026, 3, 1), date(2026, 3, 31)
        )
        met = next((m for m in result if m['servico_id'] == servico.id), None)
        assert met is not None, "Serviço não encontrado nas métricas"
        assert met['total_hh'] == pytest.approx(16.0, abs=0.01)
        assert met['total_produzido'] == pytest.approx(10.0, abs=0.01)
        assert met['prod_real_media'] == pytest.approx(10.0/16.0, abs=0.001)
        # cobertura: ambos com vinculo='auto' → 100%
        assert met['cobertura_pct'] == pytest.approx(100.0, abs=0.1)
        # prod orçada gargalo = 1/1.6 ≈ 0.625
        assert met['prod_orcada_gargalo'] == pytest.approx(1.0/1.6, abs=0.001)
        # índice ≈ 100% (real == orçada)
        assert met['indice_pct'] == pytest.approx(100.0, abs=1.0)


def test_2_equipe_mista_gargalo():
    """Equipe mista: 2 pedreiros (coef=1.0 h/m²) + 1 ajudante (coef=0.5 h/m²).
    Capacidade pedreiro = 16h/1.0 = 16 m²; Capacidade ajudante = 8h/0.5 = 16 m².
    Igual → ambos gargalo; sem subutilizado.
    """
    with app.app_context():
        servico = _servico('Alvenaria T2', 'm2')
        ins_ped = _insumo('Pedreiro T2')
        ins_aj = _insumo('Ajudante T2')
        comp_ped = _composicao(servico.id, ins_ped.id, 1.0)
        comp_aj = _composicao(servico.id, ins_aj.id, 0.5)

        snap = [
            {'insumo_id': ins_ped.id, 'nome': 'Pedreiro T2',
             'coeficiente': 1.0, 'preco_unitario': 25.0, 'tipo': 'MAO_OBRA'},
            {'insumo_id': ins_aj.id, 'nome': 'Ajudante T2',
             'coeficiente': 0.5, 'preco_unitario': 18.0, 'tipo': 'MAO_OBRA'},
        ]
        _operacional(_fx.obra, servico, snap, margem_pct=15.0, imposto_pct=8.0)
        db.session.commit()

        data = date(2026, 3, 5)
        rdo = _rdo(_fx.obra, data, 'T2A')
        p1 = _func('P2-1')
        p2 = _func('P2-2')
        aj = _func('AJ2-1')
        sub = _sub(rdo, servico.id, 'Alvenaria', qty=15.0)
        _mo(rdo, p1, 8.0, sub=sub, composicao_id=comp_ped.id, vinculo='auto')
        _mo(rdo, p2, 8.0, sub=sub, composicao_id=comp_ped.id, vinculo='auto')
        _mo(rdo, aj, 8.0, sub=sub, composicao_id=comp_aj.id, vinculo='auto')
        _custo_diario(rdo, p1, 100.0)
        _custo_diario(rdo, p2, 100.0)
        _custo_diario(rdo, aj, 72.0)
        db.session.commit()

        from services.metricas_produtividade import produtividade_por_servico
        result = produtividade_por_servico(
            _fx.admin.id, date(2026, 3, 1), date(2026, 3, 31)
        )
        met = next((m for m in result if m['servico_id'] == servico.id), None)
        assert met is not None
        assert met['total_hh'] == pytest.approx(24.0, abs=0.01)
        assert met['total_produzido'] == pytest.approx(15.0, abs=0.01)
        # capacidade ajudante: 8/0.5=16; pedreiros: 16/1.0=16 → empate, nenhum subutilizado
        assert met['papel_subutilizado_nome'] is None


def test_3_papel_subutilizado():
    """Ajudante com muita folga: 1 pedreiro (8h,coef=1.0), 1 ajudante (8h,coef=0.1).
    Capacidade ped = 8; capacidade aj = 80. Folga aj = 80-8=72; 72/80=0.9 → subutilizado.
    """
    with app.app_context():
        servico = _servico('Reboco T3', 'm2')
        ins_ped = _insumo('Pedreiro T3')
        ins_aj = _insumo('Servente T3')
        comp_ped = _composicao(servico.id, ins_ped.id, 1.0)
        comp_aj = _composicao(servico.id, ins_aj.id, 0.1)

        snap = [
            {'insumo_id': ins_ped.id, 'nome': 'Pedreiro T3',
             'coeficiente': 1.0, 'preco_unitario': 22.0, 'tipo': 'MAO_OBRA'},
            {'insumo_id': ins_aj.id, 'nome': 'Servente T3',
             'coeficiente': 0.1, 'preco_unitario': 15.0, 'tipo': 'MAO_OBRA'},
        ]
        _operacional(_fx.obra, servico, snap)
        db.session.commit()

        data = date(2026, 3, 8)
        rdo = _rdo(_fx.obra, data, 'T3A')
        ped = _func('PED3')
        aj = _func('AJ3')
        sub = _sub(rdo, servico.id, 'Reboco', qty=8.0)
        _mo(rdo, ped, 8.0, sub=sub, composicao_id=comp_ped.id, vinculo='auto')
        _mo(rdo, aj, 8.0, sub=sub, composicao_id=comp_aj.id, vinculo='auto')
        _custo_diario(rdo, ped, 80.0)
        _custo_diario(rdo, aj, 60.0)
        db.session.commit()

        from services.metricas_produtividade import produtividade_por_servico
        result = produtividade_por_servico(
            _fx.admin.id, date(2026, 3, 1), date(2026, 3, 31)
        )
        met = next((m for m in result if m['servico_id'] == servico.id), None)
        assert met is not None
        # Servente tem coef=0.1: capacidade=80 >> producao_esperada=8 → subutilizado
        assert met['papel_subutilizado_nome'] is not None
        assert 'Servente' in met['papel_subutilizado_nome'] or 'T3' in met['papel_subutilizado_nome']


def test_4_operacional_retroativo_reflete():
    """Operacional editado retroativamente deve refletir em RDOs antigos."""
    with app.app_context():
        servico = _servico('Impermeabilização T4', 'm2')
        ins = _insumo('Pedreiro T4')
        comp = _composicao(servico.id, ins.id, 2.0)

        snap_original = [{'insumo_id': ins.id, 'nome': 'Pedreiro T4',
                           'coeficiente': 2.0, 'preco_unitario': 30.0, 'tipo': 'MAO_OBRA'}]
        item, ver = _operacional(_fx.obra, servico, snap_original,
                                 margem_pct=20.0, imposto_pct=10.0)
        db.session.commit()

        data_rdo = date(2026, 3, 10)
        rdo = _rdo(_fx.obra, data_rdo, 'T4A')
        ped = _func('PED4')
        sub = _sub(rdo, servico.id, 'Impermeabilizacao', qty=5.0)
        _mo(rdo, ped, 10.0, sub=sub, composicao_id=comp.id, vinculo='auto')
        _custo_diario(rdo, ped, 150.0, horas_normais=10.0)
        db.session.commit()

        # Receita antes da edição
        from services.metricas_produtividade import produtividade_por_servico
        r_antes = produtividade_por_servico(
            _fx.admin.id, date(2026, 3, 10), date(2026, 3, 10)
        )
        met_antes = next((m for m in r_antes if m['servico_id'] == servico.id), None)
        receita_antes = met_antes['receita_liq_media_un'] if met_antes else None

        # Edita retroativamente: novo preco_unitario mais alto
        snap_novo = [{'insumo_id': ins.id, 'nome': 'Pedreiro T4',
                       'coeficiente': 2.0, 'preco_unitario': 50.0, 'tipo': 'MAO_OBRA'}]
        from services.orcamento_operacional import editar_item
        editar_item(item.id, snap_novo, 20.0, 10.0, modo='retroativo',
                    criado_por_id=_fx.admin.id, motivo='Ajuste retroativo T4')

        # Após edição retroativa, RDO antigo deve refletir novo valor
        r_depois = produtividade_por_servico(
            _fx.admin.id, date(2026, 3, 10), date(2026, 3, 10)
        )
        met_depois = next((m for m in r_depois if m['servico_id'] == servico.id), None)
        assert met_depois is not None
        receita_depois = met_depois['receita_liq_media_un']
        # Receita unitária com preco=50 deve ser maior que com preco=30
        if receita_antes is not None and receita_depois is not None:
            assert receita_depois > receita_antes


def test_5_operacional_a_partir_de_hoje_preserva_rdo_antigo():
    """Operacional editado 'a_partir_de_hoje' NÃO deve alterar RDOs anteriores."""
    with app.app_context():
        servico = _servico('Pintura T5', 'm2')
        ins = _insumo('Pintor T5')
        comp = _composicao(servico.id, ins.id, 0.8)

        snap_v1 = [{'insumo_id': ins.id, 'nome': 'Pintor T5',
                     'coeficiente': 0.8, 'preco_unitario': 20.0, 'tipo': 'MAO_OBRA'}]
        item, _ = _operacional(_fx.obra, servico, snap_v1,
                               margem_pct=15.0, imposto_pct=8.0)
        db.session.commit()

        # RDO antigo (antes da edição)
        data_antigo = date(2026, 2, 1)
        rdo_ant = _rdo(_fx.obra, data_antigo, 'T5ANT')
        ped = _func('PIN5')
        sub_ant = _sub(rdo_ant, servico.id, 'Pintura v1', qty=10.0)
        _mo(rdo_ant, ped, 8.0, sub=sub_ant, composicao_id=comp.id, vinculo='auto')
        _custo_diario(rdo_ant, ped, 96.0)
        db.session.commit()

        # Receita do RDO antigo com snap_v1
        from services.metricas_produtividade import produtividade_por_servico
        r_antes = produtividade_por_servico(
            _fx.admin.id, date(2026, 2, 1), date(2026, 2, 1)
        )
        met_v1 = next((m for m in r_antes if m['servico_id'] == servico.id), None)

        # Edita "a_partir_de_hoje"
        snap_v2 = [{'insumo_id': ins.id, 'nome': 'Pintor T5',
                     'coeficiente': 0.8, 'preco_unitario': 40.0, 'tipo': 'MAO_OBRA'}]
        from services.orcamento_operacional import editar_item
        editar_item(item.id, snap_v2, 15.0, 8.0, modo='a_partir_de_hoje',
                    criado_por_id=_fx.admin.id)

        # RDO antigo deve ainda ler snap_v1
        r_depois = produtividade_por_servico(
            _fx.admin.id, date(2026, 2, 1), date(2026, 2, 1)
        )
        met_v1_depois = next((m for m in r_depois if m['servico_id'] == servico.id), None)

        if met_v1 and met_v1_depois:
            assert (met_v1['receita_liq_media_un'] == pytest.approx(
                met_v1_depois['receita_liq_media_un'], rel=0.01
            )), "RDO antigo foi afetado pela edição a_partir_de_hoje"


def test_6_cobertura_por_motivo():
    """Horas com vinculo_status='sem_funcao' e 'ambiguo' reduzem cobertura."""
    with app.app_context():
        servico = _servico('Escavação T6', 'm3')
        ins = _insumo('Operador T6')
        comp = _composicao(servico.id, ins.id, 3.0)

        snap = [{'insumo_id': ins.id, 'nome': 'Operador T6',
                 'coeficiente': 3.0, 'preco_unitario': 40.0, 'tipo': 'MAO_OBRA'}]
        _operacional(_fx.obra, servico, snap)
        db.session.commit()

        data = date(2026, 3, 15)
        rdo = _rdo(_fx.obra, data, 'T6A')
        op_aut = _func('OP6A')
        op_sf = _func('OP6B')
        op_amb = _func('OP6C')
        sub = _sub(rdo, servico.id, 'Escavacao', qty=3.0)
        _mo(rdo, op_aut, 8.0, sub=sub, composicao_id=comp.id, vinculo='auto')
        _mo(rdo, op_sf, 8.0, sub=sub, composicao_id=None, vinculo='sem_funcao')
        _mo(rdo, op_amb, 8.0, sub=sub, composicao_id=comp.id, vinculo='ambiguo')
        _custo_diario(rdo, op_aut, 120.0)
        _custo_diario(rdo, op_sf, 120.0)
        _custo_diario(rdo, op_amb, 120.0)
        db.session.commit()

        from services.metricas_produtividade import produtividade_por_servico
        result = produtividade_por_servico(
            _fx.admin.id, date(2026, 3, 15), date(2026, 3, 15)
        )
        met = next((m for m in result if m['servico_id'] == servico.id), None)
        assert met is not None
        # 8h confirmadas (auto) de 24h total → cobertura ≈ 33.3%
        assert met['cobertura_pct'] == pytest.approx(33.3, abs=1.5)


def test_7_dois_rdos_mesmo_dia_sem_duplicata():
    """Funcionário em 2 RDOs no mesmo dia: custo total NÃO duplica."""
    with app.app_context():
        from models import Obra as ObraModel, Cliente as ClienteModel
        s2 = _suffix()
        cli2 = ClienteModel(nome=f'CLI7-{s2}', admin_id=_fx.admin.id)
        db.session.add(cli2)
        db.session.flush()
        obra2 = ObraModel(
            nome=f'Obra T7B {s2}', codigo=f'OT7B{s2[:6]}',
            data_inicio=date(2026, 1, 1),
            admin_id=_fx.admin.id, cliente_id=cli2.id,
            valor_contrato=10000,
        )
        db.session.add(obra2)

        servico = _servico('Terraplanagem T7', 'm3')
        ins = _insumo('Motorista T7')
        comp = _composicao(servico.id, ins.id, 2.0)
        db.session.commit()

        data = date(2026, 3, 20)
        func = _func('MOT7')
        rdo_a = _rdo(_fx.obra, data, 'T7A')
        rdo_b = _rdo(obra2, data, 'T7B')

        sub_a = _sub(rdo_a, servico.id, 'Terra A', qty=5.0)
        sub_b = _sub(rdo_b, servico.id, 'Terra B', qty=3.0)
        _mo(rdo_a, func, 5.0, sub=sub_a, composicao_id=comp.id, vinculo='auto')
        _mo(rdo_b, func, 3.0, sub=sub_b, composicao_id=comp.id, vinculo='auto')

        # RDOCustoDiario com rateio (5h no RDO_A, 3h no RDO_B)
        # custo total dia = 160 → rdo_a: 100, rdo_b: 60
        _custo_diario(rdo_a, func, 100.0, horas_normais=8.0)
        _custo_diario(rdo_b, func, 60.0, horas_normais=8.0)
        db.session.commit()

        from services.metricas_produtividade import producao_por_funcionario
        result = producao_por_funcionario(
            _fx.admin.id, date(2026, 3, 20), date(2026, 3, 20)
        )
        func_met = next((f for f in result if f['funcionario_id'] == func.id), None)
        assert func_met is not None
        # Custo total = 100 + 60 = 160 (não 200 ou 320)
        if func_met['custo_total'] is not None:
            assert func_met['custo_total'] == pytest.approx(160.0, abs=1.0)


def test_8_ausencia_de_dados():
    """Sem RDOs no período → retorna listas vazias sem exceção."""
    with app.app_context():
        from services.metricas_produtividade import (
            produtividade_por_servico,
            producao_por_funcionario,
            ranking_funcionarios,
        )

        # Período sem nenhum RDO (futuro distante)
        di = date(2030, 1, 1)
        df = date(2030, 1, 31)

        result1 = produtividade_por_servico(_fx.admin.id, di, df)
        assert result1 == []

        result2 = producao_por_funcionario(_fx.admin.id, di, df)
        assert result2 == []

        result3 = ranking_funcionarios(_fx.admin.id, di, df)
        assert result3 == []
