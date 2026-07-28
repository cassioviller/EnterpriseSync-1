"""Pai de custo só é apagado quando fica SEM FILHO — não quando a soma zera.

`remover_custos_rdo` (services/rdo_custos.py) e `_limpar_gestao_custo_filho`
(transporte_views.py) apagam o `GestaoCustoPai` que "não tem mais filhos".
Os dois testavam isso pela SOMA dos filhos restantes, e soma zero não é
ausência de filho: um estorno negativo ou um lançamento de valor 0 zera a
soma com filhos vivos.

Como `GestaoCustoPai.itens` (models.py:6270) é `cascade='all, delete-orphan'`,
apagar o pai leva junto TODOS os filhos — inclusive os de outras origens.
Medido antes da correção: remover 1 filho de um pai com 3 apagava os 3, dois
deles vindos de `importacao_custos`, sem relação com o RDO.

Em dev nenhum filho tem valor <= 0, então o atalho acertava por convenção de
dados. Este teste transforma a convenção em invariante do código.
"""
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints antes de qualquer request
from app import app, db
from models import (Cliente, Funcionario, GestaoCustoFilho, GestaoCustoPai,
                    Obra, RDO, RDOMaoObra, TipoUsuario, Usuario)
from services.rdo_custos import remover_custos_rdo

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-pai-zerado'
    yield


def _sfx():
    return uuid.uuid4().hex[:8]


def _cenario(valores_alheios):
    """RDO com 1 filho de custo + filhos de OUTRA origem no mesmo pai.

    Devolve (rdo_id, admin_id, pai_id, ids dos filhos alheios).
    """
    suf = _sfx()
    admin = Usuario(
        username=f'pz_{suf}', email=f'pz_{suf}@test.local',
        nome=f'Admin PZ {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
    db.session.add(admin)
    db.session.commit()

    cli = Cliente(nome=f'CLI-PZ-{suf}', admin_id=admin.id)
    db.session.add(cli)
    db.session.flush()
    obra = Obra(nome=f'Obra PZ {suf}', codigo=f'OPZ{suf[:6].upper()}',
                data_inicio=date(2026, 1, 1), admin_id=admin.id,
                cliente_id=cli.id, valor_contrato=100000)
    db.session.add(obra)
    db.session.commit()

    rdo = RDO(numero_rdo=f'RDO-PZ-{suf}', data_relatorio=date(2026, 6, 22),
              obra_id=obra.id, admin_id=admin.id, status='Finalizado')
    func = Funcionario(codigo=f'P{suf[:6].upper()}', nome=f'Pedreiro {suf}',
                       cpf=f'{suf[:3]}.{suf[3:6]}.{suf[:3]}-{suf[6:8]}',
                       data_admissao=date(2026, 1, 5), admin_id=admin.id)
    db.session.add_all([rdo, func])
    db.session.commit()

    mo = RDOMaoObra(rdo_id=rdo.id, admin_id=admin.id, funcionario_id=func.id,
                    funcao_exercida='Pedreiro', horas_trabalhadas=8.0)
    db.session.add(mo)
    db.session.commit()

    pai = GestaoCustoPai(tipo_categoria='MAO_OBRA_DIRETA',
                         entidade_nome=f'Ent {suf}', admin_id=admin.id,
                         obra_id=obra.id, status='PENDENTE')
    db.session.add(pai)
    db.session.flush()

    db.session.add(GestaoCustoFilho(
        pai_id=pai.id, admin_id=admin.id, obra_id=obra.id,
        data_referencia=date(2026, 6, 22), descricao='Do RDO',
        valor=Decimal('50.00'), origem_tabela='rdo_mao_obra', origem_id=mo.id))

    alheios = []
    for i, v in enumerate(valores_alheios):
        f = GestaoCustoFilho(
            pai_id=pai.id, admin_id=admin.id, obra_id=obra.id,
            data_referencia=date(2026, 6, 22), descricao=f'Alheio {i}',
            valor=Decimal(v), origem_tabela='importacao_custos', origem_id=0)
        db.session.add(f)
        alheios.append(f)
    db.session.commit()
    return rdo.id, admin.id, pai.id, [f.id for f in alheios]


def test_soma_zero_com_filhos_vivos_nao_apaga_o_pai():
    """O caso que destruía custo de terceiros: +30 e −30 somam zero."""
    with app.app_context():
        rid, aid, pai_id, alheios = _cenario(['30.00', '-30.00'])

        removidos = remover_custos_rdo(db.session.get(RDO, rid), aid)
        db.session.commit()

        assert removidos == 1, f'deveria remover só o filho do RDO, removeu {removidos}'
        assert db.session.get(GestaoCustoPai, pai_id) is not None, (
            'pai apagado com filhos vivos — os alheios foram junto pelo '
            'cascade delete-orphan')
        vivos = [i for i in alheios
                 if db.session.get(GestaoCustoFilho, i) is not None]
        assert len(vivos) == 2, (
            f'lançamentos de outra origem destruídos: sobraram {len(vivos)} de 2')


def test_pai_sem_filho_nenhum_continua_sendo_apagado():
    """A limpeza legítima não pode ter sido perdida no conserto."""
    with app.app_context():
        rid, aid, pai_id, _ = _cenario([])

        removidos = remover_custos_rdo(db.session.get(RDO, rid), aid)
        db.session.commit()

        assert removidos == 1
        assert db.session.get(GestaoCustoPai, pai_id) is None, (
            'pai sem filho nenhum deveria ter sido apagado')


def test_filho_de_valor_zero_tambem_segura_o_pai():
    """Soma zero por valor 0, sem negativo envolvido."""
    with app.app_context():
        rid, aid, pai_id, alheios = _cenario(['0.00'])

        remover_custos_rdo(db.session.get(RDO, rid), aid)
        db.session.commit()

        assert db.session.get(GestaoCustoPai, pai_id) is not None
        assert db.session.get(GestaoCustoFilho, alheios[0]) is not None


def _cenario_transporte(valores_alheios, lanc_id):
    """Mesmo cenário, com o filho vindo de `lancamento_transporte`.

    `_limpar_gestao_custo_filho` casa por (origem_tabela, origem_id, admin_id)
    — não precisa da linha de lançamento existir para exercitar a regra.
    """
    suf = _sfx()
    admin = Usuario(
        username=f'pt_{suf}', email=f'pt_{suf}@test.local',
        nome=f'Admin PT {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
    db.session.add(admin)
    db.session.commit()

    cli = Cliente(nome=f'CLI-PT-{suf}', admin_id=admin.id)
    db.session.add(cli)
    db.session.flush()
    obra = Obra(nome=f'Obra PT {suf}', codigo=f'OPT{suf[:6].upper()}',
                data_inicio=date(2026, 1, 1), admin_id=admin.id,
                cliente_id=cli.id, valor_contrato=100000)
    db.session.add(obra)
    db.session.commit()

    pai = GestaoCustoPai(tipo_categoria='TRANSPORTE',
                         entidade_nome=f'Ent {suf}', admin_id=admin.id,
                         obra_id=obra.id, status='PENDENTE')
    db.session.add(pai)
    db.session.flush()

    db.session.add(GestaoCustoFilho(
        pai_id=pai.id, admin_id=admin.id, obra_id=obra.id,
        data_referencia=date(2026, 6, 22), descricao='Do transporte',
        valor=Decimal('50.00'), origem_tabela='lancamento_transporte',
        origem_id=lanc_id))
    alheios = []
    for i, v in enumerate(valores_alheios):
        f = GestaoCustoFilho(
            pai_id=pai.id, admin_id=admin.id, obra_id=obra.id,
            data_referencia=date(2026, 6, 22), descricao=f'Alheio {i}',
            valor=Decimal(v), origem_tabela='importacao_custos', origem_id=0)
        db.session.add(f)
        alheios.append(f)
    db.session.commit()
    return admin.id, pai.id, [f.id for f in alheios]


def test_transporte_soma_zero_com_filhos_vivos_nao_apaga_o_pai():
    """Mesmo defeito, mesmo conserto, em transporte_views."""
    from transporte_views import _limpar_gestao_custo_filho

    with app.app_context():
        lanc_id = 987654321
        aid, pai_id, alheios = _cenario_transporte(['30.00', '-30.00'], lanc_id)

        _limpar_gestao_custo_filho(lanc_id, aid)
        db.session.commit()

        assert db.session.get(GestaoCustoPai, pai_id) is not None, (
            'pai apagado com filhos vivos — alheios foram junto pelo cascade')
        vivos = [i for i in alheios
                 if db.session.get(GestaoCustoFilho, i) is not None]
        assert len(vivos) == 2, f'sobraram {len(vivos)} de 2 lançamentos alheios'


def test_transporte_pai_sem_filho_continua_sendo_apagado():
    from transporte_views import _limpar_gestao_custo_filho

    with app.app_context():
        lanc_id = 987654322
        aid, pai_id, _ = _cenario_transporte([], lanc_id)

        _limpar_gestao_custo_filho(lanc_id, aid)
        db.session.commit()

        assert db.session.get(GestaoCustoPai, pai_id) is None
