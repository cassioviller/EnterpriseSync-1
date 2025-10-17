"""
Script de Diagnóstico: Custos de Veículos Zerados no Dashboard
Investigar por que VehicleExpense retorna R$ 0.00
"""

from app import app, db
from models import VehicleExpense, Usuario, Veiculo
from datetime import date
from sqlalchemy import func

def diagnosticar_custos_veiculo():
    with app.app_context():
        print("=" * 80)
        print("🔍 DIAGNÓSTICO: Custos de Veículos")
        print("=" * 80)
        
        # 1. Verificar se tabela existe
        print("\n1️⃣ Verificando se tabela 'frota_despesa' existe...")
        try:
            total_registros = db.session.query(func.count(VehicleExpense.id)).scalar()
            print(f"   ✅ Tabela existe: {total_registros} registros totais")
        except Exception as e:
            print(f"   ❌ Erro ao acessar tabela: {e}")
            return
        
        # 2. Verificar registros por admin_id
        print("\n2️⃣ Verificando registros por empresa (admin_id)...")
        registros_por_admin = db.session.query(
            VehicleExpense.admin_id,
            func.count(VehicleExpense.id).label('total'),
            func.sum(VehicleExpense.valor).label('valor_total')
        ).group_by(VehicleExpense.admin_id).all()
        
        if registros_por_admin:
            for admin_id, total, valor_total in registros_por_admin:
                admin = Usuario.query.get(admin_id)
                nome_admin = admin.username if admin else "Desconhecido"
                print(f"   Admin ID {admin_id} ({nome_admin}): {total} registros, R$ {valor_total or 0:.2f}")
        else:
            print("   ⚠️ Nenhum registro encontrado em nenhuma empresa")
        
        # 3. Verificar período dos dados
        print("\n3️⃣ Verificando período dos dados...")
        periodo = db.session.query(
            func.min(VehicleExpense.data_custo).label('data_min'),
            func.max(VehicleExpense.data_custo).label('data_max')
        ).first()
        
        if periodo.data_min and periodo.data_max:
            print(f"   📅 Período dos dados: {periodo.data_min} a {periodo.data_max}")
        else:
            print("   ⚠️ Nenhum registro com data")
        
        # 4. Verificar registros no período do dashboard
        print("\n4️⃣ Verificando registros no período do dashboard...")
        data_inicio = date(2025, 10, 1)
        data_fim = date(2025, 10, 31)
        print(f"   Período dashboard: {data_inicio} a {data_fim}")
        
        registros_periodo = VehicleExpense.query.filter(
            VehicleExpense.data_custo >= data_inicio,
            VehicleExpense.data_custo <= data_fim
        ).all()
        
        if registros_periodo:
            print(f"   ✅ {len(registros_periodo)} registros encontrados no período")
            total_valor = sum(r.valor or 0 for r in registros_periodo)
            print(f"   💰 Valor total: R$ {total_valor:.2f}")
            
            # Mostrar alguns exemplos
            print("\n   📋 Exemplos de registros:")
            for r in registros_periodo[:5]:
                print(f"      - {r.data_custo}: R$ {r.valor:.2f} ({r.tipo_custo}) - Admin ID: {r.admin_id}")
        else:
            print("   ❌ NENHUM registro encontrado no período do dashboard!")
        
        # 5. Verificar registros por admin_id E período
        print("\n5️⃣ Verificando registros por admin_id E período...")
        
        # Buscar todos os admin_ids que têm veículos
        admins_com_veiculos = db.session.query(
            VehicleExpense.admin_id.distinct()
        ).all()
        
        if admins_com_veiculos:
            for (admin_id,) in admins_com_veiculos:
                admin = Usuario.query.get(admin_id)
                nome_admin = admin.username if admin else "Desconhecido"
                
                registros_admin_periodo = VehicleExpense.query.filter(
                    VehicleExpense.admin_id == admin_id,
                    VehicleExpense.data_custo >= data_inicio,
                    VehicleExpense.data_custo <= data_fim
                ).all()
                
                total_admin = sum(r.valor or 0 for r in registros_admin_periodo)
                print(f"   Admin ID {admin_id} ({nome_admin}): {len(registros_admin_periodo)} registros, R$ {total_admin:.2f}")
        else:
            print("   ⚠️ Nenhum admin_id tem despesas de veículos")
        
        # 6. Verificar se há valores NULL ou zero
        print("\n6️⃣ Verificando valores NULL ou zero...")
        registros_null = VehicleExpense.query.filter(
            VehicleExpense.valor == None
        ).count()
        registros_zero = VehicleExpense.query.filter(
            VehicleExpense.valor == 0
        ).count()
        registros_positivos = VehicleExpense.query.filter(
            VehicleExpense.valor > 0
        ).count()
        
        print(f"   NULL: {registros_null}")
        print(f"   Zero: {registros_zero}")
        print(f"   Positivos: {registros_positivos}")
        
        # 7. Verificar tipos de custo
        print("\n7️⃣ Verificando tipos de custo...")
        tipos = db.session.query(
            VehicleExpense.tipo_custo,
            func.count(VehicleExpense.id).label('total'),
            func.sum(VehicleExpense.valor).label('valor_total')
        ).group_by(VehicleExpense.tipo_custo).all()
        
        if tipos:
            for tipo, total, valor_total in tipos:
                print(f"   {tipo}: {total} registros, R$ {valor_total or 0:.2f}")
        else:
            print("   ⚠️ Nenhum tipo de custo encontrado")
        
        print("\n" + "=" * 80)
        print("🎯 DIAGNÓSTICO CONCLUÍDO")
        print("=" * 80)
        
        # CONCLUSÃO
        print("\n📊 RESUMO:")
        if total_registros == 0:
            print("   ❌ PROBLEMA: Tabela está vazia - nenhum custo de veículo cadastrado")
            print("   💡 SOLUÇÃO: Cadastrar despesas de veículos no sistema")
        elif not registros_periodo:
            print("   ❌ PROBLEMA: Existem dados, mas não no período do dashboard")
            print(f"   💡 SOLUÇÃO: Ajustar período do dashboard ou cadastrar dados em {data_inicio} a {data_fim}")
        elif len(registros_periodo) > 0:
            total_valor = sum(r.valor or 0 for r in registros_periodo)
            if total_valor == 0:
                print("   ❌ PROBLEMA: Registros existem mas todos têm valor zero ou NULL")
                print("   💡 SOLUÇÃO: Corrigir valores dos registros no banco de dados")
            else:
                print("   ✅ Dados existem e estão corretos!")
                print("   ⚠️ Problema pode ser no código do dashboard ou filtro de admin_id")

if __name__ == '__main__':
    diagnosticar_custos_veiculo()
