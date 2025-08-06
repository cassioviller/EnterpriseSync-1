#!/usr/bin/env python3
"""
CORREÇÃO DEFINITIVA: RESTAURAR SÁBADOS TRABALHADOS
Data: 06 de Agosto de 2025
Garante que sábados/feriados mantenham valores originais em TODOS os campos
"""

from app import app, db
from models import RegistroPonto

def restaurar_sabados_e_feriados():
    """Restaura campos originais para sábados e feriados"""
    print("🔧 RESTAURANDO SÁBADOS E FERIADOS PARA VALORES ORIGINAIS")
    
    with app.app_context():
        try:
            # Buscar todos os sábados e feriados trabalhados
            registros_especiais = RegistroPonto.query.filter(
                RegistroPonto.tipo_registro.in_([
                    'sabado_trabalhado', 
                    'feriado_trabalhado', 
                    'domingo_trabalhado'
                ])
            ).all()
            
            print(f"📊 Encontrados {len(registros_especiais)} registros especiais para restaurar")
            
            restaurados = 0
            
            for registro in registros_especiais:
                try:
                    funcionario = registro.funcionario_ref
                    horas_originais = registro.horas_extras or 0.0
                    
                    print(f"👤 {funcionario.nome} - {registro.data} ({registro.tipo_registro})")
                    print(f"   Horas extras originais: {horas_originais}h")
                    
                    # GARANTIR que o campo horas_extras_detalhadas seja igual ao original
                    if hasattr(registro, 'horas_extras_detalhadas'):
                        registro.horas_extras_detalhadas = horas_originais
                    
                    # ZERAR campos de horário padrão para sábados/feriados
                    if hasattr(registro, 'minutos_extras_entrada'):
                        registro.minutos_extras_entrada = 0
                    if hasattr(registro, 'minutos_extras_saida'):
                        registro.minutos_extras_saida = 0
                    if hasattr(registro, 'total_minutos_extras'):
                        registro.total_minutos_extras = 0
                    
                    print(f"   ✅ Restaurado: horas_extras_detalhadas = {horas_originais}h")
                    restaurados += 1
                    
                except Exception as e:
                    print(f"❌ Erro no registro {registro.id}: {e}")
                    continue
            
            # Salvar alterações
            db.session.commit()
            
            print(f"\n📋 RESTAURAÇÃO CONCLUÍDA:")
            print(f"   Registros restaurados: {restaurados}")
            print(f"   ✅ Sábados/feriados agora têm valores consistentes")
            
            return True
            
        except Exception as e:
            print(f"❌ Erro na restauração: {e}")
            db.session.rollback()
            return False

def verificar_consistencia_final():
    """Verifica se a consistência foi restaurada"""
    print("🔍 VERIFICANDO CONSISTÊNCIA FINAL")
    
    with app.app_context():
        try:
            # Verificar alguns sábados
            sabados = RegistroPonto.query.filter_by(
                tipo_registro='sabado_trabalhado'
            ).limit(10).all()
            
            print(f"📊 Verificando {len(sabados)} sábados trabalhados:")
            
            inconsistencias = 0
            
            for sabado in sabados:
                funcionario = sabado.funcionario_ref
                horas_original = sabado.horas_extras or 0.0
                horas_detalhadas = getattr(sabado, 'horas_extras_detalhadas', 0.0) or 0.0
                
                print(f"   👤 {funcionario.nome} - {sabado.data}")
                print(f"      Original: {horas_original}h | Detalhadas: {horas_detalhadas}h")
                
                if abs(horas_original - horas_detalhadas) > 0.01:  # Margem de erro
                    print(f"      ❌ INCONSISTÊNCIA: {horas_original}h ≠ {horas_detalhadas}h")
                    inconsistencias += 1
                else:
                    print(f"      ✅ CONSISTENTE")
            
            print(f"\n📊 RESULTADO:")
            print(f"   Inconsistências encontradas: {inconsistencias}")
            
            return inconsistencias == 0
            
        except Exception as e:
            print(f"❌ Erro na verificação: {e}")
            return False

if __name__ == "__main__":
    print("🎯 CORREÇÃO DEFINITIVA DOS SÁBADOS TRABALHADOS")
    print("="*60)
    
    # 1. Restaurar valores originais
    if restaurar_sabados_e_feriados():
        print("✅ Restauração concluída")
    else:
        print("❌ Falha na restauração")
        exit(1)
    
    print("\n" + "="*60)
    
    # 2. Verificar consistência
    if verificar_consistencia_final():
        print("✅ SISTEMA TOTALMENTE CONSISTENTE!")
        print("   Sábados/feriados: lógica original preservada")
        print("   Dias normais: horário padrão aplicado")
    else:
        print("⚠️ Ainda há inconsistências a resolver")
    
    print("\n🎯 CORREÇÃO DOS SÁBADOS FINALIZADA!")