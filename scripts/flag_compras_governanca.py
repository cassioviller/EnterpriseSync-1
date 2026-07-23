#!/usr/bin/env python3
"""Liga/desliga a governança de compras por tenant — Fase 3.

Uso:
    python scripts/flag_compras_governanca.py <admin_id> --ligar
    python scripts/flag_compras_governanca.py <admin_id> --desligar
    python scripts/flag_compras_governanca.py <admin_id>          # consulta

Ligar a flag muda comportamento de produção: `POST /compras/nova` passa a
recusar pedido sem requisição aprovada. O guard do `--ligar` recusa
tenants que ainda não têm faixa de alçada configurada — ligar sem faixa
faria toda compra cair na faixa de segurança (2 aprovações + ADMIN) e
travaria o canteiro.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def governanca_ativa(admin_id):
    """True se o tenant tem a governança ligada. Falha FECHADA para o
    comportamento ANTIGO: qualquer erro devolve False."""
    if not admin_id:
        return False
    try:
        from models import ConfiguracaoEmpresa
        cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
        return bool(cfg and cfg.compras_governanca_ativa)
    except Exception:
        return False


def definir_flag(admin_id, valor):
    """Grava a flag, criando a ConfiguracaoEmpresa se ela não existir.

    `nome_empresa` é NOT NULL (models.py:3596); num tenant que nunca abriu
    a tela de configurações a linha não existe, e é preciso criá-la com um
    nome provisório em vez de estourar.
    """
    from app import db
    from models import ConfiguracaoEmpresa, Usuario

    cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    if cfg is None:
        usuario = db.session.get(Usuario, admin_id)
        cfg = ConfiguracaoEmpresa(
            admin_id=admin_id,
            nome_empresa=(usuario.nome if usuario else f'Tenant {admin_id}'))
        db.session.add(cfg)
    cfg.compras_governanca_ativa = bool(valor)
    db.session.commit()
    return cfg.compras_governanca_ativa


def _tem_faixa(admin_id):
    from models import FaixaAlcada
    return FaixaAlcada.query.filter_by(admin_id=admin_id, ativo=True).count() > 0


def main():
    parser = argparse.ArgumentParser(description='Flag de governança de compras')
    parser.add_argument('admin_id', type=int)
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument('--ligar', action='store_true')
    grupo.add_argument('--desligar', action='store_true')
    parser.add_argument('--forcar', action='store_true',
                        help='liga mesmo sem faixa de alçada configurada')
    args = parser.parse_args()

    from app import app
    with app.app_context():
        if args.ligar:
            if not _tem_faixa(args.admin_id) and not args.forcar:
                print(f'RECUSADO: tenant {args.admin_id} não tem faixa de '
                      f'alçada ativa. Toda compra cairia na faixa de '
                      f'segurança (2 aprovações + ADMIN). Rode a migration '
                      f'243 ou use --forcar se for isso mesmo.')
                return 1
            definir_flag(args.admin_id, True)
            print(f'tenant {args.admin_id}: governança de compras LIGADA')
        elif args.desligar:
            definir_flag(args.admin_id, False)
            print(f'tenant {args.admin_id}: governança de compras DESLIGADA')
        else:
            estado = 'LIGADA' if governanca_ativa(args.admin_id) else 'DESLIGADA'
            print(f'tenant {args.admin_id}: governança de compras {estado}')
        return 0


if __name__ == '__main__':
    sys.exit(main())
