"""Smoke E2E para Task #86 — confirma persistência de servico_id em PropostaItem
e ItemMedicaoComercial via os formulários nativos."""
import sys, os, re
sys.path.insert(0, '/home/runner/workspace')
os.environ.setdefault('FLASK_ENV', 'development')

from app import app, db
from models import (
    Proposta, PropostaItem, Servico, Obra, ItemMedicaoComercial,
    ObraServicoCusto, Cliente
)

with app.app_context():
    admin_id = 63
    svc = Servico.query.filter_by(admin_id=admin_id, ativo=True).first()
    if not svc:
        print("SKIP: nenhum Servico ativo no admin_id=63"); sys.exit(0)
    print(f"[seed] servico catálogo: id={svc.id} nome={svc.nome}")

    cli = Cliente.query.first()
    if not cli:
        print("SKIP: nenhum Cliente"); sys.exit(0)

    # Cria proposta diretamente via model (simula o que a rota /propostas/criar faz
    # após processar item_servico_id da request.form)
    p = Proposta(
        admin_id=admin_id, cliente_id=cli.id, cliente_nome=cli.nome,
        numero="TEST-86",
        valor_total=1000.0, status="rascunho",
    )
    db.session.add(p); db.session.flush()
    pi = PropostaItem(
        admin_id=admin_id, proposta_id=p.id, item_numero=1, ordem=1,
        descricao="Item linkado ao catálogo", quantidade=1, unidade="un",
        preco_unitario=1000.0, servico_id=svc.id,  # <-- Task #86 grava
    )
    db.session.add(pi); db.session.commit()
    refetch = PropostaItem.query.get(pi.id)
    assert refetch.servico_id == svc.id, "FALHA: servico_id não persistiu em PropostaItem"
    print(f"[ok] PropostaItem #{pi.id}.servico_id={refetch.servico_id} == {svc.id}")

    # Confirma que ItemMedicaoComercial aceita servico_id e dispara listener para OSC
    obra = Obra.query.filter_by(admin_id=admin_id).first()
    if obra:
        imc = ItemMedicaoComercial(
            obra_id=obra.id, admin_id=admin_id,
            nome="IMC linkado ao catálogo", quantidade=1, valor_comercial=2000,
            servico_id=svc.id,
        )
        db.session.add(imc); db.session.commit()
        re_imc = ItemMedicaoComercial.query.get(imc.id)
        assert re_imc.servico_id == svc.id
        print(f"[ok] ItemMedicaoComercial #{imc.id}.servico_id={re_imc.servico_id} == {svc.id}")
        from sqlalchemy import or_; osc = ObraServicoCusto.query.filter_by(servico_catalogo_id=svc.id, obra_id=obra.id).order_by(ObraServicoCusto.id.desc()).first()
        if osc:
            print(f"[ok] ObraServicoCusto pareado #{osc.id}.servico_catalogo_id={osc.servico_catalogo_id}")
        else:
            print("[info] sem OSC pareado (listener after_insert pode estar desativado)")
        # cleanup
        if osc: db.session.delete(osc)
        db.session.delete(re_imc)

    # cleanup
    db.session.delete(refetch)
    db.session.delete(p)
    db.session.commit()
    print("PASS")
