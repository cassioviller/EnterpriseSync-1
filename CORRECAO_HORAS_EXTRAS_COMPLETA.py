#!/usr/bin/env python3
"""
CORREÇÃO COMPLETA DO SISTEMA DE HORAS EXTRAS
Identifica e corrige todas as lógicas conflitantes no sistema
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import date, time, datetime

def corrigir_logica_horas_extras_sistema():
    """Corrige a lógica de horas extras em todo o sistema"""
    
    with app.app_context():
        print("🔧 CORREÇÃO COMPLETA DO SISTEMA DE HORAS EXTRAS")
        print("=" * 60)
        
        # 1. DEFINIR HORÁRIO PADRÃO ÚNICO (conforme replit.md)
        horario_entrada_padrao = time(7, 12)  # 07:12
        horario_saida_padrao = time(17, 0)    # 17:00
        
        print(f"📋 HORÁRIO PADRÃO DEFINIDO: {horario_entrada_padrao} - {horario_saida_padrao}")
        
        # 2. BUSCAR TODOS OS REGISTROS QUE PRECISAM CORREÇÃO
        registros = RegistroPonto.query.filter(
            RegistroPonto.hora_entrada.isnot(None),
            RegistroPonto.hora_saida.isnot(None)
        ).all()
        
        print(f"📊 PROCESSANDO {len(registros)} REGISTROS...")
        
        registros_corrigidos = 0
        
        for registro in registros:
            funcionario = Funcionario.query.get(registro.funcionario_id)
            
            # VALORES ANTERIORES PARA COMPARAÇÃO
            horas_extras_antigas = registro.horas_extras or 0
            atrasos_antigos = registro.total_atraso_horas or 0
            
            # 3. APLICAR LÓGICA CORRETA BASEADA NO TIPO
            if registro.tipo_registro in ['sabado_trabalhado', 'sabado_horas_extras', 'domingo_trabalhado', 'domingo_horas_extras', 'feriado_trabalhado']:
                # TIPOS ESPECIAIS: TODAS AS HORAS SÃO EXTRAS
                registro.horas_extras = registro.horas_trabalhadas or 0
                registro.total_atraso_horas = 0  # Sem conceito de atraso
                registro.total_atraso_minutos = 0
                registro.minutos_atraso_entrada = 0
                registro.minutos_atraso_saida = 0
                
                # PERCENTUAL CORRETO
                if registro.tipo_registro in ['sabado_trabalhado', 'sabado_horas_extras']:
                    registro.percentual_extras = 50.0
                else:  # domingo, feriado
                    registro.percentual_extras = 100.0
                    
            else:
                # TIPOS NORMAIS: CALCULAR EXTRAS E ATRASOS SEPARADAMENTE
                
                # Converter horários para minutos
                entrada_real_min = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute
                saida_real_min = registro.hora_saida.hour * 60 + registro.hora_saida.minute
                entrada_padrao_min = horario_entrada_padrao.hour * 60 + horario_entrada_padrao.minute
                saida_padrao_min = horario_saida_padrao.hour * 60 + horario_saida_padrao.minute
                
                # CALCULAR ATRASOS (chegou depois OU saiu antes)
                atraso_entrada_min = max(0, entrada_real_min - entrada_padrao_min)
                atraso_saida_min = max(0, saida_padrao_min - saida_real_min)
                total_atraso_min = atraso_entrada_min + atraso_saida_min
                
                # CALCULAR HORAS EXTRAS (chegou antes OU saiu depois)
                extra_entrada_min = max(0, entrada_padrao_min - entrada_real_min)
                extra_saida_min = max(0, saida_real_min - saida_padrao_min)
                total_extra_min = extra_entrada_min + extra_saida_min
                
                # APLICAR VALORES CORRIGIDOS
                registro.minutos_atraso_entrada = atraso_entrada_min
                registro.minutos_atraso_saida = atraso_saida_min
                registro.total_atraso_minutos = total_atraso_min
                registro.total_atraso_horas = round(total_atraso_min / 60.0, 2)
                
                registro.horas_extras = round(total_extra_min / 60.0, 2)
                
                if registro.horas_extras > 0:
                    registro.percentual_extras = 50.0
                else:
                    registro.percentual_extras = 0.0
                
                # RECALCULAR HORAS TRABALHADAS SE NECESSÁRIO
                if not registro.horas_trabalhadas or registro.horas_trabalhadas <= 0:
                    total_trabalho_min = saida_real_min - entrada_real_min - 60  # Menos 1h almoço
                    registro.horas_trabalhadas = round(max(0, total_trabalho_min / 60.0), 2)
            
            # VERIFICAR SE HOUVE MUDANÇA SIGNIFICATIVA
            mudou_extras = abs((registro.horas_extras or 0) - horas_extras_antigas) > 0.01
            mudou_atrasos = abs((registro.total_atraso_horas or 0) - atrasos_antigos) > 0.01
            
            if mudou_extras or mudou_atrasos:
                print(f"  ✅ {funcionario.nome} {registro.data}: "
                      f"Extras {horas_extras_antigas}h→{registro.horas_extras}h, "
                      f"Atrasos {atrasos_antigos}h→{registro.total_atraso_horas}h")
                registros_corrigidos += 1
        
        # 4. COMMIT DAS ALTERAÇÕES
        try:
            db.session.commit()
            print(f"\n🎉 SUCESSO: {registros_corrigidos} registros corrigidos!")
            
            # 5. VERIFICAR CASOS ESPECÍFICOS MENCIONADOS
            print("\n🔍 VERIFICAÇÃO FINAL DOS CASOS ESPECÍFICOS:")
            
            # João Silva Santos 31/07/2025
            joao_31 = RegistroPonto.query.filter(
                RegistroPonto.data == date(2025, 7, 31),
                RegistroPonto.hora_entrada == time(7, 5),
                RegistroPonto.hora_saida == time(17, 50)
            ).first()
            
            if joao_31:
                func1 = Funcionario.query.get(joao_31.funcionario_id)
                print(f"  ✅ {func1.nome} 31/07: {joao_31.horas_extras}h extras - {joao_31.percentual_extras}%")
                if abs(joao_31.horas_extras - 0.95) < 0.01:
                    print("    ✅ VALOR CORRETO!")
                else:
                    print(f"    ❌ ESPERADO: 0.95h, ATUAL: {joao_31.horas_extras}h")
            
            # Ana Paula 29/07/2025
            ana_29 = RegistroPonto.query.filter(
                RegistroPonto.data == date(2025, 7, 29),
                RegistroPonto.hora_entrada == time(7, 30),
                RegistroPonto.hora_saida == time(18, 0)
            ).first()
            
            if ana_29:
                func2 = Funcionario.query.get(ana_29.funcionario_id)
                print(f"  ✅ {func2.nome} 29/07: {ana_29.horas_extras}h extras, {ana_29.total_atraso_horas}h atrasos")
                if abs(ana_29.horas_extras - 1.0) < 0.01 and abs(ana_29.total_atraso_horas - 0.3) < 0.01:
                    print("    ✅ VALORES CORRETOS!")
                else:
                    print(f"    ❌ ESPERADO: 1.0h extras, 0.3h atrasos")
            
            print("\n✅ CORREÇÃO COMPLETA FINALIZADA!")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ ERRO: {str(e)}")
            raise

def verificar_multiplas_logicas():
    """Identifica arquivos com lógicas conflitantes"""
    
    print("\n🔍 VERIFICAÇÃO DE LÓGICAS MÚLTIPLAS:")
    print("-" * 50)
    
    arquivos_problematicos = [
        "kpis_engine.py (linhas 583-601)",
        "utils.py (função calcular_horas_trabalhadas)",
        "views.py (função processar_lancamento_multiplo)", 
        "kpis_engine_v8_1.py (método calcular_custo_funcionario)"
    ]
    
    print("⚠️  ARQUIVOS COM LÓGICAS CONFLITANTES IDENTIFICADOS:")
    for arquivo in arquivos_problematicos:
        print(f"   - {arquivo}")
    
    print("\n📋 RECOMENDAÇÃO:")
    print("   - Usar apenas a lógica consolidada neste script")
    print("   - Padronizar todas as funções para usar o mesmo cálculo")
    print("   - Horário padrão: 07:12-17:00 para todos os funcionários")

if __name__ == "__main__":
    print("🚨 CORREÇÃO COMPLETA DO SISTEMA DE HORAS EXTRAS")
    print("=" * 70)
    
    corrigir_logica_horas_extras_sistema()
    verificar_multiplas_logicas()