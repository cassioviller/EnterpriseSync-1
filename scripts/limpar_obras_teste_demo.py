"""Apaga as obras que os testes deixaram no tenant demo (admin_id=1).

Por que existe: até 21/08 `tests/test_resumo_custos_obra.py` criava ~19 obras
"Obra #…" por rodada no PRIMEIRO usuário da tabela — o admin demo — e a suíte
nunca limpa o banco. 🔬 21/08: 1.242 obras acumuladas; /obras do demo em 8,3 s
e 5 MB. O teste foi corrigido (tenant próprio); este script tira o que ficou.

Como apaga: pelo MESMO caminho da tela — `POST /obras/excluir/<id>` via test
client, logado como o admin demo. É a rota que conhece a ordem das
dependências (`TABELAS_DEPENDENTES_OBRA`), usa savepoint por tabela e escopa
tudo por admin_id. Nada de SQL à mão. Medido: ~2,6 s por obra.

Escopo, de propósito estreito: só `admin_id = 1` e só nomes que casam
`^Obra #` (o padrão dos testes). As 78 obras do demo com nome "de verdade"
(Residencial Bela Vista, Baias Kabod…) não são tocadas.

Uso:
    .pythonlibs/bin/python scripts/limpar_obras_teste_demo.py            # dry-run: só lista e conta
    .pythonlibs/bin/python scripts/limpar_obras_teste_demo.py --apagar   # apaga de verdade
    .pythonlibs/bin/python scripts/limpar_obras_teste_demo.py --apagar --limite 100
"""
import argparse
import os
import sys
import time

os.environ.setdefault("SIGE_BOOT_DDL", "0")
os.environ.setdefault("SIGE_ENABLE_DEMO_SEED", "false")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ADMIN_DEMO = 1
PADRAO = r'^Obra #'


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--apagar', action='store_true',
                    help='sem esta flag, só lista e conta (dry-run)')
    ap.add_argument('--limite', type=int, default=None,
                    help='apagar no máximo N obras nesta execução')
    args = ap.parse_args()

    import main as _main  # noqa: F401 — registra os blueprints
    from app import app, db
    from models import Obra

    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'limpeza-obras-teste'

    with app.app_context():
        q = (Obra.query
             .filter(Obra.admin_id == ADMIN_DEMO, Obra.nome.op('~')(PADRAO))
             .order_by(Obra.id))
        alvos = [(o.id, o.nome) for o in q.all()]
        restantes = Obra.query.filter(Obra.admin_id == ADMIN_DEMO,
                                      ~Obra.nome.op('~')(PADRAO)).count()

    print(f"tenant {ADMIN_DEMO}: {len(alvos)} obras casam {PADRAO!r}; "
          f"{restantes} NÃO casam e ficam intocadas")
    if not alvos:
        return 0
    if args.limite:
        alvos = alvos[:args.limite]

    if not args.apagar:
        for oid, nome in alvos[:10]:
            print(f"  {oid:>7}  {nome}")
        if len(alvos) > 10:
            print(f"  … e mais {len(alvos) - 10}")
        print("\ndry-run: nada apagado. Rode com --apagar para executar.")
        return 0

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(ADMIN_DEMO)
        sess['_fresh'] = True

    ok = falhou = 0
    t0 = time.time()
    for i, (oid, nome) in enumerate(alvos, 1):
        resp = client.post(f'/obras/excluir/{oid}', follow_redirects=False)
        with app.app_context():
            viva = db.session.get(Obra, oid) is not None
        if viva:
            falhou += 1
            print(f"FALHOU  {oid}  {nome}  (http {resp.status_code})", flush=True)
        else:
            ok += 1
        if i % 50 == 0 or i == len(alvos):
            print(f"{i}/{len(alvos)}  ok={ok} falhou={falhou}  "
                  f"{round(time.time() - t0)}s", flush=True)

    print(f"\nconcluído: {ok} apagadas, {falhou} falharam, "
          f"{round(time.time() - t0)}s")
    return 1 if falhou else 0


if __name__ == '__main__':
    sys.exit(main())
