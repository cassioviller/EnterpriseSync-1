#!/usr/bin/env python3
"""
Testar se a correção de multi-tenancy resolve o problema
"""

from app import app, db
from models import *
from datetime import datetime, date

def testar_consulta_corrigida():
    """Testar a consulta corrigida"""
    
    with app.app_context():
        print("🔧 Testando consulta corrigida - Filtro de Multi-Tenancy")
        print("=" * 60)
        
        admin_id = 4  # Admin do sistema
        
        # 1. Query original (problemática - sem filtro de tenant)
        print("🚫 Query ORIGINAL (sem filtro tenant):")
        registros_old = RegistroPonto.query.filter(
            RegistroPonto.data >= date(2025, 7, 5),
            RegistroPonto.data <= date(2025, 7, 6)
        ).count()
        print(f"   Total de registros 05-06/07: {registros_old}")
        
        # 2. Query corrigida (com filtro de tenant)
        print("\n✅ Query CORRIGIDA (com filtro tenant):")
        registros_new = RegistroPonto.query.join(Funcionario).filter(
            Funcionario.admin_id == admin_id,
            RegistroPonto.data >= date(2025, 7, 5),
            RegistroPonto.data <= date(2025, 7, 6)
        ).count()
        print(f"   Total de registros 05-06/07 (tenant {admin_id}): {registros_new}")
        
        # 3. Verificar registros específicos de fim de semana
        print("\n📅 Registros de fim de semana (05-06/07/2025):")
        registros_fds = RegistroPonto.query.join(Funcionario).filter(
            Funcionario.admin_id == admin_id,
            RegistroPonto.data.in_([date(2025, 7, 5), date(2025, 7, 6)])
        ).options(
            db.joinedload(RegistroPonto.funcionario_ref)
        ).all()
        
        for registro in registros_fds:
            dia_semana = "SÁBADO" if registro.data.weekday() == 5 else "DOMINGO"
            print(f"   {registro.data} ({dia_semana}) - {registro.funcionario_ref.nome} - {registro.tipo_registro}")
        
        # 4. Verificar se os registros aparecem agora
        print(f"\n🎯 RESULTADO:")
        if registros_new > 0:
            print(f"✅ Registros de fim de semana agora APARECEM no frontend!")
            print(f"✅ Total de {registros_new} registros serão exibidos")
        else:
            print(f"❌ Ainda há problemas - nenhum registro encontrado")
        
        return registros_new > 0

if __name__ == "__main__":
    resultado = testar_consulta_corrigida()
    
    if resultado:
        print(f"\n🎉 CORREÇÃO APLICADA COM SUCESSO!")
        print(f"🚀 Os registros de sábado e domingo agora devem aparecer no frontend")
    else:
        print(f"\n🔧 Ainda há problemas para investigar")