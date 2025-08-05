#!/usr/bin/env python3
"""
HOTFIX PRODUÇÃO: Correção de Horas Extras
Execute este arquivo no ambiente de produção para corrigir os cálculos
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import date, time

def aplicar_correcao_producao():
    """Aplica correção completa no ambiente de produção"""
    
    with app.app_context():
        print("🚨 HOTFIX PRODUÇÃO - CORREÇÃO HORAS EXTRAS")
        print("=" * 50)
        
        registros_corrigidos = 0
        
        # Buscar TODOS os registros com horários informados
        registros = RegistroPonto.query.filter(
            RegistroPonto.hora_entrada.isnot(None),
            RegistroPonto.hora_saida.isnot(None)
        ).all()
        
        print(f"📋 Processando {len(registros)} registros...")
        
        for registro in registros:
            funcionario = Funcionario.query.get(registro.funcionario_id)
            
            # Valores anteriores para log
            old_extra = registro.horas_extras or 0
            old_atraso = registro.total_atraso_horas or 0
            
            # APLICAR LÓGICA BASEADA NO TIPO DE REGISTRO
            if registro.tipo_registro in ['sabado_trabalhado', 'sabado_horas_extras', 'domingo_trabalhado', 'domingo_horas_extras', 'feriado_trabalhado']:
                # TIPOS ESPECIAIS: TODAS as horas são extras, SEM atrasos
                registro.horas_extras = registro.horas_trabalhadas or 0
                registro.total_atraso_horas = 0
                registro.total_atraso_minutos = 0
                registro.minutos_atraso_entrada = 0
                registro.minutos_atraso_saida = 0
                
                if registro.tipo_registro in ['sabado_trabalhado', 'sabado_horas_extras']:
                    registro.percentual_extras = 50.0
                else:  # domingo, feriado
                    registro.percentual_extras = 100.0
            else:
                # TIPOS NORMAIS: Calcular extras e atrasos independentemente
                
                # Horário padrão: 07:12-17:00 (todos funcionários)
                padrao_entrada_min = 7 * 60 + 12  # 432 min
                padrao_saida_min = 17 * 60         # 1020 min
                
                # Horário real
                real_entrada_min = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute
                real_saida_min = registro.hora_saida.hour * 60 + registro.hora_saida.minute
                
                # CALCULAR ATRASOS (chegou depois OU saiu antes)
                atraso_entrada = max(0, real_entrada_min - padrao_entrada_min)
                atraso_saida = max(0, padrao_saida_min - real_saida_min)
                total_atraso_min = atraso_entrada + atraso_saida
                
                # CALCULAR EXTRAS (chegou antes OU saiu depois)
                extra_entrada = max(0, padrao_entrada_min - real_entrada_min)
                extra_saida = max(0, real_saida_min - padrao_saida_min)
                total_extra_min = extra_entrada + extra_saida
                
                # Converter para horas
                atraso_horas = round(total_atraso_min / 60.0, 2)
                extra_horas = round(total_extra_min / 60.0, 2)
                
                # Aplicar valores
                registro.horas_extras = extra_horas
                registro.total_atraso_horas = atraso_horas
                registro.total_atraso_minutos = total_atraso_min
                registro.minutos_atraso_entrada = atraso_entrada
                registro.minutos_atraso_saida = atraso_saida
                
                # Percentual de extras
                registro.percentual_extras = 50.0 if registro.horas_extras > 0 else 0.0
                
                # Recalcular horas trabalhadas se necessário
                if not registro.horas_trabalhadas or registro.horas_trabalhadas <= 0:
                    total_min = real_saida_min - real_entrada_min - 60  # Menos 1h almoço
                    registro.horas_trabalhadas = round(max(0, total_min / 60.0), 2)
            
            # Verificar se houve mudança significativa
            mudou_extras = abs((registro.horas_extras or 0) - old_extra) > 0.01
            mudou_atrasos = abs((registro.total_atraso_horas or 0) - old_atraso) > 0.01
            
            if mudou_extras or mudou_atrasos:
                print(f"✅ {funcionario.nome} {registro.data}: "
                      f"Extras {old_extra}h→{registro.horas_extras}h, "
                      f"Atrasos {old_atraso}h→{registro.total_atraso_horas}h")
                
                registros_corrigidos += 1
        
        # Commit das alterações
        try:
            db.session.commit()
            print(f"\n🎉 SUCESSO: {registros_corrigidos} registros corrigidos!")
            
            # Estatísticas finais
            total_registros = RegistroPonto.query.filter(
                RegistroPonto.hora_entrada.isnot(None),
                RegistroPonto.hora_saida.isnot(None)
            ).count()
            
            print(f"\n📊 ESTATÍSTICAS:")
            print(f"   Total de registros processados: {total_registros}")
            print(f"   Registros corrigidos: {registros_corrigidos}")
            print(f"   Taxa de correção: {(registros_corrigidos/total_registros*100):.1f}%")
            
            print("\n✅ HOTFIX APLICADO COM SUCESSO!")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ ERRO: {str(e)}")
            raise

if __name__ == "__main__":
    aplicar_correcao_producao()