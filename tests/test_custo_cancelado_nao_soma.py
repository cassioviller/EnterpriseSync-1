"""Custo de RDO excluído não pode continuar no Realizado da obra.

Excluir um RDO não apaga o lançamento financeiro que ele gerou:
`services/rdo_custos.py:cancelar_custos_rdo` marca o `GestaoCustoPai` como
CANCELADO de propósito, para preservar o histórico para auditoria. Só que
nenhum agregado de custo olhava `status` — o RDO sumia da tela e os R$ dele
seguiam somando no Realizado, no custo acumulado e na curva.

Cancelar é decisão de quem escreve; ignorar o cancelado é obrigação de quem
lê, e mora em `services/gestao_custos_query.sem_cancelados`.
"""
import os
import sys
import uuid
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints antes de qualquer request
from app import app, db
from models import (Cliente, Funcionario, GestaoCustoPai, Obra, RDO,
                    RDOCustoDiario, RDOMaoObra, TipoUsuario, Usuario)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-custo-cancelado'
    yield


def _sfx():
    return uuid.uuid4().hex[:8]


def _cenario():
    """Obra + RDO finalizado com mão de obra + lançamento gerado. -> ids."""
    suf = _sfx()
    admin = Usuario(
        username=f'cc_{suf}', email=f'cc_{suf}@test.local',
        nome=f'Admin CC {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
    db.session.add(admin)
    db.session.commit()

    cli = Cliente(nome=f'CLI-CC-{suf}', admin_id=admin.id)
    db.session.add(cli)
    db.session.flush()
    obra = Obra(nome=f'Obra CC {suf}', codigo=f'OCC{suf[:6].upper()}',
                data_inicio=date(2026, 1, 1), admin_id=admin.id,
                cliente_id=cli.id, valor_contrato=100000)
    db.session.add(obra)
    db.session.commit()

    rdo = RDO(numero_rdo=f'RDO-CC-{suf}', data_relatorio=date(2026, 6, 22),
              obra_id=obra.id, admin_id=admin.id, status='Finalizado',
              comentario_geral='Concretagem.', clima_geral='Nublado')
    func = Funcionario(codigo=f'C{suf[:6].upper()}', nome=f'Pedreiro {suf}',
                       cpf=f'{suf[:3]}.{suf[3:6]}.{suf[:3]}-{suf[6:8]}',
                       data_admissao=date(2026, 1, 5), salario=3000.0,
                       admin_id=admin.id)
    db.session.add_all([rdo, func])
    db.session.commit()

    db.session.add(RDOMaoObra(rdo_id=rdo.id, admin_id=admin.id,
                              funcionario_id=func.id,
                              funcao_exercida='Pedreiro',
                              horas_trabalhadas=8.0))
    db.session.add(RDOCustoDiario(
        rdo_id=rdo.id, funcionario_id=func.id, admin_id=admin.id,
        data=date(2026, 6, 22), tipo_remuneracao_snapshot='salario',
        custo_total_dia=180.0, tipo_lancamento='rdo', componente_folha=180.0))
    db.session.commit()

    from services.rdo_custos import gerar_custos_mao_obra_rdo
    gerar_custos_mao_obra_rdo(db.session.get(RDO, rdo.id), admin.id)
    return admin.id, obra.id, rdo.id


def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as s:
        s['_user_id'] = str(user_id)
        s['_fresh'] = True
    return c


def _realizado(oid, aid):
    from services.resumo_custos_obra import calcular_resumo_obra
    return calcular_resumo_obra(oid, aid)['indicadores']['total_realizado']


def test_realizado_cai_quando_o_rdo_que_o_gerou_e_excluido():
    with app.app_context():
        aid, oid, rid = _cenario()
        antes = _realizado(oid, aid)
        assert antes > 0, (
            'o cenário não gerou lançamento — o teste não prova nada')

    _cliente_de(aid).post(f'/rdo/excluir/{rid}', follow_redirects=True)

    with app.app_context():
        assert db.session.get(RDO, rid) is None, 'o RDO não foi excluído'
        depois = _realizado(oid, aid)
        assert depois == 0, (
            f'Realizado seguiu em {depois} depois de o RDO sumir — custo de '
            f'RDO excluído continua somando (era {antes})')


def test_pai_continua_no_banco_como_cancelado():
    """O filtro é de leitura: o histórico financeiro NÃO some.

    Se alguém "resolver" o problema apagando o pai em vez de filtrar, este
    teste cai — e a auditoria que `cancelar_custos_rdo` existe para preservar
    ia junto.
    """
    with app.app_context():
        aid, oid, rid = _cenario()

    _cliente_de(aid).post(f'/rdo/excluir/{rid}', follow_redirects=True)

    with app.app_context():
        pais = GestaoCustoPai.query.filter_by(obra_id=oid).all()
        assert pais, 'o lançamento foi APAGADO — era para ficar como CANCELADO'
        assert all(p.status == 'CANCELADO' for p in pais), (
            f'status inesperado: {[p.status for p in pais]}')


def test_curva_e_etapa_tambem_ignoram_o_cancelado():
    """Os outros dois agregados de realizado, no cronograma físico-financeiro."""
    from services.cronograma_fisico_financeiro import (curva_realizado,
                                                       realizado_por_etapa)
    with app.app_context():
        aid, oid, rid = _cenario()
        obra = db.session.get(Obra, oid)
        assert sum(curva_realizado(obra).values()) > 0

    _cliente_de(aid).post(f'/rdo/excluir/{rid}', follow_redirects=True)

    with app.app_context():
        obra = db.session.get(Obra, oid)
        assert sum(curva_realizado(obra).values()) == 0, (
            'curva_realizado ainda conta o custo do RDO excluído')
        assert sum(realizado_por_etapa(obra).values()) == 0, (
            'realizado_por_etapa ainda conta o custo do RDO excluído')
