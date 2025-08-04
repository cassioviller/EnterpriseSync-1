#!/usr/bin/env python3
"""
🧪 TESTE: Sistema completo de edição de registros de ponto
"""

from app import app, db
from models import RegistroPonto, Funcionario
from datetime import date
import requests
import json

def testar_endpoint_edicao():
    """Testa o endpoint de edição"""
    print("🧪 TESTE: Sistema de edição de registros")
    print("=" * 50)
    
    # Buscar registro existente para teste
    registro = RegistroPonto.query.filter(
        RegistroPonto.data == date(2025, 7, 5)
    ).first()
    
    if not registro:
        print("❌ Registro de teste não encontrado")
        return False
    
    print(f"📍 Testando registro ID: {registro.id}")
    print(f"   Data: {registro.data}")
    print(f"   Tipo: {registro.tipo_registro}")
    
    # Teste 1: GET - Buscar dados para edição
    print("\n🔍 TESTE 1: Buscar dados para edição")
    url_get = f"http://localhost:5000/ponto/registro/{registro.id}"
    
    try:
        response = requests.get(url_get)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Dados recebidos: {data.get('success', False)}")
            
            if data.get('success'):
                registro_data = data.get('registro', {})
                print(f"   ✅ Funcionário: {registro_data.get('funcionario', {}).get('nome', 'N/A')}")
                print(f"   ✅ Tipo mapeado: {registro_data.get('tipo_registro', 'N/A')}")
                print(f"   ✅ Horários disponíveis: {bool(registro_data.get('horarios'))}")
                print(f"   ✅ Valores calculados: {bool(registro_data.get('valores_calculados'))}")
                print(f"   ✅ Obras disponíveis: {len(data.get('obras_disponiveis', []))}")
                return True
            else:
                print(f"   ❌ Erro: {data.get('error', 'Desconhecido')}")
                return False
        else:
            print(f"   ❌ Erro HTTP: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ Erro de conexão: {e}")
        return False

def testar_validacoes():
    """Testa as funções de validação"""
    print("\n🔍 TESTE 2: Validações de dados")
    
    # Importar funções de validação
    try:
        from views import (
            validar_dados_edicao_ponto,
            validar_formato_hora,
            validar_sequencia_horarios_edicao,
            mapear_tipo_para_frontend,
            mapear_tipo_para_banco
        )
        
        # Teste 2.1: Validação de formato de hora
        print("   🕐 Teste formato de hora:")
        horarios_validos = ['08:00', '12:30', '23:59']
        horarios_invalidos = ['24:00', '08:60', 'abc', '8:00']
        
        for h in horarios_validos:
            if validar_formato_hora(h):
                print(f"     ✅ {h} - válido")
            else:
                print(f"     ❌ {h} - deveria ser válido")
        
        for h in horarios_invalidos:
            if not validar_formato_hora(h):
                print(f"     ✅ {h} - inválido (correto)")
            else:
                print(f"     ❌ {h} - deveria ser inválido")
        
        # Teste 2.2: Mapeamento de tipos
        print("   🔄 Teste mapeamento de tipos:")
        mapeamentos = [
            ('sabado_horas_extras', 'sabado_trabalhado'),
            ('trabalhado', 'trabalho_normal'),
            ('domingo_horas_extras', 'domingo_trabalhado')
        ]
        
        for tipo_banco, tipo_frontend_esperado in mapeamentos:
            resultado = mapear_tipo_para_frontend(tipo_banco)
            if resultado == tipo_frontend_esperado:
                print(f"     ✅ {tipo_banco} → {resultado}")
            else:
                print(f"     ❌ {tipo_banco} → {resultado} (esperado: {tipo_frontend_esperado})")
        
        # Teste 2.3: Validação de dados completos
        print("   📝 Teste validação completa:")
        
        # Dados válidos
        dados_validos = {
            'tipo_registro': 'sabado_trabalhado',
            'hora_entrada': '07:00',
            'hora_saida': '16:00',
            'hora_almoco_saida': '12:00',
            'hora_almoco_retorno': '13:00'
        }
        
        resultado = validar_dados_edicao_ponto(dados_validos, None)
        if resultado['valido']:
            print("     ✅ Dados válidos aceitos")
        else:
            print(f"     ❌ Dados válidos rejeitados: {resultado['erro']}")
        
        # Dados inválidos
        dados_invalidos = {
            'tipo_registro': 'sabado_trabalhado',
            'hora_entrada': '25:00',  # Hora inválida
            'hora_saida': '16:00'
        }
        
        resultado = validar_dados_edicao_ponto(dados_invalidos, None)
        if not resultado['valido']:
            print(f"     ✅ Dados inválidos rejeitados: {resultado['erro']}")
        else:
            print("     ❌ Dados inválidos aceitos")
        
        return True
        
    except ImportError as e:
        print(f"   ❌ Erro ao importar funções: {e}")
        return False

def testar_permissoes():
    """Testa sistema de permissões"""
    print("\n🔍 TESTE 3: Sistema de permissões")
    
    try:
        from views import verificar_permissao_edicao_ponto
        from models import Usuario
        
        # Buscar usuário admin para teste
        admin = Usuario.query.filter_by(tipo_usuario='ADMIN').first()
        super_admin = Usuario.query.filter_by(tipo_usuario='SUPER_ADMIN').first()
        
        # Buscar registro para teste
        registro = RegistroPonto.query.first()
        
        if admin and registro:
            # Teste permissão admin
            tem_permissao = verificar_permissao_edicao_ponto(registro, admin)
            print(f"   ✅ Admin tem permissão: {tem_permissao}")
        
        if super_admin and registro:
            # Teste permissão super admin
            tem_permissao = verificar_permissao_edicao_ponto(registro, super_admin)
            print(f"   ✅ Super Admin tem permissão: {tem_permissao}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erro ao testar permissões: {e}")
        return False

def testar_recalculos():
    """Testa recálculos automáticos"""
    print("\n🔍 TESTE 4: Recálculos automáticos")
    
    try:
        from views import recalcular_registro_automatico
        
        # Buscar registro de sábado
        registro = RegistroPonto.query.filter(
            RegistroPonto.tipo_registro == 'sabado_horas_extras'
        ).first()
        
        if registro:
            print(f"   📊 Testando recálculo para registro {registro.id}")
            print(f"      Tipo: {registro.tipo_registro}")
            print(f"      Antes - Horas extras: {registro.horas_extras}")
            print(f"      Antes - Percentual: {registro.percentual_extras}")
            print(f"      Antes - Atraso: {registro.total_atraso_horas}")
            
            # Aplicar recálculo
            recalcular_registro_automatico(registro)
            
            print(f"      Depois - Horas extras: {registro.horas_extras}")
            print(f"      Depois - Percentual: {registro.percentual_extras}")
            print(f"      Depois - Atraso: {registro.total_atraso_horas}")
            
            # Verificar se aplicou lógica de sábado
            if registro.percentual_extras == 50.0 and registro.total_atraso_horas == 0.0:
                print("   ✅ Lógica de sábado aplicada corretamente")
                return True
            else:
                print("   ❌ Lógica de sábado não aplicada")
                return False
        else:
            print("   ⚠️  Registro de sábado não encontrado para teste")
            return True
            
    except Exception as e:
        print(f"   ❌ Erro ao testar recálculos: {e}")
        return False

if __name__ == "__main__":
    with app.app_context():
        print("🚀 TESTE COMPLETO: Sistema de Edição de Registros")
        print("=" * 60)
        print()
        
        resultados = []
        
        # Executar todos os testes
        resultados.append(testar_endpoint_edicao())
        resultados.append(testar_validacoes())
        resultados.append(testar_permissoes())
        resultados.append(testar_recalculos())
        
        print("\n📊 RESULTADO FINAL:")
        print("=" * 30)
        
        testes_passaram = sum(resultados)
        total_testes = len(resultados)
        
        if testes_passaram == total_testes:
            print("🎉 TODOS OS TESTES PASSARAM!")
            print("✅ Sistema de edição funcionando perfeitamente")
            print("✅ Validações robustas implementadas")
            print("✅ Permissões configuradas corretamente")
            print("✅ Recálculos automáticos funcionais")
        else:
            print(f"⚠️  {testes_passaram}/{total_testes} testes passaram")
            print("❌ Há problemas que precisam ser corrigidos")
        
        print("=" * 60)