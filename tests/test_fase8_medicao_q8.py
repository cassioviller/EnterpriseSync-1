"""q8 de medir_producao: quantos tenants em 5.x, 6.x, ambos, nenhum;
quantas partidas vivem em 5.x; e se existe partida órfã."""
import inspect
import os
import re
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


def test_q8_planos_de_contas_imprime_o_retrato_completo(capsys):
    """Chama q8_planos_de_contas de verdade — não só as SQLs soltas — para que
    um bug no corpo (índice errado em linha[], formatação quebrada) reprove.

    O cursor vem de db.engine.raw_connection(): é o mesmo pool de conexão que
    o resto da suíte já usa (não abre uma segunda conexão própria), mas
    devolve um cursor DBAPI cru — o mesmo contrato que _t/_um esperam e que
    main() usa de verdade via psycopg2 (%%s posicional incluído).
    """
    from scripts.medir_producao import q8_planos_de_contas
    with app.app_context():
        conn = db.engine.raw_connection()
        try:
            cur = conn.cursor()
            try:
                q8_planos_de_contas(cur)
            finally:
                cur.close()
        finally:
            conn.close()

    saida = capsys.readouterr().out
    assert 'tenants só 5.x' in saida
    assert 'partidas em 5.x' in saida
    assert 'partidas ÓRFÃS' in saida

    # Forma do retrato, não o valor de hoje — os números do dev arrastam
    # (carga de suíte) e não podem travar o teste.
    assert re.search(r'só 5\.x: \d+', saida)
    assert re.search(r'só 6\.x: \d+', saida)
    assert re.search(r'ambos: \d+', saida)
    assert re.search(r'nenhum: \d+', saida)
    assert re.search(r'partidas em 5\.x: \d+', saida)
    assert re.search(r'partidas ÓRFÃS.*: \d+', saida)


def test_q8_planos_de_contas_esta_registrada_em_main():
    """Garante que a tupla de registro em main() não perdeu a q8.

    Nunca chamamos main(): ela conecta via psycopg2.connect(DATABASE_URL), que
    em produção apontaria para produção. Em vez disso, lemos o texto-fonte de
    main() com inspect.getsource — dentro do corpo de main() o único lugar em
    que o nome `q8_planos_de_contas` pode aparecer é a tupla `for fn in (...)`
    que main() itera, então a presença do nome no fonte prova o registro sem
    executar a função.
    """
    from scripts.medir_producao import main
    src = inspect.getsource(main)
    assert 'q8_planos_de_contas' in src, (
        'q8_planos_de_contas sumiu da tupla de registro de main()')
