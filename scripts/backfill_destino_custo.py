#!/usr/bin/env python3
"""Backfill do destino do custo — SIGE Fase 4.

DRY-RUN POR PADRÃO. Sem `--aplicar` este script não escreve uma linha.

Uso:
    python scripts/backfill_destino_custo.py                  # relatório global
    python scripts/backfill_destino_custo.py --tenant 832     # um tenant
    python scripts/backfill_destino_custo.py --csv /tmp/f4.csv
    python scripts/backfill_destino_custo.py --aplicar        # grava

O relatório responde três perguntas, nesta ordem:
  1. quantos `gestao_custo_pai` têm obra recuperável por unanimidade (R1);
  2. quantos são multi-obra — que NÃO são defeito, são projeto;
  3. quantos `gestao_custo_filho` continuam sem destino, e por qual regra
     cada um seria resolvido.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _pais_e_obras(admin_id=None):
    """Devolve {pai_id: (admin_id, [obra_id dos filhos])} — inclui pai sem filho."""
    from app import db
    from models import GestaoCustoFilho, GestaoCustoPai

    q_pai = db.session.query(GestaoCustoPai.id, GestaoCustoPai.admin_id)
    if admin_id:
        q_pai = q_pai.filter(GestaoCustoPai.admin_id == admin_id)
    mapa = {pid: (aid, []) for pid, aid in q_pai.all()}

    q_filho = db.session.query(GestaoCustoFilho.pai_id, GestaoCustoFilho.obra_id)
    if admin_id:
        q_filho = q_filho.filter(GestaoCustoFilho.admin_id == admin_id)
    for pai_id, obra_id in q_filho.all():
        if pai_id in mapa:
            mapa[pai_id][1].append(obra_id)
    return mapa


def _regra_para_filho(filho, obra_do_pai):
    """Qual regra resolveria este filho órfão. Devolve (regra, obra_id|None)."""
    from app import db
    from sqlalchemy import text as _text

    from services.destino_custo import (ORIGENS_ADMINISTRATIVAS,
                                        ORIGENS_COM_OBRA)

    if obra_do_pai is not None:
        return ('R2_irmao_unanime', obra_do_pai)

    origem = filho.origem_tabela or ''
    if origem in ORIGENS_COM_OBRA and filho.origem_id:
        tabela, coluna = ORIGENS_COM_OBRA[origem]
        achado = db.session.execute(
            _text(f'SELECT {coluna} FROM {tabela} WHERE id = :oid'),  # noqa: S608
            {'oid': filho.origem_id},
        ).scalar()
        if achado:
            return ('R3_origem', achado)

    if origem in ORIGENS_ADMINISTRATIVAS:
        return ('R4_natureza_origem', None)

    return ('R5_fallback', None)


def diagnosticar(admin_id=None):
    """Relatório READ-ONLY. Não grava nada, nem faz flush."""
    from app import db
    from models import GestaoCustoFilho, GestaoCustoPai
    from services.destino_custo import classificar_pai

    mapa = _pais_e_obras(admin_id)

    situacoes = Counter()
    obra_por_pai = {}
    for pai_id, (_aid, obras) in mapa.items():
        situacao, obra_id = classificar_pai(obras)
        situacoes[situacao] += 1
        obra_por_pai[pai_id] = obra_id

    q_orfaos = db.session.query(GestaoCustoFilho).filter(
        GestaoCustoFilho.obra_id.is_(None),
        GestaoCustoFilho.centro_custo_id.is_(None),
    )
    if admin_id:
        q_orfaos = q_orfaos.filter(GestaoCustoFilho.admin_id == admin_id)
    orfaos = q_orfaos.all()

    regras = Counter()
    detalhe = []
    for filho in orfaos:
        regra, obra_id = _regra_para_filho(filho, obra_por_pai.get(filho.pai_id))
        regras[regra] += 1
        detalhe.append({
            'filho_id': filho.id,
            'pai_id': filho.pai_id,
            'admin_id': filho.admin_id,
            'data_referencia': str(filho.data_referencia),
            'descricao': (filho.descricao or '')[:80],
            'valor': str(filho.valor),
            'origem_tabela': filho.origem_tabela or '',
            'origem_id': filho.origem_id or '',
            'regra': regra,
            'obra_derivada': obra_id or '',
        })

    total_pai = db.session.query(GestaoCustoPai).count() if not admin_id else \
        db.session.query(GestaoCustoPai).filter(
            GestaoCustoPai.admin_id == admin_id).count()

    return {
        'pai': {
            'total': total_pai,
            'unanime': situacoes['unanime'],
            'multiobra': situacoes['multiobra'],
            'sem_obra': situacoes['sem_obra'],
            'sem_filho': situacoes['sem_filho'],
        },
        'filho': {
            'sem_destino': len(orfaos),
            'por_regra': dict(regras),
        },
        'detalhe': detalhe,
    }


def aplicar_pais(admin_id=None, lote=500):
    """R1 — grava `gestao_custo_pai.obra_id` por unanimidade dos filhos.

    Idempotente: recalcula sempre e só toca a linha quando o valor MUDA.
    Multi-obra e sem-obra ficam (ou voltam a ficar) NULL de propósito — a
    coluna é derivada, não é opinião gravada.

    Não faz commit: quem chama controla a transação. O `main()` comita.
    """
    from app import db
    from models import GestaoCustoPai
    from services.destino_custo import classificar_pai

    mapa = _pais_e_obras(admin_id)
    alvo = {}
    for pai_id, (_aid, obras) in mapa.items():
        _situacao, obra_id = classificar_pai(obras)
        alvo[pai_id] = obra_id

    atualizados = 0
    ids = list(alvo)
    for inicio in range(0, len(ids), lote):
        pedaco = ids[inicio:inicio + lote]
        pais = GestaoCustoPai.query.filter(GestaoCustoPai.id.in_(pedaco)).all()
        for pai in pais:
            novo = alvo.get(pai.id)
            if pai.obra_id != novo:
                pai.obra_id = novo
                atualizados += 1
        db.session.flush()

    return {'avaliados': len(ids), 'atualizados': atualizados}


def aplicar_filhos(admin_id=None):
    """R2-R5 — dá destino a todo `gestao_custo_filho` sem obra e sem centro.

    Ordem de aplicação, parando no primeiro que resolve:
      R2  irmão unânime      → herda `pai.obra_id`
      R3  origem             → herda a obra da linha de origem
      R4  natureza da origem → centro administrativo (folha, almoxarifado)
      R5  resto              → centro administrativo + carimbo [FASE4:R5]
                               nas `observacoes` do pai, para revisão humana

    Pressupõe `aplicar_pais` já rodado (R2 lê `pai.obra_id`).
    Idempotente: só olha linhas que ainda estão sem destino.
    Não faz commit.
    """
    from collections import Counter

    from app import db
    from models import GestaoCustoFilho, GestaoCustoPai
    from services.destino_custo import MARCA_FALLBACK
    from utils.centro_custo import id_do_centro_administrativo

    q = db.session.query(GestaoCustoFilho).filter(
        GestaoCustoFilho.obra_id.is_(None),
        GestaoCustoFilho.centro_custo_id.is_(None),
    )
    if admin_id:
        q = q.filter(GestaoCustoFilho.admin_id == admin_id)
    orfaos = q.all()

    if not orfaos:
        return {'avaliados': 0, 'atualizados': 0, 'por_regra': {}}

    pai_ids = {f.pai_id for f in orfaos}
    pais = {p.id: p for p in
            GestaoCustoPai.query.filter(GestaoCustoPai.id.in_(pai_ids)).all()}

    centro_por_tenant = {}
    regras = Counter()
    atualizados = 0
    pais_marcados = set()

    for filho in orfaos:
        pai = pais.get(filho.pai_id)
        obra_do_pai = pai.obra_id if pai else None
        regra, obra_id = _regra_para_filho(filho, obra_do_pai)

        if obra_id:
            filho.obra_id = obra_id
        else:
            tenant = filho.admin_id
            if tenant not in centro_por_tenant:
                centro_por_tenant[tenant] = id_do_centro_administrativo(
                    tenant, criar=True)
            centro_id = centro_por_tenant[tenant]
            if not centro_id:
                logger_aviso = (
                    f'filho {filho.id}: tenant {tenant} sem centro '
                    'administrativo — linha deixada como está')
                print(f'  AVISO {logger_aviso}')
                continue
            filho.centro_custo_id = centro_id
            if regra == 'R5_fallback' and pai is not None \
                    and pai.id not in pais_marcados:
                atual = pai.observacoes or ''
                if MARCA_FALLBACK not in atual:
                    pai.observacoes = f'{MARCA_FALLBACK} {atual}'.strip()[:2000]
                pais_marcados.add(pai.id)

        regras[regra] += 1
        atualizados += 1

    db.session.flush()
    return {'avaliados': len(orfaos), 'atualizados': atualizados,
            'por_regra': dict(regras)}


def imprimir(rel):
    p, f = rel['pai'], rel['filho']
    cobertos = p['unanime']
    pct = (100.0 * cobertos / p['total']) if p['total'] else 0.0
    print('=' * 72)
    print('FASE 4 — DESTINO DO CUSTO')
    print('=' * 72)
    print(f"gestao_custo_pai .......... {p['total']:>7}")
    print(f"  R1 obra unânime ......... {p['unanime']:>7}  ({pct:.1f}%)")
    print(f"  multi-obra (fica NULL) .. {p['multiobra']:>7}  <- projeto, não defeito")
    print(f"  filhos sem obra ......... {p['sem_obra']:>7}")
    print(f"  sem filho nenhum ........ {p['sem_filho']:>7}")
    print('-' * 72)
    print(f"gestao_custo_filho sem destino: {f['sem_destino']}")
    for regra in sorted(f['por_regra']):
        print(f"  {regra:<22} {f['por_regra'][regra]:>7}")
    print('=' * 72)


def escrever_csv(rel, caminho):
    campos = ['filho_id', 'pai_id', 'admin_id', 'data_referencia', 'descricao',
              'valor', 'origem_tabela', 'origem_id', 'regra', 'obra_derivada']
    with open(caminho, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        for linha in rel['detalhe']:
            w.writerow(linha)
    print(f'CSV escrito em {caminho} ({len(rel["detalhe"])} linha(s))')


def main():
    ap = argparse.ArgumentParser(description='Backfill do destino do custo (Fase 4)')
    ap.add_argument('--tenant', type=int, default=None, help='admin_id')
    ap.add_argument('--csv', default=None, help='arquivo do detalhe dos órfãos')
    ap.add_argument('--aplicar', action='store_true',
                    help='GRAVA. Sem esta flag o script é read-only.')
    args = ap.parse_args()

    from app import app, db

    with app.app_context():
        rel = diagnosticar(admin_id=args.tenant)
        imprimir(rel)
        if args.csv:
            escrever_csv(rel, args.csv)
        if not args.aplicar:
            print('\nDRY-RUN — nada foi gravado. Use --aplicar para gravar.')
            return

        print('\n--aplicar: gravando…')
        r_pai = aplicar_pais(admin_id=args.tenant)
        db.session.commit()
        print(f"R1 gestao_custo_pai.obra_id: {r_pai['atualizados']} de "
              f"{r_pai['avaliados']} atualizado(s)")

        r_filho = aplicar_filhos(admin_id=args.tenant)
        db.session.commit()
        print(f"R2-R5 gestao_custo_filho: {r_filho['atualizados']} de "
              f"{r_filho['avaliados']} resolvido(s)")
        for regra in sorted(r_filho['por_regra']):
            print(f"    {regra:<22} {r_filho['por_regra'][regra]:>7}")

        print('\nRelatório pós-aplicação:')
        imprimir(diagnosticar(admin_id=args.tenant))


if __name__ == '__main__':
    main()
