#!/usr/bin/env python3
"""
APLICAR HOTFIX IMEDIATAMENTE - SIGE v8.0
Para uso em produção quando não é possível aguardar reinicialização do container
"""

def aplicar_hotfix():
    print("🚨 APLICANDO HOTFIX URGENTE - Erro SQL categoria_id")
    
    import os
    from app import app
    
    # Caminho do arquivo
    views_path = 'views.py'
    
    if not os.path.exists(views_path):
        print("❌ Arquivo views.py não encontrado!")
        return False
    
    print("📝 Lendo arquivo views.py...")
    
    # Ler conteúdo atual
    with open(views_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Flag de mudança
    mudancas_feitas = False
    
    # Correção 1: Query principal
    old_query = "categorias = db.session.query(Servico.categoria).distinct().all()"
    new_query = "categorias_query = db.session.query(Servico.categoria).distinct().filter(Servico.categoria.isnot(None)).all()"
    
    if old_query in content:
        content = content.replace(old_query, new_query)
        mudancas_feitas = True
        print("✅ Correção 1: Query de categorias corrigida")
    
    # Correção 2: List comprehension
    old_list_comp = "categorias = [cat[0] for cat in categorias if cat[0]]"
    new_list_comp = "categorias = [cat[0] for cat in categorias_query if cat[0]]"
    
    if old_list_comp in content:
        content = content.replace(old_list_comp, new_list_comp)
        mudancas_feitas = True
        print("✅ Correção 2: List comprehension corrigida")
    
    # Aplicar mudanças se necessário
    if mudancas_feitas:
        print("💾 Salvando correções...")
        with open(views_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("✅ HOTFIX APLICADO COM SUCESSO!")
        print("🔄 Reinicie o serviço Flask para aplicar as mudanças:")
        print("   - Modo desenvolvimento: Ctrl+C e reiniciar")
        print("   - Produção: Reiniciar container/processo")
        return True
    else:
        print("⚠️  Nenhuma correção necessária - arquivo já atualizado")
        return False

if __name__ == "__main__":
    aplicar_hotfix()