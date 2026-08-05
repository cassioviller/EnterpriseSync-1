"""A19 — a família V1 de progresso converge num ponto só.

**Sete geradores respondiam "qual o progresso V1 desta obra"**, cada um de um
jeito diferente, para tela, lista, card e PDF. Este arquivo é o arreio da
convergência: primeiro as duas funções novas do engine (B2.7), depois cada
call-site que passa a chamá-las.

**O que cada variante errava, e que este arquivo trava:**

* **não-monotonicidade** — três variantes usavam "o percentual do RDO mais
  recente". Apontador corrige 60% para 50% e o progresso da OBRA cai, embora
  nada tenha sido desfeito;
* **homônimos colapsados** — agrupar só por `nome_subatividade` funde
  "Alvenaria" de dois serviços diferentes numa chave só e sub-conta o
  denominador;
* **sem teto de data** — cache por `obra_id` sem `ate_data` faz toda linha de
  uma lista de RDOs mostrar o número de hoje;
* **sem `admin_id`** — duas variantes consultavam `RDO` sem filtrar tenant;
* **predicado V2 frouxo** — quatro predicados vivos, nenhum filtrando `ativa` e
  `is_cliente`. Uma tarefa cópia-cliente joga o PDF para V2 enquanto a tela do
  mesmo RDO fica em V1.
"""
import os
import sys
import uuid
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import RDO, RDOServicoSubatividade, Servico, TarefaCronograma
from utils.cronograma_engine import obra_em_modo_v2, progresso_v1_acumulado

from helpers_tenant import um_tenant

pytestmark = pytest.mark.integration

DIA = date(2026, 6, 15)


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    if not app.secret_key:
        app.secret_key = 'test-a19'
    yield


def _servico(t, nome):
    s = Servico(nome=f'{nome} {t.marca}', categoria='geral',
                unidade_medida='m2', custo_unitario=10.0, ativo=True,
                admin_id=t.admin_id)
    db.session.add(s)
    db.session.flush()
    return s


def _rdo(t, dia):
    r = RDO(numero_rdo=f'RDO-{uuid.uuid4().hex[:8]}', obra_id=t.obra_id,
            data_relatorio=dia, admin_id=t.admin_id,
            criado_por_id=t.admin_id)
    db.session.add(r)
    db.session.flush()
    return r


def _sub(rdo, t, servico, nome, pct):
    db.session.add(RDOServicoSubatividade(
        rdo_id=rdo.id, servico_id=servico.id if servico else None,
        nome_subatividade=nome, percentual_conclusao=pct,
        admin_id=t.admin_id))


# ---------------------------------------------------------------------------
# progresso_v1_acumulado
# ---------------------------------------------------------------------------

def test_correcao_para_baixo_nao_derruba_o_progresso_da_obra():
    """O defeito que motiva o MAX, e o que mais dói de explicar ao cliente.

    Três variantes usavam "o percentual do RDO mais recente". Apontador lança
    60% na segunda-feira e corrige para 50% na terça — nada foi desfeito na
    obra, mas o progresso EXIBIDO cai. Com MAX ele fica em 60 e sobe quando
    subir de verdade.
    """
    with app.app_context():
        t = um_tenant('a19mono', data_ref=DIA, com_fatos=False)
        s = _servico(t, 'Alvenaria')

        r1 = _rdo(t, date(2026, 6, 15))
        _sub(r1, t, s, 'Assentamento', 60.0)
        r2 = _rdo(t, date(2026, 6, 16))
        _sub(r2, t, s, 'Assentamento', 50.0)
        db.session.commit()

        p = progresso_v1_acumulado(t.obra_id, t.admin_id, date(2026, 6, 16))
        assert p == pytest.approx(60.0), (
            f'progresso deu {p} — com "último por data" a correção de 60 para '
            f'50 derruba o número da obra, e nada foi desfeito')


def test_homonimos_de_servicos_diferentes_nao_colapsam():
    """Agrupar só por nome funde duas subatividades distintas numa chave.

    "Acabamento" existe em Alvenaria e em Pintura, e são trabalhos diferentes.
    Com chave só por nome, as duas viram uma: o MAX pega 80 e a média dá 80.
    Com a chave composta são duas chaves, e a média é 50.
    """
    with app.app_context():
        t = um_tenant('a19hom', data_ref=DIA, com_fatos=False)
        alvenaria = _servico(t, 'Alvenaria')
        pintura = _servico(t, 'Pintura')

        r = _rdo(t, DIA)
        _sub(r, t, alvenaria, 'Acabamento', 80.0)
        _sub(r, t, pintura, 'Acabamento', 20.0)
        db.session.commit()

        p = progresso_v1_acumulado(t.obra_id, t.admin_id, DIA)
        assert p == pytest.approx(50.0), (
            f'progresso deu {p} — 80.0 é o sintoma do colapso de homônimos: '
            f'as duas subatividades viraram uma chave só')


def test_o_teto_de_data_e_respeitado():
    """Sem `ate_data`, toda linha de uma lista de RDOs mostra o número de hoje.

    A variante da lista cacheava por `obra_id` e não por (obra, data): o RDO de
    segunda exibia o progresso de sexta. Aqui, olhando o dia 15, o apontamento
    do dia 16 não pode existir ainda.
    """
    with app.app_context():
        t = um_tenant('a19data', data_ref=DIA, com_fatos=False)
        s = _servico(t, 'Estrutura')

        r1 = _rdo(t, date(2026, 6, 15))
        _sub(r1, t, s, 'Pilar', 30.0)
        r2 = _rdo(t, date(2026, 6, 16))
        _sub(r2, t, s, 'Pilar', 90.0)
        db.session.commit()

        assert progresso_v1_acumulado(
            t.obra_id, t.admin_id, date(2026, 6, 15)) == pytest.approx(30.0)
        assert progresso_v1_acumulado(
            t.obra_id, t.admin_id, date(2026, 6, 16)) == pytest.approx(90.0)


def test_o_progresso_v1_nao_atravessa_tenants():
    """Duas das sete variantes consultavam `RDO` sem filtrar `admin_id`.

    🔬 **A primeira versão deste teste era vacuosa, e a sabotagem cobrou.** Ela
    semeava o RDO na OBRA de B: como a consulta já filtra `RDO.obra_id`,
    remover o `admin_id` não mudava nada — o teste passava com e sem o filtro
    que dizia estar provando.

    O cenário certo é o RDO **na obra de A com `admin_id` de B**, e ele não é
    hipotético: a FK de `RDO.obra_id` não conhece fronteira de tenant, que é o
    mesmo buraco pelo qual `ServicoObraReal` apontava para catálogo alheio na
    B1.12. Sem o filtro, o apontamento de 100% de B entra na média de A.
    """
    with app.app_context():
        a = um_tenant('a19tA', data_ref=DIA, com_fatos=False)
        b = um_tenant('a19tB', data_ref=DIA, com_fatos=False)
        s_a = _servico(a, 'Alvenaria')
        s_b = _servico(b, 'Alvenaria')

        # O apontamento legítimo de A: 20%.
        r_a = _rdo(a, DIA)
        _sub(r_a, a, s_a, 'Assentamento', 20.0)

        # RDO com a obra de A e o tenant de B — o que a FK permite.
        r_b = RDO(numero_rdo=f'RDO-{uuid.uuid4().hex[:8]}', obra_id=a.obra_id,
                  data_relatorio=DIA, admin_id=b.admin_id,
                  criado_por_id=b.admin_id)
        db.session.add(r_b)
        db.session.flush()
        _sub(r_b, b, s_b, 'Assentamento de B', 100.0)
        db.session.commit()

        p = progresso_v1_acumulado(a.obra_id, a.admin_id, DIA)
        assert p == pytest.approx(20.0), (
            f'progresso de A deu {p} — 60.0 é a média com o apontamento de B '
            f'dentro, e é o que acontece sem o filtro de admin_id')


def test_obra_sem_apontamento_v1_esta_em_zero():
    """Zero, e não "não sei": obra sem RDO V1 tem progresso V1 nulo."""
    with app.app_context():
        t = um_tenant('a19vazio', data_ref=DIA, com_fatos=False)
        assert progresso_v1_acumulado(t.obra_id, t.admin_id, DIA) == 0.0


# ---------------------------------------------------------------------------
# obra_em_modo_v2
# ---------------------------------------------------------------------------

def _tarefa(t, nome, *, ativa=True, is_cliente=False):
    tar = TarefaCronograma(
        obra_id=t.obra_id, admin_id=t.admin_id,
        nome_tarefa=f'{nome} {t.marca}', ordem=1, duracao_dias=1,
        percentual_concluido=0.0, ativa=ativa, is_cliente=is_cliente)
    db.session.add(tar)
    db.session.flush()
    return tar


def test_copia_cliente_sozinha_nao_poe_a_obra_em_v2(monkeypatch):
    """O defeito de verdade dos quatro predicados: a cópia-cliente conta.

    `is_cliente=True` é o cronograma que o cliente enxerga, e ele NUNCA recebe
    sincronização de percentual. Bastava uma tarefa dessas para o PDF do RDO ir
    para V2 enquanto a tela do mesmo RDO ficava em V1 — mesma obra, mesmo dia,
    dois números, e o PDF é o documento que o cliente assina.
    """
    import utils.cronograma_engine as eng
    monkeypatch.setattr('utils.tenant.is_v2_active', lambda: True)

    with app.app_context():
        t = um_tenant('a19cli', data_ref=DIA, com_fatos=False)
        _tarefa(t, 'Só do cliente', is_cliente=True)
        db.session.commit()

        assert eng.obra_em_modo_v2(t.obra_id, t.admin_id) is False, (
            'uma tarefa cópia-cliente, sozinha, pôs a obra em V2 — é o '
            'predicado frouxo que os quatro call-sites usavam')


def test_tarefa_arquivada_sozinha_nao_poe_a_obra_em_v2(monkeypatch):
    """`ativa=False` é tarefa removida por reimportação, preservada por
    disciplina do M05. Ela não caracteriza obra em V2."""
    import utils.cronograma_engine as eng
    monkeypatch.setattr('utils.tenant.is_v2_active', lambda: True)

    with app.app_context():
        t = um_tenant('a19arq', data_ref=DIA, com_fatos=False)
        _tarefa(t, 'Arquivada', ativa=False)
        db.session.commit()

        assert eng.obra_em_modo_v2(t.obra_id, t.admin_id) is False


def test_tarefa_interna_e_viva_poe_a_obra_em_v2(monkeypatch):
    """O caso positivo — sem ele os dois de cima passariam com um `return
    False` fixo, e o teste inteiro seria vacuoso."""
    import utils.cronograma_engine as eng
    monkeypatch.setattr('utils.tenant.is_v2_active', lambda: True)

    with app.app_context():
        t = um_tenant('a19viva', data_ref=DIA, com_fatos=False)
        _tarefa(t, 'Interna viva')
        db.session.commit()

        assert eng.obra_em_modo_v2(t.obra_id, t.admin_id) is True


def test_sem_a_flag_do_tenant_a_obra_nunca_esta_em_v2(monkeypatch):
    """Três dos quatro predicados nem consultavam `is_v2_active()`."""
    import utils.cronograma_engine as eng
    monkeypatch.setattr('utils.tenant.is_v2_active', lambda: False)

    with app.app_context():
        t = um_tenant('a19flag', data_ref=DIA, com_fatos=False)
        _tarefa(t, 'Interna viva')
        db.session.commit()

        assert eng.obra_em_modo_v2(t.obra_id, t.admin_id) is False
