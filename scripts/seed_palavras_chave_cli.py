"""
CLI — semeia as Regras de Classificação do sistema (origem='sistema') por tenant.

Uso:
  python scripts/seed_palavras_chave_cli.py <admin_id>     # um tenant
  python scripts/seed_palavras_chave_cli.py --todos        # todos os admins

Idempotente: re-rodar não duplica. Requer as categorias de fluxo de caixa já
semeadas no tenant (CategoriaFluxoCaixa.seed_defaults).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from services.seed_palavras_chave import seed_para_admin


def _admins_alvo(args):
    from models import Usuario, TipoUsuario
    if '--todos' in args:
        return [u.id for u in Usuario.query.filter(
            Usuario.tipo_usuario.in_([TipoUsuario.ADMIN, TipoUsuario.SUPER_ADMIN])
        ).all()]
    ids = [int(a) for a in args if a.isdigit()]
    return ids


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    with app.app_context():
        alvos = _admins_alvo(args)
        if not alvos:
            print("Nenhum admin_id informado. Use <admin_id> ou --todos.")
            return
        total = 0
        for admin_id in alvos:
            try:
                n = seed_para_admin(admin_id, commit=True)
                total += n
                print(f"admin {admin_id}: {n} regras criadas")
            except Exception as e:
                db.session.rollback()
                print(f"admin {admin_id}: ERRO — {e}")
        print(f"Concluído. {total} regras criadas em {len(alvos)} tenant(s).")


if __name__ == "__main__":
    main()
