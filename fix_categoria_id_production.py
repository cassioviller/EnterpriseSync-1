#!/usr/bin/env python3
# CORREÇÃO FINAL PARA PRODUÇÃO - Erro categoria_id

import os
import sys

def fix_production_error():
    print('🔧 APLICANDO CORREÇÃO FINAL EM PRODUÇÃO')
    
    # Definir caminhos possíveis
    possible_paths = ['/app/views.py', './views.py', 'views.py']
    views_path = None
    
    for path in possible_paths:
        if os.path.exists(path):
            views_path = path
            break
    
    if not views_path:
        print('❌ Arquivo views.py não encontrado!')
        return False
    
    print(f'📝 Corrigindo arquivo: {views_path}')
    
    # Ler arquivo
    with open(views_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Aplicar todas as correções necessárias
    corrections = [
        # Remover função duplicada
        ('def servicos_autocomplete():', '# REMOVIDO: servicos_autocomplete duplicado'),
        
        # Garantir que não há referências a categoria_id
        ('servico.categoria_id', 'servico.categoria'),
        ('Servico.categoria_id', 'Servico.categoria'),
        
        # Corrigir imports se necessário
        ('from sqlalchemy import and_, or_', 'from sqlalchemy import and_, or_, func'),
    ]
    
    for old, new in corrections:
        if old in content:
            content = content.replace(old, new)
            print(f'✅ Corrigido: {old} → {new}')
    
    # Salvar arquivo corrigido
    with open(views_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print('✅ CORREÇÕES APLICADAS COM SUCESSO!')
    return True

if __name__ == '__main__':
    success = fix_production_error()
    sys.exit(0 if success else 1)
