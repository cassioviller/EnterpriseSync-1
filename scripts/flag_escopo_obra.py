#!/usr/bin/env python3
"""Liga/desliga o escopo por obra por tenant — SIGE Fase 1.

Uso:
    python scripts/flag_escopo_obra.py <admin_id> --ligar
    python scripts/flag_escopo_obra.py <admin_id> --desligar
    python scripts/flag_escopo_obra.py <admin_id> --status

ATENÇÃO: ligar sem popular `usuario_obra` para o tenant faz todo
usuário não-ADMIN enxergar zero obras. Rode antes:
    python scripts/backfill_usuario_obra.py --admin-id <id> --aplicar
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import ConfiguracaoEmpresa, Usuario, db


def escopo_ativo(admin_id):
    """True se o tenant já usa escopo por obra. Falha para False."""
    if not admin_id:
        return False
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    if config is None:
        return False
    return bool(getattr(config, 'escopo_obra_ativo', False))


def definir_flag(admin_id, ligado):
    """Liga/desliga, criando a ConfiguracaoEmpresa se não existir.

    `nome_empresa` é NOT NULL: criar a linha sem ele estoura
    NotNullViolation. Mesma derivação do precedente
    `scripts/flag_cronograma_mpp.py:39-41` — nome do admin, ou um rótulo
    com o id quando o admin não tem nome.
    """
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
    if config is None:
        admin = db.session.get(Usuario, admin_id)
        nome = getattr(admin, 'nome', None) or f'Empresa {admin_id}'
        config = ConfiguracaoEmpresa(admin_id=admin_id, nome_empresa=nome)
        db.session.add(config)
    config.escopo_obra_ativo = bool(ligado)
    db.session.commit()
    return config.escopo_obra_ativo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('admin_id', type=int)
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument('--ligar', action='store_true')
    grupo.add_argument('--desligar', action='store_true')
    grupo.add_argument('--status', action='store_true')
    args = parser.parse_args()

    from app import app
    with app.app_context():
        if args.status:
            print(f'admin_id={args.admin_id} escopo_obra_ativo='
                  f'{escopo_ativo(args.admin_id)}')
            return 0

        from models import UsuarioObra
        if args.ligar:
            vinculos = UsuarioObra.query.filter_by(
                admin_id=args.admin_id, ativo=True).count()
            nao_admins = Usuario.query.filter_by(
                admin_id=args.admin_id, ativo=True).count()
            if vinculos == 0 and nao_admins > 0:
                print(f'ABORTADO: o tenant {args.admin_id} tem {nao_admins} '
                      f'usuário(s) não-admin e ZERO vínculos em usuario_obra. '
                      f'Ligar agora tiraria o acesso de todos eles.')
                print('Rode antes: python scripts/backfill_usuario_obra.py '
                      f'--admin-id {args.admin_id} --aplicar')
                return 1

        novo = definir_flag(args.admin_id, args.ligar)
        print(f'admin_id={args.admin_id} escopo_obra_ativo={novo}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
