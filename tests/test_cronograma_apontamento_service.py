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


def test_acumulado_anterior_ignora_linha_gravada_em_percentual(ctx):
    """`acum_ant` não pode somar PONTOS PERCENTUAIS como produção física.

    Este serviço nunca põe produção em linha percentual — grava 0.0 ali.
    Mas as linhas que vieram ANTES dele põem: as pré-M02 e as do import
    físico-financeiro guardam pp em `quantidade_executada_dia`. Sem o
    filtro por `tipo_apontamento`, a soma do acumulado anterior misturava
    pp com unidades e o apontamento quantitativo partia inflado.
    """
    tarefa = _tarefa(ctx, quantidade_total=200.0)
    rdo_legado = _rdo(ctx, D0)
    rdo_hoje = _rdo(ctx, D0 + timedelta(days=1))

    # linha legada em PERCENTUAL com pp na coluna de quantidade — a forma
    # que 79.334 das 121.918 linhas percentuais de dev têm
    db.session.add(RDOApontamentoCronograma(
        rdo_id=rdo_legado.id, tarefa_cronograma_id=tarefa.id,
        admin_id=ctx['admin_id'], tipo_apontamento='percentual',
        quantidade_executada_dia=60.0,   # 60 PONTOS PERCENTUAIS
        quantidade_acumulada=0.0, percentual_realizado=60.0,
        percentual_acumulado=60.0))
    db.session.commit()

    ap = registrar_apontamento(rdo_hoje, tarefa, quantidade_dia=50.0,
                               admin_id=ctx['admin_id'])
    db.session.flush()

    assert ap.quantidade_acumulada == 50.0, (
        f'os 60 pp da linha percentual entraram no acumulado físico: '
        f'{ap.quantidade_acumulada}')
    assert ap.percentual_realizado == 25.0, (
        f'50 de 200 é 25%, veio {ap.percentual_realizado}%')


def test_leitura_desempata_como_a_escrita_com_dois_rdos_no_mesmo_dia(ctx):
    """Dois RDOs na MESMA data apontando a mesma tarefa: quem vence?

    Não há unicidade de RDO por obra+data (conferido no schema; em dev há
    obras com 10 RDOs na mesma data). O lado da ESCRITA sempre desempatou
    por `(data_relatorio desc, id desc)` — `registrar_apontamento` usa
    isso para achar o percentual anterior. As leituras do motor ordenavam
    só por data, e aí a escolha ficava a cargo do banco: a mesma tarefa
    exibia um percentual ou outro, e `sincronizar_percentuais_obra`
    GRAVAVA o que saísse.

    A regra que este teste trava: vence o apontamento de maior id dentro
    da data máxima — em qualquer um dos caminhos de leitura.
    """
    from utils.cronograma_engine import (calcular_progresso_rdo,
                                         sincronizar_percentuais_obra,
                                         atualizar_percentual_tarefa)

    tarefa = _tarefa(ctx, quantidade_total=None)
    rdo_a = _rdo(ctx, D0)
    rdo_b = _rdo(ctx, D0)          # mesma data, id maior
    assert rdo_b.id > rdo_a.id

    for rdo, pct in ((rdo_a, 30.0), (rdo_b, 70.0)):
        db.session.add(RDOApontamentoCronograma(
            rdo_id=rdo.id, tarefa_cronograma_id=tarefa.id,
            admin_id=ctx['admin_id'], tipo_apontamento='percentual',
            quantidade_executada_dia=0.0, quantidade_acumulada=0.0,
            percentual_realizado=pct, percentual_acumulado=pct))
    db.session.commit()

    esperado = 70.0   # o de maior id dentro da data máxima

    # 1) leitura pontual
    assert calcular_progresso_rdo(
        tarefa.id, D0, ctx['admin_id'])['percentual_realizado'] == esperado

    # 2) leitura em lote, que GRAVA percentual_concluido
    sincronizar_percentuais_obra(ctx['obra_id'], ctx['admin_id'])
    db.session.refresh(tarefa)
    assert tarefa.percentual_concluido == esperado, (
        f'sincronizar gravou {tarefa.percentual_concluido}%')

    # 3) caminho unitário (empresa + subempreitada)
    tarefa.percentual_concluido = 0.0
    db.session.commit()
    atualizar_percentual_tarefa(tarefa.id, ctx['admin_id'])
    db.session.refresh(tarefa)
    assert tarefa.percentual_concluido == esperado

    # e é ESTÁVEL: repetir não muda a resposta
    assert calcular_progresso_rdo(
        tarefa.id, D0, ctx['admin_id'])['percentual_realizado'] == esperado


def test_bloqueia_quantitativo_em_tarefa_com_historico_em_percentual(ctx):
    """O avanço que o bloqueio protege — medido nos dois sentidos.

    Depois de 687db151 o passado não é mais reescrito: a tarefa segue em
    80% mesmo com um total cadastrado. O que continua em risco é o FUTURO
    — o primeiro apontamento quantitativo vira a linha mais recente, e a
    leitura passa a valer o que ela sozinha representa.
    """
    from utils.cronograma_engine import (
        calcular_progresso_rdo, impedimento_para_cadastrar_quantitativo)

    tarefa = _tarefa(ctx, quantidade_total=None)
    rdo1, rdo2 = _rdo(ctx, D0), _rdo(ctx, D0 + timedelta(days=1))
    for rdo, pct in ((rdo1, 60.0), (rdo2, 80.0)):
        db.session.add(RDOApontamentoCronograma(
            rdo_id=rdo.id, tarefa_cronograma_id=tarefa.id,
            admin_id=ctx['admin_id'], tipo_apontamento='percentual',
            quantidade_executada_dia=0.0, quantidade_acumulada=0.0,
            percentual_realizado=pct, percentual_acumulado=pct))
    db.session.commit()

    def avanco(ate):
        return calcular_progresso_rdo(
            tarefa.id, ate, ctx['admin_id'])['percentual_realizado']

    assert avanco(D0 + timedelta(days=10)) == 80.0

    # 1) a regra bloqueia
    msg = impedimento_para_cadastrar_quantitativo(tarefa, 200, ctx['admin_id'])
    assert msg and 'PERCENTUAL' in msg, msg

    # 2) o estrago que ela evita, medido: forçando o cadastro e apontando
    #    por quantidade, o avanço DESPENCA
    tarefa.quantidade_total = 200.0
    tarefa.unidade_medida = 'un'
    db.session.commit()
    rdo3 = _rdo(ctx, D0 + timedelta(days=2))
    registrar_apontamento(rdo3, tarefa, quantidade_dia=50.0,
                          admin_id=ctx['admin_id'])
    db.session.commit()
    assert avanco(D0 + timedelta(days=10)) == 25.0, (
        'o cenário que o bloqueio evita mudou — reveja a justificativa '
        'de impedimento_para_cadastrar_quantitativo')


def test_o_que_o_bloqueio_de_quantitativo_NAO_impede(ctx):
    """As três edições legítimas continuam livres."""
    from utils.cronograma_engine import impedimento_para_cadastrar_quantitativo

    # tarefa sem apontamento nenhum
    virgem = _tarefa(ctx, quantidade_total=None)
    assert impedimento_para_cadastrar_quantitativo(
        virgem, 48, ctx['admin_id']) is None

    # tarefa que JÁ é quantitativa: ajustar o total é o comportamento certo
    quantitativa = _tarefa(ctx, quantidade_total=100.0)
    rdo = _rdo(ctx, D0)
    registrar_apontamento(rdo, quantitativa, quantidade_dia=25.0,
                          admin_id=ctx['admin_id'])
    db.session.commit()
    assert impedimento_para_cadastrar_quantitativo(
        quantitativa, 50, ctx['admin_id']) is None

    # limpar o campo é sempre seguro
    pct = _tarefa(ctx, quantidade_total=None)
    rdo_p = _rdo(ctx, D0)
    db.session.add(RDOApontamentoCronograma(
        rdo_id=rdo_p.id, tarefa_cronograma_id=pct.id,
        admin_id=ctx['admin_id'], tipo_apontamento='percentual',
        quantidade_executada_dia=0.0, quantidade_acumulada=0.0,
        percentual_realizado=40.0, percentual_acumulado=40.0))
    db.session.commit()
    assert impedimento_para_cadastrar_quantitativo(
        pct, 0, ctx['admin_id']) is None
    assert impedimento_para_cadastrar_quantitativo(
        pct, None, ctx['admin_id']) is None
    # mas cadastrar um total nela, sim, é bloqueado
    assert impedimento_para_cadastrar_quantitativo(pct, 10, ctx['admin_id'])
