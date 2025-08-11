"""
Script para corrigir imports circulares no SIGE v8.0
Conforme documentação de debugging fornecida
"""

import re
import os
import glob

def fix_imports_in_file(filepath):
    """Corrige imports circulares em um arquivo específico"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Padrão 1: from app import db ANTES de from models import
        if 'from app import db' in content and 'from models import' in content:
            # Reorganizar ordem dos imports
            lines = content.split('\n')
            new_lines = []
            db_import = None
            models_import = None
            
            for line in lines:
                if line.strip().startswith('from app import db'):
                    db_import = line
                elif line.strip().startswith('from models import'):
                    models_import = line
                else:
                    new_lines.append(line)
            
            if db_import and models_import:
                # Inserir imports na ordem correta
                for i, line in enumerate(new_lines):
                    if line.strip().startswith('from flask') or line.strip().startswith('import'):
                        # Inserir após outros imports básicos
                        if i < len(new_lines) - 1:
                            new_lines.insert(i + 1, models_import)
                            new_lines.insert(i + 2, db_import)
                            break
                
                content = '\n'.join(new_lines)
        
        # Padrão 2: Mover imports de models para dentro de funções quando necessário
        if 'from models import *' in content and len(content.split('from models import')[1].split('\n')[0]) > 100:
            # Import muito grande, mover para função
            print(f"⚠️  Import muito grande em {filepath}, considerando refatoração")
        
        # Salvar apenas se houve mudanças
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Corrigido: {filepath}")
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ Erro ao corrigir {filepath}: {e}")
        return False

def main():
    """Executa correções em todos os arquivos Python"""
    print("🔧 INICIANDO CORREÇÃO DE IMPORTS CIRCULARES")
    print("=" * 50)
    
    # Arquivos Python no diretório atual
    python_files = glob.glob("*.py")
    
    # Remover arquivos que não devem ser modificados
    exclude_files = ['fix_circular_imports.py', 'main.py']
    python_files = [f for f in python_files if f not in exclude_files]
    
    fixed_files = 0
    total_files = len(python_files)
    
    for filepath in python_files:
        if fix_imports_in_file(filepath):
            fixed_files += 1
    
    print("\n" + "=" * 50)
    print(f"📊 RESULTADO: {fixed_files}/{total_files} arquivos corrigidos")
    
    if fixed_files > 0:
        print("\n🔄 Reinicie o servidor para aplicar as correções")
    else:
        print("\n✅ Nenhuma correção necessária")

if __name__ == "__main__":
    main()