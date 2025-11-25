#!/usr/bin/env python3
"""
FORÇAR RECÁLCULO COMPLETO DOS KPIs
Força o recálculo de todos os KPIs para atualizar a interface
"""

from app import app, db
from models import RegistroPonto, Funcionario
from kpis_engine import KPIsEngine
from datetime import date, datetime

def forcar_recalculo_completo():
    """Força recálculo de todos os KPIs no sistema"""
    
    with app.app_context():
        print("🔄 FORÇANDO RECÁLCULO COMPLETO DOS KPIs")
        print("=" * 50)
        
        # Inicializar engine de KPIs
        kpis_engine = KPIsEngine()
        
        # Buscar todos os funcionários
        funcionarios = Funcionario.query.filter_by(ativo=True).all()
        
        print(f"📊 Processando {len(funcionarios)} funcionários...")
        
        # Período padrão (julho 2025)
        data_inicio = date(2025, 7, 1)
        data_fim = date(2025, 7, 31)
        
        funcionarios_processados = 0
        
        for funcionario in funcionarios:
            print(f"\n🔄 Processando: {funcionario.nome}")
            
            # Primeiro, recalcular todos os registros de ponto deste funcionário
            registros = RegistroPonto.query.filter(
                RegistroPonto.funcionario_id == funcionario.id,
                RegistroPonto.data >= data_inicio,
                RegistroPonto.data <= data_fim
            ).all()
            
            registros_recalculados = 0
            for registro in registros:
                # Forçar recálculo usando a função corrigida
                if kpis_engine._corrigir_calculo_horas_extras(registro.id):
                    registros_recalculados += 1
            
            if registros_recalculados > 0:
                print(f"   ✅ {registros_recalculados} registros recalculados")
            
            # Agora calcular KPIs para este funcionário
            try:
                kpis = kpis_engine.calcular_kpis_funcionario(
                    funcionario.id, data_inicio, data_fim
                )
                
                # Mostrar valores principais
                horas_trabalhadas = kpis.get('horas_trabalhadas', 0)
                horas_extras = kpis.get('horas_extras', 0)
                atrasos = kpis.get('atrasos_horas', 0)
                
                print(f"   📈 KPIs: {horas_trabalhadas}h trabalhadas, {horas_extras}h extras, {atrasos}h atrasos")
                funcionarios_processados += 1
                
            except Exception as e:
                print(f"   ❌ Erro ao calcular KPIs: {str(e)}")
        
        # Commit final
        try:
            db.session.commit()
            print(f"\n🎉 RECÁLCULO COMPLETO FINALIZADO!")
            print(f"   Funcionários processados: {funcionarios_processados}")
            
            # Verificar casos específicos mencionados
            print(f"\n🔍 VERIFICAÇÃO DOS CASOS ESPECÍFICOS:")
            
            # João Silva Santos 31/07
            joao_registro = RegistroPonto.query.filter(
                RegistroPonto.data == date(2025, 7, 31)
            ).join(Funcionario).filter(
                Funcionario.nome.ilike('%João Silva Santos%')
            ).first()
            
            if joao_registro:
                print(f"   ✅ João Silva Santos 31/07: {joao_registro.horas_extras}h extras")
            
            # Ana Paula 29/07
            ana_registro = RegistroPonto.query.filter(
                RegistroPonto.data == date(2025, 7, 29)
            ).join(Funcionario).filter(
                Funcionario.nome.ilike('%Ana Paula%')
            ).first()
            
            if ana_registro:
                print(f"   ✅ Ana Paula 29/07: {ana_registro.horas_extras}h extras, {ana_registro.total_atraso_horas}h atrasos")
            
            print(f"\n✅ SISTEMA ATUALIZADO - INTERFACE DEVE REFLETIR OS NOVOS VALORES!")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ ERRO NO COMMIT: {str(e)}")
            raise

if __name__ == "__main__":
    forcar_recalculo_completo()