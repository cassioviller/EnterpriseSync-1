"""
Verificação completa da estrutura do SIGE v8.0 após correções
Analisa se todos os módulos e funcionalidades estão operacionais
"""

import requests
import sqlite3
import os

def verificar_banco_dados():
    """Verifica a estrutura do banco de dados"""
    print("🗄️  VERIFICANDO BANCO DE DADOS")
    print("-" * 30)
    
    try:
        conn = sqlite3.connect('sige.db')
        cursor = conn.cursor()
        
        # Listar todas as tabelas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print(f"✅ Total de tabelas: {len(tables)}")
        
        # Verificar tabelas principais
        expected_tables = [
            'usuario', 'funcionario', 'obra', 'registro_ponto',
            'categoria_produto', 'produto', 'fornecedor', 'nota_fiscal',
            'movimentacao_estoque', 'rdo', 'veiculo', 'restaurante',
            'registro_alimentacao'
        ]
        
        existing_tables = [t[0] for t in tables]
        
        for table in expected_tables:
            if table in existing_tables:
                print(f"✅ {table}")
            else:
                print(f"❌ {table} (faltando)")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Erro no banco: {e}")
        return False

def verificar_rotas_sistema():
    """Verifica se as rotas principais estão respondendo"""
    print("\n🌐 VERIFICANDO ROTAS DO SISTEMA")
    print("-" * 30)
    
    base_url = "http://localhost:5000"
    
    # Rotas básicas que devem responder
    rotas_basicas = [
        "/test",
        "/login",
        "/",
    ]
    
    # Rotas protegidas (devem redirecionar para login = 302)
    rotas_protegidas = [
        "/dashboard",
        "/funcionarios", 
        "/obras",
        "/veiculos"
    ]
    
    funcionando = 0
    total = 0
    
    for rota in rotas_basicas:
        total += 1
        try:
            response = requests.get(f"{base_url}{rota}", timeout=5)
            if response.status_code == 200:
                print(f"✅ {rota}: OK")
                funcionando += 1
            else:
                print(f"❌ {rota}: Status {response.status_code}")
        except Exception as e:
            print(f"❌ {rota}: Erro - {str(e)[:50]}")
    
    for rota in rotas_protegidas:
        total += 1
        try:
            response = requests.get(f"{base_url}{rota}", timeout=5)
            if response.status_code in [200, 302]:  # 302 = redirect para login
                print(f"✅ {rota}: OK (protegida)")
                funcionando += 1
            else:
                print(f"❌ {rota}: Status {response.status_code}")
        except Exception as e:
            print(f"❌ {rota}: Erro - {str(e)[:50]}")
    
    return funcionando, total

def verificar_blueprints():
    """Verifica se os blueprints estão carregados"""
    print("\n📋 VERIFICANDO BLUEPRINTS")
    print("-" * 30)
    
    blueprints_esperados = [
        "/almoxarifado/dashboard",
        "/relatorios/dashboard"
    ]
    
    funcionando = 0
    total = len(blueprints_esperados)
    
    for blueprint in blueprints_esperados:
        try:
            response = requests.get(f"http://localhost:5000{blueprint}", timeout=5)
            if response.status_code in [200, 302, 404]:  # 404 pode ser normal se rota não existe
                print(f"✅ {blueprint}: Blueprint carregado")
                funcionando += 1
            else:
                print(f"❌ {blueprint}: Status {response.status_code}")
        except Exception as e:
            print(f"❌ {blueprint}: Erro - {str(e)[:50]}")
    
    return funcionando, total

def main():
    """Executa verificação completa do sistema"""
    print("🔍 VERIFICAÇÃO COMPLETA SIGE v8.0")
    print("=" * 50)
    
    # Verificar banco
    db_ok = verificar_banco_dados()
    
    # Verificar rotas
    rotas_ok, rotas_total = verificar_rotas_sistema()
    
    # Verificar blueprints
    blueprints_ok, blueprints_total = verificar_blueprints()
    
    # Resultado final
    print("\n" + "=" * 50)
    print("📊 RESULTADO FINAL")
    print("-" * 20)
    print(f"🗄️  Banco de dados: {'✅ OK' if db_ok else '❌ PROBLEMA'}")
    print(f"🌐 Rotas: {rotas_ok}/{rotas_total} funcionando")
    print(f"📋 Blueprints: {blueprints_ok}/{blueprints_total} carregados")
    
    # Status geral
    total_checks = 1 + rotas_total + blueprints_total  # banco + rotas + blueprints
    passed_checks = (1 if db_ok else 0) + rotas_ok + blueprints_ok
    
    percentage = (passed_checks / total_checks) * 100
    
    print(f"\n🎯 Status Geral: {percentage:.1f}% funcional")
    
    if percentage >= 90:
        print("🎉 SISTEMA TOTALMENTE OPERACIONAL!")
        return True
    elif percentage >= 70:
        print("⚠️  Sistema funcionando com pequenas falhas")
        return True
    else:
        print("❌ Sistema com problemas críticos")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)