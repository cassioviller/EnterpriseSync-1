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
    args = parser.parse_args(argv)

    from app import app

    with app.app_context():
        if args.status:
            estado = status_flag(args.admin_id)
        else:
            definir_flag(args.admin_id, args.ligar)
            estado = status_flag(args.admin_id)
        quantitativas = tarefas_quantitativas(args.admin_id) if args.ligar else 0

    if not estado['admin_existe']:
        print(f"admin_id {args.admin_id} não existe")
        return 1

    print(f"admin_id={estado['admin_id']} "
          f"versao_sistema={estado['versao_sistema']} "
          f"rdo_percentual_livre={estado['rdo_percentual_livre']}")
    if quantitativas:
        print(f"AVISO: {quantitativas} tarefa(s) deste tenant estavam em modo "
              "'quantidade' e passam a ser apontadas em % acumulado. O "
              "percentual atual é preservado (as linhas quantitativas já "
              "gravam percentual_realizado); desligar a flag reverte.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
