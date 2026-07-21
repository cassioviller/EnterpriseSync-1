"""
Testes unitários de services/cronograma_apontamento_service.registrar_apontamento
(Módulo 1 — plano cronograma-mpp, passo 2/8).

Chamam o serviço DIRETAMENTE (sem HTTP) contra o banco real e verificam a
mesma semântica congelada nos testes de caracterização:
  - modo quantitativo: acumulado anterior + dia → percentual com
    round(..., 2) e teto min(100.0, ...); fallback 0.0 sem quantidade_total;
  - modo percentual (contrato NOVO do M07): acumulado digitado vai para
    percentual_acumulado, incremento para percentual_incremento_dia,
    quantidade_executada_dia/quantidade_acumulada ficam 0.0 (quantidade
    nunca guarda percentual); retrocesso exige justificativa;
  - XOR obrigatório entre quantidade_dia e percentual_acumulado;
  - UPSERT por (rdo_id, tarefa_cronograma_id);
  - sem commit (caller comita).
"""
import os
import sys
from datetime import date, datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from werkzeug.security import generate_password_hash

from models import (
    Usuario, TipoUsuario, Cliente, Obra,
    TarefaCronograma, RDO, RDOApontamentoCronograma,
)
from services.cronograma_apontamento_service import registrar_apontamento

pytestmark = pytest.mark.integration

D0 = date(2026, 6, 15)


def _suffix() -> str:
    return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')


@pytest.fixture()
def ctx():
    """App context + cenário mínimo (admin V2, obra). Rollback ao final."""
    with app.app_context():
        suf = _suffix()
        admin = Usuario(
            username=f'svc_apont_{suf}',
            email=f'svc_apont_{suf}@test.local',
            nome='Service Apontamento',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True, versao_sistema='v2',
        )
        db.session.add(admin)
        db.session.flush()
        cliente = Cliente(
            admin_id=admin.id, nome=f'Cliente Svc {suf}',
            email=f'cli_svc_{suf}@test.local', telefone='11977776666',
        )
        db.session.add(cliente)
        db.session.flush()
        obra = Obra(
            nome=f'Obra Svc {suf}', codigo=f'SVC-{suf[:10]}',
            admin_id=admin.id, cliente_id=cliente.id,
            status='Em andamento', data_inicio=D0 - timedelta(days=60),
        )
        db.session.add(obra)
        db.session.commit()
        yield {'admin_id': admin.id, 'obra_id': obra.id}
        db.session.rollback()


def _tarefa(ctx, *, quantidade_total, com_datas=True):
    t = TarefaCronograma(
        obra_id=ctx['obra_id'], admin_id=ctx['admin_id'],
        nome_tarefa=f'Tarefa Svc {_suffix()}', ordem=1,
        quantidade_total=quantidade_total, responsavel='empresa',
        duracao_dias=10 if com_datas else 1,
        data_inicio=(D0 - timedelta(days=30)) if com_datas else None,
        data_fim=(D0 - timedelta(days=20)) if com_datas else None,
    )
    db.session.add(t)
    db.session.commit()
    return t


def _rdo(ctx, data_rdo):
    r = RDO(
        numero_rdo=f'RS-{_suffix()[4:]}'[:20],
        obra_id=ctx['obra_id'], admin_id=ctx['admin_id'],
        data_relatorio=data_rdo, local='Campo', status='Finalizado',
    )
    db.session.add(r)
    db.session.commit()
    return r


def test_xor_obrigatorio(ctx):
    tarefa = _tarefa(ctx, quantidade_total=100.0)
    rdo = _rdo(ctx, D0)
    with pytest.raises(ValueError):
        registrar_apontamento(rdo, tarefa, admin_id=ctx['admin_id'])
    with pytest.raises(ValueError):
        registrar_apontamento(
            rdo, tarefa, quantidade_dia=1.0, percentual_acumulado=10.0,
            admin_id=ctx['admin_id'],
        )


def test_quantitativo_acumula_e_percentual(ctx):
    """Mesmos valores congelados na caracterização: 50/200 → 25.0;
    +30 → acum 80, 40.0. Planejado 100.0 (data_fim no passado)."""
    tarefa = _tarefa(ctx, quantidade_total=200.0)
    rdo1 = _rdo(ctx, D0)
    rdo2 = _rdo(ctx, D0 + timedelta(days=1))

    ap1 = registrar_apontamento(rdo1, tarefa, quantidade_dia=50.0,
                                admin_id=ctx['admin_id'])
    db.session.commit()
    assert ap1.quantidade_executada_dia == 50.0
    assert ap1.quantidade_acumulada == 50.0
    assert ap1.percentual_realizado == 25.0
    assert ap1.percentual_planejado == 100.0

    ap2 = registrar_apontamento(rdo2, tarefa, quantidade_dia=30.0,
                                admin_id=ctx['admin_id'])
    db.session.commit()
    assert ap2.quantidade_acumulada == 80.0
    assert ap2.percentual_realizado == 40.0
    # Invariante: incremento = diferença de acumulados
    assert ap2.quantidade_acumulada - ap1.quantidade_acumulada == ap2.quantidade_executada_dia


def test_quantitativo_arredondamento_e_teto(ctx):
    """1/3 → 33.33; 2/3 → 66.67; acima do total → teto 100.0."""
    tarefa = _tarefa(ctx, quantidade_total=3.0)
    valores = []
    for i, qty in enumerate([1.0, 1.0, 5.0]):
        rdo = _rdo(ctx, D0 + timedelta(days=i))
        ap = registrar_apontamento(rdo, tarefa, quantidade_dia=qty,
                                   admin_id=ctx['admin_id'])
        db.session.commit()
        valores.append((ap.quantidade_acumulada, ap.percentual_realizado))
    assert valores == [(1.0, 33.33), (2.0, 66.67), (7.0, 100.0)]


def test_quantitativo_fallback_sem_quantidade_total(ctx):
    """Sem quantidade_total: quantidade acumula, percentual_realizado 0.0,
    planejado None (sem plano calculável)."""
    tarefa = _tarefa(ctx, quantidade_total=None, com_datas=False)
    rdo = _rdo(ctx, D0)
    ap = registrar_apontamento(rdo, tarefa, quantidade_dia=5.0,
                               admin_id=ctx['admin_id'])
    db.session.commit()
    assert ap.quantidade_acumulada == 5.0
    assert ap.percentual_realizado == 0.0
    assert ap.percentual_planejado is None


def test_percentual_semantica_m02_e_retrocesso(ctx):
    """Contrato NOVO do M07: acumulado digitado → percentual_acumulado;
    incremento → percentual_incremento_dia; campos de quantidade ficam
    0.0 (quantidade nunca guarda percentual). Retrocesso sem justificativa
    é bloqueado; com permitir_retrocesso+justificativa grava incremento
    negativo."""
    from services.cronograma_apontamento_service import RetrocessoNaoPermitido

    tarefa = _tarefa(ctx, quantidade_total=None, com_datas=False)
    rdo1 = _rdo(ctx, D0)
    rdo2 = _rdo(ctx, D0 + timedelta(days=1))
    rdo3 = _rdo(ctx, D0 + timedelta(days=2))

    ap1 = registrar_apontamento(rdo1, tarefa, percentual_acumulado=10.0,
                                admin_id=ctx['admin_id'])
    db.session.commit()
    assert ap1.tipo_apontamento == 'percentual'
    assert ap1.quantidade_executada_dia == 0.0    # fim do abuso
    assert ap1.quantidade_acumulada == 0.0
    assert ap1.percentual_acumulado == 10.0
    assert ap1.percentual_incremento_dia == 10.0  # 10 - 0
    assert ap1.percentual_realizado == 10.0
    assert ap1.percentual_planejado is None

    ap2 = registrar_apontamento(rdo2, tarefa, percentual_acumulado=25.5,
                                admin_id=ctx['admin_id'])
    db.session.commit()
    assert ap2.percentual_acumulado == 25.5
    assert ap2.percentual_incremento_dia == 15.5  # 25.5 - 10
    assert ap2.percentual_realizado == 25.5

    # Regressão sem justificativa: bloqueada (nada gravado).
    with pytest.raises(RetrocessoNaoPermitido):
        registrar_apontamento(rdo3, tarefa, percentual_acumulado=20.0,
                              admin_id=ctx['admin_id'])
    db.session.rollback()

    # Correção justificada: incremento NEGATIVO explícito.
    ap3 = registrar_apontamento(
        rdo3, tarefa, percentual_acumulado=20.0, admin_id=ctx['admin_id'],
        permitir_retrocesso=True, justificativa='medição refeita em campo')
    db.session.commit()
    assert ap3.percentual_acumulado == 20.0
    assert ap3.percentual_incremento_dia == -5.5  # 20 - 25.5
    assert ap3.percentual_realizado == 20.0


def test_upsert_mesmo_rdo(ctx):
    """Segunda chamada para o mesmo RDO+tarefa atualiza a MESMA linha
    (semântica de apontar_producao)."""
    tarefa = _tarefa(ctx, quantidade_total=100.0)
    rdo = _rdo(ctx, D0)

    ap1 = registrar_apontamento(rdo, tarefa, quantidade_dia=20.0,
                                admin_id=ctx['admin_id'])
    db.session.commit()
    id1 = ap1.id
    ap2 = registrar_apontamento(rdo, tarefa, quantidade_dia=35.0,
                                admin_id=ctx['admin_id'])
    db.session.commit()
    assert ap2.id == id1
    n = RDOApontamentoCronograma.query.filter_by(
        rdo_id=rdo.id, tarefa_cronograma_id=tarefa.id).count()
    assert n == 1
    assert ap2.quantidade_executada_dia == 35.0
    assert ap2.quantidade_acumulada == 35.0
    assert ap2.percentual_realizado == 35.0


def test_sem_commit_do_servico(ctx):
    """O serviço NÃO comita — o apontamento fica pendente na sessão até o
    caller comitar (rollback descarta)."""
    tarefa = _tarefa(ctx, quantidade_total=100.0)
    rdo = _rdo(ctx, D0)

    registrar_apontamento(rdo, tarefa, quantidade_dia=10.0,
                          admin_id=ctx['admin_id'])
    db.session.rollback()
    n = RDOApontamentoCronograma.query.filter_by(
        rdo_id=rdo.id, tarefa_cronograma_id=tarefa.id).count()
    assert n == 0
