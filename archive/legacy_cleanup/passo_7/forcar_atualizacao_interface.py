#!/usr/bin/env python3
"""
FORÇAR ATUALIZAÇÃO DA INTERFACE
Corrige inconsistências entre interface e banco de dados
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import date, time

def forcar_atualizacao_interface():
    """Força recálculo e atualização dos valores na interface"""
    
    with app.app_context():
        print("🔄 FORÇANDO ATUALIZAÇÃO DA INTERFACE")
        print("=" * 50)
        
        # Buscar registro específico do exemplo
        registro = RegistroPonto.query.filter(
            RegistroPonto.data == date(2025, 7, 31),
            RegistroPonto.hora_entrada == time(7, 5),
            RegistroPonto.hora_saida == time(17, 50)
        ).first()
        
        if not registro:
            print("❌ Registro não encontrado")
            return
            
        print(f"📊 Registro encontrado:")
        print(f"   Data: {registro.data}")
        print(f"   Funcionário: {registro.funcionario_ref.nome}")
        print(f"   Entrada: {registro.hora_entrada}")
        print(f"   Saída: {registro.hora_saida}")
        print()
        
        # Valores antes da correção
        print(f"📋 ANTES DA CORREÇÃO:")
        print(f"   Horas Extras: {registro.horas_extras}h")
        print(f"   Atrasos: {registro.total_atraso_horas or 0}h")
        print()
        
        # Aplicar lógica correta manualmente
        entrada_real_min = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute
        saida_real_min = registro.hora_saida.hour * 60 + registro.hora_saida.minute
        entrada_padrao_min = 7*60 + 12  # 07:12
        saida_padrao_min = 17*60  # 17:00
        
        # ATRASOS (chegou depois OU saiu antes)
        atraso_entrada_min = max(0, entrada_real_min - entrada_padrao_min)
        atraso_saida_min = max(0, saida_padrao_min - saida_real_min)
        total_atraso_min = atraso_entrada_min + atraso_saida_min
        
        # HORAS EXTRAS (chegou antes OU saiu depois)
        extra_entrada_min = max(0, entrada_padrao_min - entrada_real_min)
        extra_saida_min = max(0, saida_real_min - saida_padrao_min)
        total_extra_min = extra_entrada_min + extra_saida_min
        
        # APLICAR VALORES CORRETOS
        registro.minutos_atraso_entrada = atraso_entrada_min
        registro.minutos_atraso_saida = atraso_saida_min
        registro.total_atraso_minutos = total_atraso_min
        registro.total_atraso_horas = round(total_atraso_min / 60.0, 2)
        
        registro.horas_extras = round(total_extra_min / 60.0, 2)
        registro.percentual_extras = 50.0 if registro.horas_extras > 0 else 0.0
        
        # Recalcular horas trabalhadas
        tempo_total_min = saida_real_min - entrada_real_min
        tempo_almoco = 60  # 1 hora padrão
        horas_trabalhadas = max(0, (tempo_total_min - tempo_almoco) / 60.0)
        registro.horas_trabalhadas = round(horas_trabalhadas, 2)
        
        print(f"🔧 CÁLCULO DETALHADO:")
        print(f"   Entrada: {registro.hora_entrada} ({entrada_real_min} min)")
        print(f"   Saída: {registro.hora_saida} ({saida_real_min} min)")
        print(f"   Padrão: 07:12-17:00 ({entrada_padrao_min}-{saida_padrao_min} min)")
        print()
        print(f"   Extra entrada: {extra_entrada_min} min = {extra_entrada_min/60:.2f}h")
        print(f"   Extra saída: {extra_saida_min} min = {extra_saida_min/60:.2f}h")
        print(f"   Total extras: {total_extra_min} min = {total_extra_min/60:.2f}h")
        print()
        
        # Commit das alterações
        try:
            db.session.commit()
            print(f"✅ VALORES ATUALIZADOS:")
            print(f"   Horas Extras: {registro.horas_extras}h")
            print(f"   Atrasos: {registro.total_atraso_horas}h")
            print(f"   Horas Trabalhadas: {registro.horas_trabalhadas}h")
            print(f"   Percentual: {registro.percentual_extras}%")
            print()
            print(f"🎯 INTERFACE DEVE MOSTRAR: {registro.horas_extras}h - {registro.percentual_extras}%")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao atualizar: {str(e)}")

def atualizar_todos_registros_julho():
    """Atualiza todos os registros de julho para garantir consistência"""
    
    with app.app_context():
        print("\n🔄 ATUALIZANDO TODOS OS REGISTROS DE JULHO")
        print("=" * 50)
        
        # Buscar todos os registros de julho 2025
        registros = RegistroPonto.query.filter(
            RegistroPonto.data >= date(2025, 7, 1),
            RegistroPonto.data <= date(2025, 7, 31),
            RegistroPonto.hora_entrada.isnot(None),
            RegistroPonto.hora_saida.isnot(None)
        ).all()
        
        print(f"📊 Encontrados {len(registros)} registros em julho")
        registros_atualizados = 0
        
        for registro in registros:
            if registro.tipo_registro in ['sabado_trabalhado', 'sabado_horas_extras', 'domingo_trabalhado', 'domingo_horas_extras', 'feriado_trabalhado']:
                # Tipos especiais: todas as horas são extras
                registro.horas_extras = registro.horas_trabalhadas or 0
                registro.total_atraso_horas = 0
                registro.total_atraso_minutos = 0
                registro.minutos_atraso_entrada = 0
                registro.minutos_atraso_saida = 0
                
                if registro.tipo_registro in ['sabado_trabalhado', 'sabado_horas_extras']:
                    registro.percentual_extras = 50.0
                else:
                    registro.percentual_extras = 100.0
            else:
                # Tipos normais: aplicar lógica padrão
                entrada_real_min = registro.hora_entrada.hour * 60 + registro.hora_entrada.minute
                saida_real_min = registro.hora_saida.hour * 60 + registro.hora_saida.minute
                entrada_padrao_min = 7*60 + 12  # 07:12
                saida_padrao_min = 17*60  # 17:00
                
                # ATRASOS
                atraso_entrada_min = max(0, entrada_real_min - entrada_padrao_min)
                atraso_saida_min = max(0, saida_padrao_min - saida_real_min)
                total_atraso_min = atraso_entrada_min + atraso_saida_min
                
                # EXTRAS
                extra_entrada_min = max(0, entrada_padrao_min - entrada_real_min)
                extra_saida_min = max(0, saida_real_min - saida_padrao_min)
                total_extra_min = extra_entrada_min + extra_saida_min
                
                # APLICAR
                registro.minutos_atraso_entrada = atraso_entrada_min
                registro.minutos_atraso_saida = atraso_saida_min
                registro.total_atraso_minutos = total_atraso_min
                registro.total_atraso_horas = round(total_atraso_min / 60.0, 2)
                
                registro.horas_extras = round(total_extra_min / 60.0, 2)
                registro.percentual_extras = 50.0 if registro.horas_extras > 0 else 0.0
            
            registros_atualizados += 1
        
        try:
            db.session.commit()
            print(f"✅ {registros_atualizados} registros atualizados com sucesso")
            
            # Verificar registro específico novamente
            registro_exemplo = RegistroPonto.query.filter(
                RegistroPonto.data == date(2025, 7, 31),
                RegistroPonto.hora_entrada == time(7, 5),
                RegistroPonto.hora_saida == time(17, 50)
            ).first()
            
            if registro_exemplo:
                print(f"\n🎯 VERIFICAÇÃO FINAL - Registro 31/07:")
                print(f"   Horas Extras: {registro_exemplo.horas_extras}h")
                print(f"   Interface deve mostrar: {registro_exemplo.horas_extras}h - {registro_exemplo.percentual_extras}%")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro na atualização em lote: {str(e)}")

if __name__ == "__main__":
    forcar_atualizacao_interface()
    atualizar_todos_registros_julho()