"""q8 de medir_producao: quantos tenants em 5.x, 6.x, ambos, nenhum;
quantas partidas vivem em 5.x; e se existe partida órfã."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db  # noqa: E402


def test_q8_devolve_as_tres_respostas_e_nao_inventa_orfa():
    from scripts.medir_producao import SQL_Q8_PARTIDAS_5X, SQL_Q8_PARTIDAS_ORFAS, SQL_Q8_TENANTS
    with app.app_context():
        from sqlalchemy import text
        linhas = db.session.execute(text(SQL_Q8_TENANTS)).fetchall()
        assert linhas, 'a q8 tem de devolver ao menos uma linha de retrato'
        assert {c.lower() for c in linhas[0]._mapping.keys()} >= {
            'so_5x', 'so_6x', 'ambos', 'nenhum'}

        cinco = db.session.execute(text(SQL_Q8_PARTIDAS_5X)).scalar()
        assert cinco is not None and cinco >= 0

        orfas = db.session.execute(text(SQL_Q8_PARTIDAS_ORFAS)).scalar()
        assert orfas is not None, (
            'partida órfã tem de ser CONTADA, não presumida zero — se '
            'produção divergir do dev, a fase inteira volta à mesa')
