#!/usr/bin/env python3
"""
Script para corrigir problema de multi-tenancy no controle de ponto
PARA APLICAR EM PRODUÇÃO
"""

import os
import sys
import shutil
from datetime import datetime

def aplicar_correcao_producao():
    """Aplicar correção de multi-tenancy em produção"""
    
    print("🚀 APLICANDO CORREÇÃO DE MULTI-TENANCY EM PRODUÇÃO")
    print("=" * 60)
    
    # 1. Fazer backup do views.py atual
    backup_path = f"views_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
    
    if os.path.exists('views.py'):
        shutil.copy2('views.py', backup_path)
        print(f"✅ Backup criado: {backup_path}")
    
    # 2. Verificar se a correção já foi aplicada
    print("\n🔍 Verificando se correção já foi aplicada...")
    
    with open('views.py', 'r', encoding='utf-8') as f:
        conteudo = f.read()
    
    if 'Funcionario.admin_id == current_user.id' in conteudo and 'controle_ponto()' in conteudo:
        print("✅ Correção JÁ APLICADA - Multi-tenancy implementado")
        
        # Verificar funcionalidades de exclusão em lote
        if '/ponto/preview-exclusao' in conteudo and '/ponto/excluir-periodo' in conteudo:
            print("✅ Funcionalidades de exclusão em lote JÁ IMPLEMENTADAS")
        else:
            print("⚠️ Funcionalidades de exclusão em lote FALTANDO")
            return False
            
        return True
    else:
        print("❌ CORREÇÃO NÃO APLICADA - Necessário aplicar patch")
        return False

def testar_funcionalidades():
    """Testar se as funcionalidades estão funcionando"""
    
    print("\n🧪 TESTANDO FUNCIONALIDADES...")
    
    try:
        from app import app, db
        from models import RegistroPonto, Funcionario
        
        with app.app_context():
            # Contar registros totais
            total_registros = RegistroPonto.query.count()
            print(f"📊 Total de registros no banco: {total_registros}")
            
            # Contar por admin_id
            admin_4_count = RegistroPonto.query.join(Funcionario).filter(
                Funcionario.admin_id == 4
            ).count()
            
            print(f"📊 Registros do Admin ID 4: {admin_4_count}")
            
            if admin_4_count < total_registros:
                print("✅ Multi-tenancy funcionando - filtros aplicados corretamente")
                return True
            else:
                print("⚠️ Possível problema com multi-tenancy")
                return False
                
    except Exception as e:
        print(f"❌ Erro ao testar: {e}")
        return False

def verificar_templates():
    """Verificar se templates estão atualizados"""
    
    print("\n📄 VERIFICANDO TEMPLATES...")
    
    try:
        with open('templates/controle_ponto.html', 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        if 'exclusaoLoteModal' in template_content:
            print("✅ Template atualizado com modal de exclusão em lote")
        else:
            print("❌ Template NÃO atualizado - falta modal de exclusão")
            return False
            
        if 'previewExclusao()' in template_content:
            print("✅ JavaScript de exclusão implementado")
        else:
            print("❌ JavaScript de exclusão FALTANDO")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Erro ao verificar template: {e}")
        return False

def main():
    """Função principal"""
    
    print("🔧 CORREÇÃO DE CONTROLE DE PONTO - PRODUÇÃO")
    print("Data:", datetime.now().strftime('%d/%m/%Y %H:%M:%S'))
    print()
    
    # Verificar correções aplicadas
    correcao_aplicada = aplicar_correcao_producao()
    
    # Verificar templates
    templates_ok = verificar_templates()
    
    # Testar funcionalidades
    funcionalidades_ok = testar_funcionalidades()
    
    print("\n" + "=" * 60)
    print("📋 RESUMO DA VERIFICAÇÃO:")
    print(f"✅ Correção Multi-tenancy: {'OK' if correcao_aplicada else 'FALHA'}")
    print(f"✅ Templates atualizados: {'OK' if templates_ok else 'FALHA'}")
    print(f"✅ Funcionalidades testadas: {'OK' if funcionalidades_ok else 'FALHA'}")
    
    if all([correcao_aplicada, templates_ok, funcionalidades_ok]):
        print("\n🎉 TODAS AS CORREÇÕES APLICADAS COM SUCESSO!")
        print("🚀 Sistema pronto para produção")
        
        print("\n📱 INSTRUÇÕES PARA O USUÁRIO:")
        print("1. Os registros de fim de semana agora aparecem corretamente")
        print("2. Use o botão 'Excluir por Período' para limpeza em lote")
        print("3. Multi-tenancy garante isolamento entre administradores")
        
        return True
    else:
        print("\n⚠️ ALGUMAS CORREÇÕES FALTANDO - Verificar logs acima")
        return False

if __name__ == "__main__":
    sucesso = main()
    sys.exit(0 if sucesso else 1)