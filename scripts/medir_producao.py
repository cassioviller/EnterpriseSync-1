#!/usr/bin/env python3
"""Mede em produção o que dev não consegue responder.

Somente LEITURA — nenhum INSERT, UPDATE, DELETE ou DDL. Pode rodar com o app
de pé.

    DATABASE_URL='postgres://...' python scripts/medir_producao.py

Existe porque `ESTADO-ATUAL.md` acumulou medições marcadas ⚠️ dev, que provam a
*forma* de um problema e nunca o volume: o banco de desenvolvimento é dominado
por carga de suíte (~6.479 admins de domínio de teste, 7.984 obras). Cada
pergunta abaixo está aberta num documento à espera de acesso a produção; sem
elas, dimensionar qualquer correção é chutar.

Ao terminar: cole a saída no `ESTADO-ATUAL.md` trocando ⚠️ dev por 🔬 prod com
a data. Número sem procedência é o defeito de fabricação que este projeto já
pagou uma vez.
"""
import os
import sys

try:
    import psycopg2
except ImportError:
    sys.exit("psycopg2 não instalado — rode dentro do ambiente do app.")


def _t(cur, sql, params=None):
    cur.execute(sql, params or ())
    return cur.fetchall()


def _um(cur, sql, params=None):
    linhas = _t(cur, sql, params)
    return linhas[0][0] if linhas else None


def _existe(cur, tabela):
    return _um(cur, """
        select count(*) from information_schema.tables
        where table_schema = 'public' and table_name = %s
    """, (tabela,)) > 0


def secao(titulo):
    print()
    print("=" * 72)
    print(titulo)
    print("=" * 72)


def q1_migracao_270(cur):
    """O fantasma do 270 chegou em produção?

    `41f23403` foi empurrado para origin/main com a migração do editor v2
    numerada 270; `ff94240d` só depois a renumerou para 277. Todo banco que
    deployou naquela janela gravou 270 = success. Se produção gravou, a faixa
    da Fase 6 precisa começar em 271 lá também — e uma migração 270 nova seria
    pulada em silêncio por `is_migration_executed`.
    """
    secao("1. O fantasma da migração 270 (decide a faixa da Fase 6)")
    if not _existe(cur, "migration_history"):
        print("  tabela migration_history não existe — banco anterior ao runner.")
        return
    linhas = _t(cur, """
        select migration_number, status, executed_at, execution_time_ms
        from migration_history
        where migration_number in (270, 277, 278)
        order by migration_number
    """)
    if not linhas:
        print("  270/277/278: NENHUMA rodou. O editor v2 NÃO está no parque em")
        print("  produção, e a surpresa do calendário ainda não aconteceu.")
    for num, status, quando, ms in linhas:
        print(f"  {num}: {status} em {quando} ({ms} ms)")
    tem_270 = any(l[0] == 270 for l in linhas)
    tem_277 = any(l[0] == 277 for l in linhas)
    print()
    if tem_270 and tem_277:
        print("  >> FANTASMA CONFIRMADO: a mesma migração sob dois números.")
        print("     A Fase 6 começa em 271. NÃO apague a linha 270.")
    elif tem_270:
        print("  >> Produção rodou como 270 e nunca viu a 277. O 270 está")
        print("     queimado; a 277 será pulada por já ter rodado sob o outro")
        print("     número. Confira o efeito antes de supor que faltou algo.")
    elif tem_277:
        print("  >> Limpo: só a 277. Produção deployou depois da renumeração.")

    secao("1b. Varredura geral do histórico de migrações")
    for rot, sql in (
        ("nome sob mais de um número (fantasmas)", """
            select migration_name, array_agg(migration_number order by migration_number)
            from migration_history group by migration_name
            having count(distinct migration_number) > 1"""),
        ("número sob mais de um nome (colisão)", """
            select migration_number, count(distinct migration_name)
            from migration_history group by migration_number
            having count(distinct migration_name) > 1"""),
        ("status != success", """
            select migration_number, status, error_message
            from migration_history where status <> 'success' order by 1"""),
    ):
        achados = _t(cur, sql)
        print(f"  {rot}: {len(achados)}")
        for a in achados:
            print("     ", a)


def q2_editor_v2(cur):
    """"Todo cronograma no formato novo" é verdade inteira ou só para parte?

    Tenant que não é versao_sistema='v2' fica com a flag ligada e inerte. Essa
    contagem é o que decide a frase — e é a base da semana de observação.
    """
    secao("2. Editor v2: quanto do parque está de fato em v2")
    linhas = _t(cur, """
        select coalesce(versao_sistema, '(nulo)'), count(*)
        from usuario group by 1 order by 2 desc
    """)
    for versao, n in linhas:
        print(f"  versao_sistema={versao}: {n} usuário(s)")
    print()
    print("  Tenants (admins) por versão:")
    for versao, n in _t(cur, """
        select coalesce(versao_sistema, '(nulo)'), count(*)
        from usuario where tipo_usuario = 'ADMIN' group by 1 order by 2 desc
    """):
        print(f"    {versao}: {n}")


def q3_calendario(cur):
    """Quem vai ver datas andarem na primeira edição.

    O guard de calendário virou aviso nominal no log do deploy. Estes são os
    tenants da lista: se algum trabalha sábado de verdade, calendário
    configurável deixa de ser hipótese e vira código (decisão pendente nº 1).
    """
    secao("3. Calendário: tenants que consideram sábado/domingo")
    if not _existe(cur, "calendario_empresa"):
        print("  calendario_empresa não existe neste banco.")
        return
    linhas = _t(cur, """
        select admin_id, considerar_sabado, considerar_domingo
        from calendario_empresa
        where considerar_sabado or considerar_domingo
        order by admin_id
    """)
    if not linhas:
        print("  Nenhum. A primeira edição não move data por causa de fim de semana.")
        return
    print(f"  {len(linhas)} tenant(s) na lista — datas VÃO andar na primeira edição:")
    for admin_id, sab, dom in linhas:
        nome = _um(cur, "select nome from usuario where id = %s", (admin_id,))
        print(f"    admin_id={admin_id} ({nome}) sábado={sab} domingo={dom}")


def q4_snapshots_orfaos(cur):
    """Os 40.824 snapshots com a tarefa apagada.

    ⚠️ dev 28/07. Num rollback, `_restaurar` não acha a tarefa e INSERE uma
    cópia nova — mesmo efeito do defeito já corrigido, em escala maior. Quase
    certamente carga de suíte; medir antes de escrever qualquer código.
    """
    secao("4. Snapshots de cronograma apontando para tarefa apagada")
    if not _existe(cur, "cronograma_tarefa_snapshot"):
        print("  cronograma_tarefa_snapshot não existe neste banco.")
        return
    total = _um(cur, "select count(*) from cronograma_tarefa_snapshot")
    orfaos = _um(cur, """
        select count(*) from cronograma_tarefa_snapshot s
        where s.tarefa_id is not null
          and not exists (select 1 from tarefa_cronograma t where t.id = s.tarefa_id)
    """)
    print(f"  total de snapshots: {total}")
    print(f"  com a tarefa apagada: {orfaos}")
    if total:
        print(f"  proporção: {100.0 * orfaos / total:.1f}%")
    print()
    if orfaos == 0:
        print("  >> Era carga de suíte. Nada a corrigir em produção.")
    else:
        print("  >> Volume REAL. Agora vale escrever código para o rollback.")


def q5_baselines_sem_bac(cur):
    """Quantas linhas de base vão cair no orçamento vivo.

    A migração 278 criou `cronograma_baseline.bac` nullable de propósito: as
    baselines já existentes — inclusive as que a 277 congelou no rollout — não
    têm BAC e caem no custo orçado vivo. Isso é o comportamento de antes, mas
    o CPI delas não tem régua fixa. Este número diz quantas.
    """
    secao("5. Linhas de base sem BAC congelado (CPI sem régua fixa)")
    if not _existe(cur, "cronograma_baseline"):
        print("  cronograma_baseline não existe neste banco.")
        return
    total = _um(cur, "select count(*) from cronograma_baseline")
    sem = _um(cur, "select count(*) from cronograma_baseline where bac is null")
    ativas_sem = _um(cur, """
        select count(*) from cronograma_baseline where bac is null and ativa
    """)
    print(f"  total de baselines: {total}")
    print(f"  sem BAC: {sem}")
    print(f"  ATIVAS sem BAC (as que o EVM lê hoje): {ativas_sem}")
    print()
    print("  >> Estas caem no orçado vivo, com bac_origem='vivo' no payload.")
    print("     Não preencha retroativamente: seria inventar um orçamento que")
    print("     ninguém congelou naquele momento.")


def q6_duplicacao_ponto_rdo(cur):
    """O tamanho do histórico duplicado ponto × RDO.

    Os Steps C-E do p1 impedem a duplicação nova. O Step F
    (`scripts/reconciliar_custos_mao_obra.py`, que roda em --dry-run por
    padrão) remove a antiga, e esta contagem é o que decide se vale rodá-lo.
    """
    secao("6. Dias com custo de PONTO e de RDO no mesmo (funcionário, data, obra)")
    if not _existe(cur, "custo_obra"):
        print("  custo_obra não existe neste banco.")
        return
    linhas = _t(cur, """
        select p.admin_id, count(*) as dias, sum(r.valor) as valor_rdo
        from custo_obra p
        join custo_obra r
          on r.funcionario_id = p.funcionario_id
         and r.data = p.data
         and r.obra_id = p.obra_id
         and r.admin_id = p.admin_id
         and r.rdo_id is not null
        where p.rdo_id is null
          and p.categoria = 'PONTO_ELETRONICO'
        group by p.admin_id
        order by 2 desc
    """)
    if not linhas:
        print("  Nenhum. Nada a reconciliar.")
        return
    print(f"  {len(linhas)} tenant(s) afetado(s):")
    for admin_id, dias, valor in linhas:
        print(f"    admin_id={admin_id}: {dias} dia(s), R$ {valor or 0:.2f} em duplicidade")
    print()
    print("  >> Confirme com: python scripts/reconciliar_custos_mao_obra.py")
    print("     (--dry-run é o modo padrão; só escreve com --aplicar)")


def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("Defina DATABASE_URL apontando para PRODUÇÃO.")
    alvo = url.split("@")[-1].split("?")[0]
    print(f"Banco: {alvo}")
    print("Modo: SOMENTE LEITURA")

    conn = psycopg2.connect(url)
    conn.set_session(readonly=True, autocommit=True)
    cur = conn.cursor()

    for fn in (q1_migracao_270, q2_editor_v2, q3_calendario,
               q4_snapshots_orfaos, q5_baselines_sem_bac,
               q6_duplicacao_ponto_rdo):
        try:
            fn(cur)
        except Exception as exc:      # uma pergunta que falha não derruba as outras
            secao(f"{fn.__name__}: FALHOU")
            print(f"  {type(exc).__name__}: {exc}")

    print()
    print("=" * 72)
    print("Fim. Troque ⚠️ dev por 🔬 prod no ESTADO-ATUAL.md, com a data.")
    print("=" * 72)
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
