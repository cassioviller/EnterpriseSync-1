#!/usr/bin/env python3
from app import app, db
from models import RegistroPonto

def corrigir_calculo_horas_trabalhadas():
    """Script para corrigir o cálculo incorreto de horas trabalhadas"""
    
    with app.app_context():
        print("🔧 CORRIGINDO CÁLCULO DE HORAS TRABALHADAS...")
        print("=" * 60)
        
        # Buscar registros problemáticos
        registros = RegistroPonto.query.filter(
            RegistroPonto.hora_entrada.isnot(None),
            RegistroPonto.hora_saida.isnot(None)
        ).all()
        
        corrigidos = 0
        
        for registro in registros:
            # Recalcular horas trabalhadas corretamente
            entrada_min = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute
            saida_min = registro.hora_saida.hour * 60 + registro.hora_saida.minute
            
            # Considerar almoço
            almoco_min = 0
            if registro.hora_almoco_saida and registro.hora_almoco_retorno:
                almoco_saida_min = registro.hora_almoco_saida.hour * 60 + registro.hora_almoco_saida.minute
                almoco_retorno_min = registro.hora_almoco_retorno.hour * 60 + registro.hora_almoco_retorno.minute
                almoco_min = almoco_retorno_min - almoco_saida_min
            elif registro.tipo_registro == 'trabalho_normal':
                almoco_min = 60  # 1h padrão
            
            # Cálculo correto
            total_minutos_trabalhados = saida_min - entrada_min - almoco_min
            horas_trabalhadas_corretas = max(0, total_minutos_trabalhados / 60.0)
            
            # Verificar se precisa correção
            if abs(registro.horas_trabalhadas - horas_trabalhadas_corretas) > 0.01:
                print(f"   ✅ ID {registro.id}: {registro.horas_trabalhadas:.2f}h → {horas_trabalhadas_corretas:.2f}h")
                registro.horas_trabalhadas = horas_trabalhadas_corretas
                
                # Recalcular horas extras baseado no valor correto
                if registro.tipo_registro in ['sabado_trabalhado', 'domingo_horas_extras', 'feriado_trabalhado']:
                    registro.horas_extras = horas_trabalhadas_corretas
                else:
                    registro.horas_extras = max(0, horas_trabalhadas_corretas - 8.0)
                
                corrigidos += 1
        
        if corrigidos > 0:
            db.session.commit()
            print(f"\n✅ {corrigidos} registros corrigidos!")
        else:
            print("\n❌ Nenhuma correção necessária")

if __name__ == "__main__":
    corrigir_calculo_horas_trabalhadas()