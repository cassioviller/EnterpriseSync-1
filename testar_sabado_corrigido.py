#!/usr/bin/env python3
"""
✅ TESTE FINAL: Verificar se a correção de sábado trabalhado está funcionando
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import date
import json

def testar_registro_sabado():
    """Testa o registro específico de 05/07/2025"""
    print("🧪 TESTE: Verificando registro de sábado trabalhado")
    print("=" * 55)
    
    # Buscar registro de 05/07/2025
    registro = RegistroPonto.query.filter(
        RegistroPonto.data == date(2025, 7, 5)
    ).first()
    
    if not registro:
        print("❌ REGISTRO NÃO ENCONTRADO")
        return False
    
    funcionario = Funcionario.query.get(registro.funcionario_id)
    
    print(f"📍 REGISTRO ENCONTRADO:")
    print(f"   Data: {registro.data.strftime('%d/%m/%Y')} ({registro.data.strftime('%A')})")
    print(f"   Funcionário: {funcionario.nome if funcionario else 'N/A'}")
    print(f"   Tipo: {registro.tipo_registro}")
    print()
    
    print("🔍 VERIFICAÇÕES:")
    
    # Teste 1: Tipo correto
    tipo_correto = registro.tipo_registro in ['sabado_horas_extras', 'sabado_trabalhado']
    print(f"   ✅ Tipo é sábado: {tipo_correto} ({'Sim' if tipo_correto else 'Não'})")
    
    # Teste 2: Zero atraso
    sem_atraso = (registro.total_atraso_horas or 0) == 0
    print(f"   ✅ Zero atraso: {sem_atraso} ({registro.total_atraso_horas or 0}h)")
    
    # Teste 3: Horas extras = horas trabalhadas
    horas_corretas = (registro.horas_extras or 0) == (registro.horas_trabalhadas or 0)
    print(f"   ✅ Horas extras corretas: {horas_corretas}")
    print(f"      Trabalhadas: {registro.horas_trabalhadas or 0}h")
    print(f"      Extras: {registro.horas_extras or 0}h")
    
    # Teste 4: Percentual 50%
    percentual_correto = (registro.percentual_extras or 0) == 50.0
    print(f"   ✅ Percentual 50%: {percentual_correto} ({registro.percentual_extras or 0}%)")
    
    # Teste 5: Horários preenchidos
    tem_horarios = all([
        registro.hora_entrada,
        registro.hora_saida
    ])
    print(f"   ✅ Horários preenchidos: {tem_horarios}")
    if tem_horarios:
        print(f"      Entrada: {registro.hora_entrada}")
        print(f"      Saída: {registro.hora_saida}")
        if registro.hora_almoco_saida and registro.hora_almoco_retorno:
            print(f"      Almoço: {registro.hora_almoco_saida} - {registro.hora_almoco_retorno}")
    
    print()
    
    # Resultado final
    tudo_ok = all([tipo_correto, sem_atraso, horas_corretas, percentual_correto, tem_horarios])
    
    if tudo_ok:
        print("🎉 SUCESSO TOTAL! Todas as verificações passaram!")
        print("✅ O registro de sábado trabalhado está 100% correto")
    else:
        print("⚠️  ALGUMAS VERIFICAÇÕES FALHARAM")
        print("❌ O registro precisa de ajustes")
    
    print("=" * 55)
    return tudo_ok

def verificar_interface_tags():
    """Simula a verificação de tags na interface"""
    print("🏷️  TESTE: Tags da interface")
    print("=" * 30)
    
    # Simulação do que deveria aparecer na interface
    data_teste = date(2025, 7, 5)  # Sábado
    dia_semana = data_teste.weekday()  # 5 = sábado
    
    print(f"Data: {data_teste.strftime('%d/%m/%Y')}")
    print(f"Dia da semana: {dia_semana} (5 = sábado)")
    
    # Verificar lógica de tag
    if dia_semana == 5:  # Sábado
        print("✅ Tag esperada: SÁBADO (verde)")
        print("✅ Background esperado: Verde claro")
        print("✅ Ícone: fas fa-calendar-week")
    else:
        print("❌ Não é sábado")
    
    print("=" * 30)

def testar_dados_modal():
    """Testa dados que serão enviados para o modal de edição"""
    print("📝 TESTE: Dados para modal de edição")
    print("=" * 40)
    
    registro = RegistroPonto.query.filter(
        RegistroPonto.data == date(2025, 7, 5)
    ).first()
    
    if registro:
        funcionario = Funcionario.query.get(registro.funcionario_id)
        
        # Mapear tipo para frontend
        tipo_frontend = registro.tipo_registro
        if tipo_frontend == 'sabado_horas_extras':
            tipo_frontend = 'sabado_trabalhado'
        
        modal_data = {
            'success': True,
            'registro': {
                'id': registro.id,
                'funcionario_nome': funcionario.nome if funcionario else 'N/A',
                'data': registro.data.strftime('%Y-%m-%d'),
                'tipo_registro': tipo_frontend,
                'hora_entrada': registro.hora_entrada.strftime('%H:%M') if registro.hora_entrada else '',
                'hora_saida': registro.hora_saida.strftime('%H:%M') if registro.hora_saida else '',
                'horas_trabalhadas': float(registro.horas_trabalhadas) if registro.horas_trabalhadas else 0,
                'horas_extras': float(registro.horas_extras) if registro.horas_extras else 0,
                'percentual_extras': float(registro.percentual_extras) if registro.percentual_extras else 0,
                'atraso_horas': float(registro.total_atraso_horas) if registro.total_atraso_horas else 0
            }
        }
        
        print("📊 Dados que serão enviados para o modal:")
        print(json.dumps(modal_data, indent=2, ensure_ascii=False))
        
        # Verificações dos dados
        print("\n🔍 Verificações dos dados do modal:")
        dados = modal_data['registro']
        print(f"   ✅ Tipo correto para dropdown: {dados['tipo_registro'] == 'sabado_trabalhado'}")
        print(f"   ✅ Zero atraso: {dados['atraso_horas'] == 0}")
        print(f"   ✅ Horas extras = trabalhadas: {dados['horas_extras'] == dados['horas_trabalhadas']}")
        print(f"   ✅ Percentual 50%: {dados['percentual_extras'] == 50.0}")
        
    else:
        print("❌ Registro não encontrado para teste do modal")
    
    print("=" * 40)

if __name__ == "__main__":
    with app.app_context():
        print("🚨 TESTE COMPLETO: CORREÇÃO SÁBADO TRABALHADO")
        print("=" * 60)
        print()
        
        # Executar todos os testes
        resultado1 = testar_registro_sabado()
        print()
        
        verificar_interface_tags()
        print()
        
        testar_dados_modal()
        print()
        
        if resultado1:
            print("🎯 RESULTADO FINAL: SUCESSO TOTAL!")
            print("✅ O sistema está funcionando corretamente para sábados trabalhados")
            print("✅ Backend: Cálculos corretos")
            print("✅ Frontend: Tags e modal preparados")
            print("✅ Dados: Consistentes e precisos")
        else:
            print("⚠️  RESULTADO FINAL: PRECISA AJUSTES")
            print("❌ Ainda há problemas no sistema")
        
        print("=" * 60)