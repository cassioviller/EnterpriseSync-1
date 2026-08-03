"""p1 Steps D e E — o dia contado uma vez, e custo que implica medição.

**Step D.** O ponto e o RDO lançam o mesmo dia de trabalho por caminhos
diferentes, e nenhum dos dois dedups enxergava o outro: o do RDO usa `rdo_id`
na chave, e o custo do ponto nasce com `rdo_id` NULL. Por construção, nunca se
cruzavam.

**Step E.** Três caminhos de salvar RDO chamavam o serviço de custo direto,
sem emitir `rdo_finalizado` — geravam custo e pulavam
`recalcular_medicao_apos_rdo` (event_manager.py:1509), o segundo ouvinte do
mesmo evento.
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import (CustoObra, GestaoCustoFilho, GestaoCustoPai, RDO,
                    RDOMaoObra, RegistroPonto)
from helpers_tenant import dois_tenants

pytestmark = pytest.mark.integration

DATA = date(2026, 6, 15)


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-p1-dedup'
    with app.app_context():
        yield


@pytest.fixture(scope='module')
def _par():
    with app.app_context():
        return dois_tenants('ded', DATA)


def _limpar_custos(t):
    for c in CustoObra.query.filter_by(admin_id=t.admin_id, data=DATA).all():
        db.session.delete(c)
    filhos = (GestaoCustoFilho.query
              .filter_by(admin_id=t.admin_id, data_referencia=DATA).all())
    for f in filhos:
        db.session.delete(f)
    db.session.commit()


def _rdo_com_mao_de_obra(t):
    """RDO do dia com o funcionário do tenant apontado."""
    from uuid import uuid4
    rdo = RDO(numero_rdo=f'RDO-{uuid4().hex[:8]}', obra_id=t.obra_id,
              admin_id=t.admin_id, data_relatorio=DATA,
              criado_por_id=t.admin_id)
    db.session.add(rdo)
    db.session.flush()
    db.session.add(RDOMaoObra(rdo_id=rdo.id, funcionario_id=t.funcionario_id,
                              admin_id=t.admin_id, horas_trabalhadas=8.0,
                              funcao_exercida='Servente'))
    db.session.commit()
    return rdo


def _emitir_rdo_finalizado(t, rdo):
    from event_manager import EventManager
    EventManager.emit('rdo_finalizado', {'rdo_id': rdo.id},
                      admin_id=t.admin_id)


def _custos_do_dia(t):
    return CustoObra.query.filter_by(
        admin_id=t.admin_id, funcionario_id=t.funcionario_id, data=DATA).all()


def _filhos_de_mao_de_obra(t):
    return (GestaoCustoFilho.query
            .join(GestaoCustoPai, GestaoCustoFilho.pai_id == GestaoCustoPai.id)
            .filter(GestaoCustoFilho.admin_id == t.admin_id,
                    GestaoCustoFilho.data_referencia == DATA,
                    GestaoCustoPai.entidade_id == t.funcionario_id,
                    GestaoCustoPai.tipo_categoria.in_(['SALARIO',
                                                       'MAO_OBRA_DIRETA']))
            .all())


# ---------------------------------------------------------------------------
# Step D
# ---------------------------------------------------------------------------

def test_dia_com_ponto_e_rdo_nao_gera_dois_custos_de_obra(_par):
    """O caso do mundo real: bate ponto durante o dia, RDO fechado à noite."""
    a, _b = _par
    _limpar_custos(a)

    # O arreio já semeia um RegistroPonto do dia; o custo dele vem do handler.
    assert RegistroPonto.query.filter_by(
        funcionario_id=a.funcionario_id, data=DATA,
        admin_id=a.admin_id).first() is not None

    rdo = _rdo_com_mao_de_obra(a)
    _emitir_rdo_finalizado(a, rdo)

    custos = _custos_do_dia(a)
    assert len(custos) <= 1, (
        f'{len(custos)} custos para o mesmo (funcionário, dia) — o RDO voltou '
        f'a lançar por cima do ponto')


def test_o_ledger_de_gestao_de_custos_tambem_conta_uma_vez(_par):
    """A dupla contagem tinha dois andares: `CustoObra` e `GestaoCustoFilho`,
    com dedups que não se cruzavam em nenhum dos dois."""
    a, _b = _par
    _limpar_custos(a)

    rdo = _rdo_com_mao_de_obra(a)
    _emitir_rdo_finalizado(a, rdo)
    _emitir_rdo_finalizado(a, rdo)  # reexecução: idempotência

    filhos = _filhos_de_mao_de_obra(a)
    assert len(filhos) <= 1, (
        f'{len(filhos)} lançamentos de mão de obra no mesmo dia para o mesmo '
        f'funcionário')


def test_a_deduplicacao_nao_atravessa_tenants(_par):
    """Deduplicar por (entidade, data) sem `admin_id` na chave silenciaria o
    custo do outro tenant — o erro oposto, e pior."""
    a, b = _par
    _limpar_custos(a)
    _limpar_custos(b)

    rdo_b = _rdo_com_mao_de_obra(b)
    _emitir_rdo_finalizado(b, rdo_b)

    for filho in _filhos_de_mao_de_obra(b):
        assert filho.admin_id == b.admin_id


# ---------------------------------------------------------------------------
# Step E
# ---------------------------------------------------------------------------

def test_os_tres_caminhos_emitem_o_evento_em_vez_de_chamar_o_servico():
    """Chamada direta a `gerar_custos_mao_obra_rdo` gera custo e pula
    `recalcular_medicao_apos_rdo` — custo sem medição correspondente."""
    import re

    for arquivo in ('rdo_editar_sistema.py', 'crud_rdo_completo.py'):
        with open(arquivo, encoding='utf-8') as fh:
            texto = fh.read()
        chamadas = re.findall(r'^\s*gerar_custos_mao_obra_rdo\(', texto,
                              re.MULTILINE)
        assert not chamadas, (
            f'{arquivo} voltou a chamar gerar_custos_mao_obra_rdo direto '
            f'({len(chamadas)}x) — custo sem recálculo de medição')
        assert "EventManager.emit('rdo_finalizado'" in texto, (
            f'{arquivo} não emite rdo_finalizado')


def test_o_evento_tem_os_dois_ouvintes_que_o_justificam():
    """Se um dia sobrar só o handler de custo, o Step E perde o sentido."""
    from event_manager import EventManager

    handlers = {h.__name__ for h in
                EventManager._handlers.get('rdo_finalizado', [])}
    assert 'lancar_custos_rdo' in handlers
    assert 'recalcular_medicao_apos_rdo' in handlers
