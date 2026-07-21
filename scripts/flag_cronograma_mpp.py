#!/usr/bin/env python3
"""Flag de rollout da importação de cronograma por tenant (M10).

A área de cronograma da obra (M08) só aparece para tenant V2 **com**
`configuracao_empresa.cronograma_mpp_ativo = TRUE` (migração 211, default
FALSE). Este é o instrumento das fases 1-3 do rollout: liga primeiro no
tenant de homologação, depois na obra piloto/baias, por último no geral.

Uso (CLI):
    python scripts/flag_cronograma_mpp.py <admin_id> --status
    python scripts/flag_cronograma_mpp.py <admin_id> --ligar
    python scripts/flag_cronograma_mpp.py <admin_id> --desligar

Como módulo (testes/rollout):
    from scripts.flag_cronograma_mpp import definir_flag, status_flag

Nota: a flag governa a BORDA visual. Os endpoints de importação seguem
protegidos por `cronograma_import_required` + escopo de tenant — desligar
a flag esconde a área, não é controle de acesso.
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
    config.cronograma_mpp_ativo = bool(ativo)
    db.session.commit()
    return bool(config.cronograma_mpp_ativo)


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
        'cronograma_mpp_ativo': bool(config and config.cronograma_mpp_ativo),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description='Flag de rollout da importação de cronograma (M10)')
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

    if not estado['admin_existe']:
        print(f"admin_id {args.admin_id} não existe")
        return 1

    print(f"admin_id={estado['admin_id']} "
          f"versao_sistema={estado['versao_sistema']} "
          f"cronograma_mpp_ativo={estado['cronograma_mpp_ativo']}")
    if estado['cronograma_mpp_ativo'] and estado['versao_sistema'] != 'v2':
        print("AVISO: flag ligada mas o tenant não é V2 — a área segue oculta.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
