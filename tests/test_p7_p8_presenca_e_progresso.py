"""p7 e p8 — a batida real que era sobrescrita, e o elo que ninguém lia.

**p7.** `AllocationEmployee.sincronizar_com_ponto` reescrevia
`hora_entrada`, `hora_saida` e `obra_id` do registro EXISTENTE com o turno
PLANEJADO: o funcionário batia às 7h12 na obra A e o sync trocava por
08:00–17:00 na obra do plano. A medição do que aconteceu era substituída pela
previsão — sem rastro. E o ramo que criava registro novo estourava
IntegrityError (faltava `admin_id`, NOT NULL), então nunca criou nenhum.

Doutrina do pacote: **alocação = planejada, ponto = confirmada, RDO =
apontada.**

**p8.** `RDOServicoSubatividade.subatividade_mestre_id` e
`TarefaCronograma.subatividade_mestre_id` apontam para o mesmo catálogo — o
elo existe dos dois lados e **nunca era lido** para progresso. A medição caía
para `MAX(percentual_conclusao)` da linha do RDO, uma fonte diferente da que
o Gantt mostra.
"""
import os
import sys
from datetime import date, time
from decimal import Decimal
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import (Allocation, AllocationEmployee, RDO, RDOServicoSubatividade,
                    RegistroPonto, Servico, SubatividadeMestre,
                    TarefaCronograma)
from helpers_tenant import dois_tenants
from services.progresso_subatividade import (percentual_derivado,
                                             percentual_do_servico_na_obra,
                                             tarefa_da_subatividade)

pytestmark = pytest.mark.integration

DATA = date(2026, 6, 15)


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    if not app.secret_key:
        app.secret_key = 'test-p7-p8'
    with app.app_context():
        yield


def _tenant():
    a, _b = dois_tenants('p78', DATA)
    return a


# ---------------------------------------------------------------------------
# p7 — a batida real ganha do plano
# ---------------------------------------------------------------------------

def _alocacao(t, data=DATA):
    alloc = Allocation(obra_id=t.obra_id, admin_id=t.admin_id,
                       data_alocacao=data, local_trabalho='obra')
    db.session.add(alloc)
    db.session.flush()
    ae = AllocationEmployee(allocation_id=alloc.id,
                            funcionario_id=t.funcionario_id,
                            admin_id=t.admin_id,
                            turno_inicio=time(8, 0), turno_fim=time(17, 0))
    db.session.add(ae)
    db.session.commit()
    return ae


def test_sync_nao_sobrescreve_batida_real():
    """O caso que apagava dado: o registro do dia já tem batida."""
    t = _tenant()
    registro = RegistroPonto.query.filter_by(
        funcionario_id=t.funcionario_id, data=DATA,
        admin_id=t.admin_id).first()
    registro.hora_entrada = time(7, 12)
    registro.hora_saida = time(16, 30)
    db.session.commit()

    ae = _alocacao(t)
    assert ae.sincronizar_com_ponto() is True

    db.session.expire_all()
    registro = RegistroPonto.query.filter_by(
        funcionario_id=t.funcionario_id, data=DATA,
        admin_id=t.admin_id).first()
    assert registro.hora_entrada == time(7, 12), (
        'o plano sobrescreveu a batida real de entrada')
    assert registro.hora_saida == time(16, 30)


def test_sync_marca_como_sincronizado_mesmo_sem_escrever():
    """Não escrever não pode virar retentativa infinita a cada rodada."""
    t = _tenant()
    registro = RegistroPonto.query.filter_by(
        funcionario_id=t.funcionario_id, data=DATA,
        admin_id=t.admin_id).first()
    registro.hora_entrada = time(7, 12)
    db.session.commit()

    ae = _alocacao(t)
    ae.sincronizar_com_ponto()
    db.session.expire_all()
    assert db.session.get(AllocationEmployee, ae.id).sincronizado_ponto is True


def test_sync_cria_registro_com_admin_id():
    """O ramo de criação estourava NOT NULL — nunca criou um registro."""
    t = _tenant()
    for r in RegistroPonto.query.filter_by(funcionario_id=t.funcionario_id,
                                           data=DATA).all():
        db.session.delete(r)
    db.session.commit()

    ae = _alocacao(t)
    assert ae.sincronizar_com_ponto() is True

    db.session.expire_all()
    criado = RegistroPonto.query.filter_by(
        funcionario_id=t.funcionario_id, data=DATA).first()
    assert criado is not None, 'o sync continua sem conseguir criar registro'
    assert criado.admin_id == t.admin_id
    assert criado.hora_entrada == time(8, 0)


# ---------------------------------------------------------------------------
# p8 — o elo do catálogo passa a valer
# ---------------------------------------------------------------------------

def _servico(t):
    s = Servico(nome=f'Serviço {uuid4().hex[:6]}', admin_id=t.admin_id,
                ativo=True, unidade_medida='m2', categoria='estrutural')
    db.session.add(s)
    db.session.flush()
    return s


def _subatividade(t, servico):
    sm = SubatividadeMestre(nome=f'Sub {uuid4().hex[:6]}', servico_id=servico.id,
                            admin_id=t.admin_id, ativo=True)
    db.session.add(sm)
    db.session.flush()
    return sm


def _tarefa_ligada(t, sm, pct):
    tarefa = TarefaCronograma(
        obra_id=t.obra_id, admin_id=t.admin_id, nome_tarefa=sm.nome, ordem=0,
        duracao_dias=10, percentual_concluido=pct, ativa=True,
        is_cliente=False, subatividade_mestre_id=sm.id,
        data_inicio=DATA, data_fim=DATA)
    db.session.add(tarefa)
    db.session.commit()
    return tarefa


def _linha_rdo(t, servico, sm, pct, finalizado=True):
    rdo = RDO(numero_rdo=f'RDO-{uuid4().hex[:8]}', obra_id=t.obra_id,
              admin_id=t.admin_id, data_relatorio=DATA,
              criado_por_id=t.admin_id,
              status='Finalizado' if finalizado else 'Rascunho')
    db.session.add(rdo)
    db.session.flush()
    rss = RDOServicoSubatividade(
        rdo_id=rdo.id, admin_id=t.admin_id, servico_id=servico.id,
        nome_subatividade=sm.nome, percentual_conclusao=pct,
        subatividade_mestre_id=sm.id)
    db.session.add(rss)
    db.session.commit()
    return rss


def test_o_elo_do_catalogo_encontra_a_tarefa():
    t = _tenant()
    sm = _subatividade(t, _servico(t))
    tarefa = _tarefa_ligada(t, sm, 70)

    achada = tarefa_da_subatividade(sm.id, t.obra_id, t.admin_id)
    assert achada is not None and achada.id == tarefa.id


def test_percentual_vem_do_cronograma_quando_ha_elo():
    """A linha do RDO diz 40, a tarefa diz 70: o cronograma manda."""
    t = _tenant()
    servico = _servico(t)
    sm = _subatividade(t, servico)
    _tarefa_ligada(t, sm, 70)
    rss = _linha_rdo(t, servico, sm, 40)

    perc, origem = percentual_derivado(rss, t.obra_id, t.admin_id)
    assert origem == 'cronograma'
    assert perc == 70.0


def test_sem_elo_cai_no_valor_gravado():
    """Dado antigo não tem `subatividade_mestre_id` — e continua funcionando
    como antes."""
    t = _tenant()
    servico = _servico(t)
    sm = _subatividade(t, servico)
    rss = _linha_rdo(t, servico, sm, 40)
    rss.subatividade_mestre_id = None
    db.session.commit()

    perc, origem = percentual_derivado(rss, t.obra_id, t.admin_id)
    assert origem == 'linha'
    assert perc == 40.0


def test_medicao_e_gantt_passam_a_dizer_o_mesmo_numero():
    """O sintoma que motivou o p8: a medição caía para o MAX da linha do RDO,
    fonte diferente da que o Gantt mostra."""
    t = _tenant()
    servico = _servico(t)
    sm = _subatividade(t, servico)
    _tarefa_ligada(t, sm, 70)
    _linha_rdo(t, servico, sm, 40)

    assert percentual_do_servico_na_obra(
        servico.id, t.obra_id, t.admin_id) == 70.0


def test_servico_sem_linha_devolve_none():
    """`None` distingue "sem dado" de "zero por cento" — o chamador precisa
    dessa diferença para decidir se aplica fallback."""
    t = _tenant()
    servico = _servico(t)
    assert percentual_do_servico_na_obra(
        servico.id, t.obra_id, t.admin_id) is None


def test_rdo_nao_finalizado_nao_conta():
    t = _tenant()
    servico = _servico(t)
    sm = _subatividade(t, servico)
    _linha_rdo(t, servico, sm, 40, finalizado=False)

    assert percentual_do_servico_na_obra(
        servico.id, t.obra_id, t.admin_id) is None


def test_a_derivacao_nao_atravessa_tenants():
    a, b = dois_tenants('p78b', DATA)
    servico = Servico(nome=f'S {uuid4().hex[:6]}', admin_id=a.admin_id,
                      ativo=True, unidade_medida='m2', categoria='estrutural')
    db.session.add(servico)
    db.session.flush()
    sm = SubatividadeMestre(nome='Sub', servico_id=servico.id,
                            admin_id=a.admin_id, ativo=True)
    db.session.add(sm)
    db.session.commit()

    assert tarefa_da_subatividade(sm.id, b.obra_id, b.admin_id) is None
