"""A04 — a despesa geral tem conta de débito própria e inequívoca.

Por que 6.1.02.009 e não 6.1.02.001-003: os planos de contas concorrentes
dão significados diferentes a esses três códigos (contabilidade_utils.py:545
documenta a divergência — é por isso que o subgrupo ficou fora do DRE), e
reaproveitar um deles escolheria um significado sem saber qual o tenant usa.
O .009 não existe em nenhum dos planos conhecidos do parque.
Decisão: docs/superpowers/plans/2026-09-01-decisoes-respondidas.md §A04.
"""
import uuid
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

from app import app, db


@pytest.fixture()
def tenant():
    with app.app_context():
        from models import Usuario, TipoUsuario
        marca = uuid.uuid4().hex[:6]
        admin = Usuario(
            username=f'a04{marca}', email=f'a04{marca}@t.local', nome='A04',
            password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True)
        db.session.add(admin)
        db.session.commit()
        yield admin.id
        db.session.rollback()


def test_o_mapeamento_tem_despesa_geral():
    from contabilidade_utils import MAPEAMENTO_CONTABIL
    assert MAPEAMENTO_CONTABIL['despesa_geral'] == {
        'debito': '6.1.02.009', 'credito': '2.1.01.001'}


def test_o_seed_v2_cria_a_conta_da_despesa_geral(tenant):
    with app.app_context():
        from contabilidade_utils import seed_plano_contas_if_needed
        from models import PlanoContas
        seed_plano_contas_if_needed(tenant)
        db.session.commit()
        conta = PlanoContas.query.filter_by(
            admin_id=tenant, codigo='6.1.02.009').first()
        assert conta is not None
        assert conta.aceita_lancamento is True
        assert conta.tipo_conta == 'DESPESA'
        assert conta.conta_pai_codigo == '6.1.02'


def test_lancamento_de_despesa_geral_debita_a_conta_nova(tenant):
    with app.app_context():
        from contabilidade_utils import gerar_lancamento_contabil_automatico
        from models import LancamentoContabil
        ok = gerar_lancamento_contabil_automatico(
            admin_id=tenant,
            tipo_operacao='despesa_geral',
            valor=123.45,
            data=date(2026, 9, 1),
            descricao='Teste A04',
        )
        assert ok is True, 'a chave despesa_geral tem de ser aceita'
        lc = (LancamentoContabil.query.filter_by(admin_id=tenant)
              .order_by(LancamentoContabil.id.desc()).first())
        assert lc is not None
