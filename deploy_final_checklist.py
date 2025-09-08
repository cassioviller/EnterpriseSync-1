#!/usr/bin/env python3
"""
CHECKLIST FINAL PARA DEPLOY DE PRODUÇÃO
Verifica se todos os arquivos estão corretos antes do deploy
Data: 08/09/2025 - 19:10
"""

import os
import sys
import re

def verificar_arquivo(nome_arquivo, verificacoes):
    """Verifica se um arquivo contém as strings necessárias"""
    print(f"\n🔍 VERIFICANDO: {nome_arquivo}")
    
    if not os.path.exists(nome_arquivo):
        print(f"❌ Arquivo {nome_arquivo} não encontrado!")
        return False
    
    with open(nome_arquivo, 'r', encoding='utf-8') as f:
        conteudo = f.read()
    
    todas_ok = True
    for desc, pattern in verificacoes.items():
        if pattern in conteudo:
            print(f"✅ {desc}")
        else:
            print(f"❌ {desc} - NÃO ENCONTRADO")
            todas_ok = False
    
    return todas_ok

def main():
    print("🚢 CHECKLIST FINAL - DEPLOY COMPLETO DE PRODUÇÃO")
    print("=" * 60)
    
    tudo_ok = True
    
    # 1. Verificar views.py
    verificacoes_views = {
        "Mapeamento ID 150": "'150': '1. Detalhamento do projeto'",
        "Mapeamento ID 151": "'151': '2. Seleção de materiais'",
        "Mapeamento ID 165": "'165': '16. Entrega e aceitação'",
        "Fallback de emergência": "mapeamento_emergencia",
        "Logger de correção": "FALLBACK: Mapeamento PRODUÇÃO usado"
    }
    
    if not verificar_arquivo("views.py", verificacoes_views):
        tudo_ok = False
    
    # 2. Verificar docker-entrypoint
    verificacoes_entrypoint = {
        "Correção Subatividade 150": "'Subatividade 150': '1. Detalhamento do projeto'",
        "Correção admin_id produção": "UPDATE rdo SET admin_id = 2",
        "Correção funcionários órfãos": "UPDATE funcionario SET admin_id = 2",
        "Remoção etapas inválidas": "DELETE FROM rdo_servico_subatividade"
    }
    
    if not verificar_arquivo("docker-entrypoint-production-simple.sh", verificacoes_entrypoint):
        tudo_ok = False
    
    # 3. Verificar Dockerfile
    verificacoes_dockerfile = {
        "Uso do pyproject.toml": "COPY pyproject.toml",
        "Instalação correta": "pip install --no-cache-dir .",
        "Porta 5000": "EXPOSE 5000",
        "Entrypoint correto": "docker-entrypoint-production-simple.sh"
    }
    
    if not verificar_arquivo("Dockerfile", verificacoes_dockerfile):
        tudo_ok = False
    
    # 4. Verificar pyproject.toml
    verificacoes_pyproject = {
        "Flask presente": "flask>=",
        "SQLAlchemy presente": "flask-sqlalchemy>=",
        "Gunicorn presente": "gunicorn>=",
        "PostgreSQL driver": "psycopg2-binary>="
    }
    
    if not verificar_arquivo("pyproject.toml", verificacoes_pyproject):
        tudo_ok = False
    
    print("\n" + "=" * 60)
    
    if tudo_ok:
        print("🎯 RESULTADO: ✅ TODOS OS ARQUIVOS ESTÃO CORRETOS!")
        print("")
        print("🚀 DEPLOY READY - INSTRUÇÕES FINAIS:")
        print("=" * 40)
        print("1. 📤 COMMIT das alterações:")
        print("   git add .")
        print("   git commit -m 'HOTFIX PRODUÇÃO: Correção completa subatividades RDO v10.0'")
        print("")
        print("2. 🚢 DEPLOY no EasyPanel:")
        print("   - Acesse www.sige.cassiovilier.tech/admin")
        print("   - Clique em 'Deploy' ou 'Rebuild'")
        print("   - Aguarde inicialização (2-3 minutos)")
        print("")
        print("3. ✅ CORREÇÕES QUE SERÃO APLICADAS AUTOMATICAMENTE:")
        print("   📝 Subatividade 150 → '1. Detalhamento do projeto'")
        print("   📝 Subatividade 151 → '2. Seleção de materiais'")
        print("   📝 ... (todos os IDs 150-165)")
        print("   👥 Admin_id corrigido para produção (admin_id=2)")
        print("   🧹 Limpeza de registros inválidos")
        print("")
        print("4. 🧪 TESTES PÓS-DEPLOY:")
        print("   - Criar nova RDO")
        print("   - Verificar nomes das subatividades")
        print("   - Testar busca de funcionários")
        print("")
        print("🎉 SISTEMA PRONTO PARA PRODUÇÃO!")
        
    else:
        print("❌ RESULTADO: PROBLEMAS ENCONTRADOS!")
        print("🔧 Corrija os problemas antes de fazer o deploy")
        return False
    
    return tudo_ok

if __name__ == "__main__":
    sucesso = main()
    sys.exit(0 if sucesso else 1)