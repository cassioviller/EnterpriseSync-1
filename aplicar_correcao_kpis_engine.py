#!/usr/bin/env python3
"""
CORREÇÃO FINAL: KPI Engine - Lógica de Horas Extras Corrigida
Aplicar correção definitiva na função calcular_e_atualizar_ponto
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import date, time

def corrigir_logica_kpi_engine():
    """Corrige a lógica no KPI Engine para cálculo correto de horas extras"""
    
    print("🔧 CORREÇÃO FINAL: KPI Engine - Horas Extras")
    print("=" * 60)
    
    # Importar o engine
    from kpis_engine import KPICalculator
    calculator = KPICalculator()
    
    with app.app_context():
        # Buscar registro específico do Antônio
        registro = RegistroPonto.query.join(Funcionario).filter(
            RegistroPonto.data == date(2025, 7, 31),
            Funcionario.nome.like('%Antônio%')
        ).first()
        
        if not registro:
            print("❌ Registro do Antônio não encontrado")
            return
        
        funcionario = registro.funcionario_ref
        print(f"✅ Processando: {funcionario.nome}")
        print(f"   📅 Data: {registro.data}")
        print(f"   🕐 Horário: {registro.hora_entrada} - {registro.hora_saida}")
        print(f"   ⏱️ Antes: {registro.horas_trabalhadas}h trabalhadas, {registro.horas_extras}h extras")
        
        # Aplicar o recálculo usando o KPI Engine
        resultado = calculator.calcular_e_atualizar_ponto(registro.id)
        
        if resultado:
            # Recarregar o registro para ver os novos valores
            db.session.refresh(registro)
            print(f"   ✅ Depois: {registro.horas_trabalhadas}h trabalhadas, {registro.horas_extras}h extras")
            print("🎯 CORREÇÃO APLICADA COM SUCESSO!")
        else:
            print("❌ Falha na aplicação da correção")

def corrigir_todos_registros_31_julho():
    """Recalcula todos os registros de 31/07/2025"""
    
    print("\n🔄 RECALCULANDO TODOS OS REGISTROS DE 31/07/2025")
    print("-" * 60)
    
    from kpis_engine import KPICalculator
    calculator = KPICalculator()
    
    with app.app_context():
        registros = RegistroPonto.query.filter(
            RegistroPonto.data == date(2025, 7, 31)
        ).all()
        
        print(f"📊 Encontrados {len(registros)} registros para recalcular")
        
        sucessos = 0
        for registro in registros:
            funcionario = registro.funcionario_ref
            
            print(f"🔄 {funcionario.nome}: {registro.hora_entrada}-{registro.hora_saida}")
            print(f"   Antes: {registro.horas_extras}h extras")
            
            resultado = calculator.calcular_e_atualizar_ponto(registro.id)
            
            if resultado:
                db.session.refresh(registro)
                print(f"   ✅ Depois: {registro.horas_extras}h extras")
                sucessos += 1
            else:
                print(f"   ❌ Falha no recálculo")
            
        print(f"\n📊 RESUMO: {sucessos}/{len(registros)} registros recalculados com sucesso")

if __name__ == "__main__":
    corrigir_logica_kpi_engine()
    corrigir_todos_registros_31_julho()