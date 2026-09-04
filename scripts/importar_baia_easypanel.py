"""Import de produção da Obra Baia REV10 — comando único para o EasyPanel.

Roda a cadeia completa, a partir do arquivo `IMPORTACAO_Baia_REV10_completa.xlsx`,
SEM nenhuma configuração manual:

    xlsx (catálogo)  →  Orçamento (itens + composição)  →  CronogramaTemplate
    (28 atividades, peso do cronograma refinado)  →  Obra + ItemMedicaoComercial
    + Cronograma multi-atividade vinculados.

Idempotente: se a obra da Baia já existe para o admin, não recria. Em produção:

    python -m scripts.importar_baia_easypanel            # usa o 1º admin
    python -m scripts.importar_baia_easypanel <admin_id> # admin específico
"""
import sys

from app import app, db
from models import Usuario, Orcamento, Proposta

XLSX_PADRAO = 'obra_kabod/IMPORTACAO_Baia_REV10_completa.xlsx'
NUMERO = 'ORC-BAIA-REV10'


def importar_baia_completa(admin_id, xlsx_path=XLSX_PADRAO):
    """Cadeia completa Baia (catálogo→orçamento→templates→obra). Idempotente.
    Deve rodar dentro de app_context. Retorna dict com ids e contagens."""
    from scripts.criar_orcamento_baia_rev10 import criar_orcamento_baia
    from scripts.seed_templates_baia_rev10 import seed_templates_baia
    from services.importar_obra_completa import importar_obra_completa

    # idempotência no nível da obra: Baia já importada?
    orc = Orcamento.query.filter_by(admin_id=admin_id, numero=NUMERO).first()
    if orc:
        prop = Proposta.query.filter_by(orcamento_id=orc.id, admin_id=admin_id).first()
        if prop and prop.obra_id:
            return {'criado': False, 'orcamento_id': orc.id,
                    'proposta_id': prop.id, 'obra_id': prop.obra_id}

    # 1) catálogo + orçamento (do xlsx)
    orcamento_id = criar_orcamento_baia(admin_id, xlsx_path)
    # 2) templates do cronograma refinado (28 atividades, pesos explícitos)
    seed_templates_baia(admin_id, orcamento_id)
    # 3) obra + IMC + cronograma multi-atividade
    res = importar_obra_completa(orcamento_id, admin_id)
    res['orcamento_id'] = orcamento_id
    return res


def main():
    with app.app_context():
        if len(sys.argv) > 1:
            admin_id = int(sys.argv[1])
        else:
            u = Usuario.query.filter_by(tipo_usuario='ADMIN').first() or Usuario.query.first()
            admin_id = u.id
        res = importar_baia_completa(admin_id)
        print('IMPORT BAIA:', res)


if __name__ == '__main__':
    main()
