"""Importa o catálogo da obra Baia REV10 e monta o Orçamento no sistema.

Idempotente: se o orçamento/numero já existir, recria. Mantém os dados no
tenant (catálogo + orçamento). Imprime totais e R$/m².
"""
from decimal import Decimal
from app import app, db
from models import (Usuario, Servico, Orcamento,
                    OrcamentoItem)
from services.catalogo_excel import importar_insumos_xlsx, importar_composicoes_xlsx
from services.orcamento_view_service import (snapshot_from_servico, recalcular_item,
                                             recalcular_orcamento)
from scripts.gerar_importacao_baia_rev10 import SERVICOS, calc

PATH = 'obra_kabod/IMPORTACAO_Baia_REV10_completa.xlsx'
NUMERO = 'ORC-BAIA-REV10'
AREA_COBERTA = Decimal('1173')   # m² (telha shingle, item 1.13/1.2)


def main():
    pyrows = {r[0]: r for r in calc()[0]}  # cod -> (cod,nome,un,qty,cu,custo,venda)
    with app.app_context():
        u = Usuario.query.filter_by(tipo_usuario='ADMIN').first() or Usuario.query.first()
        aid = u.id

        # 1) catálogo (idempotente via upsert dos importadores)
        r1 = importar_insumos_xlsx(open(PATH, 'rb'), aid)
        r2 = importar_composicoes_xlsx(open(PATH, 'rb'), aid)
        print(f'Catálogo: {r1["created"]} insumos, {r2["servicos_created"]} serviços, '
              f'{r2["composicoes_created"]} composições | rejeições: '
              f'{len(r1["rejected"])}/{len(r2["rejected"])}')

        # 2) orçamento — recria se já existe
        old = Orcamento.query.filter_by(admin_id=aid, numero=NUMERO).first()
        if old:
            OrcamentoItem.query.filter_by(orcamento_id=old.id).delete(synchronize_session=False)
            db.session.delete(old)
            db.session.commit()
        orc = Orcamento(admin_id=aid, numero=NUMERO, titulo='Obra Baia REV10 — 24 baias',
                        cliente_nome='Grupo Mônica', status='rascunho', criado_por=aid)
        db.session.add(orc)
        db.session.flush()

        svc_by_nome = {s.nome: s for s in Servico.query.filter_by(admin_id=aid).all()}
        for i, sdef in enumerate(SERVICOS, 1):
            cod, nome, un, qty_s = sdef[0], sdef[1], sdef[2], sdef[3]
            svc = svc_by_nome[nome]
            row = pyrows[cod]
            custo, venda = row[5], row[6]
            margem = (Decimal('1') - custo / venda) * 100 if venda > 0 else Decimal('0')
            item = OrcamentoItem(
                admin_id=aid, orcamento_id=orc.id, ordem=i, servico_id=svc.id,
                descricao=f'{cod} {nome}', unidade=un,
                quantidade=Decimal(qty_s.replace(',', '.')),
                composicao_snapshot=snapshot_from_servico(svc),
                imposto_pct=Decimal('0'),
                margem_pct=margem.quantize(Decimal('0.01')),
            )
            db.session.add(item)
            db.session.flush()
            recalcular_item(item, orc)
        recalcular_orcamento(orc)
        db.session.commit()

        # 3) leitura + R$/m²
        orc = Orcamento.query.get(orc.id)
        ct, vt = Decimal(str(orc.custo_total)), Decimal(str(orc.venda_total))
        print(f'\nOrçamento {orc.numero} (id {orc.id}) — {len(orc.itens)} itens')
        print(f'  Custo total:  R$ {ct:,.2f}')
        print(f'  Venda total:  R$ {vt:,.2f}')
        print(f'  Lucro total:  R$ {vt-ct:,.2f}  ({(vt-ct)/vt*100:.1f}% da venda)')
        print(f'\nÁrea coberta (telha shingle): {AREA_COBERTA} m²  ·  {AREA_COBERTA/24:.1f} m²/baia')
        print(f'  Custo / m²:  R$ {ct/AREA_COBERTA:,.2f}')
        print(f'  Venda / m²:  R$ {vt/AREA_COBERTA:,.2f}')
        print(f'  Benchmark construção: R$ 2.500,00/m²')
        print(f'  Venda/m² ÷ benchmark: {vt/AREA_COBERTA/2500*100:.0f}%')


if __name__ == '__main__':
    main()
