"""Exclusão de obra — a rota apaga os filhos à mão, e isso precisa de rede.

`views/obras.py:excluir_obra` limpa uma lista escrita à mão
(`TABELAS_DEPENDENTES_OBRA`) antes de deletar a obra. Duas coisas quebravam:

1. `gestao_custo_pai` (FK NO ACTION) não estava na lista. Como todo RDO com
   mão de obra gera um, QUALQUER obra com histórico de RDO era indeletável.
2. Cada DELETE rodava em conexão `AUTOCOMMIT` própria, fora da transação da
   rota. Quando o DELETE da obra estourava na FK acima, os RDOs, custos e
   lançamentos já estavam commitados um a um — a obra ficava viva e vazia, e
   repetir a exclusão dava o mesmo erro para sempre. Perda irreversível.

O teste de drift abaixo é o que impede (1) de voltar quando alguém criar uma
tabela nova; o E2E cobre (2).
"""
import os
import sys
import uuid
from datetime import date

import pytest
from sqlalchemy import text
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints antes de qualquer request
from app import app, db
from models import (Cliente, CustoObra, Funcionario, GestaoCustoPai, Obra, RDO,
                    RDOCustoDiario, RDOMaoObra, TipoUsuario, Usuario)
from views.obras import TABELAS_DEPENDENTES_OBRA

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-excluir-obra'
    yield


def _sfx():
    return uuid.uuid4().hex[:8]


def _admin():
    suf = _sfx()
    u = Usuario(
        username=f'xo_{suf}', email=f'xo_{suf}@test.local',
        nome=f'Admin XO {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id):
    suf = _sfx()
    cli = Cliente(nome=f'CLI-XO-{suf}', admin_id=admin_id)
    db.session.add(cli)
    db.session.flush()
    o = Obra(nome=f'Obra XO {suf}', codigo=f'OXO{suf[:6].upper()}',
             data_inicio=date(2026, 1, 1), admin_id=admin_id,
             cliente_id=cli.id, valor_contrato=100000)
    db.session.add(o)
    db.session.commit()
    return o


def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as s:
        s['_user_id'] = str(user_id)
        s['_fresh'] = True
    return c


def test_lista_cobre_toda_fk_no_action_para_obra():
    """Teste de drift: nenhuma FK NO ACTION para `obra` pode ficar de fora.

    CASCADE e SET NULL o banco resolve sozinho e ficam fora de propósito —
    só as NO ACTION bloqueiam o DELETE da obra. Se este teste falhar, alguém
    criou uma tabela apontando para `obra` sem ON DELETE e não a incluiu em
    `TABELAS_DEPENDENTES_OBRA`: acrescente lá, respeitando a ordem
    filho-antes-de-pai, em vez de afrouxar a asserção.
    """
    with app.app_context():
        faltando = db.session.execute(text("""
            SELECT DISTINCT c.conrelid::regclass::text
            FROM pg_constraint c
            WHERE c.contype = 'f'
              AND c.confrelid = 'obra'::regclass
              AND c.confdeltype = 'a'
            ORDER BY 1
        """)).scalars().all()

    fora = sorted(set(faltando) - set(TABELAS_DEPENDENTES_OBRA))
    assert not fora, (
        'FK(s) NO ACTION para `obra` fora de TABELAS_DEPENDENTES_OBRA — a '
        f'exclusão de obra vai estourar nelas: {fora}')


def test_lista_nao_tem_tabela_fantasma():
    """Nome na lista que não existe no banco vira erro engolido a cada exclusão.

    Eram seis (`fleet_vehicle_usage`, `movimentacao_material`, `obra_servico`,
    `proposta`, `vehicle_expense`, `vehicle_usage`): ruído que escondia os
    erros de verdade no log.
    """
    with app.app_context():
        existentes = set(db.session.execute(text("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
        """)).scalars().all())

    fantasmas = [t for t in TABELAS_DEPENDENTES_OBRA if t not in existentes]
    assert not fantasmas, f'tabelas inexistentes na lista: {fantasmas}'


def _obra_com_historico_financeiro():
    """Obra + RDO finalizado + mão de obra + lançamento em gestao_custo_*."""
    admin = _admin()
    obra = _obra(admin.id)
    suf = _sfx()
    rdo = RDO(numero_rdo=f'RDO-XO-{suf}', data_relatorio=date(2026, 6, 22),
              obra_id=obra.id, admin_id=admin.id, status='Finalizado',
              comentario_geral='Concretagem.', clima_geral='Nublado')
    func = Funcionario(codigo=f'X{suf[:6].upper()}', nome=f'Pedreiro {suf}',
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
    db.session.add(CustoObra(obra_id=obra.id, admin_id=admin.id,
                             tipo='material', descricao='Cimento',
                             valor=5000.0, data=date(2026, 6, 20)))
    db.session.commit()

    from services.rdo_custos import gerar_custos_mao_obra_rdo
    gerar_custos_mao_obra_rdo(db.session.get(RDO, rdo.id), admin.id)
    return admin.id, obra.id, rdo.id


def test_excluir_obra_com_lancamento_de_rdo_leva_tudo():
    """O caso que era impossível: obra que já teve RDO com mão de obra.

    O `gestao_custo_pai` gerado pelo RDO bloqueava o DELETE da obra, e o
    AUTOCOMMIT por tabela já tinha destruído o resto quando isso acontecia.
    """
    with app.app_context():
        aid, oid, rid = _obra_com_historico_financeiro()
        assert GestaoCustoPai.query.filter_by(obra_id=oid).count() > 0, (
            'sem gestao_custo_pai o teste não exercita o bloqueio que existia')

    _cliente_de(aid).post(f'/obras/excluir/{oid}', follow_redirects=True)

    with app.app_context():
        assert db.session.get(Obra, oid) is None, (
            'obra sobreviveu ao próprio delete — FK ainda bloqueia')
        assert db.session.get(RDO, rid) is None
        assert CustoObra.query.filter_by(obra_id=oid).count() == 0
        assert GestaoCustoPai.query.filter_by(obra_id=oid).count() == 0


def test_falha_no_delete_da_obra_nao_destroi_os_filhos():
    """Se o DELETE final estourar, NADA pode ter sido apagado.

    Simula a FK esquecida tirando `custo_obra` da lista em tempo de execução:
    a obra passa a ter um filho que ninguém limpou, o DELETE estoura, e o
    rollback tem de devolver tudo. Com o AUTOCOMMIT antigo este teste falhava
    — RDO e lançamentos já estavam commitados e não voltavam.
    """
    import views.obras as vo

    with app.app_context():
        aid, oid, rid = _obra_com_historico_financeiro()

    original = vo.TABELAS_DEPENDENTES_OBRA
    vo.TABELAS_DEPENDENTES_OBRA = [t for t in original if t != 'custo_obra']
    try:
        _cliente_de(aid).post(f'/obras/excluir/{oid}', follow_redirects=True)
    finally:
        vo.TABELAS_DEPENDENTES_OBRA = original

    with app.app_context():
        assert db.session.get(Obra, oid) is not None, (
            'a obra deveria ter sobrevivido — a FK de custo_obra bloqueia')
        assert db.session.get(RDO, rid) is not None, (
            'RDO foi destruído numa exclusão que FALHOU — o rollback não pegou')
        assert CustoObra.query.filter_by(obra_id=oid).count() == 1
        assert GestaoCustoPai.query.filter_by(obra_id=oid).count() == 1, (
            'lançamento financeiro destruído numa exclusão que falhou')
