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


def _client_v2(admin_id):
    """Cliente autenticado com o editor v2 LIGADO no tenant.

    A flag mora numa coluna de `ConfiguracaoEmpresa` — mesmo helper da Fase 1,
    usado por `tests/test_cronograma_grade_api.py`.
    """
    from models import ConfiguracaoEmpresa

    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    if config is None:
        config = ConfiguracaoEmpresa(admin_id=admin_id,
                                     nome_empresa=f'Empresa {admin_id}')
        db.session.add(config)
    config.cronograma_editor_v2 = True
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
