#!/bin/bash

# SCRIPT DE BUILD PARA DEPLOY PRODUÇÃO - SIGE v8.0
# Garante que todas as mudanças sejam aplicadas no deploy

set -e

echo "🚀 SIGE v8.0 - Preparando Deploy para Produção"

# 1. Verificar estrutura de arquivos críticos
echo "📋 Verificando arquivos críticos..."
required_files=(
    "main.py"
    "views.py" 
    "models.py"
    "propostas_consolidated.py"
    "templates/dashboard.html"
    "templates/rdo_lista_unificada.html"
    "templates/base_completo.html"
    "docker-entrypoint-easypanel-final.sh"
)

for file in "${required_files[@]}"; do
    if [[ -f "$file" ]]; then
        echo "✅ $file"
    else
        echo "❌ ERRO: $file não encontrado!"
        exit 1
    fi
done

# 2. Verificar se as rotas críticas estão presentes
echo "🔍 Verificando rotas críticas..."
if grep -q "criar_proposta" propostas_consolidated.py; then
    echo "✅ Rota criar_proposta encontrada"
else
    echo "❌ ERRO: Rota criar_proposta não encontrada!"
    exit 1
fi

if grep -q "rdo_lista_unificada" views.py; then
    echo "✅ Sistema RDO unificado encontrado"
else
    echo "❌ ERRO: Sistema RDO não encontrado!"
    exit 1
fi

# 3. Verificar se o template moderno está configurado
if grep -q "base_completo.html" templates/dashboard.html; then
    echo "✅ Template moderno configurado"
else
    echo "❌ ERRO: Template moderno não configurado!"
    exit 1
fi

# 4. Gerar arquivo de configuração para produção
echo "⚙️ Gerando configuração de produção..."
cat > production_config.py << EOF
# CONFIGURAÇÃO DE PRODUÇÃO - SIGE v8.0
# Gerado automaticamente pelo build.sh

import os

# Configurações da aplicação
FLASK_ENV = 'production'
DEBUG = False
TESTING = False

# Configurações de banco
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'pool_timeout': 20,
    'max_overflow': 0
}

# Configurações de segurança
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# Configurações de aplicação
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

print("✅ Configuração de produção carregada")
EOF

# 5. Criar arquivo de verificação de deploy
echo "🔍 Criando verificação de deploy..."
cat > verify_deploy.py << EOF
#!/usr/bin/env python3
"""
Verificação de Deploy SIGE v8.0
Testa se todas as funcionalidades críticas estão funcionando
"""

import requests
import sys
import time

def test_endpoint(url, expected_status=200):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == expected_status:
            print(f"✅ {url} - Status {response.status_code}")
            return True
        else:
            print(f"❌ {url} - Status {response.status_code} (esperado {expected_status})")
            return False
    except Exception as e:
        print(f"❌ {url} - Erro: {e}")
        return False

def main():
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
    
    print(f"🔍 Testando deploy em: {base_url}")
    
    # Endpoints críticos para testar
    endpoints = [
        f"{base_url}/",
        f"{base_url}/login",
        f"{base_url}/dashboard", 
        f"{base_url}/funcionarios",
        f"{base_url}/rdos",
        f"{base_url}/propostas",
        f"{base_url}/health"
    ]
    
    success_count = 0
    for endpoint in endpoints:
        if test_endpoint(endpoint):
            success_count += 1
        time.sleep(1)
    
    print(f"\n📊 Resultado: {success_count}/{len(endpoints)} endpoints funcionando")
    
    if success_count == len(endpoints):
        print("🎉 Deploy verificado com sucesso!")
        sys.exit(0)
    else:
        print("❌ Deploy com problemas!")
        sys.exit(1)

if __name__ == "__main__":
    main()
EOF

chmod +x verify_deploy.py

# 6. Verificar Docker
echo "🐳 Verificando Dockerfile..."
if [[ -f "Dockerfile" ]]; then
    echo "✅ Dockerfile encontrado"
    
    # Verificar se o script de entrada existe
    if [[ -f "docker-entrypoint-easypanel-final.sh" ]]; then
        echo "✅ Script de entrada encontrado"
        chmod +x docker-entrypoint-easypanel-final.sh
    else
        echo "❌ Script de entrada não encontrado!"
        exit 1
    fi
else
    echo "❌ Dockerfile não encontrado!"
    exit 1
fi

# 7. Gerar resumo do build
echo "📋 Resumo do Build:"
echo "   - Arquivos verificados: ✅"
echo "   - Rotas críticas: ✅"
echo "   - Template moderno: ✅"
echo "   - Configuração de produção: ✅"
echo "   - Verificação de deploy: ✅"
echo "   - Docker configurado: ✅"

echo ""
echo "🚀 BUILD COMPLETO - PRONTO PARA DEPLOY!"
echo ""
echo "📌 Próximos passos:"
echo "   1. docker build -t sige:latest ."
echo "   2. docker run -p 5000:5000 sige:latest"
echo "   3. python verify_deploy.py http://localhost:5000"
echo ""
echo "📌 Para EasyPanel:"
echo "   1. Fazer push do código para o repositório"
echo "   2. EasyPanel fará o build automaticamente"
echo "   3. Testar com: python verify_deploy.py https://seu-dominio.com"

exit 0