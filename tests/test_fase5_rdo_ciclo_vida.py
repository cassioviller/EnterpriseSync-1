"""Fase 5 — ciclo de vida do RDO.

Até esta fase o RDO nascia 'Finalizado' por decreto (`models.py:1112`,
comentário "Task #12: RDO sempre Finalizado") e era reescrito por oito
caminhos diferentes sem nenhuma guarda:

  views/rdo.py:698, 1540, 1630, 1755, 2614, 3967
  rdo_editar_sistema.py:221
  crud_rdo_completo.py:338, 572

A coluna `status` NÃO muda de significado — ≥9 consumidores filtram
`status == 'Finalizado'` (cronograma_views.py:2458,2488;
portal_obras_views.py:239; services/medicao_service.py:243;
services/rdo_custos.py:330; services/metricas_produtividade.py:186,972,
1302,1320,1397,1416). O ciclo de vida entra numa coluna NOVA, `estado`.
"""
import os
import sys
import uuid
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os 54 blueprints antes de qualquer request
from app import app, db
from models import Cliente, Funcionario, Obra, RDO, TipoUsuario, Usuario

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase5-rdo'
    yield


def _sfx():
    return uuid.uuid4().hex[:8]


def _admin(nome='Admin F5'):
    suf = _sfx()
    u = Usuario(
        username=f'f5a_{suf}', email=f'f5a_{suf}@test.local',
        nome=f'{nome} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id, nome='Obra F5'):
    """Obra.cliente_id é NOT NULL — o Cliente vem junto, sempre."""
    suf = _sfx()
    cli = Cliente(nome=f'CLI-F5-{suf}', admin_id=admin_id)
    db.session.add(cli)
    db.session.flush()
    o = Obra(
        nome=f'{nome} {suf}', codigo=f'OF5{suf[:6].upper()}',
        data_inicio=date(2026, 1, 1), admin_id=admin_id,
        cliente_id=cli.id, valor_contrato=100000,
    )
    db.session.add(o)
    db.session.commit()
    return o


def _rdo(obra, admin_id, criado_por_id=None, data=None):
    suf = _sfx()
    r = RDO(
        numero_rdo=f'RDO-F5-{suf}',
        data_relatorio=data or date(2026, 6, 22),
        obra_id=obra.id, admin_id=admin_id,
        criado_por_id=criado_por_id,
        comentario_geral='Concretagem do radier.',
        clima_geral='Nublado',
    )
    db.session.add(r)
    db.session.commit()
    return r


def test_rdo_tem_coluna_estado():
    with app.app_context():
        assert hasattr(RDO, 'estado'), (
            'RDO.estado não existe — o RDO continua sem ciclo de vida')


def test_estado_default_e_rascunho():
    from services.rdo_ciclo_vida import RASCUNHO

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        assert rdo.estado == RASCUNHO, (
            f'RDO novo nasceu em {rdo.estado!r}, deveria nascer em rascunho')


def test_status_legado_continua_finalizado():
    """≥9 consumidores filtram status=='Finalizado'. Não pode mudar."""
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        assert rdo.status == 'Finalizado', (
            'o default de RDO.status mudou — isso some com o RDO do portal '
            '(portal_obras_views.py:239) e das métricas')


def test_backfill_marcou_os_rdos_historicos_como_preenchido():
    """Migration 260: histórico vira 'preenchido', NUNCA 'assinado'.

    O plano original asseverava `count(estado='assinado') == 0` no banco
    inteiro — verdade só no instante pós-migration. Num banco compartilhado
    a própria suíte cria RDOs legitimamente assinados (via transicionar,
    que grava trilha). O invariante durável é: assinado SEM trilha de
    transição para 'assinado' não existe — seria autoria forjada por
    backfill.
    """
    from sqlalchemy import text
    from services.rdo_ciclo_vida import ASSINADO

    with app.app_context():
        forjados = db.session.execute(text("""
            SELECT count(*) FROM rdo r
            WHERE r.estado = :e
              AND NOT EXISTS (
                  SELECT 1 FROM rdo_transicao_estado t
                  WHERE t.rdo_id = r.id AND t.estado_novo = :e
              )
        """), {'e': ASSINADO}).scalar()
        assert forjados == 0, (
            f'{forjados} RDO(s) estão assinados SEM trilha de transição — '
            f'autoria forjada (backfill ou escrita por fora da máquina)')
        orfaos = db.session.execute(text(
            "SELECT count(*) FROM rdo WHERE estado IS NULL")).scalar()
        assert orfaos == 0, f'{orfaos} RDO(s) ficaram sem estado após o backfill'


# ---------------------------------------------------------------------------
# Trilha de transições
# ---------------------------------------------------------------------------

def test_modelo_de_transicao_existe_e_persiste():
    from models import RDOTransicaoEstado

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        t = RDOTransicaoEstado(
            rdo_id=rdo.id, admin_id=admin.id,
            estado_anterior='rascunho', estado_novo='preenchido',
            usuario_id=admin.id, motivo='submissão do dia',
            ip='203.0.113.7', detalhes={'origem': 'teste'},
        )
        db.session.add(t)
        db.session.commit()
        tid = t.id

    with app.app_context():
        recarregado = db.session.get(RDOTransicaoEstado, tid)
        assert recarregado.estado_anterior == 'rascunho'
        assert recarregado.estado_novo == 'preenchido'
        assert recarregado.detalhes == {'origem': 'teste'}
        assert recarregado.criado_em is not None


def test_transicao_e_apagada_junto_com_o_rdo():
    """ON DELETE CASCADE: excluir RDO não pode deixar trilha órfã."""
    from models import RDOTransicaoEstado

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        db.session.add(RDOTransicaoEstado(
            rdo_id=rdo.id, admin_id=admin.id,
            estado_anterior='rascunho', estado_novo='preenchido',
            usuario_id=admin.id,
        ))
        db.session.commit()
        rid = rdo.id
        db.session.delete(rdo)
        db.session.commit()
        assert RDOTransicaoEstado.query.filter_by(rdo_id=rid).count() == 0


# ---------------------------------------------------------------------------
# Máquina de estados
# ---------------------------------------------------------------------------

def test_conjunto_de_estados_e_fechado():
    from services.rdo_ciclo_vida import ESTADOS

    assert ESTADOS == {'rascunho', 'preenchido', 'assinado',
                       'aprovado', 'retificado'}


def test_transicoes_validas_sao_as_esperadas():
    from services.rdo_ciclo_vida import TRANSICOES_VALIDAS

    assert TRANSICOES_VALIDAS['rascunho'] == {'preenchido'}
    assert TRANSICOES_VALIDAS['preenchido'] == {'rascunho', 'assinado'}
    assert TRANSICOES_VALIDAS['assinado'] == {'aprovado', 'retificado'}
    assert TRANSICOES_VALIDAS['aprovado'] == {'retificado'}
    assert TRANSICOES_VALIDAS['retificado'] == set()


def test_transicionar_grava_estado_e_trilha():
    from models import RDOTransicaoEstado
    from services.rdo_ciclo_vida import PREENCHIDO, transicionar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)

        transicionar(rdo, PREENCHIDO, usuario=admin, motivo='fim do dia',
                     ip='203.0.113.7')
        db.session.commit()
        rid = rdo.id

    with app.app_context():
        recarregado = db.session.get(RDO, rid)
        assert recarregado.estado == PREENCHIDO
        trilha = RDOTransicaoEstado.query.filter_by(rdo_id=rid).all()
        assert len(trilha) == 1
        assert trilha[0].estado_anterior == 'rascunho'
        assert trilha[0].estado_novo == PREENCHIDO
        assert trilha[0].motivo == 'fim do dia'
        assert trilha[0].ip == '203.0.113.7'


def test_transicao_invalida_e_recusada():
    from services.rdo_ciclo_vida import APROVADO, TransicaoInvalida, transicionar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)  # rascunho

        with pytest.raises(TransicaoInvalida):
            transicionar(rdo, APROVADO, usuario=admin)
        db.session.rollback()
        assert db.session.get(RDO, rdo.id).estado == 'rascunho'


def test_estado_desconhecido_e_recusado():
    from services.rdo_ciclo_vida import TransicaoInvalida, transicionar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        with pytest.raises(TransicaoInvalida):
            transicionar(rdo, 'homologado', usuario=admin)
        db.session.rollback()


def test_transicao_para_o_mesmo_estado_e_no_op_sem_trilha():
    """Reenviar o mesmo estado não pode poluir a trilha."""
    from models import RDOTransicaoEstado
    from services.rdo_ciclo_vida import RASCUNHO, transicionar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        transicionar(rdo, RASCUNHO, usuario=admin)
        db.session.commit()
        assert RDOTransicaoEstado.query.filter_by(rdo_id=rdo.id).count() == 0


def test_estados_imutaveis_sao_os_tres_finais():
    from services.rdo_ciclo_vida import ESTADOS_IMUTAVEIS

    assert ESTADOS_IMUTAVEIS == {'assinado', 'aprovado', 'retificado'}


def test_garantir_editavel_passa_em_rascunho_e_preenchido():
    from services.rdo_ciclo_vida import (PREENCHIDO, garantir_editavel,
                                         transicionar)

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        garantir_editavel(rdo)          # rascunho: passa
        transicionar(rdo, PREENCHIDO, usuario=admin)
        db.session.commit()
        garantir_editavel(rdo)          # preenchido: passa


def test_garantir_editavel_recusa_assinado():
    from services.rdo_ciclo_vida import (ASSINADO, PREENCHIDO, RDOImutavel,
                                         garantir_editavel, transicionar)

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        transicionar(rdo, PREENCHIDO, usuario=admin)
        transicionar(rdo, ASSINADO, usuario=admin)
        db.session.commit()
        with pytest.raises(RDOImutavel):
            garantir_editavel(rdo)


# ---------------------------------------------------------------------------
# Guarda de imutabilidade
# ---------------------------------------------------------------------------

def _assinar_direto(rdo, admin):
    """Leva o RDO até 'assinado' sem passar pela rota (Task 7 ainda não existe)."""
    from services.rdo_ciclo_vida import ASSINADO, PREENCHIDO, transicionar
    transicionar(rdo, PREENCHIDO, usuario=admin)
    transicionar(rdo, ASSINADO, usuario=admin)
    db.session.commit()


def test_editar_rdo_assinado_e_barrado_no_flush():
    from services.rdo_ciclo_vida import RDOImutavel

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        _assinar_direto(rdo, admin)

        rdo.comentario_geral = 'reescrevendo a história'
        with pytest.raises(RDOImutavel):
            db.session.commit()
        db.session.rollback()
        assert db.session.get(RDO, rdo.id).comentario_geral == \
            'Concretagem do radier.'


def test_inserir_mao_de_obra_em_rdo_assinado_e_barrado():
    from models import RDOMaoObra
    from services.rdo_ciclo_vida import RDOImutavel

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        func = Funcionario(
            nome=f'Pedreiro {_sfx()}', cpf=_sfx().ljust(14, '0')[:14],
            codigo=f'FF5{_sfx()[:6].upper()}', data_admissao=date(2025, 1, 1),
            admin_id=admin.id, ativo=True,
        )
        db.session.add(func)
        db.session.commit()
        _assinar_direto(rdo, admin)

        db.session.add(RDOMaoObra(
            rdo_id=rdo.id, admin_id=admin.id, funcionario_id=func.id,
            funcao_exercida='Pedreiro', horas_trabalhadas=8.0))
        with pytest.raises(RDOImutavel):
            db.session.commit()
        db.session.rollback()
        assert RDOMaoObra.query.filter_by(rdo_id=rdo.id).count() == 0


def test_apontamento_de_cronograma_em_rdo_assinado_e_barrado():
    """Ponto de contato com o plano irmão (modo de apontamento)."""
    from models import RDOApontamentoCronograma, TarefaCronograma
    from services.rdo_ciclo_vida import RDOImutavel

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        tarefa = TarefaCronograma(
            obra_id=obra.id, nome_tarefa='Radier', ordem=1, duracao_dias=5,
            quantidade_total=100.0, unidade_medida='m2',
            percentual_concluido=0.0, data_inicio=date(2026, 6, 20),
            data_fim=date(2026, 6, 25), admin_id=admin.id)
        db.session.add(tarefa)
        rdo = _rdo(obra, admin.id)
        db.session.commit()
        _assinar_direto(rdo, admin)

        db.session.add(RDOApontamentoCronograma(
            rdo_id=rdo.id, tarefa_cronograma_id=tarefa.id, admin_id=admin.id,
            quantidade_executada_dia=10.0, quantidade_acumulada=10.0,
            percentual_realizado=10.0))
        with pytest.raises(RDOImutavel):
            db.session.commit()
        db.session.rollback()


def test_excluir_rdo_assinado_e_barrado():
    from services.rdo_ciclo_vida import RDOImutavel

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        _assinar_direto(rdo, admin)

        db.session.delete(rdo)
        with pytest.raises(RDOImutavel):
            db.session.commit()
        db.session.rollback()
        assert db.session.get(RDO, rdo.id) is not None


def test_transicao_de_estado_atravessa_a_guarda():
    """assinado → aprovado escreve no RDO imutável e PRECISA passar."""
    from services.rdo_ciclo_vida import APROVADO, transicionar

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        _assinar_direto(rdo, admin)

        transicionar(rdo, APROVADO, usuario=admin)
        db.session.commit()
        assert db.session.get(RDO, rdo.id).estado == APROVADO


def test_bypass_nao_vaza_entre_transacoes():
    """Depois da transição, a guarda tem que estar de pé de novo."""
    from services.rdo_ciclo_vida import (APROVADO, RDOImutavel, bypass_ativo,
                                         transicionar)

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        _assinar_direto(rdo, admin)
        transicionar(rdo, APROVADO, usuario=admin)
        db.session.commit()

        assert bypass_ativo() is False
        rdo.comentario_geral = 'depois da aprovação'
        with pytest.raises(RDOImutavel):
            db.session.commit()
        db.session.rollback()


def test_qualquer_caminho_de_escrita_e_barrado():
    """A prova de que a guarda vale para as rotas que ninguém migrou.

    `salvar_rdo_flexivel` (views/rdo.py:3967) é o caminho mais obscuro do
    módulo — sem nenhuma noção de estado. Se a guarda pega ele, pega os
    outros sete.
    """
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        _assinar_direto(rdo, admin)
        rid, oid, aid = rdo.id, obra.id, admin.id

    cliente = app.test_client()
    with cliente.session_transaction() as sess:
        sess['_user_id'] = str(aid)
        sess['_fresh'] = True

    resposta = cliente.post('/salvar-rdo-flexivel', data={
        'rdo_id': str(rid),
        'obra_id': str(oid),
        'data_relatorio': '2026-06-22',
        'comentario_geral': 'tentativa de reescrita',
    }, follow_redirects=True)
    assert resposta.status_code in (200, 302)

    with app.app_context():
        assert db.session.get(RDO, rid).comentario_geral == \
            'Concretagem do radier.', (
            'salvar_rdo_flexivel reescreveu um RDO assinado — a guarda '
            'before_flush não pegou este caminho')


# ---------------------------------------------------------------------------
# Bug 6d — duplicar_rdo
# ---------------------------------------------------------------------------

def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


def test_duplicar_rdo_nao_quebra_em_atributo_fantasma():
    """Regressão do bug 6d, parte 1.

    Antes: views/rdo.py:1624 lia `rdo_original.tempo_manha`, que NÃO é
    coluna de RDO (as colunas de clima são clima_geral, temperatura_media,
    umidade_relativa, vento_velocidade, precipitacao, condicoes_trabalho,
    observacoes_climaticas). A leitura levantava AttributeError, a função
    caía no `except` da linha 1715 e a rota NUNCA duplicava nada.
    """
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        rid, aid, oid = rdo.id, admin.id, obra.id

    resposta = _cliente_de(aid).post(f'/rdo/{rid}/duplicar',
                                     follow_redirects=False)
    assert resposta.status_code in (200, 302)

    with app.app_context():
        copias = RDO.query.filter(RDO.obra_id == oid, RDO.id != rid).all()
        assert len(copias) == 1, (
            'duplicar_rdo não criou o RDO copiado — provavelmente ainda '
            'morre no atributo fantasma tempo_manha (views/rdo.py:1624)')
        assert copias[0].clima_geral == 'Nublado'


def test_duplicar_rdo_nasce_em_rascunho():
    """Regressão do bug 6d, parte 2.

    Antes: views/rdo.py:1629 gravava status='Finalizado' na cópia. Um RDO
    duplicado é um ponto de partida para edição, não um documento
    publicado — e era exatamente essa premissa falsa que justificava o
    webhook da linha 1708.
    """
    from services.rdo_ciclo_vida import RASCUNHO

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        rid, aid, oid = rdo.id, admin.id, obra.id

    _cliente_de(aid).post(f'/rdo/{rid}/duplicar')

    with app.app_context():
        copia = RDO.query.filter(RDO.obra_id == oid, RDO.id != rid).first()
        assert copia.estado == RASCUNHO


def test_duplicar_rdo_nao_emite_webhook(monkeypatch):
    """Regressão do bug 6d, parte 3 — o bug nomeado no ESTADO-ATUAL.md.

    `duplicar_rdo` era a ÚNICA rota de escrita de RDO que chamava
    `emit_obra_rdo_publicado` (views/rdo.py:1708) sem chamar
    `EventManager.emit('rdo_finalizado')` — que é quem dispara
    `lancar_custos_rdo` (event_manager.py:578) e
    `recalcular_medicao_apos_rdo` (event_manager.py:1357). As irmãs
    emitem os dois (:1570/:1583, :1819/:1831, :4769/:4781).

    A correção adotada NÃO é "emitir os dois": é não emitir nenhum,
    porque um RDO duplicado nasce em rascunho e ainda não publicou nada.
    O webhook sai quando ele for submetido/assinado.
    """
    emitidos = []

    import utils.catalogo_eventos as catalogo
    monkeypatch.setattr(catalogo, 'emit_obra_rdo_publicado',
                        lambda rdo, admin_id: emitidos.append(rdo.id))

    from event_manager import EventManager
    eventos_legados = []
    original_emit = EventManager.emit
    monkeypatch.setattr(
        EventManager, 'emit',
        staticmethod(lambda nome, dados, admin_id=None: (
            eventos_legados.append(nome) or original_emit(nome, dados, admin_id)
            if nome != 'rdo_finalizado' else eventos_legados.append(nome))))

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        rid, aid = rdo.id, admin.id

    _cliente_de(aid).post(f'/rdo/{rid}/duplicar')

    assert emitidos == [], (
        'duplicar_rdo emitiu obra.rdo_publicado para um RDO que nasce em '
        'rascunho — bug 6d')
    assert 'rdo_finalizado' not in eventos_legados


def test_duplicar_rdo_nao_lanca_custo_de_mao_de_obra():
    """A outra metade do bug 6d: webhook sem custo.

    Se o RDO duplicado não publica, também não pode gerar RDOCustoDiario
    nem GestaoCustoFilho — nem pelo evento, nem por chamada direta.
    """
    from models import RDOCustoDiario, RDOMaoObra

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = Funcionario(
            nome=f'Montador {_sfx()}', cpf=_sfx().ljust(14, '0')[:14],
            codigo=f'FD{_sfx()[:6].upper()}', data_admissao=date(2025, 1, 1),
            admin_id=admin.id, ativo=True, tipo_remuneracao='diaria',
            valor_diaria=200.0)
        db.session.add(func)
        rdo = _rdo(obra, admin.id)
        db.session.commit()
        db.session.add(RDOMaoObra(
            rdo_id=rdo.id, admin_id=admin.id, funcionario_id=func.id,
            funcao_exercida='Montador', horas_trabalhadas=8.0))
        db.session.commit()
        rid, aid, oid = rdo.id, admin.id, obra.id

    _cliente_de(aid).post(f'/rdo/{rid}/duplicar')

    with app.app_context():
        copia = RDO.query.filter(RDO.obra_id == oid, RDO.id != rid).first()
        assert RDOMaoObra.query.filter_by(rdo_id=copia.id).count() == 1, (
            'a mão de obra não foi copiada')
        assert RDOCustoDiario.query.filter_by(rdo_id=copia.id).count() == 0, (
            'RDO duplicado em rascunho lançou custo diário')


def test_duplicar_rdo_de_outro_tenant_devolve_404():
    with app.app_context():
        admin_a, admin_b = _admin('A'), _admin('B')
        obra_b = _obra(admin_b.id)
        rdo_b = _rdo(obra_b, admin_b.id)
        # obra_b.id capturado AQUI: o commit de _rdo expira a instância e
        # acessá-la num segundo app_context levanta DetachedInstanceError.
        rid, aid, obid = rdo_b.id, admin_a.id, obra_b.id

    resposta = _cliente_de(aid).post(f'/rdo/{rid}/duplicar',
                                     follow_redirects=False)
    assert resposta.status_code in (302, 404)

    with app.app_context():
        assert RDO.query.filter_by(obra_id=obid).count() == 1


def test_duplicar_rdo_assinado_e_permitido():
    """Duplicar não é editar: o original não é tocado."""
    from services.rdo_ciclo_vida import ASSINADO

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        _assinar_direto(rdo, admin)
        rid, aid, oid = rdo.id, admin.id, obra.id

    _cliente_de(aid).post(f'/rdo/{rid}/duplicar')

    with app.app_context():
        assert db.session.get(RDO, rid).estado == ASSINADO
        assert RDO.query.filter(RDO.obra_id == oid, RDO.id != rid).count() == 1


# ---------------------------------------------------------------------------
# Rotas anônimas e exclusão
# ---------------------------------------------------------------------------

def test_visualizar_rdo_exige_login():
    """views/rdo.py:928 dizia literalmente 'SEM VERIFICAÇÃO DE PERMISSÃO'.

    Um RDO assinado que qualquer anônimo lê pela URL não tem valor
    probatório nenhum — e a numeração (`RDO-<admin_id>-<ano>-NNN`) é
    sequencial e adivinhável.
    """
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        rid = rdo.id

    resposta = app.test_client().get(f'/rdo/{rid}', follow_redirects=False)
    assert resposta.status_code in (302, 401), (
        f'/rdo/{rid} devolveu {resposta.status_code} para anônimo')
    if resposta.status_code == 302:
        assert '/login' in resposta.headers.get('Location', '')


def test_visualizar_rdo_de_outro_tenant_devolve_404():
    with app.app_context():
        admin_a, admin_b = _admin('A'), _admin('B')
        obra_b = _obra(admin_b.id)
        rdo_b = _rdo(obra_b, admin_b.id)
        rid, aid = rdo_b.id, admin_a.id

    resposta = _cliente_de(aid).get(f'/rdo/{rid}', follow_redirects=False)
    assert resposta.status_code in (302, 404), (
        f'RDO de outro tenant devolveu {resposta.status_code}')


def test_excluir_rdo_assinado_pela_rota_e_recusado():
    from services.rdo_ciclo_vida import ASSINADO

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        _assinar_direto(rdo, admin)
        rid, aid = rdo.id, admin.id

    _cliente_de(aid).post(f'/rdo/excluir/{rid}', follow_redirects=True)

    with app.app_context():
        sobrevivente = db.session.get(RDO, rid)
        assert sobrevivente is not None, 'RDO assinado foi excluído'
        assert sobrevivente.estado == ASSINADO


def test_excluir_rdo_em_rascunho_continua_funcionando():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        rid, aid = rdo.id, admin.id

    _cliente_de(aid).post(f'/rdo/excluir/{rid}', follow_redirects=True)

    with app.app_context():
        assert db.session.get(RDO, rid) is None
