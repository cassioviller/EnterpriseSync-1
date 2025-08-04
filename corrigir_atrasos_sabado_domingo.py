#!/usr/bin/env python3
"""
🎯 CORREÇÃO: Cálculo de Atraso Ana Paula - 28/07/2025
PROBLEMA: Entrada 07:30 vs previsto 07:12 = 18min atraso não calculado
"""

from app import app, db
from models import RegistroPonto, Funcionario
from kpis_engine import KPIsEngine
from datetime import datetime, time

def corrigir_atraso_especifico():
    """Corrigir cálculo de atraso para registro específico"""
    with app.app_context():
        print("🔧 CORREÇÃO: Atraso Ana Paula 28/07/2025")
        print("=" * 50)
        
        # Buscar registro específico
        ana_paula = Funcionario.query.filter(Funcionario.nome.ilike('%Ana Paula%')).first()
        if not ana_paula:
            print("❌ Funcionária Ana Paula não encontrada")
            return
            
        registro = RegistroPonto.query.filter(
            RegistroPonto.funcionario_id == ana_paula.id,
            RegistroPonto.data == datetime(2025, 7, 28).date()
        ).first()
        
        if not registro:
            print("❌ Registro de 28/07/2025 não encontrado")
            return
            
        print(f"📋 REGISTRO ENCONTRADO:")
        print(f"   • Funcionária: {ana_paula.nome}")
        print(f"   • Data: {registro.data}")
        print(f"   • Entrada real: {registro.hora_entrada}")
        print(f"   • Entrada prevista: {ana_paula.horario_trabalho.entrada if ana_paula.horario_trabalho else '07:12'}")
        print(f"   • Atraso atual (min): {registro.minutos_atraso_entrada}")
        print(f"   • Atraso atual (h): {registro.total_atraso_horas}")
        
        # Calcular atraso correto
        entrada_real = registro.hora_entrada  # 07:30
        entrada_prevista = ana_paula.horario_trabalho.entrada if ana_paula.horario_trabalho else time(7, 12)  # 07:12
        
        if entrada_real > entrada_prevista:
            # Calcular diferença em minutos
            real_minutos = entrada_real.hour * 60 + entrada_real.minute
            previsto_minutos = entrada_prevista.hour * 60 + entrada_prevista.minute
            atraso_minutos = real_minutos - previsto_minutos
            atraso_horas = atraso_minutos / 60.0
            
            print(f"\n🔍 CÁLCULO CORRETO:")
            print(f"   • Real: {entrada_real} = {real_minutos} min")
            print(f"   • Previsto: {entrada_prevista} = {previsto_minutos} min")
            print(f"   • Atraso: {atraso_minutos} min = {atraso_horas:.2f} h")
            
            # Atualizar registro
            registro.minutos_atraso_entrada = atraso_minutos
            registro.total_atraso_minutos = atraso_minutos + (registro.minutos_atraso_saida or 0)
            registro.total_atraso_horas = registro.total_atraso_minutos / 60.0
            
            db.session.commit()
            
            print(f"\n✅ CORREÇÃO APLICADA:")
            print(f"   • Atraso entrada: {registro.minutos_atraso_entrada} min")
            print(f"   • Atraso total: {registro.total_atraso_horas:.2f} h")
            
            # Forçar recálculo do KPI
            engine = KPIsEngine()
            kpis = engine.calcular_kpis_funcionario(ana_paula.id, datetime(2025, 7, 1).date(), datetime(2025, 7, 31).date())
            
            print(f"\n📊 KPI RECALCULADO:")
            print(f"   • Atrasos (horas): {kpis['atrasos_horas']}")
            
        else:
            print("✅ Sem atraso detectado")

if __name__ == "__main__":
    corrigir_atraso_especifico()