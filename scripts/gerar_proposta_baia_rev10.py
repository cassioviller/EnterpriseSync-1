"""Gera a Proposta cliente-facing a partir do Orçamento ORC-BAIA-REV10,
replicando o fluxo de views/orcamentos_views.gerar_proposta (sem template).
Idempotente: remove a proposta anterior deste orçamento antes de recriar.
"""
from datetime import datetime
from app import app, db
from models import (Usuario, Orcamento, Proposta, PropostaItem, PropostaHistorico)
from services.orcamento_view_service import recalcular_orcamento

NUMERO_ORC = 'ORC-BAIA-REV10'


def main():
    with app.app_context():
        u = Usuario.query.filter_by(tipo_usuario='ADMIN').first() or Usuario.query.first()
        aid = u.id
        orc = Orcamento.query.filter_by(admin_id=aid, numero=NUMERO_ORC).first()
        if not orc:
            raise SystemExit(f'Orçamento {NUMERO_ORC} não encontrado.')

        # idempotência: apaga proposta anterior gerada deste orçamento
        for p in Proposta.query.filter_by(admin_id=aid, orcamento_id=orc.id).all():
            PropostaItem.query.filter_by(proposta_id=p.id).delete(synchronize_session=False)
            PropostaHistorico.query.filter_by(proposta_id=p.id).delete(synchronize_session=False)
            db.session.delete(p)
        db.session.commit()

        recalcular_orcamento(orc)

        ano = datetime.now().year
        n = Proposta.query.filter_by(admin_id=aid).count() + 1
        numero = f'PROP-{ano}-{n:04d}'
        while Proposta.query.filter_by(admin_id=aid, numero=numero).first():
            n += 1
            numero = f'PROP-{ano}-{n:04d}'

        p = Proposta()
        p.admin_id = aid
        p.numero = numero
        p.titulo = orc.titulo
        p.descricao = orc.descricao
        p.cliente_id = orc.cliente_id
        p.cliente_nome = orc.cliente_nome or 'Cliente'
        p.criado_por = aid
        p.status = 'rascunho'
        p.valor_total = orc.venda_total or 0
        p.orcamento_id = orc.id
        p.versao = 1
        db.session.add(p)
        db.session.flush()

        for idx, it in enumerate(orc.itens, start=1):
            db.session.add(PropostaItem(
                admin_id=aid, proposta_id=p.id, item_numero=idx, ordem=idx,
                descricao=it.descricao, quantidade=it.quantidade, unidade=it.unidade,
                preco_unitario=it.preco_venda_unitario or 0, subtotal=it.venda_total or 0,
                servico_id=it.servico_id, quantidade_medida=it.quantidade,
                composicao_snapshot=it.composicao_snapshot or [],
            ))
        db.session.add(PropostaHistorico(
            proposta_id=p.id, usuario_id=aid, acao='criada',
            observacao=f'Proposta gerada do Orçamento {orc.numero}', admin_id=aid,
        ))
        orc.ultima_proposta_id = p.id
        if orc.status == 'rascunho':
            orc.status = 'fechado'
        db.session.commit()

        p = Proposta.query.get(p.id)
        print(f'Proposta {p.numero} (id {p.id}) gerada do orçamento {orc.numero}')
        print(f'  Cliente: {p.cliente_nome} | status: {p.status} | itens: {len(p.itens)}')
        print(f'  Valor total: R$ {float(p.valor_total):,.2f}')
        print(f'  Orçamento {orc.numero} -> status: {orc.status}')


if __name__ == '__main__':
    main()
