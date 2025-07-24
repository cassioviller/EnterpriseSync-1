#!/usr/bin/env python3
"""
Teste de saúde da aplicação Docker
SIGE v8.0 - Sistema Integrado de Gestão Empresarial
"""

from werkzeug.security import generate_password_hash, check_password_hash
import sys

def test_password():
    """Testa se a senha está correta"""
    # Hash atual do banco
    hash_banco = "scrypt:32768:8:1$nm7UZN6yEl8eY3tJ$4efb2fec46530daa51f5b0f734d7b7993fdbfa1a2758e5addd6a432158d97d27afa88a05f2ef40be21a917d1137cf2c3c465b8b6b83b93dcb7a963df5663ba8a"
    
    # Senhas para testar
    senhas = ['cassio123', 'admin123', 'password', '123456']
    
    print("🔍 Testando senhas contra hash do banco...")
    print(f"Hash: {hash_banco[:50]}...")
    
    for senha in senhas:
        resultado = check_password_hash(hash_banco, senha)
        status = "✅" if resultado else "❌"
        print(f"{status} Senha '{senha}': {resultado}")
    
    # Gerar novo hash para cassio123
    print("\n🔧 Gerando novo hash para senha 'cassio123':")
    novo_hash = generate_password_hash('cassio123')
    print(f"Novo hash: {novo_hash}")
    
    # Testar o novo hash
    teste_novo = check_password_hash(novo_hash, 'cassio123')
    print(f"✅ Teste do novo hash: {teste_novo}")
    
    return novo_hash

if __name__ == "__main__":
    novo_hash = test_password()
    print(f"\n🎯 Use este comando SQL para corrigir:")
    print(f"UPDATE usuario SET password_hash = '{novo_hash}' WHERE username = 'axiom';")