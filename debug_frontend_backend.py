#!/usr/bin/env python3
"""
Script para debugar a comunicação frontend-backend
"""

from app import app, db
from models import *
from datetime import datetime, date
import json

def analisar_mapeamento_campos():
    """Analisar mapeamento de campos frontend vs backend"""
    
    print("🔍 ANÁLISE DE MAPEAMENTO FRONTEND ↔ BACKEND")
    print("=" * 60)
    
    print("📝 CAMPOS DO FORMULÁRIO HTML:")
    print("   funcionario_id_modal → funcionario_id")
    print("   data_modal → data")
    print("   tipo_registro_modal → tipo_registro")
    print("   entrada_modal → entrada")
    print("   saida_almoco_modal → saida_almoco")
    print("   retorno_almoco_modal → retorno_almoco")
    print("   saida_modal → saida")
    print("   observacoes_modal → observacoes")
    
    print("\n📝 CAMPOS ESPERADOS PELO BACKEND:")
    print("   funcionario_id ✅")
    print("   data ✅")
    print("   tipo_registro ✅")
    print("   entrada ✅")
    print("   saida_almoco ✅")
    print("   retorno_almoco ✅")
    print("   saida ✅")
    print("   observacoes ✅")
    
    print("\n⚠️ POSSÍVEIS INCOMPATIBILIDADES:")
    print("   1. Campos com sufixo '_modal' podem não estar sendo enviados")
    print("   2. FormData pode estar com nomes errados")
    print("   3. JavaScript pode estar renomeando campos")

def verificar_logs_sistema():
    """Verificar logs do sistema para erros"""
    
    with app.app_context():
        print("\n📋 VERIFICAÇÃO DE LOGS")
        print("=" * 60)
        
        # Últimos registros criados
        ultimos_registros = RegistroPonto.query.order_by(
            RegistroPonto.id.desc()
        ).limit(5).all()
        
        print("🕒 ÚLTIMOS 5 REGISTROS CRIADOS:")
        for reg in ultimos_registros:
            funcionario = Funcionario.query.get(reg.funcionario_id)
            print(f"   ID {reg.id}: {reg.data.strftime('%d/%m')} - {funcionario.nome if funcionario else 'N/A'} - {reg.tipo_registro}")
        
        # Verificar registros específicos do usuário
        registros_funcionario_14 = RegistroPonto.query.filter_by(
            funcionario_id=14
        ).order_by(RegistroPonto.data.desc()).limit(10).all()
        
        print(f"\n👤 ÚLTIMOS 10 REGISTROS DO FUNCIONÁRIO ID 14:")
        for reg in registros_funcionario_14:
            print(f"   {reg.data.strftime('%d/%m/%Y')}: {reg.tipo_registro}")

def simular_ajax_request():
    """Simular requisição AJAX do frontend"""
    
    print("\n🌐 SIMULAÇÃO DE REQUISIÇÃO AJAX")
    print("=" * 60)
    
    # Dados como o FormData enviaria
    form_data = {
        'funcionario_id': '14',
        'data': '2025-07-05',
        'tipo_registro': 'sabado_trabalhado',
        'entrada': '07:00',
        'saida_almoco': '12:00',
        'retorno_almoco': '13:00',
        'saida': '17:00',
        'observacoes': 'Teste AJAX manual'
    }
    
    print("📤 DADOS ENVIADOS:")
    print(json.dumps(form_data, indent=2))
    
    with app.test_client() as client:
        # Tentar login primeiro
        login_response = client.post('/login', data={
            'email': 'estruturas.vale@hotmail.com',  # Email do admin
            'password': 'admin123'
        }, follow_redirects=True)
        
        print(f"\n🔐 LOGIN STATUS: {login_response.status_code}")
        
        # Tentar criar registro
        response = client.post('/ponto/registro', 
                             data=form_data,
                             content_type='application/x-www-form-urlencoded')
        
        print(f"📥 RESPONSE STATUS: {response.status_code}")
        print(f"📥 RESPONSE HEADERS: {dict(response.headers)}")
        
        if response.data:
            try:
                response_data = response.get_json()
                print(f"📥 RESPONSE JSON: {response_data}")
            except:
                print(f"📥 RESPONSE TEXT: {response.data.decode()[:200]}...")
        
        return response.status_code == 200

def testar_diferentes_endpoints():
    """Testar diferentes endpoints disponíveis"""
    
    print("\n🎯 TESTE DE ENDPOINTS DISPONÍVEIS")
    print("=" * 60)
    
    endpoints = [
        '/ponto/registro',
        '/novo-ponto',
        '/funcionarios/ponto/novo'
    ]
    
    form_data = {
        'funcionario_id': '14',
        'data_ponto': '2025-07-05',  # Tentar campo alternativo
        'data': '2025-07-05',
        'tipo_lancamento': 'sabado_trabalhado',  # Tentar campo alternativo
        'tipo_registro': 'sabado_trabalhado',
        'hora_entrada_ponto': '07:00',  # Tentar campo alternativo
        'entrada': '07:00',
        'hora_saida_ponto': '17:00',
        'saida': '17:00',
        'observacoes_ponto': 'Teste multi-endpoint',
        'observacoes': 'Teste multi-endpoint'
    }
    
    with app.test_client() as client:
        # Login
        client.post('/login', data={
            'email': 'estruturas.vale@hotmail.com',
            'password': 'admin123'
        })
        
        for endpoint in endpoints:
            print(f"\n🎯 Testando: {endpoint}")
            response = client.post(endpoint, data=form_data)
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.get_json()
                    if data and data.get('success'):
                        print(f"   ✅ Sucesso: {data.get('message', 'OK')}")
                        return endpoint
                    else:
                        print(f"   ❌ Erro: {data.get('error', 'Unknown')}")
                except:
                    print(f"   📄 HTML Response (redirect?)")
            else:
                print(f"   ❌ Falha HTTP: {response.status_code}")
    
    return None

def identificar_problema_real():
    """Identificar o problema real"""
    
    with app.app_context():
        print("\n🔍 IDENTIFICAÇÃO DO PROBLEMA REAL")
        print("=" * 60)
        
        # 1. Verificar se admin existe e está ativo
        admin = Usuario.query.filter_by(
            email='estruturas.vale@hotmail.com',
            tipo_usuario=TipoUsuario.ADMIN
        ).first()
        
        print(f"1. Admin existe: {'✅' if admin else '❌'}")
        if admin:
            print(f"   ID: {admin.id}")
            print(f"   Ativo: {admin.ativo}")
        
        # 2. Verificar se funcionário ID 14 pertence ao admin
        funcionario = Funcionario.query.get(14)
        print(f"2. Funcionário 14 existe: {'✅' if funcionario else '❌'}")
        if funcionario:
            print(f"   Nome: {funcionario.nome}")
            print(f"   Admin ID: {funcionario.admin_id}")
            print(f"   Ativo: {funcionario.ativo}")
            
            if admin and funcionario.admin_id == admin.id:
                print("   ✅ Funcionário pertence ao admin")
            else:
                print("   ❌ Funcionário NÃO pertence ao admin")
        
        # 3. Verificar registros existentes para 05/07
        registros_05_07 = RegistroPonto.query.filter_by(
            funcionario_id=14,
            data=date(2025, 7, 5)
        ).all()
        
        print(f"3. Registros 05/07 existentes: {len(registros_05_07)}")
        for reg in registros_05_07:
            print(f"   ID {reg.id}: {reg.tipo_registro}")
        
        # 4. Testar criação manual
        if len(registros_05_07) == 0:
            try:
                teste_registro = RegistroPonto(
                    funcionario_id=14,
                    data=date(2025, 7, 5),
                    tipo_registro='sabado_trabalhado',
                    hora_entrada=datetime.strptime('07:00', '%H:%M').time(),
                    hora_saida=datetime.strptime('17:00', '%H:%M').time(),
                    observacoes='Teste identificação problema'
                )
                
                db.session.add(teste_registro)
                db.session.commit()
                
                print("4. Criação manual: ✅ SUCESSO")
                print(f"   Novo ID: {teste_registro.id}")
                
                return "BACKEND_OK"
                
            except Exception as e:
                db.session.rollback()
                print(f"4. Criação manual: ❌ FALHA - {e}")
                return "BACKEND_ERROR"
        else:
            print("4. Criação manual: ⏭️ Pulado (já existe)")
            return "ALREADY_EXISTS"

if __name__ == "__main__":
    print("🔧 DEBUG FRONTEND ↔ BACKEND")
    print(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print()
    
    # 1. Analisar mapeamento
    analisar_mapeamento_campos()
    
    # 2. Verificar logs
    verificar_logs_sistema()
    
    # 3. Simular AJAX
    ajax_ok = simular_ajax_request()
    
    # 4. Testar endpoints
    endpoint_funcional = testar_diferentes_endpoints()
    
    # 5. Identificar problema real
    status_problema = identificar_problema_real()
    
    print("\n" + "=" * 60)
    print("📊 DIAGNÓSTICO FINAL:")
    print(f"   AJAX funcionando: {'✅' if ajax_ok else '❌'}")
    print(f"   Endpoint funcional: {endpoint_funcional or '❌ Nenhum'}")
    print(f"   Status do problema: {status_problema}")
    
    if endpoint_funcional:
        print(f"\n✅ SOLUÇÃO: Use endpoint {endpoint_funcional}")
        print("📋 PRÓXIMOS PASSOS:")
        print("   1. Verificar se frontend está usando endpoint correto")
        print("   2. Verificar autenticação no frontend")
        print("   3. Verificar mapeamento de campos")
    elif status_problema == "BACKEND_OK":
        print("\n✅ BACKEND FUNCIONANDO - Problema no frontend")
    else:
        print("\n❌ PROBLEMA NO BACKEND - Verificar configuração")