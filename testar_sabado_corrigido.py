#!/usr/bin/env python3
"""
🧪 TESTE: Verificar se correção de sábado foi aplicada corretamente
"""

from app import app, db
from models import RegistroPonto
from datetime import date

def testar_correcao_sabado():
    """Testa se a correção do sábado foi aplicada"""
    print("🧪 TESTE: Verificando correção de sábado 05/07/2025")
    print("=" * 50)
    
    # Buscar registro específico
    registro = RegistroPonto.query.filter(
        RegistroPonto.data == date(2025, 7, 5)
    ).first()
    
    if not registro:
        print("❌ Registro não encontrado")
        return False
    
    print(f"📊 DADOS DO REGISTRO:")
    print(f"   ID: {registro.id}")
    print(f"   Data: {registro.data}")
    print(f"   Tipo: {registro.tipo_registro}")
    print(f"   Entrada: {registro.hora_entrada}")
    print(f"   Saída: {registro.hora_saida}")
    print(f"   Horas trabalhadas: {registro.horas_trabalhadas}")
    print(f"   Horas extras: {registro.horas_extras}")
    print(f"   Atraso (horas): {registro.total_atraso_horas}")
    print(f"   Atraso (minutos): {registro.total_atraso_minutos}")
    print(f"   Percentual: {registro.percentual_extras}%")
    
    # Verificar se está correto
    resultados = []
    
    # 1. Deve ter horas extras (não deve ser None ou 0)
    if registro.horas_extras and registro.horas_extras > 0:
        print(f"✅ Horas extras: {registro.horas_extras}h (OK)")
        resultados.append(True)
    else:
        print(f"❌ Horas extras: {registro.horas_extras} (ERRO)")
        resultados.append(False)
    
    # 2. Atraso deve ser zero
    if registro.total_atraso_minutos == 0:
        print(f"✅ Atraso: {registro.total_atraso_minutos}min (OK)")
        resultados.append(True)
    else:
        print(f"❌ Atraso: {registro.total_atraso_minutos}min (ERRO)")
        resultados.append(False)
    
    # 3. Tipo deve ser sábado
    if 'sabado' in (registro.tipo_registro or ''):
        print(f"✅ Tipo: {registro.tipo_registro} (OK)")
        resultados.append(True)
    else:
        print(f"❌ Tipo: {registro.tipo_registro} (ERRO)")
        resultados.append(False)
    
    # 4. Percentual deve ser 50%
    if registro.percentual_extras == 50.0:
        print(f"✅ Percentual: {registro.percentual_extras}% (OK)")
        resultados.append(True)
    else:
        print(f"❌ Percentual: {registro.percentual_extras}% (ERRO)")
        resultados.append(False)
    
    sucesso = all(resultados)
    
    print("\n📋 RESULTADO:")
    if sucesso:
        print("🎉 TODOS OS TESTES PASSARAM!")
        print("✅ Correção aplicada com sucesso")
        print("✅ Sábado trabalhado calculado corretamente")
        return True
    else:
        print("❌ ALGUNS TESTES FALHARAM")
        print("⚠️  Correção pode não ter sido aplicada completamente")
        return False

def testar_todos_sabados():
    """Testa todos os registros de sábado"""
    print("\n🔍 TESTE: Verificando todos os sábados")
    print("=" * 50)
    
    # Buscar registros de sábado com horários
    registros_sabado = RegistroPonto.query.filter(
        db.extract('dow', RegistroPonto.data) == 6,  # PostgreSQL: sábado = 6
        RegistroPonto.hora_entrada.isnot(None),
        RegistroPonto.hora_saida.isnot(None)
    ).all()
    
    print(f"📊 Encontrados {len(registros_sabado)} sábados trabalhados")
    
    problemas = []
    
    for registro in registros_sabado:
        # Verificar se tem horas extras
        if not registro.horas_extras or registro.horas_extras == 0:
            problemas.append(f"❌ {registro.data}: sem horas extras")
        
        # Verificar se tem atraso zero
        if registro.total_atraso_minutos != 0:
            problemas.append(f"❌ {registro.data}: atraso {registro.total_atraso_minutos}min")
        
        # Verificar percentual
        if registro.percentual_extras != 50.0:
            problemas.append(f"❌ {registro.data}: percentual {registro.percentual_extras}%")
    
    if problemas:
        print("⚠️  PROBLEMAS ENCONTRADOS:")
        for problema in problemas[:5]:  # Mostrar só os primeiros 5
            print(f"   {problema}")
        if len(problemas) > 5:
            print(f"   ... e mais {len(problemas) - 5} problemas")
        return False
    else:
        print("✅ TODOS OS SÁBADOS ESTÃO CORRETOS!")
        return True

if __name__ == "__main__":
    with app.app_context():
        print("🚀 TESTE COMPLETO: Correção de Sábado")
        print("=" * 60)
        
        # Teste 1: Verificar registro específico
        teste1 = testar_correcao_sabado()
        
        # Teste 2: Verificar todos os sábados
        teste2 = testar_todos_sabados()
        
        print("\n" + "=" * 60)
        print("📋 RESUMO FINAL:")
        
        if teste1 and teste2:
            print("🎉 TODOS OS TESTES PASSARAM!")
            print("✅ Correção de sábado funcionando perfeitamente")
            print("✅ Sistema aplicando lógica correta")
        else:
            print("⚠️  ALGUNS TESTES FALHARAM")
            if not teste1:
                print("❌ Registro específico (05/07) com problemas")
            if not teste2:
                print("❌ Outros sábados com problemas")
        
        print("=" * 60)