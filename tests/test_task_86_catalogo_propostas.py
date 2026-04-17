"""Task #86 — testes de persistência de servico_id no fluxo
Catálogo → Proposta → Medição (ItemMedicaoComercial) → ObraServicoCusto.

Estes testes não usam pytest fixtures dedicados; rodam direto contra a
base de dados configurada (igual a tests/test_agrupamento_diarias_rdo.py).
Uso esperado: `python tests/test_task_86_catalogo_propostas.py` ou
`pytest tests/test_task_86_catalogo_propostas.py`.

Cobertura:
- PropostaItem aceita e persiste servico_id (apoiado por
  propostas_consolidated.py:427/467 que lê
  request.form.getlist('item_servico_id')).
- ItemMedicaoComercial aceita e persiste servico_id (apoiado por
  medicao_views.py:145-156 e 215-224).
- O listener after_insert em ItemMedicaoComercial (models.py) cria um
  ObraServicoCusto pareado herdando servico_catalogo_id, fechando o
  ciclo do catálogo.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('FLASK_ENV', 'development')

from app import app, db  # noqa: E402
from models import (  # noqa: E402
    Cliente,
    ItemMedicaoComercial,
    Obra,
    ObraServicoCusto,
    Proposta,
    PropostaItem,
    Servico,
)

ADMIN_ID = 63


def _unique_numero():
    return f"TEST-86-{int(time.time() * 1000)}"


def test_servico_id_persiste_em_proposta_item():
    with app.app_context():
        svc = Servico.query.filter_by(admin_id=ADMIN_ID, ativo=True).first()
        cli = Cliente.query.first()
        assert svc is not None, "seed: nenhum Servico ativo no admin de teste"
        assert cli is not None, "seed: nenhum Cliente"

        p = Proposta(
            admin_id=ADMIN_ID,
            cliente_id=cli.id,
            cliente_nome=cli.nome,
            numero=_unique_numero(),
            valor_total=1000.0,
            status="rascunho",
        )
        db.session.add(p)
        db.session.flush()
        pi = PropostaItem(
            admin_id=ADMIN_ID,
            proposta_id=p.id,
            item_numero=1,
            ordem=1,
            descricao="Item linkado ao catálogo",
            quantidade=1,
            unidade="un",
            preco_unitario=1000.0,
            servico_id=svc.id,
        )
        db.session.add(pi)
        db.session.commit()
        try:
            refetch = PropostaItem.query.get(pi.id)
            assert refetch.servico_id == svc.id, (
                f"servico_id não persistiu: {refetch.servico_id} != {svc.id}"
            )
        finally:
            db.session.delete(pi)
            db.session.delete(p)
            db.session.commit()


def test_servico_id_persiste_em_item_medicao_e_propaga_para_osc():
    with app.app_context():
        svc = Servico.query.filter_by(admin_id=ADMIN_ID, ativo=True).first()
        obra = Obra.query.filter_by(admin_id=ADMIN_ID).first()
        assert svc is not None, "seed: Servico ativo necessário"
        assert obra is not None, "seed: Obra necessária"

        imc = ItemMedicaoComercial(
            obra_id=obra.id,
            admin_id=ADMIN_ID,
            nome="IMC linkado ao catálogo",
            quantidade=1,
            valor_comercial=2000,
            servico_id=svc.id,
        )
        db.session.add(imc)
        db.session.commit()
        try:
            re_imc = ItemMedicaoComercial.query.get(imc.id)
            assert re_imc.servico_id == svc.id

            # Listener after_insert deve ter criado ObraServicoCusto pareado
            osc = (
                ObraServicoCusto.query.filter_by(
                    servico_catalogo_id=svc.id, obra_id=obra.id
                )
                .order_by(ObraServicoCusto.id.desc())
                .first()
            )
            assert osc is not None, "ObraServicoCusto pareado não foi criado pelo listener"
            assert osc.servico_catalogo_id == svc.id
        finally:
            # cleanup mais defensivo
            ObraServicoCusto.query.filter_by(
                servico_catalogo_id=svc.id, obra_id=obra.id
            ).delete()
            db.session.delete(re_imc)
            db.session.commit()


if __name__ == "__main__":
    test_servico_id_persiste_em_proposta_item()
    print("[ok] PropostaItem.servico_id persiste")
    test_servico_id_persiste_em_item_medicao_e_propaga_para_osc()
    print("[ok] ItemMedicaoComercial.servico_id persiste e propaga para OSC")
    print("PASS")
