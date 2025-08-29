#!/usr/bin/env python3
"""
Script para verificar e diagnosticar problemas de conexão PostgreSQL em produção
"""

import os
import psycopg2
import time
import sys

def test_postgresql_connection():
    """Testar conexão PostgreSQL com diferentes configurações"""
    
    print("🔍 DIAGNÓSTICO CONEXÃO POSTGRESQL")
    print("=" * 50)
    
    # Configurações possíveis
    configs = [
        {
            'name': 'Via DATABASE_URL',
            'url': os.environ.get('DATABASE_URL', 'postgresql://localhost:5432/sige')
        },
        {
            'name': 'Via variáveis separadas',
            'host': os.environ.get('PGHOST', 'localhost'),
            'port': os.environ.get('PGPORT', '5432'),
            'user': os.environ.get('PGUSER', 'postgres'),
            'password': os.environ.get('PGPASSWORD', ''),
            'database': os.environ.get('PGDATABASE', 'sige')
        }
    ]
    
    # Testar cada configuração
    for i, config in enumerate(configs, 1):
        print(f"\n{i}. Testando: {config['name']}")
        print("-" * 30)
        
        try:
            if 'url' in config:
                # Conexão via URL
                conn = psycopg2.connect(config['url'])
                print(f"✅ Conectado via URL: {config['url'][:50]}...")
            else:
                # Conexão via parâmetros separados
                conn = psycopg2.connect(
                    host=config['host'],
                    port=config['port'],
                    user=config['user'],
                    password=config['password'],
                    database=config['database']
                )
                print(f"✅ Conectado: {config['user']}@{config['host']}:{config['port']}/{config['database']}")
            
            # Testar query simples
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            print(f"📊 PostgreSQL: {version[:50]}...")
            
            # Testar se tabela RDO existe
            cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'rdo';")
            rdo_exists = cursor.fetchone()[0] > 0
            print(f"🗃️ Tabela RDO: {'✅ Existe' if rdo_exists else '❌ Não existe'}")
            
            if rdo_exists:
                cursor.execute("SELECT COUNT(*) FROM rdo;")
                rdo_count = cursor.fetchone()[0]
                print(f"📊 Total RDOs: {rdo_count}")
            
            cursor.close()
            conn.close()
            print("✅ Conexão testada com sucesso!")
            return True
            
        except Exception as e:
            print(f"❌ Erro: {str(e)}")
            continue
    
    print("\n❌ NENHUMA CONFIGURAÇÃO FUNCIONOU")
    return False

def test_connection_with_retry():
    """Testar conexão com retry para aguardar PostgreSQL"""
    
    print("\n🔄 TESTE COM RETRY (aguardar PostgreSQL)")
    print("=" * 50)
    
    max_attempts = 10
    wait_time = 2
    
    for attempt in range(1, max_attempts + 1):
        print(f"Tentativa {attempt}/{max_attempts}...")
        
        try:
            database_url = os.environ.get('DATABASE_URL', 'postgresql://localhost:5432/sige')
            conn = psycopg2.connect(database_url)
            
            cursor = conn.cursor()
            cursor.execute("SELECT 1;")
            result = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            print(f"✅ Conectado na tentativa {attempt}!")
            return True
            
        except Exception as e:
            print(f"❌ Tentativa {attempt} falhou: {str(e)}")
            if attempt < max_attempts:
                print(f"⏳ Aguardando {wait_time}s...")
                time.sleep(wait_time)
                wait_time += 1  # Backoff
    
    print(f"❌ Falha após {max_attempts} tentativas")
    return False

def show_environment_vars():
    """Mostrar variáveis de ambiente relacionadas ao PostgreSQL"""
    
    print("\n🔧 VARIÁVEIS DE AMBIENTE")
    print("=" * 50)
    
    pg_vars = [
        'DATABASE_URL', 'PGHOST', 'PGPORT', 'PGUSER', 
        'PGPASSWORD', 'PGDATABASE', 'DB_HOST', 'DB_PORT', 
        'DB_USER', 'DB_PASSWORD', 'DB_NAME'
    ]
    
    for var in pg_vars:
        value = os.environ.get(var, 'não definida')
        if 'PASSWORD' in var and value != 'não definida':
            masked_value = '*' * len(value)
            print(f"   {var}: {masked_value}")
        else:
            print(f"   {var}: {value}")

def generate_docker_compose():
    """Gerar docker-compose.yml para teste local"""
    
    print("\n📝 DOCKER-COMPOSE PARA TESTE")
    print("=" * 50)
    
    compose_content = '''version: '3.8'

services:
  postgres:
    image: postgres:13
    container_name: sige-postgres-test
    environment:
      POSTGRES_DB: sige
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password123
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  sige:
    build: .
    container_name: sige-app-test
    environment:
      DATABASE_URL: postgresql://postgres:password123@postgres:5432/sige
      SESSION_SECRET: test-secret-key
      FLASK_ENV: development
    ports:
      - "5000:5000"
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - .:/app
    command: gunicorn --bind 0.0.0.0:5000 --reload main:app

volumes:
  postgres_data:
'''
    
    with open('docker-compose-test.yml', 'w') as f:
        f.write(compose_content)
    
    print("✅ Arquivo criado: docker-compose-test.yml")
    print("\nPara testar:")
    print("  docker-compose -f docker-compose-test.yml up")

def main():
    print("🚨 DIAGNÓSTICO COMPLETO POSTGRESQL - PRODUÇÃO")
    print("=" * 60)
    
    # Mostrar variáveis de ambiente
    show_environment_vars()
    
    # Testar conexões
    connection_ok = test_postgresql_connection()
    
    if not connection_ok:
        # Tentar com retry
        connection_ok = test_connection_with_retry()
    
    # Gerar arquivo de teste
    generate_docker_compose()
    
    print("\n📋 RESUMO DO DIAGNÓSTICO:")
    print("=" * 30)
    
    if connection_ok:
        print("✅ PostgreSQL: Funcionando")
        print("✅ Problema: Provavelmente na aplicação")
        print("\n🎯 PRÓXIMOS PASSOS:")
        print("1. Verificar logs da aplicação")
        print("2. Testar rotas individuais")
        print("3. Verificar health check")
    else:
        print("❌ PostgreSQL: Não conecta")
        print("❌ Problema: Configuração de banco")
        print("\n🎯 PRÓXIMOS PASSOS:")
        print("1. Verificar se PostgreSQL está rodando")
        print("2. Corrigir variáveis de ambiente")
        print("3. Testar com docker-compose-test.yml")
    
    print(f"\n🕒 Diagnóstico concluído: {time.strftime('%H:%M:%S')}")

if __name__ == "__main__":
    main()