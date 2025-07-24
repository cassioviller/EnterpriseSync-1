#!/usr/bin/env python3
"""
CORREÇÃO DE PRODUÇÃO - SIGE v8.0
Corrige o erro SQL categoria_id que não existe em produção
Executa no ambiente Docker/EasyPanel para aplicar correções urgentes
"""

import os
import sys

# Script para aplicar correção específica no arquivo views.py em produção
def fix_sql_error():
    print("🔧 CORREÇÃO URGENTE - Erro SQL categoria_id")
    
    # Caminho do arquivo no container
    views_path = '/app/views.py'
    if not os.path.exists(views_path):
        views_path = 'views.py'  # Fallback para ambiente local
    
    if not os.path.exists(views_path):
        print("❌ Arquivo views.py não encontrado!")
        return False
    
    print(f"📝 Editando arquivo: {views_path}")
    
    # Ler conteúdo atual
    with open(views_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Correção específica - substituir query problemática
    old_query = "categorias = db.session.query(Servico.categoria).distinct().all()"
    new_query = "categorias_query = db.session.query(Servico.categoria).distinct().filter(Servico.categoria.isnot(None)).all()"
    
    if old_query in content:
        content = content.replace(old_query, new_query)
        
        # Também corrigir a linha seguinte
        old_list_comp = "categorias = [cat[0] for cat in categorias if cat[0]]"
        new_list_comp = "categorias = [cat[0] for cat in categorias_query if cat[0]]"
        
        if old_list_comp in content:
            content = content.replace(old_list_comp, new_list_comp)
        
        # Salvar arquivo corrigido
        with open(views_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ Correção aplicada com sucesso!")
        print("🔄 Reinicie o container/serviço para aplicar mudanças")
        return True
    else:
        print("⚠️  Query já foi corrigida ou não encontrada")
        return False

if __name__ == "__main__":
    success = fix_sql_error()
    sys.exit(0 if success else 1)