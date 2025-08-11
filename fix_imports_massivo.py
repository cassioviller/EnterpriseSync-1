"""
Correção massiva de imports em todos os arquivos do SIGE v8.0
Resolve problemas de sintaxe e imports circulares
"""

import os
import re
import glob

def fix_file_imports(filepath):
    """Corrige imports em um arquivo específico"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 1. Substituir "from app import db" por "from models import db"
        content = content.replace('from app import db', 'from models import db')
        
        # 2. Corrigir imports malformados de models
        # Procurar padrões como "from models import (Class1, Class2,\nfrom app import db"
        pattern = r'from models import \([^)]+\)\s*\n\s*from app import db'
        if re.search(pattern, content):
            # Remover a linha "from app import db" que está dentro do import de models
            content = re.sub(r'\nfrom app import db', '', content)
            # Adicionar "from models import db" no início se não existir
            if 'from models import db' not in content:
                content = 'from models import db\n' + content
        
        # 3. Corrigir imports quebrados (multi-linha malformada)
        # Padrão: from models import (Class1,\nfrom something import\n Class2)
        lines = content.split('\n')
        new_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Se encontrar import de models que termina com vírgula mas não fecha parênteses
            if line.startswith('from models import (') and line.endswith(','):
                # Procurar o fechamento dos parênteses
                import_lines = [line]
                i += 1
                
                while i < len(lines):
                    next_line = lines[i].strip()
                    
                    # Se encontrar outro from import no meio, é erro de sintaxe
                    if next_line.startswith('from ') and 'import' in next_line and not next_line.endswith(')'):
                        # Ignorar esta linha problemática
                        i += 1
                        continue
                    
                    import_lines.append(next_line)
                    
                    if ')' in next_line:
                        break
                    i += 1
                
                # Reconstruir import correto
                all_imports = ' '.join(import_lines).replace('\n', ' ')
                # Limpar espaços extras
                all_imports = re.sub(r'\s+', ' ', all_imports)
                new_lines.append(all_imports)
            else:
                new_lines.append(lines[i])
            
            i += 1
        
        content = '\n'.join(new_lines)
        
        # 4. Garantir que "from models import db" está no topo
        if 'from models import db' in content:
            content = content.replace('from models import db\n', '')
            content = 'from models import db\n' + content
        
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
    """Executa correção massiva"""
    print("🔧 CORREÇÃO MASSIVA DE IMPORTS")
    print("=" * 50)
    
    # Arquivos Python importantes
    arquivos_criticos = [
        'almoxarifado_utils.py',
        'almoxarifado_views.py',
        'relatorios_funcionais.py',
        'folha_pagamento_views.py',
        'contabilidade_views.py',
        'utils.py',
        'kpis_engine.py'
    ]
    
    fixed = 0
    total = 0
    
    for arquivo in arquivos_criticos:
        if os.path.exists(arquivo):
            total += 1
            if fix_file_imports(arquivo):
                fixed += 1
    
    # Também corrigir todos os *_utils.py e *_views.py
    pattern_files = glob.glob("*_utils.py") + glob.glob("*_views.py")
    
    for arquivo in pattern_files:
        if arquivo not in arquivos_criticos:  # Evitar duplicação
            total += 1
            if fix_file_imports(arquivo):
                fixed += 1
    
    print(f"\n📊 RESULTADO: {fixed}/{total} arquivos corrigidos")
    
    if fixed > 0:
        print("🔄 Reinicie o servidor para aplicar correções")
    
    return fixed > 0

if __name__ == "__main__":
    main()