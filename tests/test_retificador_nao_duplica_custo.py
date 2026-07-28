"""Retificar um RDO não pode contar a mão de obra duas vezes.

`criar_retificador` copia a mão de obra para o RDO novo e marca o original
como RETIFICADO. O custo do original ficava vivo: quando o retificador era
salvo, ele lançava o custo da MESMA jornada por cima. Medido antes da
correção: R$ 124,00 viravam R$ 248,00 no Realizado da obra.

`cancelar_custos_rdo` não serve aqui — ele cancela no nível do
`GestaoCustoPai`, e os dois RDOs alimentam o MESMO pai (o pai é por
entidade/categoria, não por RDO), então cancelar mataria junto o custo do
retificador. A remoção é por FILHO, casando `origem_tabela`/`origem_id` com
as linhas do original.
"""
import os
import sys
import uuid
from datetime import date

import pytest
from sqlalchemy import func as sqlfunc
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints antes de qualquer request
from app import app, db
from models import (Cliente, Funcionario, GestaoCustoFilho, GestaoCustoPai,
                    Obra, RDO, RDOMaoObra, TipoUsuario, Usuario)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-retificador'
    yield


def _sfx():
    return uuid.uuid4().hex[:8]


def _realizado(obra_id, admin_id):
    """Mesma soma de 'Realizado' de services/resumo_custos_obra.py."""
    from services.gestao_custos_query import sem_cancelados
    q = (db.session.query(sqlfunc.coalesce(sqlfunc.sum(GestaoCustoFilho.valor), 0))
         .join(GestaoCustoPai, GestaoCustoFilho.pai_id == GestaoCustoPai.id)
         .filter(GestaoCustoFilho.obra_id == obra_id)
         .filter(GestaoCustoPai.admin_id == admin_id))
    return float(sem_cancelados(q).scalar() or 0)


def _lancar_custos(rdo, admin_id):
    """O que os caminhos de salvamento do RDO fazem (rdo_editar_sistema:543-551)."""
    from services.custo_funcionario_dia import gravar_custo_funcionario_rdo
    from services.rdo_custos import gerar_custos_mao_obra_rdo
    gravar_custo_funcionario_rdo(rdo, admin_id)
    gerar_custos_mao_obra_rdo(rdo, admin_id)
    db.session.commit()


def _cenario():
    """Obra + RDO assinado com mão de obra e custo lançado."""
    suf = _sfx()
    admin = Usuario(username=f'ret_{suf}', email=f'ret_{suf}@t.local',
                    nome=f'Admin RET {suf}',
                    password_hash=generate_password_hash('Senha@2026'),
                    tipo_usuario=TipoUsuario.ADMIN, ativo=True,
                    versao_sistema='v2')
    db.session.add(admin)
    db.session.commit()

    cli = Cliente(nome=f'CLI-RET-{suf}', admin_id=admin.id)
    db.session.add(cli)
    db.session.flush()
    obra = Obra(nome=f'Obra RET {suf}', codigo=f'ORT{suf[:6].upper()}',
                data_inicio=date(2026, 1, 1), admin_id=admin.id,
                cliente_id=cli.id, valor_contrato=100000)
    db.session.add(obra)
    db.session.commit()

    rdo = RDO(numero_rdo=f'RDO-RET-{suf}', data_relatorio=date(2026, 6, 22),
              obra_id=obra.id, admin_id=admin.id,
              comentario_geral='Concretagem.', clima_geral='Nublado')
    func = Funcionario(codigo=f'R{suf[:6].upper()}', nome=f'Pedreiro {suf}',
                       cpf=f'{suf[:3]}.{suf[3:6]}.{suf[:3]}-{suf[6:8]}',
                       data_admissao=date(2026, 1, 5), salario=3000.0,
                       admin_id=admin.id)
    db.session.add_all([rdo, func])
    db.session.commit()

    db.session.add(RDOMaoObra(rdo_id=rdo.id, admin_id=admin.id,
                              funcionario_id=func.id,
                              funcao_exercida='Pedreiro',
                              horas_trabalhadas=8.0))
    db.session.commit()
    _lancar_custos(rdo, admin.id)

    from services.rdo_ciclo_vida import ASSINADO, PREENCHIDO, transicionar
    transicionar(rdo, PREENCHIDO, usuario=admin)
    transicionar(rdo, ASSINADO, usuario=admin)
    db.session.commit()
    return admin, obra.id, rdo


def test_retificar_e_salvar_nao_duplica_o_custo_da_jornada():
    from services.rdo_assinatura import criar_retificador

    with app.app_context():
        admin, obra_id, rdo = _cenario()
        antes = _realizado(obra_id, admin.id)
        assert antes > 0, 'o cenário não lançou custo — o teste não prova nada'

        novo = criar_retificador(rdo, admin, motivo='corrigir horas')
        db.session.commit()
        _lancar_custos(db.session.get(RDO, novo.id), admin.id)

        depois = _realizado(obra_id, admin.id)
        assert depois == antes, (
            f'a mesma jornada foi contada duas vezes: R$ {antes:.2f} → '
            f'R$ {depois:.2f}')


def test_custo_do_rdo_retificado_sai_ao_retificar():
    """O lançamento some no ato da retificação, não só depois de salvar.

    Entre retificar e salvar o retificador, a obra não pode continuar
    carregando o custo de um documento que foi substituído.
    """
    from services.rdo_assinatura import criar_retificador

    with app.app_context():
        admin, obra_id, rdo = _cenario()
        assert _realizado(obra_id, admin.id) > 0

        criar_retificador(rdo, admin, motivo='corrigir horas')
        db.session.commit()

        assert _realizado(obra_id, admin.id) == 0, (
            'custo do RDO retificado seguiu no Realizado')


def test_a_mao_de_obra_do_original_nao_e_apagada():
    """Remover o CUSTO não pode apagar o CONTEÚDO do RDO retificado.

    O documento continua existindo, e a mão de obra dele é o registro de
    quem trabalhou naquele dia — o que sai é o lançamento financeiro
    derivado, não o fato.
    """
    from services.rdo_assinatura import criar_retificador

    with app.app_context():
        admin, obra_id, rdo = _cenario()
        rid = rdo.id
        n_antes = RDOMaoObra.query.filter_by(rdo_id=rid).count()

        criar_retificador(rdo, admin, motivo='corrigir horas')
        db.session.commit()

        assert RDOMaoObra.query.filter_by(rdo_id=rid).count() == n_antes, (
            'a mão de obra do RDO retificado foi apagada junto com o custo')
        assert db.session.get(RDO, rid) is not None
