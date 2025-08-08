#!/usr/bin/env python3
"""
Deploy Script: Correção da coluna foto_base64
Script para execução direta em produção
"""

import os
import sys
import subprocess
from datetime import datetime

def verificar_ambiente():
    """Verificar se estamos em produção"""
    database_url = os.environ.get('DATABASE_URL', '')
    is_production = database_url.startswith('postgres')
    
    print(f"🌍 Ambiente detectado: {'PRODUÇÃO' if is_production else 'DESENVOLVIMENTO'}")
    print(f"📊 Database URL: {database_url[:50]}..." if database_url else "📊 Database: SQLite local")
    
    return is_production

def executar_migracao_foto_base64():
    """Executa a migração da coluna foto_base64"""
    
    print("=" * 70)
    print("DEPLOY: CORREÇÃO DA COLUNA FOTO_BASE64")
    print("=" * 70)
    print(f"⏰ Iniciado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Verificar ambiente
    is_prod = verificar_ambiente()
    
    try:
        # Executar migração
        print("\n🚀 Executando migração...")
        result = subprocess.run([
            sys.executable, 
            'migrations/add_foto_base64_to_funcionario.py'
        ], capture_output=True, text=True, cwd=os.getcwd())
        
        if result.returncode == 0:
            print("✅ MIGRAÇÃO EXECUTADA COM SUCESSO!")
            print("\n📋 Output da migração:")
            print(result.stdout)
        else:
            print("❌ ERRO NA MIGRAÇÃO!")
            print("\n📋 Erro:")
            print(result.stderr)
            return False
        
        # Verificar aplicação
        print("\n🔍 Verificando aplicação...")
        from app import app, db
        from models import Funcionario
        
        with app.app_context():
            # Testar acesso à coluna
            funcionario_teste = Funcionario.query.first()
            if funcionario_teste:
                foto_base64 = getattr(funcionario_teste, 'foto_base64', None)
                print(f"✅ Acesso à coluna foto_base64: {'OK' if foto_base64 is not None else 'NULL'}")
            
            # Contar registros com foto_base64
            count_base64 = Funcionario.query.filter(Funcionario.foto_base64.isnot(None)).count()
            print(f"📊 Funcionários com foto_base64: {count_base64}")
        
        print("\n🎯 DEPLOY CONCLUÍDO COM SUCESSO!")
        return True
        
    except Exception as e:
        print(f"\n❌ ERRO NO DEPLOY: {e}")
        return False

if __name__ == "__main__":
    success = executar_migracao_foto_base64()
    print("=" * 70)
    sys.exit(0 if success else 1)