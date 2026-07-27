#!/usr/bin/env python3
"""Flag de rollout do RDO em porcentagem livre por tenant.

Com `configuracao_empresa.rdo_percentual_livre = TRUE` (migração 226,
default FALSE), TODA tarefa do cronograma passa a ser apontada em
percentual acumulado no RDO — o quantitativo cadastrado (`quantidade_total`
/ `unidade_medida`) vira referência de leitura — e o
`percentual_concluido` deixa de ser derivado de
`quantidade_acumulada / quantidade_total`, passando a vir do
`percentual_realizado` do apontamento mais recente.

Com a flag desligada o comportamento é exatamente o de hoje. Nenhum dado é
reescrito: `tarefa_cronograma.modo_apontamento` fica como está, então
desligar a flag reverte o sistema por completo. Este é o instrumento do
rollout: liga primeiro no tenant de homologação, depois no geral.

Uso (CLI):
    python scripts/flag_rdo_percentual_livre.py <admin_id> --status
    python scripts/flag_rdo_percentual_livre.py <admin_id> --ligar
    python scripts/flag_rdo_percentual_livre.py <admin_id> --desligar

Como módulo (testes/rollout):
    from scripts.flag_rdo_percentual_livre import definir_flag, status_flag
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _config_do_tenant(admin_id: int, criar: bool = False):
    """Devolve a ConfiguracaoEmpresa do tenant (criando o mínimo se pedido)."""
    from app import db
    from models import ConfiguracaoEmpresa, Usuario

    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    if config or not criar:
        return config

    admin = db.session.get(Usuario, admin_id)
    nome = getattr(admin, 'nome', None) or f'Empresa {admin_id}'
    config = ConfiguracaoEmpresa(admin_id=admin_id, nome_empresa=nome)
    db.session.add(config)
    db.session.flush()
    return config


def definir_flag(admin_id: int, ativo: bool) -> bool:
    """Liga/desliga a flag do tenant. Cria a configuração se não existir.

    Requer app_context. Devolve o estado gravado.
    """
    from app import db

    config = _config_do_tenant(admin_id, criar=True)
    config.rdo_percentual_livre = bool(ativo)
    db.session.commit()
    return bool(config.rdo_percentual_livre)


def status_flag(admin_id: int) -> dict:
    """Estado da flag do tenant (sem escrever). Requer app_context."""
    from app import db
    from models import Usuario

    admin = db.session.get(Usuario, admin_id)
    config = _config_do_tenant(admin_id)
    return {
        'admin_id': admin_id,
        'admin_existe': admin is not None,
        'versao_sistema': getattr(admin, 'versao_sistema', None),
        'tem_configuracao': config is not None,
        'rdo_percentual_livre': bool(config and config.rdo_percentual_livre),
    }


def tarefas_que_regridem(admin_id: int) -> list:
    """Tarefas que PERDERIAM físico se a flag fosse ligada agora.

    A premissa de continuidade da entrega — "linha quantitativa antiga já
    grava `percentual_realizado`, então a tarefa em 62% continua em 62%" —
    vale para o que o serviço de apontamento escreve HOJE (dupla escrita do
    M07), mas **não vale para toda linha legada**: existem apontamentos com
    `quantidade_acumulada > 0` e `percentual_realizado = 0`, escritos antes
    da dupla escrita ou por caminhos que só preenchiam quantidade.

    🔬 27/07, banco de dev (⚠️ dominado por carga de suíte — prova a FORMA do
    problema, não o volume de produção): 148 apontamentos assim, em 133
    tarefas de 84 tenants.

    Nessas tarefas o `percentual_concluido` hoje sai de
    `quantidade_acumulada / quantidade_total` e, com a flag ligada, passaria
    a sair do `percentual_realizado` — que é 0. A obra perderia avanço físico
    na tela sem ninguém apontar nada. Daí o guard.

    Devolve `[{'tarefa_id', 'nome', 'obra_id', 'pct_hoje', 'pct_apos'}]` da
    tarefa mais recente para trás. Requer app_context; nunca levanta.
    """
    try:
        from app import db
        from sqlalchemy import text

        linhas = db.session.execute(text("""
            SELECT t.id, t.nome_tarefa, t.obra_id,
                   ult.quantidade_acumulada, ult.percentual_realizado,
                   t.quantidade_total
            FROM tarefa_cronograma t
            JOIN LATERAL (
                SELECT a.quantidade_acumulada, a.percentual_realizado
                FROM rdo_apontamento_cronograma a
                JOIN rdo r ON r.id = a.rdo_id
                WHERE a.tarefa_cronograma_id = t.id
                  AND a.admin_id = :admin
                ORDER BY r.data_relatorio DESC, a.id DESC
                LIMIT 1
            ) ult ON TRUE
            WHERE t.admin_id = :admin
              AND t.ativa IS TRUE
              AND t.is_cliente IS FALSE
              AND t.quantidade_total IS NOT NULL
              AND t.quantidade_total > 0
        """), {'admin': admin_id}).fetchall()
    except Exception:
        return []

    regressoes = []
    for tid, nome, obra_id, acum, pct_real, total in linhas:
        # Mesma fórmula de `_atualizar_percentual_sem_commit`, dos dois lados.
        pct_hoje = min(100.0, round(float(acum or 0) / float(total) * 100, 2))
        pct_apos = min(100.0, float(pct_real or 0))
        if pct_apos < pct_hoje - 0.01:
            regressoes.append({
                'tarefa_id': tid, 'nome': nome, 'obra_id': obra_id,
                'pct_hoje': pct_hoje, 'pct_apos': pct_apos,
            })
    regressoes.sort(key=lambda r: r['pct_hoje'] - r['pct_apos'], reverse=True)
    return regressoes


def tarefas_quantitativas(admin_id: int) -> int:
    """Quantas tarefas do tenant hoje são apontadas por quantidade.

    São exatamente as que mudam de tela ao ligar a flag (passam a pedir %
    acumulado). Só informativo — nada é reescrito. Nunca levanta.
    """
    try:
        from models import TarefaCronograma
        return (TarefaCronograma.query
                .filter(TarefaCronograma.admin_id == admin_id)
                .filter(TarefaCronograma.modo_apontamento == 'quantidade')
                .count())
    except Exception:
        return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description='Flag de rollout do RDO em porcentagem livre')
    parser.add_argument('admin_id', type=int)
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument('--ligar', action='store_true')
    grupo.add_argument('--desligar', action='store_true')
    grupo.add_argument('--status', action='store_true')
    parser.add_argument('--forcar', action='store_true',
                        help='liga mesmo com tarefas que perderiam físico')
    args = parser.parse_args(argv)

    from app import app

    with app.app_context():
        estado = status_flag(args.admin_id)
        if not estado['admin_existe']:
            print(f"admin_id {args.admin_id} não existe")
            return 1

        # Guard ANTES de gravar. A versão anterior deste script chamava
        # `definir_flag` primeiro e só depois imprimia um aviso — quem lesse
        # o aviso já estaria com a flag ligada.
        regressoes = tarefas_que_regridem(args.admin_id) if args.ligar else []
        if regressoes and not args.forcar:
            print(f'ABORTADO: {len(regressoes)} tarefa(s) do tenant '
                  f'{args.admin_id} PERDERIAM avanço físico ao ligar a flag.')
            print('Elas têm quantidade acumulada mas `percentual_realizado` '
                  'zerado no apontamento mais recente — hoje o % sai da '
                  'quantidade, e com a flag ligada sairia do percentual.')
            for r in regressoes[:10]:
                print(f"  obra {r['obra_id']} · tarefa {r['tarefa_id']} "
                      f"{r['nome'][:44]:<44} {r['pct_hoje']:6.2f}% → "
                      f"{r['pct_apos']:6.2f}%")
            if len(regressoes) > 10:
                print(f'  … e mais {len(regressoes) - 10}.')
            print('Corrija os apontamentos dessas tarefas (reapontar o % na '
                  'tela do RDO resolve) ou use --forcar se a perda for '
                  'aceitável. Desligar a flag reverte de qualquer forma.')
            return 1

        if not args.status:
            definir_flag(args.admin_id, args.ligar)
            estado = status_flag(args.admin_id)
        quantitativas = tarefas_quantitativas(args.admin_id) if args.ligar else 0

    print(f"admin_id={estado['admin_id']} "
          f"versao_sistema={estado['versao_sistema']} "
          f"rdo_percentual_livre={estado['rdo_percentual_livre']}")
    if quantitativas:
        print(f"AVISO: {quantitativas} tarefa(s) deste tenant estavam em modo "
              "'quantidade' e passam a ser apontadas em % acumulado. O "
              "percentual atual é preservado nas tarefas cujo apontamento "
              "mais recente já grava `percentual_realizado` — que é o que a "
              "dupla escrita do M07 garante para o que se aponta HOJE, não "
              "para toda linha legada. O guard acima verificou tarefa a "
              "tarefa; desligar a flag reverte de qualquer forma.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
