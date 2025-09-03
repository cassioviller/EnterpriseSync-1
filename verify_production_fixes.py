#!/usr/bin/env python3
"""
Script de Verificação de Produção - SIGE v8.1
Garante que todas as correções estão aplicadas
"""

import os
import sys
import re

def verify_javascript_fixes():
    """Verificar se todas as correções JavaScript estão presentes"""
    # Tentar ambos os caminhos (desenvolvimento e produção)
    template_paths = [
        "/app/templates/obras/detalhes_obra_profissional.html",  # Produção
        "templates/obras/detalhes_obra_profissional.html",      # Desenvolvimento
        "./templates/obras/detalhes_obra_profissional.html"     # Desenvolvimento relativo
    ]
    
    template_path = None
    for path in template_paths:
        if os.path.exists(path):
            template_path = path
            break
    
    if not template_path:
        print("❌ ERRO: Template não encontrado em nenhum local")
        print(f"   Tentativas: {template_paths}")
        return False
    
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Verificações específicas (correções aplicadas)
    checks = [
        ("DOMContentLoaded", "Event listener DOMContentLoaded"),
        ("atualizarInterfaceSelecao", "Função de atualização de interface"),
        ("if (contadorSelecionados)", "Verificação de segurança para elementos DOM"),
        ("toggleServicoSelecao", "Função de seleção de serviços"),
    ]
    
    success_count = 0
    for pattern, description in checks:
        if pattern in content:
            print(f"✅ {description}: OK")
            success_count += 1
        else:
            print(f"❌ {description}: AUSENTE")
    
    return success_count == len(checks)

def verify_api_endpoints():
    """Verificar se endpoints da API estão corretos"""
    # Tentar ambos os caminhos (desenvolvimento e produção)
    views_paths = [
        "/app/views.py",    # Produção
        "views.py",         # Desenvolvimento
        "./views.py"        # Desenvolvimento relativo
    ]
    
    views_path = None
    for path in views_paths:
        if os.path.exists(path):
            views_path = path
            break
    
    if not views_path:
        print("❌ ERRO: views.py não encontrado em nenhum local")
        print(f"   Tentativas: {views_paths}")
        return False
    
    with open(views_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Verificar endpoint da API de serviços
    if "@main_bp.route('/api/obras/servicos', methods=['POST'])" in content:
        print("✅ API endpoint '/api/obras/servicos': OK")
        return True
    else:
        print("❌ API endpoint '/api/obras/servicos': AUSENTE")
        return False

def main():
    """Verificação principal"""
    print("🔍 SIGE v8.1 - Verificação de Correções de Produção")
    print("=" * 50)
    
    all_checks_passed = True
    
    # Verificar correções JavaScript
    print("\n📋 Verificando correções JavaScript...")
    if not verify_javascript_fixes():
        all_checks_passed = False
    
    # Verificar endpoints da API
    print("\n🌐 Verificando endpoints da API...")
    if not verify_api_endpoints():
        all_checks_passed = False
    
    print("\n" + "=" * 50)
    if all_checks_passed:
        print("✅ TODAS AS CORREÇÕES CONFIRMADAS - PRODUÇÃO PRONTA!")
        sys.exit(0)
    else:
        print("❌ CORREÇÕES AUSENTES - BUILD FALHARÁ!")
        sys.exit(1)

if __name__ == "__main__":
    main()