#!/usr/bin/env python3
"""Reconcilia o custo de mão de obra contado duas vezes — Step F do p1.

**O que aconteceu antes deste script.** Ponto e RDO lançavam o mesmo dia de
trabalho por caminhos diferentes, e nenhum dos dois dedups enxergava o outro:
o do RDO usa `rdo_id` na chave e o custo do ponto nasce com `rdo_id` NULL. Os
Steps C, D e E fecharam isso **para frente** (03/08). O que já está gravado
continua duplicado — é o que este script mede e, se você mandar, corrige.

**Decisão do Cássio, 03/08:** *"consertar para frente primeiro, reconciliar
depois."* Por isso a reconciliação é script assistido, e não migração de boot:
ela apaga dinheiro já lançado, e isso não acontece sozinho num deploy.

**Critério de quem sobrevive:** o lançamento do **PONTO**. Ele é o fato
medido — batida de crachá, com hora. O do RDO é declaração de quem preencheu
o relatório. Onde os dois existem para o mesmo (funcionário, dia, obra), o do
RDO sai.

Uso:

    # 1. Sempre primeiro — não escreve nada
    python scripts/reconciliar_custos_mao_obra.py
    python scripts/reconciliar_custos_mao_obra.py --admin-id 42

    # 2. Só depois de ler o relatório acima
    python scripts/reconciliar_custos_mao_obra.py --admin-id 42 --aplicar

## O que este script NÃO faz, de propósito

* **Não apaga `RDOMaoObra`.** A rota `excluir_filho`
  (`gestao_custos_views.py:620`) apaga o registro de ORIGEM junto com o custo
  — faz sentido para exclusão manual, seria destruição de registro de campo
  aqui. O apontamento do RDO é o que a obra viveu; o que sobra é o custo
  duplicado, não o apontamento.
* **Não toca em lançamento PAGO ou RECUSADO.** Custo pago tem contrapartida
  no financeiro; sumir com ele em silêncio é criar um segundo problema. Esses
  casos saem no relatório com a marca `PAGO` para tratamento manual.
* **Não decide por você.** Sem `--aplicar` ele só conta.
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CATEGORIAS_MAO_DE_OBRA = ('SALARIO', 'MAO_OBRA_DIRETA')
ORIGENS_DE_PONTO = ('registro_ponto',)
ORIGENS_DE_RDO = ('rdo_mao_obra',)


def pares_duplicados(admin_id=None) -> list:
    """(funcionário, dia, obra) com custo de ponto **e** de RDO no ledger V2.

    Requer app_context. Não escreve nada.
    """
    from models import GestaoCustoFilho, GestaoCustoPai, Usuario
    from app import db

    q = (
        db.session.query(
            GestaoCustoFilho.id,
            GestaoCustoFilho.admin_id,
            GestaoCustoFilho.data_referencia,
            GestaoCustoFilho.obra_id,
            GestaoCustoFilho.valor,
            GestaoCustoFilho.origem_tabela,
            GestaoCustoPai.entidade_id,
            GestaoCustoPai.entidade_nome,
            GestaoCustoPai.status,
        )
        .join(GestaoCustoPai, GestaoCustoFilho.pai_id == GestaoCustoPai.id)
        .filter(GestaoCustoPai.tipo_categoria.in_(CATEGORIAS_MAO_DE_OBRA))
        .filter(GestaoCustoFilho.origem_tabela.in_(
            ORIGENS_DE_PONTO + ORIGENS_DE_RDO))
    )
    if admin_id:
        q = q.filter(GestaoCustoFilho.admin_id == admin_id)

    # Agrupa em memória: a chave cruza ORIGENS, então não dá para agrupar no
    # banco sem repetir a mesma lógica em SQL.
    por_chave = defaultdict(lambda: {'ponto': [], 'rdo': []})
    for linha in q.all():
        chave = (linha.admin_id, linha.entidade_id, linha.data_referencia,
                 linha.obra_id)
        lado = 'ponto' if linha.origem_tabela in ORIGENS_DE_PONTO else 'rdo'
        por_chave[chave][lado].append(linha)

    duplicados = []
    for (adm, func_id, data, obra_id), lados in por_chave.items():
        if not (lados['ponto'] and lados['rdo']):
            continue
        nome = lados['rdo'][0].entidade_nome
        duplicados.append({
            'admin_id': adm,
            'funcionario_id': func_id,
            'funcionario': nome,
            'data': data,
            'obra_id': obra_id,
            'valor_ponto': float(sum(l.valor or 0 for l in lados['ponto'])),
            'valor_rdo': float(sum(l.valor or 0 for l in lados['rdo'])),
            'filhos_rdo': [(l.id, l.status) for l in lados['rdo']],
        })
    return sorted(duplicados, key=lambda d: (d['admin_id'], d['data'] or 0))


def custos_obra_duplicados(admin_id=None) -> list:
    """O mesmo par, no ledger legado `CustoObra`.

    O custo do ponto tem `categoria='PONTO_ELETRONICO'` e `rdo_id` NULL; o do
    RDO tem `rdo_id` preenchido. Requer app_context; não escreve.
    """
    from models import CustoObra
    from app import db

    q = db.session.query(CustoObra).filter(CustoObra.tipo == 'mao_obra')
    if admin_id:
        q = q.filter(CustoObra.admin_id == admin_id)

    por_chave = defaultdict(lambda: {'ponto': [], 'rdo': []})
    for c in q.all():
        if not c.funcionario_id or not c.data:
            continue
        chave = (c.admin_id, c.funcionario_id, c.data, c.obra_id)
        lado = 'rdo' if c.rdo_id else 'ponto'
        por_chave[chave][lado].append(c)

    return [
        {'admin_id': adm, 'funcionario_id': f, 'data': d, 'obra_id': o,
         'ids_rdo': [c.id for c in lados['rdo']],
         'valor_rdo': float(sum(c.valor or 0 for c in lados['rdo']))}
        for (adm, f, d, o), lados in por_chave.items()
        if lados['ponto'] and lados['rdo']
    ]


def _apagar_filho_preservando_origem(filho_id: int) -> bool:
    """Apaga UM `GestaoCustoFilho` sem tocar no registro de origem.

    Deliberadamente **não** usa a cascata de `excluir_filho`: aquela rota
    chama `_excluir_origem_de_filho` e apagaria o `RDOMaoObra` junto — o
    apontamento de campo, que é registro do que a obra viveu. Aqui o alvo é o
    custo duplicado, e só ele.

    Mantém a parte segura da rota: recalcula o total do pai e remove o pai se
    ele ficou sem filhos.
    """
    from models import GestaoCustoFilho, GestaoCustoPai
    from app import db

    filho = db.session.get(GestaoCustoFilho, filho_id)
    if not filho:
        return False

    pai = db.session.get(GestaoCustoPai, filho.pai_id)
    if pai is not None and pai.status in ('PAGO', 'RECUSADO'):
        return False

    pai_id = filho.pai_id
    db.session.delete(filho)
    db.session.flush()

    if pai is not None:
        restantes = GestaoCustoFilho.query.filter_by(pai_id=pai_id).count()
        if restantes == 0:
            db.session.delete(pai)
        else:
            try:
                from gestao_custos_views import _recalcular_total_pai
                _recalcular_total_pai(pai)
            except Exception:  # pragma: no cover - defensivo
                pass
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description='Reconcilia custo de mão de obra duplicado entre ponto e '
                    'RDO (Step F do p1)')
    parser.add_argument('--admin-id', type=int, default=None,
                        help='limita a um tenant (recomendado)')
    parser.add_argument('--aplicar', action='store_true',
                        help='ESCREVE: remove o lançamento de origem RDO onde '
                             'há ponto no mesmo dia. Sem esta flag, só conta.')
    args = parser.parse_args(argv)

    from app import app

    with app.app_context():
        duplicados = pares_duplicados(args.admin_id)
        legado = custos_obra_duplicados(args.admin_id)

        if not duplicados and not legado:
            print('Nada a reconciliar: nenhum dia com custo de ponto E de RDO.')
            return 0

        por_tenant = defaultdict(list)
        for d in duplicados:
            por_tenant[d['admin_id']].append(d)

        print(f'\n=== Gestão de Custos (V2) — {len(duplicados)} dia(s) '
              f'duplicado(s) em {len(por_tenant)} tenant(s) ===')
        total_geral = 0.0
        pagos = 0
        for adm, itens in sorted(por_tenant.items()):
            soma = sum(i['valor_rdo'] for i in itens)
            total_geral += soma
            print(f'\n  tenant {adm}: {len(itens)} dia(s), '
                  f'R$ {soma:,.2f} em duplicidade')
            for i in itens[:10]:
                travado = any(st in ('PAGO', 'RECUSADO')
                              for _fid, st in i['filhos_rdo'])
                if travado:
                    pagos += 1
                marca = '  [PAGO/RECUSADO — manual]' if travado else ''
                print(f"    - {i['data']} {i['funcionario']}: "
                      f"ponto R$ {i['valor_ponto']:,.2f} + "
                      f"RDO R$ {i['valor_rdo']:,.2f}{marca}")
            if len(itens) > 10:
                print(f'    … e mais {len(itens) - 10} dia(s).')

        print(f'\n  TOTAL em duplicidade: R$ {total_geral:,.2f}')
        if pagos:
            print(f'  ⚠️  {pagos} dia(s) com lançamento PAGO/RECUSADO — este '
                  f'script NÃO os toca. Trate manualmente.')

        print(f'\n=== CustoObra (ledger legado) — {len(legado)} dia(s) '
              f'duplicado(s), R$ '
              f'{sum(i["valor_rdo"] for i in legado):,.2f} ===')

        if not args.aplicar:
            print('\n[DRY-RUN] Nada foi escrito. Para aplicar, releia os '
                  'números acima e rode de novo com --aplicar.')
            return 0

        from app import db

        removidos_v2 = 0
        for i in duplicados:
            for filho_id, _status in i['filhos_rdo']:
                if _apagar_filho_preservando_origem(filho_id):
                    removidos_v2 += 1

        from models import CustoObra
        removidos_legado = 0
        for i in legado:
            for custo_id in i['ids_rdo']:
                custo = db.session.get(CustoObra, custo_id)
                if custo is not None:
                    db.session.delete(custo)
                    removidos_legado += 1

        db.session.commit()
        print(f'\n[APLICADO] {removidos_v2} lançamento(s) de RDO removido(s) '
              f'da Gestão de Custos e {removidos_legado} de CustoObra. '
              f'Nenhum RDOMaoObra foi tocado — o apontamento de campo '
              f'permanece.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
