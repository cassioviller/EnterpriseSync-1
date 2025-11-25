#!/usr/bin/env python3
"""Análise de templates HTML - identificar órfãos"""
import re
from pathlib import Path

def main():
    print("🎨 ANÁLISE DE TEMPLATES HTML")
    print("="*80)
    
    # Listar todos templates
    templates = []
    for tmpl in Path('templates').rglob('*.html'):
        rel_path = tmpl.relative_to('templates')
        templates.append(str(rel_path))
    
    print(f"\n📊 Total de templates: {len(templates)}")
    
    # Buscar referências em arquivos Python
    referenciados = set()
    
    py_files = list(Path('.').glob('*.py'))
    
    for py_file in py_files:
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Buscar render_template
            matches = re.findall(r"render_template\s*\(\s*['\"]([^'\"]+)['\"]", content)
            referenciados.update(matches)
            
        except:
            pass
    
    # Normalizar paths (alguns podem usar / outros \)
    templates_set = set(t.replace('\\', '/') for t in templates)
    referenciados_set = set(r.replace('\\', '/') for r in referenciados)
    
    # Templates base (sempre manter)
    templates_base = {
        'base.html', 'base_completo.html', 'base_limpo.html',
        'login.html', 'error.html', '404.html', '500.html'
    }
    
    # Considerar templates que podem extender outros
    templates_extends = set()
    for tmpl in templates:
        try:
            with open(f'templates/{tmpl}', 'r', encoding='utf-8') as f:
                content = f.read()
                if 'extends' in content or 'include' in content:
                    # Pode ser usado por outros templates
                    templates_extends.add(tmpl.replace('\\', '/'))
        except:
            pass
    
    # Órfãos = não referenciados E não extends/include
    orfaos = templates_set - referenciados_set - templates_base - templates_extends
    
    print(f"✅ Templates REFERENCIADOS: {len(referenciados_set)}")
    print(f"🔗 Templates BASE/EXTENDS: {len(templates_base | templates_extends)}")
    print(f"⚠️  Templates ÓRFÃOS: {len(orfaos)}")
    
    # Categorizar por pasta
    por_pasta = {}
    for tmpl in templates:
        pasta = tmpl.split('/')[0] if '/' in tmpl else 'raiz'
        if pasta not in por_pasta:
            por_pasta[pasta] = {'total': 0, 'ref': 0, 'orfao': 0}
        por_pasta[pasta]['total'] += 1
        
        tmpl_norm = tmpl.replace('\\', '/')
        if tmpl_norm in referenciados_set or tmpl_norm in templates_base or tmpl_norm in templates_extends:
            por_pasta[pasta]['ref'] += 1
        else:
            por_pasta[pasta]['orfao'] += 1
    
    print("\n" + "="*80)
    print("\n📁 TEMPLATES POR PASTA:\n")
    
    for pasta in sorted(por_pasta.keys()):
        info = por_pasta[pasta]
        print(f"  {pasta}: {info['total']} total | {info['ref']} em uso | {info['orfao']} órfãos")
    
    # Listar alguns órfãos
    if orfaos:
        print("\n" + "="*80)
        print(f"\n⚠️  EXEMPLOS DE TEMPLATES ÓRFÃOS ({len(orfaos)} total):\n")
        for tmpl in sorted(list(orfaos)[:20]):
            print(f"   • {tmpl}")
        if len(orfaos) > 20:
            print(f"   ... e mais {len(orfaos)-20}")
    
    # Salvar relatório
    with open('relatorio_templates.txt', 'w', encoding='utf-8') as f:
        f.write("RELATÓRIO DE TEMPLATES HTML\n")
        f.write("="*80 + "\n\n")
        f.write(f"Total: {len(templates)}\n")
        f.write(f"Referenciados: {len(referenciados_set)}\n")
        f.write(f"Base/Extends: {len(templates_base | templates_extends)}\n")
        f.write(f"Órfãos: {len(orfaos)}\n\n")
        
        f.write("TEMPLATES REFERENCIADOS:\n")
        for tmpl in sorted(referenciados_set):
            f.write(f"  {tmpl}\n")
        
        f.write("\n\nTEMPLATES ÓRFÃOS:\n")
        for tmpl in sorted(orfaos):
            f.write(f"  {tmpl}\n")
    
    print(f"\n💾 Relatório: relatorio_templates.txt")
    print("\n✅ Análise concluída!\n")

if __name__ == '__main__':
    main()
