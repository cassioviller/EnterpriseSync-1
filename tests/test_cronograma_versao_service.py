"""M05 Task 2 — aplicação transacional de versão de cronograma.

Os testes que mais importam (§17 do plano): RDOs/medições intactos após
aplicar (IDs preservados), assert anti-DELETE, transacionalidade (exceção
no meio ⇒ obra byte-idêntica), concorrência sequencial (2ª aplicação
falha limpa), tarefa arquivada fora da query da UI, pendência sem decisão
bloqueia, carga inicial de pct_project só sem RDO, fusão quantitativa.

O relatorio_diff é gerado pelo serviço REAL de reconciliação (Task 1) a
partir das tarefas vivas — o teste integra o M05 de ponta a ponta.
"""
import os
import sys
import uuid
from datetime import date, datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash

from app import app, db
from models import (
    Cliente,
    CronogramaImportacao,
    CronogramaImportacaoEvento,
    CronogramaTarefaSnapshot,
    CronogramaVersao,
    Obra,
    RDO,
    RDOApontamentoCronograma,
    TarefaCronograma,
    TipoUsuario,
    Usuario,
)
from services.cronograma_normalizacao import normalizar_nome
from services.cronograma_reconciliacao import reconciliar
from services.cronograma_versao_service import (
    AplicacaoVersaoError,
    DecisaoInvalida,
    EstadoInvalido,
    PendenciasSemDecisao,
    aplicar_versao,
)

pytestmark = pytest.mark.integration

SENHA = 'Senha@2026'


def _suf() -> str:
    return f'{datetime.utcnow().strftime("%H%M%S%f")}_{uuid.uuid4().hex[:6]}'


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-versao-cronograma'
    with app.app_context():
        yield


def _ambiente():
    """admin V2 + cliente + obra novos e isolados por sufixo."""
    suf = _suf()
    admin = Usuario(
        username=f'vs_{suf}',
        email=f'vs_{suf}@test.local',
        nome=f'Admin Versao {suf}',
        password_hash=generate_password_hash(SENHA),
        tipo_usuario=TipoUsuario.ADMIN,
        ativo=True,
        versao_sistema='v2',
    )
    db.session.add(admin)
    db.session.flush()
    cliente = Cliente(
        admin_id=admin.id,
        nome=f'Cliente {suf}',
        email=f'cli_{suf}@test.local',
        telefone='11988887777',
    )
    db.session.add(cliente)
    db.session.flush()
    obra = Obra(
        nome=f'Obra Versao {suf}',
        codigo=f'VS-{suf[:12]}',
        admin_id=admin.id,
        cliente_id=cliente.id,
        status='Em andamento',
        data_inicio=date(2026, 7, 1),
    )
    db.session.add(obra)
    db.session.commit()
    # M10: a área do M08 exige a flag de rollout ligada no tenant (default
    # FALSE desde a migração 211). Ambiente de teste = tenant já liberado.
    from scripts.flag_cronograma_mpp import definir_flag
    definir_flag(admin.id, True)
    return admin, obra


def _tarefa(obra, admin, nome, ordem=0, **kw):
    t = TarefaCronograma(
        obra_id=obra.id,
        admin_id=admin.id,
        nome_tarefa=nome,
        ordem=ordem,
        duracao_dias=kw.pop('duracao_dias', 5),
        data_inicio=kw.pop('data_inicio', date(2026, 7, 1)),
        data_fim=kw.pop('data_fim', date(2026, 7, 7)),
        is_cliente=False,
        **kw,
    )
    db.session.add(t)
    db.session.commit()
    return t


def _rdo_com_apontamento(obra, admin, tarefa, acumulada=40.0, pct=40.0):
    rdo = RDO(
        numero_rdo=f'RDO-{uuid.uuid4().hex[:12]}',
        data_relatorio=date(2026, 7, 10),
        obra_id=obra.id,
        admin_id=admin.id,
    )
    db.session.add(rdo)
    db.session.flush()
    ap = RDOApontamentoCronograma(
        rdo_id=rdo.id,
        tarefa_cronograma_id=tarefa.id,
        quantidade_executada_dia=acumulada,
        quantidade_acumulada=acumulada,
        percentual_realizado=pct,
        admin_id=admin.id,
    )
    db.session.add(ap)
    db.session.commit()
    return rdo, ap


# ---------------------------------------------------------------------------
# Ponte DB → serviços puros (Task 1) e normalizado sintético (M04)
# ---------------------------------------------------------------------------

def _extrair_atuais(obra, admin):
    """Extrai as tarefas VIVAS no shape TarefaAtual — pela ponte REAL de
    produção (extrair_tarefas_atuais), não uma cópia de teste."""
    from services.cronograma_versao_service import extrair_tarefas_atuais
    return extrair_tarefas_atuais(obra.id, admin.id)


def _nt(chave, nome, **kw):
    """Tarefa do json_normalizado (shape mínimo consumido pelo M05)."""
    nn = normalizar_nome(nome)
    n = {
        'chave': chave, 'uid': None, 'wbs': None,
        'nome_original': nome, 'nome_normalizado': nn, 'caminho': nn,
        'fingerprint': None, 'pai_chave': None, 'ordem': 0,
        'inicio': '2026-08-03', 'fim': '2026-08-07', 'dias': 5.0,
        'is_marco': False, 'predecessoras': [],
        'quantidade_total': None, 'unidade': None, 'pct_project': 0.0,
    }
    n.update(kw)
    return n


def _importacao_pronta(obra, admin, *tarefas_norm):
    """Cria a importação 'aguardando_revisao' com diff REAL da Task 1."""
    ts = list(tarefas_norm)
    for ordem, t in enumerate(ts):
        t['ordem'] = ordem
    normalizado = {'tarefas': ts}
    rel = reconciliar(_extrair_atuais(obra, admin), normalizado)
    imp = CronogramaImportacao(
        obra_id=obra.id,
        admin_id=admin.id,
        arquivo_nome='novo.xml',
        origem='upload_mspdi',
        status='aguardando_revisao',
        json_normalizado=normalizado,
        relatorio_diff=rel,
        criado_por_id=admin.id,
    )
    db.session.add(imp)
    db.session.commit()
    return imp, rel


def _estado_obra(obra):
    """Foto comparável (todas as colunas relevantes) das tarefas da obra."""
    rows = (TarefaCronograma.query
            .filter_by(obra_id=obra.id)
            .order_by(TarefaCronograma.id)
            .all())
    return [(t.id, t.nome_tarefa, t.ordem, t.duracao_dias, t.data_inicio,
             t.data_fim, t.quantidade_total, t.unidade_medida, t.mpp_uid,
             t.wbs_codigo, t.fingerprint, t.is_marco, t.ativa,
             t.arquivada_em, t.tarefa_pai_id, t.predecessora_id,
             t.percentual_concluido, t.versao_criacao_id) for t in rows]


# ---------------------------------------------------------------------------
# Preservação de RDOs, IDs e percentual (o teste que mais importa)
# ---------------------------------------------------------------------------

def test_aplicar_preserva_ids_apontamentos_e_percentual():
    admin, obra = _ambiente()
    t1 = _tarefa(obra, admin, 'Fundação', ordem=0, mpp_uid=1,
                 quantidade_total=100.0, unidade_medida='m2')
    t2 = _tarefa(obra, admin, 'Alvenaria', ordem=1, mpp_uid=2)
    _rdo_com_apontamento(obra, admin, t1, acumulada=40.0, pct=40.0)
    t1.percentual_concluido = 40.0
    db.session.commit()

    imp, rel = _importacao_pronta(
        obra, admin,
        _nt('uid:1', 'Fundação Radier', uid=1, pct_project=90.0),
        _nt('uid:2', 'Alvenaria', uid=2),
        _nt('uid:3', 'Cobertura', uid=3))
    assert rel['resumo']['novas'] == 1

    versao = aplicar_versao(imp.id, {}, admin.id)

    db.session.refresh(t1)
    db.session.refresh(t2)
    # IDs preservados, conteúdo atualizado in-place.
    assert t1.nome_tarefa == 'Fundação Radier'
    assert t1.ativa is True and t2.ativa is True
    # Apontamentos intactos (contagem + valores) e percentual vindo do RDO —
    # NUNCA do pct_project (a obra tem RDO).
    aps = RDOApontamentoCronograma.query.filter_by(
        tarefa_cronograma_id=t1.id).all()
    assert len(aps) == 1
    assert aps[0].quantidade_acumulada == 40.0
    assert t1.percentual_concluido == 40.0
    # Quantidade preenchida na UI não é apagada (M04 entrega None).
    assert t1.quantidade_total == 100.0
    assert t1.unidade_medida == 'm2'
    # Nova tarefa inserida com carimbo da versão.
    nova = TarefaCronograma.query.filter_by(
        obra_id=obra.id, nome_tarefa='Cobertura').one()
    assert nova.versao_criacao_id == versao.id
    assert nova.mpp_uid == 3
    imp = db.session.get(CronogramaImportacao, imp.id)
    assert imp.status == 'aplicado'
    assert imp.aplicado_em is not None


def test_removida_e_arquivada_nunca_deletada_e_some_da_ui():
    admin, obra = _ambiente()
    t1 = _tarefa(obra, admin, 'Estrutura', ordem=0, mpp_uid=1)
    t2 = _tarefa(obra, admin, 'Demolição Provisória', ordem=1, mpp_uid=2)
    _rdo_com_apontamento(obra, admin, t2, acumulada=10.0, pct=10.0)

    imp, rel = _importacao_pronta(obra, admin, _nt('uid:1', 'Estrutura', uid=1))
    assert rel['resumo']['removidas'] == 1

    aplicar_versao(imp.id, {}, admin.id)

    db.session.refresh(t2)
    assert t2.ativa is False
    assert t2.arquivada_em is not None
    # Anti-DELETE: a linha e os apontamentos continuam existindo.
    assert db.session.get(TarefaCronograma, t2.id) is not None
    assert RDOApontamentoCronograma.query.filter_by(
        tarefa_cronograma_id=t2.id).count() == 1

    # Query da UI (endpoint JSON do card de RDO) não devolve a arquivada.
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(admin.id)
        sess['_fresh'] = True
    resp = c.get(f'/cronograma/obra/{obra.id}/tarefas-rdo')
    assert resp.status_code == 200
    ids = {item['id'] for item in resp.get_json()['tarefas']}
    assert t1.id in ids
    assert t2.id not in ids


# ---------------------------------------------------------------------------
# Transacionalidade e concorrência
# ---------------------------------------------------------------------------

def test_excecao_no_meio_faz_rollback_total(monkeypatch):
    admin, obra = _ambiente()
    _tarefa(obra, admin, 'Fundação', ordem=0, mpp_uid=1)
    _tarefa(obra, admin, 'Alvenaria', ordem=1, mpp_uid=2)
    imp, _ = _importacao_pronta(
        obra, admin,
        _nt('uid:1', 'Fundação Nova', uid=1),
        _nt('uid:9', 'Tarefa Nova', uid=9))
    antes = _estado_obra(obra)

    # Explode no snapshot FINAL — depois de updates/inserts/arquivamentos.
    import services.cronograma_versao_service as svc

    def _boom(*a, **kw):
        raise RuntimeError('falha injetada')

    monkeypatch.setattr(svc, '_snapshot_versao', _boom)
    with pytest.raises(RuntimeError):
        aplicar_versao(imp.id, {}, admin.id)

    db.session.expire_all()
    assert _estado_obra(obra) == antes
    assert CronogramaVersao.query.filter_by(obra_id=obra.id).count() == 0
    imp = db.session.get(CronogramaImportacao, imp.id)
    assert imp.status == 'aguardando_revisao'


def test_segunda_aplicacao_falha_limpa():
    admin, obra = _ambiente()
    _tarefa(obra, admin, 'Fundação', ordem=0, mpp_uid=1)
    imp, _ = _importacao_pronta(obra, admin, _nt('uid:1', 'Fundação', uid=1))

    aplicar_versao(imp.id, {}, admin.id)
    with pytest.raises(EstadoInvalido):
        aplicar_versao(imp.id, {}, admin.id)
    # Continua havendo exatamente 1 versão ativa.
    assert CronogramaVersao.query.filter_by(
        obra_id=obra.id, status='ativa').count() == 1


def test_diff_desatualizado_e_rejeitado():
    admin, obra = _ambiente()
    _tarefa(obra, admin, 'Fundação', ordem=0, mpp_uid=1)
    imp, _ = _importacao_pronta(obra, admin, _nt('uid:1', 'Fundação', uid=1))
    # Tarefa criada DEPOIS da reconciliação: o diff não a conhece.
    _tarefa(obra, admin, 'Intrusa', ordem=9)
    with pytest.raises(EstadoInvalido):
        aplicar_versao(imp.id, {}, admin.id)


# ---------------------------------------------------------------------------
# Pendências e decisões
# ---------------------------------------------------------------------------

def test_ambigua_bloqueia_sem_decisao_e_casar_resolve():
    admin, obra = _ambiente()
    t1 = _tarefa(obra, admin, 'Pintura Interna', ordem=0,
                 data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 10),
                 duracao_dias=8)
    imp, rel = _importacao_pronta(
        obra, admin,
        _nt('n1', 'Pintura Interna 1',
            inicio='2026-07-01', fim='2026-07-10', dias=8.0),
        _nt('n2', 'Pintura Interna 2',
            inicio='2026-07-01', fim='2026-07-10', dias=8.0))
    assert rel['resumo']['ambiguas'] == 1
    pend = [m for m in rel['mapeamentos'] if m['decisao_requerida']]
    assert len(pend) == 1

    # Ambíguo NUNCA se auto-aplica: sem decisão ⇒ erro com os id_temp.
    with pytest.raises(PendenciasSemDecisao) as exc:
        aplicar_versao(imp.id, {}, admin.id)
    assert exc.value.id_temps == [pend[0]['id_temp']]

    versao = aplicar_versao(
        imp.id, {pend[0]['id_temp']: {'acao': 'casar', 'chave_nova': 'n1'}},
        admin.id)
    db.session.refresh(t1)
    assert t1.nome_tarefa == 'Pintura Interna 1'   # casada manualmente
    assert t1.ativa is True
    # n2 inserida; n1 NÃO inserida em duplicidade.
    nomes = [t.nome_tarefa for t in TarefaCronograma.query.filter_by(
        obra_id=obra.id, ativa=True).all()]
    assert sorted(nomes) == ['Pintura Interna 1', 'Pintura Interna 2']
    assert versao.status == 'ativa'


def test_decisoes_invalidas():
    admin, obra = _ambiente()
    _tarefa(obra, admin, 'Fundação', ordem=0, mpp_uid=1)
    imp, rel = _importacao_pronta(obra, admin, _nt('uid:1', 'Fundação', uid=1))
    auto = rel['mapeamentos'][0]
    assert not auto['decisao_requerida']

    # Decisão sobre mapeamento sem pendência.
    with pytest.raises(DecisaoInvalida):
        aplicar_versao(imp.id, {auto['id_temp']: {'acao': 'arquivar'}},
                       admin.id)
    imp = db.session.get(CronogramaImportacao, imp.id)
    assert imp.status == 'aguardando_revisao'


def test_casar_com_chave_inexistente_e_invalido():
    admin, obra = _ambiente()
    _tarefa(obra, admin, 'Pintura Interna', ordem=0,
            data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 10),
            duracao_dias=8)
    imp, rel = _importacao_pronta(
        obra, admin,
        _nt('n1', 'Pintura Interna 1',
            inicio='2026-07-01', fim='2026-07-10', dias=8.0),
        _nt('n2', 'Pintura Interna 2',
            inicio='2026-07-01', fim='2026-07-10', dias=8.0))
    pend = [m for m in rel['mapeamentos'] if m['decisao_requerida']][0]
    with pytest.raises(DecisaoInvalida):
        aplicar_versao(
            imp.id, {pend['id_temp']: {'acao': 'casar', 'chave_nova': 'zz'}},
            admin.id)


# ---------------------------------------------------------------------------
# Carga inicial de pct_project
# ---------------------------------------------------------------------------

def test_pct_project_carrega_somente_quando_obra_nunca_teve_rdo():
    # Obra SEM RDO: pct_project vira realizado inicial.
    admin, obra = _ambiente()
    t1 = _tarefa(obra, admin, 'Fundação', ordem=0, mpp_uid=1)
    imp, _ = _importacao_pronta(
        obra, admin, _nt('uid:1', 'Fundação', uid=1, pct_project=30.0))
    aplicar_versao(imp.id, {}, admin.id)
    db.session.refresh(t1)
    assert t1.percentual_concluido == 30.0

    # Obra COM RDO: pct_project ignorado; sync com apontamentos manda.
    admin2, obra2 = _ambiente()
    t2 = _tarefa(obra2, admin2, 'Fundação', ordem=0, mpp_uid=1)
    _rdo_com_apontamento(obra2, admin2, t2, acumulada=0.0, pct=15.0)
    imp2, _ = _importacao_pronta(
        obra2, admin2, _nt('uid:1', 'Fundação', uid=1, pct_project=95.0))
    aplicar_versao(imp2.id, {}, admin2.id)
    db.session.refresh(t2)
    assert t2.percentual_concluido == 15.0


# ---------------------------------------------------------------------------
# Fusão quantitativa
# ---------------------------------------------------------------------------

def test_fusao_confirmada_soma_quantidades_e_pondera_realizado():
    admin, obra = _ambiente()
    t20 = _tarefa(obra, admin, 'Piso Térreo', ordem=0,
                  quantidade_total=100.0, unidade_medida='m2')
    t21 = _tarefa(obra, admin, 'Piso Superior', ordem=1,
                  quantidade_total=100.0, unidade_medida='m2')
    t20.percentual_concluido = 50.0
    db.session.commit()

    imp, rel = _importacao_pronta(
        obra, admin,
        _nt('nf', 'Piso Térreo Superior Regularização Contrapiso'))
    fus = [s for s in rel['sugestoes_split_merge'] if s['tipo'] == 'fundida']
    assert fus and fus[0]['antigas_ids'] == sorted([t20.id, t21.id])

    decisoes = {m['id_temp']: ({'acao': 'arquivar'}
                               if m['tarefa_atual_id'] is not None
                               else {'acao': 'nova'})
                for m in rel['mapeamentos'] if m['decisao_requerida']}
    aplicar_versao(imp.id, decisoes, admin.id)

    db.session.refresh(t20)
    db.session.refresh(t21)
    assert t20.ativa is False and t21.ativa is False
    nova = TarefaCronograma.query.filter_by(obra_id=obra.id, ativa=True).one()
    assert nova.quantidade_total == 200.0
    assert nova.unidade_medida == 'm2'
    # 50 m2 executados de 200 ⇒ 25% (avanço físico não zera na fusão).
    assert nova.percentual_concluido == 25.0


# ---------------------------------------------------------------------------
# Versionamento, snapshots e hierarquia
# ---------------------------------------------------------------------------

def test_versiona_arquiva_anterior_e_fotografa_ambas():
    admin, obra = _ambiente()
    t1 = _tarefa(obra, admin, 'Fundação', ordem=0, mpp_uid=1)
    # Simula o backfill: versão nº1 ativa AINDA sem snapshots.
    v1 = CronogramaVersao(obra_id=obra.id, admin_id=admin.id, numero=1,
                          status='ativa', observacao='backfill inicial')
    db.session.add(v1)
    db.session.commit()

    imp, _ = _importacao_pronta(
        obra, admin,
        _nt('uid:1', 'Fundação Atualizada', uid=1),
        _nt('uid:2', 'Cobertura', uid=2))
    versao = aplicar_versao(imp.id, {}, admin.id)

    db.session.refresh(v1)
    assert v1.status == 'arquivada'
    assert versao.numero == 2
    assert versao.status == 'ativa'
    assert versao.importacao_id == imp.id
    # v1 ganhou snapshot do estado ANTIGO (nome antigo) na mesma transação.
    snaps_v1 = CronogramaTarefaSnapshot.query.filter_by(versao_id=v1.id).all()
    assert [s.nome_tarefa for s in snaps_v1] == ['Fundação']
    assert snaps_v1[0].tarefa_id == t1.id
    # A nova versão fotografa o estado aplicado.
    snaps_v2 = CronogramaTarefaSnapshot.query.filter_by(
        versao_id=versao.id).order_by(CronogramaTarefaSnapshot.ordem).all()
    assert [s.nome_tarefa for s in snaps_v2] == ['Fundação Atualizada',
                                                 'Cobertura']
    # Evento de auditoria com contadores de matching.
    ev = CronogramaImportacaoEvento.query.filter_by(
        importacao_id=imp.id, evento='aplicado').one()
    assert ev.detalhes['versao_numero'] == 2
    assert ev.detalhes['matching_por_nivel'].get('mpp_uid') == 1


def test_hierarquia_e_predecessora_primeira_fs():
    admin, obra = _ambiente()
    _tarefa(obra, admin, 'Estrutura', ordem=0, mpp_uid=1)
    imp, _ = _importacao_pronta(
        obra, admin,
        _nt('uid:1', 'Estrutura', uid=1),
        _nt('uid:2', 'Painéis', uid=2, pai_chave='uid:1'),
        _nt('uid:3', 'Montagem', uid=3, pai_chave='uid:1',
            predecessoras=[{'chave': 'uid:2', 'tipo': 'SS', 'lag_dias': 0},
                           {'chave': 'uid:2', 'tipo': 'FS', 'lag_dias': 2}]))
    aplicar_versao(imp.id, {}, admin.id)

    por_nome = {t.nome_tarefa: t for t in TarefaCronograma.query.filter_by(
        obra_id=obra.id, ativa=True).all()}
    estrutura = por_nome['Estrutura']
    paineis = por_nome['Painéis']
    montagem = por_nome['Montagem']
    assert paineis.tarefa_pai_id == estrutura.id
    assert montagem.tarefa_pai_id == estrutura.id
    # Primeira FS (não a SS) vira a predecessora única.
    assert montagem.predecessora_id == paineis.id
    # Snapshot da nova versão guarda a lista tipada completa.
    versao = CronogramaVersao.query.filter_by(
        obra_id=obra.id, status='ativa').one()
    snap = CronogramaTarefaSnapshot.query.filter_by(
        versao_id=versao.id, tarefa_id=montagem.id).one()
    tipos = [p['tipo'] for p in snap.predecessoras_json]
    assert tipos == ['SS', 'FS']
