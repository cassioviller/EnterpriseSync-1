"""RDO em porcentagem livre — flag `configuracao_empresa.rdo_percentual_livre`.

Spec: `docs/superpowers/specs/2026-07-24-rdo-percentual-livre-design.md`.
Plano: `docs/superpowers/plans/2026-07-24-rdo-percentual-livre-plano.md`.

Com a flag LIGADA, toda tarefa de toda obra do tenant é apontada em
percentual acumulado: o quantitativo cadastrado vira referência de leitura e
`percentual_concluido` passa a sair do `percentual_realizado` do apontamento
mais recente, em vez de `quantidade_acumulada / quantidade_total`.

Dois eixos são igualmente importantes aqui:

  - **flag ligada** faz o que a spec pede (resolvedor, derivação, contrato
    HTTP, validações preservadas);
  - **flag desligada** não muda NADA — os testes de byte-identidade abaixo
    são o que autoriza subir isto em produção antes de ligar a flag em
    qualquer tenant.
"""
import os
import sys
import uuid
from datetime import date, timedelta

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import (
    RDO, Cliente, ConfiguracaoEmpresa, Obra, TarefaCronograma, TipoUsuario,
    Usuario,
)
from services.cronograma_apontamento_service import (
    MarcoApenasZeroOuCem,
    ModoIncompativel,
    RetrocessoNaoPermitido,
    SobreexecucaoNaoConfirmada,
    modo_da_tarefa,
    registrar_apontamento,
)
from utils.cronograma_engine import (
    atualizar_percentual_tarefa,
    calcular_progresso_geral_obra_v2,
    calcular_progresso_rdo,
    sincronizar_percentuais_obra,
)

pytestmark = pytest.mark.integration

D0 = date(2026, 6, 15)


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-rdo-percentual-livre'
    yield


def _suf() -> str:
    return uuid.uuid4().hex[:10]


@pytest.fixture()
def ctx():
    """Admin V2 + cliente + obra + ConfiguracaoEmpresa com a flag DESLIGADA.

    A configuração nasce explícita (e não ausente) porque é o estado de todo
    tenant real; `ligar_flag`/`desligar_flag` abaixo mexem só na coluna.
    """
    with app.app_context():
        suf = _suf()
        admin = Usuario(
            username=f'pctlivre_{suf}', email=f'pctlivre_{suf}@test.local',
            nome='RDO Percentual Livre',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
        )
        db.session.add(admin)
        db.session.flush()
        db.session.add(ConfiguracaoEmpresa(
            admin_id=admin.id, nome_empresa=f'Empresa PL {suf}',
            rdo_percentual_livre=False,
        ))
        cliente = Cliente(admin_id=admin.id, nome=f'Cliente PL {suf}',
                          email=f'cli_pl_{suf}@test.local',
                          telefone='11977776666')
        db.session.add(cliente)
        db.session.flush()
        obra = Obra(
            nome=f'Obra PL {suf}', codigo=f'PL-{suf[:8].upper()}',
            admin_id=admin.id, cliente_id=cliente.id,
            status='Em andamento', data_inicio=D0 - timedelta(days=60),
        )
        db.session.add(obra)
        db.session.commit()
        yield {'admin_id': admin.id, 'obra_id': obra.id}


def _flag(admin_id, ativo):
    from scripts.flag_rdo_percentual_livre import definir_flag
    return definir_flag(admin_id, ativo)


def _tarefa(ctx, **kw):
    t = TarefaCronograma(
        obra_id=ctx['obra_id'], admin_id=ctx['admin_id'],
        nome_tarefa=f'Tarefa PL {_suf()}', ordem=kw.pop('ordem', 1),
        responsavel=kw.pop('responsavel', 'empresa'),
        duracao_dias=kw.pop('duracao_dias', 10),
        data_inicio=kw.pop('data_inicio', D0 - timedelta(days=30)),
        data_fim=kw.pop('data_fim', D0 - timedelta(days=20)),
        **kw,
    )
    db.session.add(t)
    db.session.commit()
    return t


def _rdo(ctx, data_rdo):
    r = RDO(
        numero_rdo=f'PL-{_suf()}'[:20],
        obra_id=ctx['obra_id'], admin_id=ctx['admin_id'],
        data_relatorio=data_rdo, local='Campo', status='Finalizado',
    )
    db.session.add(r)
    db.session.commit()
    return r


def _cliente_http(admin_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(admin_id)
        sess['_fresh'] = True
    return c


# ---------------------------------------------------------------------------
# 0 — a flag em si
# ---------------------------------------------------------------------------

def test_coluna_existe_e_nasce_desligada(ctx):
    with app.app_context():
        config = ConfiguracaoEmpresa.query.filter_by(
            admin_id=ctx['admin_id']).first()
        assert config.rdo_percentual_livre is False


def test_script_liga_e_desliga(ctx):
    from scripts.flag_rdo_percentual_livre import status_flag

    with app.app_context():
        assert _flag(ctx['admin_id'], True) is True
        assert status_flag(ctx['admin_id'])['rdo_percentual_livre'] is True
        assert _flag(ctx['admin_id'], False) is False
        assert status_flag(ctx['admin_id'])['rdo_percentual_livre'] is False


def test_helper_falha_segura_sem_tenant():
    """Lido em laço de render: sem admin_id resolvido, devolve False."""
    from utils.tenant import rdo_percentual_livre_on

    with app.app_context():
        assert rdo_percentual_livre_on(None) is False
        assert rdo_percentual_livre_on(0) is False


# ---------------------------------------------------------------------------
# 1 — resolvedor de modo
# ---------------------------------------------------------------------------

def test_flag_on_tudo_e_percentual(ctx):
    """Inclusive tarefa com quantitativo E com escolha explícita 'quantidade'.

    A migração 221 congelou 'quantidade' na maioria das tarefas existentes:
    se a escolha explícita vencesse a flag, ligá-la não mudaria quase nada.
    """
    with app.app_context():
        quant = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')
        explicita = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                            modo_apontamento='quantidade')
        sem_qtd = _tarefa(ctx, quantidade_total=None)
        marco = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                        is_marco=True, duracao_dias=0)

        _flag(ctx['admin_id'], True)
        assert modo_da_tarefa(quant) == 'percentual'
        assert modo_da_tarefa(explicita) == 'percentual'
        assert modo_da_tarefa(sem_qtd) == 'percentual'
        assert modo_da_tarefa(marco) == 'percentual'


def test_flag_off_mantem_deducao_e_escolha(ctx):
    """Caracterização: com a flag desligada o resolvedor é o de sempre."""
    with app.app_context():
        quant = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')
        explicita = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                            modo_apontamento='percentual')
        sem_unidade = _tarefa(ctx, quantidade_total=100.0, unidade_medida=None)
        sem_qtd = _tarefa(ctx, quantidade_total=None)
        marco = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                        is_marco=True, duracao_dias=0)

        assert modo_da_tarefa(quant) == 'quantidade'
        assert modo_da_tarefa(explicita) == 'percentual'
        assert modo_da_tarefa(sem_unidade) == 'percentual'
        assert modo_da_tarefa(sem_qtd) == 'percentual'
        assert modo_da_tarefa(marco) == 'percentual'


def test_flag_nao_reescreve_a_coluna(ctx):
    """Reversibilidade: desligar a flag devolve o modo escolhido."""
    with app.app_context():
        t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                    modo_apontamento='quantidade')
        _flag(ctx['admin_id'], True)
        assert modo_da_tarefa(t) == 'percentual'

        _flag(ctx['admin_id'], False)
        db.session.expire_all()
        t = db.session.get(TarefaCronograma, t.id)
        assert t.modo_apontamento == 'quantidade'
        assert modo_da_tarefa(t) == 'quantidade'


def test_resolvedor_aceita_flag_pre_resolvida(ctx):
    """O laço da tela passa o booleano para não consultar por tarefa."""
    with app.app_context():
        t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')
        assert modo_da_tarefa(t, True) == 'percentual'
        assert modo_da_tarefa(t, False) == 'quantidade'


# ---------------------------------------------------------------------------
# 2 — apontamento: a tarefa quantitativa passa a aceitar %
# ---------------------------------------------------------------------------

def test_flag_on_aceita_percentual_em_tarefa_com_modo_quantidade(ctx):
    """Sem isto a flag seria inútil: a 221 marcou quase tudo 'quantidade'.

    O guard ModoIncompativel lia a coluna direto; com a flag ligada ele
    precisa seguir o resolvedor.
    """
    with app.app_context():
        t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                    modo_apontamento='quantidade')
        _flag(ctx['admin_id'], True)
        ap = registrar_apontamento(_rdo(ctx, D0), t, percentual_acumulado=40.0,
                                   admin_id=ctx['admin_id'])
        db.session.commit()
        assert ap.tipo_apontamento == 'percentual'
        assert ap.percentual_realizado == 40.0
        # Dupla escrita do modo percentual: quantidade nunca guarda %.
        assert ap.quantidade_executada_dia == 0.0
        assert ap.quantidade_acumulada == 0.0


def test_flag_on_recusa_apontamento_por_quantidade(ctx):
    with app.app_context():
        t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')
        _flag(ctx['admin_id'], True)
        with pytest.raises(ModoIncompativel):
            registrar_apontamento(_rdo(ctx, D0), t, quantidade_dia=10.0,
                                  admin_id=ctx['admin_id'])


def test_flag_off_mantem_guard_pela_coluna(ctx):
    """Caracterização do guard atual (Decisão D3 do plano do M07)."""
    with app.app_context():
        t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                    modo_apontamento='quantidade')
        with pytest.raises(ModoIncompativel):
            registrar_apontamento(_rdo(ctx, D0), t, percentual_acumulado=40.0,
                                  admin_id=ctx['admin_id'])


# ---------------------------------------------------------------------------
# 3 — derivação: continuidade e a regressão do bug atual
# ---------------------------------------------------------------------------

def test_continuidade_ao_ligar_a_flag(ctx):
    """Tarefa em 62% por quantidade continua em 62% no instante do rollout.

    É a dupla escrita que garante isto: a linha quantitativa já gravou
    `percentual_realizado=62`.
    """
    with app.app_context():
        t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')
        registrar_apontamento(_rdo(ctx, D0), t, quantidade_dia=62.0,
                              admin_id=ctx['admin_id'])
        db.session.commit()
        atualizar_percentual_tarefa(t.id, ctx['admin_id'])
        db.session.expire_all()
        assert db.session.get(TarefaCronograma, t.id).percentual_concluido == 62.0

        _flag(ctx['admin_id'], True)
        sincronizar_percentuais_obra(ctx['obra_id'], ctx['admin_id'])
        db.session.expire_all()
        assert db.session.get(TarefaCronograma, t.id).percentual_concluido == 62.0
        assert calcular_progresso_rdo(
            t.id, D0, ctx['admin_id'])['percentual_realizado'] == 62.0


def test_proximo_apontamento_percentual_avanca(ctx):
    """Depois da continuidade, o % digitado é que manda."""
    with app.app_context():
        t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')
        registrar_apontamento(_rdo(ctx, D0), t, quantidade_dia=62.0,
                              admin_id=ctx['admin_id'])
        db.session.commit()

        _flag(ctx['admin_id'], True)
        registrar_apontamento(_rdo(ctx, D0 + timedelta(days=1)), t,
                              percentual_acumulado=70.0,
                              admin_id=ctx['admin_id'])
        db.session.commit()
        atualizar_percentual_tarefa(t.id, ctx['admin_id'])
        db.session.expire_all()
        assert db.session.get(TarefaCronograma, t.id).percentual_concluido == 70.0


def test_regressao_percentual_em_tarefa_com_quantitativo(ctx):
    """O bug que motivou a spec: mostrava 0%, não o % digitado.

    Tarefa com `quantidade_total > 0` apontada em % grava quantidades 0.0; a
    derivação por `0/total` recalculava 0%. Com a flag ligada, a derivação é
    percentual-first e o número digitado sobrevive.
    """
    with app.app_context():
        t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')
        _flag(ctx['admin_id'], True)
        registrar_apontamento(_rdo(ctx, D0), t, percentual_acumulado=35.0,
                              admin_id=ctx['admin_id'])
        db.session.commit()

        atualizar_percentual_tarefa(t.id, ctx['admin_id'])
        db.session.expire_all()
        assert db.session.get(TarefaCronograma, t.id).percentual_concluido == 35.0

        sincronizar_percentuais_obra(ctx['obra_id'], ctx['admin_id'])
        db.session.expire_all()
        assert db.session.get(TarefaCronograma, t.id).percentual_concluido == 35.0

        assert calcular_progresso_rdo(
            t.id, D0, ctx['admin_id'])['percentual_realizado'] == 35.0


def test_flag_off_deriva_por_quantidade(ctx):
    """Byte-identidade: sem a flag, quantitativa continua derivando de qtd."""
    with app.app_context():
        t = _tarefa(ctx, quantidade_total=200.0, unidade_medida='m2')
        registrar_apontamento(_rdo(ctx, D0), t, quantidade_dia=50.0,
                              admin_id=ctx['admin_id'])
        db.session.commit()

        atualizar_percentual_tarefa(t.id, ctx['admin_id'])
        sincronizar_percentuais_obra(ctx['obra_id'], ctx['admin_id'])
        db.session.expire_all()
        assert db.session.get(TarefaCronograma, t.id).percentual_concluido == 25.0
        assert calcular_progresso_rdo(
            t.id, D0, ctx['admin_id'])['percentual_realizado'] == 25.0


def test_terceiros_continua_manual_com_a_flag(ctx):
    """Carve-out preservado: sync do RDO não sobrescreve tarefa de terceiros."""
    with app.app_context():
        t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2',
                    responsavel='terceiros')
        t.percentual_concluido = 100.0
        db.session.commit()

        _flag(ctx['admin_id'], True)
        sincronizar_percentuais_obra(ctx['obra_id'], ctx['admin_id'])
        db.session.expire_all()
        assert db.session.get(TarefaCronograma, t.id).percentual_concluido == 100.0


def _apontamento_sub(ctx, tarefa, rdo, quantidade):
    from models import RDOSubempreitadaApontamento, Subempreiteiro

    sub = Subempreiteiro(admin_id=ctx['admin_id'], nome=f'Sub PL {_suf()}')
    db.session.add(sub)
    db.session.flush()
    ap = RDOSubempreitadaApontamento(
        rdo_id=rdo.id, tarefa_cronograma_id=tarefa.id,
        subempreiteiro_id=sub.id, admin_id=ctx['admin_id'],
        qtd_pessoas=2, horas_trabalhadas=8.0, quantidade_produzida=quantidade,
    )
    db.session.add(ap)
    db.session.commit()
    return ap


def test_subempreitada_soma_ao_percentual_com_a_flag(ctx):
    """A sub reporta QUANTIDADE — mesmo com a flag, é o que ela produz.

    Sem a flag o rollup é `(acum_empresa + qtd_sub) / total`. Com a flag a
    parcela da empresa vira o % apontado e a da sub continua saindo do
    quantitativo; somadas, dão o mesmo tipo de número. Se a parcela da sub
    fosse simplesmente descartada, ligar a flag faria a obra andar para trás
    em toda tarefa com subempreitada.
    """
    with app.app_context():
        t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')
        rdo = _rdo(ctx, D0)
        _flag(ctx['admin_id'], True)
        registrar_apontamento(rdo, t, percentual_acumulado=30.0,
                              admin_id=ctx['admin_id'])
        db.session.commit()
        _apontamento_sub(ctx, t, rdo, 20.0)   # 20 de 100 = 20 pontos

        atualizar_percentual_tarefa(t.id, ctx['admin_id'])
        db.session.expire_all()
        assert db.session.get(TarefaCronograma, t.id).percentual_concluido == 50.0


def test_subempreitada_sem_total_e_ignorada_como_hoje(ctx):
    """Sem `quantidade_total` não há como converter quantidade em % —
    o ramo quantitativo já ignorava `qtd_sub` nesse caso."""
    with app.app_context():
        t = _tarefa(ctx, quantidade_total=None)
        rdo = _rdo(ctx, D0)
        _flag(ctx['admin_id'], True)
        registrar_apontamento(rdo, t, percentual_acumulado=30.0,
                              admin_id=ctx['admin_id'])
        db.session.commit()
        _apontamento_sub(ctx, t, rdo, 20.0)

        atualizar_percentual_tarefa(t.id, ctx['admin_id'])
        db.session.expire_all()
        assert db.session.get(TarefaCronograma, t.id).percentual_concluido == 30.0


# ---------------------------------------------------------------------------
# 4 — validações continuam idênticas com a flag ligada
# ---------------------------------------------------------------------------

def test_retrocesso_exige_justificativa_com_a_flag(ctx):
    with app.app_context():
        t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')
        _flag(ctx['admin_id'], True)
        registrar_apontamento(_rdo(ctx, D0), t, percentual_acumulado=50.0,
                              admin_id=ctx['admin_id'])
        db.session.commit()
        with pytest.raises(RetrocessoNaoPermitido):
            registrar_apontamento(_rdo(ctx, D0 + timedelta(days=1)), t,
                                  percentual_acumulado=30.0,
                                  admin_id=ctx['admin_id'])


def test_sobreexecucao_exige_confirmacao_com_a_flag(ctx):
    with app.app_context():
        t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')
        _flag(ctx['admin_id'], True)
        with pytest.raises(SobreexecucaoNaoConfirmada):
            registrar_apontamento(_rdo(ctx, D0), t, percentual_acumulado=105.0,
                                  admin_id=ctx['admin_id'])


def test_marco_binario_com_a_flag(ctx):
    with app.app_context():
        m = _tarefa(ctx, quantidade_total=None, is_marco=True, duracao_dias=0)
        _flag(ctx['admin_id'], True)
        with pytest.raises(MarcoApenasZeroOuCem):
            registrar_apontamento(_rdo(ctx, D0), m, percentual_acumulado=40.0,
                                  admin_id=ctx['admin_id'])
        ap = registrar_apontamento(_rdo(ctx, D0 + timedelta(days=1)), m,
                                   percentual_acumulado=100.0,
                                   admin_id=ctx['admin_id'])
        db.session.commit()
        assert ap.percentual_realizado == 100.0


# ---------------------------------------------------------------------------
# 5 — contrato HTTP de `tarefas-rdo` (o que a tela do RDO consome)
# ---------------------------------------------------------------------------

def test_tarefas_rdo_com_flag_on(ctx):
    with app.app_context():
        t = _tarefa(ctx, quantidade_total=150.0, unidade_medida='m3',
                    modo_apontamento='quantidade')
        _flag(ctx['admin_id'], True)
        oid, tid, aid = ctx['obra_id'], t.id, ctx['admin_id']

    resp = _cliente_http(aid).get(
        f'/cronograma/obra/{oid}/tarefas-rdo?data={D0.isoformat()}')
    assert resp.status_code == 200
    item = {i['id']: i for i in resp.get_json()['tarefas']}[tid]
    assert item['tipo_modo'] == 'percentual'
    assert item['saldo'] is None, 'saldo só existe no modo quantidade'
    # Quantitativo continua no payload — vira referência de leitura na tela.
    assert item['quantidade_total'] == 150.0
    assert item['unidade_medida'] == 'm3'
    # A coluna não foi reescrita: a UI do Gantt ainda vê a escolha original.
    assert item['modo_apontamento'] == 'quantidade'


def test_tarefas_rdo_com_flag_off(ctx):
    """Byte-identidade do contrato que a tela já consome hoje."""
    with app.app_context():
        t = _tarefa(ctx, quantidade_total=150.0, unidade_medida='m3')
        oid, tid, aid = ctx['obra_id'], t.id, ctx['admin_id']

    resp = _cliente_http(aid).get(
        f'/cronograma/obra/{oid}/tarefas-rdo?data={D0.isoformat()}')
    assert resp.status_code == 200
    item = {i['id']: i for i in resp.get_json()['tarefas']}[tid]
    assert item['tipo_modo'] == 'quantidade'
    assert item['saldo'] == 150.0


# ---------------------------------------------------------------------------
# 6 — agregado da obra
# ---------------------------------------------------------------------------

def test_n_tarefas_apontadas_conta_apontamento_percentual(ctx):
    """Subcontagem antiga: `quantidade_acumulada > 0` ignorava o % puro.

    Com a flag ligada a tarefa quantitativa cai no ramo percentual, que já
    sinaliza o apontamento para o agregado.
    """
    with app.app_context():
        t = _tarefa(ctx, quantidade_total=100.0, unidade_medida='m2')
        _flag(ctx['admin_id'], True)
        registrar_apontamento(_rdo(ctx, D0), t, percentual_acumulado=30.0,
                              admin_id=ctx['admin_id'])
        db.session.commit()

        agregado = calcular_progresso_geral_obra_v2(
            ctx['obra_id'], D0, ctx['admin_id'])
        assert agregado['n_tarefas_apontadas'] == 1
        assert agregado['progresso_geral_pct'] == 30.0


# ---------------------------------------------------------------------------
# 7 — guard do rollout (27/07): a flag não pode fazer obra perder físico
# ---------------------------------------------------------------------------

def _apontamento_legado(ctx, tarefa, data_rdo, acumulada, pct_realizado):
    """Grava a linha DIRETO no modelo, como os caminhos antigos faziam.

    É o formato que existe no banco antes da dupla escrita do M07: quantidade
    acumulada preenchida e `percentual_realizado` zerado. `registrar_apontamento`
    não consegue produzir isso — e é justamente essa linha que faz a tarefa
    despencar quando a flag liga.
    """
    from models import RDOApontamentoCronograma
    ap = RDOApontamentoCronograma(
        rdo_id=_rdo(ctx, data_rdo).id, tarefa_cronograma_id=tarefa.id,
        admin_id=ctx['admin_id'], quantidade_executada_dia=acumulada,
        quantidade_acumulada=acumulada, percentual_realizado=pct_realizado)
    db.session.add(ap)
    db.session.commit()
    return ap


def test_guard_detecta_tarefa_que_perderia_fisico(ctx):
    """A premissa de continuidade da entrega ("a linha quantitativa antiga já
    grava percentual_realizado") vale para o que o M07 escreve hoje, NÃO para
    toda linha legada. 🔬 27/07 em dev: 148 apontamentos com
    `quantidade_acumulada > 0` e `percentual_realizado = 0`, em 133 tarefas de
    84 tenants. Essas tarefas cairiam a 0% no instante em que a flag ligasse.
    """
    from scripts.flag_rdo_percentual_livre import tarefas_que_regridem

    with app.app_context():
        t = _tarefa(ctx, quantidade_total=48.0, unidade_medida='un')
        _apontamento_legado(ctx, t, D0, acumulada=24.0, pct_realizado=0.0)

        regressoes = tarefas_que_regridem(ctx['admin_id'])
        assert [r['tarefa_id'] for r in regressoes] == [t.id]
        assert regressoes[0]['pct_hoje'] == 50.0    # 24/48
        assert regressoes[0]['pct_apos'] == 0.0


def test_guard_ignora_tarefa_com_dupla_escrita_em_dia(ctx):
    """Linha escrita pelo serviço de apontamento tem os dois campos — a
    continuidade vale e a tarefa não pode aparecer no relatório do guard."""
    from scripts.flag_rdo_percentual_livre import tarefas_que_regridem

    with app.app_context():
        t = _tarefa(ctx, quantidade_total=48.0, unidade_medida='un')
        registrar_apontamento(_rdo(ctx, D0), t, quantidade_dia=24.0,
                              admin_id=ctx['admin_id'])
        db.session.commit()
        assert tarefas_que_regridem(ctx['admin_id']) == []


def test_cli_recusa_ligar_quando_ha_regressao_e_nao_grava(ctx):
    from scripts.flag_rdo_percentual_livre import main, status_flag

    with app.app_context():
        t = _tarefa(ctx, quantidade_total=48.0, unidade_medida='un')
        _apontamento_legado(ctx, t, D0, acumulada=24.0, pct_realizado=0.0)

    assert main([str(ctx['admin_id']), '--ligar']) == 1
    with app.app_context():
        # o ponto do guard: recusar ANTES de gravar. A versão anterior
        # chamava definir_flag e só depois avisava.
        assert status_flag(ctx['admin_id'])['rdo_percentual_livre'] is False


def test_cli_forcar_liga_mesmo_com_regressao(ctx):
    from scripts.flag_rdo_percentual_livre import main, status_flag

    with app.app_context():
        t = _tarefa(ctx, quantidade_total=48.0, unidade_medida='un')
        _apontamento_legado(ctx, t, D0, acumulada=24.0, pct_realizado=0.0)

    assert main([str(ctx['admin_id']), '--ligar', '--forcar']) == 0
    with app.app_context():
        assert status_flag(ctx['admin_id'])['rdo_percentual_livre'] is True


def test_cli_liga_sem_obstaculo_quando_nao_ha_regressao(ctx):
    from scripts.flag_rdo_percentual_livre import main, status_flag

    with app.app_context():
        t = _tarefa(ctx, quantidade_total=48.0, unidade_medida='un')
        registrar_apontamento(_rdo(ctx, D0), t, quantidade_dia=24.0,
                              admin_id=ctx['admin_id'])
        db.session.commit()

    assert main([str(ctx['admin_id']), '--ligar']) == 0
    with app.app_context():
        assert status_flag(ctx['admin_id'])['rdo_percentual_livre'] is True


def test_cli_status_nunca_grava(ctx):
    from scripts.flag_rdo_percentual_livre import main, status_flag

    assert main([str(ctx['admin_id']), '--status']) == 0
    with app.app_context():
        assert status_flag(ctx['admin_id'])['rdo_percentual_livre'] is False


def test_guard_nao_ve_tarefa_de_outro_tenant(ctx):
    """Índice por tenant: a regressão de um tenant não pode bloquear o rollout
    de outro."""
    from scripts.flag_rdo_percentual_livre import tarefas_que_regridem

    with app.app_context():
        t = _tarefa(ctx, quantidade_total=48.0, unidade_medida='un')
        _apontamento_legado(ctx, t, D0, acumulada=24.0, pct_realizado=0.0)
        assert tarefas_que_regridem(ctx['admin_id'] + 999_999) == []
