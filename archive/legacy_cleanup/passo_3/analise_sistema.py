#!/usr/bin/env python3
"""
Análise automatizada do sistema SIGE - Identificar arquivos órfãos e dependências
"""
import os
import re
import ast
from pathlib import Path
from collections import defaultdict

def analisar_imports_python():
    """Analisa todos os arquivos Python e mapeia imports"""
    
    arquivos_python = []
    imports_encontrados = defaultdict(set)
    
    # Listar todos arquivos .py no diretório raiz
    for file in Path('.').glob('*.py'):
        if file.name.startswith('analise_'):
            continue  # Pular script de análise
        arquivos_python.append(file.name)
    
    print(f"📊 Total de arquivos Python encontrados: {len(arquivos_python)}")
    print("="*80)
    
    # Para cada arquivo, encontrar imports
    for arquivo in arquivos_python:
        try:
            with open(arquivo, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Buscar padrões de import
            # import nome_modulo
            # from nome_modulo import ...
            import_patterns = [
                r'^\s*import\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                r'^\s*from\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+import',
            ]
            
            for pattern in import_patterns:
                matches = re.findall(pattern, content, re.MULTILINE)
                for match in matches:
                    # Converter module name para filename
                    possible_file = f"{match}.py"
                    if possible_file in arquivos_python:
                        imports_encontrados[arquivo].add(possible_file)
        
        except Exception as e:
            print(f"⚠️  Erro ao processar {arquivo}: {e}")
    
    return arquivos_python, imports_encontrados

def identificar_arquivos_orfaos(arquivos_python, imports_encontrados):
    """Identifica arquivos que não são importados por ninguém"""
    
    # Arquivos críticos que sempre devem ser mantidos
    arquivos_criticos = {
        'app.py', 'main.py', 'models.py', 'auth.py', 'views.py',
        'migrations.py', 'wsgi.py', 'gunicorn_config.py'
    }
    
    # Todos os arquivos que são importados
    arquivos_importados = set()
    for imports in imports_encontrados.values():
        arquivos_importados.update(imports)
    
    # Adicionar arquivos críticos como importados
    arquivos_importados.update(arquivos_criticos)
    
    # Arquivos órfãos = não são importados por ninguém
    arquivos_orfaos = set(arquivos_python) - arquivos_importados - arquivos_criticos
    
    return arquivos_orfaos, arquivos_importados

def categorizar_arquivos_orfaos(arquivos_orfaos):
    """Categoriza arquivos órfãos por tipo"""
    
    categorias = {
        'scripts_migracao': [],
        'scripts_deploy': [],
        'scripts_correcao': [],
        'scripts_teste': [],
        'scripts_populacao': [],
        'outros': []
    }
    
    for arquivo in sorted(arquivos_orfaos):
        nome_lower = arquivo.lower()
        
        if any(x in nome_lower for x in ['migration', 'migrate', 'adicionar_', 'atualizar_', 'create_']):
            categorias['scripts_migracao'].append(arquivo)
        elif any(x in nome_lower for x in ['deploy', 'producao', 'production']):
            categorias['scripts_deploy'].append(arquivo)
        elif any(x in nome_lower for x in ['fix_', 'correcao', 'corrigir', 'validar']):
            categorias['scripts_correcao'].append(arquivo)
        elif any(x in nome_lower for x in ['test', 'teste']):
            categorias['scripts_teste'].append(arquivo)
        elif any(x in nome_lower for x in ['popul', 'gerar_', 'seed']):
            categorias['scripts_populacao'].append(arquivo)
        else:
            categorias['outros'].append(arquivo)
    
    return categorias

def validar_arquivo_seguro_remover(arquivo):
    """Valida se arquivo pode ser removido com segurança usando grep"""
    
    # Buscar referências ao arquivo em todo o projeto
    arquivo_sem_ext = arquivo.replace('.py', '')
    
    # Verificar se é importado em algum lugar
    cmd_import = f"grep -r 'import {arquivo_sem_ext}' . --include='*.py' 2>/dev/null | wc -l"
    cmd_from = f"grep -r 'from {arquivo_sem_ext}' . --include='*.py' 2>/dev/null | wc -l"
    
    import subprocess
    try:
        result_import = subprocess.run(cmd_import, shell=True, capture_output=True, text=True)
        result_from = subprocess.run(cmd_from, shell=True, capture_output=True, text=True)
        
        count_import = int(result_import.stdout.strip())
        count_from = int(result_from.stdout.strip())
        
        total = count_import + count_from
        
        return total == 0, total
    except:
        return False, -1

def main():
    print("🔍 ANÁLISE AUTOMATIZADA DO SISTEMA SIGE")
    print("="*80)
    print()
    
    # 1. Analisar imports
    arquivos_python, imports_encontrados = analisar_imports_python()
    print()
    
    # 2. Identificar órfãos
    arquivos_orfaos, arquivos_importados = identificar_arquivos_orfaos(arquivos_python, imports_encontrados)
    
    print(f"✅ Arquivos IMPORTADOS (em uso): {len(arquivos_importados)}")
    print(f"⚠️  Arquivos ÓRFÃOS (não importados): {len(arquivos_orfaos)}")
    print(f"📊 Percentual órfão: {len(arquivos_orfaos)/len(arquivos_python)*100:.1f}%")
    print()
    print("="*80)
    
    # 3. Categorizar órfãos
    categorias = categorizar_arquivos_orfaos(arquivos_orfaos)
    
    print("\n📋 ARQUIVOS ÓRFÃOS POR CATEGORIA:")
    print("="*80)
    
    total_validados_seguros = 0
    
    for categoria, arquivos in categorias.items():
        if arquivos:
            print(f"\n🗂️  {categoria.upper()} ({len(arquivos)} arquivos):")
            for arquivo in arquivos[:10]:  # Mostrar apenas primeiros 10
                seguro, count = validar_arquivo_seguro_remover(arquivo)
                status = "✅ SEGURO" if seguro else f"⚠️  USADO ({count} refs)"
                print(f"   {status}: {arquivo}")
                if seguro:
                    total_validados_seguros += 1
            
            if len(arquivos) > 10:
                print(f"   ... e mais {len(arquivos) - 10} arquivos")
    
    print()
    print("="*80)
    print(f"\n✅ Total de arquivos validados SEGUROS para remoção: {total_validados_seguros}")
    print()
    
    # 4. Gerar relatório
    with open('relatorio_analise_sistema.txt', 'w', encoding='utf-8') as f:
        f.write("RELATÓRIO DE ANÁLISE DO SISTEMA SIGE\n")
        f.write("="*80 + "\n\n")
        f.write(f"Total de arquivos Python: {len(arquivos_python)}\n")
        f.write(f"Arquivos em uso (importados): {len(arquivos_importados)}\n")
        f.write(f"Arquivos órfãos: {len(arquivos_orfaos)}\n")
        f.write(f"Percentual órfão: {len(arquivos_orfaos)/len(arquivos_python)*100:.1f}%\n\n")
        
        f.write("ARQUIVOS EM USO:\n")
        f.write("-"*80 + "\n")
        for arquivo in sorted(arquivos_importados):
            f.write(f"  - {arquivo}\n")
        
        f.write("\n\nARQUIVOS ÓRFÃOS POR CATEGORIA:\n")
        f.write("-"*80 + "\n")
        for categoria, arquivos in categorias.items():
            if arquivos:
                f.write(f"\n{categoria.upper()} ({len(arquivos)}):\n")
                for arquivo in sorted(arquivos):
                    seguro, count = validar_arquivo_seguro_remover(arquivo)
                    status = "SEGURO" if seguro else f"USADO ({count} refs)"
                    f.write(f"  [{status}] {arquivo}\n")
    
    print("💾 Relatório salvo em: relatorio_analise_sistema.txt")

if __name__ == '__main__':
    main()
