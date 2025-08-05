#!/usr/bin/env python3
"""
CORREÇÃO ESPECÍFICA DOS REGISTROS NA IMAGEM
Corrige os registros específicos que estão aparecendo incorretos na interface
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import date, time

def corrigir_registros_especificos():
    """Corrige especificamente os registros visíveis na imagem"""
    
    with app.app_context():
        print("🎯 CORREÇÃO ESPECÍFICA DOS REGISTROS NA IMAGEM")
        print("=" * 60)
        
        # Registros específicos da imagem com os horários exatos
        registros_alvo = [
            {'data': date(2025, 7, 31), 'entrada': time(7, 5), 'saida': time(17, 50)},   # João 31/07
            {'data': date(2025, 7, 30), 'entrada': time(7, 6), 'saida': time(17, 36)},   # João 30/07  
            {'data': date(2025, 7, 29), 'entrada': time(7, 8), 'saida': time(17, 31)},   # Ana 29/07
            {'data': date(2025, 7, 25), 'entrada': time(7, 12), 'saida': time(17, 0)},   # 25/07
            {'data': date(2025, 7, 24), 'entrada': time(7, 8), 'saida': time(18, 31)},   # 24/07
            {'data': date(2025, 7, 23), 'entrada': time(7, 6), 'saida': time(17, 30)},   # 23/07
            {'data': date(2025, 7, 22), 'entrada': time(7, 12), 'saida': time(17, 0)},   # 22/07
            {'data': date(2025, 7, 21), 'entrada': time(7, 7), 'saida': time(17, 23)},   # 21/07
        ]
        
        # Horário padrão: 07:12 - 17:00
        padrao_entrada_min = 7 * 60 + 12  # 432 min
        padrao_saida_min = 17 * 60         # 1020 min
        
        registros_corrigidos = 0
        
        for reg_info in registros_alvo:
            # Buscar registro na data específica
            registro = RegistroPonto.query.filter(
                RegistroPonto.data == reg_info['data'],
                RegistroPonto.hora_entrada == reg_info['entrada'],
                RegistroPonto.hora_saida == reg_info['saida']
            ).first()
            
            if not registro:
                print(f"❌ Registro não encontrado: {reg_info['data']} {reg_info['entrada']}-{reg_info['saida']}")
                continue
            
            funcionario = Funcionario.query.get(registro.funcionario_id)
            
            print(f"\n🔧 Corrigindo: {funcionario.nome} - {registro.data}")
            print(f"   Horários: {registro.hora_entrada} - {registro.hora_saida}")
            
            # Valores anteriores
            old_extras = registro.horas_extras or 0
            old_atrasos = registro.total_atraso_horas or 0
            
            # APLICAR LÓGICA CONSOLIDADA
            if registro.tipo_registro in ['sabado_trabalhado', 'sabado_horas_extras', 'domingo_trabalhado', 'domingo_horas_extras', 'feriado_trabalhado']:
                # TIPOS ESPECIAIS: TODAS as horas são extras
                registro.horas_extras = registro.horas_trabalhadas or 0
                registro.total_atraso_horas = 0
                registro.total_atraso_minutos = 0
                registro.minutos_atraso_entrada = 0
                registro.minutos_atraso_saida = 0
                
                if registro.tipo_registro in ['sabado_trabalhado', 'sabado_horas_extras']:
                    registro.percentual_extras = 50.0
                else:
                    registro.percentual_extras = 100.0
                    
                print(f"   📊 TIPO ESPECIAL: {registro.horas_extras}h extras (todas as horas)")
            else:
                # TIPOS NORMAIS: Calcular extras e atrasos independentemente
                real_entrada_min = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute
                real_saida_min = registro.hora_saida.hour * 60 + registro.hora_saida.minute
                
                # ATRASOS (chegou depois OU saiu antes)
                atraso_entrada = max(0, real_entrada_min - padrao_entrada_min)
                atraso_saida = max(0, padrao_saida_min - real_saida_min)
                total_atraso_min = atraso_entrada + atraso_saida
                
                # EXTRAS (chegou antes OU saiu depois)
                extra_entrada = max(0, padrao_entrada_min - real_entrada_min)
                extra_saida = max(0, real_saida_min - padrao_saida_min)
                total_extra_min = extra_entrada + extra_saida
                
                # APLICAR VALORES
                registro.minutos_atraso_entrada = atraso_entrada
                registro.minutos_atraso_saida = atraso_saida
                registro.total_atraso_minutos = total_atraso_min
                registro.total_atraso_horas = round(total_atraso_min / 60.0, 2)
                
                registro.horas_extras = round(total_extra_min / 60.0, 2)
                registro.percentual_extras = 50.0 if registro.horas_extras > 0 else 0.0
                
                # RECALCULAR HORAS TRABALHADAS
                total_trabalho_min = real_saida_min - real_entrada_min - 60  # Menos 1h almoço
                registro.horas_trabalhadas = round(max(0, total_trabalho_min / 60.0), 2)
                
                print(f"   📊 NORMAL: {registro.horas_extras}h extras, {registro.total_atraso_horas}h atrasos")
                print(f"        Entrada: {extra_entrada}min antes + {atraso_entrada}min depois")
                print(f"        Saída: {extra_saida}min depois + {atraso_saida}min antes")
            
            # LOG DA MUDANÇA
            if abs(registro.horas_extras - old_extras) > 0.01 or abs(registro.total_atraso_horas - old_atrasos) > 0.01:
                print(f"   ✅ CORRIGIDO: Extras {old_extras}h→{registro.horas_extras}h, Atrasos {old_atrasos}h→{registro.total_atraso_horas}h")
                registros_corrigidos += 1
            else:
                print(f"   ➖ Sem alteração necessária")
        
        # COMMIT
        try:
            db.session.commit()
            print(f"\n🎉 CORREÇÃO APLICADA COM SUCESSO!")
            print(f"   Registros corrigidos: {registros_corrigidos}")
            
            # VALIDAÇÃO FINAL DOS CASOS ESPECÍFICOS
            print(f"\n🔍 VALIDAÇÃO FINAL:")
            
            # João Silva Santos 31/07 - deve ter 0.95h extras
            joao_31 = RegistroPonto.query.filter(
                RegistroPonto.data == date(2025, 7, 31),
                RegistroPonto.hora_entrada == time(7, 5),
                RegistroPonto.hora_saida == time(17, 50)
            ).first()
            
            if joao_31:
                func = Funcionario.query.get(joao_31.funcionario_id)
                print(f"   ✅ {func.nome} 31/07: {joao_31.horas_extras}h extras")
                # Cálculo esperado: 7min entrada + 50min saída = 57min = 0.95h
                if abs(joao_31.horas_extras - 0.95) < 0.01:
                    print(f"      ✅ CORRETO! (7min + 50min = 0.95h)")
                else:
                    print(f"      ❌ ESPERADO: 0.95h")
            
            # Ana Paula 29/07 - deve ter 1.0h extras + 0.3h atrasos  
            ana_29 = RegistroPonto.query.filter(
                RegistroPonto.data == date(2025, 7, 29),
                RegistroPonto.hora_entrada == time(7, 30),
                RegistroPonto.hora_saida == time(18, 0)
            ).first()
            
            if ana_29:
                func = Funcionario.query.get(ana_29.funcionario_id)
                print(f"   ✅ {func.nome} 29/07: {ana_29.horas_extras}h extras, {ana_29.total_atraso_horas}h atrasos")
                # Extras: 60min saída = 1.0h, Atrasos: 18min entrada = 0.3h
                if abs(ana_29.horas_extras - 1.0) < 0.01 and abs(ana_29.total_atraso_horas - 0.3) < 0.01:
                    print(f"      ✅ CORRETO! (60min extras + 18min atrasos)")
                else:
                    print(f"      ❌ ESPERADO: 1.0h extras, 0.3h atrasos")
            
            print(f"\n🚀 AGORA ATUALIZE A PÁGINA PARA VER OS VALORES CORRETOS!")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ ERRO: {str(e)}")
            raise

if __name__ == "__main__":
    corrigir_registros_especificos()