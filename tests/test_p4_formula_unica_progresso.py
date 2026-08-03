"""p4 — uma fórmula de progresso, não cinco.

O sistema tinha cinco maneiras de responder "quanto da obra está pronta", e
elas discordavam entre si:

1. `portal_obras_views.gerar_medicao` — média simples das tarefas da empresa.
   **Esta virava dinheiro** (`valor_medido = valor_contrato × perc`);
2. `views/dashboard.py` — média das subatividades do ÚLTIMO RDO;
3. `views/dashboard.py` (derivado) — média das obras;
4. `cronograma_views.index` — `AVG` em SQL sobre TODAS as tarefas, incluindo
   a cópia-cliente e as tarefas-pai;
5. `templates/obras/cronograma.html` — média simples em Jinja, no modo
   cliente.

O ponto único é `utils/cronograma_engine`: folhas, ponderadas por duração (ou
por quantidade, quando todas a têm).

O teste que define o pacote é o de **convergência**: a mesma obra, o mesmo
número, em todos os lugares que o exibem.
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import TarefaCronograma
from helpers_tenant import dois_tenants
from utils.cronograma_engine import (calcular_progresso_geral_obra_v2,
                                     progresso_ponderado_armazenado)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    if not app.secret_key:
        app.secret_key = 'test-p4'
    with app.app_context():
        yield


def _tenant():
    a, _b = dois_tenants('p4')
    return a


def _tarefa(t, nome, pct, duracao, pai_id=None, is_cliente=False,
            responsavel='empresa', ordem=0):
    tarefa = TarefaCronograma(
        obra_id=t.obra_id, admin_id=t.admin_id, nome_tarefa=nome, ordem=ordem,
        duracao_dias=duracao, data_inicio=date(2026, 6, 1),
        data_fim=date(2026, 6, 1 + min(duracao, 27)),
        percentual_concluido=pct, tarefa_pai_id=pai_id,
        is_cliente=is_cliente, responsavel=responsavel, ativa=True)
    db.session.add(tarefa)
    db.session.commit()
    return tarefa


def _pct(t, **kw):
    """A forma única sobre a coluna gravada — a fonte que a medição usa."""
    return progresso_ponderado_armazenado(t.obra_id, t.admin_id, **kw)


def _pct_motor(t, **kw):
    """O motor, que deriva de apontamento de RDO. Fonte diferente: tarefa sem
    apontamento conta 0, por desenho."""
    return calcular_progresso_geral_obra_v2(
        t.obra_id, date.today(), t.admin_id, **kw)['progresso_geral_pct']


# ---------------------------------------------------------------------------
# A fórmula
# ---------------------------------------------------------------------------

def test_tarefa_longa_pesa_mais_que_tarefa_curta():
    """A média simples dava o mesmo peso a 1 dia e a 40 — era o defeito que
    virava dinheiro no portal."""
    t = _tenant()
    _tarefa(t, 'Curta pronta', 100, 1)
    _tarefa(t, 'Longa parada', 0, 39, ordem=1)

    # média simples daria 50%; ponderada por duração dá 2,5%
    assert _pct(t) == pytest.approx(2.5, abs=0.1)


def test_tarefa_pai_nao_conta_junto_com_as_filhas():
    """O pai entra com o próprio percentual e as filhas entram de novo —
    dupla contagem que inflava etapa com muitas subtarefas."""
    t = _tenant()
    pai = _tarefa(t, 'Etapa', 100, 10)
    _tarefa(t, 'Filha A', 0, 5, pai_id=pai.id, ordem=1)
    _tarefa(t, 'Filha B', 0, 5, pai_id=pai.id, ordem=2)

    assert _pct(t) == pytest.approx(0.0, abs=0.1)


def test_a_copia_cliente_nao_dilui_o_numero_da_empresa():
    t = _tenant()
    _tarefa(t, 'Interna pronta', 100, 10)
    _tarefa(t, 'Do cliente parada', 0, 10, is_cliente=True, ordem=1)

    assert _pct(t) == pytest.approx(100.0, abs=0.1)


# ---------------------------------------------------------------------------
# O escopo que a medição precisa — e que fez alguém reimplementar a fórmula
# ---------------------------------------------------------------------------

def test_o_motor_aceita_escopo_por_responsavel():
    """Sem este parâmetro, o portal tinha de reimplementar tudo para manter o
    `responsavel='empresa'` — e foi assim que nasceu a média simples."""
    t = _tenant()
    _tarefa(t, 'Da empresa', 100, 10, responsavel='empresa')
    _tarefa(t, 'Do cliente', 0, 10, responsavel='cliente', ordem=1)

    assert _pct(t, responsavel='empresa') == pytest.approx(100.0, abs=0.1)
    assert _pct(t) == pytest.approx(50.0, abs=0.1)


def test_medicao_do_portal_usa_o_mesmo_numero():
    """O critério de pronto do p4, no call-site que vira dinheiro."""
    t = _tenant()
    _tarefa(t, 'Curta pronta', 100, 1)
    _tarefa(t, 'Longa parada', 0, 39, ordem=1)

    esperado = _pct(t, responsavel='empresa')

    fonte = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'portal_obras_views.py')
    with open(fonte, encoding='utf-8') as fh:
        texto = fh.read()
    assert 'progresso_ponderado_armazenado' in texto, (
        'gerar_medicao voltou a calcular progresso por conta própria')
    assert "responsavel='empresa'" in texto
    assert esperado == pytest.approx(2.5, abs=0.1)


# ---------------------------------------------------------------------------
# As fórmulas que sumiram
# ---------------------------------------------------------------------------

def test_o_template_nao_calcula_mais_progresso():
    """A quinta fórmula estava escondida numa expressão Jinja — só aparecia no
    modo cliente, onde o servidor mandava None."""
    caminho = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'templates', 'obras', 'cronograma.html')
    with open(caminho, encoding='utf-8') as fh:
        texto = fh.read()
    assert 'set perc_total' not in texto


def test_o_dashboard_nao_usa_mais_a_media_do_ultimo_rdo():
    caminho = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'views', 'dashboard.py')
    with open(caminho, encoding='utf-8') as fh:
        texto = fh.read()
    assert 'total_percentual / total_sub' not in texto, (
        'o dashboard voltou a calcular a média das subatividades do último RDO')
    assert 'progresso_geral_para_kpi' in texto


def test_o_indice_do_cronograma_ignora_pais_e_copia_cliente():
    caminho = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'cronograma_views.py')
    with open(caminho, encoding='utf-8') as fh:
        texto = fh.read()
    assert 'sqlfunc.avg(TarefaCronograma.percentual_concluido)' not in texto, (
        'o índice voltou a fazer AVG sobre todas as tarefas'
    )


def test_a_medicao_nao_zera_obra_que_avanca_sem_apontamento_de_rdo():
    """O motor conta 0 para tarefa sem apontamento — trocar a fonte embaixo da
    medição zeraria toda obra que registra avanço por import ou pela grade.
    Este teste existe para que a troca não aconteça por engano."""
    t = _tenant()
    _tarefa(t, 'Importada 80%', 80, 10)

    assert _pct(t) == pytest.approx(80.0, abs=0.1)
    assert _pct_motor(t) == pytest.approx(0.0, abs=0.1), (
        'se o motor passou a ler a coluna gravada, esta distinção acabou — '
        'reveja o p8 e o comentário em portal_obras_views.gerar_medicao')
