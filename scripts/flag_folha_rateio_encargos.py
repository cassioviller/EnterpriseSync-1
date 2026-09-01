#!/usr/bin/env python3
"""Flag do rateio de encargos patronais por obra, por tenant (A24).

Com `configuracao_empresa.folha_rateio_encargos = TRUE` (migração 318,
default FALSE), processar a folha do mês também grava a folha rateada por
obra em `FolhaProcessada` — com `encargos_fgts` e `encargos_inss_patronal`
por fatia — pelo pipeline `processar_e_salvar_folha_obra`
(`services/folha_service.py`), que estava correto, testado e sem chamador:
a mão de obra saía ~28% subestimada no custo de obra.

Com a flag desligada o comportamento é exatamente o de hoje. Nenhum dado é
reescrito ao ligar; desligar reverte por completo (as linhas já rateadas
ficam, e `salvar_folha_processada` faz upsert no reprocessamento).

⚠️ RATIFICAR com o dono antes de ligar em produção: o custo de obra vai
subir ~28% na mão de obra a partir da vigência — quem lê o resultado
precisa saber ANTES, ou vai achar que a operação piorou.

Uso (CLI):
    python scripts/flag_folha_rateio_encargos.py <admin_id> --status
    python scripts/flag_folha_rateio_encargos.py <admin_id> --ligar
    python scripts/flag_folha_rateio_encargos.py <admin_id> --desligar

Como módulo (testes/rollout):
    from scripts.flag_folha_rateio_encargos import definir_flag, status_flag

Espelho de scripts/flag_rdo_percentual_livre.py (migração 226).
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
    config.folha_rateio_encargos = bool(ativo)
    db.session.commit()
    return bool(config.folha_rateio_encargos)


def status_flag(admin_id: int) -> dict:
    """Estado da flag do tenant (sem escrever). Requer app_context."""
    from app import db
    from models import Usuario

    admin = db.session.get(Usuario, admin_id)
    config = _config_do_tenant(admin_id)
    return {
        'admin_id': admin_id,
        'admin_existe': admin is not None,
        'tem_configuracao': config is not None,
        'folha_rateio_encargos': bool(config and config.folha_rateio_encargos),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description='Flag do rateio de encargos patronais por obra (A24)')
    parser.add_argument('admin_id', type=int)
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument('--ligar', action='store_true')
    grupo.add_argument('--desligar', action='store_true')
    grupo.add_argument('--status', action='store_true')
    args = parser.parse_args(argv)

    from app import app

    with app.app_context():
        estado = status_flag(args.admin_id)
        if not estado['admin_existe']:
            print(f"admin_id {args.admin_id} não existe")
            return 1

        if not args.status:
            definir_flag(args.admin_id, args.ligar)
            estado = status_flag(args.admin_id)

    print(f"admin_id={estado['admin_id']} "
          f"folha_rateio_encargos={estado['folha_rateio_encargos']}")
    if not args.status and args.ligar:
        print('AVISO: a partir do próximo processamento de folha, o custo de '
              'obra passa a carregar a mão de obra COM encargos (~28% a mais '
              'na rubrica). Quem lê custo por obra precisa saber disso antes.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
