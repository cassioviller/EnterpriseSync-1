#!/usr/bin/env python3
"""Esvazia o banco de DESENVOLVIMENTO deixando só os tenants que importam.

🔬 21/08 — o banco de dev tinha **28 GB e 10.336.557 linhas penduradas em
tenants que não são o demo**, contra 10.979 linhas no tenant 1. Ou seja:
99,9 % do banco era resíduo de suíte. A causa é o remédio certo aplicado sem
varrer depois — desde `65c24bcc` cada teste cria o **próprio** tenant (é o que
impede o teste de sujar o demo, ver `scripts/limpar_obras_teste_demo.py`), mas
ninguém apaga o tenant no fim. Eram 167.962 usuários, 133.618 deles ADMIN.

Por que dá para apagar por `admin_id` e pronto: 🔬 das 195 tabelas do schema,
**194 têm `admin_id`** e a única que não tem não referencia tabela de tenant
nenhuma. O banco é inteiramente escopado por tenant, então remover todas as
linhas de um `admin_id` não deixa órfão em lugar nenhum.

Por que NÃO dá para simplesmente apagar de `usuario`: 🔬 235 FKs apontam para
`usuario(id)` e **230 são NO ACTION** — sem cascade. Daí a ordem topológica
(filho antes de pai) que este script calcula do próprio catálogo do Postgres.

⚠️ **NUNCA rode isto contra produção.** O script recusa se achar mais tenants
preservados do que resíduo, que é a cara de um banco real, e exige `--apagar`
para escrever. Sem a flag é dry-run.

Uso:
    python scripts/limpar_tenants_teste_dev.py              # dry-run
    python scripts/limpar_tenants_teste_dev.py --apagar     # executa
    python scripts/limpar_tenants_teste_dev.py --apagar --preservar 1,161137,169871
"""
import argparse
import os
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('SIGE_BOOT_DDL', '0')
os.environ.setdefault('SIGE_ENABLE_DEMO_SEED', 'false')

from app import app, db  # noqa: E402

# Os tenants que sobrevivem por padrão. Não são "os que existem": são os que
# planos vivos citam como prova e cujo dado ninguém consegue recriar de cabeça.
#   1       admin_alfa    — o demo, onde moram as obras Baia/Kabod e os RDOs
#   161137  piloto_admin  — o PILOTO do rollout ensaiado (43+41+21), ✅ 19/08
#   169871  manualrdo_admin — cenário das 18 telas do manual visual do RDO
PRESERVAR_PADRAO = (1, 161137, 169871)

LOTE = 50_000


def _ordem_topologica():
    """Tabelas ordenadas de filha para mãe, lida do catálogo do Postgres.

    Aresta filho→pai significa "o filho tem de ser apagado antes". Kahn sobre
    essas arestas devolve exatamente a ordem de exclusão. Ciclos (se houver)
    sobram no fim e o laço de repasses do `limpar()` cuida deles.
    """
    tabelas = [r[0] for r in db.session.execute(db.text(
        "select table_name from information_schema.tables "
        "where table_schema='public' and table_type='BASE TABLE'")).all()]

    fks = db.session.execute(db.text("""
        select tc.table_name as filho, ccu.table_name as pai
        from information_schema.table_constraints tc
        join information_schema.key_column_usage kcu
             on kcu.constraint_name = tc.constraint_name
        join information_schema.constraint_column_usage ccu
             on ccu.constraint_name = tc.constraint_name
        where tc.constraint_type = 'FOREIGN KEY' and tc.table_schema = 'public'
    """)).all()

    filhos_de = defaultdict(set)          # pai -> {filhos}
    grau = {t: 0 for t in tabelas}
    vistas = set()
    for filho, pai in fks:
        if filho == pai or (filho, pai) in vistas:
            continue                       # auto-referência não ordena nada
        vistas.add((filho, pai))
        filhos_de[pai].add(filho)
        grau[pai] = grau.get(pai, 0) + 1

    fila = [t for t in tabelas if grau[t] == 0]
    ordem = []
    while fila:
        t = fila.pop()
        ordem.append(t)
        for pai in [p for p, fs in filhos_de.items() if t in fs]:
            grau[pai] -= 1
            if grau[pai] == 0:
                fila.append(pai)
    ordem += [t for t in tabelas if t not in ordem]   # ciclos, se existirem
    return ordem


def _cond_usuario(ids):
    """Quem sai da tabela `usuario`.

    ⚠️ o `coalesce` não é enfeite: nas linhas de ADMIN o `admin_id` é NULL, e
    `NOT (id in (…) OR NULL)` devolve NULL, não TRUE — a linha não entra no
    filtro. Escrito sem ele, o dry-run acusava 34.338 usuários a apagar num
    banco de 167.962: os 133.618 ADMIN (justamente os tenants de teste que
    motivaram a limpeza) ficavam de fora em silêncio.
    """
    return ('id not in (%s) and coalesce(admin_id, -1) not in (%s)' % (ids, ids))


def _tem_admin_id(tabela):
    return db.session.execute(db.text(
        "select 1 from information_schema.columns where table_schema='public' "
        "and table_name=:t and column_name='admin_id'"), {'t': tabela}).scalar()


def _apagar_em_lotes(tabela, filtro, params):
    """DELETE por ctid em lotes — transação curta, sem lock longo na tabela."""
    total = 0
    while True:
        n = db.session.execute(db.text(
            'delete from "%s" where ctid in ('
            '  select ctid from "%s" where %s limit %d)'
            % (tabela, tabela, filtro, LOTE)), params).rowcount
        db.session.commit()
        total += n
        if n < LOTE:
            return total


def limpar(preservar, executar):
    ids = ','.join(str(i) for i in preservar)

    donos = db.session.execute(db.text(
        "select id, username, tipo_usuario from usuario where id in (%s)" % ids)).all()
    if len(donos) != len(preservar):
        sys.exit('ABORTADO: nem todos os ids a preservar existem: %s' % donos)
    print('Tenants preservados:')
    for i, u, t in donos:
        print('   id=%-7d %-22s %s' % (i, u, t))

    # Guarda contra rodar em produção: num banco real a maioria dos usuários é
    # dos tenants que ficam. Aqui o resíduo tem de ser a esmagadora maioria.
    fica = db.session.execute(db.text(
        "select count(*) from usuario where id in (%s) or admin_id in (%s)" % (ids, ids))).scalar()
    cond_usuario = _cond_usuario(ids)
    sai = db.session.execute(db.text(
        "select count(*) from usuario where %s" % cond_usuario)).scalar()
    print('\nUsuários: %d ficam, %d saem' % (fica, sai))
    if sai < fica * 10:
        sys.exit('ABORTADO: só %d usuários a apagar contra %d a preservar. Isto '
                 'não tem cara de banco de dev poluído por suíte — confira o '
                 'DATABASE_URL antes de insistir.' % (sai, fica))

    ordem = _ordem_topologica()
    print('%d tabelas, em ordem de filha para mãe.\n' % len(ordem))

    cond_normal = 'admin_id is not null and admin_id not in (%s)' % ids

    alvos = []
    for tabela in ordem:
        if not _tem_admin_id(tabela):
            continue
        cond = cond_usuario if tabela == 'usuario' else cond_normal
        n = db.session.execute(db.text(
            'select count(*) from "%s" where %s' % (tabela, cond))).scalar()
        if n:
            alvos.append((tabela, cond, n))

    total = sum(n for _, _, n in alvos)
    print('%d tabelas com linhas a apagar, %s linhas no total.' % (len(alvos), f'{total:,}'))
    for tabela, _, n in sorted(alvos, key=lambda x: -x[2])[:12]:
        print('   %-42s %s' % (tabela, f'{n:,}'))

    if not executar:
        print('\n(dry-run — nada foi apagado. Use --apagar para executar.)')
        return

    print('\nApagando…')
    t0 = time.time()
    apagadas = 0
    for passada in range(1, 6):
        pendentes = []
        for tabela, cond, _ in alvos:
            try:
                n = _apagar_em_lotes(tabela, cond, {})
                apagadas += n
                if n:
                    print('   %-42s -%s  (%.0fs)' % (tabela, f'{n:,}', time.time() - t0))
            except Exception as e:            # FK ainda presa: tenta na próxima
                db.session.rollback()
                pendentes.append((tabela, cond, 0))
                print('   %-42s adiada (%s)' % (tabela, str(e).split('\n')[0][:70]))
        if not pendentes:
            break
        alvos = pendentes
        print('   -- repasse %d, %d tabelas pendentes --' % (passada, len(pendentes)))
    else:
        sys.exit('ABORTADO: tabelas ainda presas depois de 5 repasses: %s'
                 % [t for t, _, _ in alvos])

    print('\n%s linhas apagadas em %.0f s.' % (f'{apagadas:,}', time.time() - t0))
    print('Usuários restantes: %d'
          % db.session.execute(db.text('select count(*) from usuario')).scalar())


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apagar', action='store_true', help='executa (sem isto é dry-run)')
    ap.add_argument('--preservar', default=','.join(str(i) for i in PRESERVAR_PADRAO),
                    help='ids de ADMIN a manter, separados por vírgula')
    args = ap.parse_args()
    with app.app_context():
        limpar([int(x) for x in args.preservar.split(',')], args.apagar)
