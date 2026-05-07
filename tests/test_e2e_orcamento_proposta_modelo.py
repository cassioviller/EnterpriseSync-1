"""E2E — Orçamento → Template → Proposta (Task #31).

Cobre o ciclo completo:
  FASE 1: Criar PropostaTemplate via POST real.
  FASE 2: Criar Orçamento com 2 itens via POST real.
  FASE 3: POST /orcamentos/<id>/gerar-proposta COM template_id.
  FASE 4: Verificar banco: orcamento_id, template_id, prazo, cláusulas, campos_pendentes.
  FASE 5: POST /orcamentos/<id>/gerar-proposta SEM template_id (caminho legado).
  FASE 6: Verificar campos_pendentes=[] e proposta_template_id=NULL no caminho sem modelo.
"""
import os
import sys
from datetime import date, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db  # noqa: E402

PASS, FAIL = [], []


def check(cond, msg):
    if cond:
        PASS.append(msg)
        print(f"  PASS {msg}")
    else:
        FAIL.append(msg)
        print(f"  FAIL {msg}")


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True


def main():
    with app.app_context():
        from models import (
            Usuario, TipoUsuario, Servico, Insumo, PrecoBaseInsumo,
            ComposicaoServico, Orcamento, OrcamentoItem, Proposta,
            PropostaItem, PropostaTemplate, PropostaTemplateClausula,
            PropostaClausula,
        )
        from services.orcamento_view_service import snapshot_from_servico

        admin = Usuario.query.filter_by(
            tipo_usuario=TipoUsuario.ADMIN
        ).first()
        if not admin:
            print("SKIP: nenhum admin encontrado")
            return

        admin_id = admin.admin_id if getattr(admin, 'admin_id', None) else admin.id
        suffix = f"E2E31-{date.today().toordinal()}-{os.getpid()}"

        # ─── Pré-requisito: insumo + serviço ───────────────────────────────
        ins = Insumo(admin_id=admin_id, nome=f'__{suffix}_mo', tipo='MAO_OBRA', unidade='h')
        db.session.add(ins); db.session.flush()
        db.session.add(PrecoBaseInsumo(
            admin_id=admin_id, insumo_id=ins.id,
            valor=Decimal('100.00'),
            vigencia_inicio=date.today() - timedelta(days=30),
        ))
        svc = Servico(
            admin_id=admin_id, nome=f'__{suffix}_svc',
            categoria='Teste E2E #31', unidade_medida='m2',
            imposto_pct=Decimal('8'), margem_lucro_pct=Decimal('12'),
            ativo=True,
        )
        db.session.add(svc); db.session.flush()
        db.session.add(ComposicaoServico(
            admin_id=admin_id, servico_id=svc.id,
            insumo_id=ins.id, coeficiente=Decimal('1.0'),
        ))
        db.session.commit()

        with app.test_client() as client:
            _login(client, admin)

            # ===== FASE 1: Criar PropostaTemplate via POST =====
            print(f"\n[FASE 1] Criar PropostaTemplate (suffix={suffix})")
            r1 = client.post('/propostas/templates/criar', data={
                'nome': f'__{suffix}_tmpl',
                'categoria': 'Teste',
                'descricao': 'Template E2E Task #31',
                'prazo_entrega_dias': '90',
                'validade_dias': '10',
                'condicoes_pagamento': '50% entrada\n50% entrega',
                'garantias': 'Garantia de 1 ano',
                'itens_inclusos': 'Limpeza final\nMaterial incluso',
                'clausula_titulo': ['Pagamento', 'Garantia'],
                'clausula_texto': [
                    'O pagamento é em 2 parcelas.',
                    'Garantia de 12 meses.',
                ],
                'clausula_ordem': ['1', '2'],
                'clausulas_payload_present': '1',
            }, follow_redirects=True)
            check(r1.status_code == 200, f"POST /propostas/templates/novo → 200 (got {r1.status_code})")

            tmpl = PropostaTemplate.query.filter_by(
                admin_id=admin_id, nome=f'__{suffix}_tmpl'
            ).first()
            check(tmpl is not None, "PropostaTemplate criado no banco")
            if tmpl:
                check(tmpl.prazo_entrega_dias == 90, f"prazo_entrega_dias=90 (got {tmpl.prazo_entrega_dias})")
                check(tmpl.validade_dias == 10, f"validade_dias=10 (got {tmpl.validade_dias})")
                n_cl = len(tmpl.clausulas)
                check(n_cl >= 2, f"≥2 cláusulas no template (got {n_cl})")

            # ===== FASE 2: Criar Orçamento via POST =====
            print(f"\n[FASE 2] Criar Orçamento e adicionar 2 itens")
            r2 = client.post('/orcamentos/novo', data={
                'titulo': f'__{suffix}_orc',
                'descricao': 'Orçamento E2E #31',
                'imposto_pct_global': '8',
                'margem_pct_global': '12',
            }, follow_redirects=False)
            check(r2.status_code in (200, 302), f"POST /orcamentos/novo → {r2.status_code}")

            orc = Orcamento.query.filter_by(
                admin_id=admin_id, titulo=f'__{suffix}_orc'
            ).first()
            check(orc is not None, "Orçamento criado no banco")

            if orc:
                snap = snapshot_from_servico(svc)
                for _ordem in (1, 2):
                    db.session.add(OrcamentoItem(
                        admin_id=admin_id, orcamento_id=orc.id, ordem=_ordem,
                        servico_id=svc.id,
                        descricao=f"Serviço E2E #{_ordem}",
                        unidade="m2", quantidade=Decimal("10"),
                        composicao_snapshot=snap,
                    ))
                db.session.commit()
                n_itens = len(orc.itens)
                check(n_itens == 2, f"Orçamento tem 2 itens (got {n_itens})")

            # ===== FASE 3: Gerar Proposta COM template =====
            print(f"\n[FASE 3] POST gerar-proposta COM template_id={tmpl.id if tmpl else '?'}")
            if orc and tmpl:
                r3 = client.post(
                    f'/orcamentos/{orc.id}/gerar-proposta',
                    data={'template_id': str(tmpl.id)},
                    follow_redirects=False,
                )
                check(r3.status_code in (302, 200), f"POST gerar-proposta (com tmpl) → {r3.status_code}")

                # ===== FASE 4: Verificar banco =====
                print(f"\n[FASE 4] Verificar proposta COM template no banco")
                prop_com = Proposta.query.filter_by(
                    orcamento_id=orc.id, proposta_template_id=tmpl.id,
                ).first()
                check(prop_com is not None, "Proposta com template_id encontrada")
                if prop_com:
                    check(prop_com.orcamento_id == orc.id,
                          f"orcamento_id={orc.id} ✓")
                    check(prop_com.proposta_template_id == tmpl.id,
                          f"proposta_template_id={tmpl.id} ✓")
                    check(prop_com.prazo_entrega_dias == 90,
                          f"prazo_entrega_dias=90 (got {prop_com.prazo_entrega_dias})")
                    check(prop_com.validade_dias == 10,
                          f"validade_dias=10 (got {prop_com.validade_dias})")
                    pendentes = prop_com.campos_pendentes_revisao or []
                    check(len(pendentes) > 0,
                          f"campos_pendentes_revisao não-vazio (got {pendentes})")
                    check('prazo_entrega_dias' in pendentes,
                          "'prazo_entrega_dias' nos pendentes")
                    n_cl_prop = PropostaClausula.query.filter_by(
                        proposta_id=prop_com.id
                    ).count()
                    check(n_cl_prop >= 2,
                          f"≥2 cláusulas copiadas do template (got {n_cl_prop})")
                    n_pi = PropostaItem.query.filter_by(proposta_id=prop_com.id).count()
                    check(n_pi == 2, f"2 PropostaItem gerados (got {n_pi})")

            # ===== FASE 5: Gerar Proposta SEM template =====
            print(f"\n[FASE 5] POST gerar-proposta SEM template_id")
            import time as _time
            _num2 = f"E2E31-{int(_time.time())}"
            orc2 = Orcamento(
                admin_id=admin_id,
                numero=_num2,
                titulo=f'__{suffix}_orc2',
                descricao='Orçamento E2E #31 sem template',
                criado_por=admin.id, status='rascunho',
            )
            db.session.add(orc2); db.session.flush()
            snap = snapshot_from_servico(svc)
            db.session.add(OrcamentoItem(
                admin_id=admin_id, orcamento_id=orc2.id, ordem=1,
                servico_id=svc.id, descricao="Serviço E2E sem tmpl",
                unidade="m2", quantidade=Decimal("5"),
                composicao_snapshot=snap,
            ))
            db.session.commit()

            r5 = client.post(
                f'/orcamentos/{orc2.id}/gerar-proposta',
                data={'template_id': ''},
                follow_redirects=False,
            )
            check(r5.status_code in (302, 200), f"POST gerar-proposta (sem tmpl) → {r5.status_code}")

            # ===== FASE 6: Verificar proposta sem template =====
            print(f"\n[FASE 6] Verificar proposta SEM template no banco")
            prop_sem = Proposta.query.filter_by(
                orcamento_id=orc2.id
            ).first()
            check(prop_sem is not None, "Proposta sem template encontrada")
            if prop_sem:
                check(prop_sem.proposta_template_id is None,
                      "proposta_template_id=NULL ✓")
                check(prop_sem.orcamento_id == orc2.id,
                      f"orcamento_id={orc2.id} ✓")
                pendentes_sem = prop_sem.campos_pendentes_revisao or []
                check(len(pendentes_sem) == 0,
                      f"campos_pendentes_revisao=[] (got {pendentes_sem})")

    print("\n" + "=" * 70)
    print(f"PASS={len(PASS)}  FAIL={len(FAIL)}")
    print("=" * 70)
    for m in PASS:
        print(f"  OK  {m}")
    for m in FAIL:
        print(f"  XX  {m}")
    if FAIL:
        sys.exit(1)


if __name__ == "__main__":
    main()
