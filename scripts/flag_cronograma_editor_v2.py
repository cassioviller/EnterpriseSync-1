#!/usr/bin/env python3
"""Flag de rollout do editor de cronograma v2 por tenant (Fase 1).

O motor de agendamento novo (multi-predecessoras via `tarefa_vinculo`,
caminho crítico, recálculo em cascata) só liga para tenant V2 **com**
`configuracao_empresa.cronograma_editor_v2 = TRUE` (migração 222, default
FALSE). Com a flag desligada, cada rota do cronograma executa exatamente o
código de hoje (engine antigo). Este é o instrumento do rollout: liga
primeiro no tenant de homologação, depois na obra piloto, por último no
geral.

Uso (CLI):
    python scripts/flag_cronograma_editor_v2.py <admin_id> --status
    python scripts/flag_cronograma_editor_v2.py <admin_id> --ligar
    python scripts/flag_cronograma_editor_v2.py <admin_id> --desligar

Como módulo (testes/rollout):
    from scripts.flag_cronograma_editor_v2 import definir_flag, status_flag

Nota: o motor novo usa calendário FIXO seg–sex nesta fase — ao ligar a
flag num tenant cujo `CalendarioEmpresa` considera sábado/domingo, o
recálculo passa a ignorar essa configuração (aviso emitido pelo CLI).
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
    config.cronograma_editor_v2 = bool(ativo)
    db.session.commit()
    return bool(config.cronograma_editor_v2)


def status_flag(admin_id: int) -> dict:
    """Estado da flag do tenant (sem escrever). Requer app_context."""
    from models import Usuario
    from app import db

    admin = db.session.get(Usuario, admin_id)
    config = _config_do_tenant(admin_id)
    return {
        'admin_id': admin_id,
        'admin_existe': admin is not None,
        'versao_sistema': getattr(admin, 'versao_sistema', None),
        'tem_configuracao': config is not None,
        'cronograma_editor_v2': bool(config and config.cronograma_editor_v2),
    }


def calendario_diverge(admin_id: int) -> bool:
    """True se o CalendarioEmpresa do tenant considera sábado ou domingo.

    O motor novo é seg–sex fixo nesta fase — nesse caso ligar a flag muda o
    calendário efetivo do recálculo. Requer app_context; nunca levanta.
    """
    try:
        from models import CalendarioEmpresa
        cal = CalendarioEmpresa.query.filter_by(admin_id=admin_id).first()
        return bool(cal and (cal.considerar_sabado or cal.considerar_domingo))
    except Exception:
        return False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description='Flag de rollout do editor de cronograma v2 (Fase 1)')
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
        diverge = args.ligar and calendario_diverge(args.admin_id)

    if not estado['admin_existe']:
        print(f"admin_id {args.admin_id} não existe")
        return 1

    print(f"admin_id={estado['admin_id']} "
          f"versao_sistema={estado['versao_sistema']} "
          f"cronograma_editor_v2={estado['cronograma_editor_v2']}")
    if estado['cronograma_editor_v2'] and estado['versao_sistema'] != 'v2':
        print("AVISO: flag ligada mas o tenant não é V2 — o motor novo segue inativo.")
    if diverge:
        print("AVISO: o CalendarioEmpresa deste tenant considera sábado e/ou "
              "domingo, mas o motor novo usa calendário fixo seg–sex nesta "
              "fase — o recálculo vai ignorar essa configuração.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
