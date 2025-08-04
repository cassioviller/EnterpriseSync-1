#!/usr/bin/env python3
"""
🔧 APLICAR LÓGICA DE SÁBADO TRABALHADO URGENTE
Garante que TODOS os registros de sábado sigam a regra:
- Horas extras = Horas trabalhadas
- Atraso = 0 sempre
"""

from app import app, db
from models import RegistroPonto
from datetime import datetime, time
import logging

logging.basicConfig(level=logging.INFO)

def aplicar_logica_sabado_trabalhado():
    """Aplica lógica correta para TODOS os registros de sábado"""
    print("🔧 APLICANDO LÓGICA CORRETA PARA SÁBADOS TRABALHADOS...")
    
    # Buscar TODOS os registros de sábado (dia da semana = 5)
    registros_sabado = RegistroPonto.query.filter(
        db.extract('dow', RegistroPonto.data) == 6,  # PostgreSQL: sábado = 6
        RegistroPonto.hora_entrada.isnot(None),
        RegistroPonto.hora_saida.isnot(None)
    ).all()
    
    print(f"📊 Encontrados {len(registros_sabado)} registros de sábado com horários")
    
    registros_corrigidos = 0
    
    for registro in registros_sabado:
        print(f"🔧 Processando: {registro.data} (ID: {registro.id})")
        
        # 1. GARANTIR TIPO CORRETO
        if registro.tipo_registro != 'sabado_horas_extras':
            print(f"   ↳ Corrigindo tipo: {registro.tipo_registro} → sabado_horas_extras")
            registro.tipo_registro = 'sabado_horas_extras'
        
        # 2. RECALCULAR HORAS TRABALHADAS SE NECESSÁRIO
        if registro.hora_entrada and registro.hora_saida:
            # Calcular horas trabalhadas
            entrada = datetime.combine(registro.data, registro.hora_entrada)
            saida = datetime.combine(registro.data, registro.hora_saida)
            
            total_minutos = (saida - entrada).total_seconds() / 60
            
            # Subtrair almoço se houver
            if registro.hora_almoco_saida and registro.hora_almoco_retorno:
                almoco_saida = datetime.combine(registro.data, registro.hora_almoco_saida)
                almoco_retorno = datetime.combine(registro.data, registro.hora_almoco_retorno)
                minutos_almoco = (almoco_retorno - almoco_saida).total_seconds() / 60
                total_minutos -= minutos_almoco
            
            horas_trabalhadas = total_minutos / 60.0
            
            if abs((registro.horas_trabalhadas or 0) - horas_trabalhadas) > 0.01:
                print(f"   ↳ Corrigindo horas trabalhadas: {registro.horas_trabalhadas} → {horas_trabalhadas}")
                registro.horas_trabalhadas = horas_trabalhadas
        
        # 3. APLICAR REGRA: HORAS EXTRAS = HORAS TRABALHADAS
        horas_trabalhadas = float(registro.horas_trabalhadas or 0)
        
        if registro.horas_extras != horas_trabalhadas:
            print(f"   ↳ Corrigindo horas extras: {registro.horas_extras} → {horas_trabalhadas}")
            registro.horas_extras = horas_trabalhadas
        
        # 4. ZERAR TODOS OS ATRASOS
        if (registro.total_atraso_horas != 0.0 or 
            registro.total_atraso_minutos != 0 or
            registro.minutos_atraso_entrada != 0 or
            registro.minutos_atraso_saida != 0):
            
            print(f"   ↳ Zerando atrasos: {registro.total_atraso_minutos}min → 0min")
            registro.total_atraso_horas = 0.0
            registro.total_atraso_minutos = 0
            registro.minutos_atraso_entrada = 0
            registro.minutos_atraso_saida = 0
        
        # 5. GARANTIR PERCENTUAL 50%
        if registro.percentual_extras != 50.0:
            print(f"   ↳ Corrigindo percentual: {registro.percentual_extras}% → 50.0%")
            registro.percentual_extras = 50.0
        
        registros_corrigidos += 1
    
    # Salvar alterações
    if registros_corrigidos > 0:
        try:
            db.session.commit()
            print(f"✅ {registros_corrigidos} registros de sábado corrigidos com sucesso!")
            return registros_corrigidos
        except Exception as e:
            print(f"❌ Erro ao salvar: {e}")
            db.session.rollback()
            return 0
    else:
        print("ℹ️  Nenhum registro precisava de correção")
        return 0

def corrigir_registro_especifico(data_especifica=None):
    """Corrige um registro específico se fornecido"""
    if not data_especifica:
        return
    
    from datetime import date
    if isinstance(data_especifica, str):
        # Converter string para date
        data_obj = datetime.strptime(data_especifica, '%Y-%m-%d').date()
    else:
        data_obj = data_especifica
    
    print(f"🎯 CORRIGINDO REGISTRO ESPECÍFICO: {data_obj}")
    
    registro = RegistroPonto.query.filter(
        RegistroPonto.data == data_obj
    ).first()
    
    if not registro:
        print(f"❌ Registro não encontrado para {data_obj}")
        return False
    
    # Verificar se é sábado
    if data_obj.weekday() == 5:  # Python: sábado = 5
        print(f"📅 Confirmado: {data_obj} é sábado")
        
        # Aplicar todas as correções
        original_extras = registro.horas_extras
        original_atraso = registro.total_atraso_minutos
        
        # REGRA PRINCIPAL: HORAS EXTRAS = HORAS TRABALHADAS
        horas_trabalhadas = float(registro.horas_trabalhadas or 0)
        registro.horas_extras = horas_trabalhadas
        registro.total_atraso_horas = 0.0
        registro.total_atraso_minutos = 0
        registro.minutos_atraso_entrada = 0
        registro.minutos_atraso_saida = 0
        registro.percentual_extras = 50.0
        registro.tipo_registro = 'sabado_horas_extras'
        
        try:
            db.session.commit()
            print(f"✅ REGISTRO CORRIGIDO:")
            print(f"   Horas extras: {original_extras} → {registro.horas_extras}")
            print(f"   Atraso: {original_atraso}min → {registro.total_atraso_minutos}min")
            print(f"   Tipo: {registro.tipo_registro}")
            return True
        except Exception as e:
            print(f"❌ Erro ao salvar: {e}")
            db.session.rollback()
            return False
    else:
        print(f"⚠️  {data_obj} não é sábado (dia da semana: {data_obj.weekday()})")
        return False

def verificar_resultado_final():
    """Verifica se todas as correções foram aplicadas"""
    print("\n🔍 VERIFICAÇÃO FINAL...")
    
    # Buscar todos os sábados trabalhados
    registros_sabado = RegistroPonto.query.filter(
        db.extract('dow', RegistroPonto.data) == 6,
        RegistroPonto.hora_entrada.isnot(None),
        RegistroPonto.hora_saida.isnot(None)
    ).all()
    
    problemas = []
    
    for registro in registros_sabado:
        # Verificar se horas extras = horas trabalhadas
        horas_trabalhadas = float(registro.horas_trabalhadas or 0)
        horas_extras = float(registro.horas_extras or 0)
        
        if abs(horas_extras - horas_trabalhadas) > 0.01:
            problemas.append(f"{registro.data}: extras {horas_extras} ≠ trabalhadas {horas_trabalhadas}")
        
        # Verificar se atraso = 0
        if registro.total_atraso_minutos != 0:
            problemas.append(f"{registro.data}: atraso {registro.total_atraso_minutos}min (deveria ser 0)")
        
        # Verificar percentual
        if registro.percentual_extras != 50.0:
            problemas.append(f"{registro.data}: percentual {registro.percentual_extras}% (deveria ser 50%)")
    
    if problemas:
        print("❌ PROBLEMAS ENCONTRADOS:")
        for problema in problemas[:5]:
            print(f"   • {problema}")
        if len(problemas) > 5:
            print(f"   ... e mais {len(problemas) - 5} problemas")
        return False
    else:
        print("✅ TODOS OS SÁBADOS ESTÃO CORRETOS!")
        print("🎯 REGRA APLICADA: Horas extras = Horas trabalhadas, Atraso = 0")
        return True

if __name__ == "__main__":
    with app.app_context():
        print("🚀 APLICAÇÃO URGENTE DE LÓGICA DE SÁBADO")
        print("=" * 60)
        
        # 1. Aplicar correção geral
        total_corrigidos = aplicar_logica_sabado_trabalhado()
        
        # 2. Corrigir registro específico do exemplo (05/07/2025)
        from datetime import date
        corrigir_registro_especifico('2025-07-05')
        
        # 3. Verificar resultado final
        resultado_ok = verificar_resultado_final()
        
        print("\n" + "=" * 60)
        print("📋 RESUMO FINAL:")
        print(f"✅ Registros corrigidos: {total_corrigidos}")
        print(f"✅ Lógica aplicada: {'SIM' if resultado_ok else 'PARCIAL'}")
        print("🎯 REGRA GARANTIDA:")
        print("   • Sábado trabalhado: Horas extras = Horas trabalhadas")
        print("   • Sábado trabalhado: Atraso sempre = 0")
        print("   • Percentual: 50% (adicional)")
        
        if resultado_ok:
            print("\n🎉 MISSÃO CUMPRIDA!")
            print("🔄 Recarregue a página para ver as mudanças")
        else:
            print("\n⚠️  Alguns problemas persistem - verificar logs")
        
        print("=" * 60)