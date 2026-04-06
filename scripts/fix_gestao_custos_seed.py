"""
Corrige dados do seed V2:
1. Consolida GestaoCustoPai (1 por funcionário ao invés de 1 por dia)
2. Corrige percentual_planejado nos apontamentos de cronograma
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('FLASK_APP', 'main')
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from datetime import date

ADMIN_ID = 63

def log(msg): print(f"  [OK] {msg}")
def section(msg): print(f"\n{'='*55}\n{msg}\n{'='*55}")

with app.app_context():
    from models import (
        GestaoCustoPai, GestaoCustoFilho, FluxoCaixa,
        RDOApontamentoCronograma, RDO, TarefaCronograma
    )
    from sqlalchemy import text, func

    # ─────────────────────────────────────────────────────
    # 1. CONSOLIDAR GESTÃO DE CUSTOS
    # ─────────────────────────────────────────────────────
    section("1. CONSOLIDANDO GESTÃO DE CUSTOS")

    for tipo in ('SALARIO', 'TRANSPORTE', 'ALIMENTACAO'):
        # Buscar todos os entidades únicas (funcionário/restaurante)
        entidades = db.session.execute(text(
            "SELECT DISTINCT entidade_id, entidade_nome FROM gestao_custo_pai "
            "WHERE admin_id=:aid AND tipo_categoria=:tipo "
            "AND EXISTS (SELECT 1 FROM gestao_custo_filho f WHERE f.pai_id=gestao_custo_pai.id "
            "AND f.data_referencia < '2026-04-01')",
        ), {'aid': ADMIN_ID, 'tipo': tipo}).fetchall()

        for ent_id, ent_nome in entidades:
            # Pegar todos os pais desse funcionário/entidade
            pais = GestaoCustoPai.query.filter_by(
                admin_id=ADMIN_ID, tipo_categoria=tipo, entidade_id=ent_id
            ).all()

            if len(pais) <= 1:
                # Já consolidado ou só 1
                continue

            # Coletar todos os filhos
            todos_filhos = []
            for p in pais:
                filhos = GestaoCustoFilho.query.filter_by(pai_id=p.id).all()
                todos_filhos.extend(filhos)

            if not todos_filhos:
                continue

            # Calcular totais
            valor_total = sum(f.valor for f in todos_filhos)
            datas_ref = sorted([f.data_referencia for f in todos_filhos if f.data_referencia])
            data_inicio = datas_ref[0] if datas_ref else None
            data_fim = datas_ref[-1] if datas_ref else None

            # Determinar status consolidado
            statuses = set(p.status for p in pais)
            if statuses == {'PAGO'}:
                status_novo = 'PAGO'
            elif 'PAGO' in statuses:
                status_novo = 'PARCIAL'
            elif 'AUTORIZADO' in statuses:
                status_novo = 'AUTORIZADO'
            else:
                status_novo = 'SOLICITADO'

            # Valor pago (filhos com pai PAGO)
            valor_pago = sum(
                f.valor for p in pais if p.status == 'PAGO'
                for f in GestaoCustoFilho.query.filter_by(pai_id=p.id).all()
            )
            saldo = valor_total - valor_pago if valor_pago > 0 else None

            # Datas de pagamento (pais PAGO)
            dt_pag = max(
                (p.data_pagamento for p in pais if p.status == 'PAGO' and p.data_pagamento),
                default=None
            )

            # Label do período
            if data_inicio and data_fim:
                periodo = f"{data_inicio.strftime('%d/%m')}–{data_fim.strftime('%d/%m/%Y')}"
            else:
                periodo = "Mar/2026"

            # Criar novo pai consolidado
            novo_pai = GestaoCustoPai(
                tipo_categoria=tipo,
                entidade_nome=ent_nome,
                entidade_id=ent_id,
                valor_total=valor_total,
                valor_solicitado=valor_total,
                valor_pago=valor_pago if valor_pago else None,
                saldo=saldo,
                status=status_novo,
                data_pagamento=dt_pag,
                data_vencimento=data_fim,
                observacoes=f'Período: {periodo} ({len(todos_filhos)} lançamentos)',
                admin_id=ADMIN_ID,
            )
            db.session.add(novo_pai)
            db.session.flush()

            # Mover filhos para o novo pai
            obra_id_filho = todos_filhos[0].obra_id if todos_filhos else None
            for filho in todos_filhos:
                filho.pai_id = novo_pai.id
                filho.admin_id = ADMIN_ID

            # Apagar FluxoCaixa antigos ligados aos pais velhos (vamos recriar)
            for p in pais:
                FluxoCaixa.query.filter_by(
                    referencia_tabela='gestao_custo_pai',
                    referencia_id=p.id,
                    admin_id=ADMIN_ID
                ).delete()

            # Criar 1 FluxoCaixa consolidado para os PAGO
            if valor_pago > 0 and dt_pag:
                fc_consolidado = FluxoCaixa(
                    admin_id=ADMIN_ID,
                    data_movimento=dt_pag,
                    tipo_movimento='SAIDA',
                    categoria=tipo,
                    valor=valor_pago,
                    descricao=f'{tipo.capitalize()} pago - {ent_nome} ({periodo})',
                    obra_id=obra_id_filho,
                    referencia_id=novo_pai.id,
                    referencia_tabela='gestao_custo_pai',
                )
                db.session.add(fc_consolidado)

            # Deletar pais antigos (filhos já foram movidos)
            for p in pais:
                db.session.delete(p)

            db.session.flush()
            log(f"{tipo} | {ent_nome}: {len(pais)} → 1 pai (R$ {valor_total:.2f}, status={status_novo})")

    db.session.commit()
    log("Consolidação commitada")

    # ─────────────────────────────────────────────────────
    # 2. CORRIGIR percentual_planejado NOS APONTAMENTOS
    # ─────────────────────────────────────────────────────
    section("2. CORRIGINDO PERCENTUAIS DE APONTAMENTOS RDO")

    apontamentos = db.session.execute(text("""
        SELECT a.id, a.rdo_id, a.tarefa_cronograma_id,
               a.quantidade_executada_dia, a.quantidade_acumulada, a.percentual_realizado,
               r.data_relatorio,
               t.data_inicio, t.data_fim, t.duracao_dias, t.quantidade_total
        FROM rdo_apontamento_cronograma a
        JOIN rdo r ON r.id = a.rdo_id
        JOIN tarefa_cronograma t ON t.id = a.tarefa_cronograma_id
        WHERE r.admin_id = :aid
        ORDER BY a.tarefa_cronograma_id, r.data_relatorio
    """), {'aid': ADMIN_ID}).fetchall()

    corrigidos = 0
    # Acumular quantidade por tarefa para recalcular acumulada corretamente
    acumulado_por_tarefa = {}

    for row in apontamentos:
        ap_id = row[0]
        data_rdo = row[6]
        task_start = row[7]
        task_end = row[8]
        duracao = row[9] or 1
        qtd_total = row[10] or 1
        qtd_dia = row[3]
        tarefa_id = row[2]

        # Acumular quantidade real
        if tarefa_id not in acumulado_por_tarefa:
            acumulado_por_tarefa[tarefa_id] = 0.0
        acumulado_por_tarefa[tarefa_id] += (qtd_dia or 0)
        qtd_acumulada = acumulado_por_tarefa[tarefa_id]

        # Percentual realizado = acumulado / total
        perc_realizado = min(100.0, round(qtd_acumulada / qtd_total * 100, 1))

        # Percentual planejado = dias corridos desde início da tarefa até data_rdo / duração
        if task_start and data_rdo >= task_start:
            dias_corridos = (data_rdo - task_start).days + 1
            perc_planejado = min(100.0, round(dias_corridos / duracao * 100, 1))
        elif task_start and data_rdo < task_start:
            perc_planejado = 0.0
        else:
            perc_planejado = min(100.0, round((data_rdo.day) / duracao * 100, 1))

        db.session.execute(text("""
            UPDATE rdo_apontamento_cronograma
            SET percentual_planejado = :pp,
                percentual_realizado = :pr,
                quantidade_acumulada = :qa
            WHERE id = :id
        """), {
            'pp': perc_planejado,
            'pr': perc_realizado,
            'qa': qtd_acumulada,
            'id': ap_id,
        })
        corrigidos += 1

    db.session.commit()
    log(f"Apontamentos corrigidos: {corrigidos}")

    # ─────────────────────────────────────────────────────
    # 3. ATUALIZAR percentual_concluido DAS OBRAS
    # ─────────────────────────────────────────────────────
    section("3. ATUALIZANDO PROGRESSO GERAL DAS OBRAS")

    obras_v2 = db.session.execute(text(
        "SELECT id, nome FROM obra WHERE admin_id=:aid ORDER BY id"
    ), {'aid': ADMIN_ID}).fetchall()

    for obra_id, obra_nome in obras_v2:
        # Média do percentual_realizado das tarefas
        result = db.session.execute(text("""
            SELECT avg(a.percentual_realizado)
            FROM rdo_apontamento_cronograma a
            JOIN rdo r ON r.id=a.rdo_id
            WHERE r.obra_id=:oid AND r.admin_id=:aid
        """), {'oid': obra_id, 'aid': ADMIN_ID}).scalar()

        perc_obra = round(float(result or 0), 1)

        db.session.execute(text(
            "UPDATE tarefa_cronograma SET percentual_concluido=:p WHERE obra_id=:oid AND admin_id=:aid"
        ), {'p': perc_obra, 'oid': obra_id, 'aid': ADMIN_ID})

        log(f"Obra {obra_nome}: progresso médio = {perc_obra}%")

    db.session.commit()

    # ─────────────────────────────────────────────────────
    # 4. RELATÓRIO FINAL
    # ─────────────────────────────────────────────────────
    section("4. RELATÓRIO FINAL")

    n_pais = GestaoCustoPai.query.filter_by(admin_id=ADMIN_ID).count()
    n_filhos = GestaoCustoFilho.query.filter_by(admin_id=ADMIN_ID).count()
    n_fc = FluxoCaixa.query.filter_by(admin_id=ADMIN_ID).count()
    n_ap = db.session.execute(text(
        "SELECT count(*) FROM rdo_apontamento_cronograma a JOIN rdo r ON r.id=a.rdo_id WHERE r.admin_id=:aid"
    ), {'aid': ADMIN_ID}).scalar()

    rows = db.session.execute(text("""
        SELECT tipo_categoria, status, count(*), round(sum(valor_total)::numeric,2)
        FROM gestao_custo_pai WHERE admin_id=:aid
        GROUP BY tipo_categoria, status ORDER BY tipo_categoria, status
    """), {'aid': ADMIN_ID}).fetchall()

    print(f"""
  GestaoCustoPai total: {n_pais}
  GestaoCustoFilho total: {n_filhos}
  FluxoCaixa registros: {n_fc}
  Apontamentos RDO: {n_ap}

  GESTÃO DE CUSTOS POR TIPO:""")
    for r in rows:
        print(f"    {str(r[0]):<22} | {str(r[1]):<12} | {r[2]:>3} pais | R$ {float(r[3]):>10,.2f}")

    # Amostra de apontamentos corrigidos
    ap_sample = db.session.execute(text("""
        SELECT t.nome_tarefa, r.data_relatorio,
               a.percentual_planejado, a.percentual_realizado, a.quantidade_acumulada
        FROM rdo_apontamento_cronograma a
        JOIN rdo r ON r.id=a.rdo_id
        JOIN tarefa_cronograma t ON t.id=a.tarefa_cronograma_id
        WHERE r.admin_id=:aid AND r.obra_id=212
        ORDER BY a.tarefa_cronograma_id, r.data_relatorio
        LIMIT 12
    """), {'aid': ADMIN_ID}).fetchall()

    print("\n  AMOSTRA APONTAMENTOS OBRA RESIDENCIAL V2:")
    for r in ap_sample:
        status_ind = "OK" if r[3] >= r[2] else "ATRASADO"
        print(f"    {str(r[0]):<25} | {r[1].strftime('%d/%m')} | plan={r[2]:>5.1f}% | real={r[3]:>5.1f}% | acum={r[4]:>7.1f} [{status_ind}]")

    print("\n  CORREÇÃO CONCLUÍDA COM SUCESSO!")
