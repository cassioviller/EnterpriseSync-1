"""E2E backend test — Ciclo Proposta → Obra → Medido → ContaReceber (Task #94).

Cobre o contrato real do refator:
- Aprovação de proposta cria Obra + token + IMC, SEM ContaReceber.
- Avanço do medido (IMC) → UPSERT da CR única OBR-MED-#####.
- Segundo avanço → MESMA CR (UPSERT, não duplica).
- Recebimento parcial → status PARCIAL e saldo reduzido.
- Recebimento total → status QUITADA, saldo zero.
"""
import os
import sys
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app  # noqa: E402

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
            db, Proposta, PropostaItem, Obra, ItemMedicaoComercial,
            ContaReceber, TarefaCronograma, ItemMedicaoCronogramaTarefa,
        )
        from event_manager import EventManager
        from services.medicao_service import recalcular_medicao_obra

        admin_id = 63
        numero = f"E2E-CICLO-{int(date.today().toordinal())}-{os.getpid()}"
        print(f"\n[setup] criando proposta {numero} (admin {admin_id})")

        p = Proposta(
            numero=numero,
            data_proposta=date.today(),
            cliente_nome=f"Cliente Ciclo {os.getpid()}",
            titulo="Ciclo Backend Task94",
            prazo_entrega_dias=30,
            valor_total=Decimal("1000.00"),
            status='rascunho',
            admin_id=admin_id,
        )
        db.session.add(p)
        db.session.flush()

        item = PropostaItem(
            proposta_id=p.id,
            item_numero=1,
            descricao="Serviço E2E Backend",
            quantidade=Decimal("10"),
            unidade="un",
            preco_unitario=Decimal("100.00"),
            ordem=1,
            subtotal=Decimal("1000.00"),
            admin_id=admin_id,
        )
        db.session.add(item)
        db.session.commit()
        proposta_id = p.id
        print(f"[setup] proposta_id={proposta_id}")

        # ===== FASE 1: aprovação cria estrutura SEM CR =====
        print("\n[FASE 1] Aprovação dispara propagar_proposta_para_obra")
        EventManager.emit('proposta_aprovada', {
            'proposta_id': proposta_id,
            'cliente_nome': p.cliente_nome,
            'cliente_cpf_cnpj': None,
            'valor_total': float(p.valor_total),
            'data_aprovacao': date.today().isoformat(),
        }, admin_id)
        db.session.refresh(p)

        check(p.obra_id is not None, "Proposta.obra_id setado pós-aprovação")
        check(p.convertida_em_obra is True, "Proposta.convertida_em_obra=True")
        check(p.status == 'APROVADA', "Status proposta = APROVADA")

        obra = Obra.query.get(p.obra_id)
        check(obra is not None, "Obra criada")
        check(obra.codigo and obra.codigo.startswith("OBR"),
              f"Codigo obra OBRxxxx (={obra.codigo})")
        check(bool(obra.token_cliente), "token_cliente gerado para portal")
        check(obra.portal_ativo is True, "portal_ativo=True")
        check(float(obra.valor_contrato or 0) == 1000.0,
              f"valor_contrato={float(obra.valor_contrato or 0)} == 1000")

        cr_post_aprov = ContaReceber.query.filter_by(
            origem_tipo='OBRA_MEDICAO', origem_id=obra.id, admin_id=admin_id,
        ).first()
        check(cr_post_aprov is None,
              "Nenhuma ContaReceber OBRA_MEDICAO criada na aprovação")

        imcs = ItemMedicaoComercial.query.filter_by(
            obra_id=obra.id, admin_id=admin_id
        ).all()
        check(len(imcs) >= 1, f"IMC propagado da proposta (encontrados={len(imcs)})")
        if imcs:
            check(float(imcs[0].valor_comercial or 0) == 1000.0,
                  f"IMC.valor_comercial={float(imcs[0].valor_comercial or 0)} == 1000")

        # ===== FASE 2: avanço 50% via cronograma + UPSERT =====
        print("\n[FASE 2] Avanço 50% via cronograma → recalcular_medicao_obra cria CR")
        # Criar TarefaCronograma + ItemMedicaoCronogramaTarefa para que
        # _recalcular_imc_avanco encontre vínculos reais.
        tarefa = TarefaCronograma(
            obra_id=obra.id,
            ordem=1,
            nome_tarefa="Tarefa E2E Backend",
            duracao_dias=30,
            percentual_concluido=50.0,
            admin_id=admin_id,
        )
        db.session.add(tarefa)
        db.session.flush()
        for imc in imcs:
            db.session.add(ItemMedicaoCronogramaTarefa(
                item_medicao_id=imc.id,
                cronograma_tarefa_id=tarefa.id,
                peso=Decimal("100"),
                admin_id=admin_id,
            ))
        db.session.commit()

        res = recalcular_medicao_obra(obra.id, admin_id)
        check(res is not None, "recalcular_medicao_obra retornou payload")
        if res:
            check(round(float(res['valor_medido']), 2) == 500.00,
                  f"payload.valor_medido={float(res['valor_medido']):.2f} == 500.00")
            check(round(float(res['valor_a_receber']), 2) == 500.00,
                  f"payload.valor_a_receber={float(res['valor_a_receber']):.2f} == 500.00")

        cr1 = ContaReceber.query.filter_by(
            origem_tipo='OBRA_MEDICAO', origem_id=obra.id, admin_id=admin_id,
        ).first()
        check(cr1 is not None, "CR OBR-MED criada após avanço")
        if cr1:
            esperado_doc = f"OBR-MED-{obra.id:05d}"
            check(cr1.numero_documento == esperado_doc,
                  f"numero_documento={cr1.numero_documento} == {esperado_doc}")
            check(round(float(cr1.valor_original), 2) == 500.00,
                  f"valor_original={float(cr1.valor_original):.2f} == 500.00")
            check(round(float(cr1.saldo or 0), 2) == 500.00,
                  f"saldo={float(cr1.saldo or 0):.2f} == 500.00")
            check(cr1.status == 'PENDENTE',
                  f"status={cr1.status} == PENDENTE")
            cr1_id = cr1.id

        # ===== FASE 3: avanço 100% — UPSERT (mesma CR) =====
        print("\n[FASE 3] Avanço 100% via cronograma — deve atualizar a MESMA CR")
        tarefa.percentual_concluido = 100.0
        db.session.commit()

        res = recalcular_medicao_obra(obra.id, admin_id)
        check(res is not None, "recalcular_medicao_obra (100%) retornou payload")

        crs = ContaReceber.query.filter_by(
            origem_tipo='OBRA_MEDICAO', origem_id=obra.id, admin_id=admin_id,
        ).all()
        check(len(crs) == 1,
              f"EXATAMENTE 1 CR OBR-MED para a obra (encontradas={len(crs)})")
        if crs:
            cr2 = crs[0]
            check(cr2.id == cr1_id, "CR é a mesma (UPSERT, não duplicou)")
            check(round(float(cr2.valor_original), 2) == 1000.00,
                  f"valor_original={float(cr2.valor_original):.2f} == 1000.00")
            check(round(float(cr2.saldo or 0), 2) == 1000.00,
                  f"saldo={float(cr2.saldo or 0):.2f} == 1000.00")
            check(cr2.status == 'PENDENTE',
                  f"status={cr2.status} == PENDENTE (sem recebimento)")

        # ===== FASE 4: recebimento parcial → PARCIAL =====
        print("\n[FASE 4] Recebimento parcial R$ 300 → status PARCIAL")
        cr2 = crs[0]
        cr2.valor_recebido = Decimal("300.00")
        db.session.commit()

        res = recalcular_medicao_obra(obra.id, admin_id)
        db.session.refresh(cr2)
        check(round(float(cr2.saldo or 0), 2) == 700.00,
              f"saldo após R$300 recebidos={float(cr2.saldo or 0):.2f} == 700.00")
        check(cr2.status == 'PARCIAL',
              f"status={cr2.status} == PARCIAL")

        # ===== FASE 5: recebimento total → QUITADA =====
        print("\n[FASE 5] Recebimento total R$ 1000 → status QUITADA")
        cr2.valor_recebido = Decimal("1000.00")
        db.session.commit()

        res = recalcular_medicao_obra(obra.id, admin_id)
        db.session.refresh(cr2)
        check(round(float(cr2.saldo or 0), 2) == 0.00,
              f"saldo após total recebido={float(cr2.saldo or 0):.2f} == 0.00")
        check(cr2.status == 'QUITADA',
              f"status={cr2.status} == QUITADA")

        crs_final = ContaReceber.query.filter_by(
            origem_tipo='OBRA_MEDICAO', origem_id=obra.id, admin_id=admin_id,
        ).all()
        check(len(crs_final) == 1,
              f"AINDA exatamente 1 CR OBR-MED (final={len(crs_final)})")

        # cleanup é opcional — deixamos os registros para inspeção manual
        print(f"\n[summary] obra_id={obra.id} cr_id={cr2.id}")

    print("\n" + "=" * 80)
    print(f"PASS={len(PASS)}  FAIL={len(FAIL)}")
    print("=" * 80)
    for m in PASS:
        print(f"  ✔ {m}")
    for m in FAIL:
        print(f"  ✘ {m}")
    if FAIL:
        sys.exit(1)


if __name__ == "__main__":
    main()
