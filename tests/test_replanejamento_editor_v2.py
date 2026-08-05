"""A06 — o editor v2 replaneja a curva a cada edição de data.

**O defeito.** `atualizar_tarefa` recalcula datas e **não toca
`percentual_planejado` em nenhum ponto** — a curva planejada dos apontamentos
já gravados continua apontando para um plano que não existe mais. Quem lê a
curva de avanço (`views/obras.py`, o PDF do RDO, o EVM) compara o realizado com
um planejado órfão.

`replanejar_curvas_obra` já existia e resolvia isso, mas só era chamada ao
aplicar/restaurar versão (M05). O editor v2 muda data o dia inteiro e nunca a
chamava.

**Por que o modo enxuto existe (B2.17).** A função fazia DUAS varreduras da obra
inteira só para montar `progresso_antes`/`progresso_depois` — um relatório que o
editor não lê. Pagar isso a cada edição de data seria trocar um número errado
por uma tela lenta.
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from utils.cronograma_engine import replanejar_curvas_obra

from test_cronograma_versao_service import _ambiente, _tarefa
from test_replanejamento import _rdo_apontado, _realizado

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-replan-v2'
    with app.app_context():
        yield


def _client_v2(admin_id, flag=True):
    """Cliente autenticado com o editor v2 LIGADO no tenant.

    A flag mora numa coluna de `ConfiguracaoEmpresa` — mesmo helper da Fase 1,
    usado por `tests/test_cronograma_grade_api.py`.

    `flag=False` mantém o usuário V2 (é `versao_sistema`, outro eixo) e desliga
    só o editor novo — é assim que se alcança o ramo LEGADO de `/recalcular`.
    """
    from models import ConfiguracaoEmpresa

    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    if config is None:
        config = ConfiguracaoEmpresa(admin_id=admin_id,
                                     nome_empresa=f'Empresa {admin_id}')
        db.session.add(config)
    config.cronograma_editor_v2 = flag
    db.session.commit()

    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(admin_id)
        sess['_fresh'] = True
    return c


def _cenario():
    """Tarefa de julho com um apontamento cujo planejado está órfão."""
    admin, obra = _ambiente()
    t = _tarefa(obra, admin, 'Alvenaria', ordem=0, duracao_dias=10,
                data_inicio=date(2026, 7, 1), data_fim=date(2026, 7, 14))
    ap = _rdo_apontado(obra, admin, t, date(2026, 7, 8), 0, 0, 30, 99.0)
    return admin, obra, t, ap


def _vizinhas(obra, admin):
    """Duas folhas SEM apontamento, ao lado da 'Alvenaria' do `_cenario`.

    Elas são o alvo das rotas que não editam a tarefa apontada — criar
    vínculo, recuar, excluir. A 'Alvenaria' fica intocada de propósito: o que
    o teste mede é o **efeito colateral** da rota sobre a curva planejada da
    obra inteira, e não uma edição direta daquela tarefa. Como a 'Alvenaria'
    tem apontamento, o motor a trata como ancorada e não move as datas dela —
    então o planejado correto é sempre 60,0%, e um 99,0% que sobrevive
    significa que a rota não replanejou nada.
    """
    p = _tarefa(obra, admin, 'Pintura', ordem=1, duracao_dias=5,
                data_inicio=date(2026, 7, 15), data_fim=date(2026, 7, 21))
    a = _tarefa(obra, admin, 'Acabamento', ordem=2, duracao_dias=5,
                data_inicio=date(2026, 7, 22), data_fim=date(2026, 7, 28))
    return p, a


def _planejado(ap):
    db.session.expire_all()
    return db.session.get(type(ap), ap.id).percentual_planejado


# ---------------------------------------------------------------------------
# B2.17 — modo enxuto
# ---------------------------------------------------------------------------

def test_modo_enxuto_replaneja_igual_e_dispensa_o_relatorio():
    """O que o editor v2 vai chamar: replaneja o mesmo, sem as duas varreduras.

    🔬 **A asserção que importa é a do `percentual_planejado`**, não a dos
    `None`. Um teste que só afirmasse "o relatório veio vazio" passaria com uma
    função que não replanejasse nada — mediria o vazio. Aqui o 60.0 prova que o
    trabalho foi feito, e os `None` provam que o relatório foi pulado.

    01→08/07 sem fim de semana: 6 dias úteis de 10 ⇒ 60%.
    """
    _admin, obra, _t, ap = _cenario()
    admin_id = ap.admin_id
    antes = _realizado(ap)

    rel = replanejar_curvas_obra(obra.id, admin_id, com_relatorio=False)

    db.session.refresh(ap)
    assert ap.percentual_planejado == 60.0, (
        f'o modo enxuto não replanejou: {ap.percentual_planejado}')
    assert rel['apontamentos_replanejados'] == 1
    assert rel['progresso_antes'] is None, (
        'com_relatorio=False ainda pagou a varredura de progresso')
    assert rel['progresso_depois'] is None
    assert _realizado(ap) == antes, 'o realizado foi tocado'


def test_o_default_continua_entregando_o_relatorio_completo():
    """O par do teste acima, e ele existe para o par não ser vacuoso.

    Sem esta asserção, trocar o default para `com_relatorio=False` passaria
    despercebido — e `services/cronograma_versao_service.py` chama sem
    argumentos, afirmando os dois campos como float.
    """
    _admin, obra, _t, ap = _cenario()

    rel = replanejar_curvas_obra(obra.id, ap.admin_id)

    assert isinstance(rel['progresso_antes'], float), (
        f"progresso_antes veio {rel['progresso_antes']!r} — o default mudou, e "
        f"cronograma_versao_service chama sem argumentos")
    assert isinstance(rel['progresso_depois'], float)


def test_a_rota_de_editar_tarefa_replaneja_a_curva():
    """B2.19, teste 1 — **o defeito**, pela rota.

    `atualizar_tarefa` recalculava as datas e deixava o `percentual_planejado`
    dos apontamentos apontando para o plano antigo. O RDO de 08/07 tinha 60,0%
    planejado — valor CORRETO para uma tarefa de 10 dias começando em 01/07.
    Esticando a tarefa para 30 dias, os mesmos 6 dias úteis passam a valer 20%.

    🔴 **O cenário do recorte (`PUT data_inicio`) é BLOQUEADO por um guard que a
    B2.19 não previu.** Com o editor v2 ligado, tarefa com apontamento de RDO
    tem o início **congelado** (`cronograma_views.py:975-981`,
    `ids_tarefas_iniciadas`), e a rota responde 400. Como toda tarefa que tem
    apontamento é, por definição, "iniciada", **nenhum cenário do recorte com
    `data_inicio` era executável**. `duracao_dias` está em `_SCHEDULING_FIELDS`,
    não é bloqueado, e exercita exatamente o mesmo caminho.

    A segunda asserção é a que impede a correção de virar estrago: **o realizado
    é intocável**.
    """
    _admin, obra, t, ap = _cenario()
    admin_id = ap.admin_id
    antes = _realizado(ap)

    cli = _client_v2(admin_id)
    r = cli.put(f'/cronograma/obra/{obra.id}/tarefa/{t.id}',
                json={'duracao_dias': 30})
    assert r.status_code == 200, f'a rota respondeu {r.status_code}: {r.data[:300]}'

    db.session.expire_all()
    ap_db = db.session.get(type(ap), ap.id)
    assert ap_db.percentual_planejado == pytest.approx(20.0), (
        f'planejado ficou em {ap_db.percentual_planejado} — a tarefa passou de '
        f'10 para 30 dias, então os 6 dias úteis até 08/07 valem 20%, não os '
        f'60% do plano que não existe mais')
    assert _realizado(ap_db) == antes, 'o realizado foi alterado pela edição'


def test_o_percentual_manual_digitado_sobrevive_ao_replanejamento():
    """B2.19, teste 2 — **a armadilha da ordem**, e o núcleo do item.

    🔬 Se a chamada de replanejamento entrar ANTES das linhas que reaplicam
    `perc_manual`, e alguém deixar `sincronizar=True`,
    `sincronizar_percentuais_obra` reescreve `percentual_concluido` a partir do
    último apontamento — e **o 77% que o usuário acabou de digitar vira 30%**,
    que é o que o apontamento diz.

    Depois das linhas certas e com `sincronizar=False`, o risco fecha dos dois
    lados. Este teste é o que trava isso: é o contrato daquelas quatro linhas.
    """
    _admin, obra, t, ap = _cenario()
    admin_id = ap.admin_id

    cli = _client_v2(admin_id)
    r = cli.put(f'/cronograma/obra/{obra.id}/tarefa/{t.id}',
                json={'duracao_dias': 30, 'percentual_concluido': 77.0})
    assert r.status_code == 200, f'a rota respondeu {r.status_code}: {r.data[:300]}'

    db.session.expire_all()
    t_db = db.session.get(type(t), t.id)
    assert float(t_db.percentual_concluido) == pytest.approx(77.0), (
        f'percentual_concluido ficou {t_db.percentual_concluido} — 30.0 é o que '
        f'o apontamento diz, e significa que o replanejamento arrastou '
        f'sincronizar_percentuais_obra por cima do que o usuário digitou')


def test_renomear_tarefa_nao_paga_o_replanejamento():
    """B2.19 — a guarda de `precisa_recalc`.

    Replanejar varre TODOS os apontamentos da obra. Pagar isso ao renomear uma
    tarefa seria transformar uma edição de texto numa varredura — e o
    `percentual_planejado` não tem por que mudar quando nenhuma data mudou.
    """
    _admin, obra, t, ap = _cenario()
    admin_id = ap.admin_id
    planejado_antes = ap.percentual_planejado

    cli = _client_v2(admin_id)
    r = cli.put(f'/cronograma/obra/{obra.id}/tarefa/{t.id}',
                json={'nome_tarefa': 'Alvenaria renomeada'})
    assert r.status_code == 200, f'a rota respondeu {r.status_code}: {r.data[:300]}'

    db.session.expire_all()
    ap_db = db.session.get(type(ap), ap.id)
    assert ap_db.percentual_planejado == planejado_antes, (
        'renomear a tarefa mexeu no planejado — a guarda de precisa_recalc não '
        'está segurando')


def test_sem_sincronizar_o_replanejamento_ainda_acontece():
    """`sincronizar=False` é para quem vai sincronizar por conta própria depois.

    O que ele NÃO pode fazer é pular o replanejamento junto — que seria o jeito
    silencioso de a chave nova virar um no-op.
    """
    _admin, obra, _t, ap = _cenario()

    rel = replanejar_curvas_obra(obra.id, ap.admin_id,
                                 com_relatorio=False, sincronizar=False)

    db.session.refresh(ap)
    assert ap.percentual_planejado == 60.0
    assert rel['apontamentos_replanejados'] == 1


# ---------------------------------------------------------------------------
# B2.20 — os outros CINCO pontos de recálculo
#
# O título da Task diz "seis"; o campo Files dela lista cinco funções, e é
# cinco: `_aplicar_hierarquia`, `_recalc_e_resposta_vinculo`, `criar_tarefa`,
# `excluir_tarefa` e `recalcular`. Os dois ramos de `atualizar_tarefa` são da
# B2.19 e já estão acima.
# ---------------------------------------------------------------------------

def test_criar_tarefa_replaneja_a_curva():
    """`criar_tarefa` — o ramo simples (append no fim), depois do commit.

    Nascer uma tarefa recalcula a obra; a curva planejada dos apontamentos já
    gravados tem de acompanhar. A chamada fica FORA do `try` do `ErroCiclo`:
    lá dentro o commit interno do replanejamento rodaria antes do
    `db.session.rollback()` e gravaria o que o ciclo mandou desfazer.
    """
    _admin, obra, _t, ap = _cenario()
    cli = _client_v2(ap.admin_id)

    r = cli.post(f'/cronograma/obra/{obra.id}/tarefa',
                 json={'nome_tarefa': 'Pintura', 'duracao_dias': 5,
                       'data_inicio': '2026-07-15'})
    assert r.status_code == 201, f'a rota respondeu {r.status_code}: {r.data[:300]}'

    assert _planejado(ap) == pytest.approx(60.0), (
        'criar tarefa não replanejou a curva — o apontamento de 08/07 seguiu '
        'com os 99% do plano órfão')


def test_criar_tarefa_posicionada_replaneja_a_curva():
    """`_aplicar_hierarquia` pelo lado do `criar_tarefa` posicionado.

    Mesmo helper do recuar/desrecuar/mover, outra porta de entrada — e a que
    prova que a chamada está no helper, não copiada dentro de cada rota.
    """
    _admin, obra, t, ap = _cenario()
    cli = _client_v2(ap.admin_id)

    r = cli.post(f'/cronograma/obra/{obra.id}/tarefa',
                 json={'nome_tarefa': 'Pintura', 'duracao_dias': 5,
                       'data_inicio': '2026-07-15',
                       'posicao': 'abaixo', 'ref_tarefa_id': t.id})
    assert r.status_code == 201, f'a rota respondeu {r.status_code}: {r.data[:300]}'

    assert _planejado(ap) == pytest.approx(60.0), (
        'criar tarefa posicionada não replanejou — _aplicar_hierarquia é o '
        'ponto que serve criar-posicionado, recuar, desrecuar e mover')


def test_recuar_tarefa_replaneja_a_curva():
    """`_aplicar_hierarquia` — duas linhas que cobrem quatro rotas.

    Recuar 'Acabamento' para dentro de 'Pintura' renumera e recalcula a obra
    inteira. A 'Alvenaria' apontada nem entra na operação: é justamente por
    isso que ela mede o efeito colateral sobre a curva.
    """
    _admin, obra, _t, ap = _cenario()
    _p, acab = _vizinhas(obra, _admin)
    cli = _client_v2(ap.admin_id)

    r = cli.post(f'/cronograma/obra/{obra.id}/tarefa/{acab.id}/recuar')
    assert r.status_code == 200, f'a rota respondeu {r.status_code}: {r.data[:300]}'

    assert _planejado(ap) == pytest.approx(60.0), (
        'recuar não replanejou a curva — _aplicar_hierarquia serve recuar, '
        'desrecuar, mover e criar-posicionado, e nenhuma delas tocaria o '
        'planejado')


def test_criar_vinculo_replaneja_a_curva():
    """`_recalc_e_resposta_vinculo` — serve criar, atualizar e excluir vínculo.

    O vínculo é entre as duas vizinhas; a 'Alvenaria' apontada fica fora dele.
    A chamada tem de entrar DEPOIS do commit e ANTES do `_mapas_vinculos`: se o
    replanejamento falhar e rolar back, a serialização re-consulta o banco em
    vez de ler objetos ORM expirados.
    """
    _admin, obra, _t, ap = _cenario()
    pint, acab = _vizinhas(obra, _admin)
    cli = _client_v2(ap.admin_id)

    r = cli.post(f'/cronograma/obra/{obra.id}/vinculo',
                 json={'predecessora_id': pint.id, 'sucessora_id': acab.id,
                       'tipo': 'TI'})
    assert r.status_code == 201, f'a rota respondeu {r.status_code}: {r.data[:300]}'

    assert _planejado(ap) == pytest.approx(60.0), (
        'criar vínculo não replanejou a curva — _recalc_e_resposta_vinculo é '
        'o ponto único das três rotas de vínculo')


def test_falha_no_replanejamento_nao_derruba_a_rota_de_vinculo(monkeypatch):
    """A chamada é PÓS-COMMIT: quebrar aqui não pode desfazer a edição.

    🔬 O `rollback()` do `except` do helper expira os objetos ORM. Se a chamada
    estivesse depois da serialização — ou sem o try/except — este cenário
    devolveria 500 e o usuário perderia um vínculo que já estava gravado. Aqui
    a resposta sai completa e o vínculo continua no banco.
    """
    from models import TarefaVinculo
    import utils.cronograma_engine as engine

    _admin, obra, _t, ap = _cenario()
    pint, acab = _vizinhas(obra, _admin)

    def _explode(*_a, **_kw):
        raise RuntimeError('replanejamento quebrado de propósito')

    monkeypatch.setattr(engine, 'replanejar_curvas_obra', _explode)

    cli = _client_v2(ap.admin_id)
    r = cli.post(f'/cronograma/obra/{obra.id}/vinculo',
                 json={'predecessora_id': pint.id, 'sucessora_id': acab.id,
                       'tipo': 'TI'})

    assert r.status_code == 201, (
        f'a falha do replanejamento derrubou a rota ({r.status_code}) — ela é '
        f'pós-commit e nunca pode desfazer a edição: {r.data[:300]}')
    assert r.get_json()['vinculo']['id'], 'a resposta saiu sem o vínculo'
    assert TarefaVinculo.query.filter_by(
        obra_id=obra.id, predecessora_id=pint.id,
        sucessora_id=acab.id).first() is not None, (
        'o vínculo já commitado sumiu junto com o replanejamento que falhou')


def test_excluir_tarefa_replaneja_a_curva():
    """`excluir_tarefa` — depois do recálculo pós-exclusão.

    Excluir reflui as ex-sucessoras, e as datas que mudam são exatamente as
    que a curva planejada dos apontamentos já gravados estava fotografando.
    """
    _admin, obra, _t, ap = _cenario()
    _pint, acab = _vizinhas(obra, _admin)
    cli = _client_v2(ap.admin_id)

    r = cli.delete(f'/cronograma/obra/{obra.id}/tarefa/{acab.id}')
    assert r.status_code == 200, f'a rota respondeu {r.status_code}: {r.data[:300]}'

    assert _planejado(ap) == pytest.approx(60.0), (
        'excluir tarefa não replanejou a curva')


def test_excluir_tarefa_com_ciclo_preexistente_nao_replaneja():
    """Risco 2 da B2.20 — o `except ErroCiclo` que **não retorna**.

    🔬 Em `excluir_tarefa` o `except` do recálculo pós-exclusão só faz
    `rollback()` + `logger.warning` e **deixa o fluxo seguir**. Uma chamada
    incondicional depois do bloco replanejaria por cima de um recálculo que
    foi abortado e revertido — gravaria uma curva planejada derivada de datas
    que o rollback acabou de descartar. Por isso a chamada é guardada por um
    sinalizador levantado DENTRO do `try`.

    O ciclo é semeado direto no banco (A→B e B→A): a rota de vínculo recusaria
    o segundo, e é assim mesmo que o dado sujo pré-existente chega em produção.
    """
    from models import TarefaVinculo

    _admin, obra, _t, ap = _cenario()
    pint, acab = _vizinhas(obra, _admin)
    for pred, suc in ((pint.id, acab.id), (acab.id, pint.id)):
        db.session.add(TarefaVinculo(admin_id=ap.admin_id, obra_id=obra.id,
                                     predecessora_id=pred, sucessora_id=suc,
                                     tipo='TI', lag_dias=0))
    db.session.commit()

    # Uma terceira folha, fora do ciclo, para ser a excluída.
    alvo = _tarefa(obra, _admin, 'Limpeza', ordem=3, duracao_dias=2,
                   data_inicio=date(2026, 7, 29), data_fim=date(2026, 7, 30))
    cli = _client_v2(ap.admin_id)

    r = cli.delete(f'/cronograma/obra/{obra.id}/tarefa/{alvo.id}')
    assert r.status_code == 200, f'a rota respondeu {r.status_code}: {r.data[:300]}'

    assert _planejado(ap) == pytest.approx(99.0), (
        'o replanejamento rodou por cima de um recálculo abortado — o '
        'except ErroCiclo de excluir_tarefa faz rollback e SEGUE, então a '
        'chamada precisa de um sinalizador levantado dentro do try')


def test_recalcular_replaneja_a_curva():
    """`/recalcular` — o **gatilho manual**.

    É a única rota que conserta dado velho sem exigir uma edição: sem ela, uma
    obra cuja curva envelheceu antes do A06 não teria como ser reparada pela
    UI.
    """
    _admin, obra, _t, ap = _cenario()
    cli = _client_v2(ap.admin_id)

    r = cli.post(f'/cronograma/obra/{obra.id}/recalcular')
    assert r.status_code == 200, f'a rota respondeu {r.status_code}: {r.data[:300]}'

    assert _planejado(ap) == pytest.approx(60.0), (
        '/recalcular não replanejou — é o gatilho manual, e sem ele um dado '
        'velho fica sem conserto')


def test_recalcular_no_ramo_legado_tambem_replaneja():
    """`/recalcular` com o editor v2 DESLIGADO.

    O ramo legado devolve 500 quando o recálculo falha, então tudo que passa
    do if/else é sucesso — a chamada depois dele cobre os dois ramos com uma
    linha. Este teste é o que impede que ela seja escondida dentro de um
    `if flag_on`, o que deixaria o parque não migrado sem o conserto.
    """
    _admin, obra, _t, ap = _cenario()
    cli = _client_v2(ap.admin_id, flag=False)

    r = cli.post(f'/cronograma/obra/{obra.id}/recalcular')
    assert r.status_code == 200, f'a rota respondeu {r.status_code}: {r.data[:300]}'

    assert _planejado(ap) == pytest.approx(60.0), (
        'o ramo legado de /recalcular não replanejou a curva')


# ---------------------------------------------------------------------------
# B2.19, teste 3 — o CUSTO
# ---------------------------------------------------------------------------

def test_editar_tarefa_nao_dispara_avalanche_de_queries():
    """O teto que trava a volta dos dois `calcular_progresso_geral_obra_v2`.

    🔬 **Este teste faltava, e quem apontou foi o agente que executou a B2.20** —
    a tabela da B2.19 o lista como "teste 3 — o custo" e ele não foi escrito na
    entrega de `318b294d`. Registrado aqui em vez de esquecido.

    Por que ele importa: `replanejar_curvas_obra` no modo cheio faz DUAS
    varreduras da obra inteira só para montar `progresso_antes`/`progresso_depois`.
    O editor v2 chama o replanejamento **a cada edição de data**. Se alguém um dia
    trocar `com_relatorio=False` por `True` "para ter o relatório", a tela fica
    lenta de um jeito que nenhum teste funcional acusa — todos continuariam
    verdes.

    🔬 **O teto de 60 que o recorte sugeria NÃO distinguia nada, e a sabotagem
    cobrou.** Medido neste cenário: **39 queries** com `com_relatorio=False` e
    **49** com `True` — as duas abaixo de 60, então o teste passava dos dois
    jeitos e era decoração. O teto é **45**, que fica entre os dois valores
    medidos.

    Um teto tão justo tem um custo honesto: se a semente deste arquivo crescer,
    ele pode ficar vermelho sem que nada tenha regredido. É preferível a um teto
    que nunca acusa — e o vermelho, se vier, é uma linha para reajustar com uma
    nova medição, não um mistério.
    """
    from sqlalchemy import event as sa_event

    _admin, obra, t, _ap = _cenario()
    admin_id = t.admin_id
    cli = _client_v2(admin_id)

    contador = {'n': 0}

    def _conta(conn, cursor, statement, params, context, executemany):
        contador['n'] += 1

    sa_event.listen(db.engine, 'before_cursor_execute', _conta)
    try:
        r = cli.put(f'/cronograma/obra/{obra.id}/tarefa/{t.id}',
                    json={'duracao_dias': 30})
    finally:
        sa_event.remove(db.engine, 'before_cursor_execute', _conta)

    assert r.status_code == 200, f'a rota respondeu {r.status_code}'
    assert contador['n'] < 45, (
        f'{contador["n"]} queries numa edição de UMA tarefa. Medido: 39 com o '
        f'modo enxuto e 49 com o relatório ligado — estourar 45 significa que as '
        f'duas varreduras de calcular_progresso_geral_obra_v2 voltaram ao '
        f'caminho do editor')
