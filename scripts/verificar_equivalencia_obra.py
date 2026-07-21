#!/usr/bin/env python3
"""Verificador de equivalência de obra (M09 — genérico, reutilizável no
rollout do M10).

Captura uma fotografia comparável do estado físico de uma obra (tarefas,
RDOs, apontamentos, fotos, mão de obra, percentuais, progresso geral nas
fontes do M06, medições e custos) e compara duas fotografias com tolerância
numérica. É o gate da migração (spec M09 §4.1.3): qualquer divergência
aborta (restaurar + investigar).

Uso (CLI):
    python scripts/verificar_equivalencia_obra.py <obra_id> <admin_id>
        [--salvar estado.json]          # captura e salva
        [--comparar estado.json]        # captura e compara com o salvo
        [--tolerancia 0.01]

Como módulo (testes/M10):
    from scripts.verificar_equivalencia_obra import (
        capturar_estado, comparar_estados)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def capturar_estado(obra_id: int, admin_id: int) -> dict:
    """Fotografia comparável do estado físico da obra. Requer app_context."""
    from sqlalchemy import func

    from app import db
    from models import (
        MedicaoContrato,
        RDO,
        RDOApontamentoCronograma,
        RDOFoto,
        RDOMaoObra,
        TarefaCronograma,
    )
    from utils.cronograma_engine import (
        calcular_progresso_geral_obra_v2,
        progresso_geral_para_kpi,
        rollup_realizado,
    )

    hoje = date.today()

    tarefas_vivas = (TarefaCronograma.query
                     .filter_by(obra_id=obra_id, admin_id=admin_id,
                                is_cliente=False)
                     .filter(TarefaCronograma.ativa.is_(True))
                     .order_by(TarefaCronograma.id)
                     .all())
    # % comparado só nas FOLHAS: é o trabalho real (apontamentos). Pais são
    # agregados por duração das filhas — durações mudam legitimamente na
    # migração (o rebuild antigo forçava dias>=1; o pipeline novo preserva
    # marcos com 0) e arrastariam falsos positivos de centésimos.
    pai_ids = {t.tarefa_pai_id for t in tarefas_vivas if t.tarefa_pai_id}
    pct_por_folha = {str(t.id): round(float(t.percentual_concluido or 0), 2)
                     for t in tarefas_vivas if t.id not in pai_ids}

    rdos = (RDO.query.filter_by(obra_id=obra_id)
            .order_by(RDO.data_relatorio, RDO.id).all())
    rdo_ids = [r.id for r in rdos]

    def _contar(modelo, campo_rdo='rdo_id'):
        if not rdo_ids:
            return 0
        return (db.session.query(func.count(modelo.id))
                .filter(getattr(modelo, campo_rdo).in_(rdo_ids)).scalar()) or 0

    n_apontamentos = _contar(RDOApontamentoCronograma)
    soma_qtd_dia = 0.0
    if rdo_ids:
        soma_qtd_dia = float(
            (db.session.query(func.coalesce(func.sum(
                RDOApontamentoCronograma.quantidade_executada_dia), 0.0))
             .filter(RDOApontamentoCronograma.rdo_id.in_(rdo_ids))
             .scalar()) or 0.0)

    # Progresso geral pelas fontes do M06 (devem concordar entre si).
    v2 = calcular_progresso_geral_obra_v2(
        obra_id, hoje, admin_id)['progresso_geral_pct']
    kpi = progresso_geral_para_kpi(obra_id, admin_id)
    curva = calcular_progresso_geral_obra_v2(
        obra_id, hoje, admin_id,
        com_arquivadas_historicas=True)['progresso_geral_pct']
    itens_rollup = [{
        'id': t.id, 'tarefa_pai_id': t.tarefa_pai_id, 'ordem': t.ordem,
        'duracao_dias': t.duracao_dias,
        'percentual_realizado': float(t.percentual_concluido or 0),
    } for t in tarefas_vivas]
    raizes = [t for t in tarefas_vivas if not t.tarefa_pai_id]
    agregados = rollup_realizado(itens_rollup)
    rollup_raiz = (round(agregados.get(raizes[0].id,
                                       float(raizes[0].percentual_concluido or 0)), 2)
                   if len(raizes) == 1 else None)

    medicoes = (db.session.query(
        func.count(MedicaoContrato.id),
        func.coalesce(func.sum(MedicaoContrato.pct), 0.0))
        .filter(MedicaoContrato.obra_id == obra_id).first())

    return {
        'obra_id': obra_id,
        'n_tarefas_ativas': len(tarefas_vivas),
        'pct_por_folha': pct_por_folha,
        'rdos': [r.data_relatorio.isoformat() for r in rdos],
        'n_apontamentos': int(n_apontamentos),
        'soma_quantidade_dia': round(soma_qtd_dia, 2),
        'n_fotos': int(_contar(RDOFoto)),
        'n_mao_obra': int(_contar(RDOMaoObra)),
        'progresso': {'v2': v2, 'kpi': kpi, 'curva_historica': curva,
                      'rollup_raiz': rollup_raiz},
        'medicoes': {'n': int(medicoes[0] or 0),
                     'soma_pct': round(float(medicoes[1] or 0), 4)},
    }


def comparar_estados(antes: dict, depois: dict, tolerancia: float = 0.01,
                     tolerancia_fontes: float = 0.1) -> dict:
    """Compara duas fotografias. Devolve {'equivalente': bool,
    'divergencias': [str]}. Percentual por tarefa comparado POR ID com
    `tolerancia`; as fontes de progresso do estado 'depois' precisam
    concordar ENTRE SI dentro de `tolerancia_fontes` (arredondamento de
    exibição). O progresso geral antes/depois NÃO é gate — marcos com
    duração 0 mudam pesos pós-M06 (ver plano M09)."""
    div = []

    for campo in ('n_tarefas_ativas', 'n_apontamentos', 'n_fotos',
                  'n_mao_obra'):
        if antes.get(campo) != depois.get(campo):
            div.append(f'{campo}: {antes.get(campo)} → {depois.get(campo)}')
    if antes.get('rdos') != depois.get('rdos'):
        div.append(f"rdos: {len(antes.get('rdos') or [])} data(s) → "
                   f"{len(depois.get('rdos') or [])} — listas diferem")
    if abs((antes.get('soma_quantidade_dia') or 0)
           - (depois.get('soma_quantidade_dia') or 0)) > tolerancia:
        div.append(f"soma_quantidade_dia: {antes.get('soma_quantidade_dia')} "
                   f"→ {depois.get('soma_quantidade_dia')}")

    pa, pd = antes.get('pct_por_folha') or {}, depois.get('pct_por_folha') or {}
    for tid in sorted(set(pa) | set(pd)):
        va, vd = pa.get(tid), pd.get(tid)
        if va is None or vd is None:
            div.append(f'folha {tid}: presente só em um lado '
                       f'(antes={va}, depois={vd})')
        elif abs(va - vd) > tolerancia:
            div.append(f'folha {tid}: percentual {va} → {vd}')

    med_a, med_d = antes.get('medicoes') or {}, depois.get('medicoes') or {}
    if med_a.get('n') != med_d.get('n'):
        div.append(f"medicoes.n: {med_a.get('n')} → {med_d.get('n')}")
    if abs((med_a.get('soma_pct') or 0) - (med_d.get('soma_pct') or 0)) > tolerancia:
        div.append(f"medicoes.soma_pct: {med_a.get('soma_pct')} → "
                   f"{med_d.get('soma_pct')}")

    # Concordância entre as fontes FLAT (v2/kpi/curva). O rollup_raiz é
    # agregação HIERÁRQUICA (pai por duração das filhas) — em árvores
    # profundas difere do flat por construção, e a própria tela do
    # cronograma substitui a linha raiz pelo v2; fica capturado só como
    # informação.
    fontes = depois.get('progresso') or {}
    valores = [v for v in (fontes.get('v2'), fontes.get('kpi'),
                           fontes.get('curva_historica')) if v is not None]
    if valores and max(valores) - min(valores) > tolerancia_fontes:
        div.append(f'fontes de progresso divergem entre si: {fontes}')

    return {'equivalente': not div, 'divergencias': div}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('obra_id', type=int)
    ap.add_argument('admin_id', type=int)
    ap.add_argument('--salvar')
    ap.add_argument('--comparar')
    ap.add_argument('--tolerancia', type=float, default=0.01)
    args = ap.parse_args()

    from app import app
    with app.app_context():
        estado = capturar_estado(args.obra_id, args.admin_id)

    if args.salvar:
        with open(args.salvar, 'w', encoding='utf-8') as fh:
            json.dump(estado, fh, ensure_ascii=False, indent=2)
        print(f'Estado salvo em {args.salvar} '
              f"({estado['n_tarefas_ativas']} tarefa(s), "
              f"{len(estado['rdos'])} RDO(s)).")
        return 0

    if args.comparar:
        with open(args.comparar, encoding='utf-8') as fh:
            antes = json.load(fh)
        resultado = comparar_estados(antes, estado, args.tolerancia)
        if resultado['equivalente']:
            print('EQUIVALENTE — nenhum desvio acima da tolerância.')
            return 0
        print('DIVERGENTE:')
        for d in resultado['divergencias']:
            print(f'  - {d}')
        return 1

    print(json.dumps(estado, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
