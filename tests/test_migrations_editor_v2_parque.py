"""Migração 270 — editor de cronograma v2 ligado em todo o parque (03/08/2026).

O que precisa valer, na ordem em que importa:

  * **a linha de base vem ANTES da flag.** É a única apólice contra o
    recálculo em cascata do motor novo, que desligar a flag não desfaz. Um
    teste aqui prova que a obra datada saiu da migração congelada;
  * a flag fica ligada em TODOS os tenants, inclusive nos que não tinham
    linha de `configuracao_empresa` (esses ganham uma);
  * quem já tinha linha de base ativa **não** é recongelado — senão o
    "planejado" viraria a foto de hoje e o desvio zeraria;
  * idempotência: rodar duas vezes não duplica nada;
  * o default da coluna virou TRUE, para a empresa cadastrada amanhã nascer
    no formato novo.

Integração de verdade: a migração é global por natureza (varre o banco
inteiro), então cada teste cria seu próprio tenant isolado por sufixo e
afirma apenas sobre ele — mais o efeito de tabela toda, que é o ponto.
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
    ConfiguracaoEmpresa,
    CronogramaBaseline,
    CronogramaBaselineItem,
    Obra,
    TarefaCronograma,
    TipoUsuario,
    Usuario,
)
from migrations import _migration_270_editor_v2_em_todo_o_parque as migrar_270

pytestmark = pytest.mark.integration

SENHA = 'Senha@2026'


def _suf() -> str:
    return f'{datetime.utcnow().strftime("%H%M%S%f")}_{uuid.uuid4().hex[:6]}'


def _ambiente(com_config=True, flag=False, versao='v2'):
    """admin + cliente + obra novos e isolados. `com_config=False` simula o
    tenant que nunca abriu a tela de configurações da empresa."""
    suf = _suf()
    admin = Usuario(
        username=f'e2p_{suf}',
        email=f'e2p_{suf}@test.local',
        nome=f'Admin Parque {suf}',
        password_hash=generate_password_hash(SENHA),
        tipo_usuario=TipoUsuario.ADMIN,
        ativo=True,
        versao_sistema=versao,
    )
    db.session.add(admin)
    db.session.flush()

    if com_config:
        db.session.add(ConfiguracaoEmpresa(
            admin_id=admin.id,
            nome_empresa=f'Empresa Parque {suf}',
            cronograma_editor_v2=flag))

    cliente = Cliente(
        admin_id=admin.id,
        nome=f'Cliente {suf}',
        email=f'cli_{suf}@test.local',
        telefone='11988887777',
    )
    db.session.add(cliente)
    db.session.flush()

    obra = Obra(
        nome=f'Obra Parque {suf}',
        codigo=f'E2P-{suf[:11]}',
        admin_id=admin.id,
        cliente_id=cliente.id,
        status='Em andamento',
        data_inicio=date(2026, 7, 1),
    )
    db.session.add(obra)
    db.session.commit()
    return admin, obra


def _tarefa(obra, admin, nome, ordem=0, datada=True, is_cliente=False):
    t = TarefaCronograma(
        obra_id=obra.id,
        admin_id=admin.id,
        nome_tarefa=nome,
        ordem=ordem,
        duracao_dias=5 if datada else None,
        data_inicio=date(2026, 7, 1) if datada else None,
        data_fim=date(2026, 7, 7) if datada else None,
        is_cliente=is_cliente,
    )
    db.session.add(t)
    db.session.commit()
    return t


def _config(admin_id):
    return ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()


def _baselines(obra_id, ativa=True):
    return (CronogramaBaseline.query
            .filter_by(obra_id=obra_id, is_cliente=False, ativa=ativa)
            .all())


@pytest.fixture(autouse=True)
def _config_app():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-migr-editor-v2-parque'
    with app.app_context():
        yield


# ---------------------------------------------------------------------------
# O passo que não pode inverter: congelar antes de ligar
# ---------------------------------------------------------------------------

def test_congela_a_linha_de_base_e_liga_a_flag():
    admin, obra = _ambiente(flag=False)
    a = _tarefa(obra, admin, 'Fundação')
    b = _tarefa(obra, admin, 'Estrutura', ordem=1)

    migrar_270()

    linhas = _baselines(obra.id)
    assert len(linhas) == 1, 'a obra datada tinha de sair com UMA linha de base ativa'
    itens = CronogramaBaselineItem.query.filter_by(baseline_id=linhas[0].id).all()
    assert {i.tarefa_id for i in itens} == {a.id, b.id}
    congelado = {i.tarefa_id: (i.data_inicio, i.data_fim, i.duracao_dias)
                 for i in itens}
    assert congelado[a.id] == (a.data_inicio, a.data_fim, a.duracao_dias)
    assert linhas[0].admin_id == admin.id

    db.session.expire_all()
    assert _config(admin.id).cronograma_editor_v2 is True


def test_obra_sem_datas_nao_gera_linha_de_base_mas_o_tenant_liga():
    """Sem datas não há o que congelar — e também não há o que o recálculo
    reescreva. O tenant entra no formato novo do mesmo jeito."""
    admin, obra = _ambiente(flag=False)
    _tarefa(obra, admin, 'Sem datas', datada=False)

    migrar_270()

    assert _baselines(obra.id) == []
    db.session.expire_all()
    assert _config(admin.id).cronograma_editor_v2 is True


def test_cronograma_do_cliente_fica_fora_do_congelamento():
    """A linha de base é do plano INTERNO — o do cliente é outro conjunto de
    tarefas (mesma disciplina da 266)."""
    admin, obra = _ambiente(flag=False)
    interna = _tarefa(obra, admin, 'Interna')
    _tarefa(obra, admin, 'Do cliente', ordem=1, is_cliente=True)

    migrar_270()

    (linha,) = _baselines(obra.id)
    itens = CronogramaBaselineItem.query.filter_by(baseline_id=linha.id).all()
    assert {i.tarefa_id for i in itens} == {interna.id}


def test_linha_de_base_existente_nao_e_recongelada():
    """Recongelar apagaria o planejado do tenant e zeraria o desvio."""
    admin, obra = _ambiente(flag=False)
    t = _tarefa(obra, admin, 'Já tinha plano')

    antiga = CronogramaBaseline(obra_id=obra.id, admin_id=admin.id,
                                nome='Plano de junho', ativa=True,
                                is_cliente=False)
    db.session.add(antiga)
    db.session.flush()
    db.session.add(CronogramaBaselineItem(
        baseline_id=antiga.id, tarefa_id=t.id, admin_id=admin.id,
        data_inicio=date(2026, 6, 1), data_fim=date(2026, 6, 10),
        duracao_dias=8))
    db.session.commit()

    migrar_270()

    linhas = _baselines(obra.id)
    assert len(linhas) == 1 and linhas[0].id == antiga.id
    (item,) = CronogramaBaselineItem.query.filter_by(baseline_id=antiga.id).all()
    assert (item.data_inicio, item.data_fim) == (date(2026, 6, 1), date(2026, 6, 10))


# ---------------------------------------------------------------------------
# "Todos" inclui quem não tinha linha de configuração
# ---------------------------------------------------------------------------

def test_tenant_com_cronograma_e_sem_configuracao_ganha_uma_ligada():
    admin, obra = _ambiente(com_config=False)
    _tarefa(obra, admin, 'Fundação')
    assert _config(admin.id) is None

    migrar_270()

    db.session.expire_all()
    config = _config(admin.id)
    assert config is not None, 'tenant com cronograma ficaria fora do "todos"'
    assert config.cronograma_editor_v2 is True
    assert config.nome_empresa  # NOT NULL — precisa ter saído preenchido


def test_tenant_sem_cronograma_nao_ganha_configuracao_inventada():
    admin, _obra = _ambiente(com_config=False)  # obra sem nenhuma tarefa

    migrar_270()

    db.session.expire_all()
    assert _config(admin.id) is None


def test_flag_ja_ligada_continua_ligada():
    admin, obra = _ambiente(flag=True)
    _tarefa(obra, admin, 'Fundação')

    migrar_270()

    db.session.expire_all()
    assert _config(admin.id).cronograma_editor_v2 is True


def test_tenant_v1_liga_a_flag_mesmo_inerte():
    """`cronograma_editor_v2_ativo` exige V2 **e** a flag. A migração não
    troca a versão do sistema de ninguém — só deixa a flag pronta."""
    admin, obra = _ambiente(flag=False, versao='v1')
    _tarefa(obra, admin, 'Fundação')

    migrar_270()

    db.session.expire_all()
    assert _config(admin.id).cronograma_editor_v2 is True


# ---------------------------------------------------------------------------
# Idempotência e schema
# ---------------------------------------------------------------------------

def test_rodar_duas_vezes_nao_duplica_nada():
    admin, obra = _ambiente(flag=False)
    a = _tarefa(obra, admin, 'Fundação')

    migrar_270()
    (linha,) = _baselines(obra.id)
    itens_1 = CronogramaBaselineItem.query.filter_by(baseline_id=linha.id).count()

    migrar_270()

    linhas = _baselines(obra.id)
    assert len(linhas) == 1 and linhas[0].id == linha.id
    assert CronogramaBaselineItem.query.filter_by(baseline_id=linha.id).count() == itens_1
    assert CronogramaBaselineItem.query.filter_by(tarefa_id=a.id).count() == 1
    assert ConfiguracaoEmpresa.query.filter_by(admin_id=admin.id).count() == 1


def test_default_da_coluna_virou_true():
    """Sem isto o "todos" duraria até a próxima empresa cadastrada."""
    from sqlalchemy import text as sa_text

    migrar_270()
    with db.engine.connect() as conn:
        linha = conn.execute(sa_text("""
            SELECT is_nullable, column_default FROM information_schema.columns
             WHERE table_name = 'configuracao_empresa'
               AND column_name = 'cronograma_editor_v2'
        """)).fetchone()
    assert linha is not None
    assert linha[0] == 'NO'
    assert 'true' in str(linha[1]).lower()


def test_nenhum_tenant_fica_desligado():
    """A prova que a própria migração faz — repetida aqui porque é o
    enunciado do pedido de 03/08."""
    migrar_270()
    assert ConfiguracaoEmpresa.query.filter(
        ConfiguracaoEmpresa.cronograma_editor_v2.isnot(True)).count() == 0
