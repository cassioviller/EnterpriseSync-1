#!/usr/bin/env python3
"""
🎯 TESTE ESPECÍFICO: Danilo - Por que 0.3h?
"""

from app import app, db
from models import RegistroPonto, Funcionario
from kpis_engine import KPIsEngine
from sqlalchemy import func, text
from datetime import date

def testar_danilo():
    """Testar especificamente o Danilo"""
    print("🎯 TESTE: Danilo José de Oliveira")
    print("=" * 50)
    
    danilo = Funcionario.query.filter(Funcionario.nome.like('%Danilo%')).first()
    
    if not danilo:
        print("❌ Danilo não encontrado")
        return
    
    print(f"👤 {danilo.nome} (ID: {danilo.id})")
    
    # Soma direta do database
    total_db = db.session.query(func.sum(RegistroPonto.horas_extras)).filter(
        RegistroPonto.funcionario_id == danilo.id,
        RegistroPonto.data >= date(2025, 7, 1),
        RegistroPonto.data <= date(2025, 7, 31),
        RegistroPonto.horas_extras.isnot(None)
    ).scalar() or 0
    
    print(f"📊 DB Total: {total_db:.1f}h")
    
    # KPI Engine
    engine = KPIsEngine()
    resultado = engine._calcular_horas_extras(
        danilo.id,
        date(2025, 7, 1),
        date(2025, 7, 31)
    )
    
    print(f"🤖 KPI Engine: {resultado:.1f}h")
    
    # KPIs completos
    kpis = engine.calcular_kpis_funcionario(
        danilo.id,
        date(2025, 7, 1),
        date(2025, 7, 31)
    )
    
    print(f"📋 KPIs horas_extras: {kpis['horas_extras']:.1f}h")
    
    # Listar registros com extras
    registros_extras = db.session.execute(text("""
        SELECT data, tipo_registro, horas_extras
        FROM registro_ponto
        WHERE funcionario_id = :func_id
            AND data >= '2025-07-01' 
            AND data <= '2025-07-31'
            AND horas_extras IS NOT NULL
            AND horas_extras > 0
        ORDER BY data
    """), {'func_id': danilo.id}).fetchall()
    
    print(f"\n📋 REGISTROS COM EXTRAS ({len(registros_extras)}):")
    for reg in registros_extras:
        print(f"   {reg.data} | {reg.tipo_registro} | {reg.horas_extras:.1f}h")
    
    return danilo, kpis

if __name__ == "__main__":
    with app.app_context():
        testar_danilo()