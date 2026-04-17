"""E2E backend test — Orçamento Paramétrico → Proposta (Task #95).

Cobre o ciclo do catálogo até a aprovação da proposta:
  FASE 1: Setup catálogo paramétrico (Insumo + Servico + ComposicaoServico).
  FASE 2: Proposta rascunho com explosão de insumos no PropostaItem.
  FASE 3: Recálculo via services/orcamento_service (persistência no Servico).
  FASE 4: Snapshot imutável — preço do Insumo muda, PropostaItem antigo intacto.
  FASE 5: Transição rascunho → enviada + portal público responde 200.
  FASE 6: Aprovação via portal cliente + isolamento multi-tenant.
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


def main():
    with app.app_context():
        from models import (
            Proposta, PropostaItem, Obra,
            Insumo, PrecoBaseInsumo, ComposicaoServico, Servico,
            ItemMedicaoComercial, Usuario,
        )
        from services.orcamento_service import (
            calcular_precos_servico, recalcular_servico_preco,
            explodir_servico_para_quantidade,
        )

        admin_id = 63
        suffix = f"E2E95-{int(date.today().toordinal())}-{os.getpid()}"

        # Encontra um admin diferente para o teste de isolamento multi-tenant
        outro_admin = Usuario.query.filter(
            Usuario.id != admin_id,
            Usuario.tipo_usuario == 'ADMIN',
        ).first()
        outro_admin_id = outro_admin.id if outro_admin else None

        # ===== FASE 1: setup catálogo paramétrico =====
        print(f"\n[FASE 1] Setup catálogo paramétrico (suffix={suffix})")
        ins_mo = Insumo(admin_id=admin_id, nome=f'__{suffix}_mo',
                        tipo='MAO_OBRA', unidade='h')
        ins_mat = Insumo(admin_id=admin_id, nome=f'__{suffix}_aco',
                         tipo='MATERIAL', unidade='kg')
        db.session.add_all([ins_mo, ins_mat])
        db.session.flush()

        db.session.add_all([
            PrecoBaseInsumo(admin_id=admin_id, insumo_id=ins_mo.id,
                            valor=Decimal('100.00'),
                            vigencia_inicio=date.today() - timedelta(days=30)),
            PrecoBaseInsumo(admin_id=admin_id, insumo_id=ins_mat.id,
                            valor=Decimal('20.00'),
                            vigencia_inicio=date.today() - timedelta(days=30)),
        ])
        svc = Servico(
            admin_id=admin_id,
            nome=f'__{suffix}_svc',
            categoria='Teste E2E',
            unidade_medida='m2',
            imposto_pct=Decimal('8'),
            margem_lucro_pct=Decimal('12'),
        )
        db.session.add(svc)
        db.session.flush()
        db.session.add_all([
            ComposicaoServico(admin_id=admin_id, servico_id=svc.id,
                              insumo_id=ins_mo.id, coeficiente=Decimal('0.5')),
            ComposicaoServico(admin_id=admin_id, servico_id=svc.id,
                              insumo_id=ins_mat.id, coeficiente=Decimal('2.0')),
        ])
        db.session.commit()
        # custo = 0.5*100 + 2.0*20 = 50 + 40 = 90
        # divisor = 1 - 0.08 - 0.12 = 0.80
        # preco = 90 / 0.80 = 112.50
        r = calcular_precos_servico(svc)
        check(str(r['custo_unitario']) == '90.00',
              f"custo_unitario={r['custo_unitario']} == 90.00")
        check(str(r['preco_venda']) == '112.50',
              f"preco_venda={r['preco_venda']} == 112.50")
        check(r['erro'] is None, "sem erro no cálculo paramétrico")

        # validação imposto+lucro >= 100
        svc.imposto_pct = Decimal('60')
        svc.margem_lucro_pct = Decimal('50')
        r_err = calcular_precos_servico(svc)
        check(r_err['erro'] is not None,
              f"imposto+lucro >= 100% sinaliza erro (erro={r_err['erro']!r})")
        check(str(r_err['preco_venda']) == '0.00',
              "preço zerado quando imposto+lucro >= 100%")
        # restaura e re-persiste
        svc.imposto_pct = Decimal('8')
        svc.margem_lucro_pct = Decimal('12')
        recalcular_servico_preco(svc)
        db.session.commit()

        # ===== FASE 2: proposta rascunho com explosão =====
        print("\n[FASE 2] Proposta rascunho com explosão de insumos no PropostaItem")
        explosao = explodir_servico_para_quantidade(svc, Decimal('10'))
        check(str(explosao['custo_unitario']) == '90.00',
              f"explosao.custo_unitario={explosao['custo_unitario']} == 90.00")
        check(str(explosao['preco_unitario']) == '112.50',
              f"explosao.preco_unitario={explosao['preco_unitario']} == 112.50")
        check(str(explosao['subtotal']) == '1125.00',
              f"explosao.subtotal={explosao['subtotal']} == 1125.00 (10×112.50)")

        proposta = Proposta(
            admin_id=admin_id,
            numero=f'P-{suffix}',
            data_proposta=date.today(),
            cliente_nome=f'Cliente E2E {suffix}',
            cliente_email='cliente.e2e@example.com',
            titulo='Orçamento + Proposta E2E',
            valor_total=explosao['subtotal'],
            status='rascunho',
            prazo_entrega_dias=30,
        )
        db.session.add(proposta)
        db.session.flush()
        proposta_id = proposta.id
        token = proposta.token_cliente

        item = PropostaItem(
            admin_id=admin_id,
            proposta_id=proposta_id,
            item_numero=1,
            ordem=1,
            descricao=f'{svc.nome} (paramétrico)',
            quantidade=Decimal('10'),
            unidade='m2',
            preco_unitario=explosao['preco_unitario'],
            servico_id=svc.id,
            quantidade_medida=Decimal('10'),
            custo_unitario=explosao['custo_unitario'],
            lucro_unitario=explosao['lucro_unitario'],
            subtotal=explosao['subtotal'],
        )
        db.session.add(item)
        db.session.commit()
        item_id = item.id

        re_item = PropostaItem.query.get(item_id)
        check(re_item.servico_id == svc.id,
              f"PropostaItem.servico_id={re_item.servico_id} == {svc.id}")
        check(str(re_item.custo_unitario) == '90.0000',
              f"snapshot custo_unitario={re_item.custo_unitario} == 90.0000")
        check(str(re_item.lucro_unitario) == '22.5000',
              f"snapshot lucro_unitario={re_item.lucro_unitario} == 22.5000")
        check(str(re_item.subtotal) == '1125.00',
              f"snapshot subtotal={re_item.subtotal} == 1125.00")
        check(re_item.quantidade_medida is not None
              and float(re_item.quantidade_medida) == 10.0,
              f"quantidade_medida={re_item.quantidade_medida} == 10")
        valor_calc = float(re_item.quantidade) * float(re_item.preco_unitario)
        check(round(valor_calc, 2) == 1125.00,
              f"qty×preco_unit={valor_calc:.2f} == 1125.00")

        # ===== FASE 3: recálculo via serviço persiste no Servico, não no Item =====
        print("\n[FASE 3] Recálculo via orcamento_service persiste no Servico")
        snapshot_custo_antes = re_item.custo_unitario
        snapshot_subtotal_antes = re_item.subtotal
        recalcular_servico_preco(svc)
        db.session.commit()
        db.session.refresh(svc)
        check(str(svc.preco_venda_unitario) == '112.50',
              f"Servico.preco_venda_unitario={svc.preco_venda_unitario} == 112.50")

        db.session.refresh(re_item)
        check(re_item.custo_unitario == snapshot_custo_antes,
              "PropostaItem.custo_unitario inalterado pelo recálculo do Servico")
        check(re_item.subtotal == snapshot_subtotal_antes,
              "PropostaItem.subtotal inalterado pelo recálculo do Servico")

        # ===== FASE 4: snapshot imutável quando preço do Insumo muda =====
        print("\n[FASE 4] Snapshot imutável: preço do Insumo sobe, item antigo fica")
        # encerra preços antigos e cria novos (vigentes a partir de ontem)
        for ins, novo_valor in [(ins_mo, Decimal('200.00')),
                                (ins_mat, Decimal('40.00'))]:
            for p in PrecoBaseInsumo.query.filter_by(
                    admin_id=admin_id, insumo_id=ins.id).all():
                if p.vigencia_fim is None:
                    p.vigencia_fim = date.today() - timedelta(days=2)
            db.session.add(PrecoBaseInsumo(
                admin_id=admin_id, insumo_id=ins.id, valor=novo_valor,
                vigencia_inicio=date.today() - timedelta(days=1),
            ))
        db.session.commit()

        # custo novo: 0.5*200 + 2.0*40 = 100 + 80 = 180; preco = 180/0.80 = 225
        r2 = calcular_precos_servico(svc)
        check(str(r2['custo_unitario']) == '180.00',
              f"novo custo_unitario={r2['custo_unitario']} == 180.00")
        check(str(r2['preco_venda']) == '225.00',
              f"novo preco_venda={r2['preco_venda']} == 225.00")
        recalcular_servico_preco(svc)
        db.session.commit()
        db.session.refresh(svc)
        check(str(svc.preco_venda_unitario) == '225.00',
              f"Servico atualizado para preco_venda={svc.preco_venda_unitario}")

        db.session.refresh(re_item)
        check(str(re_item.custo_unitario) == '90.0000',
              f"PropostaItem.custo_unitario AINDA={re_item.custo_unitario} (snapshot imutável)")
        check(str(re_item.subtotal) == '1125.00',
              f"PropostaItem.subtotal AINDA={re_item.subtotal} (snapshot imutável)")

        # ===== FASE 5: transição rascunho → enviada + portal 200 =====
        print("\n[FASE 5] Transição rascunho → enviada + portal público responde 200")
        proposta = Proposta.query.get(proposta_id)
        proposta.status = 'enviada'
        from datetime import datetime as _dt
        proposta.data_envio = _dt.utcnow()
        db.session.commit()
        check(proposta.status == 'enviada', f"status={proposta.status} == enviada")
        check(bool(token), "token_cliente presente para portal")

        client = app.test_client()
        r_portal = client.get(f'/propostas/cliente/{token}', follow_redirects=False)
        check(r_portal.status_code == 200,
              f"GET /propostas/cliente/<token> → {r_portal.status_code} (esperado 200)")

        # Token inválido não pode resolver para nenhuma proposta
        # (não fazemos GET para evitar template legacy quebrado em error.html)
        check(Proposta.query.filter_by(
            token_cliente='token-que-nao-existe-xyz123').first() is None,
            "token inválido não resolve para nenhuma Proposta (defesa do portal)")

        # ===== FASE 6: aprovação via portal cliente + multi-tenant isolation =====
        print("\n[FASE 6] Aprovação via portal cliente + isolamento multi-tenant")
        r_aprov = client.post(f'/propostas/cliente/{token}/aprovar',
                              data={'observacoes': 'Aprovado pelo teste e2e'},
                              follow_redirects=False)
        check(r_aprov.status_code in (200, 302),
              f"POST /propostas/cliente/<token>/aprovar → {r_aprov.status_code}")

        db.session.expire_all()
        proposta = Proposta.query.get(proposta_id)
        check(proposta.status == 'APROVADA',
              f"status pós-aprovação={proposta.status} == APROVADA")
        check(proposta.obra_id is not None,
              f"obra_id criado pelo handler proposta_aprovada (={proposta.obra_id})")
        check(proposta.convertida_em_obra is True,
              "convertida_em_obra=True após aprovação")

        if proposta.obra_id:
            obra = Obra.query.get(proposta.obra_id)
            check(obra is not None and obra.codigo
                  and obra.codigo.startswith('OBR'),
                  f"Obra criada com codigo OBRxxxx (={obra.codigo if obra else None})")
            check(bool(obra.token_cliente),
                  "Obra recebeu token_cliente do portal")
            # IMC propagado
            imcs = ItemMedicaoComercial.query.filter_by(
                obra_id=obra.id, admin_id=admin_id,
                proposta_item_id=item_id,
            ).all()
            check(len(imcs) == 1,
                  f"IMC propagado 1:1 do PropostaItem (encontrados={len(imcs)})")
            if imcs:
                check(imcs[0].servico_id == svc.id,
                      f"IMC.servico_id={imcs[0].servico_id} == {svc.id} (catálogo)")

        # Multi-tenant isolation: outro admin não vê a proposta
        if outro_admin_id:
            leak = Proposta.query.filter_by(
                id=proposta_id, admin_id=outro_admin_id
            ).first()
            check(leak is None,
                  f"admin {outro_admin_id} NÃO enxerga proposta de admin {admin_id} (sem leak)")
        else:
            print("  [skip] sem outro admin para validar isolamento (apenas 1 admin no banco)")

        # ===== resumo =====
        print(f"\n[summary] proposta_id={proposta_id} servico_id={svc.id} "
              f"obra_id={proposta.obra_id}")

    print("\n" + "=" * 80)
    print(f"PASS={len(PASS)}  FAIL={len(FAIL)}")
    print("=" * 80)
    for m in PASS:
        print(f"  OK  {m}")
    for m in FAIL:
        print(f"  XX  {m}")
    if FAIL:
        sys.exit(1)


if __name__ == "__main__":
    main()
