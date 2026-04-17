"""
tests/test_propagacao_proposta_obra.py — Task #82

Valida que ao aprovar uma proposta:
  1. Cada PropostaItem vira um ItemMedicaoComercial na obra (1:1 determinístico).
  2. O listener after_insert cria o ObraServicoCusto pareado herdando
     valor_comercial → valor_orcado e servico_id → servico_catalogo_id.
  3. Itens com nome duplicado são todos criados (não há dedupe por nome).
  4. Reexecutar a propagação não duplica (dedupe por proposta_item_id).

Roda em transação isolada (rollback no fim).
"""
import os
import sys
from datetime import date, datetime
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

from app import app, db
from models import (
    Usuario, Obra, Servico,
    Proposta, PropostaItem,
    ItemMedicaoComercial, ObraServicoCusto,
)
from handlers.propostas_handlers import _propagar_proposta_para_obra


@pytest.fixture(scope='function')
def setup_obra_proposta():
    """Cria obra + proposta + itens em transação revertida."""
    with app.app_context():
        u = Usuario.query.filter_by(tipo_usuario='ADMIN').first() or Usuario.query.first()
        if u is None:
            pytest.skip('Sem usuário admin no banco')
        aid = u.id
        try:
            obra = Obra.query.filter_by(admin_id=aid).first()
            if not obra:
                pytest.skip('Sem obra para tenant — teste pula')

            svc1 = Servico(admin_id=aid, nome='__t82_svc_a', categoria='Teste', unidade_medida='un')
            svc2 = Servico(admin_id=aid, nome='__t82_svc_b', categoria='Teste', unidade_medida='un')
            db.session.add_all([svc1, svc2])
            db.session.flush()

            proposta = Proposta(
                admin_id=aid,
                numero=f'__T82-{datetime.utcnow().strftime("%H%M%S%f")}',
                cliente_nome='Cliente Teste #82',
                obra_id=obra.id,
                valor_total=Decimal('300.00'),
                status='APROVADA',
            )
            db.session.add(proposta)
            db.session.flush()

            it1 = PropostaItem(
                admin_id=aid, proposta_id=proposta.id, item_numero=1,
                descricao='Item Alpha (com servico)', quantidade=Decimal('2'),
                unidade='un', preco_unitario=Decimal('50.00'), ordem=1,
                servico_id=svc1.id,
            )
            it2 = PropostaItem(
                admin_id=aid, proposta_id=proposta.id, item_numero=2,
                descricao='Item duplicado', quantidade=Decimal('1'),
                unidade='un', preco_unitario=Decimal('80.00'), ordem=2,
                servico_id=svc2.id,
            )
            it3 = PropostaItem(
                admin_id=aid, proposta_id=proposta.id, item_numero=3,
                descricao='Item duplicado',  # mesmo nome de propósito
                quantidade=Decimal('1'),
                unidade='un', preco_unitario=Decimal('120.00'), ordem=3,
                servico_id=None,
            )
            db.session.add_all([it1, it2, it3])
            db.session.flush()

            yield {
                'admin_id': aid,
                'obra': obra,
                'proposta': proposta,
                'svc1': svc1,
                'svc2': svc2,
                'itens': [it1, it2, it3],
            }
        finally:
            db.session.rollback()


def test_propagacao_cria_itens_e_custos(setup_obra_proposta):
    ctx = setup_obra_proposta
    aid = ctx['admin_id']
    obra = ctx['obra']
    proposta = ctx['proposta']

    criados = _propagar_proposta_para_obra(proposta.id, aid)
    assert criados == 3, f'esperava 3 ItemMedicaoComercial, criou {criados}'

    itens_med = ItemMedicaoComercial.query.filter_by(
        admin_id=aid, obra_id=obra.id
    ).filter(ItemMedicaoComercial.proposta_item_id.in_([i.id for i in ctx['itens']])).all()
    assert len(itens_med) == 3, 'todos os 3 itens (incluindo nomes duplicados) devem ser criados'

    # Cada item carrega proposta_item_id correto
    proposta_item_ids = {im.proposta_item_id for im in itens_med}
    assert proposta_item_ids == {i.id for i in ctx['itens']}

    # Item Alpha (it1): valor 100, com servico svc1
    im_alpha = next(im for im in itens_med if im.proposta_item_id == ctx['itens'][0].id)
    assert im_alpha.valor_comercial == Decimal('100.00'), f'esperava 100.00, obteve {im_alpha.valor_comercial}'
    assert im_alpha.servico_id == ctx['svc1'].id

    # Listener: ObraServicoCusto criado e pareado para itens com servico
    osc_alpha = ObraServicoCusto.query.filter_by(
        admin_id=aid, obra_id=obra.id, servico_catalogo_id=ctx['svc1'].id
    ).first()
    assert osc_alpha is not None, 'ObraServicoCusto deve ser criado pelo listener'
    assert Decimal(str(osc_alpha.valor_orcado)) == Decimal('100.00'), \
        f'valor_orcado deve herdar valor_comercial; obtido {osc_alpha.valor_orcado}'


def test_handle_proposta_aprovada_propagacao_falha_aborta_tudo(monkeypatch):
    """Garantia: se propagação falhar, handle_proposta_aprovada faz rollback
    completo (não cria ContaReceber órfã)."""
    from handlers import propostas_handlers as ph
    from models import ContaReceber

    with app.app_context():
        u = Usuario.query.filter_by(tipo_usuario='ADMIN').first() or Usuario.query.first()
        if u is None:
            pytest.skip('Sem usuário admin no banco')
        aid = u.id
        obra = Obra.query.filter_by(admin_id=aid).first()
        if not obra:
            pytest.skip('Sem obra para tenant — teste pula')

        proposta = Proposta(
            admin_id=aid,
            numero=f'__T82F-{datetime.utcnow().strftime("%H%M%S%f")}',
            cliente_nome='Cliente Falha #82',
            obra_id=obra.id,
            valor_total=Decimal('500.00'),
            status='APROVADA',
        )
        db.session.add(proposta)
        db.session.commit()
        proposta_id = proposta.id

        cr_antes = ContaReceber.query.filter_by(
            admin_id=aid, origem_tipo='PROPOSTA', origem_id=proposta_id
        ).count()

        # Força propagação a explodir
        def _boom(*a, **kw):
            raise RuntimeError('falha simulada na propagação')

        monkeypatch.setattr(ph, '_propagar_proposta_para_obra', _boom)

        try:
            with pytest.raises(RuntimeError, match='falha simulada'):
                ph.handle_proposta_aprovada(
                    {
                        'proposta_id': proposta_id,
                        'cliente_nome': 'Cliente Falha #82',
                        'cliente_cpf_cnpj': '',
                        'obra_id': obra.id,
                        'valor_total': 500.00,
                        'data_vencimento': (date.today()).isoformat(),
                        'data_aprovacao': date.today().isoformat(),
                    },
                    aid,
                )

            cr_depois = ContaReceber.query.filter_by(
                admin_id=aid, origem_tipo='PROPOSTA', origem_id=proposta_id
            ).count()
            assert cr_depois == cr_antes, (
                'ContaReceber não deve ser criada quando propagação falha (rollback completo)'
            )
        finally:
            # Cleanup — remove proposta criada
            ContaReceber.query.filter_by(
                admin_id=aid, origem_tipo='PROPOSTA', origem_id=proposta_id
            ).delete(synchronize_session=False)
            Proposta.query.filter_by(id=proposta_id).delete(synchronize_session=False)
            db.session.commit()


def test_propagacao_idempotente_por_proposta_item_id(setup_obra_proposta):
    ctx = setup_obra_proposta
    aid = ctx['admin_id']
    proposta = ctx['proposta']

    # 1ª chamada cria 3
    criados1 = _propagar_proposta_para_obra(proposta.id, aid)
    assert criados1 == 3
    # 2ª chamada não duplica
    criados2 = _propagar_proposta_para_obra(proposta.id, aid)
    assert criados2 == 0, 'reexecução não deve duplicar (dedupe por proposta_item_id)'

    total = ItemMedicaoComercial.query.filter_by(admin_id=aid, obra_id=ctx['obra'].id).filter(
        ItemMedicaoComercial.proposta_item_id.in_([i.id for i in ctx['itens']])
    ).count()
    assert total == 3, f'total deve permanecer 3, obteve {total}'
