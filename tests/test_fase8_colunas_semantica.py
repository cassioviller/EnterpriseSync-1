# tests/test_fase8_colunas_semantica.py
"""As duas colunas de significado: default que NÃO classifica no gasto, e
default operacional no DFC — os dois escolhidos por motivos opostos e
ambos deliberados (ver spec, 'Modelo de dados')."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db  # noqa: E402
from helpers_tenant import um_tenant  # noqa: E402


def test_conta_nova_nasce_nao_classificada_e_operacional():
    from models import PlanoContas
    with app.app_context():
        t = um_tenant('fase8-colunas', com_fatos=False)
        conta = PlanoContas(codigo='9.9.99.999', nome='Conta de teste',
                            tipo_conta='DESPESA', natureza='DEVEDORA',
                            nivel=4, aceita_lancamento=True, ativo=True,
                            admin_id=t.admin_id)
        db.session.add(conta)
        db.session.flush()

        assert conta.classificacao_gasto == PlanoContas.CLASSIFICACAO_NAO_CLASSIFICADO, (
            'default fixo produziria margem que parece pronta e está errada')
        assert conta.atividade_dfc == PlanoContas.DFC_OPERACIONAL, (
            'default neutro faria o DFC nascer com quase tudo fora dos três '
            'grupos — inutilizável no dia 1')
        db.session.rollback()
